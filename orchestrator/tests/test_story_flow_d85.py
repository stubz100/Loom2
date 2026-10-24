"""17 (D85) · SY3 Flow: one file per node and a rebuildable index (positions, edges, the start), the ports a node offers, binding a shot
as a node's sole property (bind / unbind / spawn / delete releases), the graph's revision guard and edge checks, validation as a list,
and the routes end to end."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import FlowEdge, FlowGraph, FlowNode, FlowOption, StaleFlow, StoryStore, node_ports, validate_flow  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def test_ports_and_validation():
    assert node_ports(FlowNode(type="dialogue")) == ["out"] and node_ports(FlowNode(type="condition")) == ["then", "else"]
    assert node_ports(FlowNode(type="jump")) == [] and node_ports(FlowNode(type="comment")) == []
    c = FlowNode(type="choice", options=[FlowOption(id="opt_a", label="A"), FlowOption(id="opt_b", label="B")])
    assert node_ports(c) == ["opt:opt_a", "opt:opt_b"]
    start, d, j, cm = FlowNode(id="n_s", type="start"), FlowNode(id="n_d", type="dialogue", title="Hello"), FlowNode(id="n_j", type="jump", target="n_zz"), FlowNode(id="n_c", type="comment")
    orphan = FlowNode(id="n_o", type="shot", title="Lost", shot_id="sht_x")
    nodes = {n.id: n for n in (start, d, j, cm, orphan, c)}
    g = FlowGraph(nodes=[], edges=[FlowEdge(**{"from": "n_s", "port": "out", "to": "n_d"}), FlowEdge(**{"from": "n_d", "port": "out", "to": "n_j"}), FlowEdge(**{"from": "n_d", "port": "nope", "to": "n_s"}),
                                   FlowEdge(**{"from": "n_gone", "port": "out", "to": "n_d"})], start="n_s")
    codes = sorted(p["code"] for p in validate_flow(g, nodes, ["met"], {}))
    assert codes == ["bad_port", "dangling_edge", "dangling_jump", "no_shot", "shot_gone", "unreachable", "unreachable"]   # Hello has no shot; Lost's shot is gone; Lost and the Choice unreachable; the Comment never flagged
    assert [p["code"] for p in validate_flow(FlowGraph(), {}, [], {})] == ["no_start"]
    two = {n.id: n for n in (start, FlowNode(id="n_s2", type="start"))}
    assert "many_starts" in [p["code"] for p in validate_flow(FlowGraph(start="n_s"), two, [], {})]
    cond = FlowNode(id="n_q", type="condition", cond={"var": "door", "op": "eq", "value": "open"})
    assert [p["code"] for p in validate_flow(FlowGraph(start="n_s"), {"n_s": start, "n_q": cond}, ["met"], {})] == ["unknown_var", "unreachable"]


def test_store_nodes_graph_bind(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    assert st.flow_nodes() == {} and st.flow_graph().nodes == [] and not (ws.story_dir / "flow" / "graph.json").is_file()   # a read writes nothing
    s = st.create_node("start", x=10, y=20)
    d = st.create_node("dialogue", "Hello", 300, 20, with_shot=False, lines=[{"speaker": None, "text": "Hi."}])   # D125: bound by hand below
    c = st.create_node("choice", "Pick", 600, 20, options=[{"id": "opt_a", "label": "A"}, {"id": "opt_b", "label": "B"}])
    g = st.flow_graph()
    assert g.start == s.id and [p.id for p in g.nodes] == [s.id, d.id, c.id] and g.nodes[1].x == 300 and g.revision == 3
    assert st.flow_node(d.id).lines[0].text == "Hi." and s.title == "Start"
    with pytest.raises(ValueError, match="unknown node type"):
        st.create_node("scene")
    # edges: one per port, ports checked, a stale revision refused
    g2 = st.put_graph({"revision": g.revision, "edges": [{"from": s.id, "port": "out", "to": d.id}, {"from": d.id, "port": "out", "to": c.id}, {"from": c.id, "port": "opt:opt_a", "to": d.id}, {"from": c.id, "port": "opt:opt_a", "to": s.id}]})
    assert [(e.from_, e.port, e.to) for e in g2.edges] == [(s.id, "out", d.id), (d.id, "out", c.id), (c.id, "opt:opt_a", d.id)]   # the second opt_a edge dropped
    with pytest.raises(StaleFlow):
        st.put_graph({"revision": g.revision, "edges": []})
    with pytest.raises(ValueError, match="no port"):
        st.put_graph({"revision": g2.revision, "edges": [{"from": c.id, "port": "out", "to": d.id}]})
    with pytest.raises(ValueError, match="missing"):
        st.put_graph({"revision": g2.revision, "edges": [{"from": "node_zz", "port": "out", "to": d.id}]})
    with pytest.raises(ValueError, match="Start node"):
        st.put_graph({"revision": g2.revision, "start": d.id})
    g3 = st.put_graph({"revision": g2.revision, "nodes": [{"id": d.id, "x": 333, "y": 44}]})
    assert next(p for p in g3.nodes if p.id == d.id).x == 333 and len(g3.nodes) == 3                   # the others keep their place
    # patch: fields by type; the shot through bind only
    d2 = st.patch_node(d.id, {"revision": d.revision, "title": "Hello there", "shot_id": "sht_sneaky"})
    assert d2.title == "Hello there" and d2.shot_id is None and d2.revision == d.revision + 1
    with pytest.raises(StaleFlow):
        st.patch_node(d.id, {"revision": d.revision, "title": "x"})
    # an option removed takes its edge with it
    c2 = st.patch_node(c.id, {"revision": st.flow_node(c.id).revision, "options": [{"id": "opt_b", "label": "B"}]})
    assert [o.id for o in c2.options] == ["opt_b"] and all(not (e.from_ == c.id and e.port == "opt:opt_a") for e in st.flow_graph().edges)
    # bind (RC2a): a shot made elsewhere is a bare Shot node; binding moves it into the node and the bare node goes; a shot of a node in
    # the story is refused (a shot is one node); unbind and delete move it out to a node of its own
    sh = st.create_shot("Gate")
    bare = sh.owner_node
    other = st.create_node("shot", "Other", 0, 300, with_shot=False)
    n, sh2 = st.bind_shot(d.id, sh.id)
    assert n.shot_id == sh.id and n.shot_version == "v1" and sh2.owner_node == d.id and st.flow_node(bare) is None
    with pytest.raises(ValueError, match="a shot is one node"):
        st.bind_shot(other.id, sh.id)
    with pytest.raises(ValueError, match="does not bind"):
        st.bind_shot(s.id, sh.id)
    with pytest.raises(KeyError):
        st.bind_shot(d.id, "sht_nope")
    st.new_shot_version(sh.id)
    n2, _ = st.bind_shot(d.id, sh.id, "v1")                                                           # re-selecting a version of its own
    assert n2.shot_version == "v1"
    st.add_take(sh.id, "v2", "image", "ast_1")
    n3, rel = st.unbind_shot(d.id)
    assert n3.shot_id not in (None, sh.id) and rel is not None and rel.id == sh.id and rel.owner_node not in (None, d.id)   # a fresh shot stays
    st.bind_shot(d.id, sh.id)
    released = st.delete_node(d.id)
    assert released is not None and released.id == sh.id and released.owner_node not in (None, d.id) and st.flow_node(d.id) is None
    g4 = st.flow_graph()
    assert all(p.id != d.id for p in g4.nodes) and all(d.id not in (e.from_, e.to) for e in g4.edges) and g4.start == s.id
    # the index is rebuilt from the node files when it is gone or disagrees
    (ws.story_dir / "flow" / "graph.json").unlink()
    g5 = st.flow_graph()
    assert {p.id for p in g5.nodes} == {s.id, c.id, other.id, released.owner_node} and g5.start == s.id and g5.edges == []
    (ws.story_dir / "flow" / "graph.json").write_text(json.dumps({**g5.model_dump(by_alias=True), "nodes": [{"id": "node_ghost", "x": 1, "y": 1}], "edges": [{"from": s.id, "port": "out", "to": "node_ghost"}]}), encoding="utf-8")
    g6 = st.flow_graph()
    assert {p.id for p in g6.nodes} == {s.id, c.id, other.id, released.owner_node} and g6.edges == []


def test_routes_flow(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.get("/story/flow").status_code == 409
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        assert cl.get("/story/flow").json() == {"graph": {"schema_version": 2, "nodes": [], "edges": [], "start": None, "revision": 0, "updated_at": cl.get("/story/flow").json()["graph"]["updated_at"]}, "nodes": []}
        assert cl.post("/story/flow/nodes", json={"type": "scene"}).status_code == 422
        s = cl.post("/story/flow/nodes", json={"type": "start", "x": 10, "y": 10}).json()
        d = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Hello", "x": 300, "y": 10, "shot": False}).json()   # D125: spawned below
        w = cl.get("/story/world").json()
        cl.put("/story/world", json={**w, "variables": [{"name": "met", "type": "bool", "values": [], "default": False}]})
        c = cl.post("/story/flow/nodes", json={"type": "choice", "title": "Pick", "x": 600, "y": 10}).json()
        r = cl.patch(f"/story/flow/nodes/{c['id']}", json={"revision": c["revision"], "options": [{"id": "opt_a", "label": "Go", "set": [{"var": "met", "value": True}]}, {"id": "opt_b", "label": "Stay"}]})
        assert r.status_code == 200 and len(r.json()["options"]) == 2
        assert cl.patch(f"/story/flow/nodes/{c['id']}", json={"revision": c["revision"], "title": "x"}).status_code == 409
        f = cl.get("/story/flow").json()
        assert f["graph"]["start"] == s["id"] and len(f["nodes"]) == 3
        r = cl.put("/story/flow/graph", json={"revision": f["graph"]["revision"], "edges": [{"from": s["id"], "port": "out", "to": d["id"]}, {"from": d["id"], "port": "out", "to": c["id"]}, {"from": c["id"], "port": "opt:opt_a", "to": d["id"]}]})
        assert r.status_code == 200 and len(r.json()["edges"]) == 3
        assert cl.put("/story/flow/graph", json={"revision": f["graph"]["revision"], "edges": []}).status_code == 409
        assert cl.put("/story/flow/graph", json={"revision": r.json()["revision"], "edges": [{"from": c["id"], "port": "out", "to": d["id"]}]}).status_code == 422
        # validate: the dialogue has no shot; opt_b leads nowhere is fine (a choice may end); nothing else
        p = cl.post("/story/flow/validate").json()["problems"]
        assert [x["code"] for x in p] == ["no_shot"] and p[0]["node_id"] == d["id"]
        # spawn a shot for the dialogue → owned; bind it to another node → 422; unbind → released
        r = cl.post(f"/story/flow/nodes/{d['id']}/shot", json={"name": "Hello shot"})
        assert r.status_code == 200 and r.json()["shot"]["owner_node"] == d["id"] and r.json()["node"]["shot_id"] == r.json()["shot"]["id"]
        sid = r.json()["shot"]["id"]
        sh = cl.post("/story/flow/nodes", json={"type": "shot", "title": "Other", "x": 0, "y": 300, "shot": False}).json()
        assert cl.post(f"/story/flow/nodes/{sh['id']}/bind", json={"shot_id": sid}).status_code == 422                # RC2a: a shot is one node
        assert cl.post(f"/story/flow/nodes/{s['id']}/bind", json={"shot_id": sid}).status_code == 422
        assert cl.post(f"/story/flow/nodes/{d['id']}/bind", json={"shot_id": sid, "version": "v9"}).status_code == 404
        assert cl.get(f"/story/shots/{sid}").json()["owner_node"] == d["id"]
        p = cl.post("/story/flow/validate").json()["problems"]
        assert sorted(x["code"] for x in p) == ["no_shot", "shot_open", "unreachable"]                      # Other: no shot, unreachable; Hello's shot not final
        r = cl.post(f"/story/flow/nodes/{d['id']}/unbind")                                                       # an empty shot: nothing moves
        assert r.status_code == 200 and r.json()["node"]["shot_id"] == sid and r.json()["shot"] is None
        cl.post(f"/story/shots/{sid}/versions")                                                                  # work in it: unbind moves it out
        r = cl.post(f"/story/flow/nodes/{d['id']}/unbind")
        assert r.status_code == 200 and r.json()["node"]["shot_id"] not in (None, sid) and r.json()["shot"]["id"] == sid
        mover = r.json()["shot"]["owner_node"]
        assert mover != d["id"] and cl.get(f"/story/shots/{sid}").json()["owner_node"] == mover
        assert cl.post(f"/story/flow/nodes/{sh['id']}/bind", json={"shot_id": sid}).status_code == 200      # a shot of its own: it moves in
        assert all(n["id"] != mover for n in cl.get("/story/flow").json()["nodes"])
        # delete the node → its shot moved to a node of its own, the edges gone
        assert cl.delete(f"/story/flow/nodes/{sh['id']}").json()["deleted"] == sh["id"]
        assert cl.get(f"/story/shots/{sid}").json()["owner_node"] not in (None, sh["id"])
        assert cl.delete(f"/story/flow/nodes/{sh['id']}").status_code == 404
        f = cl.get("/story/flow").json()
        assert all(sh["id"] not in (e["from"], e["to"]) for e in f["graph"]["edges"]) and len(f["nodes"]) == 4
