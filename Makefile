SHELL := /bin/bash
.DEFAULT_GOAL := help

UV ?= uv

.PHONY: help lock lint type test check dockerfile

help:
	@printf "Available targets:\n"
	@printf "  make lock        Resolve uv.lock\n"
	@printf "  make lint        Run ruff\n"
	@printf "  make type        Run mypy\n"
	@printf "  make test        Run unit tests\n"
	@printf "  make check       Run lint, type, and tests\n"
	@printf "  make dockerfile  Render the reusable Dockerfile template\n"

lock:
	$(UV) lock

lint:
	$(UV) run --extra dev ruff check src tests

type:
	$(UV) run --extra dev mypy src

test:
	$(UV) run python -m unittest discover -s tests -v

check: lint type test

dockerfile:
	$(UV) run anki-workbench dockerfile --out .tmp/anki-xvfb.Dockerfile
