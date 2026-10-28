"""D154: a text layer's block rides the document record — a round trip through PUT / GET and the ORA on disk, the flatten reads the pixels
only (the compositor never sees the block), a bad block is refused, the OpenAPI carries it."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState
from loom2.documents import RasterLayer, TextBlock

BLOCK = {"content": "Scene 1\nthe alley", "font": "Courier Prime", "size": 36.0, "colour": "#ffcc00", "align": "center", "leading": 1.3, "tracking": 2.0,
         "weight": "bold", "italic": False, "outline": {"width": 3.0, "colour": "#000000"}, "box": [120, 80]}


def test_the_model_defaults_and_bounds():
    r = RasterLayer()
    assert r.text is None
    t = TextBlock()
    assert (t.font, t.size, t.colour, t.align, t.leading, t.weight, t.italic, t.outline, t.box) == ("Inter", 48.0, "#ffffff", "left", 1.2, "normal", False, None, None)
    assert RasterLayer.model_validate({"text": BLOCK}).text.outline.width == 3.0
    for bad in ({"align": "middle"}, {"size": 0}, {"leading": 9}, {"weight": "light"}):
        try:
            TextBlock.model_validate({**BLOCK, **bad})
        except ValueError:
            continue
        raise AssertionError(f"{bad} accepted")


def test_round_trip_and_flatten(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "D", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "src.png"
        Image.fromarray(np.full((24, 32, 4), (20, 40, 60, 255), dtype=np.uint8), "RGBA").save(src)
        asset = client.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        d = client.post("/documents", json={"from_asset": asset["id"]}, headers=H).json()
        text_layer = {"kind": "raster", "id": "lyr_text", "name": "Scene 1", "x": 4, "y": 2, "w": 8, "h": 6, "text": BLOCK}
        d2 = client.put(f"/documents/{d['id']}", json={**d, "layers": [text_layer, *d["layers"]]}, headers=H).json()
        assert d2["layers"][0]["text"] == BLOCK                                       # the block comes back whole, the defaults filled
        px = np.zeros((6, 8, 4), dtype=np.uint8); px[1:5, 1:7] = (255, 204, 0, 255)      # the "glyphs": what the editor rasterised
        r = client.put(f"/documents/{d['id']}/layers/lyr_text/pixels", params={"w": 8, "h": 6}, content=px.tobytes(), headers={**H, "Content-Type": "application/octet-stream"})
        assert r.status_code == 200
        client.post(f"/documents/{d['id']}/save", headers=H)
        again = client.get(f"/documents/{d['id']}", headers=H).json()
        assert again["layers"][0]["text"]["content"] == "Scene 1\nthe alley" and again["layers"][0]["text"]["box"] == [120, 80]
        flat = client.post(f"/documents/{d['id']}/export", json={"format": "raw"}, headers=H)
        assert flat.status_code == 200
        out = np.frombuffer(flat.content, dtype=np.uint8).reshape(24, 32, 4)
        assert tuple(out[3, 5, :3]) == (255, 204, 0) and tuple(out[0, 0, :3]) == (20, 40, 60)   # the pixels composite; the block changes nothing
        bad = client.put(f"/documents/{d['id']}", json={**again, "layers": [{**text_layer, "text": {**BLOCK, "align": "middle"}}, *again["layers"][1:]]}, headers=H)
        assert bad.status_code in (400, 409, 422)
        # the block survives on disk and the ORA records it
        import zipfile
        ora = tmp_path / "proj" / "documents" / f"{d['id']}.ora"
        with zipfile.ZipFile(ora) as z:
            rec = json.loads(z.read("loom2.json"))
        assert rec["layers"][0]["text"]["font"] == "Courier Prime"
        schema = app.openapi()
        assert "TextBlock" in schema["components"]["schemas"] and "text" in schema["components"]["schemas"]["RasterLayer"]["properties"]
