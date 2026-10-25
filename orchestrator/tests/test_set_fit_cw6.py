"""proto01_UIcast CW6 (04 §3): a set fitted to a picture's point map — synthetic pictures ray-cast in rooms, corridors and streets of known
size from known cameras (MoGe's frame: the camera at the origin looking down −Z), with depth noise as MoGe has; the fit gives back the
kind, the sizes it can see, the camera's height, tilt and place, and names what it had to assume."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.set_fit import fit_set  # noqa: E402


def cast(box: dict, cam: tuple[float, float, float], yaw: float, pitch: float, fov: float = 60.0, w: int = 192, h: int = 108, noise: float = 0.006,
         seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """A point map of a box (x0, x1, z0, z1, height; walls named in `box['open']` left out) seen from `cam` turned by yaw (degrees, 0 looks
    down −Z) and pitch (negative looks down): positions in the camera's frame, the picture's UVs."""
    t = math.tan(math.radians(fov) / 2)
    u, v = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h)
    d = np.stack([(u - 0.5) * 2 * t, -(v - 0.5) * 2 * t * h / w, -np.ones_like(u)], -1).reshape(-1, 3)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    cp, sp, cy, sy = math.cos(math.radians(pitch)), math.sin(math.radians(pitch)), math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    R = Ry @ Rx
    dw = d @ R.T
    o = np.asarray(cam, float)
    planes = [("floor", 1, 0.0), ("ceiling", 1, box["height"]), ("left", 0, box["x0"]), ("right", 0, box["x1"]), ("back", 2, box["z0"]), ("front", 2, box["z1"])]
    tbest = np.full(len(dw), np.inf)
    for name, ax, val in planes:
        if name in box.get("open", ()):
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = (val - o[ax]) / dw[:, ax]
        hit = o + tt[:, None] * dw
        inside = (tt > 1e-6) & (hit[:, 0] >= box["x0"] - 1e-6) & (hit[:, 0] <= box["x1"] + 1e-6) & (hit[:, 2] >= box["z0"] - 1e-6) & (hit[:, 2] <= box["z1"] + 1e-6) \
            & (hit[:, 1] >= -1e-6) & (hit[:, 1] <= box["height"] + 1e-6)
        tbest = np.where(inside & (tt < tbest), tt, tbest)
    ok = np.isfinite(tbest)
    rng = np.random.default_rng(seed)
    t_noisy = tbest * (1 + noise * rng.standard_normal(len(tbest)))
    pw = o + t_noisy[:, None] * dw
    with np.errstate(invalid="ignore"):
        pc = (pw - o) @ R                                              # into the camera's frame (a ray that hit nothing stays NaN)
    pc[~ok] = np.nan
    return pc.astype(np.float32), np.stack([u.ravel(), v.ravel()], -1).astype(np.float32)


def test_a_room_seen_from_its_front():
    room = {"x0": -2.5, "x1": 2.5, "z0": -5.0, "z1": 1.0, "height": 2.8}            # 5 m × 6 m × 2.8 m
    pos, uv = cast(room, (0.4, 1.6, 0.8), yaw=0.0, pitch=-8.0, fov=75.0)              # near the front wall, a wide lens: both side walls in view
    f = fit_set(pos, uv, 75.0)
    assert f["kind"] == "room"
    assert f["height_m"] == pytest.approx(1.6, abs=0.04) and f["pitch_deg"] == pytest.approx(-8.0, abs=1.0)
    assert f["sizes"]["width"] == pytest.approx(5.0, rel=0.04)
    cam_to_back = f["camera"]["pos"][2] + f["sizes"]["depth"] / 2
    assert cam_to_back == pytest.approx(5.8, rel=0.04)                              # the back wall's distance, as seen
    assert f["sizes"]["height"] == pytest.approx(2.8, rel=0.05)                     # a ceiling seen
    assert "front" in f["assumed"] and "left" not in f["assumed"] and "right" not in f["assumed"]
    assert f["camera"]["pos"][0] == pytest.approx(0.4, abs=0.1)                     # the camera's place across the room (the room centred)


def test_a_room_seen_askew_and_without_its_ceiling():
    room = {"x0": -3.0, "x1": 4.0, "z0": -6.0, "z1": 2.0, "height": 3.2, "open": ("ceiling",)}
    pos, uv = cast(room, (1.0, 1.4, 0.0), yaw=25.0, pitch=-4.0)
    f = fit_set(pos, uv, 60.0)
    assert f["kind"] == "room"
    assert abs(abs(f["yaw_deg"]) - 25.0) < 3.0 or abs(abs(f["yaw_deg"]) - 65.0) < 3.0   # square to the room's walls
    w, d = f["sizes"]["width"], f["sizes"]["depth"]
    assert min(abs(w - 7.0) / 7.0, abs(w - 8.0) / 8.0) < 0.08 or "left" in f["assumed"] or "right" in f["assumed"]


def test_a_corridor_and_a_street():
    corridor = {"x0": -1.0, "x1": 1.0, "z0": -12.0, "z1": 1.0, "height": 2.6}
    f = fit_set(*cast(corridor, (0.0, 1.6, 0.0), yaw=0.0, pitch=-3.0), 60.0)
    assert f["kind"] == "corridor" and f["sizes"]["width"] == pytest.approx(2.0, rel=0.06)
    street = {"x0": -6.0, "x1": 6.0, "z0": -60.0, "z1": 10.0, "height": 9.0, "open": ("ceiling", "back", "front")}
    f = fit_set(*cast(street, (1.0, 1.7, 0.0), yaw=0.0, pitch=2.0), 60.0)
    assert f["kind"] == "street" and f["sizes"]["width"] == pytest.approx(12.0, rel=0.06)
    assert "length" in f["assumed"] and "pavement" in f["assumed"]


def test_too_little_floor_says_so():
    room = {"x0": -5.0, "x1": 5.0, "z0": -1.0, "z1": 1.0, "height": 3.0}
    pos, uv = cast(room, (0.0, 1.6, 0.0), yaw=0.0, pitch=12.0)                       # a wall a metre away, looked at a little up: no floor in the picture
    with pytest.raises(ValueError, match="too little floor"):
        fit_set(pos, uv, 60.0)
