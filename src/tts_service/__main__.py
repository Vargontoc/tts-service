import uvicorn
import sys
from .config import settings
from .utils.logging import setup_logging, get_logger
from .utils.dependencies import dependency_manager

def validate_dependencies():
    """Valida dependencias críticas al startup."""
    logger = get_logger("tts_service.startup")

    # Validar todas las dependencias
    results = dependency_manager.validate_all_dependencies()

    # Verificar dependencias requeridas
    missing_required = dependency_manager.get_missing_required_dependencies()
    if missing_required:
        logger.error("Faltan dependencias REQUERIDAS:")
        for dep in missing_required:
            info = dependency_manager.DEPENDENCIES[dep]
            logger.error(f"  - {dep}: {info.description}")
            logger.error(f"    Instalar con: {info.install_command}")
        logger.error("El servicio NO PUEDE ARRANCAR sin estas dependencias.")
        sys.exit(1)

    # Reportar dependencias recomendadas faltantes
    missing_recommended = dependency_manager.get_missing_recommended_dependencies()
    if missing_recommended:
        logger.warning("Faltan dependencias RECOMENDADAS (funcionalidad limitada):")
        for dep in missing_recommended:
            info = dependency_manager.DEPENDENCIES[dep]
            logger.warning(f"  - {dep}: {info.description}")
            logger.warning(f"    Instalar con: {info.install_command}")

    # Reportar estado general
    total_deps = len(dependency_manager.DEPENDENCIES)
    available_deps = sum(1 for r in results.values() if r["available"])
    logger.info(f"Dependencies check: {available_deps}/{total_deps} available")

    # Log detallado en DEBUG
    if settings.LOG_LEVEL == "DEBUG":
        logger.debug("Dependency details:")
        for name, result in results.items():
            status = "✓" if result["available"] else "✗"
            level = result["level"]
            logger.debug(f"  {status} {name} ({level}): {result['description']}")
            if not result["available"]:
                logger.debug(f"      Error: {result['error']}")


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

    # Validar dependencias críticas
    validate_dependencies()

    uvicorn.run("tts_service.api:app", host=settings.HOST, port=settings.PORT, reload=True)