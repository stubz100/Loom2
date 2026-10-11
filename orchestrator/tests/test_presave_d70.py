"""D70 (ArtCraft P10) slice 1: what an AI job reads. The editor's stack PUT and layer-pixel PUTs update the server's *open* document;
`queue` / `pipeline.prepare_document` flatten that open document (`DocumentStore.get` serves it from memory), so a job sees an upload
at once — without `POST /save`. The idle pre-save therefore flushes the stack and layers only; the .ora is written by explicit saves,
autosave and close."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.config import AppState


def test_an_ai_job_reads_the_uploaded_layer_without_a_save(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app) as c:
        assert c.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        Image.fromarray(np.full((16, 24, 3), 40, np.uint8)).save(tmp_path / "in.png")
        asset = c.post("/assets/import", json={"paths": [str(tmp_path / "in.png")]}).json()["items"][0]["id"]
        doc = c.post("/documents", json={"from_asset": asset}).json()
        did, lid = doc["id"], doc["layers"][0]["id"]
        docs = app.state.services.documents
        ora = docs.path_for(did)
        before = ora.read_bytes()
        rgba = np.zeros((16, 24, 4), np.uint8)
        rgba[..., 0], rgba[..., 3] = 250, 255                                   # the editor painted the layer red
        r = c.put(f"/documents/{did}/layers/{lid}/pixels", params={"w": 24, "h": 16}, content=rgba.tobytes(),
                  headers={"Content-Type": "application/octet-stream"})
        assert r.status_code == 200, r.text
        stack = c.get(f"/documents/{did}").json()
        assert c.put(f"/documents/{did}", json={**stack, "name": "renamed"}).status_code == 200   # and changed the stack
        od = docs.get(did)                                                       # what prepare_document flattens
        flat = od.flatten(exclude=set())
        assert flat[8, 12, 0] == 250 and flat[8, 12, 1] == 0                     # the upload, without POST /save
        assert od.doc.name == "renamed"
        assert ora.read_bytes() == before                                        # the .ora is untouched until a save
        assert c.post(f"/documents/{did}/save").status_code == 200
        assert ora.read_bytes() != before


def test_a_named_background_colour_is_a_422_not_a_500(tmp_path: Path):
    """Found by the headed `aiclick` mode: POST /documents with background "white" reached the compositor and answered 500."""
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app) as c:
        assert c.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        assert c.post("/documents", json={"name": "x", "w": 64, "h": 64, "background": "white"}).status_code == 422
        assert c.post("/documents", json={"name": "x", "w": 64, "h": 64, "background": "#ffffff"}).status_code == 200
