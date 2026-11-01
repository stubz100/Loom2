"""D180 (W60, E56): a part of a built set that moves — picked on the place's set picture, kept as a thing (its mask, its card, where it
stands), and made a 3D model by the app's image → 3D; Clay places either the card or the model as an object of its own.

- where a thing stands: its bottom centre's ray from the set picture's camera meets the floor; its size there; it faces the camera; a thing
  whose bottom is above the horizon stands FAR_M out;
- keep: the set picture's document's selection (what SAM 3's find leaves) becomes the mask, the card (the pixels, the mask as alpha) and the
  thing on the version's set; a model is queued on its cut-out and lands on the thing; a thing removed leaves the list;
- the clean: the set picture cleaned under the things (a Fill over their masks grown, its words "Remove the ferry: …", E58) is the set's
  picture once it lands, its things cleaned and the bake due again; that bake keeps each filled face's Fill where it painted (no Fill
  again); a clean that painted the things back is not used; every thing cleaned, *Clean again* takes them all from the picture before
  any clean; a set fitted again keeps the things picked on its picture, stood under the new camera.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_mesh_d84 import _pin_review  # noqa: E402

W, H = 320, 180


def _cam(y: float = 1.6, look_y: float = 1.6):
    from loom2.stages import SourceCamera
    return SourceCamera(pos=[0.0, y, 0.0], target=[0.0, look_y, -10.0], focal_mm=36.0, sensor_mm=36.0)


def test_a_thing_stands_where_the_picture_shows_it():
    from loom2.place_things import FAR_M, ray, stand
    cam = _cam()                                                                            # level, 1.6 m up, a 53° lens
    o, d, per_px = ray(cam, W, H, W / 2, H / 2)
    assert np.allclose(o, [0, 1.6, 0]) and np.allclose(d, [0, 0, -1]) and per_px == pytest.approx(2 * 0.5 / W)
    mask = np.zeros((H, W), bool)
    mask[110:150, 140:180] = True                                                           # below the horizon (row 90), centred
    s = stand(cam, mask)
    _, d_bottom, _ = ray(cam, W, H, 160, 149)
    dist = 1.6 / -d_bottom[1]
    assert s["base"][1] == 0 and s["base"][0] == pytest.approx(0, abs=0.05) and s["base"][2] == pytest.approx(d_bottom[2] * dist, abs=0.01)
    depth = -s["base"][2]
    assert s["width_m"] == pytest.approx(40 * per_px * depth, rel=0.01) and s["height_m"] == pytest.approx(40 * per_px * depth, rel=0.01)
    assert s["yaw_deg"] == pytest.approx(0, abs=0.5)                                       # facing the camera (the camera at +z from it)
    high = np.zeros((H, W), bool)
    high[30:60, 40:70] = True                                                               # above the horizon: the sky, a far thing
    far = stand(cam, high)
    assert far["base"][1] == 0 and math.hypot(far["base"][0], far["base"][2]) == pytest.approx(FAR_M, rel=0.05)
    with pytest.raises(ValueError, match="empty"):
        stand(cam, np.zeros((H, W), bool))


def _place(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from loom2.groups import GroupStore
    from loom2.stages import PlaceSet, SetSource
    from loom2.story import StoryStore
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    src = tmp_path / "pier.png"
    arr = np.zeros((H, W, 3), np.uint8)
    arr[:] = (70, 110, 120)
    arr[110:150, 140:180] = (230, 230, 225)                                                 # the ferry: a white block on the water
    Image.fromarray(arr).save(src)
    pic = rig.catalogue.ingest_file(src, kind="image", move=False, suite="generate")
    store = StoryStore(rig.ws)
    p = store.create_profile("Harbour pier", "place", GroupStore(rig.ws, rig.catalogue))
    store.set_place_set(p.id, "v1", PlaceSet(kind="ground", sources=[SetSource(asset_id=pic.id, camera=_cam())]))
    return rig, store, p.id, pic, arr


@pytest.mark.asyncio
async def test_a_thing_is_kept_cut_out_and_made_a_model(tmp_path: Path, object_info: dict, monkeypatch):
    from loom2 import place_things
    rig, store, pid, pic, arr = _place(tmp_path, object_info, monkeypatch)
    try:
        od = place_things.ensure_document(store, rig.docs, rig.catalogue, pid, "v1")
        assert od.doc.w == W and od.doc.h == H and od.doc.source_asset_id == pic.id
        assert place_things.ensure_document(store, rig.docs, rig.catalogue, pid, "v1").doc.id == od.doc.id   # one document per set
        with pytest.raises(ValueError, match="nothing is found yet"):
            place_things.keep(store, rig.docs, rig.catalogue, pid, "v1", "Ferry", [])
        box = np.zeros((H, W), bool)
        box[110:150, 140:180] = True
        od.selection = np.where(box, 255, 0).astype(np.uint8)                              # what SAM 3's find leaves
        p, t, (mrec, crec) = place_things.keep(store, rig.docs, rig.catalogue, pid, "v1", "Ferry", [{"x": 160, "y": 130, "label": 1}])
        assert mrec.kind == "mask" and mrec.parents == [pic.id] and crec.lineage_kind == "place-thing"
        cardpx = np.asarray(Image.open(rig.catalogue.abs_path(crec)))
        assert cardpx.shape == (40, 40, 4) and (cardpx[..., 3] == 255).all() and (cardpx[..., :3] == (230, 230, 225)).all()   # the ferry alone
        ps = p.version("v1").place_set
        assert [x.name for x in ps.things] == ["Ferry"] and ps.things_document_id == od.doc.id and ps.things[0].base[1] == 0
        rig.queue.load()
        await rig.queue.start()
        job = await place_things.model_job(rig.queue, store, rig.catalogue, pid, "v1", t.id)
        assert store.profile(pid).version("v1").place_set.things[0].mesh_job_id == job.id
        with pytest.raises(ValueError, match="being made"):
            await place_things.model_job(rig.queue, store, rig.catalogue, pid, "v1", t.id)
        j = await rig.wait(job.id, timeout=120)
        assert j.status == "done", (j.error, j.log_tail[-4:])
        thing = store.profile(pid).version("v1").place_set.things[0]
        assert thing.mesh_asset_id == j.result["asset_ids"][0] and thing.mesh_job_id is None
        # the clean: the picture under the ferry filled; it lands as the set's picture, the ferry cleaned, the bake due again
        place_things._put(store, pid, "v1", lambda x: setattr(x, "baked_key", "k"))
        job, prep = await place_things.clean_job(rig.queue, store, rig.docs, rig.catalogue, pid, "v1")
        assert prep["things"] == [t.id] and prep["coverage"] > box.mean() * 1.5                        # grown over its edge
        assert store.profile(pid).version("v1").place_set.clean_job_id == job.id
        with pytest.raises(ValueError, match="being cleaned"):
            await place_things.clean_job(rig.queue, store, rig.docs, rig.catalogue, pid, "v1")
        j = await rig.wait(job.id, timeout=120)
        assert j.status == "done", (j.error, j.log_tail[-4:])
        ps = store.profile(pid).version("v1").place_set
        clean = rig.catalogue.get(ps.sources[0].asset_id)
        assert clean.id != pic.id and clean.lineage_kind == "clean-plate" and clean.parents == [pic.id] and j.result["asset_ids"] == [clean.id]
        assert ps.things[0].cleaned and ps.clean_job_id is None and ps.keep_fills_key == "k" and ps.baked_key is None
        assert rig.queue.jobs[job.id].recipe["prompt_text"].startswith("Remove the ferry: only what was behind it remains")
        assert place_things._picked_on(rig.catalogue, ps, ps.things[0]) == pic.id                      # a model made now is cut from where it was
        # a clean that painted the ferry back is not used: the set keeps its picture, the ferry stays to clean
        from types import SimpleNamespace

        from loom2.origin import JobOrigin
        back = SimpleNamespace(id="job_back", log_tail=[], result={}, origin=JobOrigin(suite="story", surface=place_things.CLEAN_SURFACE, ref=pid,
                                                                                       payload={"version": "v1", "things": [t.id], "picture": clean.id}))
        same = SimpleNamespace(flatten=lambda: np.dstack([arr, np.full((H, W), 255, np.uint8)]))
        assert place_things.clean_landed(rig.queue, back, same) is None and "painted the things back" in back.log_tail[-1]
        assert store.profile(pid).version("v1").place_set.sources[0].asset_id == clean.id
        # every thing cleaned: Clean again — all of them, on a new document of the picture before any clean
        job2, prep2 = await place_things.clean_job(rig.queue, store, rig.docs, rig.catalogue, pid, "v1")
        od2 = rig.docs.get(prep2["document_id"])
        assert prep2["things"] == [t.id] and od2.doc.source_asset_id == pic.id and prep2["document_id"] != od.doc.id
        j2 = await rig.wait(job2.id, timeout=120)
        assert j2.status == "done", (j2.error, j2.log_tail[-4:])
        ps = store.profile(pid).version("v1").place_set
        assert ps.sources[0].asset_id not in (pic.id, clean.id) and ps.things[0].cleaned and ps.keep_fills_key == "k"
        # fitted again: the ferry stays (picked on this picture, cleaned or not), stood under the new camera; on another picture it goes
        from loom2.stages import PlaceSet, SetSource
        again = place_things.restand(rig.catalogue, ps, PlaceSet(kind="ground", sources=[SetSource(asset_id=pic.id, camera=_cam(y=2.4))]))
        assert [x.name for x in again.things] == ["Ferry"] and not again.things[0].cleaned and again.things[0].base[2] != ps.things[0].base[2]
        assert place_things.restand(rig.catalogue, ps, PlaceSet(kind="ground", sources=[SetSource(asset_id=clean.id, camera=_cam())])).things
        Image.fromarray(arr).save(tmp_path / "other.png")
        other = rig.catalogue.ingest_file(tmp_path / "other.png", kind="image", move=False, suite="generate")
        assert place_things.restand(rig.catalogue, ps, PlaceSet(kind="ground", sources=[SetSource(asset_id=other.id, camera=_cam())])).things == []
        assert place_things.remove(store, pid, "v1", t.id).version("v1").place_set.things == []
        with pytest.raises(ValueError, match="pick a thing"):
            await place_things.clean_job(rig.queue, store, rig.docs, rig.catalogue, pid, "v1")
        with pytest.raises(KeyError):
            place_things.remove(store, pid, "v1", t.id)
    finally:
        await rig.close()


def test_a_kept_thing_is_what_was_clicked():
    """D180's rig: SAM 3's ferry mask carried specks over the sky, and the box (so the width) read 2.6× too wide — the thing kept is what is
    connected to the clicks; with no click on the mask, the whole mask."""
    from loom2.place_things import clicked
    m = np.zeros((H, W), bool)
    m[110:150, 140:180] = True                                                              # the ferry
    m[10:12, 300:302] = True                                                                # a speck far off
    kept = clicked(m, [{"x": 160, "y": 130, "label": 1}, {"x": 5, "y": 5, "label": 0}])
    assert kept[110:150, 140:180].all() and not kept[10:12, 300:302].any()
    assert (clicked(m, [{"x": 5, "y": 5, "label": 1}]) == m).all()


def test_a_face_baked_again_keeps_its_fill():
    """The bake after a clean: the new bake where the picture sees well, the Fill where it painted and wherever the bake is unseen."""
    from loom2.place_things import keep_fill
    filled = np.full((4, 8, 3), (10, 20, 30), np.uint8)
    bake = np.full((4, 8, 4), 200, np.uint8)
    bake[..., 3] = 255
    bake[:, :4, 3] = 0                                                                      # the left half unseen
    cov = np.zeros((4, 8, 3), np.uint8)
    cov[:, 4:, 0] = 220                                                                     # the right half seen square on
    cov[0, 7, 1] = 255                                                                      # one coarse texel: the Fill's
    out = keep_fill(filled, bake, cov, "floor", "room")
    assert (out[:, :4] == (10, 20, 30)).all() and (out[1:, 4:] == 200).all() and (out[0, 4:7] == 200).all() and (out[0, 7] == (10, 20, 30)).all()


def test_the_bake_after_a_clean_keeps_the_fills(tmp_path: Path):
    """The route: a filled face baked again for the same set and camera after the clean keeps its Fill over the new bake (a set-fill image
    ← the new bake and the old Fill, in the place's home); a bake for another key does not."""
    from loom2 import place_things
    from loom2.story import StoryStore
    from test_facade_d170 import baked_set
    from test_place_sets_cw6 import _png
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws, cat, _ = svc.require_project()
        pid = baked_set(cl, svc, tmp_path, "room", 220, ("floor",))                         # key "k": the floor's left half unseen
        Image.fromarray(np.full((40, 60, 3), (10, 20, 30), np.uint8)).save(tmp_path / "fill.png")
        fill = cat.ingest_file(tmp_path / "fill.png", kind="image", move=False, suite="story", lineage_kind="set-fill")
        store = StoryStore(ws)
        store.update_face(pid, "v1", "floor", texture_asset_id=fill.id, filled=True)
        place_things._put(store, pid, "v1", lambda x: (setattr(x, "keep_fills_key", x.baked_key), setattr(x, "baked_key", None)))   # as a clean's landing

        def bake(key: str, colour: int) -> dict:
            tex = np.full((40, 60, 4), colour, np.uint8)
            tex[..., 3] = 255
            tex[:, :30, 3] = 0
            cov = np.zeros((40, 60, 3), np.uint8)
            cov[:, 30:, 0] = 220
            shas = []
            for a in (tex, cov):
                sha, data = _png(a)
                assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
                shas.append(sha)
            r = cl.put(f"/story/profiles/{pid}/versions/v1/set/bake", json={"key": key, "faces": [{"id": "floor", "image": shas[0], "coverage": shas[1],
                                                                                                     "texel_m": 0.04, "seen": 0.5, "bad": 0.5}]})
            assert r.status_code == 200, r.text
            return r.json()["versions"][0]["place_set"]
        ps = bake("k", 90)
        floor = ps["faces"][0]
        assert floor["filled"] and floor["texture_asset_id"] != floor["baked_asset_id"] and ps["keep_fills_key"] is None and ps["baked_key"] == "k"
        kept = cat.get(floor["texture_asset_id"])
        assert kept.lineage_kind == "set-fill" and kept.parents == [floor["baked_asset_id"], fill.id]
        px = np.asarray(Image.open(cat.abs_path(kept)).convert("RGB"))
        assert (px[:, :30] == (10, 20, 30)).all() and (px[:, 30:] == 90).all()             # the Fill kept, the new picture where it sees
        gs = svc.require_groups()
        assert gs.groups[gs.parent[("asset", kept.id)]].path.startswith(f"world/place/{pid}")
        ps = bake("k2", 60)                                                                 # no clean before it: a plain bake
        assert not ps["faces"][0]["filled"] and ps["faces"][0]["texture_asset_id"] == ps["faces"][0]["baked_asset_id"]


def test_a_kept_thing_has_its_thin_parts():
    """E57: SAM 3 leaves a ferry's mast out (2–3 px; a click on it adds nothing) — the kept mask takes the thin parts connected to it within
    0.4 of its height; a line not touching it, or beyond that, stays out."""
    from loom2.place_things import thin_parts
    rgb = np.full((H, W, 3), 205, np.uint8)
    rgb[110:150, 140:180] = 240                                                             # the hull and cabin
    rgb[96:110, 159:161] = 90                                                               # the mast, 2 px, standing on it
    rgb[100:102, 150:170] = 90                                                              # its yard
    rgb[60:100, 60:62] = 90                                                                 # a pole elsewhere on the quay
    rgb[150:178, 179:181] = 90                                                              # a rope down to the water, 28 px
    mask = np.zeros((H, W), bool)
    mask[110:150, 140:180] = True
    got = thin_parts(rgb, mask)
    assert got[96:110, 159:161].all() and got[100:102, 150:170].all() and got[110:150, 140:180].all()
    assert not got[60:100, 60:62].any()
    assert got[150:166, 179:181].all() and not got[167:178, 179:181].any()                   # 16 px of it: 0.4 × the 40 px thing


def test_the_clean_names_what_goes():
    """E58: the clean's words are an instruction naming the things (a prompt asking for "the same" place gave the ferry back)."""
    from loom2.place_things import clean_prompt
    assert clean_prompt(["Ferry"]) == ("Remove the ferry: only what was behind it remains — the water, the ground and the background continued, "
                                       "the same light.")
    assert clean_prompt(["Ferry", "Cart"]).startswith("Remove the ferry and the cart: only what was behind them remains")
    assert clean_prompt(["Ferry", "Cart", "Crane"]).startswith("Remove the ferry, the cart and the crane:")
    assert clean_prompt(["Thing 1"]).startswith("Remove the thing: only what was behind it") and clean_prompt(["Thing 1", "Thing 2"]).startswith("Remove the things: only what was behind them")
    assert clean_prompt(["MV Aurora"]).startswith("Remove the MV Aurora:")                    # a name in capitals kept
