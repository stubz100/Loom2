"""RG3 (D187 R4, D188 F4; proto01_rig 00): the rigging screen's Hands and Feet & legs views — the server's part.

- *Fit again* on the CPU: a hand refitted to points the author dragged (a finger made longer) keeps its count, claws and widths and the
  points SDPose read beside; a foot refitted to a dragged toe keeps its stiff sole and its placement by hand, the floor the read kept;
- a foot placed by hand on the shell: its heel, ball and toe as metres from the ankle, validated;
- the route: 404 / 422 as the others.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from loom2.hands import FootShape, HandShape, Hands, fit_hand  # noqa: E402
from test_hands_rg1 import hand_points, person  # noqa: E402


def _store(tmp_path: Path):
    from loom2.story import StoryStore
    from test_groups_d34 import _setup
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    p = st.create_profile("Grisk", "character", groups, appearance="a ghoul")
    return st, p


def test_a_hand_refitted_to_dragged_points_keeps_what_the_author_set(tmp_path: Path):
    st, p = _store(tmp_path)
    pts = hand_points(HandShape(), palm_px=100)
    base = HandShape(count=4, claw=0.2)
    shape, report, read = fit_hand([person(pts)], None, base)
    shape = shape.model_copy(update={"fingers": {**shape.fingers, "index": shape.fingers["index"].model_copy(update={"width": 0.13})}})
    st.set_part_fit(p.id, "v1", "hand", shape=shape, points={"from": "ast_h", "canvas": [832, 480], "hand": read, "report": report})
    dragged = [list(q) for q in read]
    wrist, tip = dragged[0], dragged[12]
    for k in (10, 11, 12):                                                    # the middle finger's joints pulled out along it, its tip 30 % further
        f = (k - 9) / 3 * 0.3
        dragged[k] = [dragged[k][0] + (tip[0] - dragged[9][0]) * f, dragged[k][1] + (tip[1] - dragged[9][1]) * f, 1.0]
    p2 = st.refit_part(p.id, "v1", "hand", {"hand": dragged})
    v = p2.version("v1")
    hs = v.body.hand_shape.right
    assert sum(hs.fingers["middle"].lengths) == pytest.approx(0.73 * 1.3, abs=0.02)
    assert hs.count == 4 and hs.claw == 0.2 and hs.fingers["index"].width == 0.13          # the author's count, claws and widths stay
    assert v.hand_points["hand"][12][:2] == pytest.approx(dragged[12][:2], abs=0.01) and v.hand_points["sdpose"] == read
    assert v.hand_points["from"] == "ast_h"
    again = st.refit_part(p.id, "v1", "hand", {"hand": v.hand_points["sdpose"]}).version("v1")   # back to SDPose's
    assert sum(again.body.hand_shape.right.fingers["middle"].lengths) == pytest.approx(0.73, abs=0.01) and again.hand_points["sdpose"] == read
    with pytest.raises(ValueError, match="21 points"):
        st.refit_part(p.id, "v1", "hand", {"hand": dragged[:5]})


def test_a_foot_refitted_to_a_dragged_toe_keeps_its_sole_and_its_place(tmp_path: Path):
    from loom2.hands import Feet
    from loom2.body import Body
    st, p = _store(tmp_path)
    place = {"heel": [0.0, -0.03, -0.05], "ball": [0.0, -0.035, 0.1], "toe": [0.0, -0.03, 0.16]}
    shape = FootShape(stiff=True, place=place)
    st.patch_profile(p.id, {"versions": [{"id": "v1", "body": Body(foot_shape=Feet(right=shape)).model_dump()}]})
    heel, big, small = [300.0, 400.0, 0.9], [404.0, 400.0, 0.9], [396.0, 401.0, 0.8]
    st.set_part_fit(p.id, "v1", "feet", shape=shape, points={"from": "ast_f", "canvas": [832, 480], "foot": [big, small, heel], "ankle": [318.0, 370.0, 0.9], "leg": None, "floor": 412.0})
    p2 = st.refit_part(p.id, "v1", "feet", {"foot": [[404.0, 412.0, 1.0], small, heel], "ankle": [318.0, 370.0, 0.9], "floor": 412.0})   # the toe dragged down
    f = p2.version("v1").body.foot_shape.right
    assert f.pitch == pytest.approx(math.degrees(math.atan2(12, 104)), abs=0.1)
    assert f.heel_up == pytest.approx(12 / math.dist((404, 412), (300, 400)), abs=0.002)   # over the floor the read kept
    assert f.stiff is True and f.place == place
    assert p2.version("v1").feet_points["sdpose"]["foot"][0] == big


def test_a_foot_placed_by_hand_is_validated():
    ok = FootShape(place={"heel": [0, -0.03, -0.05], "ball": [0.01, -0.04, 0.1], "toe": [0, -0.03, 0.17]})
    assert ok.place["ball"] == [0.01, -0.04, 0.1]
    with pytest.raises(ValueError, match="heel, its ball and its toe"):
        FootShape(place={"heel": [0, 0, 0]})
    with pytest.raises(ValueError, match="at most 0.6"):
        FootShape(place={"heel": [0, 0, 0], "ball": [0, 0, 0.9], "toe": [0, 0, 0.2]})
    assert Hands().left is None


def test_the_refit_route(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": []})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        p = cl.post("/story/profiles", json={"name": "Grisk", "cls": "character", "appearance": "a ghoul"}).json()
        pts = [[float(x), float(y), 1.0] for x, y, _ in hand_points(HandShape())]
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/parts/hand/refit", json={"points": {"hand": pts}})
        assert r.status_code == 200, r.text
        assert r.json()["versions"][0]["body"]["hand_shape"]["right"]["count"] == 5
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/parts/feet/refit", json={"points": {"foot": []}}).status_code == 422
        assert cl.post(f"/story/profiles/{p['id']}/versions/v9/parts/hand/refit", json={"points": {"hand": pts}}).status_code == 404
        assert cl.post(f"/story/profiles/prf_none/versions/v1/parts/hand/refit", json={"points": {"hand": pts}}).status_code == 404
