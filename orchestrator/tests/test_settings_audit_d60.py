"""D60 (PC25): the settings audit passes on the tree as it is, and catches a recipe field nothing reads."""
import importlib.util
import sys
from pathlib import Path

from pydantic import BaseModel

from loom2 import recipes

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "settings_audit.py"


def _audit():
    spec = importlib.util.spec_from_file_location("settings_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_field_reaches_the_code_that_runs(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["settings_audit.py"])
    assert _audit().main() == 0, capsys.readouterr().out


def test_an_unread_recipe_field_fails(monkeypatch, capsys):
    class Bogus(BaseModel):
        knob_nobody_reads_d60: int = 3
    Bogus.__module__ = recipes.__name__
    monkeypatch.setattr(recipes, "Bogus", Bogus, raising=False)
    monkeypatch.setattr(sys, "argv", ["settings_audit.py"])
    assert _audit().main() == 1
    assert "Bogus.knob_nobody_reads_d60" in capsys.readouterr().out
