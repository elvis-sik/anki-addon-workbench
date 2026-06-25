from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
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


def seed_with_anki_python(
    anki_python: str,
    base: Path,
    profile: str,
    lang: str,
    *,
    import_apkgs: Sequence[Path] = (),
) -> None:
    seed_command = [
        anki_python,
        str(resource_path("anki_addon_workbench._resources", "seed_anki_base.py")),
        "--base",
        str(base),
        "--profile",
        profile,
        "--lang",
        lang,
    ]
    for apkg in import_apkgs:
        seed_command.extend(["--import-apkg", str(apkg)])
    completed = subprocess.run(
        seed_command,
        check=False,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Cannot seed disposable Anki profile:\n"
            f"command: {seed_command}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def seed_base(
    base: Path,
    *,
    profile: str,
    lang: str = "en_US",
    anki_python: str | None = None,
    import_apkgs: Sequence[Path] = (),
) -> None:
    # Seeding uses Anki's own ProfileManager (via the launcher-managed Python),
    # which is correct across Anki versions. There is intentionally no
    # reverse-engineered prefs21.db fallback: launching Anki already implies a
    # usable interpreter sits next to its binary.
    if not anki_python:
        raise RuntimeError(
            "Cannot seed a disposable Anki profile: no Anki Python interpreter was "
            "found. Pass --anki-python, set ANKI_PYTHON, or ensure a 'python' "
            "executable sits next to the Anki launcher binary."
        )
    seed_with_anki_python(
        anki_python,
        base,
        profile,
        lang,
        import_apkgs=import_apkgs,
    )
