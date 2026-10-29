"""RC2a (D96, proto01_animate 31 §3b): the Flow node and its shot are one record — the shot inside the node's file, its `sht_*` id kept and
found through a rebuildable index; the migration joins a project's shots to their nodes once (the owner first, a shot without a node as a
Shot node outside the routes, the old files kept aside); one lock keeps a node's edits and its shot's from losing each other; a node turned
into a logic node refuses a shot with work in it; deleting a shot empties a node in the story and removes a bare one."""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.fsio import atomic_write_json  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def _old_shot(ws: Workspace, sid: str, name: str, owner: str | None, versions: int = 1, takes: tuple[str, ...] = ()) -> None:
    vs = [{"id": f"v{i + 1}", "state": "open", "takes": [{"kind": "image", "id": t} for t in takes], "frame_asset_id": takes[0] if takes else None} for i in range(versions)]
    atomic_write_json(ws.story_dir / "shots" / f"{sid}.json", {"schema_version": 1, "id": sid, "name": name, "owner_node": owner, "current": "v1",
                                                              "versions": vs, "revision": 4, "created_at": f"2026-10-0{versions}T00:00:00Z", "updated_at": "2026-10-10T00:00:00Z"})


def _old_node(ws: Workspace, nid: str, type_: str, title: str, shot_id: str | None = None, shot_version: str | None = None, created: str = "2026-10-01T00:00:00Z") -> None:
    atomic_write_json(ws.story_dir / "flow" / "nodes" / f"{nid}.json", {"schema_version": 1, "id": nid, "type": type_, "title": title, "shot_id": shot_id,
                                                                       "shot_version": shot_version, "revision": 2, "created_at": created, "updated_at": created})


def test_the_migration_joins_each_shot_to_its_node_once(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    (ws.story_dir / "shots").mkdir(parents=True)
    _old_shot(ws, "sht_own", "Reunion", "node_a", versions=2, takes=("ast_1",))
    _old_shot(ws, "sht_free", "Gate", None)
    _old_shot(ws, "sht_lost", "From the camera", None, takes=("ast_2",))
    _old_node(ws, "node_a", "dialogue", "Dialogue", "sht_own", "v2")                  # the default title: the shot's name is kept
    _old_node(ws, "node_b", "shot", "Second", "sht_own", "v1", created="2026-10-02T00:00:00Z")   # points at a shot another node owns
    _old_node(ws, "node_c", "shot", "Arrival", "sht_free", "v1")                      # owner None: the node pointing at it takes it
    _old_node(ws, "node_d", "dialogue", "Gone", "sht_nowhere", "v1")                  # a shot that is gone
    _old_node(ws, "node_e", "choice", "Pick", "sht_free", "v1")                       # a logic node never holds one
    atomic_write_json(ws.story_dir / "flow" / "graph.json", {"schema_version": 1, "nodes": [{"id": "node_a", "x": 0, "y": 0}, {"id": "node_b", "x": 300, "y": 0}],
                                                            "edges": [{"from": "node_a", "port": "out", "to": "node_b"}], "start": None, "revision": 7})
    atomic_write_json(ws.story_dir / "flow" / "scenes.json", {"schema_version": 3, "scenes": [], "revision": 0})   # U4's scenes for the shots: test_scenes_u4
    st = StoryStore(ws)
    assert st.migrated and st.migrated[0].startswith("RC2: 2 shots joined their Flow nodes; 1 without a node became a Shot node outside the routes")
    assert any("Second" in n for n in st.migrated) and any("Gone" in n for n in st.migrated)
    a, b, c, d, e = (st.flow_node(x) for x in ("node_a", "node_b", "node_c", "node_d", "node_e"))
    assert a.title == "Reunion" and a.shot_id == "sht_own" and a.shot_version == "v2"           # the version the node showed is current now
    sh = st.shot("sht_own")
    assert sh.owner_node == "node_a" and sh.current == "v2" and sh.name == "Reunion" and len(sh.versions) == 2 and sh.revision == 4
    assert b.shot_id not in (None, "sht_own") and st.shot(b.shot_id).versions[0].takes == []   # the loser gets a fresh shot
    assert c.shot_id == "sht_free" and st.shot("sht_free").owner_node == "node_c"
    assert d.shot_id and d.shot_id != "sht_nowhere" and e.shot_id is None
    lost = st.shot("sht_lost")
    bare = st.flow_node(lost.owner_node)
    assert bare.type == "shot" and bare.title == "From the camera" and lost.version().takes[0].id == "ast_2"
    g = st.flow_graph()
    assert next(p for p in g.nodes if p.id == bare.id).x >= 300 + 280                               # beside the graph, right of the routed nodes
    assert {p.name for p in (ws.story_dir / "shots-rc2").glob("*.json")} == {"sht_own.json", "sht_free.json", "sht_lost.json"} and not (ws.story_dir / "shots").exists()
    raw = json.loads((ws.story_dir / "flow" / "nodes" / "node_a.json").read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2 and raw["shot"]["id"] == "sht_own" and raw["shot_id"] == "sht_own"
    assert StoryStore(ws).migrated == []                                                              # once
    assert len(st.shots()) == 5                                                                        # a, b, c, d and the bare one; none for the choice
    # the index is rebuilt when it is gone or names the wrong node
    (ws.story_dir / "flow" / "shots.json").unlink()
    assert st.shot("sht_own").owner_node == "node_a"
    atomic_write_json(ws.story_dir / "flow" / "shots.json", {"schema_version": 1, "shots": {"sht_own": "node_b"}})
    assert st.shot("sht_own").owner_node == "node_a" and st.shot("sht_nope") is None


def test_one_record_holds_a_nodes_edits_and_its_shots_together(tmp_path: Path):
    st = StoryStore(Workspace.create(tmp_path / "p", name="P"))
    n = st.create_node("dialogue", "Talk")
    errors: list[BaseException] = []

    def takes(k: int) -> None:
        try:
            for i in range(10):
                st.add_take(n.shot_id, "v1", "image", f"ast_{k}_{i}")
        except BaseException as e:                       # noqa: BLE001
            errors.append(e)

    def titles(k: int) -> None:
        try:
            for i in range(10):
                st.patch_node(n.id, {"title": f"Talk {k}.{i}", "lines": [{"speaker": None, "text": f"line {k}.{i}"}]})
        except BaseException as e:                       # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=takes, args=(k,)) for k in range(4)] + [threading.Thread(target=titles, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    s = st.shot(n.shot_id)
    assert len(s.version().takes) == 40 and s.revision == 40                     # no take lost to a title's save, nor the other way
    node = st.flow_node(n.id)
    assert node.revision == n.revision + 40 and node.title.startswith("Talk ") and s.name == node.title


def test_type_changes_delete_and_the_api_view(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    n = st.create_node("shot", "Arrival", lines=[])
    empty = st.patch_node(n.id, {"type": "choice"})                               # an empty shot is dropped with the type
    assert empty.shot_id is None and st.shot(n.shot_id) is None
    again = st.patch_node(n.id, {"type": "shot"})
    assert again.shot_id and again.shot_id != n.shot_id
    st.add_take(again.shot_id, "v1", "clip", "clp_1")
    with pytest.raises(ValueError, match="work in it"):
        st.patch_node(n.id, {"type": "comment"})
    # deleting the shot of a node in the story: the node keeps its lines and gets a fresh shot
    d = st.create_node("dialogue", "Talk", lines=[{"speaker": None, "text": "Hi."}])
    st.add_take(d.shot_id, "v1", "image", "ast_1")
    assert st.delete_shot(d.shot_id)
    d2 = st.flow_node(d.id)
    assert d2.shot_id not in (None, d.shot_id) and d2.lines[0].text == "Hi." and st.shot(d.shot_id) is None
    # deleting a shot made elsewhere removes its bare node
    s = st.create_shot("From the camera", frame_asset_id="ast_9")
    assert st.flow_node(s.owner_node) is not None and st.delete_shot(s.id) and st.flow_node(s.owner_node) is None
    # the API's view: GET /story/flow carries no shot body (the nodes stay light), /story/shots the shot with its node
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "q"), "name": "q", "size_cap_gb": 10}).status_code == 200
        node = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Talk"}).json()
        assert "shot" not in node and node["shot_id"]
        assert all("shot" not in x for x in cl.get("/story/flow").json()["nodes"])
        s = cl.get(f"/story/shots/{node['shot_id']}").json()
        r = cl.patch(f"/story/shots/{s['id']}", json={"revision": s["revision"], "name": "Talk · close"})
        assert r.status_code == 200 and cl.get("/story/flow").json()["nodes"][0]["title"] == "Talk · close"     # one name
        assert cl.patch(f"/story/flow/nodes/{node['id']}", json={"type": "choice"}).status_code == 200              # still empty: dropped
