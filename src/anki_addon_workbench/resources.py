from __future__ import annotations

from importlib import resources
from pathlib import Path


def resource_path(package: str, name: str) -> Path:
    resource = resources.files(package).joinpath(name)
    return Path(str(resource))


def text_resource(package: str, name: str) -> str:
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")
