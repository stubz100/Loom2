"""17 (D85) · SY2 Shots: shot records with versions (a stage camera and / or a clip as the source, takes, the frame and the one clip), the
finalize gate (the project format's size), copies, the stage link (a camera's frame / clip becomes a take of the shots pointing at it),
the routes end to end and the finisher hook on the fake engine."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import Shot, ShotVersion, StaleShot, StoryStore, check_shot, finalize_reason  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_groups_d34 import _png  # noqa: E402


def _clip(ws: Workspace, tmp: Path, w: int = 64, h: int = 64, n: int = 3):
    frames = []
    for i in range(n):
        p = tmp / f"f{w}x{h}_{i}.png"
        from PIL import Image
        Image.new("RGB", (w, h), (i * 40, 80, 120)).save(p)
        frames.append(p)
    return ClipStore(ws).create(frames, model_id="m", fps=24, start_asset_id="ast_x")


def test_invariants_and_the_gate():
    check_shot(Shot(name="Gate", current="v1", versions=[ShotVersion(id="v1")]))
    with pytest.raises(ValueError, match="needs a name"):
        check_shot(Shot(name=" ", current="v1", versions=[ShotVersion(id="v1")]))
    with pytest.raises(ValueError, match="current version"):
        check_shot(Shot(name="G", current="v2", versions=[ShotVersion(id="v1")]))
    with pytest.raises(ValueError, match="both the stage and the camera"):
        check_shot(Shot(name="G", current="v1", versions=[ShotVersion(id="v1", stage_id="stg")]))
    v = ShotVersion(id="v1")
    assert "no clip yet" in finalize_reason(v, None, None, 1920, 1080)
    v = ShotVersion(id="v1", clip_id="clp")
    assert finalize_reason(v, None, None, 1920, 1080) == "clip clp is gone"
    assert finalize_reason(v, 1024, 576, 1920, 1080) == "Draft 1024×576 — the format is 1920×1080; render Full in Animate"
    assert finalize_reason(v, 1920, 1080, 1920, 1080) is None
    assert finalize_reason(v, 1920, 1088, 1920, 1080) is None and finalize_reason(v, 1920, 1056, 1920, 1080) is None   # the models' grids; the export crops
    assert finalize_reason(v, 1280, 704, 1920, 1080) is not None
    assert finalize_reason(ShotVersion(id="v1", state="final"), None, None, 1920, 1080) is None


def test_store_create_take_copy_finalize_delete(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    s = st.create_shot("Gate", stage_id="stg_1", camera_id="cam_1", stage_revision=3)
    v = s.version()
    assert s.current == "v1" and v.stage_id == "stg_1" and v.stage_revision == 3 and v.takes == [] and v.clip_id is None
    assert [x.id for x in st.shots()] == [s.id] and st.shot(s.id) == s
    with pytest.raises(ValueError):
        st.create_shot("  ")
    # takes: the first image fills the frame, a second is a take only; `use` swaps
    s = st.add_take(s.id, "v1", "image", "ast_a", stage_revision=4)
    assert s.version().frame_asset_id == "ast_a" and s.version().stage_revision == 4 and [t.id for t in s.version().takes] == ["ast_a"]
    s = st.add_take(s.id, "v1", "image", "ast_b")
    assert s.version().frame_asset_id == "ast_a" and [t.id for t in s.version().takes] == ["ast_a", "ast_b"]
    s = st.add_take(s.id, "v1", "image", "ast_b", use=True)
    assert s.version().frame_asset_id == "ast_b" and [t.id for t in s.version().takes] == ["ast_a", "ast_b"]       # re-taking does not duplicate
    s = st.add_take(s.id, "v1", "clip", "clp_1")
    assert s.version().clip_id == "clp_1" and [t.kind for t in s.version().takes] == ["image", "image", "clip"]
    with pytest.raises(ValueError, match="image or a clip"):
        st.add_take(s.id, "v1", "mesh", "x")
    # patch with the revision; stale refused
    s2 = st.patch_shot(s.id, {"revision": s.revision, "name": "Gate at dawn", "owner_node": "node_1"})
    assert s2.name == "Gate at dawn" and s2.owner_node == "node_1" and s2.revision == s.revision + 1
    with pytest.raises(StaleShot):
        st.patch_shot(s.id, {"revision": s.revision, "name": "x"})
    with pytest.raises(ValueError):
        st.patch_shot(s.id, {"revision": s2.revision, "versions": [{"id": "v1", "stage_id": None}]})     # a camera without its stage
    # finalize: the gate reads the clip's size against the format
    with pytest.raises(ValueError, match="Draft 640×360"):
        st.finalize_shot(s.id, "v1", (640, 360), (1920, 1080))
    s3 = st.finalize_shot(s.id, "v1", (1920, 1080), (1920, 1080))
    assert s3.version().state == "final" and s3.version().finalized_at
    assert st.finalize_shot(s.id, "v1", (1920, 1080), (1920, 1080)).revision == s3.revision                      # twice is a no-op
    with pytest.raises(ValueError, match="final"):
        st.add_take(s.id, "v1", "clip", "clp_2")
    with pytest.raises(ValueError, match="final"):
        st.patch_shot(s.id, {"revision": s3.revision, "versions": [{"id": "v1", "clip_id": "clp_2"}]})
    assert st.patch_shot(s.id, {"revision": s3.revision, "owner_node": None}).owner_node is None                   # release is always allowed
    # copy: the pointers come along, not the takes; the copy is current and open
    s4 = st.new_shot_version(s.id)
    v2 = s4.version()
    assert s4.current == "v2" and v2.derived_from == "v1" and v2.state == "open" and v2.clip_id == "clp_1" and v2.frame_asset_id == "ast_b" and v2.takes == []
    assert v2.stage_id == "stg_1" and v2.stage_revision == 4
    # the stage link: a camera's result becomes a take of every shot pointing at it (the slot filled when empty)
    other = st.create_shot("Other", stage_id="stg_1", camera_id="cam_2")
    done = st.create_shot("Done", stage_id="stg_1", camera_id="cam_1", clip_id="clp_9")
    hit = st.record_stage_result("stg_1", "cam_1", "clip", "clp_new", 7)
    assert sorted(x.name for x in hit) == ["Done", "Gate at dawn"]
    assert st.shot(s.id).version().clip_id == "clp_1" and [t.id for t in st.shot(s.id).version().takes] == ["clp_new"]   # v2 keeps its clip, records the take
    assert st.shot(done.id).version().clip_id == "clp_9" and st.shot(other.id).version().takes == []
    assert st.delete_shot(s.id) and st.shot(s.id) is None and not st.delete_shot(s.id)


def test_routes_shots(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.get("/story/shots").status_code == 409
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws = Workspace(tmp_path / "p")
        img = svc.catalogue.ingest_file(_png(tmp_path / "f.png")).id
        stg = cl.post("/stages", json={"name": "Alley"}).json()
        cam = stg["cameras"][0]["id"]
        assert cl.post("/story/shots", json={"name": "Gate", "stage_id": stg["id"]}).status_code == 422                 # a stage without its camera
        assert cl.post("/story/shots", json={"name": "Gate", "stage_id": stg["id"], "camera_id": "cam_nope"}).status_code == 422
        assert cl.post("/story/shots", json={"name": "Gate", "clip_id": "clp_nope"}).status_code == 422
        assert cl.post("/story/shots", json={"name": "Gate", "frame_asset_id": "ast_nope"}).status_code == 422
        s = cl.post("/story/shots", json={"name": "Gate", "stage_id": stg["id"], "camera_id": cam, "frame_asset_id": img}).json()
        assert s["versions"][0]["stage_revision"] == stg["revision"] and s["versions"][0]["frame_asset_id"] == img and s["versions"][0]["takes"][0]["id"] == img
        assert cl.get("/story/shots").json()["items"][0]["id"] == s["id"] and cl.get(f"/story/shots/{s['id']}").json()["name"] == "Gate"
        # a take: a draft clip; finalize refused with the reason; a full-size clip; finalize ok
        small = _clip(ws, tmp_path, 640, 360)
        r = cl.post(f"/story/shots/{s['id']}/versions/v1/take", json={"kind": "clip", "id": small.id})
        assert r.status_code == 200 and r.json()["versions"][0]["clip_id"] == small.id
        assert cl.post(f"/story/shots/{s['id']}/versions/v1/take", json={"kind": "clip", "id": "clp_nope"}).status_code == 422
        assert cl.post(f"/story/shots/{s['id']}/versions/v1/take", json={"kind": "image", "id": "ast_nope"}).status_code == 422
        r = cl.post(f"/story/shots/{s['id']}/versions/v1/finalize")
        assert r.status_code == 422 and "640×360" in r.json()["detail"] and "1920×1080" in r.json()["detail"]
        big = _clip(ws, tmp_path, 1920, 1080)
        cl.post(f"/story/shots/{s['id']}/versions/v1/take", json={"kind": "clip", "id": big.id, "use": True})
        r = cl.post(f"/story/shots/{s['id']}/versions/v1/finalize")
        assert r.status_code == 200 and r.json()["versions"][0]["state"] == "final" and r.json()["versions"][0]["clip_id"] == big.id
        assert cl.post(f"/story/shots/{s['id']}/versions/v1/take", json={"kind": "clip", "id": small.id}).status_code == 422          # final: fixed
        # patch: name and owner; stale → 409; copy → v2 open with the pointers
        s = cl.get(f"/story/shots/{s['id']}").json()
        r = cl.patch(f"/story/shots/{s['id']}", json={"revision": s["revision"], "name": "Gate at dawn", "owner_node": "node_1"})
        assert r.status_code == 200 and r.json()["owner_node"] == "node_1"
        assert cl.patch(f"/story/shots/{s['id']}", json={"revision": s["revision"], "name": "x"}).status_code == 409
        r = cl.post(f"/story/shots/{s['id']}/versions")
        assert r.status_code == 200 and r.json()["current"] == "v2" and r.json()["versions"][1]["clip_id"] == big.id and r.json()["versions"][1]["state"] == "open"
        # the stage link through the store (the finisher's path): a new clip of the camera becomes v2's take, the clip slot stays
        hit = StoryStore(ws).record_stage_result(stg["id"], cam, "clip", small.id, 5)
        assert [x.id for x in hit] == [s["id"]] and cl.get(f"/story/shots/{s['id']}").json()["versions"][1]["takes"][0]["id"] == small.id
        assert cl.delete(f"/story/shots/{s['id']}").json()["deleted"] == s["id"] and cl.get(f"/story/shots/{s['id']}").status_code == 404


async def test_a_stage_shot_fills_the_shot_pointing_at_its_camera(tmp_path: Path, object_info: dict):
    """The finisher hook: a StageShot result (ST3) lands as the frame of the shot made from that camera."""
    from loom2.groups import GroupStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from test_lifecycle import Rig
    rig = Rig(tmp_path, object_info)
    try:
        rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        stages = StageStore(rig.ws)
        stg = stages.create("Alley", {"w": 64, "h": 64, "fps": 24})
        cam = stg.cameras[0].id
        passes = {n: rig.catalogue.ingest_file(_png(tmp_path / f"{n}.png")).id for n in ("clay", "depth", "normal", "pose", "mask")}
        stages.set_passes(stg.id, {"camera_id": cam, "revision": 0, "size": {"w": 64, "h": 64}, "assets": passes, "keypoints": [], "legend": {}}, None)
        st = StoryStore(rig.ws)
        shot = st.create_shot("Gate", stage_id=stg.id, camera_id=cam, stage_revision=stg.revision)
        rig.queue.load()
        await rig.queue.start()
        spec = next(sp for sp in registry.stage_specs() if sp.recipes.stage == "clay" and rig.roster.resolve(sp.id).path)
        job = rig.queue.submit({"kind": "stage_shot", "stage_id": stg.id, "camera_id": cam, "method": "clay", "model_id": spec.id, "prompt_text": "a gate", "width": 64, "height": 64, "seeds": [3], "passes": {"clay": passes["clay"]}},
                               origin=JobOrigin(suite="stage", surface="shot", ref=stg.id, payload={"camera_id": cam}))[0]
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        s = st.shot(shot.id)
        assert s.version().frame_asset_id == done.result["asset_ids"][0] and s.version().takes[0].kind == "image" and s.version().stage_revision == stages.get(stg.id).revision
    finally:
        await rig.close()
