from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.runner import (
    build_anki_command,
    build_launch,
    prepare_base,
    run_workbench_command,
)


class RunnerTest(unittest.TestCase):
    def test_builds_direct_python_command(self) -> None:
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
            launch = build_launch(config, anki_bin="/opt/anki", anki_python="/opt/python")

            command = build_anki_command(root / "base", config.profile, launch)

            self.assertEqual(command[0], "/opt/python")
            self.assertIn("-b", command)
            self.assertIn(str(root / "base"), command)

    def test_builds_plain_anki_command(self) -> None:
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
            launch = build_launch(config, anki_bin="/opt/anki", no_direct_python=True)

            command = build_anki_command(root / "base", config.profile, launch)

            self.assertEqual(command[0], "/opt/anki")
            self.assertIn("--lang", command)

    def test_prepare_base_installs_addon_and_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            addon = root / "addon"
            probe = root / "probe"
            base = root / "base"
            addon.mkdir()
            probe.mkdir()
            (addon / "__init__.py").write_text("# addon\n", encoding="utf-8")
            (probe / "__init__.py").write_text("# probe\n", encoding="utf-8")
            config = WorkbenchConfig(
                root=root,
                config_file=root / "pyproject.toml",
                project_name="Fixture",
                addon_package="fixture_addon",
                source_root=addon,
                include=("__init__.py",),
                exclude=(),
                probe_addon=probe,
                probe_package="zz_probe",
            )

            prepare_base(config, base, include_probe=True)

            self.assertTrue((base / "addons21" / "fixture_addon" / "__init__.py").exists())
            self.assertTrue((base / "addons21" / "zz_probe" / "__init__.py").exists())

    def test_run_workbench_command_reports_helper_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "helper command failed"):
            run_workbench_command(
                ["doctor"],
                {},
                workbench_python="/definitely/missing/python",
            )


if __name__ == "__main__":
    unittest.main()
