from pathlib import Path
import shutil
import sys
import subprocess, tempfile, os
import time
from typing import Optional, Any
from .base import BaseTTSEngine, EngineRegistry
from ..utils.logging import get_logger, log_engine_operation, log_error_with_context
from ..utils.dependencies import dependency_manager


class PiperEngine(BaseTTSEngine):
    def __init__(self, model: str, config_path: Optional[str] = None, **kwargs: Any):
        self.logger = get_logger("tts_service.engines.piper")

        super().__init__(model, config_path=config_path, **kwargs)
        self.model_path = Path(model).resolve()
        self.config_path = Path(config_path).resolve() if config_path else None

        if not self.model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {self.model_path}")
        if self.config_path and not self.config_path.exists():
            raise FileNotFoundError(f"Piper config not found: {self.config_path}")

        self._piper_exe = shutil.which("piper")
        self._use_module = self._piper_exe is None

        log_engine_operation(
            self.logger, "piper", "engine_init",
            model=str(self.model_path), config=str(self.config_path),
            use_module=self._use_module
        )
        
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
        start_time = time.time()

        log_engine_operation(
            self.logger, "piper", "synthesis_start",
            text_length=len(text), sample_rate=sample_rate,
            length_scale=length_scale, noise_scale=noise_scale, speaker=speaker
        )

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
                
            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False)

                if proc.returncode != 0:
                    error_msg = proc.stderr.decode('utf-8', 'ignore')
                    log_error_with_context(
                        self.logger, RuntimeError(f"Piper subprocess failed with code {proc.returncode}"),
                        {"operation": "piper_subprocess", "error_output": error_msg, "command": cmd[0:3]}
                    )
                    raise RuntimeError(f"Piper error ({proc.returncode}):{error_msg}")

                raw_wav = proc.stdout
                if sample_rate is None:
                    duration = time.time() - start_time
                    log_engine_operation(
                        self.logger, "piper", "synthesis_complete",
                        text_length=len(text), duration=f"{duration:.2f}s", output_size=len(raw_wav)
                    )
                    return raw_wav
            except Exception as e:
                log_error_with_context(
                    self.logger, e,
                    {"operation": "piper_execution", "model": str(self.model_path)}
                )
                raise
            # If different, resample
            import io
            import wave

            # Verificar disponibilidad de dependencias de resampling
            numpy = dependency_manager.get_optional_dependency("numpy")
            soundfile = dependency_manager.get_optional_dependency("soundfile")
            librosa = dependency_manager.get_optional_dependency("librosa")

            if not all([numpy, soundfile, librosa]):
                missing_deps = []
                if not numpy: missing_deps.append("numpy")
                if not soundfile: missing_deps.append("soundfile")
                if not librosa: missing_deps.append("librosa")

                self.logger.warning(
                    f"Resampling libraries not available: {', '.join(missing_deps)}. "
                    f"Returning original audio"
                )
                duration = time.time() - start_time
                log_engine_operation(
                    self.logger, "piper", "synthesis_complete",
                    text_length=len(text), duration=f"{duration:.2f}s",
                    output_size=len(raw_wav), warning="no_resample_libs"
                )
                return raw_wav

            try:
                with wave.open(io.BytesIO(raw_wav), 'rb') as wf:
                    orig_sr = wf.getframerate()

                if orig_sr == sample_rate:
                    duration = time.time() - start_time
                    log_engine_operation(
                        self.logger, "piper", "synthesis_complete",
                        text_length=len(text), duration=f"{duration:.2f}s",
                        output_size=len(raw_wav), sample_rate=orig_sr
                    )
                    return raw_wav

                # Load original data
                self.logger.debug(f"Resampling audio from {orig_sr}Hz to {sample_rate}Hz")
                data, orig_sr_2 = soundfile.read(io.BytesIO(raw_wav))
                if orig_sr_2 != orig_sr:
                    orig_sr = orig_sr_2

                resampled = librosa.resample(data, orig_sr=orig_sr, target_sr=sample_rate)
                out_buf = io.BytesIO()
                soundfile.write(out_buf, resampled, sample_rate, format='WAV', subtype='PCM_16')
                resampled_wav = out_buf.getvalue()

                duration = time.time() - start_time
                log_engine_operation(
                    self.logger, "piper", "synthesis_complete",
                    text_length=len(text), duration=f"{duration:.2f}s",
                    output_size=len(resampled_wav), sample_rate=sample_rate, resampled=True
                )
                return resampled_wav
            except Exception as e:
                # Error durante resampling, devolver audio original
                log_error_with_context(
                    self.logger, e,
                    {"operation": "resample", "orig_sr": orig_sr, "target_sr": sample_rate}
                )
                duration = time.time() - start_time
                log_engine_operation(
                    self.logger, "piper", "synthesis_complete",
                    text_length=len(text), duration=f"{duration:.2f}s",
                    output_size=len(raw_wav), warning="resample_failed"
                )
                return raw_wav
        finally:
            try:
                os.remove(tf_path)
            except Exception:
                pass


# Registro
EngineRegistry.register("piper", lambda model, **kw: PiperEngine(model, **kw))