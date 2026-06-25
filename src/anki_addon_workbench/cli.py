from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import dockerfile, scaffold
from .config import WorkbenchConfig, load_config
from .local_docker import DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR, run_docker_smoke_local
from .runner import DEFAULT_TIMEOUT_SECONDS, doctor, parse_pointer, run_launch, run_smoke
from .types import JsonDict


def _gui_core() -> Any:
    from .gui import core as gui_core

    return gui_core


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Disposable Anki profile and GUI workbench tooling for add-on development."
    )
    parser.add_argument(
        "--config-root",
        default=".",
        help="directory to search for pyproject.toml or anki-workbench.toml",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="report config and backend availability")

    smoke = subparsers.add_parser("smoke", help="run configured Anki GUI smoke test")
    smoke.add_argument("--anki-bin")
    smoke.add_argument("--anki-python")
    smoke.add_argument("--base")
    smoke.add_argument("--keep", action="store_true")
    smoke.add_argument("--screenshot")
    smoke.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    smoke.add_argument("--no-direct-python", action="store_true")
    smoke.add_argument("--qt-platform")
    smoke.add_argument("--xvfb", action="store_true")
    smoke.add_argument("--display")
    smoke.add_argument("--screen", default="1280x1024x24")
    smoke.add_argument(
        "--allow-foreground",
        "--foreground",
        dest="allow_foreground",
        action="store_true",
        help="on macOS, do not ask Qt to avoid auto-activating the smoke Anki app",
    )

    launch = subparsers.add_parser("launch", help="launch disposable Anki for agent GUI work")
    launch.add_argument("--anki-bin")
    launch.add_argument("--anki-python")
    launch.add_argument("--base")
    launch.add_argument("--keep", action="store_true")
    launch.add_argument("--artifact-dir", default=".tmp-gui-workbench")
    launch.add_argument("--workbench-python")
    launch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    launch.add_argument("--no-direct-python", action="store_true")
    launch.add_argument("--xvfb", action="store_true")
    launch.add_argument("--display")
    launch.add_argument("--screen", default="1280x1024x24")
    launch.add_argument("--pointer", type=parse_pointer)
    launch.add_argument("--no-screenshot", action="store_true")
    launch.add_argument("--hold", action="store_true")

    screenshot = subparsers.add_parser("screenshot", help="capture a cursor-marked PNG")
    screenshot.add_argument("--out", required=True)
    screenshot.add_argument("--meta")
    screenshot.add_argument("--mark", type=parse_pointer)
    screenshot.add_argument("--label")
    screenshot.add_argument("--marker-size", type=int, default=22)
    screenshot.add_argument("--no-marker", action="store_true")

    move = subparsers.add_parser("move", help="move the pointer")
    move.add_argument("x", type=int)
    move.add_argument("y", type=int)

    click = subparsers.add_parser("click", help="click the pointer")
    click.add_argument("--button", type=int, default=1)
    click.add_argument("--x", type=int)
    click.add_argument("--y", type=int)

    key = subparsers.add_parser("key", help="press one or more key names")
    key.add_argument("keys", nargs="+")

    type_cmd = subparsers.add_parser("type", help="type text")
    type_cmd.add_argument("text")

    subparsers.add_parser("location", help="print pointer and active-window metadata")

    docker = subparsers.add_parser("dockerfile", help="render the Anki Xvfb Dockerfile")
    docker.add_argument("--out", required=True)
    docker.add_argument(
        "--workbench-spec",
        help=(
            "package spec installed in the image "
            "(default: docker_workbench_spec config value)"
        ),
    )

    local = subparsers.add_parser(
        "docker-smoke-local",
        help="build a local workbench wheel, Docker image, and run smoke",
    )
    local.add_argument(
        "--workbench-source",
        default=".",
        help="local anki-addon-workbench source tree to build into a wheel",
    )
    local.add_argument(
        "--artifact-dir",
        default=DEFAULT_LOCAL_DOCKER_ARTIFACT_DIR,
        help="directory for the wheel build context, Dockerfile, and logs",
    )
    local.add_argument(
        "--image",
        help="Docker image tag (default: configured docker_image with -local suffix)",
    )
    local.add_argument(
        "--uv-command",
        default="uv",
        help='command prefix used to build the wheel, e.g. "sfw uv"',
    )
    local.add_argument(
        "--docker-command",
        default="docker",
        help="command prefix used to invoke Docker",
    )
    local.add_argument(
        "--no-cache",
        action="store_true",
        help="pass --no-cache to docker build",
    )

    probe = subparsers.add_parser(
        "init-probe", help="scaffold a ready-to-edit probe add-on for smoke tests"
    )
    probe.add_argument("--out", required=True, help="directory to create the probe add-on in")
    probe.add_argument(
        "--force", action="store_true", help="overwrite an existing __init__.py"
    )

    return parser


def _load(args: argparse.Namespace) -> WorkbenchConfig:
    return load_config(Path(args.config_root))


def dispatch(args: argparse.Namespace) -> tuple[int, JsonDict]:
    if args.command == "location":
        return 0, _gui_core().location()
    if args.command == "move":
        return 0, _gui_core().move(args.x, args.y)
    if args.command == "click":
        return 0, _gui_core().click(args.button, args.x, args.y)
    if args.command == "key":
        return 0, _gui_core().key(args.keys)
    if args.command == "type":
        return 0, _gui_core().type_text(args.text)
    if args.command == "screenshot":
        return 0, _gui_core().screenshot(
            args.out,
            meta=args.meta,
            mark=args.mark,
            label=args.label,
            marker_size=args.marker_size,
            no_marker=args.no_marker,
        )

    if args.command == "init-probe":
        path = scaffold.init_probe(args.out, force=args.force)
        return 0, {
            "ok": True,
            "probe_init": str(path),
            "probe_package": path.parent.name,
            "next": "Point `probe_addon` at this directory in [tool.anki-addon-workbench].",
        }

    config = _load(args)
    if args.command == "doctor":
        return 0, doctor(config)
    if args.command == "dockerfile":
        workbench_spec = args.workbench_spec or config.docker_workbench_spec
        path = dockerfile.write_dockerfile(config, args.out, workbench_spec=workbench_spec)
        return 0, {
            "ok": True,
            "dockerfile": str(path),
            "anki_version": config.anki_version,
            "workbench_spec": workbench_spec,
        }
    if args.command == "docker-smoke-local":
        return run_docker_smoke_local(
            config,
            workbench_source=args.workbench_source,
            artifact_dir=args.artifact_dir,
            image=args.image,
            uv_command=args.uv_command,
            docker_command=args.docker_command,
            no_cache=args.no_cache,
        )
    if args.command == "smoke":
        return run_smoke(
            config,
            anki_bin=args.anki_bin,
            anki_python=args.anki_python,
            base=args.base,
            keep=args.keep,
            screenshot=args.screenshot,
            timeout=args.timeout,
            no_direct_python=args.no_direct_python,
            qt_platform=args.qt_platform,
            xvfb=args.xvfb,
            display=args.display,
            screen=args.screen,
            allow_foreground=args.allow_foreground,
        )
    if args.command == "launch":
        return run_launch(
            config,
            anki_bin=args.anki_bin,
            anki_python=args.anki_python,
            base=args.base,
            keep=args.keep,
            artifact_dir=args.artifact_dir,
            workbench_python=args.workbench_python,
            timeout=args.timeout,
            no_direct_python=args.no_direct_python,
            xvfb=args.xvfb,
            display=args.display,
            screen=args.screen,
            pointer=args.pointer,
            no_screenshot=args.no_screenshot,
            hold=args.hold,
        )
    raise AssertionError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        status, payload = dispatch(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    if not (args.command == "launch" and getattr(args, "hold", False)):
        print(json.dumps(payload, indent=2, sort_keys=True))
    return status
