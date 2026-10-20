"""D111 (PS5a): the final shot's record — its frames at the shot's rate (F16 resamples, F24 takes each), its layers (one plate, one shadows,
figures and props naming their Stage objects), each layer's passes copied from the uploaded blobs (one blob may stand for many frames),
the routes (make, list, read, a frame, delete) and their refusals."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.finals import frames_at  # noqa: E402


def test_frames_at_the_rate():
    assert frames_at(0, 24, 24) == list(range(25))
    f16 = frames_at(0, 240, 16)
    assert len(f16) == 161 and f16[1] == 1.5 and f16[-1] == 240.0          # D102: 10 s at F16 is 161 frames, every 1.5th Stage frame
    assert frames_at(10, 9, 16) == []


def _png(colour: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("L", (64, 48), colour).save(buf, "PNG")
    return buf.getvalue()


def test_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        shas = []
        for c in (10, 20, 30):
            b = _png(c)
            sha = hashlib.sha256(b).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=b, headers=H).status_code == 200
            shas.append(sha)
        seq = shas                                                               # three frames
        still = [shas[0]] * 3                                                   # a still camera: one blob for every frame
        layers = [{"id": "plate", "kind": "plate", "name": "Room", "passes": {"depth": still, "clay": still}},
                  {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": seq}},
                  {"id": "fig_m", "kind": "figure", "name": "Mara", "object_id": "fig_1", "profile_id": "prf_m", "passes": {"pose": seq, "depth": seq},
                   "keypoints": [[[100, 50, 1]], [[101, 50, 1]], [[102, 50, 1]]]},
                  {"id": "chest", "kind": "prop", "name": "Chest", "object_id": "chest", "passes": {"beauty": seq, "depth": seq}}]
        body = {"name": "Shot 1", "stage_id": st["id"], "camera_id": st["cameras"][0]["id"], "stage_revision": st["revision"], "range": {"start": 0, "end": 3},
                "rate": 16, "size": {"w": 832, "h": 480}, "frames": 3, "layers": layers}
        r = cl.post("/finals", json=body, headers=H)
        assert r.status_code == 200, r.text
        f = r.json()
        assert {x["id"]: x["method"] for x in f["layers"]} == {"plate": "projected", "shadows": "stage", "fig_m": "move", "chest": "rendered"}
        assert all(x["status"] == "passes" for x in f["layers"]) and [x["keypoints"] for x in f["layers"]] == [False, False, True, False]
        assert f["layers"][2]["passes"] == {"pose": 3, "depth": 3}
        d = tmp_path / "proj" / "finals" / f["id"]
        assert sorted(p.name for p in (d / "plate" / "depth").iterdir()) == ["0000.png", "0001.png", "0002.png"]
        assert (d / "fig_m" / "keypoints.json").is_file()
        fr = cl.get(f"/finals/{f['id']}/layers/chest/beauty/2", headers=H)
        assert fr.status_code == 200 and fr.content == _png(30)
        assert cl.get(f"/finals/{f['id']}/layers/chest/beauty/9", headers=H).status_code == 404
        assert [x["id"] for x in cl.get(f"/finals?stage_id={st['id']}", headers=H).json()["items"]] == [f["id"]]
        assert cl.get("/finals?stage_id=stg_other", headers=H).json()["items"] == []
        # refusals: a pass short of frames, no shadows layer, a figure without its object, a blob never uploaded, an unknown stage
        bad = {**body, "layers": [layers[0], layers[1], {**layers[2], "passes": {"pose": seq[:2], "depth": seq}}]}
        assert cl.post("/finals", json=bad, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], layers[2]]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], layers[1], {**layers[3], "object_id": None}]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "layers": [layers[0], {**layers[1], "passes": {"clay": ["0" * 64] * 3}}]}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "stage_id": "stg_nope"}, headers=H).status_code == 404
        assert len(list((tmp_path / "proj" / "finals").glob("fin_*"))) == 1                   # a refused final leaves nothing behind
        assert cl.delete(f"/finals/{f['id']}", headers=H).status_code == 200 and not d.exists()
        assert cl.get(f"/finals/{f['id']}", headers=H).status_code == 404
