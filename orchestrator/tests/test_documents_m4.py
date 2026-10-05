"""M4 documents: blend-mode math, masks, groups, adjustments, filters, ORA round trip, store, API."""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import compose
from loom2.api import create_app
from loom2.config import AppState
from loom2.documents import AdjustmentLayer, Document, DocumentStore, FilterLayer, GroupLayer, Mask, OpenDocument, RasterLayer
from loom2.workspace import Workspace


def solid(w: int, h: int, rgba) -> np.ndarray:
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[...] = rgba
    return out


def test_blend_modes_known_values():
    cb = np.array([[[0.5, 0.25, 1.0]]], dtype=np.float32)
    cs = np.array([[[0.5, 0.5, 0.5]]], dtype=np.float32)
    assert np.allclose(compose.blend("multiply", cb, cs)[0, 0], [0.25, 0.125, 0.5])
    assert np.allclose(compose.blend("screen", cb, cs)[0, 0], [0.75, 0.625, 1.0])
    assert np.allclose(compose.blend("difference", cb, cs)[0, 0], [0.0, 0.25, 0.5])
    assert np.allclose(compose.blend("linear-dodge", cb, cs)[0, 0], [1.0, 0.75, 1.0])
    assert np.allclose(compose.blend("overlay", cb, cs)[0, 0], [0.5, 0.25, 1.0])            # overlay at cs = 0.5 is identity
    assert np.allclose(compose.blend("hard-light", cb, cs)[0, 0], [0.5, 0.25, 1.0])         # hard-light at cs = 0.5 multiplies by 1: the backdrop
    assert np.allclose(compose.blend("luminosity", cb, cb)[0, 0], cb[0, 0], atol=1e-5)
    assert np.allclose(compose.blend("color", cb, cb)[0, 0], cb[0, 0], atol=1e-5)
    for mode in compose.all_blend_modes():
        out = compose.blend(mode, cb, cs)
        assert out.shape == (1, 1, 3) and np.all(out >= 0) and np.all(out <= 1), mode
    with pytest.raises(ValueError):
        compose.blend("nope", cb, cs)


def test_composite_alpha_rules():
    dst = np.array([[[1.0, 0.0, 0.0, 1.0]]], dtype=np.float32)          # opaque red
    src = np.array([[[0.0, 0.0, 1.0, 0.5]]], dtype=np.float32)          # half-alpha blue
    out = compose.composite(dst, src, "normal")
    assert np.allclose(out[0, 0], [0.5, 0.0, 0.5, 1.0])
    out = compose.composite(dst, src, "normal", alpha=0.5)             # opacity halves the source alpha
    assert np.allclose(out[0, 0], [0.75, 0.0, 0.25, 1.0])
    clear = np.zeros((1, 1, 4), dtype=np.float32)
    out = compose.composite(clear, src, "multiply")                     # over transparent: the source shows unblended
    assert np.allclose(out[0, 0], [0.0, 0.0, 1.0, 0.5])


def test_renderer_groups_masks_clip_adjustments_filters():
    w, h = 8, 8
    bg = RasterLayer(id="bg", name="bg")
    top = RasterLayer(id="top", name="top", opacity=0.5, blend="multiply", mask=Mask())
    adj = AdjustmentLayer(id="adj", type="invert")
    clipped = RasterLayer(id="clip", name="clip", clip=True)
    blur = FilterLayer(id="blur", type="gaussian_blur", params={"radius": 1.0})
    pixels = {"bg": solid(w, h, (200, 100, 50, 255)), "top": solid(w, h, (128, 128, 128, 255)), "clip": solid(w, h, (0, 0, 255, 255))}
    mask = np.zeros((h, w), dtype=np.uint8); mask[:, :4] = 255                          # top layer only on the left half
    r = compose.Renderer(w, h, pixels, {"top": mask})
    out = r.flatten_u8([n.model_dump() for n in [top, bg]])
    assert tuple(out[0, 6]) == (200, 100, 50, 255)                                        # right half: untouched bg
    assert out[0, 1][0] < 200 and out[0, 1][3] == 255                                     # left half: multiplied at 50 %
    # invert adjustment on top of bg
    out = r.flatten_u8([n.model_dump() for n in [adj, bg]])
    assert tuple(out[0, 0]) == (55, 155, 205, 255)
    # clip: the blue layer clipped to a half-transparent base shows only where the base has alpha
    half = solid(w, h, (0, 0, 0, 0)); half[:, :4] = (255, 255, 255, 255)
    r2 = compose.Renderer(w, h, {"base": half, "clip": pixels["clip"]})
    out = r2.flatten_u8([clipped.model_dump(), RasterLayer(id="base").model_dump()])
    assert tuple(out[0, 1]) == (0, 0, 255, 255) and out[0, 6][3] == 0
    # isolated group with opacity composites as one
    grp = GroupLayer(id="g", opacity=0.5, passthrough=False, children=[RasterLayer(id="a"), RasterLayer(id="b")])
    r3 = compose.Renderer(w, h, {"a": solid(w, h, (255, 255, 255, 255)), "b": solid(w, h, (0, 0, 0, 255)), "bg": pixels["bg"]})
    out = r3.flatten_u8([grp.model_dump(), bg.model_dump()])
    assert np.abs(out[0, 0].astype(int) - np.array([228, 178, 153, 255])).max() <= 1       # (bg + white) / 2, half-to-even rounding
    # gaussian blur keeps a flat image flat and spreads an edge
    edge = solid(w, h, (0, 0, 0, 255)); edge[:, 4:] = (255, 255, 255, 255)
    r4 = compose.Renderer(w, h, {"e": edge})
    out = r4.flatten_u8([blur.model_dump(), RasterLayer(id="e").model_dump()])
    assert 0 < out[0, 3][0] < 255 and 0 < out[0, 4][0] < 255 and out[0, 0][0] == 0 and out[0, 7][0] == 255
    # every adjustment and filter runs on a small image without error
    img = np.random.default_rng(1).integers(0, 256, (h, w, 4), dtype=np.uint8); img[..., 3] = 255
    r5 = compose.Renderer(w, h, {"i": img})
    for t in ("levels", "curves", "hue_saturation", "color_balance", "brightness_contrast", "exposure", "black_white", "invert"):
        params = {"curves": {"rgb": [[0, 0], [128, 160], [255, 255]]}, "levels": {"in_black": 10, "in_white": 240, "gamma": 1.2}, "hue_saturation": {"hue": 30, "saturation": 20}}.get(t, {})
        out = r5.flatten_u8([AdjustmentLayer(type=t, params=params).model_dump(), RasterLayer(id="i").model_dump()])
        assert out.shape == (h, w, 4) and out[..., 3].min() == 255, t
    for t in ("gaussian_blur", "sharpen", "noise", "high_pass"):
        out = r5.flatten_u8([FilterLayer(type=t).model_dump(), RasterLayer(id="i").model_dump()])
        assert out.shape == (h, w, 4), t
    assert compose.srgb_delta(img, img) == {"mean": 0.0, "p99": 0.0, "max": 0.0}


def test_ora_round_trip(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    store = DocumentStore(ws)
    base = np.random.default_rng(2).integers(0, 256, (12, 16, 4), dtype=np.uint8)
    od = store.create("Test doc", 16, 12, source_asset_id="ast_src", base_pixels=base)
    lid = od.doc.layers[0].id
    paint = RasterLayer(name="paint", blend="screen", opacity=0.7, x=2, y=1, mask=Mask())
    od.doc.layers.insert(0, paint)
    od.set_pixels(paint.id, solid(6, 5, (10, 200, 30, 255)))
    od.set_mask(paint.id, np.full((5, 6), 128, dtype=np.uint8))
    od.doc.layers.insert(0, AdjustmentLayer(name="curves", type="curves", params={"rgb": [[0, 0], [255, 200]]}, mask=None))
    od.selection = np.zeros((12, 16), dtype=np.uint8); od.selection[2:6, 3:9] = 255
    path = od.save()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert names[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED and z.read("mimetype") == b"image/openraster"
        assert "stack.xml" in names and f"data/{lid}.png" in names and f"data/{paint.id}.mask.png" in names and "mergedimage.png" in names and "loom2.json" in names and "data/selection.png" in names
        xml = z.read("stack.xml").decode()
        assert 'composite-op="svg:screen"' in xml and "loom2:adjustment" in xml
    store.close(od.doc.id)
    again = store.get(od.doc.id)
    assert again.doc.name == "Test doc" and [n.kind for n in again.doc.layers] == ["adjustment", "raster", "raster"]
    assert np.array_equal(again.pixels[lid], base) and np.array_equal(again.masks[paint.id], np.full((5, 6), 128, dtype=np.uint8))
    assert again.selection is not None and again.selection[3, 4] == 255 and again.doc.layers[1].x == 2
    assert np.array_equal(again.flatten(), od.flatten())
    listing = store.list()
    assert listing[0]["id"] == od.doc.id and listing[0]["layers"] == 3 and listing[0]["open"]
    # foreign ORA without loom2.json: raster + groups still load
    with zipfile.ZipFile(tmp_path / "foreign.ora", "w") as z:
        z.writestr("mimetype", "image/openraster")
        z.writestr("stack.xml", '<image w="4" h="4"><stack><stack name="G"><layer name="L" src="data/l1.png" x="1" y="0" composite-op="svg:multiply"/></stack></stack></image>')
        buf = io.BytesIO(); Image.fromarray(solid(2, 2, (9, 9, 9, 255)), "RGBA").save(buf, "PNG"); z.writestr("data/l1.png", buf.getvalue())
    f = OpenDocument.load(tmp_path / "foreign.ora")
    assert f.doc.w == 4 and isinstance(f.doc.layers[0], GroupLayer) and f.doc.layers[0].children[0].blend == "multiply" and f.pixels["l1"].shape == (2, 2, 4)
    # stack update keeps pixels for surviving layers, drops the rest
    data = again.doc.model_dump(); data["layers"] = [data["layers"][1]]
    upd = store.update_stack(od.doc.id, data)
    assert set(upd.pixels) == {paint.id} and upd.dirty
    with pytest.raises(Exception):
        store.update_stack(od.doc.id, {**data, "layers": [{"kind": "raster", "id": "x", "blend": "bogus"}]})
    assert store.delete(od.doc.id) and not store.path_for(od.doc.id).exists()


def test_documents_api(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "D", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "src.png"
        Image.fromarray(solid(32, 24, (120, 60, 30, 255)), "RGBA").save(src)
        asset = client.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        # create from the asset: one background layer with its pixels
        d = client.post("/documents", json={"from_asset": asset["id"]}, headers=H).json()
        assert d["w"] == 32 and d["h"] == 24 and len(d["layers"]) == 1 and d["source_asset_id"] == asset["id"]
        lid = d["layers"][0]["id"]
        raw = client.get(f"/documents/{d['id']}/layers/{lid}/pixels", params={"raw": 1})
        assert raw.status_code == 200 and raw.headers["x-loom-width"] == "32" and len(raw.content) == 32 * 24 * 4
        png = client.get(f"/documents/{d['id']}/layers/{lid}/pixels")
        assert png.headers["content-type"] == "image/png"
        # add a layer: stack update + raw pixel upload + mask upload
        new_layer = {"kind": "raster", "id": "lyr_new", "name": "paint", "blend": "screen", "opacity": 0.8, "x": 4, "y": 4, "w": 8, "h": 8}
        d2 = client.put(f"/documents/{d['id']}", json={**d, "layers": [new_layer, *d["layers"]], "name": "Edited"}, headers=H).json()
        assert d2["name"] == "Edited" and d2["layers"][0]["id"] == "lyr_new"
        body = solid(8, 8, (255, 255, 255, 255)).tobytes()
        r = client.put(f"/documents/{d['id']}/layers/lyr_new/pixels", params={"w": 8, "h": 8}, content=body, headers={**H, "Content-Type": "application/octet-stream"})
        assert r.status_code == 200 and r.json()["w"] == 8
        m = np.full((8, 8), 255, dtype=np.uint8); m[:, 4:] = 0
        r = client.put(f"/documents/{d['id']}/layers/lyr_new/pixels", params={"w": 8, "h": 8, "kind": "mask"}, content=m.tobytes(), headers={**H, "Content-Type": "application/octet-stream"})
        assert r.status_code == 200
        saved = client.post(f"/documents/{d['id']}/save", headers=H).json()
        assert saved["saved_at"] and (tmp_path / "proj" / "documents" / f"{d['id']}.ora").is_file()
        assert client.get("/documents").json()["items"][0]["layers"] == 2
        # flatten to the catalogue: new asset with lineage, source marked has_document
        flat = client.post(f"/documents/{d['id']}/flatten", json={"to_catalogue": True}, headers=H).json()
        assert flat["asset"]["parents"] == [asset["id"]] and flat["asset"]["suite"] == "edit" and flat["asset"]["params"]["document_id"] == d["id"]
        assert client.get(f"/assets/{asset['id']}").json()["has_document"] is True
        img = Image.open(io.BytesIO(client.post(f"/documents/{d['id']}/export", json={"format": "png"}, headers=H).content))
        px = np.asarray(img.convert("RGBA"))
        assert px.shape == (24, 32, 4) and tuple(px[0, 0]) == (120, 60, 30, 255) and px[5, 5][0] > 120 and tuple(px[5, 10]) == (120, 60, 30, 255)   # screen only under the mask
        assert client.get(f"/documents/{d['id']}/thumbnail").headers["content-type"] == "image/png"
        assert client.delete(f"/documents/{d['id']}", headers=H).status_code == 200
        assert client.get("/documents").json()["items"] == []
        client.post("/project/close", headers=H)
