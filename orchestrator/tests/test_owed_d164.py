"""D164 (E45): a shot's owed work includes the face work.

- the head is placed against the band (too small, in it, large enough, seen from behind, out of the frame);
- the owed list (GET /finals/{fid}/owed) counts a layer's face pass, or its lip-sync when its character speaks, with a cost;
- the owed run (POST) queues it, or performs a layer with its face work asked for after the matte;
- a re-take retires the layer's takes, so its face work is owed again;
- a matte that strays is made once more by the other model (the one that strays less is kept), then the face work follows.
"""
from pathlib import Path

from test_compositions_ae1 import FAKE
from test_face_pass_ae4c import S, _fake_weights, _final_with_head, _keypoints
from test_window_d163 import _figure

W, H = 848, 480


def test_the_head_is_placed_against_the_band():
    from loom2.owed import FACE_BAND, face_fit, head_stats
    lo, hi = FACE_BAND
    px = lambda tall: head_stats([_figure(400, 120, tall)] * 4, W, H)["px"]  # noqa: E731  (2.6 × nose–neck: 0.234 × the figure's height)
    small, mid, large = (lo - 4) / 0.234, (lo + hi) / 2 / 0.234, (hi + 40) / 0.234
    assert px(small) < lo <= px(mid) <= hi < px(large)
    assert [face_fit(head_stats([_figure(400, 120, t)] * 4, W, H)) for t in (small, mid, large)] == ["small", "band", "large"]
    away = [[p[:] for p in _figure(400, 120, mid)] for _ in range(4)]
    for k in away:                                                     # the right eye on the image's right of the left: its back to the camera
        k[14][0], k[15][0] = k[15][0], k[14][0]
    assert face_fit(head_stats(away, W, H)) == "away"
    assert face_fit(head_stats([_figure(-200, 120, mid)] * 4, W, H)) == "out"             # The ferryman's Ines: her head outside the frame
    assert head_stats([_figure(-200, 120, mid)] * 4, W, H)["in_frame"] == 0.0


def _app(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "effectcraft": {"cli": str(FAKE)}})
    app = create_app(state)
    return TestClient(app), app.state.services


def test_the_owed_list_counts_the_face_pass_and_the_run_queues_it(tmp_path: Path, monkeypatch):
    from loom2 import owed
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.groups import GroupStore
    from loom2.story import StoryStore
    from test_finals_d111 import _figure_ref
    monkeypatch.setattr(owed, "FACE_BAND", (20.0, 220.0))              # the fixture's head: 36 px in a 128 px frame
    cl, svc = _app(tmp_path)
    H_ = {"X-Loom-Token": svc.app.token}
    with cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H_)
        st = cl.post("/stages", json={"name": "Room"}, headers=H_).json()
        f, _ = _final_with_head(svc.ws, st["id"], st["cameras"][0]["id"], tmp_path / "src")
        o = cl.get(f"/finals/{f.id}/owed", headers=H_).json()
        assert o["band"] == [20.0, 220.0]
        face = [x for x in o["items"] if x["kind"] == "face"]
        assert [(x["layer"], x["queue"], x["after"]) for x in face] == [("fig", True, False)] and face[0]["seconds"] > 0 and o["seconds"] >= face[0]["seconds"]
        r = cl.post(f"/finals/{f.id}/owed", headers=H_)
        assert r.status_code == 200, r.text
        q = r.json()["queued"]
        assert [(x["kind"], x["layer"]) for x in q] == [("face", "fig")] and q[0]["job_id"]
        rec = cl.get(f"/jobs/{q[0]['job_id']}", headers=H_).json()["recipe"]
        assert rec["preset"] == "face" and rec["step"]["stage"] == "head"
        assert not any(x["kind"] == "face" for x in r.json()["owed"]["items"])         # under way: not owed twice
        # a re-take retires the takes (its face work owed again) and shows its own frames; an owed run's face work waits for its matte
        store = FinalStore(svc.ws)
        take = store.pass_dir(f.id, "fig", "passes/take_old")
        take.mkdir(parents=True)
        for i in range(f.frames):
            (take / f"{i:04d}.png").write_bytes((store.pass_dir(f.id, "fig", "frames") / f"{i:04d}.png").read_bytes())
        store.update_layer(f.id, "fig", takes=[{"id": "take_old", "preset": "face", "made_at": "2026-10-30T00:00:00Z"}], source="take_old", job_ids=[])
        assert not any(x["kind"] == "face" for x in cl.get(f"/finals/{f.id}/owed", headers=H_).json()["items"])   # its face take is current
        cat = Catalogue(svc.ws, [32], session_id="t")
        front = cat.ingest_file(_figure_ref(tmp_path / "front.png"), kind="image", move=False, suite="stage")
        sst = StoryStore(svc.ws)
        p = sst.create_profile("Mara", "character", GroupStore(svc.ws, cat), appearance="a woman in a red coat")
        sst.set_anim_ref(p.id, "v1", "front", front.id)
        store.update_layer(f.id, "fig", profile_id=p.id)
        r = cl.post(f"/finals/{f.id}/layers/fig/run", json={"then_owed": True}, headers=H_)
        assert r.status_code == 200, r.text
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.source is None and [t.get("stale") for t in layer.takes] == [True] and layer.then_owed and not layer.matte_retry
        face = [x for x in cl.get(f"/finals/{f.id}/owed", headers=H_).json()["items"] if x["kind"] == "face"]
        assert [(x["queue"], x["after"], x["why"]) for x in face] == [(False, True, "queued after its performance")]


def test_lip_sync_is_owed_for_a_speaking_character(tmp_path: Path, monkeypatch):
    from loom2 import owed
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    monkeypatch.setattr(owed, "FACE_BAND", (20.0, 220.0))
    ws = Workspace.create(tmp_path / "p", name="P")
    f, _ = _final_with_head(ws, "stg_1", "cam_1", tmp_path / "src")
    store = FinalStore(ws)
    layer = lambda: next(x for x in store.get(f.id).layers if x.id == "fig")  # noqa: E731
    said = [{"text": "Hello.", "audio_asset_id": "ast_1"}]
    lane = lambda secs: [{"final_layer": "fig", "in": 0.2, "out": 0.2 + secs, "start": 0.2, "path": "x.wav"}]  # noqa: E731
    it = owed.layer_owed(ws, None, store, f, layer(), said, None)
    assert (it["kind"], it["queue"], it["why"]) == ("lipsync", False, "its lines go on the lanes at Final")   # no face pass first: lip-sync makes the head
    assert owed.layer_owed(ws, None, store, f, layer(), said, lane(0.6))["queue"] is True
    it = owed.layer_owed(ws, None, store, f, layer(), said, lane(6.0))
    assert not it["queue"] and "longer than 4.8 s" in it["why"]
    away = _keypoints(f.frames)
    for k in away:
        k[14][0], k[15][0] = k[15][0], k[14][0]
    from loom2.fsio import atomic_write_json
    atomic_write_json(store.folder(f.id) / "fig" / "keypoints.json", {"schema_version": 1, "frames": away})
    it = owed.layer_owed(ws, None, store, f, layer(), said, lane(0.6))
    assert not it["queue"] and it["why"] == "it is seen from behind"
    assert owed.layer_owed(ws, None, store, f, layer(), [], None) is None                     # from behind and silent: nothing owed (E45 B2)
    store.update_layer(f.id, "fig", takes=[{"id": "take_l", "preset": "lipsync"}])
    atomic_write_json(store.folder(f.id) / "fig" / "keypoints.json", {"schema_version": 1, "frames": _keypoints(f.frames)})
    assert owed.layer_owed(ws, None, store, f, layer(), said, lane(0.6)) is None              # lip-synced on this performance
    assert S == 128


async def test_a_stray_matte_is_made_again_by_the_other_model_then_the_face_work_follows(tmp_path: Path, object_info: dict, monkeypatch):
    """The fake's SAM 3 answers a box that covers under half of the figure's Stage silhouette, so the matte strays on every frame: the
    finisher queues the subject matte into matte_retry/, which strays as much, so the first is kept; then the layer's owed face work
    (then_owed) is queued."""
    import test_lifecycle
    from loom2 import owed
    from loom2.finals import FinalStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    monkeypatch.setattr(owed, "FACE_BAND", (20.0, 220.0))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_with_head(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        _fake_weights(tmp_path, [next(s for s in registry.animate_specs()), registry.get(registry.segment_model("text")), registry.get(registry.segment_model("subject"))])
        rig.queue.load()
        await rig.queue.start()
        store = FinalStore(rig.ws)
        store.update_layer(f.id, "fig", then_owed=True, status="running", window=[])        # matted at the frame (its frames are there)
        job = rig.queue.submit({"kind": "matte_sequence", "final_id": f.id, "layer_id": "fig", "mode": "text"},
                               origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "matte": True}))[0]
        store.add_job(f.id, "fig", job.id)
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        assert any("made again by" in line for line in j.log_tail), j.log_tail[-4:]
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.matte_retry and layer.status == "done" and layer.matte_check["strays"]
        again = rig.queue.jobs[layer.job_ids[-1]]
        assert again.recipe["kind"] == "matte_sequence" and again.recipe["mode"] == "subject"
        j2 = await rig.wait(again.id, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert "the first kept" in layer.matte_check["retried"] and not store.pass_dir(f.id, "fig", "matte_retry").exists()
        assert len(list(store.pass_dir(f.id, "fig", "matte").glob("*.png"))) == f.frames
        assert not layer.then_owed and any("the face pass queued after its matte" in line for line in j2.log_tail), j2.log_tail[-3:]
        face = rig.queue.jobs[layer.job_ids[-1]]
        assert face.recipe["kind"] == "layer_pass" and face.recipe["preset"] == "face"
    finally:
        await rig.close()
