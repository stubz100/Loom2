"""D93 follow-up: a Flow node pins a version per speaker (`FlowNode.speaker_versions`, profile id → version id; absent = current) — PATCH
accepts a character's own version and refuses anything else (422), a pin whose version was deleted since stays on other saves, and a node
file from before reads with no pins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import FlowNode, StoryStore  # noqa: E402


def test_pins(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        mara = cl.post(f"/story/profiles/{mara['id']}/versions", json={}).json()                  # v2: rain gear
        assert [v["id"] for v in mara["versions"]] == ["v1", "v2"]
        harbour = cl.post("/story/profiles", json={"name": "Harbour", "cls": "place"}).json()
        n = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Arrival"}).json()
        assert n["speaker_versions"] == {}
        r = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "lines": [{"speaker": mara["id"], "text": "We're late."}], "speaker_versions": {mara["id"]: "v2"}})
        assert r.status_code == 200 and r.json()["speaker_versions"] == {mara["id"]: "v2"}
        n = r.json()
        for bad in ({mara["id"]: "v9"}, {harbour["id"]: "v1"}, {"prf_gone": "v1"}, {mara["id"]: 2}, ["v1"]):
            assert cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "speaker_versions": bad}).status_code == 422, bad
        # back to current: the key goes
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "speaker_versions": {}}).json()
        assert n["speaker_versions"] == {}
        # a pin whose version disappears stays on other saves (the client shows it and falls back to current)
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "speaker_versions": {mara["id"]: "v2"}}).json()
        st = StoryStore(app.state.services.ws)                                                   # the version goes (a hand edit, an old copy)
        prof = st.profile(mara["id"])
        st.save_profile(prof.model_copy(update={"versions": [v for v in prof.versions if v.id == "v1"], "current": "v1"}))
        r = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "title": "Arrival, late", "speaker_versions": n["speaker_versions"]})
        assert r.status_code == 200 and r.json()["speaker_versions"] == {mara["id"]: "v2"}
        assert cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": r.json()["revision"], "speaker_versions": {mara["id"]: "v3"}}).status_code == 422
        cl.post("/project/close")


def test_an_old_node_file_reads_without_pins(tmp_path: Path):
    old = {"schema_version": 1, "id": "node_old", "type": "dialogue", "title": "Before", "lines": [{"speaker": "prf_1", "text": "hi"}], "revision": 3,
           "created_at": "2026-10-14T08:00:00Z", "updated_at": "2026-10-14T08:00:00Z"}
    n = FlowNode.model_validate(json.loads(json.dumps(old)))
    assert n.speaker_versions == {} and n.lines[0].speaker == "prf_1"
