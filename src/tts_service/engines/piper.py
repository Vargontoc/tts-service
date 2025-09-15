from pathlib import Path
import shutil
import sys
import subprocess, tempfile, os
from typing import Optional, Any
from .base import BaseTTSEngine, EngineRegistry


class PiperEngine(BaseTTSEngine): 
    def __init__(self, model: str, config_path: Optional[str] = None, **kwargs: Any):
        super().__init__(model, config_path=config_path, **kwargs)
        self.model_path = Path(model).resolve()
        self.config_path = Path(config_path).resolve() if config_path else None
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {self.model_path}")
        if self.config_path and not self.config_path.exists():
            raise FileNotFoundError(f"Piper config not found: {self.config_path}")
        self._piper_exe = shutil.which("piper")
        self._use_module = self._piper_exe is None
        
    def synthesize_wav(
        self,
        text: str,
        sample_rate: Optional[int] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        speaker: Optional[int] = None,
        **kwargs: Any
        ) -> bytes :
        if not text or not text.strip():
            raise ValueError("Texto vacío")
        
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8",delete=False) as tf:
            tf.write(text.strip() + "\n")
            tf_path = tf.name
        try:
            
            cmd = []
            if self._use_module:
                cmd = [sys.executable, "-m", "piper"]
            else:
                cmd = [self._piper_exe]
                 
            cmd += ["--model", str(self.model_path), "--output_file", "-", "--input_file", tf_path]
            if self.config_path:
                cmd += ["--config", str(self.config_path)]

            if length_scale:
                cmd += ["--length_scale", str(length_scale)]
            if noise_scale:
                cmd += ["--noise_scale", str(noise_scale)]
            if noise_w:
                cmd += ["--noise_w", str(noise_w)]
            if speaker is not None:
                cmd += ["--speaker", str(speaker)]
                
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False)
            
            if proc.returncode != 0:
                raise RuntimeError(f"Piper error ({proc.returncode}):{proc.stderr.decode('utf-8', 'ignore')}")
            raw_wav = proc.stdout
            if sample_rate is None:
                return raw_wav
            # If different, resample
            try:
                import io, wave, numpy as np, soundfile as sf, librosa
                with wave.open(io.BytesIO(raw_wav), 'rb') as wf:
                    orig_sr = wf.getframerate()
                if orig_sr == sample_rate:
                    return raw_wav
                # Load original data
                data, orig_sr_2 = sf.read(io.BytesIO(raw_wav))
                if orig_sr_2 != orig_sr:
                    orig_sr = orig_sr_2
                resampled = librosa.resample(data, orig_sr=orig_sr, target_sr=sample_rate)
                out_buf = io.BytesIO()
                sf.write(out_buf, resampled, sample_rate, format='WAV', subtype='PCM_16')
                return out_buf.getvalue()
            except ImportError:
                # Librerías de resampling no disponibles, devolver audio original
                return raw_wav
            except Exception:
                # Error durante resampling, devolver audio original
                return raw_wav
        finally:
            try:
                os.remove(tf_path)
            except Exception:
                pass


# Registro
EngineRegistry.register("piper", lambda model, **kw: PiperEngine(model, **kw))