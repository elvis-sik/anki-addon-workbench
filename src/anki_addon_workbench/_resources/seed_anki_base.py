from __future__ import annotations

import argparse
from pathlib import Path

from aqt.profiles import ProfileManager  # type: ignore[import-not-found]


def seed_base(base: Path, profile: str, lang: str) -> None:
    base.mkdir(parents=True, exist_ok=True)
    manager = ProfileManager(base)
    manager.setupMeta()
    manager.meta["defaultLang"] = lang
    manager.meta["firstRun"] = False
    manager.create(profile)
    manager.load(profile)
    manager.save()
    assert manager.db is not None
    manager.db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--profile", default="User 1")
    parser.add_argument("--lang", default="en_US")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    seed_base(Path(args.base), args.profile, args.lang)
