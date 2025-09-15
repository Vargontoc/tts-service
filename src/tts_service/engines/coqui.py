from __future__ import annotations
from functools import lru_cache
from typing import Optional, List, Any
import threading
import time
from .base import BaseTTSEngine, EngineRegistry
from ..utils.logging import get_logger, log_engine_operation, log_error_with_context
from ..utils.dependencies import safe_import_coqui_tts, safe_import_torch, dependency_manager

# Import Coqui TTS de forma segura
_CoquiTTS, _coqui_error = safe_import_coqui_tts()
if _CoquiTTS is None:
    raise ImportError(
        f"Coqui TTS no está disponible. "
        f"Error: {_coqui_error}. "
        f"Instalar con: pip install TTS"
    )


@lru_cache(maxsize=4)
def _get_tts_instance(model_name: str, use_gpu: bool = False):
    # model_name debería ser un identificador válido para la API de Coqui
    return _CoquiTTS(model_name, gpu=use_gpu)  # type: ignore


class CoquiEngine(BaseTTSEngine):
    """
    Motor Coqui TTS.
    """
    def __init__(self, model_name: str, use_gpu: Optional[bool] = None, **kwargs: Any):
        self.logger = get_logger(f"tts_service.engines.coqui")

        if use_gpu is None:
            torch = safe_import_torch()
            if torch:
                try:
                    use_gpu = bool(torch.cuda.is_available())
                    self.logger.debug(f"GPU auto-detection: {use_gpu}")
                except Exception as e:
                    use_gpu = False
                    self.logger.debug(f"GPU detection failed: {e}, using CPU")
            else:
                use_gpu = False
                self.logger.debug("PyTorch not available, using CPU")

        super().__init__(model_name, use_gpu=use_gpu, **kwargs)
        self.model_name = model_name
        self.use_gpu = use_gpu
        self._lock = threading.Lock()

        log_engine_operation(
            self.logger, "coqui", "engine_init",
            model=model_name, use_gpu=use_gpu
        )

        self.tts = _get_tts_instance(model_name, self.use_gpu)

    def list_speakers(self) -> List[str]:
        speakers = getattr(self.tts, "speakers", None)
        if speakers is None:
            return []
        return list(speakers) if isinstance(speakers, (list, tuple)) else []

    def synthesize_wav(
        self,
        text: str,
        sample_rate: Optional[int] = None,
        speaker: Optional[int | str] = None,
        **kwargs: Any
    ) -> bytes:
        start_time = time.time()

        log_engine_operation(
            self.logger, "coqui", "synthesis_start",
            text_length=len(text), sample_rate=sample_rate, speaker=speaker
        )

        if not text or not text.strip():
            raise ValueError("Texto vacío")

        if speaker is not None and self.list_speakers():
            speakers = self.list_speakers()
            if isinstance(speaker, int):
                if speaker < 0 or speaker >= len(speakers):
                    raise ValueError(f"Índice speaker fuera de rango (0-{len(speakers)-1})")
            elif isinstance(speaker, str) and speaker not in speakers:
                raise ValueError(f"Speaker '{speaker}' no existe. Disponibles: {speakers}")

        try:
            with self._lock:
                if speaker is not None:
                    out = self.tts.tts(text=text, speaker=speaker)  # type: ignore
                else:
                    out = self.tts.tts(text=text)  # type: ignore
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {"operation": "tts_synthesis", "model": self.model_name, "text_length": len(text)}
            )
            raise

        if isinstance(out, tuple):
            waveform, orig_sr = out[0], out[1]
        else:
            waveform = out
            orig_sr = getattr(self.tts, "output_sample_rate", 22050)

        target_sr = sample_rate or orig_sr
        if target_sr != orig_sr:
            numpy = dependency_manager.get_optional_dependency("numpy")
            librosa = dependency_manager.get_optional_dependency("librosa")

            if not numpy or not librosa:
                missing_deps = []
                if not numpy: missing_deps.append("numpy")
                if not librosa: missing_deps.append("librosa")
                raise RuntimeError(
                    f"Librerías requeridas para resample no disponibles: {', '.join(missing_deps)}. "
                    f"Instalar con: pip install {' '.join(missing_deps)}"
                )

            try:
                waveform = librosa.resample(
                    numpy.asarray(waveform), orig_sr=orig_sr, target_sr=target_sr
                )
                orig_sr = target_sr
            except Exception as e:
                raise RuntimeError(f"Error al re-muestrear audio de {orig_sr}Hz a {target_sr}Hz: {e}") from e

        soundfile = dependency_manager.get_optional_dependency("soundfile")
        if not soundfile:
            raise RuntimeError(
                "SoundFile no está disponible para generar WAV. "
                "Instalar con: pip install soundfile"
            )

        try:
            import io
            buf = io.BytesIO()
            soundfile.write(buf, waveform, orig_sr, format="WAV", subtype="PCM_16")
            wav_bytes = buf.getvalue()

            duration = time.time() - start_time
            log_engine_operation(
                self.logger, "coqui", "synthesis_complete",
                text_length=len(text), duration=f"{duration:.2f}s",
                output_size=len(wav_bytes), sample_rate=orig_sr
            )

            return wav_bytes
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {"operation": "wav_generation", "model": self.model_name, "sample_rate": orig_sr}
            )
            raise RuntimeError(f"Error generando WAV con sample_rate {orig_sr}Hz: {e}") from e


# Registro automático
EngineRegistry.register("coqui", lambda model, **kw: CoquiEngine(model, **kw))