from __future__ import annotations

import unittest

from anki_addon_workbench.cli import build_parser


class CliTest(unittest.TestCase):
    def test_parser_accepts_public_commands(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.parse_args(["doctor"]).command, "doctor")
        self.assertEqual(parser.parse_args(["smoke"]).command, "smoke")
        self.assertEqual(parser.parse_args(["launch"]).command, "launch")
        self.assertEqual(parser.parse_args(["location"]).command, "location")
        self.assertEqual(parser.parse_args(["move", "1", "2"]).command, "move")
        self.assertEqual(parser.parse_args(["click"]).button, 1)
        self.assertEqual(parser.parse_args(["key", "Escape"]).keys, ["Escape"])
        self.assertEqual(parser.parse_args(["type", "hello"]).text, "hello")
        self.assertEqual(parser.parse_args(["dockerfile", "--out", "Dockerfile"]).out, "Dockerfile")


if __name__ == "__main__":
    unittest.main()
