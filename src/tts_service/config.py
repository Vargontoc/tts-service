from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Any
from pathlib import Path
from pydantic import Field, model_validator
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignora variables legacy (EMOTION_PRESETS, etc.)
    )
    
    APP_NAME: str = "tts_service"
    API_VERSION: str = "v0"
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    API_KEY: str = Field(..., description="API key requerida para autenticación")
    CORS_ORIGINS_RAW: str = ""
    CORS_ORIGINS: List[str] = Field(default_factory=list, exclude=True)

    ENABLE_FALLBACK: bool = True
    COQUI_USE_GPU: str = Field("auto", description="auto|true|false (aún soportado si no hay unified JSON)")
    TTS_TIMEOUT_SECONDS: int = Field(0, description="0 = sin timeout")
    TTS_NORMALIZE_NUMBERS: bool = True  # se puede override en unified JSON defaults
    ENABLE_PROSODY_CONTROL: bool = True  # fallback si unified JSON ausente
    
    @model_validator(mode="after")
    def _build_cors(self): 
        s = (self.CORS_ORIGINS_RAW or "").strip()
        if not s:
            self.CORS_ORIGINS = []
            return self
        if s.startswith("["):  # JSON
            self.CORS_ORIGINS = json.loads(s)
        else:  # CSV
            self.CORS_ORIGINS = [x.strip() for x in s.split(",") if x.strip()]
        return self
    
            
settings = Settings()
