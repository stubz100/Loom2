"""D125 (S11, SP3): an existing shot's open version pointed at a stage camera (no second shot made), its stage results then landing on it by the
camera; a camera the stage lacks, a final version and half a source are refused; both null unlink it."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def test_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Tavern"}, headers=H).json()
        cam = st["cameras"][0]["id"]
        n = cl.post("/story/flow/nodes", json={"type": "shot", "title": "The door"}, headers=H).json()
        sid = n["shot_id"]
        r = cl.put(f"/story/shots/{sid}/versions/v1/source", json={"stage_id": st["id"], "camera_id": cam}, headers=H)
        assert r.status_code == 200, r.text
        v = r.json()["versions"][0]
        assert v["stage_id"] == st["id"] and v["camera_id"] == cam and v["stage_revision"] == st["revision"]
        assert len(cl.get("/story/shots", headers=H).json()["items"]) == 1                                   # the node's shot, no second one
        assert cl.put(f"/story/shots/{sid}/versions/v1/source", json={"stage_id": st["id"], "camera_id": "cam_nope"}, headers=H).status_code == 422
        assert cl.put(f"/story/shots/{sid}/versions/v1/source", json={"stage_id": "stg_nope", "camera_id": cam}, headers=H).status_code == 422
        assert cl.put(f"/story/shots/{sid}/versions/v9/source", json={"stage_id": st["id"], "camera_id": cam}, headers=H).status_code == 404
        # the stage's results come back to it by the camera
        ws = Workspace(tmp_path / "proj")
        hit = StoryStore(ws).record_stage_result(st["id"], cam, "image", "ast_still", st["revision"])
        assert [s.id for s in hit] == [sid] and StoryStore(ws).shot(sid).version().frame_asset_id == "ast_still"
        # unlinked: both null
        r = cl.put(f"/story/shots/{sid}/versions/v1/source", json={"stage_id": None, "camera_id": None}, headers=H)
        assert r.status_code == 200 and r.json()["versions"][0]["stage_id"] is None and r.json()["versions"][0]["stage_revision"] is None


def test_a_final_version_keeps_its_source(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    s = st.create_shot("Gate", clip_id=None)
    s = st.add_take(s.id, "v1", "clip", "clp_1")
    st.finalize_shot(s.id, "v1", (832, 480), (1920, 1080))
    import pytest
    with pytest.raises(ValueError, match="final"):
        st.set_source(s.id, "v1", "stg", "cam", 1)
    with pytest.raises(ValueError, match="both"):
        st.set_source(st.create_shot("Other").id, "v1", "stg", None, None)
