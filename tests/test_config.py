from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anki_addon_workbench.config import load_config


class ConfigTest(unittest.TestCase):
    def test_loads_pyproject_table_and_resolves_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
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
""",
                encoding="utf-8",
            )

            config = load_config(root)

            self.assertEqual(config.project_name, "Fixture")
            self.assertEqual(config.addon_package, "fixture_addon")
            self.assertEqual(config.source_root, root / "addon")
            self.assertEqual(config.include, ("__init__.py",))
            self.assertIn(".git", config.exclude)
            self.assertIn("local", config.exclude)
            self.assertEqual(config.probe_addon, root / "tests" / "probe")
            self.assertEqual(config.probe_package, "zz_probe")
            self.assertEqual(config.docker_image, "fixture-image")

    def test_falls_back_to_anki_workbench_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "anki-workbench.toml").write_text(
                """
project_name = "Fallback"
addon_package = "fallback_addon"
""",
                encoding="utf-8",
            )

            config = load_config(root)

            self.assertEqual(config.project_name, "Fallback")
            self.assertEqual(config.addon_package, "fallback_addon")
            self.assertEqual(config.source_root, root)

    def test_requires_addon_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "anki-workbench.toml").write_text(
                'project_name = "Broken"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "addon_package"):
                load_config(root)


if __name__ == "__main__":
    unittest.main()
