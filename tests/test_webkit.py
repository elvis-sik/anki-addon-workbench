from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.config import WorkbenchConfig
from anki_addon_workbench.webkit import run_webkit_smoke


def _config(root: Path, **overrides: object) -> WorkbenchConfig:
    params: dict[str, object] = dict(
        root=root,
        config_file=root / "pyproject.toml",
        project_name="Fixture",
        addon_package=None,
        source_root=root,
        include=(),
        exclude=(),
        seed_apkgs=(root / "deck.apkg",),
        webkit_selectors=("#answer svg",),
    )
    params.update(overrides)
    return WorkbenchConfig(**params)  # type: ignore[arg-type]


def test_run_webkit_smoke_uses_desktop_probe_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "base" / "User 1" / "collection.media"
    media.mkdir(parents=True)
    captured: dict[str, object] = {}

    def fake_run_smoke(*args: object, **kwargs: object) -> tuple[int, dict[str, object]]:
        captured["run_smoke_kwargs"] = kwargs
        return 0, {
            "ok": True,
            "media_dir": str(media),
            "samples": [
                {
                    "card_id": 1,
                    "note_id": 2,
                    "question_html": "<div id='answer'><svg></svg></div>",
                    "answer_html": "<div id='answer'><svg></svg></div>",
                }
            ],
        }

    def fake_render(*args: object, **kwargs: object) -> dict[str, object]:
        captured["render_args"] = args
        captured["render_kwargs"] = kwargs
        return {"ok": True, "checks": []}

    monkeypatch.setattr("anki_addon_workbench.webkit.run_smoke", fake_run_smoke)
    monkeypatch.setattr("anki_addon_workbench.webkit.run_webkit_render_smoke", fake_render)

    status, payload = run_webkit_smoke(_config(tmp_path), base=str(tmp_path / "base"))

    assert status == 0
    assert payload["ok"] is True
    assert captured["run_smoke_kwargs"]["deck_smoke_include_html"] is True  # type: ignore[index]
    assert captured["render_kwargs"]["media_dir"] == media  # type: ignore[index]
    assert captured["render_kwargs"]["selectors"] == ("#answer svg",)  # type: ignore[index]


def test_run_webkit_smoke_reports_missing_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media = tmp_path / "media"
    media.mkdir()

    monkeypatch.setattr(
        "anki_addon_workbench.webkit.run_smoke",
        lambda *args, **kwargs: (0, {"ok": True, "media_dir": str(media), "samples": []}),
    )

    status, payload = run_webkit_smoke(_config(tmp_path), base=str(tmp_path / "base"))

    assert status == 1
    assert payload["ok"] is False
    assert "question_html" in str(payload["error"])
