from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .addon_copy import copy_filtered_tree
from .config import WorkbenchConfig
from .profile import default_anki_bin, default_anki_python, direct_runner_path, path_exists, seed_base
from .resources import text_resource
from .types import JsonDict

DEFAULT_TIMEOUT_SECONDS = 45

# Probe contract: the workbench passes these file paths to the probe add-on via
# the environment. The probe writes its JSON result (with a boolean ``ok``) to
# RESULT_ENV; SCREENSHOT_ENV is an optional path a probe may capture into.
RESULT_ENV = "ANKI_ADDON_WORKBENCH_RESULT"
SCREENSHOT_ENV = "ANKI_ADDON_WORKBENCH_SCREENSHOT"
DECK_SMOKE_RENDER_LIMIT_ENV = "ANKI_ADDON_WORKBENCH_DECK_SMOKE_RENDER_LIMIT"
DECK_SMOKE_INCLUDE_HTML_ENV = "ANKI_ADDON_WORKBENCH_DECK_SMOKE_INCLUDE_HTML"
QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV = "QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"

# Helper add-on injected into host GUI runs on macOS (unless foreground mode is
# requested) so the disposable Anki window never activates or covers the
# user's screen. Runtime kill-switch: ANKI_ADDON_WORKBENCH_STEALTH=0.
STEALTH_PACKAGE = "zz_workbench_stealth"

# Printed by aqt itself once the main window is up; used as the readiness
# marker where xdotool cannot see windows (macOS, or xdotool not installed).
STARTUP_MARKER = "Starting main loop"


def stealth_default(*, allow_foreground: bool, xvfb: bool) -> bool:
    """Whether to inject the stealth helper: macOS host GUI runs only."""
    return sys.platform == "darwin" and not allow_foreground and not xvfb


def validate_probe_result(payload: object) -> str | None:
    """Return a human-readable error if a probe result violates the contract.

    The contract: the probe writes a JSON object with a top-level boolean ``ok``.
    Returns ``None`` when the payload is valid.
    """
    if not isinstance(payload, dict):
        return (
            f"probe wrote a result to ${RESULT_ENV} that was not a JSON object. "
            "Scaffold a correct probe with `anki-workbench init-probe`."
        )
    if not isinstance(payload.get("ok"), bool):
        return (
            "probe result is missing the required boolean 'ok' field. The probe "
            f"must write JSON with a top-level boolean 'ok' to ${RESULT_ENV}. "
            "Scaffold a correct probe with `anki-workbench init-probe`."
        )
    return None


@dataclass(frozen=True)
class AnkiLaunch:
    command: list[str]
    anki_bin: str
    anki_python: str | None


def choose_anki_bin(config: WorkbenchConfig, override: str | None = None) -> str:
    # Environment-specific paths (e.g. the launcher-managed bin inside the Docker
    # image) are supplied via the ANKI_BIN env var rather than hardcoded here.
    return override or config.anki_bin or os.environ.get("ANKI_BIN") or default_anki_bin()


def choose_anki_python(
    config: WorkbenchConfig,
    anki_bin: str,
    *,
    override: str | None = None,
    no_direct_python: bool = False,
) -> str | None:
    if override:
        return override
    if config.anki_python:
        return config.anki_python
    env_python = os.environ.get("ANKI_PYTHON")
    if env_python:
        return env_python
    if no_direct_python:
        return None
    return default_anki_python(anki_bin)


def build_anki_command(base: Path, profile: str, launch: AnkiLaunch) -> list[str]:
    if launch.anki_python:
        return [
            launch.anki_python,
            str(direct_runner_path()),
            "-b",
            str(base),
            "-p",
            profile,
            "--lang",
            "en",
        ]
    return [
        launch.anki_bin,
        "-b",
        str(base),
        "-p",
        profile,
        "--lang",
        "en",
    ]


def build_launch(
    config: WorkbenchConfig,
    *,
    anki_bin: str | None = None,
    anki_python: str | None = None,
    no_direct_python: bool = False,
) -> AnkiLaunch:
    resolved_bin = choose_anki_bin(config, anki_bin)
    resolved_python = choose_anki_python(
        config,
        resolved_bin,
        override=anki_python,
        no_direct_python=no_direct_python,
    )
    return AnkiLaunch(
        command=[],
        anki_bin=resolved_bin,
        anki_python=resolved_python,
    )


def prepare_base(
    config: WorkbenchConfig,
    base: Path,
    *,
    include_probe: bool,
    include_stealth: bool = False,
) -> Path:
    addons_dir = base / "addons21"
    addons_dir.mkdir(parents=True, exist_ok=True)
    if include_stealth:
        stealth_dir = addons_dir / STEALTH_PACKAGE
        stealth_dir.mkdir(parents=True, exist_ok=True)
        (stealth_dir / "__init__.py").write_text(
            text_resource("anki_addon_workbench._resources", "stealth_addon.py"),
            encoding="utf-8",
        )
    if config.addon_package is not None:
        copy_filtered_tree(
            config.source_root,
            addons_dir / config.addon_package,
            include=config.include,
            exclude=config.exclude,
        )
    if include_probe and config.probe_addon is not None:
        copy_filtered_tree(
            config.probe_addon,
            addons_dir / config.probe_package,
            exclude=config.exclude,
        )
    elif include_probe and config.seed_apkgs:
        builtin_probe = addons_dir / config.probe_package
        builtin_probe.mkdir(parents=True, exist_ok=True)
        (builtin_probe / "__init__.py").write_text(
            text_resource("anki_addon_workbench._resources", "deck_smoke_probe.py"),
            encoding="utf-8",
        )
    return addons_dir


def start_xvfb(display: str, screen: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            "Xvfb",
            display,
            "-screen",
            "0",
            screen,
            "-nolisten",
            "tcp",
            "+extension",
            "XTEST",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def terminate_process(process: subprocess.Popen[str], timeout: int = 8) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def _run_xdotool(
    args: list[str],
    env: dict[str, str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["xdotool", *args],
        check=check,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_workbench_command(
    command: list[str],
    env: dict[str, str],
    *,
    workbench_python: str,
) -> JsonDict:
    try:
        result = subprocess.run(
            [workbench_python, "-m", "anki_addon_workbench", *command],
            check=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise RuntimeError(
            "anki_addon_workbench helper command failed:\n"
            f"command: {command}\n"
            f"python: {workbench_python}\n"
            f"error: {exc}"
        ) from exc
    if result.returncode != 0:
        raise RuntimeError(
            "anki_addon_workbench helper command failed:\n"
            f"command: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("anki_addon_workbench helper did not return a JSON object")
    return payload


def wait_for_window(
    process: subprocess.Popen[str],
    env: dict[str, str],
    *,
    title: str = "Anki",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    stdout_path: Path | None = None,
) -> int | None:
    # xdotool only sees X11 windows: on macOS (native windows) or when it is
    # not installed, fall back to waiting for aqt's startup marker in the
    # captured stdout log instead of window enumeration.
    if sys.platform == "darwin" or shutil.which("xdotool") is None:
        return _wait_for_startup_marker(process, timeout=timeout, stdout_path=stdout_path)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return None
        result = _run_xdotool(["search", "--name", title], env)
        if result.returncode == 0:
            ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if ids:
                return int(ids[-1])
        time.sleep(0.25)
    return None


def _wait_for_startup_marker(
    process: subprocess.Popen[str],
    *,
    timeout: int,
    stdout_path: Path | None,
    settle_seconds: float = 2.0,
    fallback_seconds: float = 15.0,
) -> int | None:
    """Wait until aqt prints STARTUP_MARKER to the stdout log.

    Returns a pseudo window id (0) on success - callers only check for None.
    Without a log to watch (or a marker, e.g. older Anki), assume the window
    is up once the process has stayed alive for ``fallback_seconds``.
    """
    start = time.monotonic()
    deadline = start + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return None
        if stdout_path is not None and stdout_path.exists():
            try:
                text = stdout_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if STARTUP_MARKER in text:
                time.sleep(settle_seconds)
                return 0 if process.poll() is None else None
        if time.monotonic() - start >= fallback_seconds:
            return 0
        time.sleep(0.25)
    return None


def _base_path(value: str | None, *, prefix: str) -> Path:
    if value:
        return Path(value)
    return Path(tempfile.mkdtemp(prefix=prefix))


def _build_env(
    *,
    display: str | None = None,
    qt_platform: str | None = None,
    prevent_macos_auto_activation: bool = False,
) -> dict[str, str]:
    env = os.environ.copy()
    if display:
        env["DISPLAY"] = display
    if qt_platform:
        env["QT_QPA_PLATFORM"] = qt_platform
    if prevent_macos_auto_activation and sys.platform == "darwin":
        env.setdefault(QT_MAC_DISABLE_FOREGROUND_TRANSFORM_ENV, "1")
    # Line-buffered child output so the startup marker reaches the captured
    # stdout log while the process is still running (see wait_for_window).
    env.setdefault("PYTHONUNBUFFERED", "1")
    env["ANKI_SINGLE_INSTANCE_KEY"] = f"anki-addon-workbench-{uuid.uuid4().hex}"
    return env


def _seed_for_launch(
    base: Path,
    config: WorkbenchConfig,
    launch: AnkiLaunch,
) -> None:
    seed_base(
        base,
        profile=config.profile,
        anki_python=launch.anki_python,
        import_apkgs=config.seed_apkgs,
    )


def run_smoke(
    config: WorkbenchConfig,
    *,
    anki_bin: str | None = None,
    anki_python: str | None = None,
    base: str | None = None,
    keep: bool = False,
    screenshot: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    no_direct_python: bool = False,
    qt_platform: str | None = None,
    xvfb: bool = False,
    display: str | None = None,
    screen: str = "1280x1024x24",
    allow_foreground: bool = False,
    deck_smoke_include_html: bool = False,
) -> tuple[int, JsonDict]:
    base_path = _base_path(base, prefix="anki-workbench-smoke-")
    result_path = base_path / "gui-smoke-result.json"
    screenshot_path = Path(screenshot) if screenshot else base_path / "gui-smoke-screenshot.png"
    stdout_path = base_path / "anki-stdout.log"
    stderr_path = base_path / "anki-stderr.log"

    env = _build_env(
        display=display,
        qt_platform=qt_platform,
        prevent_macos_auto_activation=not allow_foreground,
    )
    if not env.get("DISPLAY"):
        env["DISPLAY"] = ":99"

    xvfb_process: subprocess.Popen[str] | None = None
    if xvfb:
        xvfb_process = start_xvfb(env["DISPLAY"], screen)
        time.sleep(0.4)

    launch = build_launch(
        config,
        anki_bin=anki_bin,
        anki_python=anki_python,
        no_direct_python=no_direct_python,
    )
    command = build_anki_command(base_path, config.profile, launch)
    payload: JsonDict

    try:
        prepare_base(
            config,
            base_path,
            include_probe=True,
            include_stealth=stealth_default(allow_foreground=allow_foreground, xvfb=xvfb),
        )
        _seed_for_launch(base_path, config, launch)

        env[RESULT_ENV] = str(result_path)
        env[SCREENSHOT_ENV] = str(screenshot_path)
        env[DECK_SMOKE_RENDER_LIMIT_ENV] = str(config.deck_smoke_render_limit)
        if deck_smoke_include_html:
            env[DECK_SMOKE_INCLUDE_HTML_ENV] = "1"

        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            try:
                completed = subprocess.run(
                    command,
                    env=env,
                    text=True,
                    stdout=stdout,
                    stderr=stderr,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return 124, {
                    "ok": False,
                    "error": f"Anki GUI smoke test timed out after {timeout}s",
                    "base": str(base_path),
                    "stdout": str(stdout_path),
                    "stderr": str(stderr_path),
                }

        if not result_path.exists():
            return completed.returncode or 1, {
                "ok": False,
                "error": "Anki exited without writing a GUI smoke result",
                "returncode": completed.returncode,
                "base": str(base_path),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            }

        raw_payload = json.loads(result_path.read_text(encoding="utf-8"))
        error = validate_probe_result(raw_payload)
        if error is not None:
            invalid: JsonDict = {"ok": False, "error": error, "base": str(base_path)}
            if isinstance(raw_payload, dict):
                invalid["result"] = raw_payload
            return 1, invalid
        assert isinstance(raw_payload, dict)  # narrowed by validate_probe_result
        payload = raw_payload
        payload.setdefault("base", str(base_path))
        payload.setdefault("stdout", str(stdout_path))
        payload.setdefault("stderr", str(stderr_path))
        status = 0 if payload.get("ok") else 1
        if keep:
            payload["kept_base"] = str(base_path)
        return status, payload
    finally:
        if xvfb_process is not None:
            terminate_process(xvfb_process, timeout=2)
        if not keep and base is None:
            shutil.rmtree(base_path, ignore_errors=True)


def parse_pointer(value: str) -> tuple[int, int]:
    raw_x, raw_y = value.replace(",", " ").split()
    return (int(raw_x), int(raw_y))


def run_launch(
    config: WorkbenchConfig,
    *,
    anki_bin: str | None = None,
    anki_python: str | None = None,
    base: str | None = None,
    keep: bool = False,
    artifact_dir: str = ".tmp-gui-workbench",
    workbench_python: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    no_direct_python: bool = False,
    xvfb: bool = False,
    display: str | None = None,
    screen: str = "1280x1024x24",
    pointer: tuple[int, int] | None = None,
    no_screenshot: bool = False,
    hold: bool = False,
    allow_foreground: bool = False,
) -> tuple[int, JsonDict]:
    base_path = _base_path(base, prefix="anki-workbench-launch-")
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    stdout_path = artifacts / "anki-stdout.log"
    stderr_path = artifacts / "anki-stderr.log"
    screenshot_path = artifacts / "screenshot-000.png"
    metadata_path = artifacts / "screenshot-000.json"

    env = _build_env(
        display=display or os.environ.get("DISPLAY") or ":99",
        prevent_macos_auto_activation=not allow_foreground,
    )
    xvfb_process: subprocess.Popen[str] | None = None
    if xvfb:
        xvfb_process = start_xvfb(env["DISPLAY"], screen)
        time.sleep(0.4)

    launch = build_launch(
        config,
        anki_bin=anki_bin,
        anki_python=anki_python,
        no_direct_python=no_direct_python,
    )
    # GUI commands run pyautogui/Pillow, which live in the workbench's own
    # environment (the [gui] extra) -- not in Anki's bundled interpreter. Default
    # to this interpreter unless the caller overrides it explicitly.
    helper_python = workbench_python or sys.executable
    command = build_anki_command(base_path, config.profile, launch)
    anki_process: subprocess.Popen[str] | None = None
    output: JsonDict = {
        "ok": False,
        "base": str(base_path),
        "artifact_dir": str(artifacts),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "display": env["DISPLAY"],
    }

    try:
        prepare_base(
            config,
            base_path,
            include_probe=False,
            include_stealth=stealth_default(allow_foreground=allow_foreground, xvfb=xvfb),
        )
        _seed_for_launch(base_path, config, launch)

        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr:
            anki_process = subprocess.Popen(
                command,
                env=env,
                stdout=stdout,
                stderr=stderr,
                text=True,
            )

            window_id = wait_for_window(
                anki_process, env, timeout=timeout, stdout_path=stdout_path
            )
            if window_id is None:
                output["error"] = "Anki window was not found before timeout or process exit"
                output["returncode"] = anki_process.poll()
                return 1, output

            output["window_id"] = window_id
            output["anki_pid"] = anki_process.pid
            output["xvfb_pid"] = xvfb_process.pid if xvfb_process is not None else None
            output["command"] = command
            output["workbench_python"] = helper_python

            if pointer is not None:
                output["initial_move"] = run_workbench_command(
                    ["move", str(pointer[0]), str(pointer[1])],
                    env,
                    workbench_python=helper_python,
                )

            if not no_screenshot:
                output["screenshot"] = run_workbench_command(
                    [
                        "screenshot",
                        "--out",
                        str(screenshot_path),
                        "--meta",
                        str(metadata_path),
                    ],
                    env,
                    workbench_python=helper_python,
                )

            output["ok"] = True
            if hold:
                print(json.dumps(output, indent=2, sort_keys=True), flush=True)
                while anki_process.poll() is None:
                    time.sleep(0.5)
                return int(anki_process.returncode or 0), output
            return 0, output
    except KeyboardInterrupt:
        if anki_process is not None:
            anki_process.send_signal(signal.SIGINT)
        return 130, {**output, "ok": False, "error": "interrupted"}
    finally:
        if not hold and anki_process is not None:
            terminate_process(anki_process)
        if xvfb_process is not None and (
            not hold or anki_process is None or anki_process.poll() is not None
        ):
            terminate_process(xvfb_process, timeout=2)
        if not keep and not hold and base is None:
            shutil.rmtree(base_path, ignore_errors=True)


def doctor(config: WorkbenchConfig) -> JsonDict:
    anki_bin = choose_anki_bin(config)
    anki_python = choose_anki_python(config, anki_bin)
    from . import __version__
    from .gui import core as gui_core

    gui_status = gui_core.doctor()
    return {
        "ok": True,
        "workbench_version": __version__,
        "config": config.as_json(),
        "anki_bin": anki_bin,
        "anki_bin_exists": path_exists(Path(anki_bin)) or shutil.which(anki_bin) is not None,
        "anki_python": anki_python,
        "anki_python_exists": bool(anki_python and path_exists(Path(anki_python))),
        "docker": shutil.which("docker"),
        "xvfb": shutil.which("Xvfb"),
        "xdotool": shutil.which("xdotool"),
        "gui": gui_status,
        "python": sys.executable,
    }
