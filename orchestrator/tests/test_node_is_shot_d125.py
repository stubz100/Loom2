"""D125 (#4, SP2): a Dialogue or Shot node has its shot from the moment it is made — the shot takes the node's title and follows its renames
until it is renamed by hand; a node turned visual gets one; deleting a node keeps its shot unbound or deletes it too, as asked."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def test_a_visual_node_is_made_with_its_shot(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    n = st.create_node("dialogue", "Reunion")
    assert n.shot_id and n.shot_version == "v1"
    sh = st.shot(n.shot_id)
    assert sh.name == "Reunion" and sh.owner_node == n.id
    assert st.shot(st.create_node("shot").shot_id).name == "Shot"                   # untitled: the type's name
    assert st.create_node("choice", "Stay or go").shot_id is None                    # logic nodes have none
    assert st.create_node("dialogue", "Bare", with_shot=False).shot_id is None       # the API can opt out (a shot bound later)


def test_the_shot_follows_the_title_and_a_node_turned_visual_gets_one(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    n = st.create_node("shot", "Arrival")
    n = st.patch_node(n.id, {"title": "Arrival in the rain"})
    assert st.shot(n.shot_id).name == "Arrival in the rain"
    sh = st.shot(n.shot_id)
    st.patch_shot(sh.id, {"revision": sh.revision, "name": "Arrival · wide"})       # renamed by hand: it keeps its own name
    st.patch_node(n.id, {"title": "Arrival at night"})
    assert st.shot(n.shot_id).name == "Arrival · wide"
    c = st.create_node("choice", "Door")
    c = st.patch_node(c.id, {"type": "shot"})
    assert c.shot_id and st.shot(c.shot_id).name == "Door"


def test_deleting_a_node_keeps_or_deletes_its_shot(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    a = st.create_node("dialogue", "Kept")
    released = st.delete_node(a.id)
    assert released is not None and released.owner_node is None and st.shot(a.shot_id) is not None
    b = st.create_node("dialogue", "Gone")
    assert st.delete_node(b.id, delete_shot=True) is None and st.shot(b.shot_id) is None


def test_routes(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        n = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Reunion"}, headers=H).json()
        assert n["shot_id"]
        assert cl.get(f"/story/shots/{n['shot_id']}", headers=H).json()["owner_node"] == n["id"]
        bare = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Bare", "shot": False}, headers=H).json()
        assert bare["shot_id"] is None
        r = cl.post(f"/story/flow/nodes/{n['id']}/shot", json={"name": "Reunion · wide"}, headers=H).json()     # its untouched shot is reused, renamed
        assert r["shot"]["id"] == n["shot_id"] and r["shot"]["name"] == "Reunion · wide"
        assert len(cl.get("/story/shots", headers=H).json()["items"]) == 1
        assert cl.delete(f"/story/flow/nodes/{n['id']}?shot=delete", headers=H).status_code == 200
        assert cl.get(f"/story/shots/{n['shot_id']}", headers=H).status_code == 404
