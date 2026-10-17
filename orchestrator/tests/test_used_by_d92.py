"""D92 §4.2 (owed): "used by" on Catalogue groups — computed from the story and stage records (nothing stored): a Cast version's reference
set and candidates, a style's samples, a Flow node's board, a Stage's album page, a library entry; `deep` adds the groups inside (what a
delete takes with it); the route answers for asked ids or every used group."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.fsio import atomic_write_json, read_json  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.usedby import all_users, users_of  # noqa: E402

from test_groups_d34 import _setup  # noqa: E402


def _world(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    mara = st.create_profile("Mara", "character", groups, hero_asset_id=ids[0])
    st.set_candidates(mara.id, "v1", groups.create("Mara · candidates").id)
    mara = st.new_version(mara.id, groups)
    mara = st.patch_profile(mara.id, {"revision": mara.revision, "versions": [{**v.model_dump(), **({"label": "rain gear"} if v.id == "v2" else {})} for v in mara.versions]})
    ink = groups.create("Ink wash samples")
    st.put_world({"styles": [{"id": "sty_ink", "name": "Ink wash", "fragment": "ink wash", "group_id": ink.id}]})
    board = groups.create("Harbour board")
    node = st.create_node("dialogue", "Arrival")
    node = st.patch_node(node.id, {"revision": node.revision, "board_group_id": board.id})
    stages = StageStore(ws)
    stg = stages.create("Pier")
    page = groups.create("Pier page", parent_id=board.id)                 # a group inside the board
    stg = stg.model_copy(update={"group_id": page.id})
    stages.save(stg)
    return ws, groups, st, mara, ink, board, node, stg, page


def test_every_kind_of_user_is_found(tmp_path: Path):
    ws, groups, st, mara, ink, board, node, stg, page = _world(tmp_path)
    users = all_users(ws)
    v1, v2 = mara.versions
    assert [(u.kind, u.name, u.extra, u.version, u.cls) for u in users[v1.group_id]] == [("profile_ref", "Mara", "v1", "v1", "character")]
    assert [(u.kind, u.extra) for u in users[v1.candidates_group_id]] == [("profile_candidates", "v1")]
    assert [(u.kind, u.extra, u.version) for u in users[v2.group_id]] == [("profile_ref", "rain gear", "v2")]   # the label when it has one
    assert [(u.kind, u.id, u.name) for u in users[ink.id]] == [("style", "sty_ink", "Ink wash")]
    assert [(u.kind, u.id, u.name, u.extra) for u in users[board.id]] == [("flow_board", node.id, "Arrival", "dialogue")]
    assert [(u.kind, u.id, u.name) for u in users[stg.group_id]] == [("stage", stg.id, "Pier")]
    assert all(u.group_id == gid for gid, us in users.items() for u in us)


def test_deep_adds_the_groups_inside_and_unused_groups_answer_empty(tmp_path: Path):
    ws, groups, st, mara, ink, board, node, stg, page = _world(tmp_path)
    loose = groups.create("Loose")
    shallow = users_of(ws, groups, [board.id, loose.id, "grp_missing"])
    assert [u.kind for u in shallow[board.id]] == ["flow_board"] and shallow[loose.id] == [] and shallow["grp_missing"] == []
    deep = users_of(ws, groups, [board.id], deep=True)
    assert [(u.kind, u.group_id) for u in deep[board.id]] == [("flow_board", board.id), ("stage", page.id)]


def test_library_entries_count_without_seeding(tmp_path: Path):
    ws, groups, *_ = _world(tmp_path)
    lib_path = ws.story_dir / "library.json"
    assert not lib_path.exists()
    all_users(ws)
    assert not lib_path.exists()                                          # a read never seeds (writes) the library
    pics = groups.create("Dusk pictures")
    atomic_write_json(lib_path, {"schema_version": 1, "entries": [{"id": "lib_1", "field": "lighting", "name": "dusk", "text": "violet dusk", "group_id": pics.id}],
                                 "revision": 1})
    assert [(u.kind, u.name, u.extra) for u in all_users(ws)[pics.id]] == [("library", "dusk", "lighting")]
    assert read_json(lib_path)["revision"] == 1


def test_route(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.get("/groups/used-by").status_code == 409                                    # no project
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "U", "size_cap_gb": 10})
        g = cl.post("/groups", json={"name": "Mara refs"}).json()
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        vg = p["versions"][0]["group_id"]
        assert set(cl.get("/groups/used-by").json()) == {vg}
        r = cl.get("/groups/used-by", params={"ids": [vg, g["id"]]}).json()
        assert r[g["id"]] == [] and r[vg] == [{"kind": "profile_ref", "id": p["id"], "name": "Mara", "extra": "v1", "version": "v1", "cls": "character", "group_id": vg}]
        assert cl.get("/groups/used-by", params={"ids": [vg], "deep": True}).json()[vg][0]["kind"] == "profile_ref"
        cl.post("/project/close")
