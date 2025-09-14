import io
import numpy as np
import soundfile as sf
from typing import Optional

# Simple prosody post-processing (time-stretch, pitch, energy)
# NOTE: This is a lightweight placeholder; for quality pitch shifting
# a phase vocoder (librosa.effects.pitch_shift) could be used.

try:
    import librosa
except ImportError:  # pragma: no cover
    librosa = None  # type: ignore


def apply_prosody(wav_bytes: bytes, speaking_rate: Optional[float], pitch_shift: Optional[float], energy: Optional[float]) -> bytes:
    if not any([speaking_rate, pitch_shift, energy]):
        return wav_bytes
    try:
        data, sr = sf.read(io.BytesIO(wav_bytes))
        if data.ndim > 1:
            data = data.mean(axis=1)  # mono mix
        if energy and energy != 1.0:
            data = np.clip(data * energy, -1.0, 1.0)
        if librosa:
            if speaking_rate and speaking_rate != 1.0:
                data = librosa.effects.time_stretch(data, rate=1.0 / speaking_rate)
            if pitch_shift and pitch_shift != 0:
                data = librosa.effects.pitch_shift(data, sr=sr, n_steps=pitch_shift)
        buf = io.BytesIO()
        sf.write(buf, data, sr, format='WAV', subtype='PCM_16')
        return buf.getvalue()
    except Exception:
        return wav_bytes
