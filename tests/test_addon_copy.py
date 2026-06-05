from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from anki_addon_workbench.addon_copy import copy_filtered_tree


class AddonCopyTest(unittest.TestCase):
    def test_include_copies_only_requested_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dst"
            src.mkdir()
            (src / "__init__.py").write_text("# add-on\n", encoding="utf-8")
            (src / "manifest.json").write_text("{}", encoding="utf-8")
            (src / "tests").mkdir()
            (src / "tests" / "test_addon.py").write_text("pass\n", encoding="utf-8")

            copy_filtered_tree(
                src,
                dst,
                include=("__init__.py", "manifest.json"),
                exclude=("tests",),
            )

            self.assertTrue((dst / "__init__.py").exists())
            self.assertTrue((dst / "manifest.json").exists())
            self.assertFalse((dst / "tests").exists())

    def test_exclude_applies_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dst"
            src.mkdir()
            (src / "keep.py").write_text("x = 1\n", encoding="utf-8")
            (src / "__pycache__").mkdir()
            (src / "__pycache__" / "keep.pyc").write_text("no\n", encoding="utf-8")
            (src / "nested").mkdir()
            (src / "nested" / ".pytest_cache").mkdir()
            (src / "nested" / ".pytest_cache" / "x").write_text("no\n", encoding="utf-8")

            copy_filtered_tree(src, dst, exclude=("__pycache__", ".pytest_cache"))

            self.assertTrue((dst / "keep.py").exists())
            self.assertFalse((dst / "__pycache__").exists())
            self.assertFalse((dst / "nested" / ".pytest_cache").exists())

    def test_include_must_match_something(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            dst = root / "dst"
            src.mkdir()

            with self.assertRaises(FileNotFoundError):
                copy_filtered_tree(src, dst, include=("missing.py",))


if __name__ == "__main__":
    unittest.main()
