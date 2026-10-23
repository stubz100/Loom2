"""SC3e (D120): a final made on a stage with a picture set takes that picture as its plate — the plate layer's method is `picture` (Stage
renders the relief textured with the picture along the camera path; no Klein still), the Klein plate route refuses it with the reason, and
the frames Stage stores carry the set's picture as the plate's still (the lineage the assembled shot keeps). A stage without one, or with
its picture set hidden, keeps PS5b's projected plate."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image


def _png(colour: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 36), (colour, colour, colour)).save(buf, "PNG")
    return buf.getvalue()


def test_the_plate_of_a_picture_set_is_its_picture(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.stages import StageStore
    from loom2.workspace import Workspace
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        src = tmp_path / "room.png"
        src.write_bytes(_png(120))
        pic = cl.post("/assets/import", json={"paths": [str(src)]}, headers=H).json()["items"][0]
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        store = StageStore(Workspace.open(tmp_path / "proj"))
        st = store.add_image_set(st["id"], "ast_relief", pic["id"], 70.0, -1.0).model_dump()      # the set (its relief need not exist here)
        shas = []
        for c in (10, 20, 30):
            b = _png(c)
            sha = hashlib.sha256(b).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=b, headers=H).status_code == 200
            shas.append(sha)
        layers = [{"id": "plate", "kind": "plate", "name": "Picture set", "passes": {"depth": shas, "clay": shas}},
                  {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": shas}}]
        body = {"name": "Shot 1", "stage_id": st["id"], "camera_id": st["cameras"][-1]["id"], "stage_revision": st["revision"], "range": {"start": 0, "end": 3},
                "rate": 16, "size": {"w": 832, "h": 480}, "frames": 3, "layers": layers}
        r = cl.post("/finals", json=body, headers=H)
        assert r.status_code == 200, r.text
        f = r.json()
        assert {x["id"]: x["method"] for x in f["layers"]} == {"plate": "picture", "shadows": "stage"}
        r = cl.post(f"/finals/{f['id']}/plate", json={"prompt_text": "", "refs": []}, headers=H)
        assert r.status_code == 422 and "the set's picture" in r.json()["detail"]                    # no Klein still for it
        r = cl.put(f"/finals/{f['id']}/layers/plate/frames", json={"frames": shas}, headers=H)
        assert r.status_code == 200, r.text
        plate = next(x for x in r.json()["layers"] if x["id"] == "plate")
        assert plate["status"] == "done" and plate["frames_done"] == 3 and plate["still_asset_id"] == pic["id"]
        assert cl.get(f"/finals/{f['id']}/layers/plate/frames/2", headers=H).content == _png(30)
        # the set hidden: PS5b's projected plate again
        doc = cl.get(f"/stages/{st['id']}", headers=H).json()
        doc["objects"] = [{**o, "visible": False} if o["kind"] == "set" else o for o in doc["objects"]]
        doc = cl.put(f"/stages/{st['id']}", json=doc, headers=H).json()
        g = cl.post("/finals", json={**body, "stage_revision": doc["revision"]}, headers=H).json()
        assert next(x for x in g["layers"] if x["id"] == "plate")["method"] == "projected"
        # the picture set gone after the final was made: its plate cannot be the picture
        doc["objects"] = [o for o in doc["objects"] if o["kind"] != "set"]
        cl.put(f"/stages/{st['id']}", json=doc, headers=H)
        r = cl.put(f"/finals/{f['id']}/layers/plate/frames", json={"frames": shas}, headers=H)
        assert r.status_code == 422 and "no picture set" in r.json()["detail"]
