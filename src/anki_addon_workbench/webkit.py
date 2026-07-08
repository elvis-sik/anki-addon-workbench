from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from .card_render import probe_samples_to_card_sides, run_webkit_render_smoke
from .config import WorkbenchConfig
from .runner import DEFAULT_TIMEOUT_SECONDS, run_smoke
from .types import JsonDict


def _compact_desktop_payload(payload: JsonDict) -> JsonDict:
    compact: JsonDict = dict(payload)
    samples = compact.get("samples")
    if not isinstance(samples, list):
        return compact

    compact_samples: list[object] = []
    for sample in samples:
        if not isinstance(sample, dict):
            compact_samples.append(sample)
            continue
        compact_sample = dict(sample)
        for key in ("question_html", "answer_html"):
            value = compact_sample.pop(key, None)
            if isinstance(value, str):
                compact_sample[f"{key}_length"] = len(value)
        compact_samples.append(compact_sample)
    compact["samples"] = compact_samples
    return compact


def run_webkit_smoke(
    config: WorkbenchConfig,
    *,
    anki_bin: str | None = None,
    anki_python: str | None = None,
    base: str | None = None,
    keep: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    no_direct_python: bool = False,
    qt_platform: str | None = None,
    xvfb: bool = False,
    display: str | None = None,
    screen: str = "1280x1024x24",
    allow_foreground: bool = False,
    selectors: tuple[str, ...] | None = None,
    device: str | None = None,
    render_timeout_ms: int | None = None,
) -> tuple[int, JsonDict]:
    base_path = Path(base) if base else Path(tempfile.mkdtemp(prefix="anki-workbench-webkit-"))
    effective_selectors = selectors if selectors is not None else config.webkit_selectors
    effective_device = device or config.webkit_device
    effective_render_timeout_ms = render_timeout_ms or config.card_smoke_timeout_ms

    try:
        desktop_status, desktop_payload = run_smoke(
            config,
            anki_bin=anki_bin,
            anki_python=anki_python,
            base=str(base_path),
            keep=keep,
            timeout=timeout,
            no_direct_python=no_direct_python,
            qt_platform=qt_platform,
            xvfb=xvfb,
            display=display,
            screen=screen,
            allow_foreground=allow_foreground,
            deck_smoke_include_html=True,
        )
        if desktop_status != 0 or not bool(desktop_payload.get("ok")):
            return desktop_status or 1, {
                "ok": False,
                "stage": "desktop_probe",
                "desktop_smoke": desktop_payload,
            }

        media_dir_value = desktop_payload.get("media_dir")
        if not isinstance(media_dir_value, str) or not media_dir_value:
            return 1, {
                "ok": False,
                "stage": "desktop_probe",
                "error": (
                    "desktop probe did not provide media_dir. `webkit-smoke` needs "
                    "the built-in deck probe, which is enabled for seed_apkgs when "
                    "probe_addon is omitted."
                ),
                "desktop_smoke": desktop_payload,
            }

        card_sides = probe_samples_to_card_sides(desktop_payload.get("samples"))
        desktop_summary = _compact_desktop_payload(desktop_payload)
        if not card_sides:
            return 1, {
                "ok": False,
                "stage": "desktop_probe",
                "error": (
                    "desktop probe did not provide question_html/answer_html samples. "
                    "`webkit-smoke` needs rendered card HTML from the built-in deck probe."
                ),
                "desktop_smoke": desktop_summary,
            }

        media_dir = Path(media_dir_value)
        if not media_dir.is_dir():
            return 1, {
                "ok": False,
                "stage": "desktop_probe",
                "error": f"desktop probe media_dir does not exist: {media_dir}",
                "desktop_smoke": desktop_summary,
            }

        try:
            webkit_payload = run_webkit_render_smoke(
                card_sides,
                media_dir=media_dir,
                selectors=effective_selectors,
                timeout_ms=effective_render_timeout_ms,
                device_name=effective_device,
            )
        except Exception as exc:
            return 1, {
                "ok": False,
                "stage": "webkit",
                "error": str(exc),
                "desktop_smoke": desktop_summary,
            }

        ok = bool(webkit_payload.get("ok"))
        payload: JsonDict = {
            "ok": ok,
            "stage": "complete" if ok else "webkit",
            "base": str(base_path),
            "desktop_smoke": desktop_summary,
            "webkit": webkit_payload,
        }
        if keep:
            payload["kept_base"] = str(base_path)
        return (0 if ok else 1), payload
    finally:
        if not keep and base is None:
            shutil.rmtree(base_path, ignore_errors=True)
