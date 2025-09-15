
import hashlib
import os
from pathlib import Path
from typing import Optional


def get_cache_dir() -> Path:
    """Obtiene el directorio de cache configurado."""
    # Import aquí para evitar circular imports
    try:
        from ..config import settings
        cache_dir = settings.get_cache_dir()
    except ImportError:
        # Fallback si no se puede importar settings
        cache_dir = Path("cache")

    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def is_cache_enabled() -> bool:
    """Verifica si el cache está habilitado."""
    try:
        from ..config import settings
        return settings.CACHE_ENABLED
    except ImportError:
        return True  # Default habilitado


def get_cache_max_size_bytes() -> int:
    """Obtiene el tamaño máximo del cache en bytes."""
    try:
        from ..config import settings
        if settings.CACHE_MAX_SIZE_MB == 0:
            return 0  # Ilimitado
        return settings.CACHE_MAX_SIZE_MB * 1024 * 1024
    except ImportError:
        return 1024 * 1024 * 1000  # 1GB default

def make_key(txt: str, voice: str, sample_rate: int, fmt: str) -> str:
    """Clave legacy (sin provider)."""
    base = f"{voice}|{sample_rate}|{fmt}|{txt.strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def make_key_v2(txt: str, provider: str, model: str, voice: str, sample_rate: int, fmt: str) -> str:
    base = f"v2|{provider}|{model}|{voice}|{sample_rate}|{fmt}|{txt.strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def make_key_v3(txt: str, provider: str, model: str, voice: str, sample_rate: int, fmt: str,
                speaking_rate: float|None, pitch_shift: float|None, energy: float|None) -> str:
    base = f"v3|{provider}|{model}|{voice}|{sample_rate}|{fmt}|{speaking_rate}|{pitch_shift}|{energy}|{txt.strip()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def get_cache_path(key: str, fmt: str) -> Path:
    """Obtiene el path completo para un archivo de cache."""
    return get_cache_dir() / f"{key}.{fmt}"


def exists(key: str, fmt: str) -> bool:
    """Verifica si existe un archivo en el cache."""
    if not is_cache_enabled():
        return False
    return get_cache_path(key, fmt).exists()


def load(key: str, fmt: str) -> bytes:
    """Carga datos desde el cache."""
    if not is_cache_enabled():
        raise RuntimeError("Cache is disabled")
    return get_cache_path(key, fmt).read_bytes()


def save(key: str, fmt: str, data: bytes) -> Optional[Path]:
    """Guarda datos en el cache."""
    if not is_cache_enabled():
        return None

    # Verificar límite de tamaño si está configurado
    max_size = get_cache_max_size_bytes()
    if max_size > 0:
        current_size = get_cache_size()
        if current_size + len(data) > max_size:
            # Limpiar cache si excede el límite
            cleanup_cache(max_size // 2)  # Limpiar hasta la mitad del límite

    path = get_cache_path(key, fmt)
    path.write_bytes(data)
    return path


def get_cache_size() -> int:
    """Obtiene el tamaño total del cache en bytes."""
    cache_dir = get_cache_dir()
    total_size = 0
    try:
        for file_path in cache_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total_size


def cleanup_cache(target_size: int) -> int:
    """
    Limpia el cache eliminando archivos más antiguos hasta alcanzar el tamaño objetivo.

    Args:
        target_size: Tamaño objetivo en bytes

    Returns:
        Número de archivos eliminados
    """
    cache_dir = get_cache_dir()
    files_removed = 0

    try:
        # Obtener todos los archivos con su tiempo de acceso
        files = []
        for file_path in cache_dir.rglob('*'):
            if file_path.is_file():
                stat = file_path.stat()
                files.append((file_path, stat.st_atime, stat.st_size))

        # Ordenar por tiempo de acceso (más antiguos primero)
        files.sort(key=lambda x: x[1])

        current_size = sum(f[2] for f in files)

        # Eliminar archivos hasta alcanzar el tamaño objetivo
        for file_path, _, file_size in files:
            if current_size <= target_size:
                break
            try:
                file_path.unlink()
                current_size -= file_size
                files_removed += 1
            except (OSError, PermissionError):
                pass

    except (OSError, PermissionError):
        pass

    return files_removed


def clear_cache() -> int:
    """
    Limpia todo el cache.

    Returns:
        Número de archivos eliminados
    """
    cache_dir = get_cache_dir()
    files_removed = 0

    try:
        for file_path in cache_dir.rglob('*'):
            if file_path.is_file():
                try:
                    file_path.unlink()
                    files_removed += 1
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass

    return files_removed