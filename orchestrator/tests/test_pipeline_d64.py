"""D64 (ArtCraft P2): plan → finalize → submit — the pure plan per kind, finishers driven by output files (no engine), the preview's
contract problems equal a submission's, the queue writer keeps write order off the event loop, and /recipes/preview covers every kind."""
from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState
from loom2.documents import Document, OpenDocument
from loom2.edit_ai import RegionPlan
from loom2.engine import finishers
from loom2.engine.graphs import Compiled, compile_recipe, effective_params, i2v_params, recipe_weights
from loom2.engine.pipeline import Submission, placeholder_inputs, plan, preview_problems
from loom2.recipes import I2V, Inpaint, RefImage, Segment, T2I, Upscale
from test_graph_parity_d64 import _pin_review


# ---- plan() per kind ----------------------------------------------------------------------------------------------------------------
def test_plan_t2i_is_the_effective_params_and_weights():
    r = T2I(prompt_mode="text", prompt_text="a cat", seeds=[1, 2, 3])
    p = plan(r)
    assert p.kind == "t2i" and p.engine and p.needs == [] and p.count == 3
    assert p.params == effective_params(r) and p.weights == recipe_weights(r)
    assert p.estimate["seconds"] > 0 and p.vram_gb > 0
    assert plan(T2I(model_id="klein-base-9b", prompt_mode="text", prompt_text="x", refs=[RefImage(asset_id="a")])).needs == ["refs"]


def test_plan_document_kinds_need_the_document_and_carry_a_baseline():
    fill = plan(Inpaint(document_id="d", mode="fill", prompt_text="x", seeds=[1, 2]))
    assert fill.needs == ["document"] and fill.engine and fill.count == 2 and fill.estimate["seconds"] == 28.0
    assert fill.params["mode"] == "fill" and "prompt_text" not in fill.params
    hero = plan(Inpaint(document_id="d", mode="fill_hero", prompt_text="x"))
    assert hero.estimate["seconds"] == 270.0 and "flux2-dev-fp8mixed" in hero.weights
    sam = plan(Segment(document_id="d", model_id="sam3", mode="text", text="a crate"))
    assert sam.estimate["seconds"] == 3.5 and sam.needs == ["document"]
    up = plan(Upscale(document_id="d", model_id="realesrgan-x2", source="visible", refine=True, refine_model_id="klein-base-9b"))
    assert "tile" in up.estimate["source"]


def test_plan_quick_remove_runs_without_an_engine():
    p = plan(Inpaint(document_id="d", mode="quick_remove"))
    assert not p.engine and p.vram_gb == 0.0 and p.weights == [] and p.model_id is None and p.estimate["source"].endswith("CPU)")


def test_plan_i2v_needs_frames():
    r = I2V(start_asset="a", end_asset="b", preset="motion")
    p = plan(r)
    assert p.needs == ["frames"] and p.params == i2v_params(r) and p.weights == recipe_weights(r)


# ---- the preview's contract problems are the submission's ---------------------------------------------------------------------------
def test_preview_problems_equal_the_submissions(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    broken = copy.deepcopy(object_info)
    r = Inpaint(document_id="d", mode="fill", prompt_text="x", seeds=[1])
    real = placeholder_inputs(r, object_info)                     # the names a real upload would have produced (they are in the enum)
    first = compile_recipe(r, roster, object_info, 1, "loom2/x", inputs=real)
    victim = next(n["class_type"] for n in first.graph.values() if n["class_type"] not in ("LoadImage", "SaveImage"))
    del broken[victim]
    submitted = compile_recipe(r, roster, broken, 7, "loom2/job", inputs=real).problems
    previewed = preview_problems(r, roster, broken)
    assert submitted and previewed == submitted
    assert preview_problems(r, roster, object_info) == []
    assert preview_problems(r, roster, None) is None               # before the engine answered once there is nothing to check against


# ---- finishers driven by output files, no engine ------------------------------------------------------------------------------------
def _ctx(tmp_path: Path, od: OpenDocument) -> SimpleNamespace:
    events: list = []
    out = tmp_path / "state" / "engine_out"
    out.mkdir(parents=True)
    q = SimpleNamespace(app=SimpleNamespace(state_dir=tmp_path / "state"), documents=SimpleNamespace(get=lambda _id: od),
                        hub=SimpleNamespace(broadcast=lambda *a: events.append(a)), progress=lambda job, text: None, wall_s=lambda: 1.0)
    q.events = events
    return q


def test_selection_finisher_joins_the_engine_mask(tmp_path: Path):
    od = OpenDocument(Document(name="s", w=64, h=48), tmp_path / "s.ora")
    q = _ctx(tmp_path, od)
    m = np.zeros((48, 64), np.uint8)
    m[10:20, 30:50] = 255
    Image.fromarray(np.dstack([m, m, m])).save(q.app.state_dir / "engine_out" / "mask.png")
    job = SimpleNamespace(id="j1", batch_id=None, result={}, log_tail=[])
    rec = Segment(document_id="d", mode="subject", feather=0)
    asyncio.run(finishers.SelectionFinisher().finish(job, rec, [{"filename": "mask.png", "subfolder": ""}], Submission(Compiled({}, "")), q))
    assert od.selection is not None and od.selection[15, 40] == 255 and od.selection[5, 5] == 0
    assert job.result["selection"]["coverage"] > 0 and any(e[0] == "document.changed" for e in q.events)


def test_document_finisher_pastes_a_candidate_layer(tmp_path: Path):
    od = OpenDocument(Document(name="p", w=64, h=48), tmp_path / "p.ora")
    q = _ctx(tmp_path, od)
    Image.fromarray(np.full((16, 20, 3), 200, np.uint8)).save(q.app.state_dir / "engine_out" / "out.png")
    plan_ = RegionPlan(x=10, y=8, w=20, h=16, ew=20, eh=16, scale=1.0)
    alpha = np.zeros((48, 64), np.uint8)
    alpha[8:24, 10:30] = 255
    sub = Submission(Compiled({}, ""), {"plan": plan_, "alpha_mask": alpha, "context": np.zeros((16, 20, 3), np.uint8)})
    job = SimpleNamespace(id="j2", batch_id="b2", seed=5, result={"region": plan_.to_dict()}, log_tail=[])
    asyncio.run(finishers.DocumentFinisher().finish(job, Inpaint(document_id="d", mode="fill", feather=0, seeds=[1]), [{"filename": "out.png", "subfolder": ""}], sub, q))
    lid = job.result["layers"][0]
    node = od.doc.find(lid)
    assert node is not None and (node.x, node.y) == (10, 8) and node.mask is not None
    assert job.result["group"] == "grp_b2" and od.pixels[lid].shape == (16, 20, 4)


def test_finisher_for_each_kind():
    assert isinstance(finishers.finisher_for(T2I(prompt_text="x")), finishers.AssetFinisher)
    assert isinstance(finishers.finisher_for(Segment(document_id="d")), finishers.SelectionFinisher)
    assert isinstance(finishers.finisher_for(Inpaint(document_id="d")), finishers.DocumentFinisher)
    assert isinstance(finishers.finisher_for(I2V(start_asset="a")), finishers.ClipFinisher)
    assert not finishers.AssetFinisher.frees_cache and finishers.DocumentFinisher.frees_cache


# ---- the queue writer: off the loop, in call order ----------------------------------------------------------------------------------
def _bare_queue(tmp_path: Path):
    from loom2.queue import JobQueue
    return JobQueue(SimpleNamespace(queue_path=tmp_path / "queue.json"), SimpleNamespace(settings=None), SimpleNamespace(), None, None, SimpleNamespace())


def test_queue_writes_land_in_call_order(tmp_path: Path):
    q = _bare_queue(tmp_path)

    async def burst() -> dict:
        for i in range(40):                      # a burst of changes: written off the loop, the newest snapshot last
            q.paused = i % 2 == 1                # i = 39 → paused
            q.persist()
        assert q._writer is not None             # deferred while the loop runs
        await q.flush()
        return json.loads(q.ws.queue_path.read_text(encoding="utf-8"))
    assert asyncio.run(burst())["paused"] is True
    q.paused = False
    q.persist()                                  # no running loop: synchronous
    assert json.loads(q.ws.queue_path.read_text(encoding="utf-8"))["paused"] is False


def test_queue_flush_reports_a_failed_write_once(tmp_path: Path, monkeypatch):
    import loom2.queue as queue_mod
    q = _bare_queue(tmp_path)

    def full(*a, **kw):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(queue_mod, "atomic_write_json", full)

    async def run() -> list[str]:
        out = []
        q.persist()
        try:
            await q.flush()
        except OSError as e:
            out.append(str(e))
        await q.flush()                          # reported once
        return out
    assert len(asyncio.run(run())) == 1


# ---- /recipes/preview for every kind ------------------------------------------------------------------------------------------------
def test_preview_covers_edit_recipes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app, headers=H) as c:
        r = c.post("/recipes/preview", json={"recipe": {"kind": "inpaint", "document_id": "d", "mode": "fill", "prompt_text": "x", "seeds": [1, 2]}})
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["kind"] == "inpaint" and p["needs"] == ["document"] and p["count"] == 2 and p["engine"] is True
        assert p["estimate"]["seconds"] == 28.0 and p["problems"] is None and p["missing"]          # no engine yet; weights not fetched here
        q = c.post("/recipes/preview", json={"recipe": {"kind": "inpaint", "document_id": "d", "mode": "quick_remove"}}).json()
        assert q["engine"] is False and q["weights"] == [] and q["missing"] == []
        s = c.post("/recipes/preview", json={"recipe": {"kind": "segment", "document_id": "d", "model_id": "sam3", "mode": "text", "text": "a crate"}}).json()
        assert s["estimate"]["seconds"] == 3.5
        t = c.post("/recipes/preview", json={"recipe": {"kind": "t2i", "prompt_text": "a cat"}}).json()
        assert "serialized_prompt" in t and "weights" in t and "problems" in t
