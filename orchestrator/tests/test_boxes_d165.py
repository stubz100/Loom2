"""D165: a character layer's window and head box as keyframed boxes the author adjusts on Performance's frames.

- the automatic track becomes keys (few for a figure standing still, more where it turns) and the keys interpolate back;
- the routes: GET /finals/{fid}/boxes offers the automatic keys; PUT sets keys, removes a box or gives it back to the rule;
- the run performs in the author's window and stamps it, so a window changed since is seen (and a re-take from a batch refused);
- Clay's redraw keeps the keys; a head box removed by hand takes the face work off the owed list, one set by hand puts it on;
- the face pass crops the author's head boxes and stamps its take with them.
"""
from pathlib import Path

from test_face_pass_ae4c import _fake_weights, _final_with_head, _run_chain
from test_window_d163 import W, H, _app, _figure, _final


def test_a_track_becomes_keys_and_the_keys_interpolate_back():
    from loom2.boxes import interpolate, simplify
    still = [{"cx": 400.0, "cy": 240.0, "h": 300.0}] * 40
    assert [k["frame"] for k in simplify(still, "h", H)] == [0, 39]
    walk = [{"cx": 100.0 + 10 * i, "cy": 240.0, "h": 300.0} for i in range(40)]
    assert [k["frame"] for k in simplify(walk, "h", H)] == [0, 39]            # a straight walk: its ends
    turn = [{"cx": 100.0 + 10 * min(i, 20) - 10 * max(0, i - 20), "cy": 240.0, "h": 300.0} for i in range(41)]
    keys = simplify(turn, "h", H)
    assert [k["frame"] for k in keys] == [0, 20, 40]                          # it turns back at frame 20: a key there
    back = interpolate(keys, "h", 41)
    assert max(abs(b["cx"] - t["cx"]) for b, t in zip(back, turn)) < 0.02 * H
    held = interpolate([{"frame": 5, "cx": 10.0, "cy": 20.0, "h": 30.0}, {"frame": 9, "cx": 50.0, "cy": 20.0, "h": 30.0}], "h", 12)
    assert held[0]["cx"] == 10.0 and held[7]["cx"] == 30.0 and held[11]["cx"] == 50.0   # the ends held, the middle on the line


def test_the_windows_and_head_boxes_from_keys_and_their_misses():
    from loom2.boxes import head_misses, heads_from, layer_windows, simplify, window_cuts, window_track, windows_from
    from loom2.finals import FinalLayer, layer_window
    kps = [_figure(300 + 4 * i, 200, 120) for i in range(30)]
    auto = layer_window(kps, 30)
    keys = simplify(window_track(kps, 30), "h", H)
    mine = windows_from(keys, 30)
    assert max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(auto, mine)) < 0.05 * H and window_cuts(kps, mine) == []
    lay = FinalLayer(id="fig", kind="figure", name="T", method="move")
    assert layer_windows(lay, kps, 30) == auto
    assert layer_windows(lay.model_copy(update={"window_keys": []}), kps, 30) == []
    tight = [{"frame": 0, "cx": 300.0, "cy": 230.0, "h": 60.0}]                # a window of 60 px around the head: the body left out
    assert window_cuts(kps, layer_windows(lay.model_copy(update={"window_keys": tight}), kps, 30)) == list(range(30))
    boxes = heads_from([{"frame": 0, "cx": 5.0, "cy": 5.0, "side": 40.0}], 3, W, H)
    assert boxes[0] == (0, 0, 40)                                              # clamped to the picture, as the paste needs
    assert head_misses(kps, boxes) == [0, 1, 2]


def test_the_routes_offer_set_remove_and_reset_the_boxes(tmp_path: Path, monkeypatch):
    from loom2 import owed
    from loom2.boxes import sig
    from loom2.catalogue import Catalogue
    from loom2.finals import WINDOW, FinalStore
    from loom2.groups import GroupStore
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    from test_finals_d111 import _figure_ref
    cl, H_ = _app(tmp_path)
    with cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H_)
        ws = Workspace(tmp_path / "proj")
        cat = Catalogue(ws, [32], session_id="t")
        front = cat.ingest_file(_figure_ref(tmp_path / "front.png"), kind="image", move=False, suite="stage")
        st = StoryStore(ws)
        p = st.create_profile("Tomas", "character", GroupStore(ws, cat), appearance="an old man in a navy pea coat")
        st.set_anim_ref(p.id, "v1", "front", front.id)
        stage = cl.post("/stages", json={"name": "Pier"}, headers=H_).json()
        store = FinalStore(ws)
        kps = {"fig": [_figure(400 + 2 * i, 240, 44) for i in range(20)]}
        f = _final(ws, stage, kps)
        store.update_layer(f.id, "fig", profile_id=p.id)
        b = cl.get(f"/finals/{f.id}/boxes", headers=H_).json()
        assert b["window"] == list(WINDOW) and (b["w"], b["h"], b["frames"]) == (W, H, 20)
        lay = b["layers"][0]
        assert lay["window"]["mode"] == "auto" and lay["window"]["keys"] == lay["window"]["offer"] and len(lay["window"]["frames"]) == 20
        assert lay["head"]["mode"] == "auto" and len(lay["head"]["frames"]) == 20 and lay["fit"] == "small"
        # the window moved 20 px right and made 1.5× taller on frame 0, the rest of the keys kept
        keys = [dict(k) for k in lay["window"]["keys"]]
        keys[0] = {**keys[0], "cx": keys[0]["cx"] + 20, "h": keys[0]["h"] * 1.5}
        r = cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"window": "keys", "window_keys": keys}, headers=H_)
        assert r.status_code == 200, r.text
        lay = r.json()["layers"][0]
        assert lay["window"]["mode"] == "keys" and abs(lay["window"]["frames"][0][3] - keys[0]["h"]) < 0.5
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.window_keys and abs(WINDOW[1] / layer.window[0][2] - keys[0]["h"]) < 0.5
        # the run performs in it and stamps it; a window changed after the performance is seen, and a re-take from a batch refused
        r = cl.post(f"/finals/{f.id}/layers/fig/run", json={}, headers=H_)
        assert r.status_code == 200, r.text
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.window_sig == sig(layer.window)
        assert cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"window": "auto"}, headers=H_).status_code == 409   # being performed
        store.update_layer(f.id, "fig", status="done", frames_done=20, batches=[{"k": 0, "job_id": "job_x", "clip_id": "clp_x"}])
        assert not cl.get(f"/finals/{f.id}/boxes", headers=H_).json()["layers"][0]["window"]["changed"]
        lay = cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"window": "auto"}, headers=H_).json()["layers"][0]
        assert lay["window"]["mode"] == "auto" and lay["window"]["changed"]
        r = cl.post(f"/finals/{f.id}/layers/fig/run", json={"from_batch": 1}, headers=H_)
        assert r.status_code == 422 and "window changed" in r.json()["detail"]
        # removed: at the frame; Clay's redraw keeps the author's choice
        lay = cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"window": "none"}, headers=H_).json()["layers"][0]
        assert lay["window"]["mode"] == "none" and lay["window"]["frames"] == [] and lay["window"]["keys"] == [] and lay["window"]["offer"]
        png = ws.temp_dir / "p.png"
        store.set_passes(f.id, "fig", {"pose": [png] * 20, "depth": [png] * 20}, kps["fig"], None, [])
        assert next(x for x in store.get(f.id).layers if x.id == "fig").window == []
        # the head box: removed by hand takes the face work off the owed list; set by hand puts it on whatever the band says
        monkeypatch.setattr(owed, "FACE_BAND", (1000.0, 2000.0))             # every head "small": no face work by the rule
        store.update_layer(f.id, "fig", status="done", frames_done=20)
        md = store.pass_dir(f.id, "fig", "matte")
        md.mkdir(parents=True, exist_ok=True)
        assert not [x for x in cl.get(f"/finals/{f.id}/owed", headers=H_).json()["items"] if x["kind"] == "face"]
        hk = [{"frame": 0, "cx": 400.0, "cy": 250.0, "side": 60.0}]
        lay = cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"head": "keys", "head_keys": hk}, headers=H_).json()["layers"][0]
        assert lay["head"]["mode"] == "keys" and lay["head"]["frames"][5] == [370.0, 220.0, 60.0, 60.0]
        assert [x["kind"] for x in cl.get(f"/finals/{f.id}/owed", headers=H_).json()["items"] if x["layer"] == "fig"] == ["face"]
        cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"head": "none"}, headers=H_)
        assert not [x for x in cl.get(f"/finals/{f.id}/owed", headers=H_).json()["items"] if x["layer"] == "fig"]
        assert cl.put(f"/finals/{f.id}/layers/fig/boxes", json={"head": "keys", "head_keys": []}, headers=H_).status_code == 422
        assert cl.put(f"/finals/{f.id}/layers/plate/boxes", json={"head": "none"}, headers=H_).status_code == 422


async def test_the_face_pass_crops_the_head_boxes_set_by_hand(tmp_path: Path, object_info: dict, monkeypatch):
    """The fake engine: a head box set by hand 10 px right of the tracked one is the box the face pass crops and pastes, and its take
    carries the boxes' signature (a head box changed after it says so)."""
    import test_lifecycle
    from loom2.boxes import heads_from, sig
    from loom2.finals import FinalStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    from test_compositions_ae1 import FAKE
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_with_head(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        animate = next(s for s in registry.animate_specs())
        _fake_weights(tmp_path, [animate, registry.get(registry.segment_model("text"))])
        store = FinalStore(rig.ws)
        keys = [{"frame": 0, "cx": 74.0, "cy": 32.0, "side": 40.0}, {"frame": f.frames - 1, "cx": 86.0, "cy": 32.0, "side": 40.0}]
        store.update_layer(f.id, "fig", head_keys=keys)
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "face", "model_id": animate.id, "step": {"take_id": "take_hk01", "stage": "head", "k": 0}},
                               origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "face", "take": "take_hk01"}))[0]
        await _run_chain(rig, job.id)
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        take = next(t for t in layer.takes if t["id"] == "take_hk01")
        want = heads_from(keys, f.frames, f.size["w"], f.size["h"])
        assert take["boxes"] == [list(want[0]), list(want[-1])] and take["head_sig"] == sig(want)
    finally:
        await rig.close()
