from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path


def _matches(pattern: str, rel_posix: str) -> bool:
    normalized = pattern.strip("/")
    if not normalized:
        return False
    name = rel_posix.rsplit("/", 1)[-1]
    return (
        fnmatch.fnmatch(rel_posix, normalized)
        or fnmatch.fnmatch(name, normalized)
        or rel_posix == normalized
        or rel_posix.startswith(f"{normalized}/")
    )


def should_exclude(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    rel = path.relative_to(root).as_posix()
    if not rel:
        return False
    return any(_matches(pattern, rel) for pattern in patterns)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_directory(src: Path, dst: Path, root: Path, exclude: tuple[str, ...]) -> None:
    for child in src.iterdir():
        if should_exclude(child, root, exclude):
            continue
        target = dst / child.name
        if child.is_dir():
            _copy_directory(child, target, root, exclude)
        elif child.is_file():
            _copy_file(child, target)


def _copy_entry(src: Path, dst: Path, root: Path, exclude: tuple[str, ...]) -> None:
    if should_exclude(src, root, exclude):
        return
    if src.is_dir():
        _copy_directory(src, dst, root, exclude)
    elif src.is_file():
        _copy_file(src, dst)


def copy_filtered_tree(
    source_root: Path,
    destination: Path,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> None:
    source_root = source_root.resolve()
    if not source_root.exists():
        raise FileNotFoundError(f"source root does not exist: {source_root}")

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    if include:
        matched = False
        for pattern in include:
            entries = sorted(source_root.glob(pattern))
            if not entries:
                continue
            matched = True
            for entry in entries:
                rel = entry.resolve().relative_to(source_root)
                _copy_entry(entry.resolve(), destination / rel, source_root, exclude)
        if not matched:
            raise FileNotFoundError(f"include patterns matched nothing under {source_root}")
        return

    for child in source_root.iterdir():
        _copy_entry(child, destination / child.name, source_root, exclude)
