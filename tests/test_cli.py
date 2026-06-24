from __future__ import annotations

from anki_addon_workbench.cli import build_parser


def test_parser_accepts_public_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["doctor"]).command == "doctor"
    assert parser.parse_args(["smoke"]).command == "smoke"
    assert parser.parse_args(["launch"]).command == "launch"
    assert parser.parse_args(["location"]).command == "location"
    assert parser.parse_args(["move", "1", "2"]).command == "move"
    assert parser.parse_args(["click"]).button == 1
    assert parser.parse_args(["key", "Escape"]).keys == ["Escape"]
    assert parser.parse_args(["type", "hello"]).text == "hello"
    assert parser.parse_args(["dockerfile", "--out", "Dockerfile"]).out == "Dockerfile"
    assert parser.parse_args(["init-probe", "--out", "probe"]).out == "probe"
