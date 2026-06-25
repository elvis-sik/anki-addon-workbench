from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import anki_addon_workbench.runner as runner
from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.runner import (
    QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV,
    build_anki_command,
    build_launch,
    doctor,
    prepare_base,
    run_workbench_command,
    validate_probe_result,
)


def _config(root: Path, **overrides: object) -> WorkbenchConfig:
    params: dict[str, object] = dict(
        root=root,
        config_file=root / "pyproject.toml",
        project_name="Fixture",
        addon_package="fixture_addon",
        source_root=root,
        include=(),
        exclude=(),
    )
    params.update(overrides)
    return WorkbenchConfig(**params)  # type: ignore[arg-type]


def test_builds_direct_python_command(tmp_path: Path) -> None:
    config = _config(tmp_path)
    launch = build_launch(config, anki_bin="/opt/anki", anki_python="/opt/python")

    command = build_anki_command(tmp_path / "base", config.profile, launch)

    assert command[0] == "/opt/python"
    assert "-b" in command
    assert str(tmp_path / "base") in command


def test_builds_plain_anki_command(tmp_path: Path) -> None:
    config = _config(tmp_path)
    launch = build_launch(config, anki_bin="/opt/anki", no_direct_python=True)

    command = build_anki_command(tmp_path / "base", config.profile, launch)

    assert command[0] == "/opt/anki"
    assert "--lang" in command


def test_prepare_base_installs_addon_and_probe(tmp_path: Path) -> None:
    addon = tmp_path / "addon"
    probe = tmp_path / "probe"
    base = tmp_path / "base"
    addon.mkdir()
    probe.mkdir()
    (addon / "__init__.py").write_text("# addon\n", encoding="utf-8")
    (probe / "__init__.py").write_text("# probe\n", encoding="utf-8")
    config = _config(
        tmp_path,
        source_root=addon,
        include=("__init__.py",),
        probe_addon=probe,
        probe_package="zz_probe",
    )

    prepare_base(config, base, include_probe=True)

    assert (base / "addons21" / "fixture_addon" / "__init__.py").exists()
    assert (base / "addons21" / "zz_probe" / "__init__.py").exists()


def test_prepare_base_allows_deck_only_probe(tmp_path: Path) -> None:
    probe = tmp_path / "probe"
    base = tmp_path / "base"
    probe.mkdir()
    (probe / "__init__.py").write_text("# probe\n", encoding="utf-8")
    config = _config(
        tmp_path,
        addon_package=None,
        probe_addon=probe,
        probe_package="zz_probe",
    )

    prepare_base(config, base, include_probe=True)

    assert not (base / "addons21" / "fixture_addon").exists()
    assert (base / "addons21" / "zz_probe" / "__init__.py").exists()


def test_prepare_base_installs_builtin_deck_probe_for_seed_apkgs(tmp_path: Path) -> None:
    base = tmp_path / "base"
    config = _config(
        tmp_path,
        addon_package=None,
        seed_apkgs=(tmp_path / "out" / "deck.apkg",),
        probe_addon=None,
        probe_package="zz_probe",
    )

    prepare_base(config, base, include_probe=True)

    init_file = base / "addons21" / "zz_probe" / "__init__.py"
    assert init_file.exists()
    assert "builtin_deck_smoke" in init_file.read_text(encoding="utf-8")


def test_prepare_base_does_not_install_builtin_probe_without_seed_apkgs(tmp_path: Path) -> None:
    base = tmp_path / "base"
    config = _config(tmp_path, probe_addon=None, probe_package="zz_probe")

    prepare_base(config, base, include_probe=True)

    assert not (base / "addons21" / "zz_probe").exists()


def _run_smoke_with_fake_anki(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    platform: str,
    allow_foreground: bool = False,
) -> dict[str, str]:
    captured: dict[str, dict[str, str]] = {}

    monkeypatch.delenv(QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV, raising=False)
    monkeypatch.setattr(runner.sys, "platform", platform)

    def fake_prepare_base(
        config: WorkbenchConfig,
        base: Path,
        *,
        include_probe: bool,
    ) -> Path:
        addons_dir = base / "addons21"
        addons_dir.mkdir(parents=True)
        return addons_dir

    def fake_run(
        command: list[str],
        env: dict[str, str],
        text: bool,
        stdout: object,
        stderr: object,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        captured["env"] = env.copy()
        Path(env[runner.RESULT_ENV]).write_text('{"ok": true}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner, "prepare_base", fake_prepare_base)
    monkeypatch.setattr(runner, "_seed_for_launch", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    status, payload = runner.run_smoke(
        _config(tmp_path),
        anki_python="/opt/anki-python",
        base=str(tmp_path / "base"),
        allow_foreground=allow_foreground,
    )

    assert status == 0
    assert payload["ok"] is True
    return captured["env"]


def test_run_smoke_asks_qt_not_to_auto_activate_on_macos_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _run_smoke_with_fake_anki(tmp_path, monkeypatch, platform="darwin")

    assert env[QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV] == "1"


def test_run_smoke_allow_foreground_opt_out_does_not_set_qt_macos_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _run_smoke_with_fake_anki(
        tmp_path,
        monkeypatch,
        platform="darwin",
        allow_foreground=True,
    )

    assert QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV not in env


def test_run_smoke_does_not_set_qt_macos_env_on_other_platforms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = _run_smoke_with_fake_anki(tmp_path, monkeypatch, platform="linux")

    assert QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV not in env


def test_run_workbench_command_reports_helper_failure() -> None:
    with pytest.raises(RuntimeError, match="helper command failed"):
        run_workbench_command(
            ["doctor"],
            {},
            workbench_python="/definitely/missing/python",
        )


def test_doctor_reports_workbench_version(tmp_path: Path) -> None:
    payload = doctor(_config(tmp_path))

    assert payload["workbench_version"]


def test_validate_probe_result_accepts_boolean_ok() -> None:
    assert validate_probe_result({"ok": True, "extra": 1}) is None
    assert validate_probe_result({"ok": False}) is None


@pytest.mark.parametrize(
    "payload",
    [
        ["not", "a", "dict"],
        {"missing": "ok"},
        {"ok": "true"},  # truthy but not a bool
        {"ok": 1},
    ],
)
def test_validate_probe_result_rejects_contract_violations(payload: object) -> None:
    error = validate_probe_result(payload)
    assert error is not None
    assert "init-probe" in error
