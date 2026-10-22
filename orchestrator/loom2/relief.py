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
