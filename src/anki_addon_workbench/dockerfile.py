from __future__ import annotations

import json
from pathlib import Path

from .config import WorkbenchConfig
from .resources import text_resource


def _docker_arg_string(value: str, *, key: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single-line value")
    return json.dumps(value)


def render_dockerfile(config: WorkbenchConfig, *, workbench_spec: str | None = None) -> str:
    spec = workbench_spec or config.docker_workbench_spec
    template = text_resource("anki_addon_workbench.templates", "anki-xvfb.Dockerfile")
    return (
        template.replace("{{ANKI_VERSION}}", config.anki_version)
        .replace(
            "{{WORKBENCH_SPEC}}",
            _docker_arg_string(spec, key="workbench_spec"),
        )
    )


def write_dockerfile(
    config: WorkbenchConfig, out: str | Path, *, workbench_spec: str | None = None
) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dockerfile(config, workbench_spec=workbench_spec), encoding="utf-8")
    return path
