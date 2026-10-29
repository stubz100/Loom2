"""U8 (D157, proto01_UI2 05 §2): the Bin as a place — its tree of homes with their counts (a version's role pages folded into its home,
the things on no page shown in `imports`, the Trash's count), a home's things with their roles (a version's as World shows them, a shot
version's final, frame and clip; a parent shows everything below it), a search across every home with each thing's home, and a cut's
movie landing in the cut's own home."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import home, home_items, owner_home, search, subtree_pages, tree, version_home  # noqa: E402
from loom2.catalogue import AssetQuery  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import TimelineStore  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402


def _flat(nodes: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for n in nodes:
        out[n["path"]] = n
        out.update(_flat(n["children"]))
    return out


def test_the_bins_tree_items_and_search(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=6)
    st = StoryStore(ws)
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[0])
    vh = version_home(groups, ines, "v1")
    groups.move([("asset", ids[1])], vh.id)                                     # a candidate, in the version's home itself
    gate = st.create_node("shot", "Gate")
    sh = home(groups, f"shots/{gate.shot_id}/v1", {f"shots/{gate.shot_id}": "Gate", f"shots/{gate.shot_id}/v1": "v1"})
    groups.move([("asset", ids[2])], sh.id)
    st.add_take(gate.shot_id, "v1", "image", ids[2], use=True)                  # the shot's frame
    cat.trash([ids[3]])
    fog = cat.ingest_file(_png(tmp_path / "fog.png"), prompt_text="harbour fog at dawn")   # on no page, as ids[4] and ids[5]
    home(groups, "imports")
    t = tree(groups)
    by = _flat(t["homes"])
    assert [n["path"] for n in t["homes"]] == ["world", "shots", "imports"]                       # the Bin's order
    v = by[f"world/character/{ines.id}/v1"]
    assert (v["count"], v["name"], by["world"]["total"]) == (2, "v1", 2) and v["pages"]           # the reference set is a role inside it
    assert by[f"world/character/{ines.id}"]["name"] == "Ines" and by["world/character"]["name"] == "Characters"
    assert (by[f"shots/{gate.shot_id}"]["name"], by[f"shots/{gate.shot_id}/v1"]["count"], by["shots"]["total"]) == ("Gate", 1, 1)
    assert by["imports"]["count"] == 3 and t["trash"] == 1                                        # ids[4], ids[5], the fog; ids[3] trashed
    # a home's things with their roles; a parent shows everything below it
    it = {x["asset"].id: (x["roles"], x["path"]) for x in home_items(groups, ws, vh.id)["items"]}
    assert it == {ids[0]: (["hero"], vh.path), ids[1]: (["candidate"], vh.path)}
    assert {x["asset"].id: x["roles"] for x in home_items(groups, ws, sh.id)["items"]} == {ids[2]: ["frame"]}
    assert {x["asset"].id for x in home_items(groups, ws, by["world"]["id"])["items"]} == {ids[0], ids[1]}
    assert {x["asset"].id for x in home_items(groups, ws, by["imports"]["id"])["items"]} == {ids[4], ids[5], fog.id}
    # a search across every home, each thing with its home
    found = search(groups, "harbour")["items"]
    assert [(x["asset"].id, x["path"]) for x in found] == [(fog.id, "imports")]
    assert {x["path"] for x in search(groups, "shot")["items"]} >= {vh.path, sh.path, "imports"}
    # the Dock's drawer lists a home and everything under it through the catalogue (`home_id`, expanded by the route)
    pages, loose = subtree_pages(groups, by["world"]["id"])
    assert {a.id for a in cat.list(AssetQuery(group_ids=pages, unplaced_too=loose)).items} == {ids[0], ids[1]} and not loose
    pages, loose = subtree_pages(groups, by["imports"]["id"])
    assert loose and {a.id for a in cat.list(AssetQuery(group_ids=pages, unplaced_too=loose)).items} == {ids[4], ids[5], fog.id}
    # a cut's movie or draft lands in the cut's home
    tl = TimelineStore(ws).create("Episode 1")
    h = owner_home(groups, ws, {"suite": "animate", "surface": "sequence", "ref": tl.id, "payload": {}})
    assert h is not None and h.path == f"episode/{tl.id}" and h.name == "Episode 1"
