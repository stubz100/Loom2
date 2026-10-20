"""D111 (PS5a): the final shot's record — its frames at the shot's rate (F16 resamples, F24 takes each), its layers (one plate, one shadows,
figures and props naming their Stage objects), each layer's passes copied from the uploaded blobs (one blob may stand for many frames),
the routes (make, list, read, a frame, delete) and their refusals."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.finals import frames_at  # noqa: E402


def test_frames_at_the_rate():
    assert frames_at(0, 24, 24) == list(range(25))
    f16 = frames_at(0, 240, 16)
    assert len(f16) == 161 and f16[1] == 1.5 and f16[-1] == 240.0          # D102: 10 s at F16 is 161 frames, every 1.5th Stage frame
    assert frames_at(10, 9, 16) == []


def _png(colour: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (64, 48), colour).save(buf, "PNG")
    return buf.getvalue()


def test_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        shas = []
        for c in (10, 20, 30):
            b = _png(c)
            sha = hashlib.sha256(b).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=b, headers=H).status_code == 200
            shas.append(sha)
        seq = shas                                                               # three frames
        still = [shas[0]] * 3                                                   # a still camera: one blob for every frame
        layers = [{"id": "plate", "kind": "plate", "name": "Room", "passes": {"depth": still, "clay": still}},
                  {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": seq}},
                  {"id": "fig_m", "kind": "figure", "name": "Mara", "object_id": "fig_1", "profile_id": "prf_m", "passes": {"pose": seq, "depth": seq},
                   "keypoints": [[[100, 50, 1]], [[101, 50, 1]], [[102, 50, 1]]]},
                  {"id": "chest", "kind": "prop", "name": "Chest", "object_id": "chest", "passes": {"beauty": seq, "depth": seq}}]
        body = {"name": "Shot 1", "stage_id": st["id"], "camera_id": st["cameras"][0]["id"], "stage_revision": st["revision"], "range": {"start": 0, "end": 3},
                "rate": 16, "size": {"w": 832, "h": 480}, "frames": 3, "layers": layers}
        r = cl.post("/finals", json=body, headers=H)
        assert r.status_code == 200, r.text
        f = r.json()
        assert {x["id"]: x["method"] for x in f["layers"]} == {"plate": "projected", "shadows": "stage", "fig_m": "move", "chest": "rendered"}
        assert all(x["status"] == "passes" for x in f["layers"]) and [x["keypoints"] for x in f["layers"]] == [False, False, True, False]
        assert f["layers"][2]["passes"] == {"pose": 3, "depth": 3}
        d = tmp_path / "proj" / "finals" / f["id"]
        assert sorted(p.name for p in (d / "plate" / "depth").iterdir()) == ["0000.png", "0001.png", "0002.png"]
        assert (d / "fig_m" / "keypoints.json").is_file()
        fr = cl.get(f"/finals/{f['id']}/layers/chest/beauty/2", headers=H)
        assert fr.status_code == 200 and fr.content == _png(30)
        assert cl.get(f"/finals/{f['id']}/layers/chest/beauty/9", headers=H).status_code == 404
        assert [x["id"] for x in cl.get(f"/finals?stage_id={st['id']}", headers=H).json()["items"]] == [f["id"]]
        assert cl.get("/finals?stage_id=stg_other", headers=H).json()["items"] == []
        # refusals: a pass short of frames, no shadows layer, a figure without its object, a blob never uploaded, an unknown stage
        bad = {**body, "layers": [layers[0], layers[1], {**layers[2], "passes": {"pose": seq[:2], "depth": seq}}]}
        assert cl.post("/finals", json=bad, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], layers[2]]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], layers[1], {**layers[3], "object_id": None}]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], {**layers[1], "passes": {"clay": ["0" * 64] * 3}}]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "stage_id": "stg_nope"}, headers=H).status_code == 404
        assert len(list((tmp_path / "proj" / "finals").glob("fin_*"))) == 1                   # a refused final leaves nothing behind
        assert cl.delete(f"/finals/{f['id']}", headers=H).status_code == 200 and not d.exists()
        assert cl.get(f"/finals/{f['id']}", headers=H).status_code == 404


def _final_on_disk(ws, stage_id: str, camera_id: str, frames: int = 3):
    """A final with its plate and shadows passes (mid-grey PNGs), as PS5a leaves it."""
    from loom2.finals import FinalStore
    from PIL import Image
    src = ws.temp_dir / "blobs"
    src.mkdir(parents=True, exist_ok=True)
    png = src / "grey.png"
    Image.new("RGB", (64, 48), (128, 128, 128)).save(png)
    still = [png] * frames
    data = {"name": "Shot", "stage_id": stage_id, "camera_id": camera_id, "stage_revision": 0, "range": {"start": 0, "end": 3}, "rate": 16,
            "size": {"w": 128, "h": 128}, "frames": frames,
            "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"}, {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
    return FinalStore(ws).create(data, {"plate": {"depth": still, "clay": still}, "shadows": {"clay": still}}, {})


def test_plate_route_queues_the_stage_shot_and_frames_finish_the_layer(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import PLATE_LEAD
    from loom2.workspace import Workspace
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        f = _final_on_disk(Workspace(tmp_path / "proj"), st["id"], st["cameras"][0]["id"])
        r = cl.post(f"/finals/{f.id}/plate", json={"prompt_text": "a whitewashed room, daylight from a window"}, headers=H)
        assert r.status_code == 200, r.text
        job = next(j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] == r.json()["job_id"])
        assert job["recipe"]["kind"] == "stage_shot" and job["recipe"]["method"] == "clay" and job["recipe"]["passes"] == {"clay": r.json()["pass_asset_id"]}
        assert job["recipe"]["prompt_text"].startswith(PLATE_LEAD) and job["recipe"]["prompt_text"].endswith("daylight from a window")
        assert job["recipe"]["empty"] is True                                    # the empty set's lead: no mannequins, no people
        assert (job["origin"]["surface"], job["origin"]["ref"]) == ("final_plate", f.id)
        fin = cl.get(f"/finals/{f.id}", headers=H).json()
        plate = next(x for x in fin["layers"] if x["id"] == "plate")
        assert plate["status"] == "queued" and plate["job_ids"] == [job["id"]]
        # the projected frames (the client's) finish the layer
        b = _png(90)
        sha = hashlib.sha256(b).hexdigest()
        cl.put(f"/blobs/{sha}", content=b, headers=H)
        assert cl.put(f"/finals/{f.id}/layers/plate/frames", json={"frames": [sha] * 2}, headers=H).status_code == 422   # one per frame
        done = cl.put(f"/finals/{f.id}/layers/plate/frames", json={"frames": [sha] * 3}, headers=H)
        assert done.status_code == 200
        plate = next(x for x in done.json()["layers"] if x["id"] == "plate")
        assert plate["status"] == "done" and plate["frames_done"] == 3
        assert cl.get(f"/finals/{f.id}/layers/plate/frames/2", headers=H).content == b
        assert cl.put(f"/finals/{f.id}/layers/nope/frames", json={"frames": [sha] * 3}, headers=H).status_code == 404


async def test_the_plate_still_lands_on_its_final_not_on_a_story_shot(tmp_path: Path, object_info: dict, monkeypatch):
    """The Stage shot of the plate through the fake engine: its image is the plate layer's still (status running: Stage projects it next);
    no Story shot takes it."""
    import test_lifecycle
    from loom2.finals import FINAL_PLATE_SURFACE, FinalStore
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Room")
        f = _final_on_disk(rig.ws, st.id, st.cameras[0].id)
        clay = rig.catalogue.ingest_file(FinalStore(rig.ws).pass_dir(f.id, "plate", "clay") / "0000.png", kind="image", move=False, suite="stage")
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "stage_shot", "stage_id": st.id, "camera_id": st.cameras[0].id, "passes": {"clay": clay.id}, "method": "clay", "prompt_text": "an empty room"},
                               origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=f.id))[0]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        plate = next(x for x in FinalStore(rig.ws).get(f.id).layers if x.id == "plate")
        assert plate.still_asset_id == j.result["asset_ids"][0] and plate.status == "running"
    finally:
        await rig.close()


def test_an_empty_set_has_its_own_lead():
    """PS5b: the clay lead names mannequins and people (the rig's first plate grew two men); an empty set's speaks of the place alone."""
    from loom2.engine.graphs import STAGE_CLAY_LEAD, STAGE_SET_LEAD, stage_prompt
    from loom2.recipes import StageShot
    base = {"stage_id": "s", "camera_id": "c", "passes": {"clay": "a"}, "prompt_text": "a whitewashed room"}
    assert stage_prompt(StageShot(**base)).startswith(STAGE_CLAY_LEAD)
    empty = stage_prompt(StageShot(**base, empty=True))
    assert empty.startswith(STAGE_SET_LEAD) and "mannequin" not in empty and empty.endswith("a whitewashed room")


# ---- PS5c: character layers ------------------------------------------------------------------------------------------------------
def test_batches_and_stitching():
    from loom2.finals import plan_batches, stitch
    assert plan_batches(33) == [{"frames": 33, "offset": 0}] and plan_batches(34) == [{"frames": 37, "offset": 0}] and plan_batches(5) == [{"frames": 9, "offset": 0}]
    assert plan_batches(161) == [{"frames": 77, "offset": 0}, {"frames": 77, "offset": 77}, {"frames": 77, "offset": 149}]      # E23a's 10 s at F16
    assert len(plan_batches(149)) == 2 and len(plan_batches(150)) == 3
    a = [Path(f"a{i}") for i in range(77)]
    b = [Path(f"b{i}") for i in range(77)]
    out = stitch([a, b], 100)
    assert len(out) == 100 and out[76] == Path("a76") and out[77] == Path("b5")                  # the 5 carried frames dropped
    with pytest.raises(ValueError):
        stitch([a], 100)


def _figure_ref(path: Path) -> Path:
    """A reference on a plain grey ground: a dark figure 300 px tall."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (640, 360), (200, 200, 205))
    d = ImageDraw.Draw(im)
    d.rectangle((300, 30, 340, 330), fill=(40, 40, 60))
    im.save(path)
    return path


def _kp(nose=(400.0, 100.0), feet_y=300.0, x=400.0) -> list:
    k = [[0.0, 0.0, 0.0] for _ in range(18)]
    k[0] = [nose[0], nose[1], 1.0]
    for i in (8, 11):
        k[i] = [x, (nose[1] + feet_y) / 2, 1.0]
    for i, dx in ((10, -10), (13, 10)):
        k[i] = [x + dx, feet_y, 1.0]
    return k


def test_the_reference_stands_where_the_figure_starts(tmp_path: Path):
    import numpy as np
    from PIL import Image
    from loom2.finals import place_reference
    ref = _figure_ref(tmp_path / "ref.png")
    out = tmp_path / "placed.png"
    assert place_reference(ref, _kp(), 832, 480, out)
    a = np.asarray(Image.open(out).convert("L"))
    ys, xs = np.nonzero(a < 120)
    assert abs(xs.mean() - 400) < 6                                                  # centred on the hips
    assert abs(ys.max() - (300 + 0.045 * 200)) < 4 and abs((ys.max() - ys.min()) - 200 / 0.86) < 6   # feet on the figure's, its height scaled
    assert a[5, 5] > 190                                                             # the reference's own ground around it
    assert not place_reference(ref, None, 832, 480, tmp_path / "x.png")              # no keypoints: CN4's padded reference instead
    gone = _kp()
    gone[10][2] = 0.0
    assert not place_reference(ref, gone, 832, 480, tmp_path / "y.png")              # an ankle off-screen at the start


def test_a_chained_batch_compiles_with_its_carried_frames(tmp_path: Path, object_info: dict):
    from loom2.engine import graphs
    from loom2.models import registry
    from loom2.recipes import I2V
    from test_graph_parity_d64 import _pin_review
    roster = _pin_review().full_roster(tmp_path)
    spec = next(s for s in registry.animate_specs())
    base = {"model_id": spec.id, "start_asset": "ast_ref", "frames": 77, "fps": 16, "width": 832, "height": 480, "guide": {"asset_id": "ast_g", "kind": "pose", "strength": 1.0}}
    first = graphs.build_i2v(I2V(**base, chain={"offset": 0}), roster, 1, "x", "ref.png", guide_name="pose.mp4")
    node = next(n for n in first.graph.values() if n["class_type"] == "WanAnimateToVideo")
    assert node["inputs"]["video_frame_offset"] == 0 and "continue_motion" not in node["inputs"]
    later = graphs.build_i2v(I2V(**base, chain={"clip_id": "clp_a", "carry": 5, "offset": 77}), roster, 1, "x", "ref.png", guide_name="pose.mp4", carry_names=[f"c{i}.png" for i in range(5)])
    node = next(n for n in later.graph.values() if n["class_type"] == "WanAnimateToVideo")
    assert node["inputs"]["video_frame_offset"] == 77 and node["inputs"]["continue_motion_max_frames"] == 5 and node["inputs"]["continue_motion"][0] == "cb4"
    assert sorted(n["inputs"]["image"] for n in later.graph.values() if n["class_type"] == "LoadImage" and n["inputs"]["image"].startswith("c")) == [f"c{i}.png" for i in range(5)]
    with pytest.raises(graphs.CompileError):
        graphs.build_i2v(I2V(**base, chain={"clip_id": "clp_a", "offset": 77}), roster, 1, "x", "ref.png", guide_name="pose.mp4")     # the frames not uploaded
    with pytest.raises(graphs.CompileError):
        graphs.build_i2v(I2V(model_id=registry.default_model("i2v"), start_asset="a", chain={"offset": 0}), roster, 1, "x", "s.png")    # not a pose-driven model


def test_the_run_route_refuses_what_it_cannot_perform(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.workspace import Workspace
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        f = _final_on_disk(Workspace(tmp_path / "proj"), st["id"], st["cameras"][0]["id"])
        assert cl.post(f"/finals/{f.id}/layers/plate/run", json={}, headers=H).status_code == 422          # the plate is projected
        assert cl.post(f"/finals/{f.id}/layers/nope/run", json={}, headers=H).status_code == 404


async def test_a_character_layer_runs_in_chained_batches_and_is_stitched(tmp_path: Path, object_info: dict, monkeypatch):
    """Two batches on the fake engine (100 frames: 77, then 77 carrying 5): the second continues the first (its carried frames uploaded,
    the guide from 77); the layer's frames are the stitch, 100 frames; its matte follows by itself (PS5d: SAM 3 on the layer's frames, one
    mask each); then the assembly (PS5e) composites the plate, the prop and the character into a clip, and the final names it."""
    import test_lifecycle
    from loom2.finals import FINAL_LAYER_SURFACE, FinalStore, character_recipe, plan_batches
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
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
        bare_d, fig_d, prop_d = (rig.ws.temp_dir / f"{k}.png" for k in ("bare_d", "fig_d", "prop_d"))
        Image.new("L", (128, 128), 100).save(bare_d)
        im = Image.new("L", (128, 128), 100); im.paste(180, (51, 25, 77, 115)); im.save(fig_d)          # the figure, near
        im = Image.new("L", (128, 128), 100); im.paste(140, (10, 70, 40, 110)); im.save(prop_d)         # the prop, further, to her left
        data = {"name": "Shot", "stage_id": st.id, "camera_id": st.cameras[0].id, "stage_revision": 0, "range": {"start": 0, "end": 149}, "rate": 16,
                "size": {"w": 128, "h": 128}, "frames": n,
                "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"}, {"id": "fig", "kind": "figure", "name": "Mara", "object_id": "fig_1", "method": "move"},
                           {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
        store = FinalStore(rig.ws)
        data["layers"].insert(1, {"id": "box", "kind": "prop", "name": "Box", "object_id": "box", "method": "rendered"})
        f = store.create(data, {"plate": {"depth": [bare_d] * n, "clay": [png] * n}, "fig": {"pose": [png] * n, "depth": [fig_d] * n}, "box": {"beauty": [png] * n, "depth": [prop_d] * n},
                                "shadows": {"clay": [png] * n}}, {})
        ref = rig.catalogue.ingest_file(_figure_ref(tmp_path / "ref.png"), kind="image", move=False, suite="stage")
        from loom2.stages import encode_guide
        mp4 = rig.ws.temp_dir / "pose.mp4"
        encode_guide([png] * n, mp4, 16)
        guide = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", frames=n, fps=16.0, w=128, h=128)
        f = store.update_layer(f.id, "fig", reference_asset_id=ref.id, guide_asset_id=guide.id, seed=3)
        spec = next(s for s in registry.animate_specs())
        plan = plan_batches(n)
        assert len(plan) == 2
        layer = next(x for x in f.layers if x.id == "fig")
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit(character_recipe(f, layer, spec.id, "Mara, moving", plan[0], None),
                               origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id, payload={"layer": "fig", "batch": 0, "batches": 2}))[0]
        store.update_layer(f.id, "fig", status="queued", batches=[{"k": 0, "job_id": job.id, "clip_id": None}], job_ids=[job.id])
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert len(layer.batches) == 2 and layer.batches[0]["clip_id"] == j.result["clip_id"]
        j2 = await rig.wait(layer.batches[1]["job_id"], timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        assert j2.recipe["chain"] == {"clip_id": j.result["clip_id"], "carry": 5, "offset": 77} and j2.recipe["seeds"] == [3]
        assert any("carried on: the last 5 frames" in line for line in j2.log_tail)
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.status == "running" and layer.frames_done == n                     # stitched; its matte runs next
        assert len(list(store.pass_dir(f.id, "fig", "frames").glob("*.png"))) == n
        jm = await rig.wait(layer.job_ids[-1], timeout=60)
        assert jm.status == "done" and jm.recipe["kind"] == "matte_sequence", (jm.error, jm.log_tail[-5:])
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.status == "done" and len(list(store.pass_dir(f.id, "fig", "matte").glob("*.png"))) == n
        # PS5e: the plate's frames (as Stage would project them), then the assembly
        from loom2 import final_assembly
        from loom2.final_assembly import check_ready
        assert check_ready(store, store.get(f.id)) == ["the plate is not projected yet"]
        store.set_frames(f.id, "plate", [png] * n)
        monkeypatch.setattr(final_assembly, "rife_binary", lambda: None)              # the clip at its own rate (RIFE is a local tool)
        ja = rig.queue.submit({"kind": "assemble_final", "final_id": f.id}, origin=JobOrigin(suite="stage", surface="final_assemble", ref=f.id))[0]
        ja = await rig.wait(ja.id, timeout=120)
        assert ja.status == "done", (ja.error, ja.log_tail[-5:])
        done = store.get(f.id)
        assert done.clip_id == ja.result["clip_id"] and done.assembly["frames"] == n and "fig" in done.assembly["offsets_px"]
        from loom2.clips import ClipStore
        clip = ClipStore(rig.ws).get(done.clip_id)
        assert clip.frames == n and clip.fps == 16 and clip.w == 128
        a = rig.catalogue.get(ja.result["asset_ids"][0])
        assert a.kind == "video" and a.lineage_kind == "final" and ref.id in a.parents
    finally:
        await rig.close()


def test_the_matte_is_sam3_where_offered_else_the_subject_matte(tmp_path: Path):
    """PS5d: SAM 3's licence keeps it `full`-only; under `open` a character layer is matted by BiRefNet's subject matte (MIT)."""
    from loom2.engine import graphs
    from loom2.recipes import MatteSequence, matte_mode
    from test_graph_parity_d64 import _pin_review
    assert matte_mode("full") == "text" and matte_mode("open") == "subject"
    roster = _pin_review().full_roster(tmp_path)
    sam = graphs.build_matte_sequence(MatteSequence(final_id="f", layer_id="l"), roster, "v.mp4", "x")
    sub = graphs.build_matte_sequence(MatteSequence(final_id="f", layer_id="l", mode="subject"), roster, "v.mp4", "x")
    assert {n["class_type"] for n in sam.graph.values()} >= {"SAM3_Detect", "LoadVideo"} and "RemoveBackground" not in {n["class_type"] for n in sam.graph.values()}
    assert {n["class_type"] for n in sub.graph.values()} >= {"RemoveBackground", "LoadVideo"} and "SAM3_Detect" not in {n["class_type"] for n in sub.graph.values()}
