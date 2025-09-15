from __future__ import annotations
from functools import lru_cache
from typing import Optional, List, Any
import threading
import time
from .base import BaseTTSEngine, EngineRegistry
from ..utils.logging import get_logger, log_engine_operation, log_error_with_context

try:
    from TTS.api import TTS as _CoquiTTS
except ImportError:
    try:
        from coqui_tts.api import TTS as _CoquiTTS  # type: ignore
    except ImportError as e:
        raise ImportError(
            "No se encontró el paquete Coqui TTS. Instala con: pip install TTS"
        ) from e


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
            try:
                import torch
                use_gpu = bool(torch.cuda.is_available())
                self.logger.debug(f"GPU auto-detection: {use_gpu}")
            except Exception:
                use_gpu = False
                self.logger.debug("GPU auto-detection failed, using CPU")

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
            try:
                import numpy as np, librosa
                waveform = librosa.resample(
                    np.asarray(waveform), orig_sr=orig_sr, target_sr=target_sr
                )
                orig_sr = target_sr
            except ImportError as e:
                raise RuntimeError(f"Librerías requeridas para resample no disponibles (numpy, librosa): {e}") from e
            except Exception as e:
                raise RuntimeError(f"Error al re-muestrear audio de {orig_sr}Hz a {target_sr}Hz: {e}") from e

        try:
            import io, soundfile as sf
            buf = io.BytesIO()
            sf.write(buf, waveform, orig_sr, format="WAV", subtype="PCM_16")
            wav_bytes = buf.getvalue()

            duration = time.time() - start_time
            log_engine_operation(
                self.logger, "coqui", "synthesis_complete",
                text_length=len(text), duration=f"{duration:.2f}s",
                output_size=len(wav_bytes), sample_rate=orig_sr
            )

            return wav_bytes
        except ImportError as e:
            log_error_with_context(
                self.logger, e,
                {"operation": "wav_generation", "model": self.model_name}
            )
            raise RuntimeError(f"Librería soundfile no disponible para generar WAV: {e}") from e
        except Exception as e:
            log_error_with_context(
                self.logger, e,
                {"operation": "wav_generation", "model": self.model_name, "sample_rate": orig_sr}
            )
            raise RuntimeError(f"Error generando WAV con sample_rate {orig_sr}Hz: {e}") from e


# Registro automático
EngineRegistry.register("coqui", lambda model, **kw: CoquiEngine(model, **kw))