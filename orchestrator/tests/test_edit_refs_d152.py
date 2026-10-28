"""D152 (post-MVP item 5): references in Edit AI — the deck's images chained as ReferenceLatents after the source's own in the inpaint
graphs (LanPaint and ICM) and the refine graph (Klein base / dev), the model's limit kept and said, none on the creative families; the
T2I graph as it was (the parity snapshot says so); the route carries them; the planner reports them."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs, pipeline  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2I, Inpaint, RefImage  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
IMG = {"image": "alley-rain_s20261004.png", "mask": "alley-rain_s20261004.png", "w": 960, "h": 544}
REFS = {"a": "hero.png", "b": "coat.png"}


def _roster():
    spec = importlib.util.spec_from_file_location("pin_review", REPO / "scripts" / "pin_review.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.full_roster(Path(tempfile.mkdtemp(prefix="refs-")))


def _latents(c: graphs.Compiled) -> list[str]:
    return [k for k, n in c.graph.items() if n["class_type"] == "ReferenceLatent"]


def test_the_inpaint_graphs_chain_the_deck_after_the_source(object_info: dict):
    roster = _roster()
    two = [RefImage(asset_id="a", note="the hero"), RefImage(asset_id="b")]
    fill = graphs.compile_recipe(Inpaint(document_id="d", mode="fill", prompt_text="her face", refs=two, seeds=[1]), roster, object_info, 1, "loom2/t", ref_files=REFS, inputs=IMG)
    lat = _latents(fill)
    assert len(lat) == 3 and lat[0] == "8"                                                 # the source's, then the two of the deck
    last = lat[-1]
    assert fill.graph["9"]["inputs"]["conditioning"] == [last, 0]                           # the guider takes the chain's end
    assert fill.graph[last]["inputs"]["conditioning"] == [lat[1], 0] and fill.graph[lat[1]]["inputs"]["conditioning"] == ["8", 0]
    assert any(n["class_type"] == "ImageScale" and n["inputs"]["width"] == 1024 for n in fill.graph.values())
    assert fill.summary["refs"] == 2 and not [p for p in fill.problems if "not in enum" not in p]
    match = graphs.compile_recipe(Inpaint(document_id="d", mode="fill_match", prompt_text="x", refs=two[:1], seeds=[1]), roster, object_info, 1, "loom2/t", ref_files=REFS, inputs=IMG)
    lat = _latents(match)
    assert len(lat) == 2 and match.graph["9"]["inputs"]["positive"] == [lat[-1], 0]        # ICM's positive from the chain's end
    plain = graphs.compile_recipe(Inpaint(document_id="d", mode="fill", prompt_text="x", seeds=[1]), roster, object_info, 1, "loom2/t", inputs=IMG)
    assert _latents(plain) == ["8"] and plain.summary["refs"] == 0                          # without a deck: the graph of before
    with pytest.raises(graphs.CompileError):                                                 # a reference not uploaded is a refusal, not a silent drop
        graphs.compile_recipe(Inpaint(document_id="d", mode="fill", prompt_text="x", refs=two, seeds=[1]), roster, object_info, 1, "loom2/t", inputs=IMG)


def test_the_refine_graph_chains_the_deck_on_the_flux_family_only(object_info: dict):
    roster = _roster()
    ref = [RefImage(asset_id="a")]
    base = graphs.compile_recipe(I2I(document_id="d", model_id="klein-base-9b", source="visible", strength=0.3, refs=ref, seeds=[1]), roster, object_info, 1, "loom2/t", ref_files=REFS, inputs=IMG)
    lat = _latents(base)
    assert len(lat) == 1 and base.graph["9"]["inputs"]["positive"] == [lat[0], 0]
    creative = next(s for s in registry.image_specs() if s.recipes.i2i and s.graph not in registry.FLUX_GRAPHS)
    other = graphs.compile_recipe(I2I(document_id="d", model_id=creative.id, source="visible", strength=0.3, refs=ref, seeds=[1]), roster, object_info, 1, "loom2/t", ref_files=REFS, inputs=IMG)
    assert _latents(other) == []                                                             # no ReferenceLatent in that family's graph


def test_the_limit_is_kept_and_said():
    spec = registry.get("klein-base-9b")
    assert spec is not None and spec.inputs.refs_max >= 1
    many = [RefImage(asset_id=f"r{i}") for i in range(spec.inputs.refs_max + 2)]
    p = pipeline.plan(I2I(document_id="d", model_id="klein-base-9b", source="visible", refs=many))
    assert p.params["refs"] == spec.inputs.refs_max and p.params["max_refs"] == spec.inputs.refs_max and p.params["refs_dropped"] == 2
    q = pipeline.plan(Inpaint(document_id="d", mode="fill", refs=many[:1]))
    assert q.params["refs"] == 1 and q.params["refs_dropped"] == 0 and q.params["max_refs"] >= 1
    creative = next(s for s in registry.image_specs() if s.recipes.i2i and s.graph not in registry.FLUX_GRAPHS)
    r = pipeline.plan(I2I(document_id="d", model_id=creative.id, source="visible", refs=many[:1]))
    assert r.params["refs"] == 0 and r.params["max_refs"] == 0 and r.params["refs_dropped"] == 1


def test_the_route_carries_the_deck(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    import numpy as np
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        assert client.post("/project", json={"path": str(tmp_path / "proj"), "name": "AI", "size_cap_gb": 10}, headers=H).status_code == 200
        client.post("/queue/pause", headers=H)
        did = client.post("/documents", json={"w": 64, "h": 48, "name": "ai"}, headers=H).json()["id"]
        sel = np.zeros((48, 64), dtype=np.uint8); sel[10:30, 20:40] = 255
        client.put(f"/documents/{did}/selection", params={"w": 64, "h": 48}, content=sel.tobytes(), headers={**H, "Content-Type": "application/octet-stream"})
        r = client.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "fill", "prompt_text": "her face", "seeds": [1], "refs": [{"asset_id": "ast_hero", "note": "the hero"}], "ref_max_px": 768}, "stage": True}, headers=H)
        assert r.status_code == 200, r.text
        job = r.json()["jobs"][0]
        assert job["recipe"]["refs"] == [{"asset_id": "ast_hero", "blob": None, "note": "the hero", "mention": None}] and job["recipe"]["ref_max_px"] == 768
        pv = client.post("/recipes/preview", json={"recipe": {"kind": "i2i", "document_id": did, "model_id": "klein-base-9b", "refs": [{"asset_id": "ast_hero"}]}}, headers=H)
        assert pv.status_code == 200, pv.text
        assert pv.json()["params"]["refs"] == 1 and pv.json()["params"]["refs_dropped"] == 0
