"""SC3 (D120, after E30): a set from an image — the recipe and its MoGe spec, the graph, the lens read back from a relief, the job through
the fake engine landing on a stage as a locked set with the picture's camera, and the route."""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np
import pytest
from loom2.engine import graphs
from loom2.engine.pipeline import placeholder_inputs, plan
from loom2.models import registry
from loom2.recipes import ImageToSet, parse_recipe, warm_group
from loom2.relief import DEFAULT_LENS_DEG, focal_mm_for, lens_of_glb
from loom2.roster import ROSTER_BY_ID
from loom2.stages import StageObject, StageStore

from test_mesh_d84 import _pin_review


def test_recipe_spec_and_weights():
    r = parse_recipe({"kind": "image_to_set", "asset_id": "ast_pic"})
    assert isinstance(r, ImageToSet) and r.model_id == "moge2-vitl" and r.relief == "cut" and r.decimation == 2 and r.lens_deg is None and r.stage_id is None
    assert registry.default_model("set") == "moge2-vitl" and registry.default_model("set", "open") == "moge2-vitl"       # MIT: offered under open too
    assert warm_group(r) == "moge2-vitl" and graphs.recipe_weights(r) == ["moge2-vitl"] and "open" in ROSTER_BY_ID["moge2-vitl"].variants
    with pytest.raises(ValueError):
        parse_recipe({"kind": "image_to_set", "asset_id": "a", "lens_deg": 10})
    with pytest.raises(ValueError):
        parse_recipe({"kind": "image_to_set", "asset_id": "a", "relief": "rubber"})


def test_graph_lens_and_threshold(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    c = graphs.build_set_from_image(ImageToSet(asset_id="a"), roster, "loom2/job_1", "pic.png")
    classes = {n["class_type"] for n in c.graph.values()}
    assert classes == {"LoadImage", "LoadMoGeModel", "MoGeInference", "MoGePointMapToMesh", "SaveGLB", "MoGeRender", "SaveImage"} and c.output_node == "5"
    assert c.graph["3"]["inputs"]["fov_x_degrees"] == 0.0 and c.graph["4"]["inputs"]["discontinuity_threshold"] == 0.04 and c.graph["4"]["inputs"]["texture"] is True
    assert c.graph["2"]["inputs"]["model_name"].endswith(".safetensors") and c.graph["5"]["inputs"]["filename_prefix"] == "loom2/job_1"
    c2 = graphs.build_set_from_image(ImageToSet(asset_id="a", lens_deg=69.5, relief="sheet", decimation=1), roster, "loom2/job_2", "pic.png")
    assert c2.graph["3"]["inputs"]["fov_x_degrees"] == 69.5 and c2.graph["4"]["inputs"]["discontinuity_threshold"] == 0.0 and c2.graph["4"]["inputs"]["decimation"] == 1
    assert c2.summary["relief"] == "sheet" and c2.summary["lens_deg"] == 69.5
    for cls in classes:
        assert cls in object_info, cls                                                                # the fixture knows every node the graph names
    p = plan(ImageToSet(asset_id="a"))
    assert p.kind == "image_to_set" and p.engine and p.needs == ["source"] and p.warm_group == "moge2-vitl" and p.vram_gb == 2.0 and p.estimate["seconds"] == 1.0
    assert placeholder_inputs(ImageToSet(asset_id="a"), object_info)["image"]


def grid_glb(path: Path, fov_x: float, w: int = 32, h: int = 18, depth: float = 4.0, floor_y: float = -0.9) -> None:
    """A relief as MoGePointMapToMesh would write one: a grid of points at one depth seen through a lens of `fov_x`, with the picture's UVs."""
    fx = 0.5 / math.tan(math.radians(fov_x) / 2)                                                     # normalised by the width
    fy = fx * w / h                                                                                   # square pixels
    u, v = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    x = (u - 0.5) / fx * depth
    y = -(v - 0.5) / fy * depth                                                                       # glTF: Y up; v grows downwards
    y = np.maximum(y, floor_y)                                                                        # a floor cuts the lowest rows
    pos = np.stack([x, y, -np.full_like(x, depth)], axis=-1).reshape(-1, 3).astype(np.float32)
    uv = np.stack([u, v], axis=-1).reshape(-1, 2).astype(np.float32)
    idx = []
    for r in range(h - 1):
        for c in range(w - 1):
            a = r * w + c
            idx += [a, a + w, a + 1, a + 1, a + w, a + w + 1]
    idx_b = np.array(idx, np.uint32).tobytes()
    binary = pos.tobytes() + uv.tobytes() + idx_b
    doc = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
           "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "indices": 2}]}],
           "accessors": [{"bufferView": 0, "componentType": 5126, "count": w * h, "type": "VEC3", "min": pos.min(axis=0).tolist(), "max": pos.max(axis=0).tolist()},
                         {"bufferView": 1, "componentType": 5126, "count": w * h, "type": "VEC2"},
                         {"bufferView": 2, "componentType": 5125, "count": len(idx), "type": "SCALAR"}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pos.tobytes())}, {"buffer": 0, "byteOffset": len(pos.tobytes()), "byteLength": len(uv.tobytes())},
                           {"buffer": 0, "byteOffset": len(pos.tobytes()) + len(uv.tobytes()), "byteLength": len(idx_b)}],
           "buffers": [{"byteLength": len(binary)}]}
    js = json.dumps(doc, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary)) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def test_lens_read_back_from_a_relief(tmp_path: Path):
    p = tmp_path / "relief.glb"
    grid_glb(p, fov_x=70.0)
    lens = lens_of_glb(p)
    assert lens is not None and abs(lens["fov_x"] - 70.0) < 0.5 and abs(lens["fov_y"] - 2 * math.degrees(math.atan(math.tan(math.radians(35)) * 18 / 32))) < 0.5
    assert lens["depth_median"] == 4.0 and lens["y_floor"] == -0.9 and lens["vertices"] == 32 * 18 and lens["faces"] == 31 * 17 * 2
    from fake_comfy import minimal_glb
    bare = tmp_path / "bare.glb"
    bare.write_bytes(minimal_glb())
    assert lens_of_glb(bare) is None                                                                   # no UVs: the lens is not read
    assert focal_mm_for(90.0) == 18.0 and focal_mm_for(DEFAULT_LENS_DEG) == 31.2


def test_store_adds_the_set_and_the_picture_camera(tmp_path: Path):
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    store = StageStore(ws)
    st = store.create("Room")
    st2 = store.add_image_set(st.id, "ast_relief", "ast_pic", 69.1, -0.94)
    obj, cam = st2.objects[-1], st2.cameras[-1]
    assert obj.kind == "set" and obj.preset == "image" and obj.asset_id == "ast_relief" and obj.plate_asset_id == "ast_pic" and obj.lens_deg == 69.1 and obj.floor_y == -0.94
    assert obj.locked and obj.plate_camera_id == cam.id and obj.name == "Picture set" and cam.name == "Picture camera"
    assert cam.pos == [0.0, 0.94, 0.0] and cam.target == [0.0, 0.94, -1.0] and cam.focal_mm == focal_mm_for(69.1) and st2.active_camera == cam.id
    assert st2.revision == st.revision + 1
    st3 = store.add_image_set(st.id, "ast_r2", "ast_p2", None, None)                                   # the fallbacks: the default lens, a metre under the camera
    assert st3.objects[-1].name == "Picture set 2" and st3.objects[-1].lens_deg == DEFAULT_LENS_DEG and st3.objects[-1].floor_y == -1.0 and st3.cameras[-1].pos[1] == 1.0
    with pytest.raises(KeyError):
        store.add_image_set("stg_missing", "a", "b", None, None)
    # SC3b: a rebuild in place — the same set takes the new relief, lens and floor; its camera goes back to where the picture was taken
    first = st2.objects[-1]
    cam_id = first.plate_camera_id
    moved = store.get(st.id)
    next(c for c in moved.cameras if c.id == cam_id).pos = [0.4, 1.2, 0.3]                       # the author moved it about
    store.save(moved)
    st4 = store.replace_image_set(st.id, first.id, "ast_relief2", 75.0, -1.21)
    again = next(o for o in st4.objects if o.id == first.id)
    pcam = next(c for c in st4.cameras if c.id == cam_id)
    assert again.asset_id == "ast_relief2" and again.lens_deg == 75.0 and again.floor_y == -1.21 and again.plate_asset_id == "ast_pic"
    assert pcam.pos == [0.0, 1.21, 0.0] and pcam.target == [0.0, 1.21, -1.0] and pcam.focal_mm == focal_mm_for(75.0) and pcam.roll == 0.0
    assert len([o for o in st4.objects if o.preset == "image"]) == 2 and len(st4.cameras) == len(st3.cameras)   # nothing added
    st5 = store.replace_image_set(st.id, first.id, "ast_relief3", None, None)                        # no reading: the set keeps its lens and floor
    assert next(o for o in st5.objects if o.id == first.id).lens_deg == 75.0 and next(o for o in st5.objects if o.id == first.id).floor_y == -1.21
    cur = store.get(st.id)
    cur.objects.append(StageObject(id="box_1", kind="prop", name="Box"))
    store.save(cur)
    with pytest.raises(ValueError, match="not a picture set"):
        store.replace_image_set(st.id, "box_1", "a", None, None)
    with pytest.raises(KeyError):
        store.replace_image_set(st.id, "set_missing", "a", None, None)


async def test_set_job_end_to_end_on_the_fake_engine(tmp_path: Path, object_info: dict, monkeypatch):
    """The route → the job → the fake engine's GLB (no UVs: the default lens) → a mesh asset with lineage image-to-set → the stage's set and camera."""
    import test_lifecycle
    from PIL import Image
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        src = tmp_path / "room.png"
        Image.new("RGB", (96, 54), (200, 190, 170)).save(src)
        pic = rig.catalogue.ingest_file(src, kind="image", move=False, suite="generate")
        st = StageStore(rig.ws).create("Room")
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "image_to_set", "asset_id": pic.id, "stage_id": st.id, "lens_deg": 72.0},
                               origin={"suite": "stage", "surface": "image_set", "ref": st.id})[0]   # type: ignore[arg-type]
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a and a.kind == "mesh" and a.path.endswith(".glb") and a.lineage_kind == "image-to-set" and a.parents == [pic.id] and a.params["format"] == "glb"
        assert a.params["relief"] == {} and j.result["relief"] is None                                 # the fake's triangle has no UVs
        st2 = StageStore(rig.ws).get(st.id)
        assert st2 is not None and j.result["stage_id"] == st.id and j.result["set_id"] == st2.objects[-1].id and j.result["camera_id"] == st2.cameras[-1].id
        obj = st2.objects[-1]
        assert obj.preset == "image" and obj.asset_id == a.id and obj.plate_asset_id == pic.id and obj.lens_deg == 72.0 and obj.floor_y == -1.0 and obj.locked
        assert st2.active_camera == obj.plate_camera_id and st2.cameras[-1].focal_mm == focal_mm_for(72.0)
        # SC3b: the lens corrected — the job rebuilds the same set in place; the first relief stays in the Catalogue
        job2 = rig.queue.submit({"kind": "image_to_set", "asset_id": pic.id, "stage_id": st.id, "lens_deg": 80.0, "replace_set_id": obj.id})[0]
        j2 = await rig.wait(job2.id, timeout=60)
        assert j2.status == "done", (j2.error, j2.log_tail[-5:])
        st3 = StageStore(rig.ws).get(st.id)
        again = next(o for o in st3.objects if o.id == obj.id)
        assert j2.result["set_id"] == obj.id and again.asset_id == j2.result["asset_ids"][0] != a.id and again.lens_deg == 80.0
        assert len(st3.objects) == len(st2.objects) and len(st3.cameras) == len(st2.cameras) and rig.catalogue.get(a.id) is not None
        assert next(c for c in st3.cameras if c.id == obj.plate_camera_id).focal_mm == focal_mm_for(80.0)
    finally:
        await rig.close()


def test_route_queues_the_job_or_refuses(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from PIL import Image
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    with TestClient(create_app(state)) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "P", "size_cap_gb": 10}).status_code == 200
        st = cl.post("/stages", json={"name": "Room"}).json()
        src = tmp_path / "pic.png"
        Image.new("RGB", (64, 36), (120, 120, 120)).save(src)
        pic = cl.post("/assets/import", json={"paths": [str(src)]}).json()["items"][0]
        assert cl.post("/stages/stg_missing/image-set", json={"asset_id": pic["id"]}).status_code == 404
        assert cl.post(f"/stages/{st['id']}/image-set", json={"asset_id": "ast_nope"}).status_code == 422
        assert cl.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": 400}).status_code == 422
        r = cl.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": 65, "relief": "sheet"})
        assert r.status_code == 200, r.text
        j = cl.get(f"/jobs/{r.json()['job_id']}").json()
        assert j["recipe"]["kind"] == "image_to_set" and j["recipe"]["stage_id"] == st["id"] and j["recipe"]["relief"] == "sheet" and j["recipe"]["lens_deg"] == 65
        assert j["origin"]["surface"] == "image_set" and j["origin"]["ref"] == st["id"] and j["recipe"]["replace_set_id"] is None
        # SC3b: a rebuild names a picture set of this stage, and keeps the set's relief kind unless the body says another
        assert cl.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "replace_set_id": "set_nope"}).status_code == 422
        from loom2.stages import StageStore as _Store
        from loom2.workspace import Workspace as _Ws
        store = _Store(_Ws.open(tmp_path / "proj"))
        relief = cl.post("/assets/import", json={"paths": [str(src)]}).json()["items"][0]                 # a stand-in for the relief asset
        doc = store.add_image_set(st["id"], relief["id"], pic["id"], 70.0, -1.0)
        set_id = doc.objects[-1].id
        cat = app_catalogue(cl)                                                                             # the relief's recipe said "sheet"
        rec = cat.get(relief["id"])
        cat._index(rec.model_copy(update={"params": {**rec.params, "recipe": {"relief": "sheet"}}}))
        r2 = cl.post(f"/stages/{st['id']}/image-set", json={"asset_id": pic["id"], "lens_deg": 74, "replace_set_id": set_id})
        assert r2.status_code == 200, r2.text
        j2 = cl.get(f"/jobs/{r2.json()['job_id']}").json()
        assert j2["recipe"]["replace_set_id"] == set_id and j2["recipe"]["relief"] == "sheet" and j2["recipe"]["lens_deg"] == 74


def app_catalogue(cl):
    """The open project's Catalogue behind a TestClient (the app's services)."""
    return cl.app.state.services.catalogue
