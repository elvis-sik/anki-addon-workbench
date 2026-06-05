from __future__ import annotations

from pathlib import Path

from .config import WorkbenchConfig
from .resources import text_resource


def render_dockerfile(config: WorkbenchConfig) -> str:
    template = text_resource("anki_addon_workbench.templates", "anki-xvfb.Dockerfile")
    return template.replace("{{ANKI_VERSION}}", config.anki_version)


def write_dockerfile(config: WorkbenchConfig, out: str | Path) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dockerfile(config), encoding="utf-8")
    return path
