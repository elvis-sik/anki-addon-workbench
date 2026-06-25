<h1 align="center">🔬 anki-addon-workbench</h1>

<p align="center">
  <em>Headless, disposable-profile testing &amp; cross-platform GUI tooling for Anki add-on and deck development.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/anki-addon-workbench/"><img alt="PyPI" src="https://img.shields.io/pypi/v/anki-addon-workbench?color=blue&logo=pypi&logoColor=white"></a>
  <a href="https://pypi.org/project/anki-addon-workbench/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/anki-addon-workbench?logo=python&logoColor=white"></a>
  <a href="https://github.com/elvis-sik/anki-addon-workbench/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/elvis-sik/anki-addon-workbench/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/elvis-sik/anki-addon-workbench/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/pypi/l/anki-addon-workbench?color=green"></a>
  <img alt="Platforms" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Xvfb-lightgrey">
</p>

Disposable Anki profile, add-on install, Docker/Xvfb, smoke-test, and GUI
workbench tooling for Anki add-on **and deck** development.

It helps an agent or developer launch Anki away from a real profile, install the
add-on under test, run a probe add-on, capture marked screenshots, and send
mouse or keyboard input — locally on macOS/Linux or inside a virtual display.

The first target users are add-on authors who want to make GUI work less manual
without risking their daily Anki profile, and deck authors who need to see how
cards actually render inside Anki (where JavaScript and styling can behave
differently than in a browser) without manually closing and reopening Anki —
which triggers a sync round-trip each time.

## 🔁 How it works

```text
        ┌──────────────────┐                        ┌──────────────────┐
        │    live Anki     │  move · click · type   │    screenshot    │
        │    disposable    │ ─────────────────────▶ │  cursor-marked   │
        │     profile      │      (pyautogui)       │   .png + .json   │
        └──────────────────┘                        └─────────┬────────┘
                  ▲                                           │
                  │           agent reads & decides           │
                  └───────────────────────────────────────────┘
```

🗑️ disposable profile · 🚫 no sync churn · 🤖 agent reads the marked shot and adjusts — then loops. No closing and reopening Anki (and no sync round-trip) between glances.

## Install

From PyPI:

```sh
# core smoke/profile/Docker tooling only (dependency-light)
uv add anki-addon-workbench

# include the GUI primitives (pyautogui + Pillow) for screenshot/move/click/type
uv add 'anki-addon-workbench[gui]'
```

(`pip install 'anki-addon-workbench[gui]'` works too.)

The GUI extra is optional: the core `smoke`, `launch` (without screenshots),
`profile`, and `dockerfile` tooling has no heavy dependencies. The
screenshot/pointer/keyboard commands lazy-load pyautogui + Pillow and fail with
a clear install hint if the `[gui]` extra is missing.

**Platform notes.** GUI primitives are cross-platform via pyautogui:

- **macOS** — works against your local `/Applications/Anki.app`; grant Terminal
  (or your runner) *Screen Recording* and *Accessibility* permission once.
- **Linux/Xvfb** — works headless; pyautogui uses `scrot` + `python-xlib`
  (installed by the bundled Docker image).

## Configure An Add-On

Add this to the add-on project's `pyproject.toml`:

```toml
[tool.anki-addon-workbench]
project_name = "My Add-on"
addon_package = "my_addon"
source_root = "."
include = ["__init__.py", "manifest.json", "README.md"]
exclude = ["tests", "user_files", ".git", "__pycache__"]
probe_addon = "tests/gui_smoke/probe_addon"
anki_version = "25.09"
profile = "User 1"
docker_image = "my-addon-anki-gui"
# Optional. Override when dogfooding an unreleased workbench build.
docker_workbench_spec = "anki-addon-workbench[gui]"
```

If the project does not have a `pyproject.toml`, place the same keys in
`anki-workbench.toml`.

## CLI

```sh
anki-workbench doctor
anki-workbench smoke
anki-workbench launch --xvfb --pointer 500,180 --keep
anki-workbench screenshot --out .tmp/shot.png --meta .tmp/shot.json
anki-workbench move 500 180
anki-workbench click
anki-workbench key Escape
anki-workbench type "search text"
anki-workbench dockerfile --out tests/gui_smoke/Dockerfile
anki-workbench docker-smoke-local --uv-command "sfw uv"
anki-workbench init-probe --out tests/gui_smoke/probe_addon
```

`smoke` installs the configured add-on and optional probe add-on into a
disposable base folder, seeds the profile so the first-run language dialog does
not appear, launches Anki, waits for the probe to write JSON, prints the JSON,
and removes the base folder unless `--keep` is passed.

`launch` starts disposable Anki without the probe add-on so an agent can inspect
and interact with the live GUI. It can start Xvfb, wait for the Anki window,
move the pointer, and capture a cursor-marked screenshot.

All commands print JSON. The screenshot command draws a high-contrast synthetic
marker at the pointer (headless screenshots do not include the real cursor),
which is far more reliable than depending on the display server to render it.

> **`type` is ASCII-oriented.** It uses pyautogui's keystroke synthesis, which
> reliably types ASCII and common keys but **cannot reliably type non-ASCII text
> (e.g. CJK, accented characters)** — those need an input method the synthetic
> keystrokes bypass. For non-Latin search/input, set the field value through
> Anki/AnkiConnect rather than `type`. (This is a regression from the old
> `xdotool type` backend, traded for cross-platform support.)

## The Probe Contract

`smoke` works by installing a small **probe add-on** alongside the add-on under
test. When Anki finishes starting, the probe writes a JSON result to the path in
the `ANKI_ADDON_WORKBENCH_RESULT` environment variable and then exits Anki. The
runner reads that file, prints it, and uses `ok` for its exit status.

**Scaffold one in one command** — you rarely need to write a probe by hand:

```sh
anki-workbench init-probe --out tests/gui_smoke/probe_addon
```

This writes a documented, self-contained `__init__.py` with a `run_checks()`
function to edit. Then point `probe_addon` at that directory in your config.

The result contract:

| Field         | Type | Meaning                                                          |
| ------------- | ---- | ---------------------------------------------------------------- |
| `ok`          | bool | **Required.** Whether the probe's checks passed.                 |
| `checks`      | list | Optional. `[{"name": str, "ok": bool, ...}]` per-check detail.   |
| anything else | json | Optional. Echoed back verbatim in the smoke output.             |

The runner validates that `ok` is present and boolean; if a probe forgets it (or
never writes / never exits, which times out), the smoke output says exactly what
went wrong and points you back to `init-probe`. A probe may also read
`ANKI_ADDON_WORKBENCH_SCREENSHOT` for a path to capture a screenshot to.

## Docker/Xvfb

Render the reusable Anki launcher image template in the add-on project:

```sh
anki-workbench dockerfile --out tests/gui_smoke/Dockerfile
```

Then build it and run it with the add-on project mounted:

```sh
docker build -f my-addon/tests/gui_smoke/Dockerfile -t my-addon-anki-gui my-addon
docker run --rm -v "$PWD":/workspace -w /workspace/my-addon my-addon-anki-gui
```

The image installs the Anki Linux launcher, Xvfb, `xdotool`, `scrot`,
QtWebEngine runtime libraries, Python, and the configured workbench package spec
(`anki-addon-workbench[gui]` by default). The Anki binary path is provided via
the `ANKI_BIN` environment variable (set in the image), not hardcoded in the
library. The workbench itself is installed into the image, so generated
Dockerfiles are standalone and do not require a sibling source checkout.

When dogfooding an unreleased workbench build, either set
`docker_workbench_spec` in `[tool.anki-addon-workbench]` or pass an override:

```sh
anki-workbench dockerfile \
  --out tests/gui_smoke/Dockerfile \
  --workbench-spec "anki-addon-workbench[gui] @ https://github.com/elvis-sik/anki-addon-workbench/archive/<commit>.zip"
```

For workbench maintainers, the higher-level local-wheel path avoids publishing
or pushing before testing:

```sh
anki-workbench docker-smoke-local --uv-command "sfw uv"
```

It builds a wheel from `--workbench-source` (default: `.`), creates a small
Docker build context containing that wheel, renders a Dockerfile that installs
the wheel with `[gui]`, builds the configured image with a `-local` suffix, and
runs the configured smoke test with the project mounted at `/workspace`.
Artifacts and command logs are written under `.tmp/anki-workbench-local`.

## Development

```sh
make check
make docker-smoke-local
```

Tests run on `pytest` (`make test`) and cover config loading, add-on copy
filtering, profile seeding, command construction, Dockerfile rendering, probe
scaffolding, and the GUI marker rendering. Docker GUI smoke tests are kept behind
explicit CI commands because Anki launcher downloads and QtWebEngine startup are
comparatively slow. `make docker-smoke-local` is the maintainer confidence check
for unreleased workbench changes: it installs the local wheel into the generated
Docker image instead of pulling the published PyPI package.

## Releasing

Releases publish to PyPI via GitHub Actions using **Trusted Publishing** (OIDC) —
no API token is stored. To cut a release:

```sh
# 1. bump `version` in pyproject.toml, commit
# 2. tag and push — the tag must match the version
git tag v0.2.0
git push origin v0.2.0
```

The [`release.yml`](.github/workflows/release.yml) workflow checks that the tag
matches `pyproject.toml`, builds the sdist + wheel with `uv build`, and publishes.

One-time setup on PyPI (Account → Publishing → Add a pending publisher):

- **PyPI Project Name:** `anki-addon-workbench`
- **Owner / Repository:** your GitHub org/repo
- **Workflow name:** `release.yml`
- **Environment name:** `pypi`
