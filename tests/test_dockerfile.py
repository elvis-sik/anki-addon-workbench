from __future__ import annotations

from pathlib import Path

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.dockerfile import render_dockerfile, write_dockerfile


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


def test_render_includes_anki_version_and_runtime_tools(tmp_path: Path) -> None:
    text = render_dockerfile(_config(tmp_path, anki_version="25.09"))

    assert "ARG ANKI_LAUNCHER_VERSION=25.09" in text
    assert "libxi6" in text
    assert "xdotool" in text
    assert "xvfb" in text
    # GUI backend deps and de-hardcoded Anki path.
    assert "pyautogui" in text
    assert "scrot" in text
    assert "ENV ANKI_BIN=" in text
    # The second repo is gone; PYTHONPATH points at the single package only.
    assert "gui-agent-workbench" not in text


def test_write_dockerfile_creates_parent_directory(tmp_path: Path) -> None:
    out = write_dockerfile(_config(tmp_path), tmp_path / "nested" / "Dockerfile")

    assert out.exists()
