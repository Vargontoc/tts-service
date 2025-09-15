"""
Validación y manejo robusto de dependencias opcionales.
Centraliza la lógica de verificación e import de paquetes opcionales.
"""

import importlib
import sys
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class DependencyLevel(Enum):
    """Niveles de criticidad de las dependencias."""
    REQUIRED = "required"        # Requerida para funcionalidad básica
    RECOMMENDED = "recommended"  # Recomendada para funcionalidad completa
    OPTIONAL = "optional"        # Opcional, mejora funcionalidad


@dataclass
class DependencyInfo:
    """Información sobre una dependencia."""
    name: str
    package: str
    level: DependencyLevel
    description: str
    install_command: str
    alternative_names: List[str] = None
    min_version: Optional[str] = None
    check_version: bool = False


class DependencyManager:
    """Gestor centralizado de dependencias opcionales."""

    # Configuración de dependencias conocidas
    DEPENDENCIES = {
        # TTS Engines
        "coqui_tts": DependencyInfo(
            name="coqui_tts",
            package="TTS",
            level=DependencyLevel.RECOMMENDED,
            description="Coqui TTS engine para síntesis de voz de alta calidad",
            install_command="pip install TTS",
            alternative_names=["coqui_tts", "TTS"],
        ),

        # Audio processing
        "torch": DependencyInfo(
            name="torch",
            package="torch",
            level=DependencyLevel.RECOMMENDED,
            description="PyTorch para GPU support en Coqui TTS",
            install_command="pip install torch",
        ),
        "librosa": DependencyInfo(
            name="librosa",
            package="librosa",
            level=DependencyLevel.RECOMMENDED,
            description="Librosa para resampling y manipulación de audio",
            install_command="pip install librosa",
        ),
        "soundfile": DependencyInfo(
            name="soundfile",
            package="soundfile",
            level=DependencyLevel.RECOMMENDED,
            description="SoundFile para I/O de archivos de audio",
            install_command="pip install soundfile",
        ),
        "numpy": DependencyInfo(
            name="numpy",
            package="numpy",
            level=DependencyLevel.RECOMMENDED,
            description="NumPy para operaciones de array en audio",
            install_command="pip install numpy",
        ),

        # Logging
        "python_json_logger": DependencyInfo(
            name="python_json_logger",
            package="pythonjsonlogger",
            level=DependencyLevel.OPTIONAL,
            description="Logging estructurado en formato JSON",
            install_command="pip install python-json-logger",
            alternative_names=["pythonjsonlogger"],
        ),

        # Audio conversion
        "pydub": DependencyInfo(
            name="pydub",
            package="pydub",
            level=DependencyLevel.REQUIRED,
            description="PyDub para conversión de formatos de audio",
            install_command="pip install pydub",
        ),
    }

    def __init__(self):
        self._cache: Dict[str, Tuple[bool, Optional[Any], Optional[str]]] = {}

    def check_dependency(self, name: str) -> Tuple[bool, Optional[Any], Optional[str]]:
        """
        Verifica si una dependencia está disponible.

        Args:
            name: Nombre de la dependencia en DEPENDENCIES

        Returns:
            Tuple de (disponible, módulo_importado, mensaje_error)
        """
        if name in self._cache:
            return self._cache[name]

        if name not in self.DEPENDENCIES:
            error_msg = f"Dependencia desconocida: {name}"
            result = (False, None, error_msg)
            self._cache[name] = result
            return result

        dep_info = self.DEPENDENCIES[name]

        # Intentar importar el paquete principal
        module, error_msg = self._try_import(dep_info.package)
        if module:
            result = (True, module, None)
            self._cache[name] = result
            return result

        # Intentar nombres alternativos
        if dep_info.alternative_names:
            for alt_name in dep_info.alternative_names:
                module, _ = self._try_import(alt_name)
                if module:
                    result = (True, module, None)
                    self._cache[name] = result
                    return result

        # No se pudo importar
        result = (False, None, error_msg)
        self._cache[name] = result
        return result

    def _try_import(self, package_name: str) -> Tuple[Optional[Any], Optional[str]]:
        """Intenta importar un paquete y retorna el módulo o error."""
        try:
            module = importlib.import_module(package_name)
            return module, None
        except ImportError as e:
            return None, str(e)
        except Exception as e:
            return None, f"Error inesperado importando {package_name}: {e}"

    def require_dependency(self, name: str) -> Any:
        """
        Requiere una dependencia y la retorna o lanza excepción.

        Args:
            name: Nombre de la dependencia

        Returns:
            Módulo importado

        Raises:
            ImportError: Si la dependencia no está disponible
        """
        available, module, error = self.check_dependency(name)
        if not available:
            dep_info = self.DEPENDENCIES.get(name)
            if dep_info:
                raise ImportError(
                    f"Dependencia requerida '{name}' no está disponible.\n"
                    f"Descripción: {dep_info.description}\n"
                    f"Instalar con: {dep_info.install_command}\n"
                    f"Error: {error}"
                )
            else:
                raise ImportError(f"Dependencia desconocida '{name}': {error}")
        return module

    def get_optional_dependency(self, name: str, default: Any = None) -> Any:
        """
        Obtiene una dependencia opcional, retornando default si no está disponible.

        Args:
            name: Nombre de la dependencia
            default: Valor por defecto si no está disponible

        Returns:
            Módulo importado o valor por defecto
        """
        available, module, _ = self.check_dependency(name)
        return module if available else default

    def validate_all_dependencies(self) -> Dict[str, Dict[str, Any]]:
        """
        Valida todas las dependencias conocidas.

        Returns:
            Dict con el estado de todas las dependencias
        """
        results = {}

        for name, dep_info in self.DEPENDENCIES.items():
            available, module, error = self.check_dependency(name)

            results[name] = {
                "available": available,
                "level": dep_info.level.value,
                "description": dep_info.description,
                "install_command": dep_info.install_command,
                "error": error,
                "module": module.__name__ if module else None,
            }

        return results

    def get_missing_required_dependencies(self) -> List[str]:
        """Retorna lista de dependencias requeridas que faltan."""
        missing = []
        for name, dep_info in self.DEPENDENCIES.items():
            if dep_info.level == DependencyLevel.REQUIRED:
                available, _, _ = self.check_dependency(name)
                if not available:
                    missing.append(name)
        return missing

    def get_missing_recommended_dependencies(self) -> List[str]:
        """Retorna lista de dependencias recomendadas que faltan."""
        missing = []
        for name, dep_info in self.DEPENDENCIES.items():
            if dep_info.level == DependencyLevel.RECOMMENDED:
                available, _, _ = self.check_dependency(name)
                if not available:
                    missing.append(name)
        return missing

    def clear_cache(self) -> None:
        """Limpia el cache de dependencias verificadas."""
        self._cache.clear()


# Instancia global del gestor de dependencias
dependency_manager = DependencyManager()


# Funciones de conveniencia para importar dependencias comunes
def safe_import_torch():
    """Import seguro de torch con manejo de errores."""
    return dependency_manager.get_optional_dependency("torch")


def safe_import_librosa():
    """Import seguro de librosa con manejo de errores."""
    return dependency_manager.get_optional_dependency("librosa")


def safe_import_soundfile():
    """Import seguro de soundfile con manejo de errores."""
    return dependency_manager.get_optional_dependency("soundfile")


def safe_import_numpy():
    """Import seguro de numpy con manejo de errores."""
    return dependency_manager.get_optional_dependency("numpy")


def safe_import_coqui_tts():
    """Import seguro de Coqui TTS con manejo de errores."""
    available, module, error = dependency_manager.check_dependency("coqui_tts")
    if not available:
        return None, error

    # Intentar obtener la clase TTS específica
    try:
        if hasattr(module, 'api'):
            tts_class = getattr(module.api, 'TTS', None)
        else:
            tts_class = getattr(module, 'TTS', None)
        return tts_class, None
    except Exception as e:
        return None, f"Error accediendo a TTS class: {e}"


def require_audio_processing_stack():
    """
    Requiere el stack completo de procesamiento de audio.

    Raises:
        ImportError: Si alguna dependencia crítica falta
    """
    required_deps = ["numpy", "soundfile"]
    for dep in required_deps:
        dependency_manager.require_dependency(dep)