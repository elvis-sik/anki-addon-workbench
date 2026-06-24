from __future__ import annotations

from pathlib import Path

from .resources import text_resource

_PROBE_TEMPLATE = ("anki_addon_workbench._resources", "probe_addon_template.py.tmpl")


def init_probe(out: str | Path, *, force: bool = False) -> Path:
    """Write a ready-to-edit probe add-on package at ``out``.

    Creates ``<out>/__init__.py`` from the bundled template. The directory name
    becomes the probe add-on's package name; point ``probe_addon`` at it in your
    ``[tool.anki-addon-workbench]`` config.
    """
    destination = Path(out)
    init_file = destination / "__init__.py"
    if init_file.exists() and not force:
        raise FileExistsError(f"{init_file} already exists (pass force=True to overwrite)")
    destination.mkdir(parents=True, exist_ok=True)
    init_file.write_text(text_resource(*_PROBE_TEMPLATE), encoding="utf-8")
    return init_file
