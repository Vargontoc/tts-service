
import hashlib
from pathlib import Path


CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

def make_key(txt: str, voice: str, sample_rate: int, fmt: str) -> str:
    base = f"{voice}|{sample_rate}|{fmt}|{txt.strip()}"
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