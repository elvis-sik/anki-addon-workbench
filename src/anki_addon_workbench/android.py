from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import struct
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

from .config import WorkbenchConfig
from .types import JsonDict

ANKIDROID_PACKAGE = "com.ichi2.anki"
ANKIDROID_DECK_PICKER = "com.ichi2.anki/.DeckPicker"
ANKIDROID_INTENT_HANDLER = "com.ichi2.anki/.IntentHandler"
DEFAULT_ANDROID_AVD = "aaw_test"
DEFAULT_CDP_PORT = 9222


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class AndroidDevice:
    def __init__(self, adb: str = "adb") -> None:
        self.adb = adb

    def run(self, args: list[str], *, check: bool = True, timeout: int = 60) -> CommandResult:
        command = [self.adb, *args]
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        result = CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                "adb command failed:\n"
                f"command: {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        return result

    def shell(self, args: list[str], *, check: bool = True, timeout: int = 60) -> str:
        return self.run(["shell", *args], check=check, timeout=timeout).stdout

    def tap(self, x: int, y: int) -> None:
        self.shell(["input", "tap", str(x), str(y)])


def run_android_smoke(
    config: WorkbenchConfig,
    *,
    ankidroid_apk: str | None = None,
    start_emulator: bool = False,
    avd_name: str = DEFAULT_ANDROID_AVD,
    adb: str = "adb",
    emulator: str = "emulator",
    boot_timeout: int = 240,
    cdp_port: int = DEFAULT_CDP_PORT,
    selectors: tuple[str, ...] | None = None,
    render_timeout_ms: int | None = None,
) -> tuple[int, JsonDict]:
    if not config.seed_apkgs:
        return 1, {
            "ok": False,
            "error": "android-smoke requires seed_apkgs in [tool.anki-addon-workbench]",
        }

    apk = ankidroid_apk or config.android_ankidroid_apk or os.environ.get("ANKIDROID_APK")
    effective_selectors = selectors if selectors is not None else config.android_selectors
    timeout_ms = render_timeout_ms or config.card_smoke_timeout_ms
    device = AndroidDevice(adb=adb)
    emulator_process: subprocess.Popen[str] | None = None
    imported: list[JsonDict] = []

    try:
        if start_emulator:
            emulator_process = subprocess.Popen(
                [
                    emulator,
                    "-avd",
                    avd_name,
                    "-no-audio",
                    "-no-boot-anim",
                    "-gpu",
                    "swiftshader_indirect",
                    "-no-snapshot",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        wait_for_android_boot(device, timeout=boot_timeout)

        if apk:
            device.run(["install", "-r", apk], timeout=180)
        onboard_ankidroid(device)

        deck_names: list[str] = []
        for index, apkg in enumerate(config.seed_apkgs):
            deck_names.extend(extract_deck_names(apkg))
            imported.append(import_apkg(device, apkg, index=index))

        open_reviewer(device, deck_names=deck_names, timeout=max(30, timeout_ms // 1000))
        inspection = inspect_ankidroid_webview(
            device,
            selectors=effective_selectors,
            port=cdp_port,
            timeout_ms=timeout_ms,
        )
        ok = bool(inspection.get("ok"))
        return (
            0 if ok else 1,
            {
                "ok": ok,
                "engine": "android-webview",
                "selectors": list(effective_selectors),
                "seed_apkgs": [str(path) for path in config.seed_apkgs],
                "imported": imported,
                "inspection": inspection,
            },
        )
    except Exception as exc:
        return 1, {
            "ok": False,
            "engine": "android-webview",
            "error": str(exc),
            "imported": imported,
        }
    finally:
        if emulator_process is not None and emulator_process.poll() is None:
            emulator_process.terminate()
            try:
                emulator_process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                emulator_process.kill()


def wait_for_android_boot(device: AndroidDevice, *, timeout: int) -> None:
    device.run(["wait-for-device"], timeout=timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = device.shell(["getprop", "sys.boot_completed"], check=False).strip()
        if value == "1":
            return
        time.sleep(2)
    raise TimeoutError(f"Android emulator did not finish booting within {timeout}s")


def onboard_ankidroid(device: AndroidDevice) -> None:
    device.shell(["am", "start", "-n", ANKIDROID_DECK_PICKER])
    device.shell(
        ["appops", "set", "--uid", ANKIDROID_PACKAGE, "MANAGE_EXTERNAL_STORAGE", "allow"],
        check=False,
    )
    tap_text(device, ("Get Started", "GET STARTED"), timeout=12, required=False)
    tap_text(device, ("Continue", "CONTINUE", "Allow", "ALLOW"), timeout=12, required=False)


def import_apkg(device: AndroidDevice, apkg: Path, *, index: int) -> JsonDict:
    if not apkg.is_file():
        raise FileNotFoundError(apkg)

    remote_name = f"aaw-{index}-{_short_digest(apkg)}-{apkg.name}"
    remote_path = f"/sdcard/Download/{remote_name}"
    device.run(["push", str(apkg), remote_path], timeout=180)
    device.shell(
        [
            "am",
            "broadcast",
            "-a",
            "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d",
            f"file://{remote_path}",
        ],
        check=False,
    )
    content_id = wait_for_download_media_id(device, remote_name, timeout=45)
    content_uri = f"content://media/external/downloads/{content_id}"

    device.shell(["am", "force-stop", ANKIDROID_PACKAGE], check=False)
    device.shell(
        [
            "am",
            "start",
            "-a",
            "android.intent.action.VIEW",
            "-t",
            "application/apkg",
            "-d",
            content_uri,
            "--grant-read-uri-permission",
            "-n",
            ANKIDROID_INTENT_HANDLER,
        ],
        timeout=30,
    )
    tap_text(device, ("Add", "ADD"), timeout=60, required=False)
    tap_text(device, ("Import", "IMPORT"), timeout=120, required=False)
    return {"apkg": str(apkg), "remote_path": remote_path, "content_uri": content_uri}


def open_reviewer(
    device: AndroidDevice,
    *,
    deck_names: list[str],
    timeout: int,
) -> None:
    device.shell(["am", "start", "-n", ANKIDROID_DECK_PICKER])
    candidates = tuple(deck_names) + ("Default",)
    if not tap_text(device, candidates, timeout=timeout, required=False):
        tap_first_deck_row(device, timeout=timeout)
    tap_text(device, ("Study Now", "STUDY NOW"), timeout=timeout, required=False)


def inspect_ankidroid_webview(
    device: AndroidDevice,
    *,
    selectors: tuple[str, ...],
    port: int,
    timeout_ms: int,
) -> JsonDict:
    socket_name = find_webview_devtools_socket(device)
    device.run(["forward", f"tcp:{port}", f"localabstract:{socket_name}"])
    target = find_flashcard_cdp_target(port=port)
    ws_url = target.get("webSocketDebuggerUrl")
    if not isinstance(ws_url, str):
        raise RuntimeError("AnkiDroid WebView target did not expose webSocketDebuggerUrl")

    with RawCdpClient(ws_url, timeout=timeout_ms / 1000) as client:
        client.call("Runtime.enable")
        expression = _inspection_expression(selectors)
        result = client.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
    value = result.get("result", {}).get("result", {}).get("value")
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected Runtime.evaluate result: {result}")

    selector_checks = value.get("selectors")
    ok = isinstance(selector_checks, list) and all(
        isinstance(item, dict) and bool(item.get("visible")) for item in selector_checks
    )
    return {
        "ok": ok,
        "target": target,
        "socket": socket_name,
        "page": value,
    }


def find_webview_devtools_socket(device: AndroidDevice) -> str:
    proc_net = device.shell(["cat", "/proc/net/unix"])
    matches = re.findall(r"webview_devtools_remote_[0-9]+", proc_net)
    if not matches:
        raise RuntimeError("no Android WebView devtools socket found")
    return matches[0]


def find_flashcard_cdp_target(*, port: int) -> JsonDict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("CDP /json response was not a list")
    targets = [target for target in payload if isinstance(target, dict)]
    for target in targets:
        if target.get("title") == "AnkiDroid Flashcard":
            return target
    if targets:
        return targets[0]
    raise RuntimeError("CDP /json did not list any WebView targets")


def wait_for_download_media_id(device: AndroidDevice, display_name: str, *, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        output = device.shell(
            [
                "content",
                "query",
                "--uri",
                "content://media/external/downloads",
                "--projection",
                "_id:_display_name",
            ],
            check=False,
        )
        media_id = parse_media_store_id(output, display_name)
        if media_id is not None:
            return media_id
        time.sleep(1)
    raise TimeoutError(f"MediaStore did not index {display_name!r} within {timeout}s")


def parse_media_store_id(output: str, display_name: str) -> str | None:
    for line in output.splitlines():
        if display_name not in line:
            continue
        match = re.search(r"_id=([0-9]+)", line)
        if match is not None:
            return match.group(1)
    return None


def tap_text(
    device: AndroidDevice,
    texts: tuple[str, ...],
    *,
    timeout: int,
    required: bool,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        node = find_ui_node(device, texts)
        if node is not None:
            left, top, right, bottom = parse_bounds(node.attrib.get("bounds", ""))
            device.tap((left + right) // 2, (top + bottom) // 2)
            return True
        time.sleep(1)
    if required:
        raise TimeoutError(f"could not find Android UI text: {texts}")
    return False


def tap_first_deck_row(device: AndroidDevice, *, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = dump_ui_tree(device)
        for node in root.iter("node"):
            resource_id = node.attrib.get("resource-id", "")
            clickable = node.attrib.get("clickable") == "true"
            if clickable and ("deck" in resource_id.lower() or node.attrib.get("text")):
                left, top, right, bottom = parse_bounds(node.attrib.get("bounds", ""))
                if bottom > top and right > left:
                    device.tap((left + right) // 2, (top + bottom) // 2)
                    return
        time.sleep(1)
    raise TimeoutError("could not find a tappable AnkiDroid deck row")


def find_ui_node(device: AndroidDevice, texts: tuple[str, ...]) -> ElementTree.Element | None:
    wanted = {text.casefold() for text in texts if text}
    root = dump_ui_tree(device)
    for node in root.iter("node"):
        values = [
            node.attrib.get("text", ""),
            node.attrib.get("content-desc", ""),
            node.attrib.get("resource-id", ""),
        ]
        haystack = " ".join(values).casefold()
        if any(text.casefold() in haystack for text in wanted):
            return node
    return None


def dump_ui_tree(device: AndroidDevice) -> ElementTree.Element:
    device.shell(["uiautomator", "dump", "/sdcard/aaw-window.xml"], check=False)
    xml = device.run(["exec-out", "cat", "/sdcard/aaw-window.xml"], check=False).stdout
    return ElementTree.fromstring(xml)


def parse_bounds(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"\[([0-9]+),([0-9]+)\]\[([0-9]+),([0-9]+)\]", value)
    if match is None:
        raise ValueError(f"invalid Android UI bounds: {value!r}")
    return tuple(int(group) for group in match.groups())  # type: ignore[return-value]


def extract_deck_names(apkg: Path) -> list[str]:
    if not apkg.is_file():
        return []
    with tempfile.TemporaryDirectory(prefix="aaw-apkg-") as tempdir:
        with zipfile.ZipFile(apkg) as archive:
            names = set(archive.namelist())
            collection_name = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
            if collection_name not in names:
                return []
            archive.extract(collection_name, tempdir)
        collection_path = Path(tempdir) / collection_name
        with sqlite3.connect(collection_path) as conn:
            row = conn.execute("select decks from col").fetchone()
    if row is None or not isinstance(row[0], str):
        return []
    data = json.loads(row[0])
    if not isinstance(data, dict):
        return []
    names = [
        deck.get("name")
        for deck in data.values()
        if isinstance(deck, dict) and isinstance(deck.get("name"), str)
    ]
    return sorted(name for name in names if name)


class RawCdpClient:
    def __init__(self, url: str, *, timeout: float) -> None:
        self.url = url
        self.timeout = timeout
        self._socket: socket.socket | None = None
        self._next_id = 1

    def __enter__(self) -> RawCdpClient:
        parsed = urlparse(self.url)
        if parsed.scheme != "ws" or parsed.hostname is None:
            raise ValueError(f"only ws:// CDP URLs are supported: {self.url}")
        port = parsed.port or 80
        sock = socket.create_connection((parsed.hostname, port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = self._recv_until(sock, b"\r\n\r\n")
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"CDP WebSocket handshake failed: {response!r}")
        self._socket = sock
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._socket is not None:
            self._socket.close()

    def call(self, method: str, params: JsonDict | None = None) -> JsonDict:
        message_id = self._next_id
        self._next_id += 1
        self._send_json({"id": message_id, "method": method, "params": params or {}})
        while True:
            payload = self._recv_json()
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(f"CDP call {method} failed: {payload['error']}")
                return payload

    def _send_json(self, payload: JsonDict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self._send_frame(data)

    def _recv_json(self) -> JsonDict:
        while True:
            opcode, data = self._recv_frame()
            if opcode == 1:
                payload = json.loads(data.decode("utf-8"))
                if isinstance(payload, dict):
                    return payload
            elif opcode == 8:
                raise RuntimeError("CDP WebSocket closed")
            elif opcode == 9:
                self._send_frame(data, opcode=10)

    def _send_frame(self, data: bytes, *, opcode: int = 1) -> None:
        if self._socket is None:
            raise RuntimeError("CDP WebSocket is not connected")
        header = bytearray([0x80 | opcode])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0x80 | 126, *struct.pack("!H", length)])
        else:
            header.extend([0x80 | 127, *struct.pack("!Q", length)])
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self._socket.sendall(bytes(header) + mask + masked)

    def _recv_frame(self) -> tuple[int, bytes]:
        if self._socket is None:
            raise RuntimeError("CDP WebSocket is not connected")
        first, second = self._recv_exact(2)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]
        mask = self._recv_exact(4) if masked else b""
        data = self._recv_exact(length)
        if masked:
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        return opcode, data

    def _recv_exact(self, length: int) -> bytes:
        if self._socket is None:
            raise RuntimeError("CDP WebSocket is not connected")
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self._socket.recv(length - len(chunks))
            if not chunk:
                raise RuntimeError("CDP WebSocket closed while reading")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _recv_until(sock: socket.socket, marker: bytes) -> bytes:
        data = bytearray()
        while marker not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("CDP WebSocket closed during handshake")
            data.extend(chunk)
        return bytes(data)


def _inspection_expression(selectors: tuple[str, ...]) -> str:
    selector_json = json.dumps(list(selectors))
    return f"""(() => {{
  const selectors = {selector_json};
  function visible(el) {{
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style.visibility !== "hidden" &&
      style.display !== "none" &&
      rect.width > 0 &&
      rect.height > 0;
  }}
  return {{
    title: document.title,
    href: location.href,
    readyState: document.readyState,
    bodyTextLength: document.body ? document.body.innerText.length : 0,
    selectors: selectors.map((selector) => {{
      const matches = Array.from(document.querySelectorAll(selector));
      return {{
        selector,
        count: matches.length,
        visible: matches.some(visible)
      }};
    }}),
    workbenchErrors: window.__aawCardErrors || [],
    bootErrors: window.__aawBootErrors || window.SightSingingBootErrors || []
  }};
}})()"""


def _short_digest(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def ensure_android_tools() -> JsonDict:
    return {
        "adb": shutil.which("adb"),
        "emulator": shutil.which("emulator"),
        "java": shutil.which("java"),
    }
