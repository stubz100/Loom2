"""C6 (D181, propo02 04 §4.7; 05 Q12, Q13): the Bin's kinds.

- the vocabulary is closed: every lineage kind the orchestrator writes is in kinds.LINEAGE_KINDS with a shelf each, and an ingest with a
  stranger is refused;
- a thing's shelf: its lineage kind's, else its asset kind's in the class of its home (a picture in a shot's home is a still, a video there a
  take; a mask is a working file anywhere, Q13);
- the tree's third level: each home's shelves with their counts, from the index (no manifest read); a home's listing filtered to one shelf;
  the search names the kind of what it finds.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import home, home_items, search, tree, version_home  # noqa: E402
from loom2.kinds import LINEAGE_KINDS, SHELF_OF_LINEAGE, SHELF_ORDER, home_class, shelf_of, shelf_sql  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_bin_u8 import _flat  # noqa: E402
from test_groups_d34 import _png, _setup  # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "loom2"


def test_the_vocabulary_is_closed():
    written = set()
    for p in SRC.rglob("*.py"):
        if p.name == "kinds.py":
            continue
        text = p.read_text(encoding="utf-8")
        written.update(re.findall(r'lineage_kind="([a-z0-9-]+)"', text))
        written.update(re.findall(r'"lineage_kind":\s*"([a-z0-9-]+)"', text))          # a kind written as a dict's entry
    assert written and written <= set(LINEAGE_KINDS), sorted(written - set(LINEAGE_KINDS))      # a job cannot land outside the shelves
    assert set(SHELF_OF_LINEAGE.values()) <= set(SHELF_ORDER)
    assert shelf_of("stage-pass", "image", "shot") == "passes" and shelf_of("set-fill", "image", "place") == "set" and shelf_of("animatic", "video", "shot") == "animatic"
    assert shelf_of(None, "image", "shot") == "stills" and shelf_of(None, "image", "character") == "pictures" and shelf_of(None, "video", "shot") == "takes"
    assert shelf_of(None, "mask", "place") == "working" and shelf_of(None, "audio", "character") == "voice" and shelf_of(None, "mesh", "prop") == "model"
    assert home_class("shots/sht_1/v1") == "shot" and home_class("world/character/prf_1/v1") == "character" and home_class("world/sketches") == "sketches" and home_class("imports") == "imports"
    frag, args = shelf_sql("stills", "shot")
    assert "lineage_kind IN" in frag and "frame-extract" in args and "lineage_kind IS NULL AND kind IN" in frag and "image" in args
    assert shelf_sql("nowhere", "shot") == ("0", [])


def test_an_ingest_outside_the_vocabulary_is_refused(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=1)
    with pytest.raises(ValueError, match="not in the Bin's vocabulary"):
        cat.ingest_file(_png(tmp_path / "x.png"), lineage_kind="set-mystery")
    ok = cat.ingest_file(_png(tmp_path / "y.png"), lineage_kind="set-fill")
    assert ok.lineage_kind == "set-fill" and cat.get(ok.id).lineage_kind == "set-fill"


def test_the_trees_kinds_the_shelf_filter_and_the_search(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=4)
    st = StoryStore(ws)
    quay = st.create_profile("Quay", "place", groups, hero_asset_id=ids[0])
    vh = version_home(groups, quay, "v1")
    fill = cat.ingest_file(_png(tmp_path / "fill.png"), lineage_kind="set-fill", prompt_text="the quay's wall filled")
    bake = cat.ingest_file(_png(tmp_path / "bake.png"), lineage_kind="set-bake")
    mask = cat.ingest_file(_png(tmp_path / "cov.png"), kind="mask", lineage_kind=None)
    groups.move([("asset", fill.id), ("asset", bake.id), ("asset", mask.id), ("asset", ids[1])], vh.id)
    gate = st.create_node("shot", "Gate")
    sh = home(groups, f"shots/{gate.shot_id}/v1", {f"shots/{gate.shot_id}": "Gate", f"shots/{gate.shot_id}/v1": "v1"})
    still = cat.ingest_file(_png(tmp_path / "still.png"), prompt_text="the gate at dawn")
    passes = cat.ingest_file(_png(tmp_path / "depth.png"), lineage_kind="stage-pass")
    groups.move([("asset", still.id), ("asset", passes.id), ("asset", ids[2])], sh.id)
    t = tree(groups, ws)
    by = _flat(t["homes"])
    place = by[f"world/place/{quay.id}/v1"]
    assert [(k["id"], k["count"]) for k in place["kinds"]] == [("pictures", 2), ("set", 2), ("working", 1)]   # the hero and a candidate; the fill and the bake; the mask (Q13)
    shot = by[f"shots/{gate.shot_id}/v1"]
    assert [(k["id"], k["count"]) for k in shot["kinds"]] == [("stills", 2), ("passes", 1)]                 # pictures in a shot's home are stills
    assert by["world"]["kinds"] == [] or all(k["count"] for k in by["world"]["kinds"])                     # a heading counts nothing of its own
    # one shelf of a home
    assert {x["asset"].id for x in home_items(groups, ws, vh.id)["items"]} == {ids[0], ids[1], fill.id, bake.id, mask.id}
    from loom2.bins import home_page
    only = home_page(groups, ws, vh.id, limit=100, shelf="set")["items"]
    assert {x["asset"].id for x in only} == {fill.id, bake.id} and {x["shelf"] for x in only} == {"set"}
    assert {x["asset"].id for x in home_page(groups, ws, sh.id, limit=100, shelf="stills")["items"]} == {still.id, ids[2]}
    assert {x["asset"].id for x in home_page(groups, ws, sh.id, limit=100, shelf="passes")["items"]} == {passes.id}
    assert home_page(groups, ws, vh.id, limit=100, shelf="takes")["items"] == []
    # every thing says its shelf; the search names the kind of what it finds
    shelves = {x["asset"].id: x["shelf"] for x in home_items(groups, ws, by["world"]["id"])["items"]}
    assert shelves[fill.id] == "set" and shelves[mask.id] == "working" and shelves[ids[0]] == "pictures"
    found = {x["asset"].id: x["shelf"] for x in search(groups, "quay")["items"]}
    assert found == {fill.id: "set"}
    assert {x["asset"].id: x["shelf"] for x in search(groups, "gate")["items"]} == {still.id: "stills"}
