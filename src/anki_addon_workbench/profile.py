from __future__ import annotations

import os
import pickle
import random
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from .resources import resource_path


def default_anki_bin() -> str:
    candidates = [
        Path("/Applications/Anki.app/Contents/Resources/.venv/bin/anki"),
        Path("/root/.local/share/AnkiProgramFiles/.venv/bin/anki"),
        Path("/usr/local/bin/anki"),
        Path("/usr/bin/anki"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    found = shutil.which("anki")
    return found or "anki"


def default_anki_python(anki_bin: str) -> str | None:
    candidate = Path(anki_bin).parent / "python"
    if candidate.exists():
        return str(candidate)
    return None


def direct_runner_path() -> Path:
    return resource_path("anki_addon_workbench._resources", "run_anki_direct.py")


def seed_with_anki_python(anki_python: str, base: Path, profile: str, lang: str) -> None:
    subprocess.run(
        [
            anki_python,
            str(resource_path("anki_addon_workbench._resources", "seed_anki_base.py")),
            "--base",
            str(base),
            "--profile",
            profile,
            "--lang",
            lang,
        ],
        check=True,
        env=os.environ.copy(),
    )


def seed_without_anki_python(base: Path, profile: str, lang: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    db_path = base / "prefs21.db"
    meta: dict[str, object] = {
        "ver": 0,
        "updates": True,
        "created": int(time.time()),
        "id": random.randrange(0, 2**63),
        "lastMsg": 0,
        "suppressUpdate": False,
        "firstRun": False,
        "defaultLang": lang,
    }
    profile_conf: dict[str, object] = {
        "mainWindowGeom": None,
        "mainWindowState": None,
        "numBackups": 50,
        "lastOptimize": int(time.time()),
        "searchHistory": [],
        "syncKey": None,
        "syncMedia": True,
        "autoSync": False,
        "allowHTML": False,
        "importMode": 1,
        "lastColour": "#00f",
        "stripHTML": True,
        "deleteMedia": False,
    }

    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            create table if not exists profiles
            (name text primary key collate nocase, data blob not null)
            """
        )
        db.execute(
            "insert or replace into profiles values (?, ?)",
            ("_global", pickle.dumps(meta, protocol=4)),
        )
        db.execute(
            "insert or replace into profiles values (?, ?)",
            (profile, pickle.dumps(profile_conf, protocol=4)),
        )


def seed_base(
    base: Path,
    *,
    profile: str,
    lang: str = "en_US",
    anki_python: str | None = None,
) -> None:
    if anki_python:
        seed_with_anki_python(anki_python, base, profile, lang)
    else:
        seed_without_anki_python(base, profile, lang)
