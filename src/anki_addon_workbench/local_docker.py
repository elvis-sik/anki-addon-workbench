from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import WorkbenchConfig
from .dockerfile import write_dockerfile
from .types import JsonDict

DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR = ".tmp/anki-workbench-local"


@dataclass(frozen=True)
class LoggedCommand:
    command: list[str]
    returncode: int
    log: Path
    output: str


def _split_command(value: str, *, key: str) -> list[str]:
    parts = shlex.split(value)
    if not parts:
        raise ValueError(f"{key} must not be empty")
    return parts


def _run_logged(command: list[str], log_path: Path, *, cwd: Path | None = None) -> LoggedCommand:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = completed.stdout or ""
    log_path.write_text(f"$ {shlex.join(command)}\n{output}", encoding="utf-8")
    return LoggedCommand(
        command=command,
        returncode=completed.returncode,
        log=log_path,
        output=output,
    )


def _command_json(result: LoggedCommand) -> JsonDict:
    return {
        "command": result.command,
        "returncode": result.returncode,
        "log": str(result.log),
    }


def _find_built_wheel(wheel_dir: Path) -> Path:
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        found = ", ".join(path.name for path in wheels) or "none"
        raise RuntimeError(f"expected exactly one built wheel in {wheel_dir}, found: {found}")
    return wheels[0]


def _parse_json_object(output: str) -> JsonDict | None:
    stripped = output.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def run_docker_smoke_local(
    config: WorkbenchConfig,
    *,
    workbench_source: str = ".",
    artifact_dir: str = DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR,
    image: str | None = None,
    uv_command: str = "uv",
    docker_command: str = "docker",
    no_cache: bool = False,
) -> tuple[int, JsonDict]:
    """Build a local wheel, install it in the Docker image, and run smoke.

    This is intentionally a maintainer/development path. Normal add-on projects
    should use ``dockerfile`` plus the published ``anki-addon-workbench[gui]``
    package spec.
    """

    source = Path(workbench_source).resolve()
    if not source.exists():
        return 1, {"ok": False, "stage": "wheel", "error": f"{source} does not exist"}

    artifacts = Path(artifact_dir).resolve()
    build_context = artifacts / "context"
    wheel_dir = build_context / "wheels"
    logs = artifacts / "logs"
    dockerfile_path = build_context / "Dockerfile"
    image_tag = image or f"{config.docker_image}-local"

    if build_context.exists():
        shutil.rmtree(build_context)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    uv_prefix = _split_command(uv_command, key="uv_command")
    docker_prefix = _split_command(docker_command, key="docker_command")

    wheel_result = _run_logged(
        [
            *uv_prefix,
            "build",
            "--wheel",
            "--out-dir",
            str(wheel_dir),
            "--clear",
            "--no-create-gitignore",
            str(source),
        ],
        logs / "wheel-build.log",
        cwd=source,
    )
    if wheel_result.returncode != 0:
        return (
            wheel_result.returncode,
            {
                "ok": False,
                "stage": "wheel",
                "artifact_dir": str(artifacts),
                "wheel_build": _command_json(wheel_result),
            },
        )

    wheel = _find_built_wheel(wheel_dir)
    wheel_in_context = wheel.relative_to(build_context).as_posix()
    write_dockerfile(
        config,
        dockerfile_path,
        local_workbench_wheel=wheel_in_context,
    )

    docker_build_command = [
        *docker_prefix,
        "build",
        "-f",
        str(dockerfile_path),
        "-t",
        image_tag,
    ]
    if no_cache:
        docker_build_command.append("--no-cache")
    docker_build_command.append(str(build_context))

    docker_build_result = _run_logged(docker_build_command, logs / "docker-build.log")
    if docker_build_result.returncode != 0:
        return (
            docker_build_result.returncode,
            {
                "ok": False,
                "stage": "docker_build",
                "artifact_dir": str(artifacts),
                "wheel": str(wheel),
                "dockerfile": str(dockerfile_path),
                "image": image_tag,
                "wheel_build": _command_json(wheel_result),
                "docker_build": _command_json(docker_build_result),
            },
        )

    docker_run_result = _run_logged(
        [
            *docker_prefix,
            "run",
            "--rm",
            "--mount",
            f"type=bind,source={config.root.resolve()},target=/workspace",
            "-w",
            "/workspace",
            image_tag,
        ],
        logs / "docker-run.log",
    )

    smoke = _parse_json_object(docker_run_result.output)
    ok = docker_run_result.returncode == 0
    payload: JsonDict = {
        "ok": ok,
        "stage": "complete" if ok else "docker_run",
        "artifact_dir": str(artifacts),
        "build_context": str(build_context),
        "wheel": str(wheel),
        "dockerfile": str(dockerfile_path),
        "image": image_tag,
        "wheel_build": _command_json(wheel_result),
        "docker_build": _command_json(docker_build_result),
        "docker_run": _command_json(docker_run_result),
    }
    if smoke is not None:
        payload["smoke"] = smoke
    return (0 if ok else docker_run_result.returncode or 1), payload
