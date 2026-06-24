"""Cross-platform GUI primitives (pointer, keyboard, marked screenshots).

Backed by pyautogui + Pillow, installed via the optional ``[gui]`` extra. All
heavy imports are lazy so this package is importable without a display or the
extra present; calling a command without the extra raises a clear install hint.
"""

from __future__ import annotations

from . import core
from .models import ActiveWindow, Marker, PointerLocation

__all__ = ["ActiveWindow", "Marker", "PointerLocation", "core"]
