"""D173 (M6, the author's idea; E49c, E50): a crowd plays on a set's face — a loop of the face's own texture with people along it.

- the loop's size follows the stretch's aspect (≈ 0.5 MP on Wan's ×16 grid), within 0.5–2.7× the face's height;
- the start's words make the face an elevation with its people in profile; the loop's hold the camera;
- the tone lock takes a brightness drift out and fades the seam (the last frame is the first);
- the chain on the fake engine: Klein's refine on a document, its landing queues the loop (first = last frame, the default I2V spec), the
  loop lands locked and the face plays it; a ground face or a stretch too long is refused; removed, the crowd is gone.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))


def test_the_size_and_the_words():
    from loom2.place_sets import CROWD_MAX_ASPECT, crowd_prompts, crowd_size
    assert crowd_size(11.2, 4.96) == (1088, 480)                                  # E49's stretch
    w, h = crowd_size(5.0, 5.0)
    assert w == h and w % 16 == 0 and abs(w * h - 520_000) < 60_000
    with pytest.raises(ValueError, match="at most"):
        crowd_size(CROWD_MAX_ASPECT * 5.0 + 1, 5.0)
    with pytest.raises(ValueError, match="at least"):
        crowd_size(1.0, 5.0)
    start, motion = crowd_prompts("facade_right", "Fish market stalls: counters of fish on ice", "")
    assert start.startswith("A flat elevation of fish market stalls: counters of fish on ice, seen square on: people walking left and right")
    assert "nobody facing the camera" in start and motion.endswith("a static locked-off camera.") and "nobody walks toward the camera" in motion
    start, motion = crowd_prompts("wall_back", "", "Shoppers with baskets at the counters.")
    assert start.startswith("A flat elevation of a wall, seen square on: Shoppers with baskets at the counters,") and motion.startswith("Shoppers with baskets")


def test_the_tone_lock_takes_the_drift_out_and_fades_the_seam(tmp_path: Path):
    from loom2.engine.tone import lock_loop
    paths = []
    for k in range(9):                                                            # a wall drifting 1.5 levels a frame, a figure walking below
        a = np.full((40, 64, 3), 100 + 1.5 * k, np.float64)
        a[:, :, 1] += np.linspace(0, 40, 64)[None, :]
        a[28:38, 4 + 5 * k:10 + 5 * k] = 30
        p = tmp_path / f"{k:03d}.png"
        Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(p)
        paths.append(p)
    r = lock_loop(paths, band=0.4, fade=2)
    out = [np.asarray(Image.open(p), dtype=np.float64) for p in paths]
    assert r["seam_before"] > 8 and r["seam_after"] < r["seam_before"] / 2
    assert np.abs(out[-1] - out[0]).max() == 0                                    # the last frame is the first
    assert all(abs(o[:16].mean() - out[0][:16].mean()) < 0.6 for o in out)       # the wall stands still in tone
    assert out[4][30, 4 + 5 * 4 + 2].mean() < 60                                 # the figure is still there


def test_the_route_refuses_the_ground_and_a_stretch_too_long(tmp_path: Path):
    from test_facade_d170 import baked_set
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        pid = baked_set(cl, svc, tmp_path, "street", 120, ("facade_right", "road"))      # 60 × 40 texels at 4 cm: 2.4 × 1.6 m
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/crowd", json={"face": "road", "from_m": 0, "to_m": 2})
        assert r.status_code == 422 and "not on the ground" in r.json()["detail"]
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/crowd", json={"face": "facade_right", "from_m": 0, "to_m": 0.3})
        assert r.status_code == 422 and "at least 0.5 m" in r.json()["detail"]
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/crowd", json={"face": "nope", "from_m": 0, "to_m": 2})
        assert r.status_code == 404
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/crowd", json={"face": "facade_right", "from_m": 0.2, "to_m": 2.4, "words": "shoppers at the counters"})
        assert r.status_code == 200, r.text
        assert r.json()["size"] == list(__import__("loom2.place_sets", fromlist=["crowd_size"]).crowd_size(2.2, 1.6))
        job = svc.queue.jobs[r.json()["job_id"]]
        assert job.recipe["kind"] == "i2i" and job.recipe["strength"] == 0.6 and "shoppers at the counters" in job.recipe["prompt_text"]
        assert job.recipe["match_colour"] is True                                                # E51: the start keeps the face's colours
        assert job.origin.surface == "set_crowd_start" and job.origin.payload["from_m"] == 0.2
        face = next(f for f in cl.get(f"/story/profiles/{pid}").json()["versions"][0]["place_set"]["faces"] if f["id"] == "facade_right")
        assert face["crowd"]["status"] == "making" and face["crowd"]["job_id"] == job.id
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/crowd", json={"face": "facade_right", "from_m": 0, "to_m": 2})
        assert r.status_code == 422 and "being made" in r.json()["detail"]                      # one at a time on a face
        p = cl.delete(f"/story/profiles/{pid}/versions/v1/set/crowd/facade_right").json()
        assert next(f for f in p["versions"][0]["place_set"]["faces"] if f["id"] == "facade_right")["crowd"] is None
        assert svc.queue.jobs[job.id].status == "cancelled"


async def test_the_crowd_runs_from_the_refine_to_the_loop(tmp_path: Path, object_info: dict, monkeypatch):
    """The chain on the fake engine: the refine lands, its document becomes the start (lineage set-crowd ← the texture), the loop runs
    from it back to it on the default I2V spec, lands locked, and the face plays it."""
    import test_lifecycle
    from loom2.groups import GroupStore
    from loom2.models import registry
    from loom2.place_sets import queue_crowd
    from loom2.stages import PlaceSet, SetFace
    from loom2.story import StoryStore
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        store = StoryStore(rig.ws)
        p = store.create_profile("Fish market", "place", GroupStore(rig.ws, rig.catalogue))
        tex = np.full((40, 60, 3), 140, np.uint8)
        tex[:, :, 1] = np.linspace(60, 200, 60).astype(np.uint8)[None, :]
        Image.fromarray(tex).save(tmp_path / "t.png")
        t = rig.catalogue.ingest_file(tmp_path / "t.png", kind="image", move=False, suite="story")
        store.set_place_set(p.id, "v1", PlaceSet(kind="street", sizes={}, faces=[SetFace(id="facade_right", texture_asset_id=t.id, baked_asset_id=t.id, texel_m=0.04,
                                                                                          material="fish market stalls")]))
        rig.queue.load()
        await rig.queue.start()
        first = await queue_crowd(rig.queue, p.id, "v1", "facade_right", 0.0, 2.4)
        j = await rig.wait(first.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        start = j.result["asset_ids"][0]
        assert rig.catalogue.get(start).parents == [t.id]
        loop = rig.queue.jobs[j.result["next_job_id"]]
        assert loop.recipe["kind"] == "i2v" and loop.recipe["start_asset"] == loop.recipe["end_asset"] == start
        assert loop.recipe["model_id"] == registry.default_model("i2v", rig.queue.app.settings.variant) and loop.origin.surface == "set_crowd"
        assert "a static locked-off camera" in loop.recipe["prompt_text"]
        j2 = await rig.wait(loop.id, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        assert any("the crowd's loop: the seam" in x for x in j2.log_tail)
        crowd = next(f for f in store.profile(p.id).version("v1").place_set.faces if f.id == "facade_right").crowd
        assert crowd.status == "done" and crowd.job_id is None and crowd.clip_id == j2.result["clip_id"] and crowd.asset_id == j2.result["asset_ids"][0]
        from loom2.clips import ClipStore
        clips = ClipStore(rig.ws)
        rec = clips.get(crowd.clip_id)
        a = np.asarray(Image.open(clips.frame_path(rec.id, 0)))
        b = np.asarray(Image.open(clips.frame_path(rec.id, rec.frames - 1)))
        assert crowd.frames == rec.frames and np.abs(a.astype(int) - b.astype(int)).max() <= 1      # it loops
    finally:
        await rig.close()
