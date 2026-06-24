from __future__ import annotations

from dataclasses import dataclass

from ..types import JsonDict


@dataclass(frozen=True)
class PointerLocation:
    x: int
    y: int
    screen: int = 0
    window: int = 0

    def to_json(self) -> JsonDict:
        return {
            "x": self.x,
            "y": self.y,
            "screen": self.screen,
            "window": self.window,
        }


@dataclass(frozen=True)
class ActiveWindow:
    id: int | None
    name: str | None

    def to_json(self) -> JsonDict:
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True)
class Marker:
    x: int
    y: int
    size: int = 22
    label: str | None = None

    def to_json(self) -> JsonDict:
        return {
            "x": self.x,
            "y": self.y,
            "size": self.size,
            "label": self.label or f"x={self.x} y={self.y}",
        }
