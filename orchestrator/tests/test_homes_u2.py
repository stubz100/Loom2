"""U2e (D157, G1): every creation lands in the home of what it was made for — a shot version's (made for it, a final made for it, a line's
voice), a profile version's (a Cast job: the set fit, the anim test …). A job's assets that no page took go there when it completes; the
Unprocessed assets of before are sorted by their origin once; Image's free work stays unplaced (U8 retires Unprocessed with the Catalogue)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import land, migrate_bins, owner_home  # noqa: E402
from loom2.fsio import atomic_write_json, read_json  # noqa: E402
from loom2.story import FOR_SHOT, StoryStore  # noqa: E402

from test_groups_d34 import _png, _setup  # noqa: E402


def test_assets_land_in_their_owners_home(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    gate = st.create_node("shot", "Gate", lines=[{"speaker": None, "text": "Open it."}])
    pier = st.create_profile("Harbour pier", "place", groups)
    for_shot = {"suite": "generate", "surface": FOR_SHOT, "ref": None, "payload": {"shot_id": gate.shot_id, "version": "v1"}}
    h = owner_home(groups, ws, for_shot)
    assert h is not None and h.path == f"shots/{gate.shot_id}/v1" and groups.groups[groups.parent[("group", h.id)]].name == "Gate"
    assert owner_home(groups, ws, {"suite": "story", "surface": "set_fit", "ref": pier.id, "payload": {"version": "v1"}}).path == f"world/place/{pier.id}/v1"
    assert owner_home(groups, ws, {"suite": "story", "surface": "voice", "ref": gate.id, "payload": {}}).path == f"shots/{gate.shot_id}/v1"
    assert owner_home(groups, ws, {"suite": "generate", "surface": "panel", "ref": None, "payload": {}}) is None        # Image's free work
    assert owner_home(groups, ws, {"suite": "story", "surface": "set_fit", "ref": "prf_gone", "payload": {}}) is None
    assert owner_home(groups, ws, None) is None
    # land: a loose asset goes home, one on a page stays where it is
    page = groups.create("Moodboard")
    groups.move([("asset", ids[1])], page.id)
    assert land(groups, ws, for_shot, [ids[0], ids[1]]).id == h.id
    assert groups.parent[("asset", ids[0])] == h.id and groups.parent[("asset", ids[1])] == page.id
    assert land(groups, ws, {"suite": "generate", "surface": "panel"}, [ids[2]]) is None and ("asset", ids[2]) not in groups.parent


def test_unprocessed_is_sorted_once(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    gate = st.create_node("shot", "Gate")
    made = cat.ingest_file(_png(tmp_path / "take.png"), origin={"suite": "generate", "surface": FOR_SHOT, "ref": None, "payload": {"shot_id": gate.shot_id, "version": "v1"}})
    free = cat.ingest_file(_png(tmp_path / "free.png"), origin={"suite": "generate", "surface": "panel", "ref": None, "payload": {}})
    atomic_write_json(groups.dir / "bins.json.corrupt-20261029-021718", {"schema_version": 1, "migrated_at": "2026-10-29T00:00:00Z", "pages": 0, "styles": 0, "boards": 0})   # U2d's run (moved aside by the album, U4)
    assert migrate_bins(ws, groups) == ["U2: 1 unprocessed asset went to the home of what it was made for"]
    assert groups.groups[groups.parent[("asset", made.id)]].path == f"shots/{gate.shot_id}/v1" and ("asset", free.id) not in groups.parent
    assert read_json(ws.path / "bins.json")["schema_version"] == 2 and migrate_bins(ws, groups) == []
    assert not list(groups.dir.glob("bins.json*"))                                          # the misfiled marks are gone from the album
