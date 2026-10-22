"""D118 (AE4a): a pass on a layer — the job through the fake engine, its frames a take the layer shows as its source, the composition's
footage swapped (file.replaceFootage in the fake), the assembly reading the active source, the source set back, a take removed; the routes."""
import json
from pathlib import Path

from PIL import Image

from test_compositions_ae1 import FAKE, N, S, _final_assembled


async def test_layer_pass_job(tmp_path: Path, object_info: dict):
    import test_lifecycle
    from loom2 import final_assembly
    from loom2.compositions import CompositionStore
    from loom2.effectcraft import EffectCraft
    from loom2.finals import FinalStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_assembled(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        ec, cs = EffectCraft(rig.app), CompositionStore(rig.ws)
        cs.make(f, ec)
        rig.queue.load()
        await rig.queue.start()
        from loom2.roster import ROSTER_BY_ID
        spec = next(s for s in registry.video_specs() if s.graph == "wan22")
        ltx = next((s for s in registry.video_specs() if s.graph == "ltx23" and s.recipes.guide_lora), None)
        for rid in dict.fromkeys([*spec.weights(), *(ltx.weights() if ltx else []), *([ltx.recipes.guide_lora] if ltx else [])]):   # the passes' weights "on disk"
            e = ROSTER_BY_ID[rid]
            p = tmp_path / "models" / e.folder / e.name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * 16)
        job = rig.queue.submit({"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "cleanup", "strength": 0.1, "model_id": spec.id},
                               origin=JobOrigin(suite="stage", surface="final-layer", ref=f.id, payload={"layer": "fig", "pass": "cleanup"}))[0]
        j = await rig.wait(job.id, timeout=120)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        assert j.result["compiled"]["preset"] == "cleanup" and j.result["compiled"]["strength"] == 0.1 and j.result["compiled"]["pad"] == [0, 0]
        store = FinalStore(rig.ws)
        f2 = store.get(f.id)
        lay = next(x for x in f2.layers if x.id == "fig")
        assert len(lay.takes) == 1 and lay.source == lay.takes[0]["id"] == j.result["take_id"] and lay.takes[0]["preset"] == "cleanup"
        take = lay.source
        d = store.pass_dir(f.id, "fig", f"passes/{take}")
        assert len(list(d.glob("*.png"))) == N and Image.open(d / "0000.png").size == (S, S)
        assert store.frames_dir(f.id, "fig") == d
        # the composition follows on sync: the layer's footage item points at the take; not stale
        c = cs.sync_sources(f2, ec)
        assert c.sources["fig"] == take and c.stale is False and c.revision == 1
        pj = json.loads(cs.ecproj(f.id).read_text(encoding="utf-8"))
        paths = [str(it.get("path") or (it.get("kind") or {}).get("path") or "").replace("\\", "/") for it in pj["items"].values()]
        assert any(f"passes/{take}/0000.png" in p for p in paths)
        assert cs.sync_sources(f2, ec).revision == 1                              # nothing moved: no save
        # the assembly reads the active source
        tmp = tmp_path / "asm"
        stats = final_assembly.assemble_frames(store, store.get(f.id), tmp, None)
        assert stats["frames"] == N
        # back to the original, then the take removed (its frames too)
        f3 = store.set_source(f.id, "fig", None)
        c = cs.set_source(f3, ec, "fig", None)
        assert c.sources["fig"] is None and store.frames_dir(f.id, "fig").name == "frames"
        f4 = store.remove_take(f.id, "fig", take)
        assert next(x for x in f4.layers if x.id == "fig").takes == [] and not d.exists()
        ec.stop()
        # the creative pass: LTX locked to the depth, the picture padded to 64 and cropped back
        ltx = next((s for s in registry.video_specs() if s.graph == "ltx23" and s.recipes.guide_lora), None)
        if ltx is not None:
            job = rig.queue.submit({"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "creative", "strength": 0.35, "model_id": ltx.id})[0]
            j = await rig.wait(job.id, timeout=120)
            assert j.status == "done", (j.error, j.log_tail[-5:])
            assert j.result["compiled"]["pad"] == [(-S) % 64, (-S) % 64]
            lay = next(x for x in store.get(f.id).layers if x.id == "fig")
            assert lay.takes[-1]["preset"] == "creative" and lay.source == lay.takes[-1]["id"]
            assert Image.open(store.pass_dir(f.id, "fig", f"passes/{lay.source}") / "0000.png").size == (S, S)
    finally:
        await rig.close()


def test_layer_pass_routes(tmp_path: Path):
    """The routes: a pass queued (the model picked for the preset), a prop refused, the source set and the take listed; without the engine the
    job stays queued."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "effectcraft": {"cli": str(FAKE)}})
    app = create_app(state)
    svc = app.state.services
    H = {"X-Loom-Token": svc.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        f, _ = _final_assembled(svc.ws, st["id"], st["cameras"][0]["id"], tmp_path / "src")
        r = cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "cleanup", "strength": 0.1}, headers=H)
        assert r.status_code == 200, r.text
        job = cl.get(f"/jobs/{r.json()['job_id']}", headers=H).json()
        assert job["kind"] == "layer_pass" and job["recipe"]["preset"] == "cleanup" and job["recipe"]["model_id"] and job["origin"]["payload"]["layer"] == "fig"
        assert cl.post(f"/finals/{f.id}/layers/box/pass", json={"preset": "cleanup"}, headers=H).status_code == 422          # a prop: later
        assert cl.post(f"/finals/{f.id}/layers/plate/pass", json={"preset": "cleanup"}, headers=H).status_code == 200
        assert cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "cleanup", "strength": 5}, headers=H).status_code == 422
        assert cl.post(f"/finals/{f.id}/layers/fig/source", json={"take": "take_nope"}, headers=H).status_code == 404
        r = cl.post(f"/finals/{f.id}/layers/fig/source", json={"take": None}, headers=H)
        assert r.status_code == 200 and r.json()["final"]["layers"][2]["source"] is None and r.json()["composition"] is None
        assert cl.delete(f"/finals/{f.id}/layers/fig/takes/take_nope", headers=H).status_code == 404
        assert cl.post(f"/finals/{f.id}/composition/sync", headers=H).status_code == 404     # no composition yet
