"""CA4 / CA5 (02 §3, proto01_animate 31 §4): a character layer's batches — the plan with each batch's frames, state and cost (its time when
done; else the mean of this final's measured batches by frames, else the queue's estimate) and the shot's total owed; a re-take from a
batch on (the batches before it kept, the new seed's batch continuing the kept one's clip, the rest chained, the layer stitched and matted
again); a run staged in the queue (an overnight start)."""
from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_finals_d111 import _figure_ref, _final_on_disk  # noqa: E402


async def test_retake_from_a_batch_and_a_staged_run(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from loom2.finals import FINAL_LAYER_SURFACE, FinalStore, character_recipe, plan_batches
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.routes.finals import RunBody, _retake_from, final_plan
    from loom2.stages import StageStore, encode_guide
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Room")
        png = rig.ws.temp_dir / "p.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 128), (128, 128, 128)).save(png)
        n = 100
        data = {"name": "Shot", "stage_id": st.id, "camera_id": st.cameras[0].id, "stage_revision": 0, "range": {"start": 0, "end": 149}, "rate": 16,
                "size": {"w": 128, "h": 128}, "frames": n,
                "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"}, {"id": "fig", "kind": "figure", "name": "Mara", "object_id": "fig_1", "method": "move"},
                           {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
        store = FinalStore(rig.ws)
        f = store.create(data, {"plate": {"depth": [png] * n, "clay": [png] * n}, "fig": {"pose": [png] * n, "depth": [png] * n}, "shadows": {"clay": [png] * n}}, {})
        ref = rig.catalogue.ingest_file(_figure_ref(tmp_path / "ref.png"), kind="image", move=False, suite="stage")
        mp4 = rig.ws.temp_dir / "pose.mp4"
        encode_guide([png] * n, mp4, 16)
        guide = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", frames=n, fps=16.0, w=128, h=128)
        f = store.update_layer(f.id, "fig", reference_asset_id=ref.id, guide_asset_id=guide.id, seed=3)
        spec = next(s for s in registry.animate_specs())
        plan = plan_batches(n)
        layer = next(x for x in f.layers if x.id == "fig")
        rig.queue.load()
        await rig.queue.start()
        svc = types.SimpleNamespace(queue=rig.queue, hub=rig.queue.hub, app=rig.app, require_project=lambda: (rig.ws, rig.catalogue, None))
        # CA4: the plan before anything ran — two batches owed, their frames, a cost each from the queue's estimate
        p = await final_plan(svc, f.id)
        b = p["layers"][0]["batches"]
        assert [x["state"] for x in b] == ["owed", "owed"] and b[0]["covers"] == [0, 76] and b[1]["covers"] == [77, 99]
        assert all(x["seconds"] for x in b) and p["seconds_owed"] == round(sum(x["seconds"] for x in b), 1) and p["source"] == "the queue's estimate"
        job = rig.queue.submit(character_recipe(f, layer, spec.id, "Mara, moving", plan[0], None),
                               origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id, payload={"layer": "fig", "batch": 0, "batches": 2, "prompt": "Mara, moving"}))[0]
        store.update_layer(f.id, "fig", status="queued", batches=[{"k": 0, "job_id": job.id, "clip_id": None}], job_ids=[job.id])
        j0 = await rig.wait(job.id, timeout=60)
        j1 = await rig.wait(next(x for x in store.get(f.id).layers if x.id == "fig").batches[1]["job_id"], timeout=60)
        jm = await rig.wait(next(x for x in store.get(f.id).layers if x.id == "fig").job_ids[-1], timeout=60)
        assert (j0.status, j1.status, jm.status) == ("done", "done", "done")
        # CA4: done now — their times measured; nothing owed
        p = await final_plan(svc, f.id)
        assert [x["state"] for x in p["layers"][0]["batches"]] == ["done", "done"] and p["seconds_owed"] == 0.0
        # CA5: batch 2 again with a new seed — batch 1 kept, the new batch continuing its clip; stitched and matted again
        f = store.get(f.id)
        layer = next(x for x in f.layers if x.id == "fig")
        r = await _retake_from(svc, store, f, layer, RunBody(from_batch=1), spec.id, "Mara, moving", ref.id)
        jr = await rig.wait(r["job_id"], timeout=60)
        assert jr.status == "done", (jr.error, jr.log_tail[-5:])
        assert jr.recipe["seeds"] == [4] and jr.recipe["chain"] == {"clip_id": j0.result["clip_id"], "carry": 5, "offset": 77}
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.batches[0]["clip_id"] == j0.result["clip_id"] and layer.batches[1]["clip_id"] == jr.result["clip_id"] and layer.seed == 4
        jm2 = await rig.wait(layer.job_ids[-1], timeout=60)
        assert jm2.status == "done" and jm2.recipe["kind"] == "matte_sequence"
        assert next(x for x in store.get(f.id).layers if x.id == "fig").frames_done == n
        # refused: a batch the plan has not, or one whose earlier batches are not made
        import pytest
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            await _retake_from(svc, store, store.get(f.id), layer, RunBody(from_batch=2), spec.id, "x", ref.id)
        # CA4: a run staged — the queue holds it until Run staged
        f = store.get(f.id)
        layer = next(x for x in f.layers if x.id == "fig")
        r = await _retake_from(svc, store, f, layer, RunBody(from_batch=1, stage=True), spec.id, "Mara, moving", ref.id)
        assert rig.queue.get(r["job_id"]).status == "staged"
        p = await final_plan(svc, f.id)
        assert [x["state"] for x in p["layers"][0]["batches"]] == ["done", "staged"] and p["seconds_owed"] > 0
        assert p["source"].startswith("measured")                                       # this final's batches measured now
    finally:
        await rig.close()


def test_the_plan_route(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.workspace import Workspace
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        st = cl.post("/stages", json={"name": "Room"}).json()
        f = _final_on_disk(Workspace(tmp_path / "p"), st["id"], st["cameras"][0]["id"])
        r = cl.get(f"/finals/{f.id}/plan")
        assert r.status_code == 200 and r.json() == {"final_id": f.id, "layers": [], "seconds_owed": 0.0, "source": "the queue's estimate"}   # no character layer
        assert cl.get("/finals/fin_nope/plan").status_code == 404
        assert cl.post(f"/finals/{f.id}/layers/plate/run", json={"from_batch": 1}).status_code == 422
