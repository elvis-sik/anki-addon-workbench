from __future__ import annotations

import json
import os
from pathlib import Path

from aqt import gui_hooks, mw
from aqt.qt import QTimer


def _finish() -> None:
    result_path = os.environ.get("ANKI_ADDON_WORKBENCH_RESULT")
    if result_path:
        payload = {"ok": True, "probe": "fixture", "has_main_window": mw is not None}
        Path(result_path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if mw is not None:
        mw.unloadProfileAndExit()


def _schedule() -> None:
    QTimer.singleShot(500, _finish)


gui_hooks.main_window_did_init.append(_schedule)
