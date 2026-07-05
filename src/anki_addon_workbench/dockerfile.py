from __future__ import annotations

import json
from pathlib import PurePosixPath
from pathlib import Path

from .config import WorkbenchConfig
from .resources import text_resource


def _docker_arg_string(value: str, *, key: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} must be a single-line value")
    return json.dumps(value)


def _docker_copy_wheel_line(local_workbench_wheel: str | None) -> tuple[str, str | None]:
    if local_workbench_wheel is None:
        return "", None
    if "\n" in local_workbench_wheel or "\r" in local_workbench_wheel:
        raise ValueError("local_workbench_wheel must be a single-line relative path")

    source = PurePosixPath(local_workbench_wheel)
    if source.is_absolute() or ".." in source.parts or not source.name.endswith(".whl"):
        raise ValueError("local_workbench_wheel must be a relative .whl path")

    target = PurePosixPath("/tmp/anki-addon-workbench") / source.name
    return f"COPY {json.dumps([source.as_posix(), target.as_posix()])}\n", target.as_posix()


def render_dockerfile(
    config: WorkbenchConfig,
    *,
    workbench_spec: str | None = None,
    local_workbench_wheel: str | None = None,
) -> str:
    copy_line, wheel_target = _docker_copy_wheel_line(local_workbench_wheel)
    if wheel_target is not None and workbench_spec is None:
        spec = f"{wheel_target}[gui]"
    else:
        spec = workbench_spec or config.docker_workbench_spec
    template = text_resource("anki_addon_workbench.templates", "anki-xvfb.Dockerfile")
    return (
        template.replace("{{ANKI_VERSION}}", config.anki_version)
        .replace("{{WORKBENCH_LOCAL_WHEEL_COPY}}", copy_line)
        .replace(
            "{{WORKBENCH_SPEC}}",
            _docker_arg_string(spec, key="workbench_spec"),
        )
    )


def render_android_dockerfile(
    config: WorkbenchConfig,
    *,
    workbench_spec: str | None = None,
    ankidroid_apk_url: str | None = None,
) -> str:
    template = text_resource("anki_addon_workbench.templates", "android-emulator.Dockerfile")
    spec = workbench_spec or config.android_workbench_spec
    apk_url = ankidroid_apk_url or config.android_ankidroid_apk or ""
    return (
        template.replace("{{WORKBENCH_SPEC}}", _docker_arg_string(spec, key="workbench_spec"))
        .replace(
            "{{ANKIDROID_APK_URL}}",
            _docker_arg_string(apk_url, key="ankidroid_apk_url"),
        )
    )


def write_dockerfile(
    config: WorkbenchConfig,
    out: str | Path,
    *,
    workbench_spec: str | None = None,
    local_workbench_wheel: str | None = None,
) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_dockerfile(
            config,
            workbench_spec=workbench_spec,
            local_workbench_wheel=local_workbench_wheel,
        ),
        encoding="utf-8",
    )
    return path


def write_android_dockerfile(
    config: WorkbenchConfig,
    out: str | Path,
    *,
    workbench_spec: str | None = None,
    ankidroid_apk_url: str | None = None,
) -> Path:
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_android_dockerfile(
            config,
            workbench_spec=workbench_spec,
            ankidroid_apk_url=ankidroid_apk_url,
        ),
        encoding="utf-8",
    )
    return path
