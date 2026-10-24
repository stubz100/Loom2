"""D129 (HP1, proto01_animate 31 §2): a held prop is its own thing in a figure's hand — `parent` the figure, `parent_joint` the hand, its
transform local to that hand. Only a prop (a 3D model, a stand-in, an image plane) is held, and only by a figure."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402


def test_what_can_be_held_and_by_whom(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        st = cl.post("/stages", json={"name": "Kitchen"}).json()
        fig = {"id": "fig_1", "kind": "mannequin", "name": "Mara", "preset": "adult"}
        room = {"id": "set_1", "kind": "set", "name": "Room", "preset": "room"}
        cup = {"id": "prop_1", "kind": "prop", "name": "Cup", "preset": "block", "parent": "fig_1", "parent_joint": "r_hand",
               "transform": {"pos": [0, -0.04, 0.03], "rot": [0, 0, 0], "scale": [0.1, 0.1, 0.1]}}
        r = cl.put(f"/stages/{st['id']}", json={**st, "objects": [fig, room, cup]})
        assert r.status_code == 200, r.text
        held = next(o for o in r.json()["objects"] if o["id"] == "prop_1")
        assert held["parent"] == "fig_1" and held["parent_joint"] == "r_hand" and held["transform"]["pos"] == [0, -0.04, 0.03]
        st = r.json()
        bad = [{**cup, "parent": "set_1"},                                          # a set holds nothing
               {**cup, "parent": None},                                             # a hand needs its figure
               {**fig, "id": "fig_2", "parent": "fig_1", "parent_joint": "l_hand"},  # a figure is not held
               {**cup, "parent_joint": "tail"}]                                     # two hands
        for b in bad:
            objs = [fig, room, b] if b["id"] != "fig_2" else [fig, room, b]
            assert cl.put(f"/stages/{st['id']}", json={**st, "objects": objs}).status_code == 422, b
        r = cl.put(f"/stages/{st['id']}", json={**st, "objects": [fig, room, {**cup, "parent": None, "parent_joint": None}]})
        assert r.status_code == 200 and next(o for o in r.json()["objects"] if o["id"] == "prop_1")["parent_joint"] is None   # let go
