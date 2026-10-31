"""D174 (E52, the author's hybrid): walkers on a layer of their own — people cut out of a loop made over a stretch of a vertical face,
only those walking on the ground line at the face's depth, played over the face as a packed clip (colour | mask).

- the filter keeps a person whose feet reach the base and who is no taller than a person at the face's depth, drops one behind a counter
  (stopping high) and a giant, and keeps a kept walker on the next frame while they overlap;
- a matte runs over a final's layer or a clip;
- the routes queue a segment (the walkers' words) and remove it; the chain on the fake engine refines, loops, mattes and packs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _mask(h: int, w: int, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    m = np.zeros((h, w), np.float32)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = 1.0
    return m


def test_the_walkers_filter():
    from loom2.place_sets import walker_masks
    h, w, px_m = 400, 800, 100.0                                              # a 4 m face at 100 px a metre
    walker = (100, 200, 140, 396)                                             # 1.96 m, feet at the base
    behind = (300, 120, 330, 240)                                             # stops at 60 %: behind a counter
    giant = (500, 20, 600, 399)                                               # 3.8 m tall, feet at the base
    out, kept, dropped = walker_masks([_mask(h, w, [walker, behind, giant])], px_m)
    assert (kept, dropped) == (1, 2)
    assert out[0][300, 120] == 1.0 and out[0][200, 315] == 0.0 and out[0][200, 550] == 0.0
    hidden = (102, 200, 142, 330)                                             # the next frame: the same walker, the feet hidden
    out, kept, _ = walker_masks([_mask(h, w, [walker]), _mask(h, w, [hidden])], px_m)
    assert out[1][250, 120] == 1.0                                            # kept: it overlaps the walker of the frame before
    out, _, _ = walker_masks([_mask(h, w, [hidden])], px_m)
    assert out[0].max() == 0.0                                                # alone it stops too high


def test_the_places_and_the_words():
    from loom2.place_sets import walker_places, walker_prompt
    sel = walker_places(752, 672, 5.6, 4.96)                                  # E53's stretch: three places
    cols = (sel.max(axis=0) > 0).astype(int)
    assert int(np.sum(np.diff(cols) == 1)) + int(cols[0]) == 3
    rows = np.nonzero(sel.max(axis=1))[0]
    assert rows.max() == 672 - 5 and abs((rows.max() - rows.min() + 1) / (672 / 4.96) - 1.9) < 0.02
    assert walker_prompt("facade_right", "fish market stalls: counters of fish on ice", "") ==         "a shopper carrying a basket, walking in profile, the whole figure from head to feet, standing on the floor in front of fish market stalls"
    assert walker_prompt("wall_back", "", "Two old men with sticks.").startswith("Two old men with sticks, walking in profile")


def test_a_segment_fades_at_its_edges():
    from loom2.place_sets import edge_fade
    r = edge_fade(752, 5.6)                                                   # 0.3 m of 5.6 m: 40 px each side
    assert r[0] == 0.0 and r[-1] == 0.0 and r[376] == 1.0 and np.count_nonzero(r < 1.0) == 2 * 40


def test_a_matte_runs_over_a_layer_or_a_clip():
    from loom2.recipes import MatteSequence
    assert MatteSequence(clip_id="clp_1", text="person:20").clip_id == "clp_1"
    assert MatteSequence(final_id="fin_1", layer_id="fig_1").final_id == "fin_1"
    with pytest.raises(ValueError, match="a final's layer"):
        MatteSequence()


def test_the_routes_queue_and_remove_a_segment(tmp_path: Path):
    from test_facade_d170 import baked_set
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        pid = baked_set(cl, svc, tmp_path, "street", 120, ("facade_right", "road"))
        assert cl.post(f"/story/profiles/{pid}/versions/v1/set/walkers", json={"face": "road", "from_m": 0, "to_m": 2}).status_code == 422
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/walkers", json={"face": "facade_right", "from_m": 0.2, "to_m": 2.4})
        assert r.status_code == 200, r.text
        job = svc.queue.jobs[r.json()["job_id"]]
        assert job.recipe["kind"] == "inpaint" and job.recipe["prompt_mode"] == "prompt_first"                         # E53: painted into places
        assert job.recipe["prompt_text"].startswith("a shopper carrying a basket, walking in profile, the whole figure from head to feet")
        sel = svc.require_documents().get(job.recipe["document_id"]).selection
        assert sel is not None and sel[-2].max() == 0 and sel[-5].max() == 255 and sel[:4].max() == 0                  # standing on the base (this face is lower than a person)
        layer = job.origin.payload["layer"]
        assert layer.startswith("wlk_") and job.origin.payload["height_m"] == pytest.approx(1.6)
        face = next(f for f in cl.get(f"/story/profiles/{pid}").json()["versions"][0]["place_set"]["faces"] if f["id"] == "facade_right")
        assert face["crowd"] is None and [(w["id"], w["status"], w["job_id"]) for w in face["walkers"]] == [(layer, "making", job.id)]
        r = cl.post(f"/story/profiles/{pid}/versions/v1/set/walkers", json={"face": "facade_right", "from_m": 0, "to_m": 2})
        assert r.status_code == 422 and "being made" in r.json()["detail"]
        assert cl.delete(f"/story/profiles/{pid}/versions/v1/set/walkers/facade_right/nope").status_code == 404
        p = cl.delete(f"/story/profiles/{pid}/versions/v1/set/walkers/facade_right/{layer}").json()
        assert next(f for f in p["versions"][0]["place_set"]["faces"] if f["id"] == "facade_right")["walkers"] == []
        assert svc.queue.jobs[job.id].status == "cancelled"


async def test_the_walkers_run_from_the_refine_to_the_packed_clip(tmp_path: Path, object_info: dict, monkeypatch):
    """The chain on the fake engine: the refine, the loop, SAM 3 over the loop (the fake answers a standing figure), the walkers filtered
    and packed side by side into a clip of their own (lineage set-walkers ← the loop), the segment done."""
    import test_lifecycle
    from loom2.clips import ClipStore
    from loom2.groups import GroupStore
    from loom2.place_sets import queue_crowd
    from loom2.stages import PlaceSet, SetFace
    from loom2.story import StoryStore
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        store = StoryStore(rig.ws)
        p = store.create_profile("Fish market", "place", GroupStore(rig.ws, rig.catalogue))
        Image.fromarray(np.full((40, 60, 3), 140, np.uint8)).save(tmp_path / "t.png")
        t = rig.catalogue.ingest_file(tmp_path / "t.png", kind="image", move=False, suite="story")
        store.set_place_set(p.id, "v1", PlaceSet(kind="street", sizes={}, faces=[SetFace(id="facade_right", texture_asset_id=t.id, baked_asset_id=t.id, texel_m=0.04)]))
        rig.queue.load()
        await rig.queue.start()
        first = await queue_crowd(rig.queue, p.id, "v1", "facade_right", 0.0, 2.4, layer="wlk_test")
        j = await rig.wait(first.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        assert j.recipe["kind"] == "inpaint"
        loop = rig.queue.jobs[j.result["next_job_id"]]
        assert loop.recipe["start_asset"] == loop.recipe["end_asset"] and "their feet on the ground" in loop.recipe["prompt_text"]
        j2 = await rig.wait(loop.id, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        matte = rig.queue.jobs[j2.result["next_job_id"]]
        assert matte.recipe["kind"] == "matte_sequence" and matte.recipe["clip_id"] == j2.result["clip_id"] and matte.recipe["text"] == "person:20"
        j3 = await rig.wait(matte.id, timeout=60)
        assert j3.status == "done", (j3.error, j3.log_tail[-5:])
        seg = next(f for f in store.profile(p.id).version("v1").place_set.faces if f.id == "facade_right").walkers[0]
        assert seg.id == "wlk_test" and seg.status == "done" and seg.kept >= 1 and seg.clip_id == j2.result["clip_id"], seg
        clips = ClipStore(rig.ws)
        loop_rec = clips.get(seg.clip_id)
        packed = next(c for c in clips.list() if c.asset_id == seg.asset_id)
        assert packed.w == 2 * loop_rec.w and packed.h == loop_rec.h and packed.params["walkers_of"] == loop_rec.id
        assert rig.catalogue.get(seg.asset_id).parents == [loop_rec.asset_id]
        right = np.asarray(Image.open(clips.frame_path(packed.id, 0)).convert("L"))[:, loop_rec.w:]
        assert right.max() == 255 and right.min() == 0                          # the mask: the standing figure on black
    finally:
        await rig.close()
