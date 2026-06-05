from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.dockerfile import render_dockerfile, write_dockerfile


class DockerfileTest(unittest.TestCase):
    def test_render_includes_anki_version_and_runtime_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = WorkbenchConfig(
                root=root,
                config_file=root / "pyproject.toml",
                project_name="Fixture",
                addon_package="fixture_addon",
                source_root=root,
                include=(),
                exclude=(),
                anki_version="25.09",
            )

            text = render_dockerfile(config)

            self.assertIn("ARG ANKI_LAUNCHER_VERSION=25.09", text)
            self.assertIn("xdotool", text)
            self.assertIn("xvfb", text)

    def test_write_dockerfile_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = WorkbenchConfig(
                root=root,
                config_file=root / "pyproject.toml",
                project_name="Fixture",
                addon_package="fixture_addon",
                source_root=root,
                include=(),
                exclude=(),
            )
            out = write_dockerfile(config, root / "nested" / "Dockerfile")

            self.assertTrue(out.exists())


if __name__ == "__main__":
    unittest.main()
