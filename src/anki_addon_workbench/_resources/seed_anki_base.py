from __future__ import annotations

import argparse
from pathlib import Path

from anki.collection import Collection
from aqt.profiles import ProfileManager


def import_apkg(collection: Collection, path: Path) -> None:
    try:
        from anki.collection import ImportAnkiPackageOptions, ImportAnkiPackageRequest

        collection.import_anki_package(
            ImportAnkiPackageRequest(
                package_path=str(path),
                options=ImportAnkiPackageOptions(
                    merge_notetypes=True,
                    with_scheduling=False,
                    with_deck_configs=True,
                ),
            )
        )
    except (AttributeError, ImportError):
        from anki.importing import AnkiPackageImporter

        AnkiPackageImporter(collection, str(path)).run()


def seed_base(base: Path, profile: str, lang: str, import_apkgs: list[Path]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    manager = ProfileManager(base)
    manager.setupMeta()
    manager.meta["defaultLang"] = lang
    manager.meta["firstRun"] = False
    manager.create(profile)
    manager.load(profile)
    manager.save()
    collection_path = manager.collectionPath()
    assert manager.db is not None
    manager.db.close()
    if import_apkgs:
        collection = Collection(collection_path)
        try:
            for apkg in import_apkgs:
                import_apkg(collection, apkg)
        finally:
            collection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--profile", default="User 1")
    parser.add_argument("--lang", default="en_US")
    parser.add_argument("--import-apkg", action="append", default=[])
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    seed_base(
        Path(args.base),
        args.profile,
        args.lang,
        [Path(path) for path in args.import_apkg],
    )
