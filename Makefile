SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help lock lint type test test-xvfb check dockerfile docker-smoke-local

help:
	@printf "Available targets:\n"
	@printf "  make lock        Resolve uv.lock\n"
	@printf "  make lint        Run ruff\n"
	@printf "  make type        Run mypy\n"
	@printf "  make test        Run unit tests (GUI display tests auto-skip)\n"
	@printf "  make test-xvfb   Run GUI tests on a virtual display (Linux/Xvfb)\n"
	@printf "  make check       Run lint, type, and tests\n"
	@printf "  make dockerfile  Render the reusable Dockerfile template\n"
	@printf "  make docker-smoke-local  Build a local wheel image and run Docker smoke\n"

lock:
	$(UV) lock

lint:
	$(UV) run --extra dev ruff check src tests

type:
	$(UV) run --extra dev mypy src

test:
	$(UV) run --extra dev --extra gui pytest

test-xvfb:
	xvfb-run -a $(UV) run --extra dev --extra gui pytest tests/test_gui_xvfb.py -v

check: lint type test

dockerfile:
	$(UV) run anki-workbench dockerfile --out .tmp/anki-xvfb.Dockerfile

docker-smoke-local:
	$(UV) run anki-workbench docker-smoke-local --uv-command "$(UV)"
