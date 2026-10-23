"""SC3 (D120): what a relief GLB says about the picture it was made from — E30's reading of MoGe's point map.

`MoGePointMapToMesh` writes the mesh in glTF coordinates (X right, Y up, Z back) with the camera that took the picture at the origin
looking down −Z, and the picture's own UVs; so the lens is in the vertices: a vertex at image position (u, v) sits at x / −z = (u − ½) / fx
with fx normalised by the width (the same for v and fy), and the floor's height under the camera is the lowest y the picture reaches.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np

CTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DEFAULT_LENS_DEG = 60.0                                   # when the GLB carries no UVs to read the lens from (a bare mesh)


def glb_read(path: Path) -> tuple[dict, bytes]:
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    doc = json.loads(b[20:20 + n])
    off = 20 + n
    bn = struct.unpack_from("<I", b, off)[0]
    return doc, b[off + 8:off + 8 + bn]


def accessor(doc: dict, binary: bytes, idx: int) -> np.ndarray:
    acc = doc["accessors"][idx]
    bv = doc["bufferViews"][acc["bufferView"]]
    ctype, ncomp = CTYPES[acc["componentType"]], NCOMP[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    item = np.dtype(ctype).itemsize * ncomp
    stride = bv.get("byteStride", item)
    if stride == item:
        return np.frombuffer(binary, ctype, count=acc["count"] * ncomp, offset=start).reshape(acc["count"], ncomp)
    raw = np.frombuffer(binary, np.uint8, count=stride * (acc["count"] - 1) + item, offset=start)
    return np.lib.stride_tricks.as_strided(raw, shape=(acc["count"], item), strides=(stride, 1)).copy().view(ctype).reshape(acc["count"], ncomp)


def mesh_arrays(doc: dict, binary: bytes) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    """The first primitive's positions, UVs (None without them) and triangles (None without an index)."""
    prim = doc["meshes"][0]["primitives"][0]
    pos = accessor(doc, binary, prim["attributes"]["POSITION"]).astype(np.float32)
    uv = accessor(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in prim["attributes"] else None
    idx = accessor(doc, binary, prim["indices"]).reshape(-1, 3) if "indices" in prim else None
    return pos, uv, idx


def lens_of(pos: np.ndarray, uv: np.ndarray) -> dict | None:
    """The lens (degrees, horizontal and vertical), the median depth, the depth range and the floor's height from the vertices."""
    z = -pos[:, 2]
    ok = np.isfinite(z) & (z > 1e-3) & np.isfinite(pos).all(axis=1)
    if ok.sum() < 16:
        return None
    x, y, u, v = pos[ok, 0], pos[ok, 1], uv[ok, 0], uv[ok, 1]
    z = z[ok]
    mx = np.abs(x) > 0.05 * z
    my = np.abs(y) > 0.05 * z
    if mx.sum() < 8 or my.sum() < 8:
        return None
    fx = float(np.median(np.abs((u[mx] - 0.5) * z[mx] / x[mx])))
    fy = float(np.median(np.abs((v[my] - 0.5) * z[my] / y[my])))
    if not (fx > 0 and fy > 0):
        return None
    return {"fov_x": round(math.degrees(2 * math.atan(0.5 / fx)), 2), "fov_y": round(math.degrees(2 * math.atan(0.5 / fy)), 2),
            "depth_median": round(float(np.median(z)), 3), "zrange": [round(float(np.percentile(z, 1)), 3), round(float(np.percentile(z, 99)), 3)],
            "y_floor": round(float(np.percentile(y, 2)), 3), "vertices": int(pos.shape[0])}


def lens_of_glb(path: Path) -> dict | None:
    """None when the GLB has no UVs to read the lens from (a bare mesh)."""
    doc, binary = glb_read(path)
    pos, uv, idx = mesh_arrays(doc, binary)
    if uv is None:
        return None
    out = lens_of(pos, uv)
    if out is not None:
        out["faces"] = int(idx.shape[0]) if idx is not None else 0
    return out


def focal_mm_for(lens_deg: float, sensor_mm: float = 36.0) -> float:
    """The focal length a Stage camera needs for a horizontal field of view on its sensor."""
    return round(sensor_mm / 2 / math.tan(math.radians(max(1.0, min(179.0, lens_deg)) / 2)), 1)


# ---- SC3d: a picture set levelled by its floor ---------------------------------------------------------------------------------------
LEVEL_MAX_DEG = 25.0                                       # a steeper "floor" is not one (a wall, a slope): the set stays as it came


def floor_fit(pos: np.ndarray, uv: np.ndarray, rows: float = 0.62, keep: np.ndarray | None = None) -> dict | None:
    """The floor plane y = a·x + b·z + c among the picture's lowest rows (v > `rows`; `keep` a vertex mask of the points it may use): a
    seeded RANSAC over near-level planes only (within LEVEL_MAX_DEG — the walls, a box's front and a cupboard in those rows are vertical
    and never the floor), its inliers within a tolerance growing with depth (MoGe's noise does), then least squares on them. None when the
    picture shows too little floor. In the relief's frame (the picture camera at the origin looking down −Z)."""
    ok = np.isfinite(pos).all(axis=1) & (uv[:, 1] > rows)
    if keep is not None:
        ok &= keep
    if ok.sum() < 200:
        return None
    p = pos[ok]
    rng = np.random.default_rng(0)
    probe = p[rng.choice(len(p), min(len(p), 20000), replace=False)]
    tol = lambda q: 0.02 + 0.01 * np.abs(q[:, 2])  # noqa: E731
    min_ny = math.cos(math.radians(LEVEL_MAX_DEG))
    best, best_n = None, 0
    for _ in range(256):
        a, b, c = probe[rng.choice(len(probe), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = float(np.linalg.norm(n))
        if norm < 1e-9 or abs(n[1]) / norm < min_ny:
            continue
        n = n / norm
        count = int((np.abs((probe - a) @ n) / abs(n[1]) <= tol(probe)).sum())
        if count > best_n:
            best, best_n = (a, n), count
    if best is None:
        return None
    a, n = best
    d = np.abs((p - a) @ n) / abs(n[1])
    inl = d <= tol(p)
    A = np.c_[p[:, 0], p[:, 2], np.ones(len(p))]
    for _ in range(3):                         # the band narrowed to the floor's own noise: a wall's foot within the tolerance pulls the far floor up
        inl = d <= np.minimum(tol(p), max(0.01, 2.5 * float(np.median(d[inl]))))
        if inl.sum() < 200:
            return None
        sol, *_ = np.linalg.lstsq(A[inl], p[inl, 1], rcond=None)
        d = np.abs(A @ sol - p[:, 1])
    return {"a": float(sol[0]), "b": float(sol[1]), "c": float(sol[2]), "points": int(inl.sum()), "share": round(float(inl.mean()), 3),
            "residual": round(float(np.median(d[inl])), 4)}


def levelling(fit: dict, lift: float) -> dict | None:
    """SC3d: the transform that lays the fitted floor level on the stage floor (y = 0) — a pitch about x (the photograph's camera looked up
    or down; a sideways tilt is small in photographs and left), after the set's own lift (`lift` = −floor_y) — and where the picture camera
    then stands and looks. None beyond LEVEL_MAX_DEG or when the fit is poor (the set stays as it came)."""
    phi = math.atan(fit["b"])                                                   # R_x(φ) takes the floor's normal (−a, 1, −b) to the yz-plane's up
    if abs(math.degrees(phi)) > LEVEL_MAX_DEG or fit["residual"] > 0.05:
        return None
    cphi, sphi = math.cos(phi), math.sin(phi)
    rot = lambda v: np.array([v[0], cphi * v[1] - sphi * v[2], sphi * v[1] + cphi * v[2]])  # noqa: E731
    # the floor's height after the turn: the plane sampled in the room, lifted and turned; the set raised so it lands on y = 0
    pts = [rot(np.array([x, fit["a"] * x + fit["b"] * z + fit["c"] + lift, z])) for x in (-1.0, 0.0, 1.0) for z in (-2.0, -4.0, -6.0)]
    pos_y = -float(np.mean([q[1] for q in pts]))
    cam = rot(np.array([0.0, lift, 0.0])) + np.array([0.0, pos_y, 0.0])
    fwd = rot(np.array([0.0, 0.0, -1.0]))
    return {"rot": [round(math.degrees(phi), 3), 0.0, 0.0], "pos": [0.0, round(pos_y, 4), 0.0],
            "camera": {"pos": [round(float(v), 4) for v in cam], "target": [round(float(v), 4) for v in cam + fwd]},
            "pitch_deg": round(math.degrees(phi), 2), "roll_deg": round(math.degrees(math.atan(fit["a"])), 2), "fit": fit}


def floor_of_glb(path: Path) -> dict | None:
    """SC3d: a relief's floor (see `floor_fit`), or None (no UVs, too little floor)."""
    doc, binary = glb_read(path)
    pos, uv, _ = mesh_arrays(doc, binary)
    return floor_fit(pos, uv) if uv is not None else None


def floor_height(fit: dict) -> float:
    """The picture camera's height over a fitted floor (the plane's distance from the relief's origin)."""
    return abs(fit["c"]) / math.sqrt(1.0 + fit["a"] ** 2 + fit["b"] ** 2)


def level_of_glb(path: Path, lift: float) -> dict | None:
    """SC3d: a relief's levelling (see `levelling`), or None (no UVs, too little floor, too steep)."""
    fit = floor_of_glb(path)
    return levelling(fit, lift) if fit else None


def subject_distance(pos: np.ndarray) -> float | None:
    """SC3e: how far a picture camera looks — the distance whose depth pass (Stage's `depthRange`: 0.6× to 3× the camera's distance to its
    target) holds the relief's depths, the nearest 2 % to the farthest 2 % (the geometric middle of the distances that do; the near end
    when none does: the things in front matter more). A target 1 m ahead saturated a room 1.4–6.5 m deep, so the final's depth passes
    could not tell a prop from the set (SC3e's rig). None without depths in front of the camera."""
    z = -pos[:, 2]
    z = z[np.isfinite(z) & (z > 1e-3)]
    if len(z) < 16:
        return None
    near, far = float(np.percentile(z, 2)), float(np.percentile(z, 98))
    lo, hi = far / 3.0, near / 0.6
    return round(math.sqrt(lo * hi) if lo <= hi else hi, 3)


def frame_of_glb(path: Path, lift: float) -> tuple[dict | None, float | None]:
    """SC3d / SC3e: a relief read once for its picture set — its levelling (see `levelling`) and its camera's subject distance (see
    `subject_distance`), either None when the relief cannot say."""
    doc, binary = glb_read(path)
    pos, uv, _ = mesh_arrays(doc, binary)
    fit = floor_fit(pos, uv) if uv is not None else None
    return (levelling(fit, lift) if fit else None), subject_distance(pos)


def to_stage(p: np.ndarray | list, lift: float, level: dict | None) -> np.ndarray:
    """A point of the relief's frame on the stage: lifted by the set's floor, then (SC3d) turned and raised as the set is."""
    v = np.array([float(p[0]), float(p[1]) + lift, float(p[2])])
    if not level:
        return v
    phi = math.radians(level["rot"][0])
    c, s = math.cos(phi), math.sin(phi)
    return np.array([v[0], c * v[1] - s * v[2], s * v[1] + c * v[2]]) + np.asarray(level["pos"], float)
