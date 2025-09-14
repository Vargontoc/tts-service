from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional, Any, List, Callable
import threading

__all__ = ["BaseTTSEngine", "EngineRegistry", "get_engine"]


class BaseTTSEngine(ABC):
    """Interfaz base para motores TTS."""

    def __init__(self, model: str, **kwargs):  # pragma: no cover - simple asignación
        self.model = model
        self._init_kwargs = kwargs

    @abstractmethod
    def synthesize_wav(self, text: str, **kwargs) -> bytes:
        """Genera audio WAV en bytes."""
        raise NotImplementedError

    def list_speakers(self) -> List[str]:  # pragma: no cover - default
        return []


class _EngineRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._factories: Dict[str, Callable[..., BaseTTSEngine]] = {}

    def register(self, name: str, factory: Callable[..., BaseTTSEngine]):
        with self._lock:
            self._factories[name.lower()] = factory

    def create(self, name: str, *args, **kwargs) -> BaseTTSEngine:
        key = name.lower()
        with self._lock:
            if key not in self._factories:
                raise ValueError(f"Engine provider desconocido: {name}")
            return self._factories[key](*args, **kwargs)

    def providers(self) -> List[str]:  # pragma: no cover
        with self._lock:
            return sorted(self._factories.keys())


EngineRegistry = _EngineRegistry()


def get_engine(provider: str, model: str, **kwargs) -> BaseTTSEngine:
    return EngineRegistry.create(provider, model, **kwargs)
