"""CS3 (proto01_UIcast 06 §2.10, D136 U19): skeleton changes in a shot are deliberate. A final's character layer remembers the body its guide
was drawn with and, per frame, that body's hash (Stage compares them with the stage's bodies now: *the skeleton changed*); its passes are
drawn again by Stage and replace the old ones — the guide video encoded again when the layer was performed, so a re-take from a batch
performs the new guide."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _png(colour: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (64, 48), colour).save(buf, "PNG")
    return buf.getvalue()


def test_a_character_layer_keeps_its_body_and_takes_new_passes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import FinalStore
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        shas = []
        for c in (10, 20, 30, 40, 50, 60):
            b = _png(c)
            sha = hashlib.sha256(b).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=b, headers=H).status_code == 200
            shas.append(sha)
        old, new = shas[:3], shas[3:]
        mara = {"height_m": 1.66, "neck": 1.54, "figure": "female"}
        layers = [{"id": "plate", "kind": "plate", "name": "Room", "passes": {"depth": old, "clay": old}},
                  {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": old}},
                  {"id": "fig_m", "kind": "figure", "name": "Mara", "object_id": "fig_1", "profile_id": "prf_m", "passes": {"pose": old, "depth": old},
                   "keypoints": [[[100, 50, 1]]] * 3, "body": mara, "body_hashes": ["a", "a", "a"]}]
        body = {"name": "Shot 1", "stage_id": st["id"], "camera_id": st["cameras"][0]["id"], "stage_revision": st["revision"], "range": {"start": 0, "end": 3},
                "rate": 16, "size": {"w": 832, "h": 480}, "frames": 3, "layers": layers}
        f = cl.post("/finals", json=body, headers=H).json()
        fig = next(x for x in f["layers"] if x["id"] == "fig_m")
        assert fig["body"] == mara and fig["body_hashes"] == ["a", "a", "a"]
        assert next(x for x in f["layers"] if x["id"] == "plate")["body_hashes"] == []
        # the skeleton changed from the second frame on: the passes drawn again
        put = {"passes": {"pose": new, "depth": new}, "keypoints": [[[110, 50, 1]]] * 3, "body": {**mara, "neck": 1.2}, "body_hashes": ["a", "b", "b"]}
        r = cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json=put, headers=H)
        assert r.status_code == 200, r.text
        fig = next(x for x in r.json()["layers"] if x["id"] == "fig_m")
        assert fig["body"]["neck"] == 1.2 and fig["body_hashes"] == ["a", "b", "b"] and fig["passes"] == {"pose": 3, "depth": 3}
        assert r.json()["revision"] > f["revision"]
        d = tmp_path / "proj" / "finals" / f["id"] / "fig_m"
        assert (d / "pose" / "0002.png").read_bytes() == _png(60) and not (d / "pose.new").exists()
        assert FinalStore(app.state.services.require_project()[0]).keypoints(f["id"], "fig_m")[0] == [[110, 50, 1]]
        assert fig["guide_asset_id"] is None                                                   # never performed: no guide video to redo
        FinalStore(app.state.services.require_project()[0]).update_layer(f["id"], "fig_m", guide_asset_id="ast_old")
        again = cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json=put, headers=H).json()
        g = next(x for x in again["layers"] if x["id"] == "fig_m")["guide_asset_id"]
        assert g and g != "ast_old"                                                             # performed: the guide encoded again from the new pose pass
        a = cl.get(f"/assets/{g}", headers=H).json()
        assert a["kind"] == "video" and a["params"]["pass"] == "pose-sequence"
        # refusals: a pass short of frames, the hashes miscounted, a plate, a layer at work, a blob never uploaded
        assert cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json={**put, "passes": {"pose": new[:2], "depth": new}}, headers=H).status_code == 422
        assert cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json={**put, "body_hashes": ["a"]}, headers=H).status_code == 422
        assert cl.put(f"/finals/{f['id']}/layers/plate/passes", json=put, headers=H).status_code == 422
        assert cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json={**put, "passes": {"pose": ["0" * 64] * 3, "depth": new}}, headers=H).status_code == 422
        FinalStore(app.state.services.require_project()[0]).update_layer(f["id"], "fig_m", status="running")
        assert cl.put(f"/finals/{f['id']}/layers/fig_m/passes", json=put, headers=H).status_code == 409
        assert (d / "pose" / "0000.png").read_bytes() == _png(40)                              # the refused ones left the passes as they were
