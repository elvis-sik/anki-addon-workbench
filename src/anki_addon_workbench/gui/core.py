from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from ..types import JsonDict
from . import _backend
from .models import Marker


def doctor() -> JsonDict:
    pyautogui = _backend.pyautogui_available()
    pillow = _backend.pillow_available()
    return {
        "ok": pyautogui and pillow,
        "platform": sys.platform,
        "display": os.environ.get("DISPLAY"),
        "pyautogui": pyautogui,
        "pillow": pillow,
        "xdotool": shutil.which("xdotool"),
    }


def location() -> JsonDict:
    return {
        "ok": True,
        "pointer": _backend.position().to_json(),
        "active_window": _backend.active_window().to_json(),
    }


def move(x: int, y: int) -> JsonDict:
    return {"ok": True, "location": _backend.move(x, y).to_json()}


def click(button: int = 1, x: int | None = None, y: int | None = None) -> JsonDict:
    if (x is None) != (y is None):
        raise ValueError("x and y must be provided together")
    if x is not None and y is not None:
        _backend.move(x, y)
    return {"ok": True, **_backend.click(button)}


def key(keys: list[str]) -> JsonDict:
    for name in keys:
        _backend.press_key(name)
    return {"ok": True, "keys": keys}


def type_text(text: str) -> JsonDict:
    _backend.type_text(text)
    return {"ok": True, "text": text}


def screenshot(
    out: str | Path,
    *,
    meta: str | Path | None = None,
    mark: tuple[int, int] | None = None,
    label: str | None = None,
    marker_size: int = 22,
    no_marker: bool = False,
) -> JsonDict:
    pointer = _backend.position()
    image = _backend.capture_image()

    marker = None
    if not no_marker:
        marker_x, marker_y = mark if mark is not None else (pointer.x, pointer.y)
        marker = Marker(x=int(marker_x), y=int(marker_y), size=int(marker_size), label=label)
        _backend.draw_marker(image, marker)

    output = Path(str(out))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(output), "PNG")

    width, height = image.size
    metadata: JsonDict = {
        "ok": True,
        "backend": "pyautogui",
        "display": os.environ.get("DISPLAY"),
        "screenshot": str(output),
        "marker": marker.to_json() if marker else None,
        "pointer": pointer.to_json(),
        "active_window": _backend.active_window().to_json(),
        "screen": {"x": 0, "y": 0, "width": int(width), "height": int(height)},
        "captured_at": int(time.time()),
    }

    meta_path = Path(str(meta)) if meta else output.with_suffix(".json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    metadata["metadata"] = str(meta_path)
    return metadata
