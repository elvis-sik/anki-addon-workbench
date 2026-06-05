# anki-addon-workbench

Disposable Anki profile, add-on install, Docker/Xvfb, smoke-test, and GUI
workbench tooling for Anki add-on development.

This project is the Anki-specific layer above
[`gui-agent-workbench`](https://github.com/elvis-sik/gui-agent-workbench). It
helps an agent or developer launch Anki away from a real profile, install the
add-on under test, run a probe add-on, capture marked screenshots, and send
mouse or keyboard input inside a virtual display.

The first target user is an add-on author who wants to make GUI work less
manual without risking their daily Anki profile.

## Install

For local development from sibling clones:

```sh
git clone git@github.com:elvis-sik/gui-agent-workbench.git
git clone git@github.com:elvis-sik/anki-addon-workbench.git
cd anki-addon-workbench
uv sync --extra dev
```

For a project that already has both repositories checked out side by side, add
`anki-addon-workbench` as an editable path dependency and let its local source
override point at `../gui-agent-workbench`.

PyPI publishing is intentionally not part of v1. Private GitHub installs are
supported once the caller has GitHub credentials for both repositories.

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
```

`smoke` installs the configured add-on and optional probe add-on into a
disposable base folder, seeds the profile so the first-run language dialog does
not appear, launches Anki, waits for the probe to write JSON, prints the JSON,
and removes the base folder unless `--keep` is passed.

`launch` starts disposable Anki without the probe add-on so an agent can inspect
and interact with the live GUI. It can start Xvfb, wait for the Anki window,
move the pointer, and capture a cursor-marked screenshot.

The screenshot, pointer, click, key, and type commands are thin pass-throughs to
`gui-agent-workbench`.

## Docker/Xvfb

Render the reusable Anki launcher image template in the add-on project:

```sh
anki-workbench dockerfile --out tests/gui_smoke/Dockerfile
```

Then build it from the add-on project and run it with a workspace mount that
contains the add-on project, `anki-addon-workbench`, and
`gui-agent-workbench` as siblings:

```sh
docker build -f my-addon/tests/gui_smoke/Dockerfile -t my-addon-anki-gui my-addon
docker run --rm -v "$PWD":/workspace -w /workspace/my-addon my-addon-anki-gui
```

The image installs the Anki Linux launcher, Xvfb, `xdotool`, QtWebEngine runtime
libraries, and Python. It expects source checkouts to be mounted at runtime, so
local edits are visible without rebuilding the image and private GitHub
credentials are not needed inside Docker.

## Development

```sh
make check
```

The unit tests cover config loading, add-on copy filtering, profile seeding,
command construction, and Dockerfile rendering. Docker GUI smoke tests are kept
behind explicit CI commands because Anki launcher downloads and QtWebEngine
startup are comparatively slow.
