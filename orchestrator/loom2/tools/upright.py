"""D109 (spike E28c): a model made from one image (Pixal3D, P18) is built in the reference camera's frame, so a reference seen from above
gives a model tilted by that view's elevation — E28c's chest leaned 21° and tumbled as it turned, its door came out 0.4 m thick into the
wall. Every image → mesh result is stood upright before it enters the Catalogue: the tilt about x and z (within ±45°, so it is never
laid on a side) and the turn about y (±45°) giving the smallest upright bounding box, searched at 5° and refined at 1°, are written into
the GLB's mesh nodes as their rotation. A plain GLB reader and writer: the JSON chunk changes, the binary chunk is copied as it is.
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

import numpy as np

GLB_MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942


def read_glb(path: Path) -> tuple[dict, bytes]:
    b = path.read_bytes()
    magic, _version, _total = struct.unpack_from("<III", b, 0)
    if magic != GLB_MAGIC:
        raise ValueError(f"{path.name} is not a binary glTF")
    n, kind = struct.unpack_from("<II", b, 12)
    if kind != JSON_CHUNK:
        raise ValueError(f"{path.name}: the first chunk is not JSON")
    doc = json.loads(b[20:20 + n])
    off = 20 + n
    binary = b""
    if off + 8 <= len(b):
        bn, bkind = struct.unpack_from("<II", b, off)
        if bkind == BIN_CHUNK:
            binary = b[off + 8:off + 8 + bn]
    return doc, binary


def write_glb(path: Path, doc: dict, binary: bytes) -> None:
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary = binary + b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + (8 + len(binary) if binary else 0)
    out = struct.pack("<III", GLB_MAGIC, 2, total) + struct.pack("<II", len(js), JSON_CHUNK) + js
    if binary:
        out += struct.pack("<II", len(binary), BIN_CHUNK) + binary
    path.write_bytes(out)


def quat_to_matrix(q: list[float]) -> np.ndarray:
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def matrix_to_quat(m: np.ndarray) -> list[float]:
    """A rotation matrix as glTF's [x, y, z, w]."""
    t = float(np.trace(m))
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, s / 4]
    i = int(np.argmax(np.diag(m)))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2
    q = [0.0, 0.0, 0.0, 0.0]
    q[i] = s / 4
    q[j] = (m[j, i] + m[i, j]) / s
    q[k] = (m[k, i] + m[i, k]) / s
    q[3] = (m[k, j] - m[j, k]) / s
    return q


def euler(a: float, b: float, c: float) -> np.ndarray:
    """Rz(c) · Ry(b) · Rx(a), degrees."""
    a, b, c = (math.radians(v) for v in (a, b, c))
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


def _positions(doc: dict, binary: bytes, mesh: int) -> np.ndarray:
    pts = []
    for prim in doc["meshes"][mesh]["primitives"]:
        acc = doc["accessors"][prim["attributes"]["POSITION"]]
        if acc.get("componentType") != 5126 or acc.get("type") != "VEC3" or "bufferView" not in acc:
            raise ValueError("positions that are not plain float VEC3 (a sparse or compressed GLB)")
        bv = doc["bufferViews"][acc["bufferView"]]
        start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = bv.get("byteStride") or 12
        n = acc["count"]
        raw = np.frombuffer(binary, np.uint8, count=stride * (n - 1) + 12, offset=start)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(n, 12), strides=(stride, 1))
        pts.append(np.ascontiguousarray(rows).view(np.float32).reshape(-1, 3))
    return np.concatenate(pts).astype(np.float64)


def node_points(doc: dict, binary: bytes) -> tuple[list[int], np.ndarray]:
    """The mesh nodes (each a root's direct mesh, as image → mesh writes them) and their points through each node's scale, rotation and
    translation. A node with a full matrix, or a mesh under a parent node, is refused (not what Pixal3D writes)."""
    nodes = doc.get("nodes", [])
    parents = {c for nd in nodes for c in nd.get("children", [])}
    idx, pts = [], []
    for i, nd in enumerate(nodes):
        if "mesh" not in nd:
            continue
        if "matrix" in nd or i in parents:
            raise ValueError("a mesh node with a matrix or a parent")
        p = _positions(doc, binary, nd["mesh"]) * np.array(nd.get("scale", [1, 1, 1]))
        if "rotation" in nd:
            p = p @ quat_to_matrix(nd["rotation"]).T
        pts.append(p + np.array(nd.get("translation", [0, 0, 0])))
        idx.append(i)
    if not idx:
        raise ValueError("no mesh node")
    return idx, np.concatenate(pts)


def best_turn(pts: np.ndarray, samples: int = 4000) -> tuple[np.ndarray, list[float]]:
    """The rotation (and its x, y, z angles) giving the smallest upright bounding box: x and z within ±45°, y within ±45°. Ties go to the
    smallest turn (a millionth of the box per degree), so a flat or already-upright mesh is left as it is."""
    rng = np.random.default_rng(0)
    p = pts[rng.choice(len(pts), min(samples, len(pts)), replace=False)]
    unit = float(np.linalg.norm(p.max(axis=0) - p.min(axis=0))) ** 3 * 1e-6
    best: tuple[float, tuple[float, float, float]] = (math.inf, (0.0, 0.0, 0.0))
    for step, span, centre in ((5.0, 45.0, (0.0, 0.0, 0.0)), (1.0, 5.0, None)):
        c0 = centre if centre is not None else best[1]
        grids = [np.arange(c0[k] - span, c0[k] + span + 1e-6, step) for k in range(3)]
        for a in grids[0]:
            for b in grids[1]:
                for c in grids[2]:
                    q = p @ euler(a, b, c).T
                    v = float(np.prod(q.max(axis=0) - q.min(axis=0))) + unit * (abs(a) + abs(b) + abs(c))
                    if v < best[0]:
                        best = (v, (float(a), float(b), float(c)))
    return euler(*best[1]), [round(x, 1) for x in best[1]]


def figure_box(matte: Path) -> list[int] | None:
    """CS2 (E36): where the figure stands in its picture — the bounding box of the image → mesh graph's own BiRefNet matte (the cut-out
    Pixal3D was given, at the picture's size): [x0, y0, x1, y1, width, height] in the picture's pixels; None for an empty matte."""
    from PIL import Image
    with Image.open(matte) as im:
        a = np.asarray(im.convert("L")) > 127
    ys, xs = np.nonzero(a)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1, int(a.shape[1]), int(a.shape[0])]


def set_scene_extras(path: Path, data: dict) -> None:
    """Write `data` under the GLB's scene `extras.loom2` (three's GLTFLoader gives it as the scene's userData.loom2)."""
    doc, binary = read_glb(path)
    scenes = doc.setdefault("scenes", [{"nodes": [i for i, nd in enumerate(doc.get("nodes", []))]}])
    sc = scenes[doc.get("scene", 0)]
    sc.setdefault("extras", {}).setdefault("loom2", {}).update(data)
    write_glb(path, doc, binary)


def undo_upright(path: Path, angles: list[float]) -> None:
    """CS2 (E36): the turn stand_upright wrote (its x, y, z angles) taken back. A character's shell is made front-on from an upright
    reference, and the smallest upright box tilts a figure that holds its arms out — E36's six A-pose shells leaned 12–44°."""
    doc, binary = read_glb(path)
    idx, _ = node_points(doc, binary)
    back = euler(*angles).T
    for i in idx:
        nd = doc["nodes"][i]
        r = back @ (quat_to_matrix(nd["rotation"]) if "rotation" in nd else np.eye(3))
        if np.allclose(r, np.eye(3), atol=1e-6):
            nd.pop("rotation", None)
        else:
            nd["rotation"] = [round(float(v), 7) for v in matrix_to_quat(r)]
        if "translation" in nd:
            nd["translation"] = [round(float(v), 7) for v in back @ np.array(nd["translation"], float)]
    write_glb(path, doc, binary)


def stand_upright(path: Path) -> list[float]:
    """Rewrite the GLB with its mesh nodes turned upright; the angles (x, y, z degrees) applied."""
    doc, binary = read_glb(path)
    idx, pts = node_points(doc, binary)
    turn, angles = best_turn(pts)
    if any(abs(a) > 0.05 for a in angles):
        for i in idx:
            nd = doc["nodes"][i]
            r = quat_to_matrix(nd["rotation"]) if "rotation" in nd else np.eye(3)
            nd["rotation"] = [round(float(v), 7) for v in matrix_to_quat(turn @ r)]
            if "translation" in nd:
                nd["translation"] = [round(float(v), 7) for v in turn @ np.array(nd["translation"], float)]
        write_glb(path, doc, binary)
    return angles
