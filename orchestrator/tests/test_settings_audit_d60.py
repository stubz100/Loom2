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


def test_review_r7_a_field_named_only_as_a_parameter_or_key_fails(monkeypatch, capsys):
    """R7: a bare name — a function parameter or keyword with the field's name, a dict key — is not a read from the recipe."""
    mod = _audit()
    assert not mod.read_in("def f(knob_r7=3):\n    return g(knob_r7=knob_r7, d={'knob_r7': 1}, o=self.knob_r7)", "knob_r7")
    assert mod.read_in("x = recipe.knob_r7", "knob_r7") and mod.read_in('x = getattr(recipe, "knob_r7", 0)', "knob_r7")

    class Bogus(BaseModel):
        knob_param_only_r7: int = 3
    Bogus.__module__ = recipes.__name__
    monkeypatch.setattr(recipes, "Bogus", Bogus, raising=False)
    real = mod._sources
    monkeypatch.setattr(mod, "_sources", lambda files: real(files) + "\ndef helper(knob_param_only_r7: int = 3):\n    return {\"knob_param_only_r7\": knob_param_only_r7}\n")
    monkeypatch.setattr(sys, "argv", ["settings_audit.py"])
    assert mod.main() == 1
    assert "Bogus.knob_param_only_r7" in capsys.readouterr().out
