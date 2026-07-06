from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from anki_addon_workbench.android import (
    ANDROID_STORAGE_CLEANUP_TIMEOUT,
    ANKIDROID_INTENT_HANDLER,
    ANKIDROID_PACKAGE,
    _inspection_expression,
    clear_ankidroid_app_data,
    extract_apkg_for_ankidroid,
    extract_deck_names,
    parse_bounds,
    parse_media_store_id,
    start_ankidroid,
)


def test_parse_media_store_id_finds_matching_download() -> None:
    output = """
Row: 0 _id=12, _display_name=other.apkg
Row: 1 _id=34, _display_name=aaw-deck.apkg
"""

    assert parse_media_store_id(output, "aaw-deck.apkg") == "34"


def test_parse_bounds_returns_coordinates() -> None:
    assert parse_bounds("[10,20][110,220]") == (10, 20, 110, 220)


def test_start_ankidroid_uses_exported_intent_handler() -> None:
    class FakeDevice:
        calls: list[list[str]]

        def __init__(self) -> None:
            self.calls = []

        def shell(self, args: list[str], **_: object) -> str:
            self.calls.append(args)
            return ""

    device = FakeDevice()

    start_ankidroid(device)  # type: ignore[arg-type]

    assert device.calls == [["am", "start", "-n", ANKIDROID_INTENT_HANDLER]]


def test_clear_ankidroid_app_data_is_explicit_pm_clear() -> None:
    class FakeDevice:
        calls: list[tuple[list[str], dict[str, object]]]

        def __init__(self) -> None:
            self.calls = []

        def shell(self, args: list[str], **kwargs: object) -> str:
            self.calls.append((args, kwargs))
            return ""

    device = FakeDevice()

    clear_ankidroid_app_data(device)  # type: ignore[arg-type]

    assert device.calls == [
        (["pm", "clear", ANKIDROID_PACKAGE], {"timeout": 60}),
        (
            ["rm", "-rf", "/sdcard/AnkiDroid"],
            {"check": False, "timeout": ANDROID_STORAGE_CLEANUP_TIMEOUT},
        ),
        (
            ["rm", "-rf", f"/sdcard/Android/data/{ANKIDROID_PACKAGE}"],
            {"check": False, "timeout": ANDROID_STORAGE_CLEANUP_TIMEOUT},
        ),
    ]


def test_extract_deck_names_from_apkg(tmp_path: Path) -> None:
    collection = tmp_path / "collection.anki2"
    with sqlite3.connect(collection) as conn:
        conn.execute("create table col (decks text)")
        conn.execute(
            "insert into col values (?)",
            [
                json.dumps(
                    {
                        "1": {"name": "Default"},
                        "2": {"name": "Decks::Fixture"},
                    }
                )
            ],
        )
    apkg = tmp_path / "deck.apkg"
    with zipfile.ZipFile(apkg, "w") as archive:
        archive.write(collection, "collection.anki2")

    assert extract_deck_names(apkg) == ["Decks::Fixture", "Default"]


def test_extract_apkg_for_ankidroid_maps_collection_and_media(tmp_path: Path) -> None:
    apkg = tmp_path / "deck.apkg"
    collection = tmp_path / "collection.anki21"
    with sqlite3.connect(collection) as conn:
        conn.execute("create table col (decks text)")
        conn.execute("create table cards (did integer)")
        conn.execute(
            "insert into col values (?)",
            [
                json.dumps(
                    {
                        "1": {"id": 1, "name": "Default"},
                        "2": {"id": 2, "name": "Nested::Deck"},
                    }
                )
            ],
        )
        conn.execute("insert into cards values (2)")
    with zipfile.ZipFile(apkg, "w") as archive:
        archive.writestr("collection.anki2", b"legacy")
        archive.write(collection, "collection.anki21")
        archive.writestr("media", json.dumps({"0": "audio.mp3", "1": "nested/image.png"}))
        archive.writestr("0", b"audio")
        archive.writestr("1", b"image")

    collection_path, media_dir, media_count = extract_apkg_for_ankidroid(
        apkg, tmp_path / "out"
    )

    with sqlite3.connect(collection_path) as conn:
        assert conn.execute("select did from cards").fetchall() == [(1,)]
        decks = json.loads(conn.execute("select decks from col").fetchone()[0])
    assert list(decks) == ["1"]
    assert decks["1"]["name"] == "Default"
    assert (media_dir / "audio.mp3").read_bytes() == b"audio"
    assert (media_dir / "nested" / "image.png").read_bytes() == b"image"
    assert media_count == 2


def test_inspection_expression_embeds_selectors_as_json() -> None:
    expression = _inspection_expression(("#answer svg",))

    assert '"#answer svg"' in expression
    assert "document.querySelectorAll(selector)" in expression
