"""D34 groups: album pages, one placement per item, Unprocessed, group / ungroup / delete, duplicates, stale layout, repair,
collection migration, trash and purge, and the API surface (proto01_design/01 §6c, §8)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.catalogue import AssetQuery, Catalogue
from loom2.config import AppState
from loom2.groups import MARGIN, ROOT_ID, GroupStore, StaleGroup
from loom2.fsio import StateError, read_json
from loom2.workspace import Workspace


def _png(path: Path, w: int = 64, h: int = 32) -> Path:
    Image.new("RGB", (w, h), (10, 20, 30)).save(path)
    return path


def _setup(tmp_path: Path, n: int = 4) -> tuple[Workspace, Catalogue, GroupStore, list[str]]:
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32], session_id="ses_now")
    ids = [cat.ingest_file(_png(tmp_path / f"{i}.png"), prompt_text=f"shot {i}").id for i in range(n)]
    for i in ids:
        cat.make_thumbs(cat.get(i))
    return ws, cat, GroupStore(ws, cat), ids


def _unprocessed(cat: Catalogue) -> set[str]:
    return {a.id for a in cat.list(AssetQuery(folder="unprocessed")).items}


def test_unprocessed_and_one_placement(tmp_path: Path):
    ws, cat, st, ids = _setup(tmp_path)
    assert (ws.path / "groups" / "album.json").is_file()
    assert _unprocessed(cat) == set(ids)                                          # new items land in Unprocessed
    g1, g2 = st.create("Act 1"), st.create("Act 2")
    st.move([("asset", ids[0]), ("asset", ids[1])], g1.id)
    assert _unprocessed(cat) == {ids[2], ids[3]}
    assert cat.counts()["unprocessed"] == 2
    assert {a.id for a in cat.list(AssetQuery(group_id=g1.id)).items} == {ids[0], ids[1]}
    st.move([("asset", ids[0])], g2.id)                                           # moving takes it off the old page
    assert [it.id for it in st.groups[g1.id].items] == [ids[1]]
    assert st.where([ids[0], ids[3]]) == {ids[0]: {"group_id": g2.id, "path": [{"id": ROOT_ID, "name": "Album"}, {"id": g2.id, "name": "Act 2"}]}, ids[3]: None}
    st.move([("asset", ids[0])], None)                                            # back to Unprocessed
    assert ids[0] in _unprocessed(cat)
    with pytest.raises(StateError):
        st.move([("group", g1.id)], None)                                         # a group never goes to Unprocessed


def test_nesting_and_cycles(tmp_path: Path):
    _, _, st, _ = _setup(tmp_path, 0)
    a = st.create("A")
    b = st.create("B", parent_id=a.id)
    assert [c["name"] for c in st.tree()["children"]] == ["A"] and st.tree()["children"][0]["children"][0]["id"] == b.id
    with pytest.raises(StateError):
        st.move([("group", a.id)], b.id)                                          # not inside its own descendant
    with pytest.raises(StateError):
        st.move([("group", a.id)], a.id)
    with pytest.raises(StateError):
        st.move([("group", ROOT_ID)], a.id)
    st.move([("group", b.id)], ROOT_ID)
    assert {c["id"] for c in st.tree()["children"]} == {a.id, b.id}


def test_group_ungroup_keep_layout(tmp_path: Path):
    _, cat, st, ids = _setup(tmp_path, 3)
    page = st.create("Alley")
    st.move([("asset", i) for i in ids], page.id, [{"x": 100, "y": 200}, {"x": 400, "y": 260}, {"x": 900, "y": 900}])
    g = st.group_items(page.id, [("asset", ids[0]), ("asset", ids[1])], "Close-ups")
    inner = {it.id: (it.x, it.y) for it in st.groups[g.id].items}
    assert inner == {ids[0]: (MARGIN, MARGIN), ids[1]: (300 + MARGIN, 60 + MARGIN)}          # relative layout kept
    card = next(it for it in st.groups[page.id].items if it.kind == "group")
    assert (card.x, card.y) == (100, 200)                                          # the card takes their place
    assert {a.id for a in cat.list(AssetQuery(group_id=g.id)).items} == {ids[0], ids[1]}
    st.ungroup(g.id)
    back = {it.id: (it.x, it.y) for it in st.groups[page.id].items}
    assert back[ids[0]] == (100, 200) and back[ids[1]] == (400, 260)
    assert g.id not in st.groups and not (st.dir / f"{g.id}.json").exists()


def test_delete_returns_assets_to_unprocessed(tmp_path: Path):
    _, cat, st, ids = _setup(tmp_path, 3)
    outer = st.create("Outer")
    inner = st.create("Inner", parent_id=outer.id)
    st.move([("asset", ids[0])], outer.id)
    st.move([("asset", ids[1])], inner.id)
    freed = st.delete(outer.id)
    assert set(freed) == {ids[0], ids[1]}
    assert _unprocessed(cat) == set(ids)
    assert outer.id not in st.groups and inner.id not in st.groups
    assert all(cat.get(i).trashed_at is None for i in ids)                         # nothing is trashed


def test_duplicates(tmp_path: Path):
    ws, cat, st, ids = _setup(tmp_path, 2)
    page = st.create("Alley")
    st.move([("asset", ids[0])], page.id, [{"x": 50, "y": 60, "w": 300}])
    cat.patch(ids[0], {"tags": ["alley"], "rating": 4})
    [dup_id] = st.duplicate_assets([ids[0]])
    dup, orig = cat.get(dup_id), cat.get(ids[0])
    assert dup.duplicate_of == orig.id and dup.path != orig.path and cat.abs_path(dup).is_file()
    assert dup.tags == ["alley"] and dup.rating == 4 and dup.prompt_text == orig.prompt_text
    assert dup.parents == [] and dup.root_id == dup.id and cat.lineage(dup_id)["parents"] == []    # not lineage
    assert dup.thumb_status == "done" and ws.thumb_path(dup_id, 32).is_file()
    placed = next(it for it in st.groups[page.id].items if it.id == dup_id)
    assert (placed.x, placed.y, placed.w) == (74, 84, 300)                         # next to the original, same size
    [dup2] = st.duplicate_assets([ids[1]])                                         # an Unprocessed original: the copy stays Unprocessed
    assert dup2 in _unprocessed(cat)
    sub = st.create("Sub", parent_id=page.id)
    st.move([("asset", ids[1])], sub.id)
    copy = st.duplicate_group(page.id)
    assert copy.name == "Alley copy" and st.parent[("group", copy.id)] == ROOT_ID
    copied_assets = st._asset_ids(copy.id)
    assert len(copied_assets) == 3 and not set(copied_assets) & {ids[0], ids[1], dup_id}   # all new items
    assert any(it.kind == "group" and st.groups[it.id].name == "Sub" for it in st.groups[copy.id].items)


def test_stale_layout_and_persistence(tmp_path: Path):
    ws, cat, st, ids = _setup(tmp_path, 2)
    page = st.create("Alley")
    st.move([("asset", ids[0])], page.id)
    rev = st.groups[page.id].revision
    st.layout(page.id, [{"kind": "asset", "id": ids[0], "x": 10, "y": 20, "w": 320, "z": 5}], revision=rev)
    with pytest.raises(StaleGroup):
        st.layout(page.id, [{"kind": "asset", "id": ids[0], "x": 99}], revision=rev)
    st2 = GroupStore(ws, cat)                                                       # reopen: the files are the truth
    it = st2.groups[page.id].items[0]
    assert (it.x, it.y, it.w, it.z) == (10, 20, 320, 5)
    assert _unprocessed(cat) == {ids[1]}


def test_repair_double_placement(tmp_path: Path):
    ws, cat, st, ids = _setup(tmp_path, 1)
    a, b = st.create("A"), st.create("B")
    st.move([("asset", ids[0])], a.id)
    rec = read_json(st.dir / f"{b.id}.json")                                       # a hand edit places it on B too, more recently
    rec["items"].append({"kind": "asset", "id": ids[0], "x": 0, "y": 0, "w": 240, "z": 1})
    rec["updated_at"] = "2999-01-01T00:00:00+00:00"
    (st.dir / f"{b.id}.json").write_text(json.dumps(rec), encoding="utf-8")
    st2 = GroupStore(ws, cat)
    assert st2.parent[("asset", ids[0])] == b.id and not st2.groups[a.id].items


def test_collections_migrate_once(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32])
    ids = [cat.ingest_file(_png(tmp_path / f"{i}.png"), rating=i).id for i in range(3)]
    heroes = cat.collection_create("Heroes")
    cat.collection_add(heroes.id, [ids[0], ids[1]])
    alley = cat.collection_create("Alley")
    cat.collection_add(alley.id, [ids[1]])                                          # ids[1] is in two collections
    cat.collection_create("Rated", kind="smart", filter_={"rating_min": 2})        # ids[2]
    st = GroupStore(ws, cat)
    assert st.migrated == 3
    by_name = {g.name: g for g in st.groups.values()}
    assert {it.id for it in by_name["Heroes"].items} == {ids[0], ids[1]}           # the oldest keeps the original
    [alley_item] = by_name["Alley"].items
    assert cat.get(alley_item.id).duplicate_of == ids[1]                            # the other gets a duplicate
    assert {it.id for it in by_name["Rated"].items} == {ids[2]}
    assert {it.id for it in st.groups[ROOT_ID].items} == {g.id for g in by_name.values() if g.id != ROOT_ID}
    assert GroupStore(ws, cat).migrated == 0                                        # once


def test_trash_hides_and_purge_forgets(tmp_path: Path):
    _, cat, st, ids = _setup(tmp_path, 2)
    page = st.create("Alley")
    st.move([("asset", i) for i in ids], page.id)
    cat.trash([ids[0]])
    p = st.page(page.id)
    assert [it["id"] for it in p["group"]["items"]] == [ids[1]] and ids[0] not in p["assets"]
    assert ids[0] not in _unprocessed(cat)                                         # still placed while in Trash
    cat.restore([ids[0]])
    assert {it["id"] for it in st.page(page.id)["group"]["items"]} == set(ids)
    cat.trash([ids[0]])
    gone = cat.purge([ids[0]])
    st.forget_assets(gone)
    assert [it.id for it in st.groups[page.id].items] == [ids[1]]


def test_groups_api(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "m"), "mounted_model_trees": []})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "G", "size_cap_gb": 10}, headers=H)
        a = client.post("/assets/import", json={"paths": [str(_png(tmp_path / "a.png"))]}, headers=H).json()["items"][0]
        assert client.get("/assets/counts").json()["unprocessed"] == 1
        g = client.post("/groups", json={"name": "Act 1"}, headers=H).json()
        assert client.get("/groups/tree").json()["children"][0]["name"] == "Act 1"
        assert client.post("/groups/move", json={"items": [{"kind": "asset", "id": a["id"]}], "to": g["id"]}, headers=H).status_code == 200
        page = client.get(f"/groups/{g['id']}").json()
        assert page["path"][-1]["name"] == "Act 1" and a["id"] in page["assets"]
        assert client.get("/assets", params={"folder": "unprocessed"}).json()["total"] == 0
        assert client.get("/groups/where", params={"ids": [a["id"]]}).json()[a["id"]]["group_id"] == g["id"]
        rev = page["group"]["revision"]
        assert client.patch(f"/groups/{g['id']}/items", json={"revision": rev, "items": [{"kind": "asset", "id": a["id"], "x": 5, "y": 6}]}, headers=H).status_code == 200
        assert client.patch(f"/groups/{g['id']}/items", json={"revision": rev, "items": []}, headers=H).status_code == 409   # stale
        assert client.get("/groups/grp_nope").status_code == 404
        dup = client.post("/assets/duplicate", json={"ids": [a["id"]]}, headers=H).json()["ids"]
        assert len(client.get(f"/groups/{g['id']}").json()["assets"]) == 2 and dup[0] != a["id"]
        assert client.get(f"/lineage/tree/{a['id']}").json()["locations"][a["id"]]["group_id"] == g["id"]
        assert client.delete(f"/groups/{g['id']}", headers=H).json()["unprocessed"] == [a["id"], dup[0]]
        assert client.get("/assets/counts").json()["unprocessed"] == 2


def test_date_presets(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws, [32], session_id="ses_now")
    new = cat.ingest_file(_png(tmp_path / "n.png")).id
    old = cat.ingest_file(_png(tmp_path / "o.png"), created_at="2020-01-01T00:00:00+00:00", session_id="ses_old").id
    prev = cat.ingest_file(_png(tmp_path / "p.png"), created_at="2021-01-01T00:00:00+00:00", session_id="ses_prev").id
    assert {a.id for a in cat.list(AssetQuery(date_preset="today")).items} == {new}
    assert {a.id for a in cat.list(AssetQuery(date_preset="7d")).items} == {new}
    assert {a.id for a in cat.list(AssetQuery(date_preset="last_session")).items} == {prev}        # the latest session before this one
    assert old not in {a.id for a in cat.list(AssetQuery(date_preset="30d")).items}
