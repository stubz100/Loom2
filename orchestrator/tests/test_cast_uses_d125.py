"""D125 (S5, SP5): Cast's readiness reads each profile's shots — a Dialogue line's speaker, a node's place, a stage figure or a prop's mesh
bound to it, with the shot's route — and each version's reference count (GET /story/cast/uses)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402


def test_uses(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}, headers=H).json()
        quay = cl.post("/story/profiles", json={"name": "Quay", "cls": "place"}, headers=H).json()
        lamp = cl.post("/story/profiles", json={"name": "Lamp", "cls": "prop"}, headers=H).json()
        talk = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Talk"}, headers=H).json()
        cl.patch(f"/story/flow/nodes/{talk['id']}", json={"lines": [{"speaker": mara["id"], "text": "Hello.", "audio_asset_id": None, "audio_text": None}],
                                                           "place_id": quay["id"]}, headers=H)
        walk = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Walk"}, headers=H).json()
        st = cl.post("/stages", json={"name": "Quay"}, headers=H).json()
        st["objects"] = [{"id": "obj_f", "kind": "mannequin", "preset": "adult", "name": "Mara", "profile_id": mara["id"]},
                         {"id": "obj_l", "kind": "mesh", "name": "Lamp", "profile_id": lamp["id"]}]
        assert cl.put(f"/stages/{st['id']}", json=st, headers=H).status_code == 200
        assert cl.put(f"/story/shots/{walk['shot_id']}/versions/v1/source", json={"stage_id": st["id"], "camera_id": st["cameras"][0]["id"]}, headers=H).status_code == 200
        r = cl.get("/story/cast/uses", headers=H)
        assert r.status_code == 200, r.text
        by = {x["profile_id"]: x for x in r.json()["items"]}
        uses = {u["name"]: u for u in by[mara["id"]]["uses"]}
        assert uses["Talk"]["how"] == ["speaker"] and uses["Talk"]["route"] == "i2v"
        assert uses["Walk"]["how"] == ["figure"] and uses["Walk"]["route"] == "stage"
        assert [(u["name"], u["how"]) for u in by[quay["id"]]["uses"]] == [("Talk", ["place"])]
        assert [(u["name"], u["how"]) for u in by[lamp["id"]]["uses"]] == [("Walk", ["prop"])]
        assert by[mara["id"]]["refs"] == {"v1": 0}
