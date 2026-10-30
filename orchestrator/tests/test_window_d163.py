"""D163 (E43; W46, W58, W47): a character layer is performed in its own window.

- the window holds the whole figure (every one of its 18 points, in the frame or not) at Wan's portrait size, and a layer is performed in
  it when it gives the figure at least the frame's pixels on every frame — a small figure and one cut by the frame, not a close shot;
- the guide is the pose drawn in the window (passes.ts drawPose on the server: limbs, points, D158's away face, D101's hands and feet);
- the run takes the window's size and places the reference there; a final made before D163 gets its window at its next run;
- the batches stitch into `window/frames`, the matte runs there, and both are pasted back into `frames/` and `matte/` at the final's size;
- the matte is checked against the figure's Stage silhouette; the reference cut-out keeps a head a ground-coloured collar parts (W47).
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from loom2.finals import WINDOW, draw_pose, figure_windows, layer_window, paste_back, to_window  # noqa: E402

W, H = 848, 480


def _figure(cx: float, top: float, tall: float) -> list:
    """A standing figure's 18 points (COCO-18), `tall` from the eyes to the ankles, facing the camera (its right on the image's left)."""
    k = [[0.0, 0.0, 1.0] for _ in range(18)]
    at = lambda i, dx, f: k.__setitem__(i, [cx + dx * tall, top + f * tall, 1.0])  # noqa: E731
    at(0, 0, 0.03); at(14, -0.03, 0.0); at(15, 0.03, 0.0); at(16, -0.06, 0.01); at(17, 0.06, 0.01); at(1, 0, 0.12)
    at(2, -0.12, 0.13); at(5, 0.12, 0.13); at(3, -0.16, 0.3); at(6, 0.16, 0.3); at(4, -0.18, 0.45); at(7, 0.18, 0.45)
    at(8, -0.06, 0.5); at(11, 0.06, 0.5); at(9, -0.06, 0.75); at(12, 0.06, 0.75); at(10, -0.06, 1.0); at(13, 0.06, 1.0)
    for p in k:                                                         # Stage: a point outside the frame is not drawn (but kept)
        p[2] = 1.0 if (0 <= p[0] < W and 0 <= p[1] < H) else 0.0
    return k


def _whole(kps: list, wins: list) -> bool:
    return all(all(p[2] for p in to_window(k, w)) for k, w in zip(kps, wins))


def test_the_window_holds_the_whole_figure_and_is_used_when_it_enlarges_it():
    small = [_figure(400 + i, 240, 44) for i in range(20)]            # W46: Tomas, ~50 px at 18 m
    wins = figure_windows(small, 20)
    assert _whole(small, wins) and min(w[2] for w in wins) > 8 and layer_window(small, 20) == wins
    cut = [_figure(130, 250, 330) for _ in range(20)]                  # W58: Ines, the knees and ankles below the frame
    assert any(not p[2] for p in cut[0])
    wins = figure_windows(cut, 20)
    assert _whole(cut, wins) and layer_window(cut, 20) == wins        # the window reaches outside the frame and holds her whole
    close = [_figure(420, 120, 1400) for _ in range(20)]                # a close shot: the body far taller than the frame
    assert layer_window(close, 20) == [] and layer_window(None, 20) == [] and layer_window([], 20) == []
    walk = [_figure(100 + 30 * i, 200 - 4 * i, 200 - 6 * i) for i in range(20)]   # walking away: smaller, and across the frame
    assert _whole(walk, figure_windows(walk, 20))                      # the smoothing never cuts her


def test_the_guide_is_drawn_as_stage_draws_it():
    k = to_window(_figure(400, 240, 44), figure_windows([_figure(400, 240, 44)], 1)[0])
    img = np.asarray(draw_pose(k, *WINDOW))
    assert img.shape == (WINDOW[1], WINDOW[0], 3)
    nose = k[0]
    assert tuple(img[int(nose[1]), int(nose[0])]) == (255, 0, 0)       # the nose's disc, in COCO-18's first colour
    mid = ((k[8][0] + k[9][0]) / 2, (k[8][1] + k[9][1]) / 2)
    assert img[int(mid[1]), int(mid[0])].sum() > 100                    # a limb drawn between the hip and the knee
    away = [list(p) for p in k]
    away[2][0], away[5][0] = k[5][0], k[2][0]                           # mirrored: her back to the camera
    away[14][0], away[15][0] = k[15][0], k[14][0]
    img2 = np.asarray(draw_pose(away, *WINDOW))
    assert img2[int(nose[1]), int(nose[0])].sum() < 60                  # D158: no nose on a figure facing away
    hand = [[k[4][0] + 3 * i, k[4][1] + 2 * i, 1.0] for i in range(21)]
    img3 = np.asarray(draw_pose(k, *WINDOW, {"feet": [], "left": [], "right": hand}))
    assert tuple(img3[int(hand[10][1]), int(hand[10][0])]) == (0, 0, 255)   # D101: a hand's points in blue


def test_a_take_is_pasted_back_where_its_window_is():
    win = [100.0, 50.0, 4.0]                                             # 120 × 212 frame pixels
    take = Image.new("RGB", WINDOW, (0, 0, 0))
    ImageDraw.Draw(take).rectangle((200, 400, 280, 600), fill=(255, 255, 255))
    out = np.asarray(paste_back(take, win, W, H, (9, 9, 9)))
    ys, xs = np.nonzero(out[..., 0] > 128)
    assert abs(xs.min() - (100 + 200 / 4)) <= 1 and abs(ys.min() - (50 + 400 / 4)) <= 1 and abs(xs.max() - (100 + 280 / 4)) <= 1
    assert tuple(out[5, 5]) == (9, 9, 9)
    edge = np.asarray(paste_back(take, [-60.0, 300.0, 1.2], W, H, 0))   # partly outside the frame: what is outside is dropped
    assert edge.shape == (H, W, 3)


def test_the_cutout_keeps_a_head_parted_by_a_ground_coloured_collar(tmp_path: Path):
    from loom2.finals import cutout
    im = Image.new("RGB", (400, 600), (200, 200, 205))
    d = ImageDraw.Draw(im)
    d.ellipse((170, 40, 230, 110), fill=(40, 30, 25))                   # the dark hair
    d.rectangle((185, 111, 215, 112), fill=(192, 192, 197))             # a collar 2 px tall, ΔE ≈ 3 from the ground
    d.rectangle((140, 113, 260, 520), fill=(190, 40, 40))               # the red coat
    im.save(tmp_path / "ref.png")
    img, alpha, ground = cutout(tmp_path / "ref.png")
    assert img.shape[0] > 450 and alpha[:60].max() > 0.5                # the head is kept above the collar
    assert ground == (200, 200, 205)


def _final(ws, stage, keypoints: dict, n: int = 20, window=None):
    from loom2.finals import FinalStore
    png = ws.temp_dir / "p.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (W, H), (128, 128, 128)).save(png)
    data = {"name": "Shot", "stage_id": stage["id"], "camera_id": stage["cameras"][0]["id"], "stage_revision": 0, "range": {"start": 0, "end": n - 1}, "rate": 16,
            "size": {"w": W, "h": H}, "frames": n,
            "layers": [{"id": "plate", "kind": "plate", "name": "Pier", "method": "projected"}, {"id": "fig", "kind": "figure", "name": "Tomas", "object_id": "fig_1", "method": "move"},
                       {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
    store = FinalStore(ws)
    f = store.create(data, {"plate": {"depth": [png] * n, "clay": [png] * n}, "fig": {"pose": [png] * n, "depth": [png] * n}, "shadows": {"clay": [png] * n}},
                     keypoints, {"fig": [{"feet": [], "left": [], "right": []}] * n})
    if window == "unset":                                               # a final made before D163
        f = store.update_layer(f.id, "fig", window=None)
    return f


def _app(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    return TestClient(app), {"X-Loom-Token": app.state.services.app.token}


def test_a_small_figure_runs_in_its_window_and_a_close_shot_at_the_frame(tmp_path: Path):
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
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

        def run(kps: dict, window=None) -> tuple[dict, dict, object]:
            f = _final(ws, stage, kps, window=window)
            store.update_layer(f.id, "fig", profile_id=p.id)
            r = cl.post(f"/finals/{f.id}/layers/fig/run", json={}, headers=H_)
            assert r.status_code == 200, r.text
            job = next(j for j in cl.get("/jobs", headers=H_).json()["items"] if j["id"] == r.json()["job_id"])
            return r.json(), job, store.get(f.id)

        small = {"fig": [_figure(400, 240, 44)] * 20}
        out, job, f = run(small)
        layer = next(x for x in f.layers if x.id == "fig")
        assert out["window"] and out["window"] > 8 and out["placed"]          # a whole figure placed in its window
        assert (job["recipe"]["width"], job["recipe"]["height"]) == WINDOW and len(layer.window) == 20
        guide = cat.get(layer.guide_asset_id)
        assert (guide.w, guide.h) == WINDOW and len(list(store.pass_dir(f.id, "fig", "window/pose").glob("*.png"))) == 20
        ref = np.asarray(Image.open(cat.abs_path(cat.get(layer.reference_asset_id))))
        assert ref.shape[:2] == (WINDOW[1], WINDOW[0])
        out, job, f = run({"fig": [_figure(420, 120, 1400)] * 20})            # a close shot: at the frame, as before
        assert out["window"] is None and (job["recipe"]["width"], job["recipe"]["height"]) == (W, H)
        assert next(x for x in f.layers if x.id == "fig").window == []
        out, job, f = run(small, window="unset")                               # a final from before D163: decided at its run
        assert out["window"] and next(x for x in f.layers if x.id == "fig").window


async def test_a_windowed_layer_is_matted_in_its_window_and_pasted_back(tmp_path: Path, object_info: dict, monkeypatch):
    """The fake engine: one batch at 480 × 848; the stitch lands in window/frames; SAM 3 answers at the window's size; the finisher pastes the
    take and the matte back into frames/ and matte/ at the final's size, where the window is, and checks the matte."""
    import test_lifecycle
    from loom2.finals import FINAL_LAYER_SURFACE, FinalStore, character_recipe, plan_batches
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore, encode_guide
    from test_finals_d111 import _figure_ref
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Pier")
        n = 20
        f = _final(rig.ws, {"id": st.id, "cameras": [{"id": st.cameras[0].id}]}, {"fig": [_figure(400, 240, 44)] * n}, n=n)
        store = FinalStore(rig.ws)
        layer = next(x for x in f.layers if x.id == "fig")
        assert layer.window
        ref = rig.catalogue.ingest_file(_figure_ref(tmp_path / "ref.png"), kind="image", move=False, suite="stage")
        mp4 = rig.ws.temp_dir / "pose.mp4"
        frame = rig.ws.temp_dir / "g.png"
        Image.new("RGB", WINDOW, (0, 0, 0)).save(frame)
        encode_guide([frame] * n, mp4, 16)
        guide = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", frames=n, fps=16.0, w=WINDOW[0], h=WINDOW[1])
        f = store.update_layer(f.id, "fig", reference_asset_id=ref.id, guide_asset_id=guide.id, seed=3)
        layer = next(x for x in f.layers if x.id == "fig")
        spec = next(s for s in registry.animate_specs())
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit(character_recipe(f, layer, spec.id, "Tomas, moving", plan_batches(n)[0], None),
                               origin=JobOrigin(suite="stage", surface=FINAL_LAYER_SURFACE, ref=f.id, payload={"layer": "fig", "batch": 0, "batches": 1}))[0]
        store.update_layer(f.id, "fig", status="queued", batches=[{"k": 0, "job_id": job.id, "clip_id": None}], job_ids=[job.id])
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        take = sorted(store.pass_dir(f.id, "fig", "window/frames").glob("*.png"))
        assert len(take) == n and Image.open(take[0]).size == WINDOW
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        jm = await rig.wait(layer.job_ids[-1], timeout=60)
        assert jm.status == "done" and jm.recipe["kind"] == "matte_sequence", (jm.error, jm.log_tail[-5:])
        assert any("in its window, pasted back" in line for line in jm.log_tail)
        layer = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert layer.status == "done"
        assert len(list(store.pass_dir(f.id, "fig", "window/matte").glob("*.png"))) == n
        frames, matte = sorted(store.pass_dir(f.id, "fig", "frames").glob("*.png")), sorted(store.pass_dir(f.id, "fig", "matte").glob("*.png"))
        assert len(frames) == n and len(matte) == n and Image.open(frames[0]).size == (W, H) and Image.open(matte[0]).size == (W, H)
        m = np.asarray(Image.open(matte[0]).convert("L")) > 128
        ys, xs = np.nonzero(m)
        x0, y0, s = layer.window[0]                                      # the fake's matte (a box 2/5–3/5 × 1/5–9/10 of the window), where the window is
        assert abs(xs.min() - (x0 + WINDOW[0] * 2 / 5 / s)) <= 2 and abs(ys.max() - (y0 + WINDOW[1] * 9 / 10 / s)) <= 2
        assert m.sum() < 0.05 * W * H                                     # a small figure's matte, not the frame
    finally:
        await rig.close()


def test_the_matte_check_finds_a_matte_that_strays_from_its_figure(tmp_path: Path):
    from loom2.finals import FinalStore, matte_check
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    n = 3
    bare, fig = ws.temp_dir / "bare.png", ws.temp_dir / "fig.png"
    bare.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (W, H), 100).save(bare)
    im = Image.new("L", (W, H), 100)
    im.paste(180, (380, 200, 420, 300))
    im.save(fig)
    store = FinalStore(ws)
    f = store.create({"name": "S", "stage_id": "stg_1", "camera_id": "cam_1", "stage_revision": 0, "range": {"start": 0, "end": 2}, "rate": 16, "size": {"w": W, "h": H}, "frames": n,
                      "layers": [{"id": "plate", "kind": "plate", "name": "P", "method": "projected"}, {"id": "fig", "kind": "figure", "name": "T", "object_id": "o", "method": "move"},
                                 {"id": "shadows", "kind": "shadows", "name": "S", "method": "stage"}]},
                     {"plate": {"depth": [bare] * n, "clay": [bare] * n}, "fig": {"pose": [bare] * n, "depth": [fig] * n}, "shadows": {"clay": [bare] * n}}, {})

    def mattes(boxes: list) -> dict:
        d = store.pass_dir(f.id, "fig", "matte")
        d.mkdir(parents=True, exist_ok=True)
        for i, box in enumerate(boxes):
            m = Image.new("L", (W, H), 0)
            if box:
                m.paste(255, box)
            m.save(d / f"{i:04d}.png")
        return matte_check(store, store.get(f.id), "fig")
    good = mattes([(378, 198, 422, 302)] * n)
    assert good["strays"] == [] and good["cover_min"] >= 0.95 and good["ratio_max"] < 1.3
    bad = mattes([(378, 198, 422, 302), (0, 0, W, H), (500, 50, 600, 150)])    # good · the whole frame (W46) · beside the figure
    assert bad["strays"] == [1, 2] and bad["ratio_max"] > 100 and bad["cover_min"] == 0.0
