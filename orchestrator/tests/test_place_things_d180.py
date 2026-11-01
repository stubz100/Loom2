"""D180 (W60, E56): a part of a built set that moves — picked on the place's set picture, kept as a thing (its mask, its card, where it
stands), and made a 3D model by the app's image → 3D; Clay places either the card or the model as an object of its own.

- where a thing stands: its bottom centre's ray from the set picture's camera meets the floor; its size there; it faces the camera; a thing
  whose bottom is above the horizon stands FAR_M out;
- keep: the set picture's document's selection (what SAM 3's find leaves) becomes the mask, the card (the pixels, the mask as alpha) and the
  thing on the version's set; a model is queued on its cut-out and lands on the thing; a thing removed leaves the list.
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
        job = place_things.model_job(rig.queue, store, rig.catalogue, pid, "v1", t.id)
        assert store.profile(pid).version("v1").place_set.things[0].mesh_job_id == job.id
        with pytest.raises(ValueError, match="being made"):
            place_things.model_job(rig.queue, store, rig.catalogue, pid, "v1", t.id)
        j = await rig.wait(job.id, timeout=120)
        assert j.status == "done", (j.error, j.log_tail[-4:])
        thing = store.profile(pid).version("v1").place_set.things[0]
        assert thing.mesh_asset_id == j.result["asset_ids"][0] and thing.mesh_job_id is None
        assert place_things.remove(store, pid, "v1", t.id).version("v1").place_set.things == []
        with pytest.raises(KeyError):
            place_things.remove(store, pid, "v1", t.id)
    finally:
        await rig.close()
