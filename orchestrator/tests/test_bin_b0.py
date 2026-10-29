"""B0 (D159, proto01_UI2 11 §4–5): a Bin that holds up — a home read a page at a time (a cursor, a kind filter, the total with the first
page), the tree counted from the index, homes named as their records are now and a deleted record's home marked gone (hidden when empty,
its things given to the Sketches), and *Move to…* asking before a thing loses a role (the record letting go of it when confirmed), refusing
when a record is made on it or its version is final."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import home, home_items, home_page, move_things, rehome, tree, version_home  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_bin_u8 import _flat  # noqa: E402
from test_groups_d34 import _setup  # noqa: E402


def test_a_home_is_read_a_page_at_a_time(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=7)
    sk = home(groups, "world/sketches")
    groups.move([("asset", a) for a in ids[:5]], sk.id)
    first = home_page(groups, ws, sk.id, limit=2)
    assert first["total"] == 5 and len(first["items"]) == 2 and first["next_cursor"]
    seen = [x["asset"].id for x in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        more = home_page(groups, ws, sk.id, cursor=cursor, limit=2)
        seen += [x["asset"].id for x in more["items"]]
        cursor = more["next_cursor"]
    assert sorted(seen) == sorted(ids[:5]) and len(seen) == 5                    # every thing once, newest first
    assert home_page(groups, ws, sk.id, kinds=["video"])["items"] == []          # the kind chips filter on the server
    assert len(home_page(groups, ws, sk.id, kinds=["image", "mask"])["items"]) == 5
    imp = home(groups, "imports")                                                # the things on no page, not capped at a page
    assert home_page(groups, ws, imp.id)["total"] == 2
    by = _flat(tree(groups, ws)["homes"])
    assert by["imports"]["count"] == 2 and by["world/sketches"]["count"] == 5    # the counts from the index
    assert cat.placed_counts()[sk.id] == 5
    cat.trash([ids[0]])
    assert _flat(tree(groups, ws)["homes"])["world/sketches"]["count"] == 4


def test_homes_follow_their_records(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=3)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    vh = version_home(groups, ines, "v1")
    groups.move([("asset", ids[1])], vh.id)
    st.patch_profile(ines.id, {"name": "Ines Varga"})
    by = _flat(tree(groups, ws)["homes"])
    assert by[f"world/character/{ines.id}"]["name"] == "Ines Varga"               # a rename shows at once
    assert not by[f"world/character/{ines.id}"]["gone"]
    st.delete_profile(ines.id, groups)
    by = _flat(tree(groups, ws)["homes"])
    gone = by[f"world/character/{ines.id}"]
    assert gone["gone"] and gone["total"] == 2                                    # deleted, its things still there
    out = rehome(groups, gone["id"])
    assert out["moved"] == 2
    by = _flat(tree(groups, ws)["homes"])
    assert f"world/character/{ines.id}" not in by and by["world/sketches"]["count"] == 2
    # a gone home with nothing left in it is not shown
    bob = st.create_profile("Bob", "character", groups)
    version_home(groups, bob, "v1")
    st.delete_profile(bob.id, groups)
    assert f"world/character/{bob.id}" not in _flat(tree(groups, ws)["homes"])


def test_move_asks_before_a_thing_loses_its_role(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=6)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    vh = version_home(groups, ines, "v1")
    groups.move([("asset", ids[1]), ("asset", ids[2])], vh.id)
    st.set_anim_ref(ines.id, "v1", "front", ids[2])
    sk = home(groups, "world/sketches")
    # a candidate moves; the hero and the A-pose are asked about and stay
    out = move_things(groups, ws, [ids[0], ids[1], ids[2]], sk.id)
    assert out["moved"] == [ids[1]] and {a["id"]: a["roles"] for a in out["ask"]} == {ids[0]: ["hero"], ids[2]: ["a_pose_front"]}
    assert st.profile(ines.id).versions[0].hero_asset_id == ids[0]
    # confirmed, they move and the record lets go of them
    out = move_things(groups, ws, [ids[0], ids[2]], sk.id, confirm=True)
    assert sorted(out["moved"]) == sorted([ids[0], ids[2]]) and out["records"] == [ines.id]
    v = st.profile(ines.id).versions[0]
    assert v.hero_asset_id is None and v.anim_ref_asset_id is None
    assert {x["asset"].id for x in home_items(groups, ws, sk.id)["items"]} == {ids[0], ids[1], ids[2]}
    # within its home a thing just moves (a candidate made a reference is World's, not a move out)
    groups.move([("asset", ids[3])], vh.id)
    out = move_things(groups, ws, [ids[3]], ines.versions[0].group_id)
    assert out["moved"] == [ids[3]] and not out["ask"]
    # a role a record is made on stays: a prop's 3D model
    cup = st.create_profile("Cup", "prop", groups, hero_asset_id=ids[4])
    ch = version_home(groups, cup, "v1")
    groups.move([("asset", ids[5])], ch.id)
    p = st.profile(cup.id)
    st.save_profile(p.model_copy(update={"versions": [p.versions[0].model_copy(update={"model_asset_id": ids[5]})]}))
    out = move_things(groups, ws, [ids[5]], sk.id, confirm=True)
    assert out["moved"] == [] and out["refused"][0]["role"] == "model"
    # a final version's hero stays
    st.lock_version(cup.id, "v1", groups)
    out = move_things(groups, ws, [ids[4]], sk.id, confirm=True)
    assert out["moved"] == [] and out["refused"][0]["why"] == "its version is final"


def test_a_shots_frame_is_let_go(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=2)
    st = StoryStore(ws)
    gate = st.create_node("shot", "Gate")
    sh = home(groups, f"shots/{gate.shot_id}/v1")
    groups.move([("asset", ids[0])], sh.id)
    st.add_take(gate.shot_id, "v1", "image", ids[0], use=True)
    assert st.shot(gate.shot_id).versions[0].frame_asset_id == ids[0]
    sk = home(groups, "world/sketches")
    assert move_things(groups, ws, [ids[0]], sk.id)["ask"][0]["roles"] == ["frame"]
    move_things(groups, ws, [ids[0]], sk.id, confirm=True)
    assert st.shot(gate.shot_id).versions[0].frame_asset_id is None
