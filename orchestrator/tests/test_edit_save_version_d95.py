"""D95 (IM1, UX0 #4): Edit's one Save writes the document and a new Catalogue version — but not a second version of a document unchanged
since the last one (`reuse_unchanged`: the flatten returns the last version while the document's write counter `save_seq` has not moved;
painting moves it too, since the editor saves the `.ora` after every change)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState
from loom2.documents import RasterLayer

W, H = 16, 12
OCT = {"Content-Type": "application/octet-stream"}


def _app(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    return create_app(state)


def test_save_reuses_the_version_of_an_unchanged_document_and_makes_a_new_one_after_a_change(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app)
    H_ = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H_)
        d = client.post("/documents", json={"name": "doc", "w": W, "h": H, "background": "#203040"}, headers=H_).json()
        doc_id = d["id"]
        stack = {**d, "layers": [RasterLayer(id="paint", name="paint").model_dump(), *d["layers"]]}
        r = client.put(f"/documents/{doc_id}", json=stack, headers=H_)
        assert r.status_code == 200, r.text

        def paint(value: int) -> None:
            px = np.full((H, W, 4), value, dtype=np.uint8)
            px[..., 3] = 255
            r = client.put(f"/documents/{doc_id}/layers/paint/pixels", params={"w": W, "h": H, "kind": "image"}, content=px.tobytes(), headers={**H_, **OCT})
            assert r.status_code == 200, r.text
            assert client.post(f"/documents/{doc_id}/save", headers=H_).status_code == 200

        def save_version() -> dict:
            r = client.post(f"/documents/{doc_id}/flatten", json={"to_catalogue": True, "reuse_unchanged": True}, headers=H_)
            assert r.status_code == 200, r.text
            return r.json()

        paint(40)
        first = save_version()
        assert first["reused"] is False
        again = save_version()                                    # nothing changed: the same version, no second asset
        assert again["reused"] is True and again["asset"]["id"] == first["asset"]["id"]
        paint(200)                                                # a stroke (pixels only, no stack change) within the same second counts
        second = save_version()
        assert second["reused"] is False and second["asset"]["id"] != first["asset"]["id"]
        plain = client.post(f"/documents/{doc_id}/flatten", json={"to_catalogue": True}, headers=H_).json()
        assert plain["reused"] is False and plain["asset"]["id"] != second["asset"]["id"]   # without the flag: always a new asset (as before)
