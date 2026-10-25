"""proto01_UIcast CW7 (02 §9, 04 §5): a place's built set on any stage, bound to its Cast place; the final shot made on it takes the set as
its plate — method `set` (Stage renders the baked and filled faces along the camera path; no Klein still, no projection), the Klein plate
route refuses it with the reason, the frames Stage stores carry the set's picture as the plate's still. A built set not yet baked, or
hidden, keeps PS5b's projected plate; only a built set binds among the sets."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image


def _png(colour: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (colour, colour, colour)).save(buf, "PNG")
    return buf.getvalue()


def test_a_built_set_is_the_plate(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "kitchen.png"
        src.write_bytes(_png(120))
        pic = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        place = cl.post("/story/profiles", json={"name": "Kitchen", "cls": "place"}, headers=H).json()
        cam = {"pos": [0.3, 1.6, 2.0], "target": [0.1, 1.3, -3.0], "roll": 0.0, "focal_mm": 24.0, "sensor_mm": 36.0}
        ps = {"kind": "room", "sizes": {"width": 5, "depth": 6, "height": 2.8}, "parts": {}, "baked_key": "k",
              "faces": [{"id": "wall_back", "texture_asset_id": pic["id"], "baked_asset_id": pic["id"]}], "sources": [{"asset_id": pic["id"], "camera": cam}]}
        st = cl.post("/stages", json={"name": "Kitchen scene"}, headers=H).json()
        built = {"id": "set_k", "kind": "set", "name": "Kitchen", "preset": "built", "locked": True, "profile_id": place["id"], "place_set": ps}
        r = cl.put(f"/stages/{st['id']}", json={**st, "objects": [built]}, headers=H)
        assert r.status_code == 200, r.text                                                         # a built set binds to its place
        st = r.json()
        bad = cl.put(f"/stages/{st['id']}", json={**st, "objects": [{"id": "set_r", "kind": "set", "name": "Room", "preset": "room", "profile_id": place["id"]}]}, headers=H)
        assert bad.status_code == 422 and "built set" in bad.json()["detail"]                       # a preset room does not
        shas = []
        for c in (10, 20, 30):
            b = _png(c)
            sha = hashlib.sha256(b).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=b, headers=H).status_code == 200
            shas.append(sha)
        layers = [{"id": "plate", "kind": "plate", "name": "Kitchen", "passes": {"depth": shas, "clay": shas}},
                  {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": shas}}]
        body = {"name": "Shot 1", "stage_id": st["id"], "camera_id": st["cameras"][0]["id"], "stage_revision": st["revision"], "range": {"start": 0, "end": 3},
                "rate": 16, "size": {"w": 832, "h": 480}, "frames": 3, "layers": layers}
        r = cl.post("/finals", json=body, headers=H)
        assert r.status_code == 200, r.text
        f = r.json()
        assert {x["id"]: x["method"] for x in f["layers"]} == {"plate": "set", "shadows": "stage"}
        r = cl.post(f"/finals/{f['id']}/plate", json={"prompt_text": "", "refs": []}, headers=H)
        assert r.status_code == 422 and "built set" in r.json()["detail"]                           # no Klein still for it
        r = cl.put(f"/finals/{f['id']}/layers/plate/method", json={"method": "projected"}, headers=H)
        assert r.status_code == 422
        r = cl.put(f"/finals/{f['id']}/layers/plate/frames", json={"frames": shas}, headers=H)
        assert r.status_code == 200, r.text
        plate = next(x for x in r.json()["layers"] if x["id"] == "plate")
        assert plate["status"] == "done" and plate["frames_done"] == 3 and plate["still_asset_id"] == pic["id"]   # the set's picture: its lineage
        # a built set not baked yet: PS5b's projected plate
        doc = cl.get(f"/stages/{st['id']}", headers=H).json()
        doc["objects"] = [{**o, "place_set": {**o["place_set"], "faces": []}} for o in doc["objects"]]
        doc = cl.put(f"/stages/{st['id']}", json=doc, headers=H).json()
        g = cl.post("/finals", json={**body, "stage_revision": doc["revision"]}, headers=H).json()
        assert next(x for x in g["layers"] if x["id"] == "plate")["method"] == "projected"
        # the built set gone after the final was made: its plate cannot be the set
        doc["objects"] = []
        cl.put(f"/stages/{st['id']}", json=doc, headers=H)
        r = cl.put(f"/finals/{f['id']}/layers/plate/frames", json={"frames": shas}, headers=H)
        assert r.status_code == 422 and "no built set" in r.json()["detail"]
