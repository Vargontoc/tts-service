import uvicorn
from .config import settings
from .utils.logging import setup_logging

if __name__ == "__main__":
    # Configurar logging antes de iniciar la aplicación
    setup_logging(
        level=settings.LOG_LEVEL,
        log_file=settings.LOG_FILE,
        log_dir=settings.LOG_DIR,
        enable_structured=settings.LOG_STRUCTURED,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT
    )

    uvicorn.run("tts_service.api:app", host=settings.HOST, port=settings.PORT, reload=True)