# AGENTS.md

## Scope

These instructions apply to the `anki-addon-workbench` repository.

## Project Intent

`anki-addon-workbench` provides reusable disposable-profile, add-on install,
Docker/Xvfb, and smoke-test tooling for Anki add-on development. It is an
Anki-specific layer built on `gui-agent-workbench`.

## Development

- Keep Anki-specific behavior here; keep generic pointer, keyboard, and
  screenshot primitives in `gui-agent-workbench`.
- Treat real Anki profiles and collections as out of scope. Tests should use
  disposable base folders and fixture add-ons.
- Use `uv` for dependency management and keep the lockfile current.
- Run `make check` before committing meaningful changes.
