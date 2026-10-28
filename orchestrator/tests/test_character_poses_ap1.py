"""AP1b (D141, proto01_UIcast 06 §2.9): a character's own poses — *Save for ‹character›* keeps a pose fitted in Animate's pose editor (its
joints, the drop that stands it on its feet, its pins) on the character version; a new version takes them along; only a character has
them; a pose's pins name a hand or a foot and hold a point."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.stages import Pose  # noqa: E402

from test_skeleton_bench_cs2 import _client  # noqa: E402

CROUCH = {"preset": "crouch", "joints": {"r_knee": [100.0, 0.0, 0.0]}, "extra": {}, "ground": 0.21, "pins": {"r_foot": [-0.1, 0.04, 0.2], "l_hand": [0.3, 0.5, 0.4]}}
HELD = {**CROUCH, "contacts": {"l_hand": {"object_id": "self", "joint": "root"}}, "gaze": {"camera": True}}   # AP1b, the rest


def test_a_pose_pin_is_a_hand_or_a_foot_at_a_point():
    assert Pose.model_validate(CROUCH).pins["r_foot"] == [-0.1, 0.04, 0.2]
    assert Pose().pins == {} and Pose().ground == 0.0                                                 # a stage written before AP1 reads as it was
    for bad in ({"r_knee": [0, 0, 0]}, {"r_foot": [0, 0]}):
        with pytest.raises(ValueError):
            Pose(pins=bad)


def test_a_pin_can_be_held_to_a_thing_or_a_joint_and_the_figure_can_look_at_something():
    """AP1b, the rest (06 §2.9): a contact names the frame a pin is read in (a thing, or a figure's joint — "self" its own); a gaze names
    what the head turns to; a stage from before reads with neither; a joint that is not one of the figure's is refused."""
    p = Pose.model_validate(HELD)
    assert p.contacts["l_hand"].object_id == "self" and p.contacts["l_hand"].joint == "root" and p.gaze is not None and p.gaze.camera
    assert Pose.model_validate(CROUCH).contacts == {} and Pose.model_validate(CROUCH).gaze is None
    assert Pose.model_validate({**HELD, "gaze": {"object_id": "obj_x", "joint": "head"}}).gaze.joint == "head"
    for bad in ({"l_hand": {"object_id": "obj_x", "joint": "nose"}}, {"r_knee": {"object_id": "obj_x"}}, {"l_hand": {"joint": "root"}}):
        with pytest.raises(ValueError):
            Pose(contacts=bad)
    with pytest.raises(ValueError):
        Pose(gaze={"camera": "yes please"})


def test_a_character_keeps_its_own_poses(tmp_path: Path):
    _, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        p = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        r = cl.put(f"/story/profiles/{p['id']}/versions/v1/poses/crouch", json=CROUCH)
        assert r.status_code == 200, r.text
        assert r.json()["versions"][0]["poses"]["crouch"] == {**CROUCH, "contacts": {}, "gaze": None}
        r = cl.put(f"/story/profiles/{p['id']}/versions/v1/poses/{'hands on hips'}", json={**CROUCH, "preset": "stand", "pins": {}})
        assert sorted(r.json()["versions"][0]["poses"]) == ["crouch", "hands on hips"]                # a name of its own, spaces and all
        again = cl.post(f"/story/profiles/{p['id']}/versions").json()                                  # a new version (a costume): the poses go along
        assert sorted(again["versions"][1]["poses"]) == ["crouch", "hands on hips"]
        r = cl.delete(f"/story/profiles/{p['id']}/versions/v1/poses/crouch")
        assert r.status_code == 200 and sorted(r.json()["versions"][0]["poses"]) == ["hands on hips"]
        assert sorted(r.json()["versions"][1]["poses"]) == ["crouch", "hands on hips"]                # the other version's own
        assert cl.put(f"/story/profiles/{p['id']}/versions/v1/poses/crouch", json={**CROUCH, "pins": {"r_knee": [0, 0, 0]}}).status_code == 422
        assert cl.put(f"/story/profiles/{p['id']}/versions/v9/poses/crouch", json=CROUCH).status_code == 404
        prop = cl.post("/story/profiles", json={"name": "Box", "cls": "prop"}).json()
        assert cl.put(f"/story/profiles/{prop['id']}/versions/v1/poses/crouch", json=CROUCH).status_code == 422
