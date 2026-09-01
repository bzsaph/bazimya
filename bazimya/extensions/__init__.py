"""Extensions: packages that add routes, commands, middleware and views."""

from .extension import Extension, ExtensionCommand, registry, reset_registry
from .manager import ExtensionManager

__all__ = [
    "Extension",
    "ExtensionCommand",
    "ExtensionManager",
    "registry",
    "reset_registry",
]
