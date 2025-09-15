from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Any, Optional
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

    # Configuración de paths
    MODELS_DIR: str = Field("models", description="Directorio de modelos TTS")
    VOICES_CONFIG_FILE: str = Field("voices.json", description="Archivo de configuración de voces legacy")
    UNIFIED_CONFIG_FILE: str = Field("tts_config.json", description="Archivo de configuración unificada")

    # Configuración de logging
    LOG_LEVEL: str = Field("INFO", description="Nivel de logging: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FILE: Optional[str] = Field(None, description="Nombre del archivo de log (None = solo console)")
    LOG_DIR: str = Field("logs", description="Directorio para archivos de log")
    LOG_STRUCTURED: bool = Field(True, description="Habilitar logging estructurado JSON")
    LOG_MAX_BYTES: int = Field(10_485_760, description="Tamaño máximo del archivo de log en bytes (10MB)")
    LOG_BACKUP_COUNT: int = Field(5, description="Número de archivos de backup a mantener")

    # Configuración de cache
    CACHE_DIR: str = Field("cache", description="Directorio para archivos de cache")
    CACHE_ENABLED: bool = Field(True, description="Habilitar sistema de cache")
    CACHE_MAX_SIZE_MB: int = Field(1000, description="Tamaño máximo del cache en MB (0 = ilimitado)")
    
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

    def get_models_dir(self) -> Path:
        """Obtiene el directorio de modelos como Path absoluto."""
        if Path(self.MODELS_DIR).is_absolute():
            return Path(self.MODELS_DIR)
        return PROJECT_ROOT / self.MODELS_DIR

    def get_voices_config_path(self) -> Path:
        """Obtiene el path del archivo de configuración de voces legacy."""
        return self.get_models_dir() / self.VOICES_CONFIG_FILE

    def get_unified_config_path(self) -> Path:
        """Obtiene el path del archivo de configuración unificada."""
        return self.get_models_dir() / self.UNIFIED_CONFIG_FILE

    def get_cache_dir(self) -> Path:
        """Obtiene el directorio de cache como Path absoluto."""
        if Path(self.CACHE_DIR).is_absolute():
            return Path(self.CACHE_DIR)
        return PROJECT_ROOT / self.CACHE_DIR
    
            
settings = Settings()
