"""proto01_UIcast CW6 (04 §3; E38): a place's set fitted to a picture — MoGe-2's metric point map read as a room, a corridor, a street or open
ground, with the camera that took the picture.

In the relief's frame (the picture camera at the origin looking down −Z, +Y up, D120): the floor (relief.floor_fit) gives the camera's
height, tilt and roll; the points are laid level (floor y = 0, the camera at (0, h, 0)); the walls are vertical planes found by RANSAC
among what stands above the floor, snapped to two square axes (a built room is square-cornered); the set's frame is turned so the wall
the camera faces is its back (−Z). The sizes come from the planes:

  · room: the side walls' distance (one side seen: the floor's extent on the other), the back wall's distance, the depth behind the
    camera a third of the room's in front (the picture never sees it, 04 §3), the height from a ceiling, else the walls' top when the
    picture sees it, else 3 m;
  · corridor: a room narrower than 3.2 m and at least twice as long as it is wide;
  · street: no back wall within 25 m and the side walls at least 5 m apart (façades), 30 m long (the default the author drags);
  · ground: no wall at all.

What the picture did not show is named in `assumed`, so the overlay (04 §3 step 4) can offer exactly those to drag. Pure numpy: the
synthetic rooms of the tests give the truth a picture cannot (E38 measures real pictures)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .relief import LEVEL_MAX_DEG, floor_fit, floor_height, focal_mm_for

WALL_MIN_SHARE = 0.03          # a vertical plane holding fewer of the standing points is clutter, not a wall
WALL_MAX_M = 25.0              # farther than this a vertical plane is a backdrop (E38: the field's hills read as 70 m walls)
WALL_MIN_TOP_M = 1.8           # a vertical plane ending lower is furniture or a fence
FLOOR_MIN_DROP_M = 0.5         # a floor closer under the camera than this is a misread (a band of wall), the lowest points tried instead
SNAP_DEG = 15.0                # a wall within this of the square axes is taken as square
STREET_MIN_WIDTH = 5.0
CORRIDOR_MAX_WIDTH = 3.2
DEFAULT_HEIGHT = {"room": 3.0, "corridor": 2.6, "street": 9.0}
DEFAULT_STREET_LENGTH = 30.0
DEFAULT_PAVEMENT = 2.0


def _rot_to_up(n: np.ndarray) -> np.ndarray:
    """The least rotation taking unit vector `n` to +Y (Rodrigues)."""
    up = np.array([0.0, 1.0, 0.0])
    v = np.cross(n, up)
    s, c = float(np.linalg.norm(v)), float(n @ up)
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


def _yaw(deg: float) -> np.ndarray:
    t = math.radians(deg)
    return np.array([[math.cos(t), 0.0, math.sin(t)], [0.0, 1.0, 0.0], [-math.sin(t), 0.0, math.cos(t)]])


def vertical_planes(q: np.ndarray, rng: np.random.Generator, max_planes: int = 5) -> list[dict[str, Any]]:
    """Vertical planes among level points `q` (y up): seeded RANSAC on pairs (the plane through them, containing +Y), inliers within a
    tolerance growing with distance from the camera (MoGe's noise does), the largest first; each refined by least squares on its own."""
    pts = q.copy()
    keep = np.ones(len(pts), bool)
    out: list[dict[str, Any]] = []
    total = len(pts)
    dist = np.hypot(pts[:, 0], pts[:, 2])
    tol = 0.03 + 0.012 * dist
    for _ in range(max_planes):
        idx = np.flatnonzero(keep)
        if len(idx) < max(200, WALL_MIN_SHARE * total):
            break
        probe = idx[rng.choice(len(idx), min(len(idx), 20000), replace=False)]
        best, best_n = None, 0
        for _ in range(400):
            a, b = pts[probe[rng.choice(len(probe), 2, replace=False)]]
            dx, dz = b[0] - a[0], b[2] - a[2]
            L = math.hypot(dx, dz)
            if L < 0.3:
                continue
            n = np.array([-dz / L, 0.0, dx / L])
            d = np.abs((pts[probe] - a) @ n)
            count = int((d <= tol[probe]).sum())
            if count > best_n:
                best, best_n = (a, n), count
        if best is None:
            break
        a, n = best
        inl = keep & (np.abs((pts - a) @ n) <= tol)
        if inl.sum() < max(200, WALL_MIN_SHARE * total):
            break
        # refine: the line in xz through the inliers (total least squares), the normal its perpendicular
        xz = pts[inl][:, [0, 2]]
        c = xz.mean(axis=0)
        _, _, vt = np.linalg.svd(xz - c, full_matrices=False)
        n = np.array([vt[1, 0], 0.0, vt[1, 1]])
        off = float(n[[0, 2]] @ c)
        if off > 0:                                           # the normal toward the camera (the origin, where n·x = 0 > off): the face we see
            n, off = -n, -off
        res = np.abs(pts[:, [0, 2]] @ n[[0, 2]] - off)
        inl = keep & (res <= tol)
        ys = pts[inl, 1]
        out.append({"normal": n, "offset": off, "points": int(inl.sum()), "share": round(float(inl.sum() / total), 3),
                    "top": float(np.percentile(ys, 99)) if len(ys) else 0.0, "residual": round(float(np.median(res[inl])), 4), "mask": inl})
        keep &= ~inl
    return out


def fit_set(pos: np.ndarray, uv: np.ndarray, lens_deg: float | None = None, seed: int = 0, camera_height_m: float | None = None) -> dict[str, Any]:
    """The set and camera a picture's point map shows (see the module). `camera_height_m`: the camera's height over the floor when the author
    knows it (eye level, 1.6 m, by default in the builder) — E38: MoGe-2's metric scale ran 1.06–2× short even on Stage's exact clay
    renders, so the scale comes from that height, before the sizes and the kind are read. Raises ValueError when the picture shows too little
    floor."""
    ok = np.isfinite(pos).all(axis=1)
    pos, uv = pos[ok], uv[ok]
    fl = floor_fit(pos, uv)
    if fl is not None and floor_height(fl) < FLOOR_MIN_DROP_M:
        # E38's corridor: a plane through the two walls' feet collected more points than the narrow floor — the floor is the lowest
        low = uv[:, 1] > 0.62
        if low.sum() > 200:
            fl = floor_fit(pos, uv, keep=pos[:, 1] <= float(np.percentile(pos[low, 1], 30)))
    if fl is None or floor_height(fl) < FLOOR_MIN_DROP_M or math.degrees(math.atan(math.hypot(fl["a"], fl["b"]))) > LEVEL_MAX_DEG:
        raise ValueError("the picture shows too little floor to stand a set on")   # a steep "floor" is a band of wall (as SC3's levelling says)
    scale = 1.0
    if camera_height_m:                                              # the scale from the camera's height (after the floor is read, its retry too)
        scale = camera_height_m / floor_height(fl)
        pos = pos * scale
        fl = {**fl, "c": fl["c"] * scale}
    h = floor_height(fl)
    n = np.array([-fl["a"], 1.0, -fl["b"]])
    n /= np.linalg.norm(n)
    if n[1] < 0:
        n = -n
    R = _rot_to_up(n)
    q = pos @ R.T + np.array([0.0, h, 0.0])                       # level: the floor at y = 0, the camera at (0, h, 0)
    fwd = R @ np.array([0.0, 0.0, -1.0])
    up = R @ np.array([0.0, 1.0, 0.0])
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, float(fwd[1])))))
    rng = np.random.default_rng(seed)
    standing = (q[:, 1] > 0.15)
    planes = vertical_planes(q[standing], rng) if standing.sum() > 200 else []
    on_wall = np.zeros(len(q), bool)
    st_idx = np.flatnonzero(standing)
    for p in planes:
        on_wall[st_idx[p["mask"]]] = True
    # a ceiling: what is left above the camera, off the walls, in one level band holding enough points spread over a square metre
    ceil_h = None
    above = (q[:, 1] > h + 0.3) & ~on_wall
    if above.sum() > 150:
        ys = q[above, 1]
        hist, edges = np.histogram(ys, bins=80)
        k = int(np.argmax(hist))
        guess = float((edges[k] + edges[k + 1]) / 2)
        band = above & (np.abs(q[:, 1] - guess) < 0.05 + 0.01 * np.hypot(q[:, 0], q[:, 2]))
        if band.sum() >= max(150, 0.015 * len(q)):
            xz = q[band][:, [0, 2]]
            if float(np.ptp(xz[:, 0])) * float(np.ptp(xz[:, 1])) >= 1.0:
                ceil_h = float(np.median(q[band, 1]))
    wall_pts = standing
    # a plane farther than WALL_MAX_M is a backdrop (hills, a skyline), and one ending below WALL_MIN_TOP_M furniture or a fence (E38: a
    # kitchen's cabinet fronts, the field's fence) — neither is a wall of the set
    planes = [p for p in planes if abs(p["offset"]) <= WALL_MAX_M and p["top"] >= WALL_MIN_TOP_M]
    # the square axes: the largest wall's normal and its perpendicular; others snapped to them or dropped
    walls: list[dict[str, Any]] = []
    if planes:
        ax = planes[0]["normal"]
        for p in planes:
            ang = math.degrees(math.atan2(p["normal"][2], p["normal"][0]) - math.atan2(ax[2], ax[0])) % 90.0
            if min(ang, 90.0 - ang) <= SNAP_DEG:
                walls.append(p)
    # the set's frame: of the four square turns the walls allow, the one that sets the camera looking most nearly down −Z (a room's wall
    # in front becomes its back; a street's façades its sides)
    yaw = 0.0
    if walls:
        base = math.degrees(math.atan2(walls[0]["normal"][0], walls[0]["normal"][2]))
        f2 = np.array([fwd[0], 0.0, fwd[2]])
        yaw = max((base + 90.0 * k for k in range(4)), key=lambda y: float(-(_yaw(-y) @ f2)[2]))
        yaw = (yaw + 180.0) % 360.0 - 180.0
    Y = _yaw(-yaw)
    qs = q @ Y.T
    cam = Y @ np.array([0.0, h, 0.0])
    fwd_s, up_s = Y @ fwd, Y @ up
    sides: dict[str, float] = {}
    for p in walls:
        nn = Y @ p["normal"]
        o = p["offset"]                                                # n·x = o in the level frame; the turn keeps the offset
        if abs(nn[2]) > abs(nn[0]):                                    # n·x = o, the normal toward the camera: the plane z = ±o
            key = "back" if nn[2] > 0 else "front"
            val = o if nn[2] > 0 else -o
        else:
            key = "left" if nn[0] > 0 else "right"
            val = o if nn[0] > 0 else -o
        p["side"], p["at"] = key, val
        if key not in sides or abs(val - cam[0 if key in ("left", "right") else 2]) < abs(sides[key] - cam[0 if key in ("left", "right") else 2]):
            sides[key] = val                                           # the nearest plane on each side bounds the space
    floor_pts = qs[(np.abs(qs[:, 1]) < 0.06)]
    assumed: list[str] = []
    # the extent on each side: a wall, else the floor's reach
    fx = floor_pts[:, 0] if len(floor_pts) else qs[:, 0]
    fz = floor_pts[:, 2] if len(floor_pts) else qs[:, 2]
    x_l = sides.get("left")
    x_r = sides.get("right")
    if x_l is None:
        x_l = float(np.percentile(fx, 2)); assumed.append("left")
    if x_r is None:
        x_r = float(np.percentile(fx, 98)); assumed.append("right")
    z_b = sides.get("back")
    width = x_r - x_l
    if not walls:
        kind = "ground"
    elif z_b is None or abs(z_b) > 25.0:
        kind = "street" if width >= STREET_MIN_WIDTH else "corridor"
    elif width <= CORRIDOR_MAX_WIDTH and abs(z_b) >= 2.0 * width:
        kind = "corridor"
    else:
        kind = "room"
    if z_b is None:
        z_b = float(np.percentile(fz, 2)); assumed.append("back")
    in_front = cam[2] - z_b                                         # the camera's distance to the back
    z_f = sides.get("front")
    if z_f is None:
        z_f = cam[2] + max(0.5, in_front / 3.0); assumed.append("front")
    tops = [p["top"] for p in walls]
    if ceil_h is not None:
        height = ceil_h
    elif tops and max(tops) > 1.0:
        top = max(tops)
        # the wall's top inside the picture (its points stop below the frame's top edge) is its height; at the edge it is a guess
        on_walls = np.zeros(int(wall_pts.sum()), bool)
        for p in walls:
            on_walls |= p["mask"]
        edge = float(uv[wall_pts][on_walls, 1].min()) if on_walls.any() else 0.0
        height = top if edge > 0.03 else max(top, DEFAULT_HEIGHT.get(kind, 3.0))
        if edge <= 0.03:
            assumed.append("height")
    else:
        height = DEFAULT_HEIGHT.get(kind, 3.0); assumed.append("height")
    centre = np.array([(x_l + x_r) / 2, 0.0, (z_b + z_f) / 2])
    if kind == "street":
        sizes = {"width": round(width, 3), "length": DEFAULT_STREET_LENGTH, "pavement": DEFAULT_PAVEMENT, "height_l": round(height, 3), "height_r": round(height, 3)}
        centre = np.array([(x_l + x_r) / 2, 0.0, cam[2] - DEFAULT_STREET_LENGTH / 6])   # the street runs 2/3 ahead, 1/3 behind (placeSet.ts)
        assumed += ["length", "pavement"]
    elif kind == "ground":
        sizes = {"size": 40.0, "backdrop": 30.0, "height": 12.0}
        centre = np.array([0.0, 0.0, 0.0])
    elif kind == "corridor":
        sizes = {"width": round(width, 3), "height": round(height, 3), "length": round(z_f - z_b, 3)}
    else:
        sizes = {"width": round(width, 3), "depth": round(z_f - z_b, 3), "height": round(height, 3)}
    cam_pos = cam - centre
    target = cam_pos + fwd_s
    roll = math.degrees(math.atan2(-float(np.cross(fwd_s, up_s) @ np.array([0.0, 1.0, 0.0])), float(up_s[1])))
    lens = lens_deg if lens_deg else 60.0
    return {
        "kind": kind, "sizes": sizes, "assumed": sorted(set(assumed)),
        "camera": {"pos": [round(float(v), 4) for v in cam_pos], "target": [round(float(v), 4) for v in target], "roll": round(roll, 2),
                   "focal_mm": focal_mm_for(lens), "sensor_mm": 36.0},
        "height_m": round(h, 4), "pitch_deg": round(pitch, 2), "yaw_deg": round(yaw, 2), "ceiling": ceil_h is not None, "scale": round(scale, 4),
        "walls": [{"side": p["side"], "at": round(float(p["at"] - (centre[0] if p["side"] in ("left", "right") else centre[2])), 3), "points": p["points"],
                   "share": p["share"], "residual": p["residual"]} for p in walls],
        "floor": {"share": fl["share"], "residual": fl["residual"]}, "lens_deg": round(lens, 2),
    }
