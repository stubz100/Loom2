"""D108: a set is architecture — a schema-1 stage whose set is the room or the street reads with the set's old blocks as `block` props,
where they stood (the set's position, yaw and scale applied), and a schema-2 stage reads unchanged."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.stages import STAGE_SCHEMA_VERSION, StageStore, migrate  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def v1(*objects: dict) -> dict:
    return {"schema_version": 1, "id": "stg_old", "objects": list(objects), "cameras": []}


def a_set(preset: str, pos=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), **kw) -> dict:
    return {"id": "set_a", "kind": "set", "name": "Set 1", "preset": preset, "colour_id": 1, "locked": True,
            "transform": {"pos": list(pos), "rot": list(rot), "scale": list(scale)}, **kw}


def test_room_blocks_become_props():
    out = migrate(v1(a_set("room"), {"id": "fig_1", "kind": "mannequin", "name": "Ada", "colour_id": 2}))
    assert out["schema_version"] == STAGE_SCHEMA_VERSION == 3                              # (CS1: 3 — the bodies and the figures read in the same pass)
    props = [o for o in out["objects"] if o["kind"] == "prop"]
    assert [p["preset"] for p in props] == ["block", "block"]
    assert props[0]["transform"]["pos"] == pytest.approx([1.9, 0.0, -1.8]) and props[0]["transform"]["scale"] == pytest.approx([1.2, 0.8, 0.8])
    assert props[1]["transform"]["pos"] == pytest.approx([0.0, 0.0, 0.0]) and props[1]["transform"]["scale"] == pytest.approx([0.45, 0.48, 0.45])
    assert {p["colour_id"] for p in props}.isdisjoint({1, 2}) and len({p["colour_id"] for p in props}) == 2
    assert all(p["locked"] for p in props)                                  # as locked as the set they came from


def test_a_moved_set_moves_its_blocks():
    out = migrate(v1(a_set("street", pos=(10, 0, 5), rot=(0, 90, 0), scale=(2, 2, 2))))
    (p,) = [o for o in out["objects"] if o["kind"] == "prop"]
    # the street's block foot (−3.2, 0, −2) scaled ×2 → (−6.4, 0, −4), turned 90° about y → (−4, 0, 6.4), then moved by (10, 0, 5)
    assert p["transform"]["pos"] == pytest.approx([6.0, 0.0, 11.4])
    assert p["transform"]["rot"] == [0.0, 90.0, 0.0] and p["transform"]["scale"] == pytest.approx([2.0, 4.4, 0.8])


def test_other_sets_and_new_documents_unchanged():
    for preset in ("deck", "empty"):
        assert [o["kind"] for o in migrate(v1(a_set(preset)))["objects"]] == ["set"]
    cur = {**v1(a_set("room")), "schema_version": STAGE_SCHEMA_VERSION}
    assert migrate(cur) is cur


def test_the_store_reads_old_files_migrated(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StageStore(ws)
    st.path("stg_old").write_text(json.dumps(v1(a_set("room"))), encoding="utf-8")
    s = st.get("stg_old")
    assert s is not None and s.schema_version == STAGE_SCHEMA_VERSION and [o.preset for o in s.objects] == ["room", "block", "block"]
    assert [x.id for x in st.list()] == ["stg_old"]
    s2 = st.put("stg_old", s.model_dump())                                   # the next save writes the current schema; nothing doubles
    assert [o.preset for o in s2.objects] == ["room", "block", "block"] and json.loads(st.path("stg_old").read_text(encoding="utf-8"))["schema_version"] == STAGE_SCHEMA_VERSION
