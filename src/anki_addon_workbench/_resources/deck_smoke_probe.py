"""Built-in APKG/deck smoke probe for anki-addon-workbench."""

from __future__ import annotations

import json
import os
import re
import traceback
from html import unescape
from pathlib import Path

from aqt import gui_hooks, mw
from aqt.qt import QTimer

RESULT_ENV = "ANKI_ADDON_WORKBENCH_RESULT"
RENDER_LIMIT_ENV = "ANKI_ADDON_WORKBENCH_DECK_SMOKE_RENDER_LIMIT"
INCLUDE_HTML_ENV = "ANKI_ADDON_WORKBENCH_DECK_SMOKE_INCLUDE_HTML"
SETTLE_MS = 500


def _render_limit() -> int:
    raw = os.environ.get(RENDER_LIMIT_ENV, "5")
    try:
        limit = int(raw)
    except ValueError:
        return 5
    return min(max(limit, 1), 50)


def _preview(html: str, limit: int = 120) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(unescape(text).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def _include_html() -> bool:
    return os.environ.get(INCLUDE_HTML_ENV) in {"1", "true", "True", "yes", "on"}


def _media_dir() -> str | None:
    if mw is None or mw.col is None:
        return None
    media = getattr(mw.col, "media", None)
    if media is None:
        return None
    dir_method = getattr(media, "dir", None)
    if callable(dir_method):
        return str(dir_method())
    path = getattr(media, "_dir", None)
    return str(path) if path is not None else None


def run_checks() -> dict[str, object]:
    if mw is None or mw.col is None:
        return {"ok": False, "error": "Anki main window or collection is unavailable"}

    col = mw.col
    render_limit = _render_limit()
    include_html = _include_html()
    card_count = int(col.card_count() or 0)
    note_count = int(col.note_count() or 0)
    deck_names = sorted(deck.name for deck in col.decks.all_names_and_ids())
    notetype_names = sorted(nt.name for nt in col.models.all_names_and_ids())
    card_ids = [
        int(card_id)
        for card_id in col.db.list(
            f"select id from cards order by id limit {render_limit}"
        )
    ]

    samples = []
    render_failures = []
    for card_id in card_ids:
        try:
            card = col.get_card(card_id)
            question = card.question()
            answer = card.answer()
            samples.append(
                {
                    "card_id": card_id,
                    "note_id": int(card.nid),
                    "deck_id": int(card.did),
                    "template_ord": int(card.ord),
                    "question_length": len(question),
                    "answer_length": len(answer),
                    "question_preview": _preview(question),
                    "answer_preview": _preview(answer),
                    **(
                        {"question_html": question, "answer_html": answer}
                        if include_html
                        else {}
                    ),
                }
            )
        except Exception as exc:
            render_failures.append({"card_id": card_id, "error": str(exc)})

    checks = [
        {"name": "collection has cards", "ok": card_count > 0, "count": card_count},
        {"name": "collection has notes", "ok": note_count > 0, "count": note_count},
        {
            "name": "sample cards render",
            "ok": not render_failures and len(samples) == min(card_count, render_limit),
            "rendered": len(samples),
            "failures": render_failures,
        },
    ]

    return {
        "ok": all(check["ok"] for check in checks),
        "probe": "builtin_deck_smoke",
        "checks": checks,
        "collection": {
            "cards": card_count,
            "notes": note_count,
            "decks": deck_names,
            "notetypes": notetype_names,
        },
        "render_limit": render_limit,
        "media_dir": _media_dir() if include_html else None,
        "samples": samples,
    }


def _finish() -> None:
    result_path = os.environ.get(RESULT_ENV)
    try:
        payload = run_checks()
    except Exception as exc:
        payload = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}
    if result_path:
        Path(result_path).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    if mw is not None:
        mw.unloadProfileAndExit()


gui_hooks.main_window_did_init.append(lambda: QTimer.singleShot(SETTLE_MS, _finish))
