from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.addon_copy import copy_filtered_tree


def test_include_copies_only_requested_entries(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
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

    assert (dst / "__init__.py").exists()
    assert (dst / "manifest.json").exists()
    assert not (dst / "tests").exists()


def test_exclude_applies_recursively(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "keep.py").write_text("x = 1\n", encoding="utf-8")
    (src / "__pycache__").mkdir()
    (src / "__pycache__" / "keep.pyc").write_text("no\n", encoding="utf-8")
    (src / "nested").mkdir()
    (src / "nested" / ".pytest_cache").mkdir()
    (src / "nested" / ".pytest_cache" / "x").write_text("no\n", encoding="utf-8")

    copy_filtered_tree(src, dst, exclude=("__pycache__", ".pytest_cache"))

    assert (dst / "keep.py").exists()
    assert not (dst / "__pycache__").exists()
    assert not (dst / "nested" / ".pytest_cache").exists()


def test_include_must_match_something(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()

    with pytest.raises(FileNotFoundError):
        copy_filtered_tree(src, dst, include=("missing.py",))
