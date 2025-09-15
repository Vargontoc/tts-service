from __future__ import annotations
from functools import lru_cache
from typing import Optional, List, Any
import threading
from .base import BaseTTSEngine, EngineRegistry

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
        if use_gpu is None:
            try:
                import torch
                use_gpu = bool(torch.cuda.is_available())
            except Exception:
                use_gpu = False
        super().__init__(model_name, use_gpu=use_gpu, **kwargs)
        self.model_name = model_name
        self.use_gpu = use_gpu
        self._lock = threading.Lock()
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
        if not text or not text.strip():
            raise ValueError("Texto vacío")

        if speaker is not None and self.list_speakers():
            speakers = self.list_speakers()
            if isinstance(speaker, int):
                if speaker < 0 or speaker >= len(speakers):
                    raise ValueError(f"Índice speaker fuera de rango (0-{len(speakers)-1})")
            elif isinstance(speaker, str) and speaker not in speakers:
                raise ValueError(f"Speaker '{speaker}' no existe. Disponibles: {speakers}")

        with self._lock:
            if speaker is not None:
                out = self.tts.tts(text=text, speaker=speaker)  # type: ignore
            else:
                out = self.tts.tts(text=text)  # type: ignore

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
            return buf.getvalue()
        except ImportError as e:
            raise RuntimeError(f"Librería soundfile no disponible para generar WAV: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Error generando WAV con sample_rate {orig_sr}Hz: {e}") from e


# Registro automático
EngineRegistry.register("coqui", lambda model, **kw: CoquiEngine(model, **kw))