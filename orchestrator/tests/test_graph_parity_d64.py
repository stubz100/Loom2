"""D64 / D65 guard: the H2 refactors (plan → finalize → submit, the model registry) must not change a single compiled graph.

Every recipe variant `scripts/pin_review.py` compiles (17: t2i dev / turbo / Klein / refs, i2i, the inpaint modes, upscale + tiled
refine, segment, i2v Wan / FLF / LTX beats) is compiled against the pinned object_info fixture; its graph hash and summary must
equal the snapshot recorded before the refactor (`fixtures/graph_parity.json`). Regenerate only for an intended graph change:

    orchestrator/.venv/Scripts/python.exe -m pytest orchestrator/tests/test_graph_parity_d64.py --parity-update
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from loom2.engine.graphs import compile_recipe

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(__file__).parent / "fixtures" / "graph_parity.json"


def _pin_review():
    spec = importlib.util.spec_from_file_location("pin_review", REPO / "scripts" / "pin_review.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def compile_all(tmp_path: Path, object_info: dict) -> dict[str, dict]:
    pr = _pin_review()
    roster = pr.full_roster(tmp_path)
    out: dict[str, dict] = {}
    for name, recipe, inputs in pr.recipes():
        c = compile_recipe(recipe, roster, object_info, 1, "loom2/parity", ref_files=inputs.get("refs"), inputs=inputs)
        out[name] = {"graph_hash": c.graph_hash, "problems": c.problems, "summary": json.loads(json.dumps(c.summary, sort_keys=True, default=str))}
    return out


def test_graph_parity(tmp_path: Path, object_info: dict, request: pytest.FixtureRequest) -> None:
    got = compile_all(tmp_path, object_info)
    assert len(got) == 17
    if request.config.getoption("--parity-update"):
        SNAPSHOT.write_text(json.dumps(got, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("snapshot rewritten")
    want = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert sorted(got) == sorted(want)
    for name in want:
        assert got[name] == want[name], f"{name}: the compiled graph changed"
