"""SC3d: a picture set laid level by its floor. MoGe gives the relief in the picture camera's frame, so a photograph taken looking down
(the rig's room, ≈ 7°) gives a floor that rises into the room; the floor fitted to the picture's lowest rows says by how much, and the set
is turned and raised so that floor is the stage floor (the figures stand on it), its picture camera pitched to match."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from loom2 import set_things
from loom2.relief import floor_fit, floor_height, floor_of_glb, glb_read, level_of_glb, levelling, mesh_arrays, subject_distance, to_stage
from loom2.stages import StageStore
from loom2.workspace import Workspace

from test_set_things_d123 import _glb, room_relief


def _floor_points(path: Path, pitch: float) -> np.ndarray:
    """The relief's points on the room's floor (y = −1 in the room; the camera's frame turned back by its pitch), near and far."""
    doc, binary = glb_read(path)
    pos, _, _ = mesh_arrays(doc, binary)
    c, s = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    return pos[np.abs(c * pos[:, 1] - s * pos[:, 2] + 1.0) < 1e-4]


@pytest.mark.parametrize("pitch", [-8.0, -3.0, 0.0, 5.0])
def test_pitch_recovered_and_the_floor_laid_on_the_stage(tmp_path: Path, pitch: float):
    path = tmp_path / "room.glb"
    room_relief(path, pitch_deg=pitch)
    lift = 1.0
    level = level_of_glb(path, lift)
    assert level is not None and abs(level["pitch_deg"] - pitch) < 0.2 and abs(level["roll_deg"]) < 0.2
    assert abs(level["rot"][0] - level["pitch_deg"]) < 0.01 and level["rot"][1:] == [0.0, 0.0]
    floor = _floor_points(path, pitch)
    assert len(floor) > 1000 and floor[:, 2].min() < -5.0                                 # near and far
    ys = np.array([to_stage(p, lift, level)[1] for p in floor[::7]])
    assert np.abs(ys).max() < 0.02                                                        # the floor is the stage floor, near and far
    cam = np.array(level["camera"]["pos"]); fwd = np.array(level["camera"]["target"]) - cam
    assert abs(cam[1] - 1.0) < 0.02 and fwd[1] == pytest.approx(math.sin(math.radians(pitch)), abs=0.005)   # a metre up, pitched as taken
    assert np.allclose(to_stage([0.0, 0.0, 0.0], lift, level), cam, atol=1e-4)           # the picture camera stands where the relief's origin went


def test_no_floor_or_too_steep_stays_as_it_came(tmp_path: Path):
    # a wall straight ahead fills the picture: its lowest rows are no floor
    u, v = np.meshgrid((np.arange(64) + 0.5) / 64, (np.arange(36) + 0.5) / 36)
    wall = np.stack([(u - 0.5) * 8, -(v - 0.5) * 4.5, np.full_like(u, -6.0)], axis=-1).reshape(-1, 3)
    uv = np.stack([u, v], axis=-1).reshape(-1, 2)
    p = tmp_path / "wall.glb"
    _glb(p, wall, uv, np.array([0, 1, 64]))
    assert level_of_glb(p, 1.0) is None
    # a "floor" at 40° (a slope, a staircase): fitted, but not laid level
    steep = {"a": 0.0, "b": math.tan(math.radians(40)), "c": -1.0, "points": 900, "residual": 0.0}
    assert levelling(steep, 1.0) is None
    assert levelling(steep | {"b": 0.1, "residual": 0.2}, 1.0) is None                    # a poor fit neither
    # the fake engine's triangle carries no UVs
    tri = tmp_path / "tri.glb"
    _glb(tri, np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float), None, np.array([0, 1, 2]))
    assert level_of_glb(tri, 1.0) is None
    assert floor_fit(np.zeros((10, 3)), np.ones((10, 2))) is None                           # too few points


def test_the_store_lays_the_set_level_and_a_rebuild_without_a_relief_does_not(tmp_path: Path):
    ws = Workspace.create(tmp_path / "proj", name="P", size_cap_gb=10)
    store = StageStore(ws)
    path = tmp_path / "room.glb"
    room_relief(path, pitch_deg=-7.0)
    st = store.add_image_set(store.create("Room").id, "ast_relief", "ast_pic", 70.0, -1.0, path)
    obj, cam = st.objects[-1], st.cameras[-1]
    assert obj.level is not None and abs(obj.level["pitch_deg"] + 7.0) < 0.2 and obj.level["residual"] < 0.01
    assert obj.transform.rot[0] == pytest.approx(obj.level["pitch_deg"], abs=0.01) and obj.transform.rot[1:] == [0.0, 0.0]
    assert 0.0 < obj.transform.pos[1] < 1.0 and abs(cam.pos[1] - 1.0) < 0.02 and cam.target[1] < cam.pos[1]
    doc, binary = glb_read(path)
    d = subject_distance(mesh_arrays(doc, binary)[0])
    assert math.dist(cam.pos, cam.target) == pytest.approx(d, abs=1e-3)                        # SC3e: it looks at the picture's subject distance
    again = store.get(st.id)                                                                  # it is in the file
    assert again.objects[-1].level == obj.level and again.objects[-1].transform == obj.transform
    st = store.replace_image_set(st.id, obj.id, "ast_relief_2", 75.0, -1.2)                   # no relief given: as it came
    obj, cam = st.objects[-1], st.cameras[-1]
    assert obj.level is None and obj.transform.pos == [0.0, 0.0, 0.0] and obj.transform.rot == [0.0, 0.0, 0.0]
    assert cam.pos == [0.0, 1.2, 0.0] and cam.target == [0.0, 1.2, -1.0]


def test_a_footprint_carried_to_the_clean_plates_relief(tmp_path: Path):
    """The clean plate's relief is the same room from the same camera at MoGe's scale of the moment: the footprint read on the relief the
    thing was picked on, carried by the ratio of the camera's heights, is the one the box would have there — and on its floor."""
    picked, clean, truth = tmp_path / "picked.glb", tmp_path / "clean.glb", tmp_path / "truth.glb"
    box = room_relief(picked, pitch_deg=-6.0)
    room_relief(clean, box=False, pitch_deg=-6.0, scale=1.15)
    room_relief(truth, pitch_deg=-6.0, scale=1.15)
    foot = set_things.footprint(picked, box, box, -1.0)
    dst = floor_of_glb(clean)
    assert floor_height(dst) == pytest.approx(1.15, abs=0.01) and floor_height(foot["floor"]) == pytest.approx(1.0, abs=0.01)
    moved = set_things.carried(foot, dst)
    want = set_things.footprint(truth, box, box, -1.15)
    assert moved["carried"] == pytest.approx(1.15, abs=0.01)
    for k in ("x", "y", "z", "width"):
        assert moved[k] == pytest.approx(want[k], abs=0.03), k
    assert moved["y"] == pytest.approx(dst["a"] * moved["x"] + dst["b"] * moved["z"] + dst["c"], abs=1e-9)      # on the clean floor


def test_the_picture_camera_looks_where_the_depth_pass_holds_the_picture(tmp_path: Path):
    """SC3e: Stage's depth pass spans 0.6× to 3× the camera's distance to its target; the picture camera's target is put where that span
    holds the relief's depths (a target 1 m ahead saturated the room, and the final's masks could not tell a prop from the set)."""
    path = tmp_path / "room.glb"
    room_relief(path, pitch_deg=-6.0)
    doc, binary = glb_read(path)
    pos = mesh_arrays(doc, binary)[0]
    z = -pos[:, 2]
    near, far = float(np.percentile(z, 2)), float(np.percentile(z, 98))
    d = subject_distance(pos)
    assert 0.6 * d <= near + 1e-3 and 3.0 * d >= far - 1e-3 and d > 1.5                             # the room's 2 % to 98 % inside the pass
    deep = np.c_[np.zeros(100), np.zeros(100), -np.linspace(1.0, 40.0, 100)]                          # deeper than one pass can hold: the near end
    assert subject_distance(deep) == pytest.approx(float(np.percentile(np.linspace(1.0, 40.0, 100), 2)) / 0.6, abs=1e-3)
    assert subject_distance(np.zeros((10, 3))) is None
