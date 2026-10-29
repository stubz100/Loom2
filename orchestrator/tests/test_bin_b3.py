"""B3 (D159 Q2, proto01_UI2 11 §5, R1): every album page in a home — once, at open (bins schema 3): a stage's page to the shot first made
through the stage, a board to its node's shot, a page nobody uses to the Sketches, the pages inside a page with it; a page is then a folder
of its home (the tree lists it, it opens on its own things, a thing moved into it stays there), and a new page asked for on the album's
root is made in the Sketches."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import BINS_SCHEMA_VERSION, home, home_page, migrate_bins, move_things, page_parent, stage_home, tree  # noqa: E402
from loom2.fsio import atomic_write_json, read_json_or  # noqa: E402
from loom2.groups import ROOT_ID  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_groups_d34 import _setup  # noqa: E402


def _home_of(groups, gid: str) -> str:
    """The path of the home a page sits in."""
    while gid in groups.groups:
        g = groups.groups[gid]
        if g.kind == "bin":
            return g.path or ""
        gid = groups.parent.get(("group", gid), "")
    return ""


def _find(nodes, gid):
    for n in nodes:
        if n["id"] == gid:
            return n
        f = _find(n["children"], gid)
        if f:
            return f
    return None


def test_the_pages_in_no_home_go_to_their_owners_once(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=6)
    st = StoryStore(ws)
    gate = st.create_node("shot", "Gate")
    time.sleep(1.1)                                                                     # a later second: Quay is the second shot made
    quay = st.create_node("shot", "Quay")
    stages = StageStore(ws)
    stay = stages.create("Stay")
    st.set_source(gate.shot_id, "v1", stay.id, stay.cameras[0].id, stay.revision)
    st.set_source(quay.shot_id, "v1", stay.id, stay.cameras[0].id, stay.revision)    # a second shot through the same stage
    page = groups.create(f"Stage · {stay.name}")                                        # the old way: on the album's root
    stages.set_passes(stay.id, {}, page.id)
    groups.move([("asset", ids[0]), ("asset", ids[1])], page.id)
    board = groups.create("Moodboard")
    groups.move([("asset", ids[2])], board.id)
    st.patch_node(quay.id, {"board_group_id": board.id})
    mine = groups.create("My picks")                                                    # the author's, used by nothing
    inner = groups.create("Close-ups", parent_id=mine.id)
    groups.move([("asset", ids[3])], inner.id)
    atomic_write_json(ws.path / "bins.json", {"schema_version": 2, "migrated_at": "2026-10-28T10:00:00Z"})   # U2's pages done
    notes = migrate_bins(ws, groups)
    assert any("3 album pages moved" in n for n in notes), notes                      # (and B4 homes the things on no page)
    assert _home_of(groups, page.id) == f"shots/{gate.shot_id}"                         # the shot first made through it
    assert _home_of(groups, board.id) == f"shots/{quay.shot_id}"
    assert _home_of(groups, mine.id) == "world/sketches" and groups.parent[("group", inner.id)] == mine.id   # with the page inside it
    assert read_json_or(ws.path / "bins.json", {})["schema_version"] == BINS_SCHEMA_VERSION >= 3                    # B4 is 4
    root = groups.groups[ROOT_ID]
    assert all(groups.groups[it.id].kind == "bin" for it in root.items if it.kind == "group")   # the root holds the homes only
    assert migrate_bins(ws, groups) == []                                               # once


def test_a_page_is_a_folder_of_its_home(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=4)
    sketches = home(groups, "world/sketches")
    mine = groups.create("My picks", parent_id=sketches.id)
    inner = groups.create("Close-ups", parent_id=mine.id)
    groups.move([("asset", ids[0])], sketches.id)
    groups.move([("asset", ids[1])], mine.id)
    groups.move([("asset", ids[2])], inner.id)
    t = tree(groups, ws)
    node = _find(t["homes"], sketches.id)
    folder = _find(t["homes"], mine.id)
    assert folder is not None and folder["page"] is True and folder["path"] == f"world/sketches/{mine.id}" and folder["name"] == "My picks"
    assert (folder["count"], folder["total"]) == (1, 2) and folder["children"][0]["id"] == inner.id
    assert node["total"] == 3                                                           # the home shows all below it, each once
    listing = home_page(groups, ws, mine.id)
    assert sorted(i["asset"].id for i in listing["items"]) == sorted([ids[1], ids[2]]) and listing["path"] == f"world/sketches/{mine.id}"
    assert {i["home_id"] for i in listing["items"]} == {sketches.id}
    assert len(home_page(groups, ws, sketches.id)["items"]) == 3
    out = move_things(groups, ws, [ids[3]], mine.id)                                    # into the page, not just its home
    assert out["moved"] == [ids[3]] and groups.parent[("asset", ids[3])] == mine.id


def test_new_pages_are_made_in_a_home(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=1)
    sketches = home(groups, "world/sketches")
    assert page_parent(groups, ROOT_ID) == sketches.id                                  # the album's root holds the homes only
    look = home(groups, "world/look")
    assert page_parent(groups, look.id) == look.id
    st = StoryStore(ws)
    stages = StageStore(ws)
    lone = stages.create("Lone")
    assert stage_home(groups, ws, lone).path == "world/sketches"                         # a stage no shot uses yet
    gate = st.create_node("shot", "Gate")
    st.set_source(gate.shot_id, "v1", lone.id, lone.cameras[0].id, lone.revision)
    assert stage_home(groups, ws, lone).path == f"shots/{gate.shot_id}"
