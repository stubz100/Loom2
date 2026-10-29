"""B4 (D159 Q4, proto01_UI2 11 §5): no thing on no page — a job's things no owner takes go to where a free thing lives (Image's free work
to the Sketches, a stage's with the shot made through it, a look-preset swatch to the Look, a quick start beside its picture), an import to
Imports; the unplaced things are moved once (bins schema 4: a set builder's bake to its place's version, a render whose record is gone to
the Sketches), and a stray at each open."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.bins import BINS_SCHEMA_VERSION, free_home, home_of, land, migrate_bins, version_home  # noqa: E402
from loom2.fsio import atomic_write_json, read_json_or  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from test_groups_d34 import _setup  # noqa: E402


def _at(groups, aid: str) -> str:
    h = home_of(groups, groups.parent.get(("asset", aid)))
    return h.path if h is not None else ""


def test_a_jobs_things_no_owner_takes_land_where_free_things_live(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=6)
    st = StoryStore(ws)
    assert land(groups, ws, {"suite": "generate", "surface": "panel", "ref": None, "payload": {}}, [ids[0]]).path == "world/sketches"
    assert land(groups, ws, {"suite": "generate", "surface": "swatch", "ref": "34a4", "payload": {}}, [ids[1]]).path == "world/look"
    stages = StageStore(ws)
    stay = stages.create("Stay")
    gate = st.create_node("shot", "Gate")
    st.set_source(gate.shot_id, "v1", stay.id, stay.cameras[0].id, stay.revision)
    assert land(groups, ws, {"suite": "stage", "surface": "shot", "ref": stay.id, "payload": {}}, [ids[2]]).path == f"shots/{gate.shot_id}"
    ines = st.create_profile("Ines", "character", groups)
    vh = version_home(groups, ines, "v1")
    groups.move([("asset", ids[3])], vh.id)
    assert land(groups, ws, {"suite": "catalogue", "surface": "start", "ref": ids[3], "payload": {}}, [ids[4]]).id == vh.id   # beside its picture
    assert land(groups, ws, {"suite": "generate", "surface": "panel"}, [ids[5]], free=False) is None and ("asset", ids[5]) not in groups.parent
    assert free_home(groups, ws, None).path == "world/sketches"


def test_the_unplaced_things_are_moved_once_and_strays_at_each_open(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path, n=4)
    atomic_write_json(ws.path / "bins.json", {"schema_version": 3, "migrated_at": "2026-10-29T10:00:00Z", "pages_homed": 0})
    notes = migrate_bins(ws, groups)
    assert any(n.startswith("B4: 4 things on no page went to a home") for n in notes), notes
    assert all(("asset", a) in groups.parent for a in ids)                             # nothing on no page
    assert _at(groups, ids[1]) == "world/sketches"
    assert read_json_or(ws.path / "bins.json", {})["schema_version"] == BINS_SCHEMA_VERSION == 4
    assert migrate_bins(ws, groups) == []                                               # once
    groups.move([("asset", ids[2])], None)                                              # a stray: a route left it on no page
    assert migrate_bins(ws, groups) == ["B4: 1 thing on no page went to a home (world/sketches 1)"]
    assert _at(groups, ids[2]) == "world/sketches"
