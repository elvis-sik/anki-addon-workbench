from __future__ import annotations

import contextlib
import json
import mimetypes
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlsplit

from .types import JsonDict

CardSide = Literal["question", "answer"]

HARNESS_PATH = "/_anki_addon_workbench_card.html"

INJECTION_HARNESS = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Anki Add-on Workbench Card Harness</title>
    <style>
      body { margin: 0; padding: 16px; }
    </style>
  </head>
  <body class="card">
    <div id="qa"></div>
    <script>
      (function () {
        function targetUrl(target) {
          return target && (target.currentSrc || target.src || target.href || "");
        }

        function serializeError(kind, event) {
          var target = event && event.target;
          var payload = {
            kind: kind,
            message: String((event && (event.message || event.reason)) || ""),
            filename: String((event && event.filename) || ""),
            lineno: Number((event && event.lineno) || 0),
            colno: Number((event && event.colno) || 0),
            target: target ? String(target.tagName || target.nodeName || "") : "",
            url: String(targetUrl(target))
          };
          if (event && event.error && event.error.stack) {
            payload.stack = String(event.error.stack);
          }
          if (event && event.reason && event.reason.stack) {
            payload.stack = String(event.reason.stack);
          }
          return payload;
        }

        window.__aawCardErrors = [];
        window.addEventListener("error", function (event) {
          window.__aawCardErrors.push(serializeError("error", event));
        }, true);
        window.addEventListener("unhandledrejection", function (event) {
          window.__aawCardErrors.push(serializeError("unhandledrejection", event));
        });

        window.__aawInjectCard = function (html) {
          var qa = document.getElementById("qa");
          qa.innerHTML = html;
          var oldScripts = Array.prototype.slice.call(qa.querySelectorAll("script"));

          oldScripts.forEach(function (oldScript) {
            var script = document.createElement("script");
            for (var i = 0; i < oldScript.attributes.length; i += 1) {
              var attr = oldScript.attributes[i];
              script.setAttribute(attr.name, attr.value);
            }
            if (oldScript.src) {
              script.src = oldScript.getAttribute("src") || oldScript.src;
            } else {
              script.textContent = oldScript.textContent;
            }
            oldScript.parentNode.replaceChild(script, oldScript);
          });
        };
      }());
    </script>
  </body>
</html>
"""


@dataclass(frozen=True)
class RenderedCardSide:
    card_id: int
    note_id: int | None
    side: CardSide
    html: str


class _MediaHTTPServer(ThreadingHTTPServer):
    media_dir: Path


class _MediaRequestHandler(BaseHTTPRequestHandler):
    server: _MediaHTTPServer

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path in {"/", HARNESS_PATH}:
            self._send_text(INJECTION_HARNESS, content_type="text/html; charset=utf-8")
            return

        target = self._resolve_media_path(path)
        if target is None or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "media file not found")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_text(self, text: str, *, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _resolve_media_path(self, path: str) -> Path | None:
        rel = Path(path.lstrip("/"))
        if rel.is_absolute() or ".." in rel.parts:
            return None
        return self.server.media_dir / rel


class CardMediaServer:
    def __init__(self, media_dir: Path) -> None:
        self.media_dir = media_dir
        self._server: _MediaHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> CardMediaServer:
        server = _MediaHTTPServer(("127.0.0.1", 0), _MediaRequestHandler)
        server.media_dir = self.media_dir
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._server = server
        self._thread = thread
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("card media server is not running")
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def harness_url(self) -> str:
        return f"{self.base_url}{HARNESS_PATH}"


def probe_samples_to_card_sides(samples: object) -> list[RenderedCardSide]:
    if not isinstance(samples, list):
        return []

    sides: list[RenderedCardSide] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        card_id = sample.get("card_id")
        if not isinstance(card_id, int):
            continue
        note_id = sample.get("note_id")
        normalized_note_id = note_id if isinstance(note_id, int) else None
        for side, key in (("question", "question_html"), ("answer", "answer_html")):
            html = sample.get(key)
            if isinstance(html, str):
                sides.append(
                    RenderedCardSide(
                        card_id=card_id,
                        note_id=normalized_note_id,
                        side=side,
                        html=html,
                    )
                )
    return sides


def run_webkit_render_smoke(
    card_sides: list[RenderedCardSide],
    *,
    media_dir: Path,
    selectors: tuple[str, ...],
    timeout_ms: int,
    device_name: str,
) -> JsonDict:
    sync_playwright, timeout_error = _load_playwright()

    checks: list[JsonDict] = []
    with CardMediaServer(media_dir) as server:
        with sync_playwright() as playwright:
            device = playwright.devices.get(device_name)
            if device is None:
                known = ", ".join(sorted(playwright.devices))
                raise ValueError(f"unknown Playwright device {device_name!r}; known devices: {known}")

            browser = playwright.webkit.launch()
            try:
                context = browser.new_context(**device)
                try:
                    for card_side in card_sides:
                        checks.append(
                            _check_webkit_card_side(
                                context,
                                card_side,
                                harness_url=server.harness_url,
                                selectors=selectors,
                                timeout_ms=timeout_ms,
                                timeout_error=timeout_error,
                            )
                        )
                finally:
                    context.close()
            finally:
                browser.close()

    return {
        "ok": all(bool(check.get("ok")) for check in checks),
        "engine": "webkit",
        "device": device_name,
        "media_dir": str(media_dir),
        "card_sides": len(card_sides),
        "selectors": list(selectors),
        "checks": checks,
    }


def _load_playwright() -> tuple[Any, type[BaseException]]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "WebKit card smoke requires the optional Playwright dependency. "
            "Install `anki-addon-workbench[webkit]`, then run "
            "`python -m playwright install webkit` once in that environment."
        ) from exc
    return sync_playwright, PlaywrightTimeoutError


def _check_webkit_card_side(
    context: Any,
    card_side: RenderedCardSide,
    *,
    harness_url: str,
    selectors: tuple[str, ...],
    timeout_ms: int,
    timeout_error: type[BaseException],
) -> JsonDict:
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[JsonDict] = []

    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error"
        else None,
    )
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on(
        "response",
        lambda response: failed_requests.append(
            {"url": response.url, "status": response.status}
        )
        if response.status >= 400
        else None,
    )

    selector_checks: list[JsonDict] = []
    try:
        page.goto(harness_url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.evaluate("html => window.__aawInjectCard(html)", card_side.html)
        with contextlib.suppress(timeout_error):
            page.wait_for_load_state("networkidle", timeout=timeout_ms)

        for selector in selectors:
            try:
                page.locator(selector).first.wait_for(state="visible", timeout=timeout_ms)
                selector_checks.append({"selector": selector, "ok": True})
            except timeout_error as exc:
                selector_checks.append(
                    {"selector": selector, "ok": False, "error": str(exc)}
                )

        card_errors = page.evaluate("() => window.__aawCardErrors || []")
        if not isinstance(card_errors, list):
            card_errors = [{"kind": "internal", "message": "card error log was not a list"}]

        ok = (
            not console_errors
            and not page_errors
            and not failed_requests
            and not card_errors
            and all(bool(check.get("ok")) for check in selector_checks)
        )
        return {
            "ok": ok,
            "card_id": card_side.card_id,
            "note_id": card_side.note_id,
            "side": card_side.side,
            "selectors": selector_checks,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "card_errors": json.loads(json.dumps(card_errors)),
            "failed_requests": failed_requests,
        }
    finally:
        page.close()
