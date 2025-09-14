
import hashlib
from pathlib import Path


CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

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

def get_cache_path(key:str, fmt: str) -> Path:
    return CACHE_DIR / f"{key}.{fmt}"

def exists(key: str, fmt: str) -> bool:
    return get_cache_path(key, fmt).exists()

def load(key: str, fmt: str) -> bytes:
    return get_cache_path(key, fmt).read_bytes()

def save(key: str, fmt: str, data: bytes):
    path = get_cache_path(key, fmt)
    path.write_bytes(data)
    return path