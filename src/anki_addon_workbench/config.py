from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


DEFAULT_EXCLUDE = (
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    "__pycache__",
    "dist",
    "build",
    "*.egg-info",
    "user_files",
)

DEFAULT_DOCKER_WORKBENCH_SPEC = "anki-addon-workbench[gui]"
DEFAULT_ANDROID_WORKBENCH_SPEC = "anki-addon-workbench"


@dataclass(frozen=True)
class WorkbenchConfig:
    root: Path
    config_file: Path
    project_name: str
    addon_package: str | None
    source_root: Path
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    seed_apkgs: tuple[Path, ...] = ()
    probe_addon: Path | None = None
    probe_package: str = "zz_anki_workbench_probe"
    deck_smoke_render_limit: int = 5
    anki_bin: str | None = None
    anki_python: str | None = None
    anki_version: str = "25.09"
    profile: str = "User 1"
    docker_image: str = "anki-addon-workbench-gui"
    docker_workbench_spec: str = DEFAULT_DOCKER_WORKBENCH_SPEC
    webkit_selectors: tuple[str, ...] = ()
    webkit_device: str = "iPhone 14"
    card_smoke_timeout_ms: int = 8000
    android_selectors: tuple[str, ...] = ()
    android_image: str = "anki-addon-workbench-android"
    android_workbench_spec: str = DEFAULT_ANDROID_WORKBENCH_SPEC
    android_ankidroid_apk: str | None = None
    android_clear_app_data: bool = False
    android_ui_dump_timeout: float = 30

    def as_json(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "config_file": str(self.config_file),
            "project_name": self.project_name,
            "addon_package": self.addon_package,
            "source_root": str(self.source_root),
            "include": list(self.include),
            "exclude": list(self.exclude),
            "seed_apkgs": [str(path) for path in self.seed_apkgs],
            "probe_addon": str(self.probe_addon) if self.probe_addon else None,
            "probe_package": self.probe_package,
            "deck_smoke_render_limit": self.deck_smoke_render_limit,
            "anki_bin": self.anki_bin,
            "anki_python": self.anki_python,
            "anki_version": self.anki_version,
            "profile": self.profile,
            "docker_image": self.docker_image,
            "docker_workbench_spec": self.docker_workbench_spec,
            "webkit_selectors": list(self.webkit_selectors),
            "webkit_device": self.webkit_device,
            "card_smoke_timeout_ms": self.card_smoke_timeout_ms,
            "android_selectors": list(self.android_selectors),
            "android_image": self.android_image,
            "android_workbench_spec": self.android_workbench_spec,
            "android_ankidroid_apk": self.android_ankidroid_apk,
            "android_clear_app_data": self.android_clear_app_data,
            "android_ui_dump_timeout": self.android_ui_dump_timeout,
        }


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not parse to a TOML table")
    return data


def _tool_table_from_pyproject(path: Path) -> dict[str, Any] | None:
    data = _read_toml(path)
    table = data.get("tool", {}).get("anki-addon-workbench")
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError("[tool.anki-addon-workbench] must be a TOML table")
    return table


def _find_pyproject_with_table(start: Path) -> tuple[Path, dict[str, Any]] | None:
    for directory in (start, *start.parents):
        candidate = directory / "pyproject.toml"
        if not candidate.exists():
            continue
        table = _tool_table_from_pyproject(candidate)
        if table is not None:
            return candidate, table
    return None


def _find_fallback_toml(start: Path) -> tuple[Path, dict[str, Any]] | None:
    for directory in (start, *start.parents):
        candidate = directory / "anki-workbench.toml"
        if candidate.exists():
            return candidate, _read_toml(candidate)
    return None


def _as_str_tuple(value: object, *, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a TOML array of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{key} must contain only strings")
        result.append(item)
    return tuple(result)


def _resolve_path_items(root: Path, values: Iterable[str], *, key: str) -> tuple[Path, ...]:
    paths: list[Path] = []
    for value in values:
        path = Path(os.path.expanduser(value))
        if not path.is_absolute():
            path = root / path
        paths.append(path)
    return tuple(paths)


def _resolve_optional_path(root: Path, value: object, *, key: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string path")
    path = Path(os.path.expanduser(value))
    if not path.is_absolute():
        path = root / path
    return path


def _resolve_path(root: Path, value: object, *, key: str, default: str) -> Path:
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string path")
    path = Path(os.path.expanduser(value))
    if not path.is_absolute():
        path = root / path
    return path


def _optional_str(value: object, *, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _required_str(table: dict[str, Any], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required and must be a non-empty string")
    return value


def _optional_positive_int(value: object, *, key: str, default: int) -> int:
    if value is None:
        return default
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _optional_positive_float(value: object, *, key: str, default: float) -> float:
    if value is None:
        return default
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


def _optional_bool(value: object, *, key: str, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _config_from_table(path: Path, table: dict[str, Any]) -> WorkbenchConfig:
    root = path.parent
    project_name = _required_str(table, "project_name")
    addon_package = _optional_str(table.get("addon_package"), key="addon_package")
    include = _as_str_tuple(table.get("include"), key="include")
    configured_exclude = _as_str_tuple(table.get("exclude"), key="exclude")
    seed_apkgs = _resolve_path_items(
        root,
        _as_str_tuple(table.get("seed_apkgs"), key="seed_apkgs"),
        key="seed_apkgs",
    )
    exclude = tuple(dict.fromkeys((*DEFAULT_EXCLUDE, *configured_exclude)))
    probe_package = _optional_str(table.get("probe_package"), key="probe_package")

    if addon_package is None and not seed_apkgs and table.get("probe_addon") is None:
        raise ValueError(
            "addon_package is required unless seed_apkgs or probe_addon is configured"
        )

    return WorkbenchConfig(
        root=root,
        config_file=path,
        project_name=project_name,
        addon_package=addon_package,
        source_root=_resolve_path(root, table.get("source_root"), key="source_root", default="."),
        include=include,
        exclude=exclude,
        seed_apkgs=seed_apkgs,
        probe_addon=_resolve_optional_path(root, table.get("probe_addon"), key="probe_addon"),
        probe_package=probe_package or "zz_anki_workbench_probe",
        deck_smoke_render_limit=_optional_positive_int(
            table.get("deck_smoke_render_limit"),
            key="deck_smoke_render_limit",
            default=5,
        ),
        anki_bin=_optional_str(table.get("anki_bin"), key="anki_bin"),
        anki_python=_optional_str(table.get("anki_python"), key="anki_python"),
        anki_version=_optional_str(table.get("anki_version"), key="anki_version") or "25.09",
        profile=_optional_str(table.get("profile"), key="profile") or "User 1",
        docker_image=_optional_str(table.get("docker_image"), key="docker_image")
        or "anki-addon-workbench-gui",
        docker_workbench_spec=_optional_str(
            table.get("docker_workbench_spec"), key="docker_workbench_spec"
        )
        or DEFAULT_DOCKER_WORKBENCH_SPEC,
        webkit_selectors=_as_str_tuple(table.get("webkit_selectors"), key="webkit_selectors"),
        webkit_device=_optional_str(table.get("webkit_device"), key="webkit_device")
        or "iPhone 14",
        card_smoke_timeout_ms=_optional_positive_int(
            table.get("card_smoke_timeout_ms"),
            key="card_smoke_timeout_ms",
            default=8000,
        ),
        android_selectors=_as_str_tuple(table.get("android_selectors"), key="android_selectors"),
        android_image=_optional_str(table.get("android_image"), key="android_image")
        or "anki-addon-workbench-android",
        android_workbench_spec=_optional_str(
            table.get("android_workbench_spec"), key="android_workbench_spec"
        )
        or DEFAULT_ANDROID_WORKBENCH_SPEC,
        android_ankidroid_apk=_optional_str(
            table.get("android_ankidroid_apk"), key="android_ankidroid_apk"
        ),
        android_clear_app_data=_optional_bool(
            table.get("android_clear_app_data"), key="android_clear_app_data"
        ),
        android_ui_dump_timeout=_optional_positive_float(
            table.get("android_ui_dump_timeout"),
            key="android_ui_dump_timeout",
            default=30,
        ),
    )


def load_config(start: str | Path | None = None) -> WorkbenchConfig:
    start_path = Path(start or ".").resolve()
    if start_path.is_file():
        start_path = start_path.parent

    found = _find_pyproject_with_table(start_path)
    if found is None:
        found = _find_fallback_toml(start_path)
    if found is None:
        raise FileNotFoundError(
            "No [tool.anki-addon-workbench] table or anki-workbench.toml was found"
        )

    path, table = found
    return _config_from_table(path, table)
