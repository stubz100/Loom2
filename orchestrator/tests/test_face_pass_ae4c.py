"""D118 (AE4c): the face pass — the head tracked from the layer's keypoints, rendered by Wan Animate on the head crop in batches (the fake
engine answers the frames RGBA), pasted back under the grown mask, the take's own matte; Lip-sync with a line attached: the S2V talking head
per window first, then the batches with the face video; the composition swaps her matte with the source; the routes' refusals."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from test_compositions_ae1 import FAKE

S, N = 128, 13                                     # 13 frames: two Animate batches once BATCH is 9 (the test shrinks it)


def _img(p: Path, value: int, size: int = S, rect: tuple[int, int, int, int] | None = None, inside: int = 0, mode: str = "L") -> Path:
    im = Image.new(mode, (size, size), value)
    if rect:
        im.paste(inside, rect)
    im.save(p)
    return p


def _keypoints(n: int) -> list:
    """COCO-18 keypoints of a small figure whose head sits at (64, 30) and drifts right one pixel a frame: nose 0, neck 1, eyes 14 / 15,
    ears 16 / 17; the rest below (the hips at 8 / 11, the ankles at 10 / 13 — place_reference's needs)."""
    out = []
    for i in range(n):
        x = 64 + i
        k = [[x, 30, 1], [x, 44, 1], [x - 8, 46, 1], [x - 10, 60, 1], [x - 11, 74, 1], [x + 8, 46, 1], [x + 10, 60, 1], [x + 11, 74, 1],
             [x - 5, 76, 1], [x - 5, 96, 1], [x - 5, 116, 1], [x + 5, 76, 1], [x + 5, 96, 1], [x + 5, 116, 1],
             [x - 3, 28, 1], [x + 3, 28, 1], [x - 6, 30, 1], [x + 6, 30, 1]]
        out.append(k)
    return out


def _final_with_head(ws, stage_id: str, camera_id: str, tmp: Path, n: int = N):
    """A final like test_compositions_ae1's, n frames: the figure's frames carry a bright head disc at the keypoints' head, her matte covers
    it, her keypoints are on the record (the face pass tracks the head from them); assembled, so the composition's footage exists."""
    from loom2 import final_assembly
    from loom2.finals import FinalStore
    from loom2.fsio import atomic_write_json
    tmp.mkdir(parents=True, exist_ok=True)
    grey = _img(tmp / "grey.png", 128, mode="RGB")
    bare_d = _img(tmp / "bare_d.png", 100)
    fig_d = _img(tmp / "fig_d.png", 100, rect=(40, 20, 90, 120), inside=180)
    box_d = _img(tmp / "box_d.png", 100, rect=(10, 70, 40, 110), inside=140)
    shade = _img(tmp / "shade.png", 64, mode="RGB")
    data = {"name": "Shot", "stage_id": stage_id, "camera_id": camera_id, "stage_revision": 0, "range": {"start": 0, "end": n}, "rate": 16,
            "size": {"w": S, "h": S}, "frames": n,
            "layers": [{"id": "plate", "kind": "plate", "name": "Room", "method": "projected"},
                       {"id": "box", "kind": "prop", "name": "Box", "object_id": "box", "method": "rendered"},
                       {"id": "fig", "kind": "figure", "name": "Mara", "object_id": "fig_1", "method": "move"},
                       {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
    store = FinalStore(ws)
    kps = _keypoints(n)
    f = store.create(data, {"plate": {"depth": [bare_d] * n, "clay": [grey] * n}, "box": {"beauty": [grey] * n, "depth": [box_d] * n},
                            "fig": {"pose": [grey] * n, "depth": [fig_d] * n}, "shadows": {"clay": [shade] * n}}, {"fig": kps})
    store.set_frames(f.id, "plate", [grey] * n)
    frames, mattes = [], []
    for i in range(n):
        x = 64 + i
        im = Image.new("RGB", (S, S), (90, 90, 90))
        im.paste((230, 200, 170), (x - 9, 21, x + 9, 39))                                     # her head
        im.paste((60, 60, 160), (x - 12, 40, x + 12, 118))                                    # her body
        frames.append(im)
        im.save(tmp / f"fig_{i:04d}.png")
        m = Image.new("L", (S, S), 0)
        m.paste(255, (x - 9, 21, x + 9, 39))
        m.paste(255, (x - 12, 40, x + 12, 118))
        m.save(tmp / f"matte_{i:04d}.png")
        mattes.append(tmp / f"matte_{i:04d}.png")
    store.set_frames(f.id, "fig", [tmp / f"fig_{i:04d}.png" for i in range(n)])
    md = store.pass_dir(f.id, "fig", "matte")
    md.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (md / f"{i:04d}.png").write_bytes(mattes[i].read_bytes())
    atomic_write_json(store.folder(f.id) / "fig" / "keypoints.json", {"schema_version": 1, "frames": kps})
    stats = final_assembly.assemble_frames(store, store.get(f.id), tmp / "assembled", None, store.folder(f.id) / "comp")
    return store.set_result(f.id, "clip_fake", stats), stats


def _fake_weights(tmp_path: Path, specs: list) -> None:
    from loom2.roster import ROSTER_BY_ID
    for rid in dict.fromkeys(r for s in specs if s is not None for r in s.weights()):
        e = ROSTER_BY_ID[rid]
        p = tmp_path / "models" / e.folder / e.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)


async def _run_chain(rig, job_id: str, timeout: float = 120.0) -> list:
    """The jobs of a chained pass, each waited for; the list of the finished records."""
    out = []
    while job_id:
        j = await rig.wait(job_id, timeout=timeout)
        assert j.status == "done", (j.error, j.log_tail[-6:])
        out.append(j)
        job_id = j.result.get("next_job_id")
    return out


def test_head_boxes_and_windows():
    from loom2.heads import CROP, head_boxes, paste_head, windows
    boxes = head_boxes(_keypoints(N), N, S, S)
    assert len(boxes) == N and all(b[2] >= 48 for b in boxes) and all(0 <= b[0] and b[0] + b[2] <= S and 0 <= b[1] and b[1] + b[2] <= S for b in boxes)
    assert boxes[0][0] < boxes[-1][0]                                                     # the box follows the head to the right
    # the paste: a red head RGBA at the crop size pasted onto a grey frame — red inside the box, grey outside, the mask covers the old silhouette
    base = np.full((S, S, 3), 90, dtype=np.uint8)
    head = Image.new("RGBA", (CROP, CROP), (0, 0, 0, 0))
    head.paste((255, 0, 0, 255), (CROP // 4, CROP // 4, 3 * CROP // 4, 3 * CROP // 4))
    old = np.zeros((boxes[0][2], boxes[0][2]), dtype=np.float32)
    out, p, alpha = paste_head(base, head, boxes[0], old)
    x0, y0, s = boxes[0]
    assert out[y0 + s // 2, x0 + s // 2].tolist() == [255, 0, 0] and out[0, 0].tolist() == [90, 90, 90] and out[S - 1, S - 1].tolist() == [90, 90, 90]
    assert p.shape == (s, s) and 0.99 < p[s // 2, s // 2] <= 1.0 and p[0, 0] < 0.05 and alpha[s // 2, s // 2] > 0.99
    # the windows: a line over frames 1–9 at 16 fps → one run of 9 frames (4n + 1) from frame 1; a long line cut at 77
    w = windows([{"in": 0.0625, "out": 0.5625, "start": 0.0625, "path": "x.wav", "layer": 7, "text": "Hello"}], 16, N)
    assert w == [{"k": 0, "f0": 1, "f1": 10, "frames": 9, "file_t0": 0.0, "path": "x.wav", "layer": 7, "text": "Hello", "asset_id": None}]
    w = windows([{"in": 0.0, "out": 10.0, "start": -0.5}], 16, 160)
    assert [x["frames"] for x in w] == [77, 77, 9] and [x["f0"] for x in w] == [0, 77, 154] and w[1]["file_t0"] == 77 / 16 + 0.5
    assert windows([{"in": 5.0, "out": 6.0, "start": 5.0}], 16, 13) == []                   # a line after the shot's end: no window


async def test_face_pass_chain(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from loom2 import finals as finals_mod
    from loom2.compositions import CompositionStore
    from loom2.effectcraft import EffectCraft
    from loom2.finals import FinalStore
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.stages import StageStore
    monkeypatch.setattr(finals_mod, "BATCH", 9)                                             # two batches for 13 frames: 9, then 9 from offset 9 carrying 5
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}})
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_with_head(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        ec, cs = EffectCraft(rig.app), CompositionStore(rig.ws)
        cs.make(f, ec)
        animate = next(s for s in registry.animate_specs())
        s2v = next(s for s in registry.lipsync_specs())
        _fake_weights(tmp_path, [animate, s2v, registry.get(registry.segment_model("text"))])
        rig.queue.load()
        await rig.queue.start()
        store = FinalStore(rig.ws)
        # the Face pass: head 0 → head 1 → the take
        take_id = "take_face0001"
        job = rig.queue.submit({"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "face", "model_id": animate.id, "step": {"take_id": take_id, "stage": "head", "k": 0}},
                               origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "face", "take": take_id}))[0]
        jobs = await _run_chain(rig, job.id)
        assert len(jobs) == 2
        c0, c1 = jobs[0].result["compiled"], jobs[1].result["compiled"]
        assert (c0["stage"], c0["k"], c0["of"], c0["frames"], c0["offset"], c0["carry"], c0["face"]) == ("head", 0, 2, 9, 0, 0, False)
        assert (c1["stage"], c1["k"], c1["frames"], c1["offset"], c1["carry"]) == ("head", 1, 9, 9, 5)
        assert c0["width"] == c0["height"] == 512 and jobs[1].result["take_id"] == take_id
        f2 = store.get(f.id)
        lay = next(x for x in f2.layers if x.id == "fig")
        assert lay.source == take_id and lay.takes[-1]["preset"] == "face" and lay.takes[-1]["head"] is True and lay.takes[-1]["matte"] is True and lay.takes[-1]["lines"] == []
        d = store.pass_dir(f.id, "fig", f"passes/{take_id}")
        assert len(list(d.glob("*.png"))) == N and Image.open(d / "0000.png").size == (S, S)
        assert len(list((d / "head").glob("*.png"))) == N and Image.open(d / "head" / "0000.png").mode == "RGBA" and Image.open(d / "head" / "0000.png").size == (512, 512)
        assert len(list((d / "matte").glob("*.png"))) == N and len(list((d / "matte_comp").glob("*.png"))) == N and not (d / "work").exists()
        assert store.frames_dir(f.id, "fig") == d and store.matte_dir(f.id, "fig") == d / "matte"
        # the paste: the fake's head (its colour, opaque) fills the box; outside the box the frame is as performed
        plan_boxes = lay.takes[-1]["boxes"]
        x0, y0, s_ = plan_boxes[0]
        base = np.asarray(Image.open(store.pass_dir(f.id, "fig", "frames") / "0000.png").convert("RGB"))
        out = np.asarray(Image.open(d / "0000.png").convert("RGB"))
        assert not np.array_equal(out[y0 + s_ // 2, x0 + s_ // 2], base[y0 + s_ // 2, x0 + s_ // 2]) and np.array_equal(out[S - 1, 0], base[S - 1, 0])
        m_new = np.asarray(Image.open(d / "matte" / "0000.png").convert("L"))
        assert m_new[y0 + s_ // 2, x0 + s_ // 2] == 255 and m_new[S - 1, 0] == 0                # her matte follows the new head (opaque in the fake)
        # the composition follows on sync: her footage and her matte's point at the take
        c = cs.sync_sources(f2, ec)
        assert c.sources["fig"] == take_id and c.stale is False
        pj = json.loads(cs.ecproj(f.id).read_text(encoding="utf-8"))
        paths = [str(it.get("path") or (it.get("kind") or {}).get("path") or "").replace("\\", "/") for it in pj["items"].values()]
        assert any(f"passes/{take_id}/0000.png" in p for p in paths) and any(f"passes/{take_id}/matte_comp/0000.png" in p for p in paths)
        f3 = store.set_source(f.id, "fig", None)
        c = cs.set_source(f3, ec, "fig", None)
        pj = json.loads(cs.ecproj(f.id).read_text(encoding="utf-8"))
        paths = [str(it.get("path") or (it.get("kind") or {}).get("path") or "").replace("\\", "/") for it in pj["items"].values()]
        assert any("comp/fig_matte/0000.png" in p for p in paths) and not any("matte_comp" in p for p in paths)
        assert store.matte_dir(f.id, "fig").name == "matte" and store.matte_dir(f.id, "fig").parent.name == "fig"
        # Lip-sync: a line attached to her layer → the talking head (one window of 9 frames from frame 1), then the two batches with the face video
        from test_layer_pass_ae4 import _wav
        wav = _wav(tmp_path / "line.wav", seconds=0.5)
        meta = {"final_layer": "fig", "asset_id": "ast_line1", "node_id": None, "index": None, "speaker": None, "text": "Hello there", "duration_s": 0.5}
        c = cs.add_audio(store.get(f.id), ec, wav, meta, 0.0625, "Mara · Hello there")
        ec.stop()
        take2 = "take_lips0001"
        job = rig.queue.submit({"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "lipsync", "model_id": s2v.id, "step": {"take_id": take2, "stage": "face_video", "k": 0}},
                               origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "lipsync", "take": take2}))[0]
        jobs = await _run_chain(rig, job.id)
        assert [(j.result["compiled"]["stage"], j.result["compiled"]["k"]) for j in jobs] == [("face_video", 0), ("head", 0), ("head", 1)]
        from loom2.heads import windows
        wnd = windows([t for t in cs.audio_timing(f, c) if t["final_layer"] == "fig"], 16, N)          # the fake's layer plays to the comp's end: one window from frame 1
        assert len(wnd) == 1 and wnd[0]["f0"] == 1 and wnd[0]["frames"] % 4 == 1 and wnd[0]["frames"] <= N
        assert jobs[0].result["compiled"]["frames"] == wnd[0]["frames"] and jobs[0].result["compiled"]["model_id"] == s2v.id and jobs[0].recipe["model_id"] == s2v.id
        assert jobs[1].result["compiled"]["face"] is True and jobs[1].recipe["model_id"] == animate.id
        lay = next(x for x in store.get(f.id).layers if x.id == "fig")
        assert lay.source == take2 and lay.takes[-1]["preset"] == "lipsync" and lay.takes[-1]["lines"] == [{"layer": c.audio[0].layer, "text": "Hello there", "f0": 1, "f1": wnd[0]["f1"]}]
        assert not (store.pass_dir(f.id, "fig", f"passes/{take2}") / "work").exists()
        # dropped: the take's folder goes with it, the source falls back
        f4 = store.remove_take(f.id, "fig", take2)
        assert next(x for x in f4.layers if x.id == "fig").source is None and not store.pass_dir(f.id, "fig", f"passes/{take2}").exists()
        # an unfinished pass's folder is swept
        (store.pass_dir(f.id, "fig", "passes/take_orphan") / "work").mkdir(parents=True)
        assert store.sweep_unfinished(f.id, "fig") == 1 and not store.pass_dir(f.id, "fig", "passes/take_orphan").exists() and d.exists()
    finally:
        await rig.close()


def test_face_pass_routes(tmp_path: Path):
    """The route: Face on a character layer with keypoints and a matte queues the chain's first step (the Animate spec, a take id in the
    payload); refused on the plate, without keypoints, and Lip-sync without a line on the layer."""
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import FinalStore
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "effectcraft": {"cli": str(FAKE)}})
    app = create_app(state)
    svc = app.state.services
    H = {"X-Loom-Token": svc.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        f, _ = _final_with_head(svc.ws, st["id"], st["cameras"][0]["id"], tmp_path / "src")
        assert cl.post(f"/finals/{f.id}/layers/plate/pass", json={"preset": "face"}, headers=H).status_code == 422
        r = cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "lipsync"}, headers=H)
        assert r.status_code == 422 and "attach a line" in r.json()["detail"]
        r = cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "face"}, headers=H)
        assert r.status_code == 200, r.text
        job = cl.get(f"/jobs/{r.json()['job_id']}", headers=H).json()
        rec = job["recipe"]
        assert rec["preset"] == "face" and rec["step"]["stage"] == "head" and rec["step"]["k"] == 0 and rec["step"]["take_id"].startswith("take_")
        assert job["origin"]["payload"]["take"] == rec["step"]["take_id"] and job["origin"]["payload"]["pass"] == "face"
        FinalStore(svc.ws).update_layer(f.id, "fig", keypoints=False)
        r = cl.post(f"/finals/{f.id}/layers/fig/pass", json={"preset": "face"}, headers=H)
        assert r.status_code == 422 and "keypoints" in r.json()["detail"]


async def test_mouth_by_the_model(tmp_path: Path, object_info: dict, monkeypatch):
    """D118 (AE4d): Lip-sync with the mouth by the model — the head batches, then the lip-sync runner (the fake, in place of LatentSync) on the
    kept heads as a CPU-path job that takes the card, its output back under the heads' silhouettes, the take with the model's mouth."""
    import sys
    import test_lifecycle
    from loom2 import finals as finals_mod
    from loom2.compositions import CompositionStore
    from loom2.config import Settings
    from loom2.effectcraft import EffectCraft
    from loom2.engine.pipeline import plan
    from loom2.finals import FinalStore
    from loom2.lipsync import lipsync_available, nearest
    from loom2.models import registry
    from loom2.origin import JobOrigin
    from loom2.recipes import parse_recipe
    from loom2.stages import StageStore
    from test_layer_pass_ae4 import _wav
    assert nearest(16, 16, 25) == [0, 1, 1, 2, 3, 3, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 12, 12, 13, 13, 14, 15, 15] and len(nearest(81, 16, 25)) == 127
    assert "lipsync-setup" in (lipsync_available(Settings(variant="full", lipsync={"python": str(tmp_path / "nope.exe")})) or "")   # no venv: the setup script is named
    assert "open variant" in (lipsync_available(Settings(variant="open")) or "")
    monkeypatch.setattr(finals_mod, "BATCH", 9)
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        ck = tmp_path / "lipsync" / "checkpoints"
        ck.mkdir(parents=True)
        (ck / "latentsync_unet.pt").write_bytes(b"x")
        rig.app.update_settings({"effectcraft": {"cli": str(FAKE)}, "lipsync": {"python": sys.executable, "run": str(Path(__file__).parent / "fake_lipsync.py"), "checkout": str(ck.parent)}})
        assert lipsync_available(rig.app.settings) is None
        st = StageStore(rig.ws).create("Room")
        f, _ = _final_with_head(rig.ws, st.id, st.cameras[0].id, tmp_path / "src")
        ec, cs = EffectCraft(rig.app), CompositionStore(rig.ws)
        cs.make(f, ec)
        wav = _wav(tmp_path / "line.wav", seconds=0.5)
        meta = {"final_layer": "fig", "asset_id": "ast_line1", "node_id": None, "index": None, "speaker": None, "text": "Hello there", "duration_s": 0.5}
        c = cs.add_audio(f, ec, wav, meta, 0.0625, "Mara · Hello there")
        ec.stop()
        animate = next(s for s in registry.animate_specs())
        _fake_weights(tmp_path, [animate, registry.get(registry.segment_model("text"))])
        rig.queue.load()
        await rig.queue.start()
        store = FinalStore(rig.ws)
        take_id = "take_mouth0001"
        data = {"kind": "layer_pass", "final_id": f.id, "layer_id": "fig", "preset": "lipsync", "mouth": "model", "model_id": animate.id, "step": {"take_id": take_id, "stage": "head", "k": 0}}
        p0 = plan(parse_recipe(data), "full")
        assert p0.engine is True and p0.gpu is False and p0.params["mouth"] == "model"
        pm = plan(parse_recipe({**data, "step": {"take_id": take_id, "stage": "mouth", "k": 0}}), "full")
        assert pm.engine is False and pm.gpu is True and pm.weights == [] and pm.estimate["seconds"] == 120.0
        job = rig.queue.submit(data, origin=JobOrigin(suite="stage", surface="final_layer", ref=f.id, payload={"layer": "fig", "pass": "lipsync", "take": take_id, "mouth": "model"}))[0]
        jobs = await _run_chain(rig, job.id)
        assert [(j.result["compiled"].get("stage") if j.result.get("compiled") else "mouth", j.recipe["step"]["k"]) for j in jobs] == [("head", 0), ("head", 1), ("mouth", 0)]
        mouth = jobs[-1]
        assert mouth.result["take_id"] == take_id and any("mouth by the model" in line for line in mouth.log_tail)
        lay = next(x for x in store.get(f.id).layers if x.id == "fig")
        t = lay.takes[-1]
        assert lay.source == take_id and t["preset"] == "lipsync" and t["mouth"] == "model" and t["mouth_steps"] == 20 and t["mouth_s"] >= 0
        assert t["lines"] == [{"layer": c.audio[0].layer, "text": "Hello there", "f0": 1, "f1": N}]            # the fake's layer plays to the comp's end
        d = store.pass_dir(f.id, "fig", f"passes/{take_id}")
        head = np.asarray(Image.open(d / "head" / "0000.png").convert("RGBA"))
        px = head[int(512 * 0.7), 256]
        assert head.shape == (512, 512, 4) and px[0] > 240 and px[1] < 20 and px[2] < 20 and px[3] == 255     # the fake's red mouth (through h264), the silhouette kept
        assert head[20, 20, 0] < 240 and not (d / "work").exists() and len(list(d.glob("*.png"))) == N
        log = (rig.app.logs_dir / f"lipsync-{mouth.id}.log").read_text(encoding="utf-8")
        assert "syncing head_25.mp4 to lines.wav" in log and "done in" in log
    finally:
        await rig.close()
