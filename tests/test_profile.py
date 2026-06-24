from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.profile import seed_base


def test_seed_base_requires_anki_python(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no Anki Python interpreter"):
        seed_base(tmp_path, profile="User 1", anki_python=None)
