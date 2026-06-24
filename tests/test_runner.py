from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.runner import (
    build_anki_command,
    build_launch,
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


def test_run_workbench_command_reports_helper_failure() -> None:
    with pytest.raises(RuntimeError, match="helper command failed"):
        run_workbench_command(
            ["doctor"],
            {},
            workbench_python="/definitely/missing/python",
        )


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
