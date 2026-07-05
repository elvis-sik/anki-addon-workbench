from __future__ import annotations

import urllib.request
from pathlib import Path

from anki_addon_workbench.card_render import (
    HARNESS_PATH,
    CardMediaServer,
    probe_samples_to_card_sides,
)


def test_probe_samples_to_card_sides_extracts_question_and_answer_html() -> None:
    sides = probe_samples_to_card_sides(
        [
            {
                "card_id": 123,
                "note_id": 456,
                "question_html": "<div>front</div>",
                "answer_html": "<div>back</div>",
            }
        ]
    )

    assert [side.side for side in sides] == ["question", "answer"]
    assert [side.html for side in sides] == ["<div>front</div>", "<div>back</div>"]


def test_card_media_server_serves_harness_and_media(tmp_path: Path) -> None:
    media = tmp_path / "media"
    media.mkdir()
    (media / "_script.js").write_text("window.loaded = true;\n", encoding="utf-8")

    with CardMediaServer(media) as server:
        with urllib.request.urlopen(f"{server.base_url}{HARNESS_PATH}") as response:
            harness = response.read().decode("utf-8")
        with urllib.request.urlopen(f"{server.base_url}/_script.js") as response:
            script = response.read().decode("utf-8")

    assert "__aawInjectCard" in harness
    assert script == "window.loaded = true;\n"
