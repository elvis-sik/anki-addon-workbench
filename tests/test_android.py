from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from anki_addon_workbench.android import (
    ANDROID_STORAGE_CLEANUP_TIMEOUT,
    ANKIDROID_INTENT_HANDLER,
    ANKIDROID_PACKAGE,
    CommandResult,
    _inspection_expression,
    accept_scheduler_upgrade,
    clear_ankidroid_app_data,
    dump_ui_tree,
    extract_apkg_for_ankidroid,
    extract_deck_names,
    find_flashcard_cdp_target,
    parse_bounds,
    parse_media_store_id,
    start_ankidroid,
    tap_first_deck_row,
)


class FakeUrlResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> FakeUrlResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


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


def test_find_flashcard_cdp_target_polls_until_webview_target_appears(monkeypatch) -> None:
    payloads = [[], [], [{"title": "AnkiDroid Flashcard", "id": "card"}]]
    sleeps: list[float] = []

    def fake_urlopen(url: str, *, timeout: float) -> FakeUrlResponse:
        assert url == "http://127.0.0.1:9222/json"
        assert timeout > 0
        return FakeUrlResponse(payloads.pop(0))

    monkeypatch.setattr("anki_addon_workbench.android.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("anki_addon_workbench.android.time.sleep", sleeps.append)

    target = find_flashcard_cdp_target(port=9222, timeout=15, poll_interval=1)

    assert target == {"title": "AnkiDroid Flashcard", "id": "card"}
    assert sleeps == [1, 1]


def test_dump_ui_tree_retries_until_uiautomator_output_is_parseable(monkeypatch) -> None:
    outputs = ["", "", '<hierarchy><node text="Ready" /></hierarchy>']
    sleeps: list[float] = []

    class FakeDevice:
        def run(self, args: list[str], *, check: bool = True) -> CommandResult:
            if args[:1] == ["exec-out"]:
                return CommandResult(command=args, returncode=0, stdout=outputs.pop(0), stderr="")
            return CommandResult(command=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("anki_addon_workbench.android.time.sleep", sleeps.append)

    root = dump_ui_tree(FakeDevice(), timeout=5, poll_interval=0.3)  # type: ignore[arg-type]

    node = root.find("node")
    assert node is not None
    assert node.attrib["text"] == "Ready"
    assert sleeps == [0.3, 0.3]


def test_dump_ui_tree_raises_timeout_error_with_uiautomator_diagnostics(monkeypatch) -> None:
    class FakeDevice:
        def run(self, args: list[str], *, check: bool = True) -> CommandResult:
            if args[:1] == ["shell"]:
                return CommandResult(
                    command=args,
                    returncode=1,
                    stdout="",
                    stderr="ERROR: could not get idle state.",
                )
            return CommandResult(command=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("anki_addon_workbench.android.time.sleep", lambda _: None)

    with pytest.raises(TimeoutError, match="could not get idle state"):
        dump_ui_tree(FakeDevice(), timeout=0.01, poll_interval=0.01)  # type: ignore[arg-type]


def test_accept_scheduler_upgrade_taps_positive_dialog_button(monkeypatch) -> None:
    root = ElementTree.fromstring(
        """
        <hierarchy>
          <node text="Scheduler upgrade required" />
          <node resource-id="android:id/button3" text="Learn More"
                clickable="true" bounds="[10,20][110,120]" />
          <node resource-id="android:id/button1" text="OK"
                clickable="true" bounds="[210,220][310,320]" />
        </hierarchy>
        """
    )

    class FakeDevice:
        taps: list[tuple[int, int]] = []

        def tap(self, x: int, y: int) -> None:
            self.taps.append((x, y))

    monkeypatch.setattr("anki_addon_workbench.android.dump_ui_tree", lambda _: root)
    device = FakeDevice()

    assert accept_scheduler_upgrade(device, timeout=1) is True  # type: ignore[arg-type]
    assert device.taps == [(260, 270)]


def test_tap_first_deck_row_ignores_other_clickable_text(monkeypatch) -> None:
    root = ElementTree.fromstring(
        f"""
        <hierarchy>
          <node resource-id="android:id/button3" text="Learn More"
                clickable="true" bounds="[10,20][110,120]" />
          <node resource-id="{ANKIDROID_PACKAGE}:id/deck_layout" text=""
                clickable="true" bounds="[210,220][410,420]" />
        </hierarchy>
        """
    )

    class FakeDevice:
        taps: list[tuple[int, int]] = []

        def tap(self, x: int, y: int) -> None:
            self.taps.append((x, y))

    monkeypatch.setattr("anki_addon_workbench.android.dump_ui_tree", lambda _: root)
    device = FakeDevice()

    tap_first_deck_row(device, timeout=1)  # type: ignore[arg-type]

    assert device.taps == [(310, 320)]
