"""D118 (AE4e): processing layers — a pass over the stack from a layer down: the composition rendered apart with the layers above switched
off (a copy of the project, the fake CLI), the pass over it through the fake engine, the frames frozen under processing/<id>/, the
composition bringing the layer in above its layer on sync, stale when the layers below change, replaced when run again, gone when
dropped; the routes."""
import json
from pathlib import Path

from PIL import Image

from test_compositions_ae1 import FAKE, N, S, _final_assembled


async def test_processing_layer(tmp_path: Path, object_info: dict):
    import test_lifecycle
    from loom2.compositions import CompositionStore
    from loom2.effectcraft import EffectCraft
    from loom2.finals import FinalStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.recipes import parse_recipe
    from loom2.stages import StageStore
    from loom2.engine.pipeline import plan
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_assembled(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        ec, cs = EffectCraft(rig.app), CompositionStore(rig.ws)
        c = cs.make(f, ec)
        fig = next(cl for cl in c.layers if cl.id == "fig")
        # the copy for the render: the layers above the point switched off, the point and below kept, a signature of them
        copy = cs.folder(f.id) / "comp.below.test.ecproj"
        below, sig = cs.below_copy(f, fig.layer, copy)
        pj = json.loads(copy.read_text(encoding="utf-8"))
        layers = cs._comp_layers(pj)
        pos = next(i for i, l in enumerate(layers) if int(l["id"]) == fig.layer)
        orig = {int(l["id"]): dict(l["switches"]) for l in cs._comp_layers(json.loads(cs.ecproj(f.id).read_text(encoding="utf-8")))}
        assert [int(l["id"]) for l in layers[pos:]] == below and all(l["switches"]["video"] is False for l in layers[:pos])
        assert all(l["switches"] == orig[int(l["id"])] for l in layers[pos:])                   # the layers below as they were (a matte layer stays hidden)
        assert len(sig) == 24 and cs.below_signatures(f, [("x", below)])["x"] == sig
        copy.unlink()
        ec.stop()
        spec = next(s for s in registry.video_specs() if s.graph == "wan22")
        from loom2.roster import ROSTER_BY_ID
        for rid in spec.weights():
            e = ROSTER_BY_ID[rid]
            p = tmp_path / "models" / e.folder / e.name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * 16)
        rig.queue.load()
        await rig.queue.start()
        data = {"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "cleanup", "strength": 0.1, "model_id": spec.id, "scope": "below"}
        assert plan(parse_recipe(data), "full").params["preset"] == "cleanup"
        job = rig.queue.submit(data, origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "cleanup", "scope": "below"}))[0]
        j = await rig.wait(job.id, timeout=120)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        assert j.result["processing_id"] == "proc_fig" and j.result["compiled"]["scope"] == "below" and j.result["compiled"]["processing"]["below"] == below
        assert any("rendered" in line for line in j.log_tail)
        store = FinalStore(rig.ws)
        f2 = store.get(f.id)
        rec = next(p for p in f2.processing if p.id == "proc_fig")
        assert rec.above == "fig" and rec.preset == "cleanup" and rec.job_id == j.id and rec.below == below and rec.signature == sig and rec.frames == N
        d = store.processing_dir(f.id, "proc_fig")
        assert len(list((d / "frames").glob("*.png"))) == N and Image.open(d / "frames" / "0000.png").size == (S, S) and not (d / "in").exists()
        # the composition brings it in on sync: a footage layer above Mara, named for the pass; not stale
        ec = EffectCraft(rig.app)
        c = cs.sync_sources(f2, ec)
        assert "proc_fig" in c.processing and c.processing_jobs["proc_fig"] == j.id and c.stale is False and c.processing_stale == {"proc_fig": False}
        pl = next(cl for cl in c.layers if cl.id == "proc_fig")
        assert pl.kind == "processing" and pl.name == "Processed · Clean up (Mara down)" and pl.layer == c.processing["proc_fig"]
        names = {l["id"]: l["name"] for l in cs.layers(f2, ec)}
        assert names[pl.layer] == "Processed · Clean up (Mara down)"
        pj = json.loads(cs.ecproj(f.id).read_text(encoding="utf-8"))
        paths = [str(it.get("path") or (it.get("kind") or {}).get("path") or "").replace("\\", "/") for it in pj["items"].values()]
        assert any("processing/proc_fig/frames/0000.png" in p for p in paths)
        assert cs.sync_sources(f2, ec).revision == c.revision                            # nothing moved: no save
        # a change below (the plate moved) makes it stale; run again replaces the footage and clears it
        plate = next(cl for cl in c.layers if cl.id == "plate")
        cs.command(f2, ec, "layer.timing", {"layers": [plate.layer], "delta": 0.0625})
        c = cs.get(f2)
        assert c.processing_stale == {"proc_fig": True}
        ec.stop()
        job = rig.queue.submit({**data, "strength": 0.2}, origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "cleanup", "scope": "below"}))[0]
        j2 = await rig.wait(job.id, timeout=120)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        f3 = store.get(f.id)
        rec = next(p for p in f3.processing if p.id == "proc_fig")
        assert rec.job_id == j2.id and rec.strength == 0.2 and rec.signature != sig and len(f3.processing) == 1
        ec = EffectCraft(rig.app)
        c = cs.sync_sources(f3, ec)
        assert c.processing["proc_fig"] == pl.layer and c.processing_jobs["proc_fig"] == j2.id and c.processing_stale == {"proc_fig": False}
        assert sum(1 for l in cs.layers(f3, ec) if l["name"].startswith("Processed")) == 1
        # dropped on the final: the layer goes on sync
        f4 = store.remove_processing(f.id, "proc_fig")
        assert f4.processing == [] and not d.exists()
        c = cs.sync_sources(f4, ec)
        assert c.processing == {} and not any(cl.kind == "processing" for cl in c.layers) and not any(l["name"].startswith("Processed") for l in cs.layers(f4, ec))
        ec.stop()
    finally:
        await rig.close()


def test_processing_routes(tmp_path: Path):
    """The route: a pass over the stack below needs the composition; the face pass refuses the scope; a processing layer dropped."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import FinalStore, ProcessingLayer
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
        r = cl.post(f"/finals/{f.id}/layers/box/pass", json={"preset": "cleanup", "scope": "below"}, headers=H)
        assert r.status_code == 422 and "composition" in r.json()["detail"]                 # no composition yet
        assert cl.post(f"/finals/{f.id}/composition", headers=H).status_code == 200
        assert cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "face", "scope": "below"}, headers=H).status_code == 422
        r = cl.post(f"/finals/{f.id}/layers/box/pass", json={"preset": "cleanup", "strength": 0.3, "scope": "below"}, headers=H)   # a prop: fine as a point (Clean up: offered under open too)
        assert r.status_code == 200, r.text
        job = cl.get(f"/jobs/{r.json()['job_id']}", headers=H).json()
        assert job["recipe"]["scope"] == "below" and job["recipe"]["layer_id"] == "box" and job["recipe"]["strength"] == 0.3 and job["origin"]["payload"]["scope"] == "below"
        assert cl.delete(f"/finals/{f.id}/processing/proc_nope", headers=H).status_code == 404
        fs = FinalStore(svc.ws)
        fs.set_processing(f.id, ProcessingLayer(id="proc_box", above="box", preset="creative", strength=0.3, model_id="m", job_id="job_x", frames=N, made_at="now", signature="s", below=[]))
        r = cl.delete(f"/finals/{f.id}/processing/proc_box", headers=H)
        assert r.status_code == 200 and r.json()["final"]["processing"] == [] and r.json()["composition"]["processing"] == {}
