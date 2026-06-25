from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from anki_addon_workbench.profile import default_anki_bin, seed_base


def test_seed_base_requires_anki_python(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no Anki Python interpreter"):
        seed_base(tmp_path, profile="User 1", anki_python=None)


def test_seed_base_passes_import_apkgs_to_anki_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    run_kwargs: list[dict[str, Any]] = []

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        run_kwargs.append(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("anki_addon_workbench.profile.subprocess.run", fake_run)

    seed_base(
        tmp_path / "base",
        profile="User 1",
        anki_python="/opt/anki/python",
        import_apkgs=[tmp_path / "one.apkg", tmp_path / "two.apkg"],
    )

    assert calls
    command = calls[0]
    assert command[0] == "/opt/anki/python"
    assert command.count("--import-apkg") == 2
    assert str(tmp_path / "one.apkg") in command
    assert str(tmp_path / "two.apkg") in command
    assert run_kwargs[0]["stdout"] == subprocess.PIPE
    assert run_kwargs[0]["stderr"] == subprocess.PIPE
    assert run_kwargs[0]["text"] is True


def test_seed_base_reports_anki_python_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 3, stdout="seed out", stderr="seed err")

    monkeypatch.setattr("anki_addon_workbench.profile.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="Cannot seed disposable Anki profile") as exc:
        seed_base(
            tmp_path / "base",
            profile="User 1",
            anki_python="/opt/anki/python",
        )

    assert "seed out" in str(exc.value)
    assert "seed err" in str(exc.value)


def test_default_anki_bin_ignores_unreadable_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked_exists(self: Path) -> bool:
        if str(self).startswith("/root/"):
            raise PermissionError("blocked")
        return False

    monkeypatch.setattr(Path, "exists", blocked_exists)
    monkeypatch.setattr("anki_addon_workbench.profile.shutil.which", lambda _: None)

    assert default_anki_bin() == "anki"
