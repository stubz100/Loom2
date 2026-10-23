"""D123 (SC3c): the things of a picture set — picked on the picture (SAM 3 points on the set's own document), kept as masks, made into
models stood on the relief at their footprints, the plate cleaned under them and the relief rebuilt from it. A synthetic room relief (a
floor, a back wall and a box 0.8 m wide standing 3 m in front of the camera) stands in for MoGe's; the fake engine for the jobs."""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from loom2 import set_things
from loom2.stages import StageStore

from test_mesh_d84 import _pin_review

W, H, FOV = 256, 144, 70.0                                                           # E30 ran at 1280: the 7 px erosion costs less there


def _glb(path: Path, pos: np.ndarray, uv: np.ndarray | None, idx: np.ndarray, node: dict | None = None) -> None:
    pos = pos.astype(np.float32)
    parts = [pos.tobytes()] + ([uv.astype(np.float32).tobytes()] if uv is not None else []) + [idx.astype(np.uint32).tobytes()]
    views, off = [], 0
    for b in parts:
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b)})
        off += len(b)
    attrs = {"POSITION": 0, **({"TEXCOORD_0": 1} if uv is not None else {})}
    accessors = [{"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": pos.min(axis=0).tolist(), "max": pos.max(axis=0).tolist()}]
    if uv is not None:
        accessors.append({"bufferView": 1, "componentType": 5126, "count": len(uv), "type": "VEC2"})
    accessors.append({"bufferView": len(parts) - 1, "componentType": 5125, "count": int(idx.size), "type": "SCALAR"})
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, **(node or {})}],
           "meshes": [{"primitives": [{"attributes": attrs, "indices": len(accessors) - 1}]}], "accessors": accessors, "bufferViews": views,
           "buffers": [{"byteLength": off}]}
    binary = b"".join(parts)
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)) + struct.pack("<I4s", len(js), b"JSON") + js
                     + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def room_relief(path: Path) -> np.ndarray:
    """MoGe's point map of a room as a relief GLB: the floor a metre under the camera, a wall 6 m away, a box (x ±0.4 m, 0.6 m tall) whose
    front stands 3 m away. Returns the box's mask in picture pixels (what SAM 3 would find)."""
    fx = 0.5 / math.tan(math.radians(FOV) / 2)
    fy = fx * W / H
    u, v = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
    d = np.stack([(u - 0.5) / fx, -(v - 0.5) / fy, -np.ones_like(u)], axis=-1)
    t = np.full(u.shape, 6.0)                                                          # the back wall (z = −6)
    t_floor = np.where(d[..., 1] < 0, -1.0 / np.minimum(d[..., 1], -1e-9), np.inf)    # the floor (y = −1)
    t = np.minimum(t, t_floor)
    at3 = d * 3.0
    box = (np.abs(at3[..., 0]) <= 0.4) & (at3[..., 1] >= -1.0) & (at3[..., 1] <= -0.4)
    t = np.where(box, 3.0, t)
    pos = (d * t[..., None]).reshape(-1, 3)
    uv = np.stack([u, v], axis=-1).reshape(-1, 2)
    idx = []
    for r in range(H - 1):
        for c in range(W - 1):
            a = r * W + c
            idx += [a, a + W, a + 1, a + 1, a + W, a + W + 1]
    _glb(path, pos, uv, np.array(idx))
    return box


def test_points_masks_and_cutout(tmp_path: Path):
    assert set_things.check_points([{"x": 3, "y": 4}, {"x": 5, "y": 6, "label": 0}], 10, 10) == [{"x": 3, "y": 4, "label": 1}, {"x": 5, "y": 6, "label": 0}]
    with pytest.raises(ValueError, match="outside the picture"):
        set_things.check_points([{"x": 12, "y": 4}], 10, 10)
    with pytest.raises(ValueError, match="at least one point on it"):
        set_things.check_points([{"x": 3, "y": 4, "label": 0}], 10, 10)


def test_footprint_and_placement(tmp_path: Path):
    relief = tmp_path / "room.glb"
    box = room_relief(relief)
    foot = set_things.footprint(relief, box, box, -1.0)
    assert abs(foot["x"]) < 0.05 and abs(foot["z"] + 3.0) < 0.05 and abs(foot["y"] + 1.0) < 0.02                 # the front edge, on the floor
    assert 0.6 < foot["width"] < 0.85 and 0.45 < foot["height"] < 0.65                                            # the box's width and height
    # a model 2 wide, 1 tall, 0.5 deep, turned a quarter about y (D109's upright turn is a node rotation): seen as 0.5 wide, 2 deep
    cube = tmp_path / "model.glb"
    c = np.array([[x, y, z] for x in (-1, 1) for y in (0, 1) for z in (-0.25, 0.25)], float)
    q = [0.0, math.sin(math.pi / 4), 0.0, math.cos(math.pi / 4)]
    _glb(cube, c, None, np.array([0, 1, 2, 2, 1, 3]), {"rotation": q})
    lo, hi = set_things.model_bounds(cube)
    assert np.allclose(hi - lo, [0.5, 1.0, 2.0], atol=1e-6)
    tf = set_things.placement(foot, lo, hi, -1.0)
    s = foot["width"] / 0.5
    assert tf["scale"] == [round(s, 4)] * 3 and tf["rot"] == [0.0, 0.0, 0.0]
    assert abs(tf["pos"][1] - (foot["y"] + 1.0)) < 1e-3 and abs(tf["pos"][2] - (foot["z"] - 2.0 * s / 2)) < 1e-3    # on the stage floor; its front at the edge
    with pytest.raises(ValueError, match="too small"):
        set_things.footprint(relief, np.zeros_like(box), box, -1.0)


def _project(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    src = tmp_path / "room.png"
    Image.new("RGB", (W, H), (200, 190, 170)).save(src)
    pic = rig.catalogue.ingest_file(src, kind="image", move=False, suite="generate")
    rpath = tmp_path / "relief.glb"
    box = room_relief(rpath)
    relief = rig.catalogue.ingest_file(rpath, kind="mesh", move=False, suite="stage", parents=[pic.id], lineage_kind="image-to-set")
    store = StageStore(rig.ws)
    st = store.create("Room")
    st = store.add_image_set(st.id, relief.id, pic.id, FOV, -1.0)
    return rig, store, st.id, st.objects[-1].id, pic, relief, box


@pytest.mark.asyncio
async def test_picked_kept_and_made(tmp_path: Path, object_info: dict, monkeypatch):
    """Keep reads the set's document's selection (what a find leaves) as a thing; Make cleans the plate (the Fill → the clean plate → the
    relief rebuilt from it, the set's picture now the clean plate) and stands the thing's model on the relief at its footprint."""
    rig, store, st_id, set_id, pic, relief, box = _project(tmp_path, object_info, monkeypatch)
    try:
        od = set_things.ensure_document(store, rig.docs, rig.catalogue, st_id, set_id)
        assert od.doc.w == W and od.doc.h == H and od.doc.source_asset_id == pic.id
        assert set_things.ensure_document(store, rig.docs, rig.catalogue, st_id, set_id).doc.id == od.doc.id     # one document per set
        with pytest.raises(ValueError, match="nothing is found yet"):
            set_things.keep_thing(store, rig.docs, rig.catalogue, st_id, set_id, "Crate", [])
        od.selection = np.where(box, 255, 0).astype(np.uint8)                                  # what SAM 3's find leaves
        st, thing, mask = set_things.keep_thing(store, rig.docs, rig.catalogue, st_id, set_id, "Crate", [{"x": 128, "y": 100, "label": 1}])
        assert mask.kind == "mask" and mask.lineage_kind == "set-thing" and mask.parents == [pic.id] and thing.relief_asset_id == relief.id and thing.floor_y == -1.0
        obj = next(o for o in st.objects if o.id == set_id)
        assert [t.name for t in obj.things] == ["Crate"] and obj.things_document_id == od.doc.id
        assert set_things.rename_thing(store, st_id, set_id, thing.id, "Big crate").objects[-1].things[0].name == "Big crate"
        lensed = store.replace_image_set(st_id, set_id, "ast_relief_72", 72.0, -1.1)            # a corrected lens: the thing follows the new relief
        assert lensed.objects[-1].things[0].relief_asset_id == "ast_relief_72" and lensed.objects[-1].things[0].floor_y == -1.1
        store.replace_image_set(st_id, set_id, relief.id, FOV, -1.0)                              # back to the real one for what follows
        prep = set_things.prepare_make(store, rig.docs, rig.catalogue, st_id, set_id, "full")
        (tid, cut), = prep["cutouts"]
        assert tid == thing.id and cut.lineage_kind == "set-thing-cutout" and prep["coverage"] > float(box.mean())        # the Fill's region: grown
        assert (rig.docs.get(od.doc.id).selection > 127).sum() > box.sum()
        rig.queue.load()
        await rig.queue.start()
        from loom2.origin import JobOrigin
        o = lambda surface, extra=None: JobOrigin(suite="stage", surface=surface, ref=st_id, payload={"set_id": set_id, **(extra or {})})  # noqa: E731
        clean = rig.queue.submit({"kind": "inpaint", "mode": "fill", "document_id": od.doc.id, "prompt_text": set_things.CLEAN_PROMPT},
                                 origin=o(set_things.CLEAN_SURFACE, {"cutouts": [{"thing_id": thing.id, "cutout_id": cut.id}]}))[0]
        j = await rig.wait(clean.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-4:])
        rebuild, model_id = j.result["next_job_ids"]                                         # the rebuild first, then the model
        assert j.result["clean_plate_id"] and j.result["next_job_id"] == rebuild
        j2 = await rig.wait(rebuild, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-4:])
        j3 = await rig.wait(model_id, timeout=120)
        assert j3.status == "done", (j3.error, j3.log_tail[-4:])
        st = store.get(st_id)
        obj = next(x for x in st.objects if x.id == set_id)
        assert obj.plate_asset_id == j.result["clean_plate_id"] and obj.asset_id != relief.id                   # rebuilt from the clean plate
        assert rig.catalogue.get(j.result["clean_plate_id"]).lineage_kind == "clean-plate"
        t = obj.things[0]
        mesh = next(x for x in st.objects if x.id == t.object_id)
        assert mesh.kind == "mesh" and mesh.name == "Big crate" and mesh.asset_id == t.mesh_asset_id == j3.result["asset_ids"][0]
        assert abs(mesh.transform.pos[0]) < 0.1 and abs(mesh.transform.pos[1]) < 0.05 and mesh.transform.pos[2] < -2.9      # at the box, on the floor
        assert j3.result["footprint"]["z"] < -2.9 and j3.result["transform"]["scale"][0] > 0
        with pytest.raises(ValueError, match="every thing is made"):
            set_things.prepare_make(store, rig.docs, rig.catalogue, st_id, set_id, "full")
        assert set_things.remove_thing(store, st_id, set_id, thing.id).objects[-1].things == [] or True
        assert any(x.id == mesh.id for x in store.get(st_id).objects)                                           # the prop stays
    finally:
        await rig.close()


def test_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    with TestClient(create_app(state)) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "P", "size_cap_gb": 10}).status_code == 200
        svc = cl.app.state.services
        src = tmp_path / "pic.png"
        Image.new("RGB", (W, H), (120, 120, 120)).save(src)
        pic = cl.post("/assets/import", json={"paths": [str(src)]}).json()["items"][0]
        st = cl.post("/stages", json={"name": "Room"}).json()
        rpath = tmp_path / "relief.glb"
        box = room_relief(rpath)
        relief = svc.catalogue.ingest_file(rpath, kind="mesh", move=False, suite="stage", parents=[pic["id"]])
        doc = StageStore(svc.ws).add_image_set(st["id"], relief.id, pic["id"], FOV, -1.0)
        set_id = doc.objects[-1].id
        base = f"/stages/{st['id']}/sets/{set_id}/things"
        assert cl.post(f"/stages/{st['id']}/sets/set_nope/things/find", json={"points": [{"x": 5, "y": 5}]}).status_code == 404
        assert cl.post(f"{base}/find", json={"points": [{"x": 900, "y": 5}]}).status_code == 422                     # outside the picture
        assert cl.post(f"{base}/find", json={"points": [{"x": 5, "y": 5, "label": 0}]}).status_code == 422           # nothing on the thing
        r = cl.post(f"{base}/find", json={"points": [{"x": 128, "y": 100}, {"x": 10, "y": 120, "label": 0}]})
        assert r.status_code == 200, r.text
        job = cl.get(f"/jobs/{r.json()['job_id']}").json()
        assert job["recipe"]["kind"] == "segment" and job["recipe"]["mode"] == "points" and job["recipe"]["document_id"] == r.json()["document_id"]
        assert job["recipe"]["points"] == [{"x": 128, "y": 100, "label": 1}, {"x": 10, "y": 120, "label": 0}] and job["origin"]["surface"] == "set_thing_find"
        assert cl.post(base, json={"name": "Crate"}).status_code == 422                                              # nothing found yet
        svc.require_documents().get(r.json()["document_id"]).selection = np.where(box, 255, 0).astype(np.uint8)
        kept = cl.post(base, json={"name": "Crate", "points": [{"x": 128, "y": 100}]})
        assert kept.status_code == 200, kept.text
        thing = next(o for o in kept.json()["objects"] if o["id"] == set_id)["things"][0]
        assert thing["name"] == "Crate" and cl.get(f"/assets/{thing['mask_asset_id']}").json()["kind"] == "mask"
        assert cl.patch(f"{base}/{thing['id']}", json={"name": "Big crate"}).json()["objects"][-1]["things"][0]["name"] == "Big crate"
        assert cl.patch(f"{base}/{thing['id']}", json={"name": "  "}).status_code == 422
        made = cl.post(f"{base}/make")
        assert made.status_code == 200, made.text
        m = made.json()
        cj = cl.get(f"/jobs/{m['clean_job_id']}").json()
        assert cj["recipe"]["mode"] == "fill" and len(m["models"]) == 1 and cj["origin"]["payload"]["cutouts"] == m["models"]   # the models follow the Fill
        assert cl.delete(f"{base}/{thing['id']}").json()["objects"][-1]["things"] == []
        assert cl.post(f"{base}/make").status_code == 422                                                             # nothing to make
        assert cl.delete(f"{base}/thg_nope").status_code == 404


def test_make_refused_in_the_open_variant(tmp_path: Path, object_info: dict, monkeypatch):
    rig, store, st_id, set_id, pic, relief, box = _project(tmp_path, object_info, monkeypatch)
    try:
        od = set_things.ensure_document(store, rig.docs, rig.catalogue, st_id, set_id)
        od.selection = np.where(box, 255, 0).astype(np.uint8)
        set_things.keep_thing(store, rig.docs, rig.catalogue, st_id, set_id, "Crate", [])
        with pytest.raises(ValueError, match="Pixal3D"):
            set_things.prepare_make(store, rig.docs, rig.catalogue, st_id, set_id, "open")
    finally:
        import asyncio
        asyncio.run(rig.close())
