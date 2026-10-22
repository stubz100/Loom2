"""D119 (SC2): stage templates — an arrangement of the Clay level saved under a name as a project record, listed and replaced through
/project/stage-templates (distinct names, at least one object each)."""
from pathlib import Path


def test_stage_templates_record(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    svc = app.state.services
    H = {"X-Loom-Token": svc.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        assert cl.get("/project/stage-templates", headers=H).json() == {"schema_version": 1, "templates": []}
        room = {"id": "set_x", "kind": "set", "name": "Set 1", "preset": "room", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}}
        lamp = {"id": "light_x", "kind": "light", "name": "Light 1", "transform": {"pos": [-2, 3, 2], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "light": {"strength": 2.0}}
        r = cl.put("/project/stage-templates", json={"templates": [{"name": "Kitchen", "objects": [room, lamp]}]}, headers=H)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["schema_version"] == 1 and [t["name"] for t in got["templates"]] == ["Kitchen"] and got["templates"][0]["saved_at"] and got["templates"][0]["thumb_asset_id"] is None
        assert got["templates"][0]["objects"][1]["light"] == {"strength": 2.0}
        assert cl.get("/project/stage-templates", headers=H).json()["templates"][0]["objects"][0]["preset"] == "room"
        assert (tmp_path / "proj" / "stages" / "templates.json").is_file()
        assert cl.put("/project/stage-templates", json={"templates": [{"name": "Kitchen", "objects": [room]}, {"name": "kitchen ", "objects": [room]}]}, headers=H).status_code == 200   # distinct after trim? no: "Kitchen" vs "kitchen" differ
        assert cl.put("/project/stage-templates", json={"templates": [{"name": "A", "objects": [room]}, {"name": "A", "objects": [lamp]}]}, headers=H).status_code == 422
        assert cl.put("/project/stage-templates", json={"templates": [{"name": " ", "objects": [room]}]}, headers=H).status_code == 422
        assert cl.put("/project/stage-templates", json={"templates": [{"name": "Empty", "objects": []}]}, headers=H).status_code == 422
        r = cl.put("/project/stage-templates", json={"templates": []}, headers=H)
        assert r.status_code == 200 and r.json()["templates"] == []
