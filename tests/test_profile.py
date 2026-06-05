from __future__ import annotations

import pickle
import sqlite3
import tempfile
import unittest
from pathlib import Path

from anki_addon_workbench.profile import seed_without_anki_python


class ProfileTest(unittest.TestCase):
    def test_seed_without_anki_python_creates_profile_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            seed_without_anki_python(base, "User 1", "en_US")

            with sqlite3.connect(base / "prefs21.db") as db:
                rows = dict(db.execute("select name, data from profiles").fetchall())

            self.assertIn("_global", rows)
            self.assertIn("User 1", rows)
            meta = pickle.loads(rows["_global"])
            self.assertFalse(meta["firstRun"])
            self.assertEqual(meta["defaultLang"], "en_US")


if __name__ == "__main__":
    unittest.main()
