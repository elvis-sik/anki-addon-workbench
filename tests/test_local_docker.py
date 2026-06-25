from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.local_docker import run_docker_smoke_local


def _config(root: Path) -> WorkbenchConfig:
    return WorkbenchConfig(
        root=root,
        config_file=root / "pyproject.toml",
        project_name="Fixture",
        addon_package="fixture_addon",
        source_root=root,
        include=(),
        exclude=(),
        docker_image="fixture-image",
    )


def test_run_docker_smoke_local_builds_wheel_image_and_runs_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "workbench-source"
    source.mkdir()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:3] == ["sfw", "uv", "build"]:
            out_dir = Path(command[command.index("--out-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "anki_addon_workbench-0.2.1-py3-none-any.whl").write_text(
                "wheel",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="built wheel\n")
        if command[:2] == ["docker", "build"]:
            return subprocess.CompletedProcess(command, 0, stdout="built image\n")
        if command[:2] == ["docker", "run"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"ok": true, "probe": "fixture"}\n',
            )
        return subprocess.CompletedProcess(command, 99, stdout="unexpected\n")

    monkeypatch.setattr("anki_addon_workbench.local_docker.subprocess.run", fake_run)

    status, payload = run_docker_smoke_local(
        _config(tmp_path),
        workbench_source=str(source),
        artifact_dir=str(tmp_path / "artifacts"),
        image="fixture-local",
        uv_command="sfw uv",
    )

    assert status == 0
    assert payload["ok"] is True
    assert payload["stage"] == "complete"
    assert payload["image"] == "fixture-local"
    assert payload["smoke"] == {"ok": True, "probe": "fixture"}
    assert calls[0][:3] == ["sfw", "uv", "build"]
    assert calls[1][:4] == ["docker", "build", "-f", str(tmp_path / "artifacts/context/Dockerfile")]
    assert calls[2][:2] == ["docker", "run"]
    assert f"type=bind,source={tmp_path.resolve()},target=/workspace" in calls[2]

    dockerfile = tmp_path / "artifacts" / "context" / "Dockerfile"
    assert dockerfile.exists()
    text = dockerfile.read_text(encoding="utf-8")
    assert 'COPY ["wheels/anki_addon_workbench-0.2.1-py3-none-any.whl"' in text


def test_run_docker_smoke_local_reports_wheel_build_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "workbench-source"
    source.mkdir()

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, stdout="nope\n")

    monkeypatch.setattr("anki_addon_workbench.local_docker.subprocess.run", fake_run)

    status, payload = run_docker_smoke_local(
        _config(tmp_path),
        workbench_source=str(source),
        artifact_dir=str(tmp_path / "artifacts"),
    )

    assert status == 2
    assert payload["ok"] is False
    assert payload["stage"] == "wheel"
    assert "wheel_build" in payload
