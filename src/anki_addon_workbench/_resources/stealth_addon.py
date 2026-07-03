"""Workbench stealth helper: keep disposable Anki out of the user's way.

Installed automatically for host GUI runs on macOS (smoke and launch)
unless foreground mode is requested. The disposable Anki window is shown
without activation (no focus steal), lowered in the stacking order, and
parked so that only a tiny sliver stays on screen - fully off-screen
windows get marked occluded and QtWebEngine stops compositing them,
which would break widget grabs and webview-driven probes.

Set ANKI_ADDON_WORKBENCH_STEALTH=0 to disable at runtime.
"""

from __future__ import annotations

import os

from aqt import gui_hooks, mw
from aqt.qt import Qt

SLIVER_PX = 2


def _stealth_enabled() -> bool:
    return os.environ.get("ANKI_ADDON_WORKBENCH_STEALTH", "1") != "0"


def _park_main_window() -> None:
    if mw is None:
        return
    screen = mw.screen() or mw.app.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        mw.move(
            geometry.x() + geometry.width() - SLIVER_PX,
            geometry.y() + geometry.height() - SLIVER_PX,
        )
    mw.lower()


if mw is not None and _stealth_enabled():
    # Must be set before the window is first shown to stop activation.
    mw.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    gui_hooks.main_window_did_init.append(_park_main_window)
