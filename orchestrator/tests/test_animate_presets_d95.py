"""D95 (AN1, UX0 #11): Animate's saved panels are a project record (`animate/presets.json`), no longer browser storage — names distinct and
non-empty, the frames (start, end, beats) never saved, `last` one of the names or none."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState


def _app(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    return create_app(state)


def test_animate_presets_are_a_project_record(tmp_path: Path):
    app = _app(tmp_path)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "A", "size_cap_gb": 10}, headers=H)
        assert client.get("/project/animate-presets", headers=H).json() == {"schema_version": 1, "presets": [], "last": None}
        body = {"presets": [{"name": "dusk walk", "panel": {"model_id": "m", "preset": "draft", "start": "ast_1", "end": None, "beats": [{"frame": 3}], "prompt": "she walks"}}],
                "last": "dusk walk"}
        r = client.put("/project/animate-presets", json=body, headers=H)
        assert r.status_code == 200, r.text
        got = client.get("/project/animate-presets", headers=H).json()
        assert got["last"] == "dusk walk" and got["presets"][0]["panel"] == {"model_id": "m", "preset": "draft", "prompt": "she walks"}   # no frames
        on_disk = json.loads((tmp_path / "proj" / "animate" / "presets.json").read_text(encoding="utf-8"))
        assert on_disk["schema_version"] == 1 and on_disk["presets"][0]["name"] == "dusk walk"
        assert client.put("/project/animate-presets", json={"presets": [{"name": "a"}, {"name": "a"}]}, headers=H).status_code == 422
        assert client.put("/project/animate-presets", json={"presets": [{"name": "b"}], "last": "gone"}, headers=H).json()["last"] is None
