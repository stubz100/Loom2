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
            "size": {"w": 64, "h": 64}, "frames": frames,
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
