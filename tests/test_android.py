from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from anki_addon_workbench.android import (
    _inspection_expression,
    extract_deck_names,
    parse_bounds,
    parse_media_store_id,
)


def test_parse_media_store_id_finds_matching_download() -> None:
    output = """
Row: 0 _id=12, _display_name=other.apkg
Row: 1 _id=34, _display_name=aaw-deck.apkg
"""

    assert parse_media_store_id(output, "aaw-deck.apkg") == "34"


def test_parse_bounds_returns_coordinates() -> None:
    assert parse_bounds("[10,20][110,220]") == (10, 20, 110, 220)


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


def test_inspection_expression_embeds_selectors_as_json() -> None:
    expression = _inspection_expression(("#answer svg",))

    assert '"#answer svg"' in expression
    assert "document.querySelectorAll(selector)" in expression
