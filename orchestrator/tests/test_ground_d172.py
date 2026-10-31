"""D172 (E48, the market walk's M14 and E47's floor band): the ground outside a room is filled from above, its grazing part too.

- a road's, a pavement's and a corridor's or open ground's floor: a texel under a cosine of 0.35 is the Fill's; a room's floor keeps 0.05
  (stage/setBake.ts unseenCos is the twin);
- their lead: "A flat plan view of ‹material›, seen from directly above …", without the place's words; a room's floor keeps D143's.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_facade_d170 import baked_set, fill_selection  # noqa: E402


def test_the_ground_outside_a_room_has_its_own_cut():
    from loom2.place_sets import FACADE_COS, GROUND_COS, UNSEEN_COS, unseen_cos
    assert GROUND_COS == 0.35
    assert unseen_cos("road", "street") == unseen_cos("pavement_left", "street") == unseen_cos("floor", "corridor") == unseen_cos("floor", "ground") == GROUND_COS
    assert unseen_cos("floor", "room") == unseen_cos("floor") == unseen_cos("end", "street") == unseen_cos("wall_left", "corridor") == UNSEEN_COS
    assert unseen_cos("facade_right", "street") == FACADE_COS


def test_the_ground_is_painted_from_above():
    from loom2.place_sets import fill_prompt
    unnamed = fill_prompt("road", "", "a long row of fish stalls in an old covered market hall", "street")
    assert unnamed.startswith("A flat plan view of the road's surface, seen from directly above — no perspective, no walls, no ceiling, no people")
    assert "market hall" not in unnamed and "The place" not in unnamed                     # the place's words painted the hall's roof (E47)
    assert fill_prompt("pavement_right", "Wet grey stone paving slabs", "x", "street").startswith("A flat plan view of wet grey stone paving slabs")
    assert fill_prompt("floor", "", "a sandy beach", "ground").startswith("A flat plan view of the floor")
    assert fill_prompt("floor", "", "a farmhouse kitchen", "room").startswith("The floor, seen straight on: its surface continued plain")


def test_the_fill_takes_the_grazing_ground_of_a_street_not_of_a_room(tmp_path):
    """Through the routes: a road and a floor seen at a cosine of 0.2 on their right halves — in a street the road's Fill takes the whole
    face and paints it from above; in a room the floor's takes only its unseen half."""
    from test_skeleton_bench_cs2 import _client
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        street = baked_set(cl, svc, tmp_path, "street", 51, ("road",))
        sel, prompt = fill_selection(cl, svc, street, "road")
        assert sel.all() and prompt.startswith("A flat plan view of the road's surface")
        (tmp_path / "room").mkdir()
        room = baked_set(cl, svc, tmp_path / "room", "room", 51, ("floor",))
        sel, prompt = fill_selection(cl, svc, room, "floor")
        assert sel[:, :30].all() and not sel[:, 30:].any() and prompt.startswith("The floor, seen straight on")
