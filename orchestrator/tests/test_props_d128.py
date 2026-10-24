"""D128: every prop has a 3D model, in both builds — a prop version's model can be imported as a GLB (no weights involved, so the
`open` variant has one too). The import checks the binary glTF 2.0 header, refuses a character, lands as a mesh in the Catalogue as it
is (the author's orientation and scale) and sets the version's model; the Catalogue's own import takes a .glb as a mesh."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_props_d110 import box_glb  # noqa: E402


def test_import_a_prop_model(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "open"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        glb = tmp_path / "cup.glb"
        box_glb(glb, tilt=(0.0, 0.0, 0.0))
        fake = tmp_path / "cup2.glb"
        fake.write_bytes(b"not a model at all, just text")
        prop = cl.post("/story/profiles", json={"name": "Cup", "cls": "prop"}, headers=H).json()
        who = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}, headers=H).json()
        url = f"/story/profiles/{prop['id']}/versions/{prop['current']}/model"
        r = cl.post(url, headers=H)                                    # no image → 3D in `open`: the answer points to the import
        assert r.status_code == 422
        r = cl.post(url + "/import", json={"path": str(fake)}, headers=H)
        assert r.status_code == 422 and "glTF 2.0" in r.json()["detail"]
        assert cl.post(url + "/import", json={"path": str(tmp_path / "cup.png")}, headers=H).status_code == 422
        r = cl.post(f"/story/profiles/{who['id']}/versions/{who['current']}/model/import", json={"path": str(glb)}, headers=H)
        assert r.status_code == 422 and "only a prop" in r.json()["detail"]
        r = cl.post(url + "/import", json={"path": f'"{glb}"'}, headers=H)            # a path pasted with its quotes
        assert r.status_code == 200, r.text
        v = r.json()["versions"][0]
        assert v["model_asset_id"] and v["model_from"] is None
        mesh = cl.get(f"/assets/{v['model_asset_id']}", headers=H).json()
        assert mesh["kind"] == "mesh" and mesh["params"]["format"] == "glb" and mesh["params"]["imported_from"] == str(glb)
        assert Path(tmp_path / "proj").exists() and glb.exists()                    # copied, not moved
        items = cl.post("/assets/import", json={"paths": [str(glb)]}, headers=H).json()["items"]
        assert len(items) == 1 and items[0]["kind"] == "mesh"
        r = cl.post("/assets/import", json={"paths": [str(fake)]}, headers=H)
        assert r.status_code == 422 or not r.json()["items"]
