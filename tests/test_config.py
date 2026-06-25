from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.config import load_config


def test_loads_pyproject_table_and_resolves_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "pyproject.toml").write_text(
        """
[tool.anki-addon-workbench]
project_name = "Fixture"
addon_package = "fixture_addon"
source_root = "addon"
include = ["__init__.py"]
exclude = ["local"]
probe_addon = "tests/probe"
probe_package = "zz_probe"
anki_version = "25.09"
profile = "User 1"
docker_image = "fixture-image"
docker_workbench_spec = "anki-addon-workbench[gui]==9.9.9"
seed_apkgs = ["out/sample.apkg"]
""",
        encoding="utf-8",
    )

    config = load_config(root)

    assert config.project_name == "Fixture"
    assert config.addon_package == "fixture_addon"
    assert config.source_root == root / "addon"
    assert config.include == ("__init__.py",)
    assert ".git" in config.exclude
    assert "local" in config.exclude
    assert config.probe_addon == root / "tests" / "probe"
    assert config.probe_package == "zz_probe"
    assert config.seed_apkgs == (root / "out" / "sample.apkg",)
    assert config.docker_image == "fixture-image"
    assert config.docker_workbench_spec == "anki-addon-workbench[gui]==9.9.9"


def test_falls_back_to_anki_workbench_toml(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "anki-workbench.toml").write_text(
        """
project_name = "Fallback"
addon_package = "fallback_addon"
""",
        encoding="utf-8",
    )

    config = load_config(root)

    assert config.project_name == "Fallback"
    assert config.addon_package == "fallback_addon"
    assert config.source_root == root
    assert config.docker_workbench_spec == "anki-addon-workbench[gui]"


def test_requires_addon_package(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "anki-workbench.toml").write_text(
        'project_name = "Broken"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="addon_package"):
        load_config(root)


def test_allows_deck_only_config_with_seed_apkgs(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / "anki-workbench.toml").write_text(
        """
project_name = "Deck Fixture"
seed_apkgs = ["out/deck.apkg"]
probe_addon = "tests/probe"
""",
        encoding="utf-8",
    )

    config = load_config(root)

    assert config.addon_package is None
    assert config.seed_apkgs == (root / "out" / "deck.apkg",)
    assert config.probe_addon == root / "tests" / "probe"
