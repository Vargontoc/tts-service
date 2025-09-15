"""
Sistema de logging estructurado para TTS Service.
Proporciona configuración centralizada y loggers específicos por módulo.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json


class TTSFormatter(logging.Formatter):
    """Formatter personalizado que incluye información de contexto TTS."""

    def format(self, record: logging.LogRecord) -> str:
        # Añadir información específica del contexto TTS si está disponible
        if hasattr(record, 'engine'):
            record.msg = f"[{record.engine}] {record.msg}"
        if hasattr(record, 'voice_id'):
            record.msg = f"[voice:{record.voice_id}] {record.msg}"
        if hasattr(record, 'request_id'):
            record.msg = f"[req:{record.request_id}] {record.msg}"

        return super().format(record)


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    enable_structured: bool = True,
    max_bytes: int = 10_485_760,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configura el sistema de logging para TTS Service.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Nombre del archivo de log (None = solo console)
        log_dir: Directorio para archivos de log
        enable_structured: Si usar logging estructurado con JSON
        max_bytes: Tamaño máximo del archivo antes de rotación
        backup_count: Número de archivos de backup a mantener
    """

    # Configuración base
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "()": TTSFormatter,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "file": {
                "()": TTSFormatter,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "console",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "tts_service": {
                "level": level,
                "handlers": ["console"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            }
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"]
        }
    }

    # Añadir handler de archivo si se especifica
    if log_file and log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        full_path = log_path / log_file

        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "file",
            "filename": str(full_path),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8"
        }

        # Añadir file handler a los loggers
        config["loggers"]["tts_service"]["handlers"].append("file")
        config["loggers"]["uvicorn"]["handlers"].append("file")
        config["root"]["handlers"].append("file")

    # Configurar logging estructurado (JSON) si está habilitado
    if enable_structured and log_file:
        config["formatters"]["json"] = {
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s"
        }

        if log_dir:
            json_path = Path(log_dir) / f"{Path(log_file).stem}.json"
            config["handlers"]["json_file"] = {
                "class": "logging.handlers.RotatingFileHandler",
                "level": level,
                "formatter": "json",
                "filename": str(json_path),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
                "encoding": "utf-8"
            }
            config["loggers"]["tts_service"]["handlers"].append("json_file")

    # Aplicar configuración
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Obtiene un logger específico para un módulo.

    Args:
        name: Nombre del módulo (ej: 'tts_service.engines.coqui')

    Returns:
        Logger configurado
    """
    return logging.getLogger(name)


def log_engine_operation(logger: logging.Logger, engine: str, operation: str, **kwargs) -> None:
    """
    Log específico para operaciones de engines TTS.

    Args:
        logger: Logger a usar
        engine: Nombre del engine (coqui, piper)
        operation: Operación realizada
        **kwargs: Información adicional (voice_id, duration, etc.)
    """
    extra = {"engine": engine}
    extra.update(kwargs)
    logger.info(f"{operation}", extra=extra)


def log_api_request(logger: logging.Logger, endpoint: str, request_id: str, **kwargs) -> None:
    """
    Log específico para requests de API.

    Args:
        logger: Logger a usar
        endpoint: Endpoint llamado
        request_id: ID único de la request
        **kwargs: Información adicional
    """
    extra = {"request_id": request_id}
    extra.update(kwargs)
    logger.info(f"API request to {endpoint}", extra=extra)


def log_error_with_context(logger: logging.Logger, error: Exception, context: Dict[str, Any]) -> None:
    """
    Log de errores con contexto adicional.

    Args:
        logger: Logger a usar
        error: Excepción ocurrida
        context: Contexto adicional del error
    """
    logger.error(
        f"Error: {type(error).__name__}: {str(error)}",
        extra=context,
        exc_info=True
    )