"""CA3 (D130, proto01_animate 31 §4c): the plate generated along the path — the plate's Klein still landing on a plate whose method is
`generated` queues LTX-2.3 from it on the final's plate depth pass (the guide on the clip's 32 grid and LTX's 8k + 1 frames, at the final's
rate), and the clip's frames, resized and trimmed, are the plate's own; the method switched on the plate's row keeps the still (projected:
Stage projects it; generated: its clip queued now); a final longer than LTX's longest clip is projected. O4: a Shot's plate in a scene takes
the scene's first plate as its first reference."""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_finals_d111 import _final_on_disk  # noqa: E402


def test_the_clip_on_the_grid_and_the_method_check():
    from loom2.finals import PLATE_PATH_MAX, Final, plate_method_check, plate_path_frames, plate_path_size
    assert [plate_path_frames(n) for n in (2, 9, 10, 81, 100, 121)] == [9, 9, 17, 81, 105, 121]
    f = Final(stage_id="s", camera_id="c", stage_revision=0, range={"start": 0, "end": 120}, size={"w": 832, "h": 468}, frames=81)
    assert plate_path_size(f, 576) == (1024, 576)                                          # E34's size at a 16:9 final
    assert plate_path_size(f.model_copy(update={"size": {"w": 480, "h": 832}}), 576) == (320, 576)
    plate_method_check("projected", 721)
    plate_method_check("generated", PLATE_PATH_MAX)
    with pytest.raises(ValueError, match="at most 257"):
        plate_method_check("generated", PLATE_PATH_MAX + 1)
    with pytest.raises(ValueError, match="not 'move'"):
        plate_method_check("move", 3)


async def test_the_still_lands_and_the_plate_is_generated_along_the_path(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from fastapi import HTTPException
    from loom2.finals import FINAL_PLATE_PATH_SURFACE, FINAL_PLATE_SURFACE, PLATE_LEAD, PLATE_PATH_TAIL, FinalStore
    from loom2.origin import JobOrigin
    from loom2.routes.finals import PlateMethodBody, final_plate_method
    from loom2.stages import StageStore
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Room")
        store = FinalStore(rig.ws)
        f = _final_on_disk(rig.ws, st.id, st.cameras[0].id)
        f = store.update_layer(f.id, "plate", method="generated")
        clay = rig.catalogue.ingest_file(store.pass_dir(f.id, "plate", "clay") / "0000.png", kind="image", move=False, suite="stage")
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "stage_shot", "stage_id": st.id, "camera_id": st.cameras[0].id, "passes": {"clay": clay.id}, "method": "clay", "prompt_text": "an empty room"},
                               origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=f.id, payload={"prompt": "a whitewashed room"}))[0]
        store.update_layer(f.id, "plate", status="queued", job_ids=[job.id])
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        assert plate.still_asset_id == j.result["asset_ids"][0] and plate.guide_asset_id and len(plate.job_ids) == 2
        clip_job = rig.queue.jobs[plate.job_ids[-1]]
        r = clip_job.recipe
        assert (r["kind"], r["start_asset"], r["frames"], r["fps"], r["guide"]) == ("i2v", plate.still_asset_id, 9, 16, {"asset_id": plate.guide_asset_id, "kind": "depth", "strength": 1.0})
        assert r["width"] % 32 == 0 and r["height"] == 576 and r["prompt_text"] == f"{PLATE_LEAD} a whitewashed room. {PLATE_PATH_TAIL}"
        assert (clip_job.origin.surface, clip_job.origin.ref) == (FINAL_PLATE_PATH_SURFACE, f.id)
        guide = rig.catalogue.get(plate.guide_asset_id)
        assert (guide.frames, guide.w, guide.h) == (9, r["width"], 576)                         # the depth pass at the clip's size, held to 9 frames
        jc = await rig.wait(clip_job.id, timeout=60)
        assert jc.status == "done", (jc.error, jc.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        assert (plate.status, plate.frames_done, plate.clip_id) == ("done", 3, jc.result["clip_id"])
        frames = sorted(store.pass_dir(f.id, "plate", "frames").glob("*.png"))
        assert len(frames) == 3 and Image.open(frames[0]).size == (128, 128)                   # trimmed to the final's 3, at its size
        svc = types.SimpleNamespace(queue=rig.queue, hub=rig.queue.hub, app=rig.app, require_project=lambda: (rig.ws, rig.catalogue, None))
        # the plate's row: projected keeps the still for Stage to project; generated again queues a clip from it at once
        fin = await final_plate_method(svc, f.id, PlateMethodBody(method="projected"))
        plate = next(x for x in fin["layers"] if x["id"] == "plate")
        assert (plate["method"], plate["status"], plate["frames_done"], plate["clip_id"]) == ("projected", "running", 0, None)
        fin = await final_plate_method(svc, f.id, PlateMethodBody(method="generated", prompt_text="a whitewashed room"))
        plate = next(x for x in fin["layers"] if x["id"] == "plate")
        assert plate["method"] == "generated" and plate["status"] == "queued" and plate["job_ids"][-1] != clip_job.id
        with pytest.raises(HTTPException) as e:                                                # at work: wait for it
            await final_plate_method(svc, f.id, PlateMethodBody(method="projected"))
        assert e.value.status_code == 409
        jc2 = await rig.wait(plate["job_ids"][-1], timeout=60)
        assert jc2.status == "done" and next(x for x in store.get(f.id).layers if x.id == "plate").status == "done"
        # a picture set's plate is neither
        store.update_layer(f.id, "plate", method="picture")
        with pytest.raises(HTTPException) as e:
            await final_plate_method(svc, f.id, PlateMethodBody(method="generated"))
        assert e.value.status_code == 422
    finally:
        await rig.close()


def test_a_long_final_is_projected_and_a_scene_shares_its_first_plate(tmp_path: Path):
    """The route refuses a generated plate past LTX's longest clip before any still is made; O4: the second Shot of a scene takes the
    first Shot's plate still as its first reference (the place), the first Shot none."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import FinalStore
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        ws = Workspace(tmp_path / "proj")
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        store = FinalStore(ws)
        long = _final_on_disk(ws, st["id"], st["cameras"][0]["id"], frames=300)
        r = cl.put(f"/finals/{long.id}/layers/plate/method", json={"method": "generated"}, headers=H)
        assert r.status_code == 422 and "at most 257" in r.json()["detail"]
        store.update_layer(long.id, "plate", method="generated")
        r = cl.post(f"/finals/{long.id}/plate", json={"prompt_text": "a room"}, headers=H)
        assert r.status_code == 422 and "project it" in r.json()["detail"]
        # O4: two Shots in a scene, the first with its plate made
        story = StoryStore(ws)
        a, b = story.create_node("dialogue", "Wide", 0, 0), story.create_node("dialogue", "Mara", 0, 200)
        story.create_scene("The quay", [a.id, b.id])
        sa, sb = story.flow_node(a.id).shot_id, story.flow_node(b.id).shot_id
        fa = _final_on_disk(ws, st["id"], st["cameras"][0]["id"])
        fa = store.save(fa.model_copy(update={"shot_id": sa})) or store.get(fa.id)
        store.update_layer(fa.id, "plate", still_asset_id="ast_first_plate")
        fb = _final_on_disk(ws, st["id"], st["cameras"][0]["id"])
        store.save(fb.model_copy(update={"shot_id": sb}))
        r = cl.post(f"/finals/{fb.id}/plate", json={"prompt_text": "the quay", "refs": [{"asset_id": "ast_style", "note": None}]}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["scene_plate"] == "ast_first_plate"
        job = next(j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] == r.json()["job_id"])
        assert [x["asset_id"] for x in job["recipe"]["refs"]] == ["ast_first_plate", "ast_style"] and job["origin"]["payload"]["prompt"] == "the quay" and job["origin"]["payload"]["people"] is False   # D184: the payload carries what the anchor stills need
        r = cl.post(f"/finals/{fa.id}/plate", json={"prompt_text": "the quay"}, headers=H)
        assert r.status_code == 200 and r.json()["scene_plate"] is None                       # the scene's first Shot


def test_a_guided_clip_snaps_to_the_ic_loras_grid():
    """The rig (2026-10-24): LTX's IC-LoRA works on a latent halved again — a guided clip at 992 × 576 (latent 31 × 18) was refused by the
    engine. The spec's guide_size_mult (64) is the guided clip's grid; the plain clip keeps the model's 32; /capabilities says it."""
    from loom2.engine.graphs import i2v_params
    from loom2.models import registry
    from loom2.recipes import I2V
    spec = next(s for s in registry.video_specs() if s.recipes.guide_lora)
    assert spec.recipes.guide_size_mult == 64
    guided = I2V(model_id=spec.id, start_asset="a", width=992, height=576, frames=81, guide={"asset_id": "g", "kind": "depth"})
    assert (i2v_params(guided)["width"], i2v_params(guided)["height"]) == (960, 576)
    plain = guided.model_copy(update={"guide": None})
    assert i2v_params(plain)["width"] == 992


def test_the_anchors_a_generated_plate_wants():
    """D184 (C5): a still every BEAT_SECONDS and the last frame, unless a beat is within half a second of it; none under a second."""
    from loom2.finals import Final, plate_beats_wanted
    mk = lambda frames, rate=16: Final(stage_id="stg_x", camera_id="cam_x", stage_revision=0, range={"start": 0, "end": frames}, rate=rate, size={"w": 128, "h": 128}, frames=frames)
    assert plate_beats_wanted(mk(9)) == []                                                      # under a second: the first still holds it
    assert plate_beats_wanted(mk(161)) == [80, 160]                                            # 10 s at F16: 5 s and the last frame
    assert plate_beats_wanted(mk(241, 24)) == [120, 240]
    assert plate_beats_wanted(mk(85)) == [80]                                                  # the last frame within half a second of a beat: not twice
    assert plate_beats_wanted(mk(33)) == [32]


@pytest.mark.asyncio
async def test_the_anchor_stills_land_before_the_clip_and_the_extras_ride_the_plate(tmp_path: Path, object_info: dict, monkeypatch):
    """D184 (C5): a generated plate's first still lands → its anchor stills are queued one after another from the plate's clay pass at
    their frames (the same words, references, mentions, size and seed) → the clip is queued with them as LTX beats at the clip's frames;
    the extras on the plate make the lead speak of the people and ride along as mentions."""
    import test_lifecycle
    from loom2 import finals as F
    from loom2.finals import FINAL_PLATE_PATH_SURFACE, FINAL_PLATE_SURFACE, PLATE_LEAD_PEOPLE, PLATE_PATH_TAIL_PEOPLE, FinalStore
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    from test_finals_d111 import _final_on_disk
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    monkeypatch.setattr(F, "BEAT_SECONDS", 1)                                                  # a beat every second on a two-second final
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        from loom2.groups import GroupStore
        from loom2.story import StoryStore
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)                                # a bound figure's mention needs the project's Cast
        man = StoryStore(rig.ws).create_profile("Man with a newspaper", "character", groups, appearance="a man in a grey coat")
        st = StageStore(rig.ws).create("Street")
        store = FinalStore(rig.ws)
        f = _final_on_disk(rig.ws, st.id, st.cameras[0].id, frames=33)
        extras = [{"object_id": "fig_extra", "profile_id": man.id, "version": "v1", "name": "Man with a newspaper"}]
        f = store.update_layer(f.id, "plate", method="generated", extras=extras, beats=[{"frame": k, "asset_id": None, "job_id": None} for k in F.plate_beats_wanted(f)])
        assert [b["frame"] for b in next(x for x in f.layers if x.id == "plate").beats] == [16, 32]
        clay = rig.catalogue.ingest_file(store.pass_dir(f.id, "plate", "clay") / "0000.png", kind="image", move=False, suite="stage")
        rig.queue.load()
        await rig.queue.start()
        text = F.plate_still_text("a cobbled street", "", True)
        assert text.startswith(PLATE_LEAD_PEOPLE)
        mentions = [{"profile_id": man.id, "version": "v1", "figure": "fig_extra"}]
        payload = {"prompt": "", "text": text, "refs": [], "mentions": mentions, "seed": 3, "size": [128, 128], "people": True}
        job = rig.queue.submit({"kind": "stage_shot", "stage_id": st.id, "camera_id": st.cameras[0].id, "passes": {"clay": clay.id}, "method": "clay", "empty": False,
                                "prompt_text": text, "mentions": mentions, "seeds": [3], "width": 128, "height": 128},
                               origin=JobOrigin(suite="stage", surface=FINAL_PLATE_SURFACE, ref=f.id, payload=payload))[0]
        store.update_layer(f.id, "plate", status="queued", job_ids=[job.id])
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        assert plate.still_asset_id == j.result["asset_ids"][0] and plate.clip_id is None            # the first still: no clip yet — the anchors first
        assert plate.beats[0]["job_id"] and plate.beats[0]["asset_id"] is None and "anchor at frame 16" in " ".join(j.log_tail)
        b16 = rig.queue.jobs[plate.beats[0]["job_id"]]
        assert b16.recipe["prompt_text"] == text and b16.recipe["mentions"][0]["figure"] == "fig_extra" and b16.recipe["empty"] is False and b16.recipe["seeds"] == [3]
        assert b16.origin.payload["beat"] == 16 and rig.catalogue.get(b16.recipe["passes"]["clay"]).params["frame"] == 16
        j16 = await rig.wait(b16.id, timeout=60)
        assert j16.status == "done", (j16.error, j16.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        assert plate.beats[0]["asset_id"] == j16.result["asset_ids"][0] and plate.beats[1]["job_id"] and plate.clip_id is None
        j32 = await rig.wait(plate.beats[1]["job_id"], timeout=60)
        assert j32.status == "done", (j32.error, j32.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        assert plate.beats[1]["asset_id"] == j32.result["asset_ids"][0] and "generated along the path" in " ".join(j32.log_tail)
        clip_job = rig.queue.jobs[plate.job_ids[-1]]
        r = clip_job.recipe
        assert (clip_job.origin.surface, r["kind"], r["start_asset"], r["frames"]) == (FINAL_PLATE_PATH_SURFACE, "i2v", plate.still_asset_id, 33)
        assert r["beats"] == [{"frame": 16, "asset_id": plate.beats[0]["asset_id"], "strength": 1.0}, {"frame": 32, "asset_id": plate.beats[1]["asset_id"], "strength": 1.0}]
        assert r["prompt_text"] == f"{PLATE_LEAD_PEOPLE} {PLATE_PATH_TAIL_PEOPLE}"
        jc = await rig.wait(clip_job.id, timeout=90)
        assert jc.status == "done", (jc.error, jc.log_tail[-5:])
        assert next(x for x in store.get(f.id).layers if x.id == "plate").status == "done"
    finally:
        await rig.close()
