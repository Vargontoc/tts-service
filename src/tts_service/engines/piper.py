from pathlib import Path
import subprocess, tempfile, os
from typing import Optional


class PiperEngine: 
    def __init__(self, model_path: str, config_path: Optional[str] = None):
        self.model_path = Path(model_path).resolve()
    
        self.config_path = Path(config_path).resolve() if config_path else None
       
        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {self.model_path}")
        if self.config_path and not self.config_path.exists():
            raise FileNotFoundError(f"Piper config not found: {self.config_path}")
        
    def synthesize_wav(
        self,
        text: str,
        sample_rate: Optional[int] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        speaker: Optional[int] = None
        ) -> bytes :
        
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8",delete=False) as tf:
            tf.write(text.strip() + "\n")
            tf_path = tf.name
        try:
            
            cmd = ["piper", "--model", str(self.model_path), "--output_file", "-", "--input_file", tf_path]
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
            
            print("The command is {}".format(proc.args))
            if proc.returncode != 0:
                raise RuntimeError(f"Piper error ({proc.returncode}):{proc.stderr.decode('utf-8', 'ignore')}")
            return proc.stdout
        finally:
            try:
                os.remove(tf_path)
            except Exception:
                pass