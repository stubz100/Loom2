"""B1 (D159, proto01_UI2 11 §3): one thing as the Bin shows it — its home and its roles (Imports when it is on no page) — and what uses it:
an entity version (its hero, an A-pose), a shot version (its frame, a take)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import home, move_things, settle, thing, uses_of, version_home  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_groups_d34 import _setup  # noqa: E402


def test_a_thing_with_its_home_and_what_uses_it(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=4)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    vh = version_home(groups, ines, "v1")
    groups.move([("asset", ids[1])], vh.id)
    st.set_anim_ref(ines.id, "v1", "front", ids[1])
    imports = home(groups, "imports")
    t = thing(groups, ws, ids[0])
    assert t is not None and (t["roles"], t["home_id"], t["path"]) == (["hero"], vh.id, vh.path)
    assert thing(groups, ws, ids[1])["roles"] == ["a_pose_front"]
    loose = thing(groups, ws, ids[3])
    assert loose is not None and (loose["roles"], loose["home_id"], loose["path"]) == ([], imports.id, "imports")
    assert thing(groups, ws, "ast_none") is None
    # what uses it: Ines's v1 names her hero; a shot names a take and its frame
    assert [(u["kind"], u["id"], u["version"], u["role"]) for u in uses_of(ws, ids[0])] == [("version", ines.id, "v1", "hero")]
    gate = st.create_node("shot", "Gate")
    st.add_take(gate.shot_id, "v1", "image", ids[2], use=True)
    assert [(u["kind"], u["name"], u["role"]) for u in uses_of(ws, ids[2])] == [("shot", "Gate v1", "frame")]
    st.add_take(gate.shot_id, "v1", "image", ids[3], use=False)
    assert [u["role"] for u in uses_of(ws, ids[3])] == ["take"]
    assert uses_of(ws, "ast_none") == []


def test_things_put_into_an_entity_or_a_shot_go_to_its_current_version(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=3)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups)
    vh = version_home(groups, ines, "v1")
    entity = groups.groups[groups.parent[("group", vh.id)]]                     # world/character/<Ines>
    assert settle(groups, ws, entity.id).id == vh.id and settle(groups, ws, vh.id).id == vh.id
    gate = st.create_node("shot", "Gate")
    sv = home(groups, f"shots/{gate.shot_id}/v1")
    assert settle(groups, ws, groups.parent[("group", sv.id)]).id == sv.id
    world = home(groups, "world")
    assert settle(groups, ws, world.id) is None and settle(groups, ws, home(groups, "world/character").id) is None
    out = move_things(groups, ws, [ids[0]], entity.id)                          # into her current version, where World reads it
    assert out["moved"] == [ids[0]] and thing(groups, ws, ids[0])["path"] == vh.path
    with pytest.raises(ValueError):                                             # a heading takes nothing
        move_things(groups, ws, [ids[1]], world.id)
