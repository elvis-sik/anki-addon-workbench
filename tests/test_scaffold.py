from __future__ import annotations

from pathlib import Path

import pytest

from anki_addon_workbench.scaffold import init_probe


def test_init_probe_writes_contract_compliant_template(tmp_path: Path) -> None:
    out = tmp_path / "my_probe"
    init_file = init_probe(out)

    assert init_file == out / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    # The scaffolded probe documents and honors the result contract.
    assert "ANKI_ADDON_WORKBENCH_RESULT" in text
    assert "def run_checks()" in text
    assert "unloadProfileAndExit" in text
    # The template is unlinted (.py.tmpl), so guard against shipping a probe that
    # won't even parse. (aqt isn't importable here, so we compile, not exec.)
    compile(text, str(init_file), "exec")


def test_init_probe_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    out = tmp_path / "my_probe"
    init_probe(out)

    with pytest.raises(FileExistsError):
        init_probe(out)

    # force overwrites cleanly.
    assert init_probe(out, force=True).exists()
