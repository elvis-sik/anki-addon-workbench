"""Real-display integration test for the GUI primitives.

Drives the actual pyautogui + Pillow backend against a live X server. Skips
automatically when there is no DISPLAY (e.g. local macOS) or the `[gui]` extra
is missing. CI runs this under `xvfb-run`, which is the headless environment the
unit tests cannot exercise.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from anki_addon_workbench.gui import _backend, core

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY")
    or not (_backend.pyautogui_available() and _backend.pillow_available()),
    reason="requires DISPLAY and the [gui] extra (run under xvfb-run)",
)


def test_captures_a_real_non_empty_screenshot(tmp_path: Path) -> None:
    from PIL import Image

    out = tmp_path / "shot.png"
    meta = tmp_path / "shot.json"
    result = core.screenshot(out, meta=meta, mark=(50, 50), label="xvfb")

    assert result["ok"] is True
    assert out.exists() and out.stat().st_size > 0
    assert meta.exists()

    width, height = Image.open(out).size
    assert width > 0 and height > 0
    assert result["screen"]["width"] == width
    assert result["screen"]["height"] == height


def test_pointer_move_is_honored() -> None:
    core.move(123, 77)
    pointer = _backend.position()
    # Xvfb warps the pointer exactly; allow a tiny slack for safety.
    assert abs(pointer.x - 123) <= 2
    assert abs(pointer.y - 77) <= 2
