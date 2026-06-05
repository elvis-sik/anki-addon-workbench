from __future__ import annotations

import os

import aqt  # type: ignore[import-not-found]


key = os.environ.get("ANKI_SINGLE_INSTANCE_KEY")
if key:
    aqt.AnkiApp.KEY = key

raise SystemExit(aqt.run())
