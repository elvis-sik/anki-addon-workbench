"""Workbench tooling for disposable Anki add-on GUI development."""

from importlib.metadata import PackageNotFoundError, version

from .config import WorkbenchConfig, load_config

__all__ = ["WorkbenchConfig", "load_config"]

try:
    __version__ = version("anki-addon-workbench")
except PackageNotFoundError:  # pragma: no cover - editable/import-from-source fallback
    __version__ = "0.0.0+local"
