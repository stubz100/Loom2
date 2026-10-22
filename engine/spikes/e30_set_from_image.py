"""E30 — a set from an image (D119, proto01_animate 25 §3): MoGe's relief and the cut-out props, measured on set images.

The author (2026-10-22): "we should be able to create 3D scenes from images." Today a set is architecture (D108's boxes) or a Cast prop
(Pixal3D, P18). Here an image of a place becomes a **relief**: MoGe-2 (the scene-depth model Pixal3D already carries, MIT) gives every
pixel a metric 3D point; the engine's MoGePointMapToMesh triangulates the point map into a textured mesh (the image as its texture); the
camera that took the picture sits at the origin looking down -Z with MoGe's own lens. The relief is then moved around in Three.js (the
Stage's renderer, frontend/src/spikes/e30Set.ts in Edge) and two things are counted per camera move over the frame:
the **holes** inside the picture (pixels no geometry covers — what was hidden behind something; the picture's own edge coming into the frame is counted apart) and the **smear** (pixels where
one texel is spread over more than three pixels — the rubber-sheet stretch at a depth jump). Their sum is the **tear**; the budget is the
largest move that keeps it small.

Arms:
  relief    the image as one relief: `cut` (MoGe's discontinuity threshold 0.04 — the mesh is cut at depth jumps, so a move opens honest
            holes) and `sheet` (threshold 0 — one rubber sheet, so a move stretches instead)
  props     D109's pipeline on the room: the free-standing things are cut from the picture (E28b's SAM 3 masks), the plate without them
            is the relief (E28b's clean room, D108) and each thing is its Pixal3D model (E28c's), stood on the relief at the footprint its
            mask has in the picture's point map, scaled to the width the point map gives its front edge; `room_holes` beside it is the picture's own
            relief with the things cut out and nothing behind them (why the clean plate matters)
Images (bench/sets/, frozen by `sources`): room (E22's plate: a crate, a stool block, a table, a big block), room_empty (E28b's clean
room), bare (PS5b's still), street (a Klein 9B still of an empty alley at night, new).
Moves: truck ±0.25 / 0.5 / 1 m, pedestal ±0.25 / 0.5 m, dolly −0.5 / −1 / +0.5 m, pan ±5 / 10 / 20° (about the camera itself: no
parallax, only the frame's edge), tilt ±5 / 10°, orbit ±10 / 20° about the scene's median depth (truck + counter-pan). Bars (25 §3): the
Draft frame at ±10° / ±0.5 m; tear ≤ 1 % clean, ≤ 3 % acceptable for a Draft shot.
Passes: beauty (the image re-projected — the plate of that camera), clay, depth — on the sheets for a few moves.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e30_set_from_image.py sources | relief [--images room,...] [--dec 2] | props | render | score
`sources` and `relief` need the engine (scripts/engine-start.ps1); `render` needs Vite dev on 1420 and the engine stopped (D97: one
GPU workload at a time — Edge renders with WebGL); `props` and `score` are offline. Outputs under engine/spikes/out/e30/ (git-ignored).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine, klein_t2i  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")        # the tables carry ≤ and °; the console is cp1252

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "bench" / "sets"
OUT = REPO / "engine" / "spikes" / "out" / "e30"
RELIEF = OUT / "relief"
VIEWS = OUT / "views"
ENGINE_OUT = REPO / "engine" / "comfyui_out"                                 # scripts/engine-start.ps1 --output-directory
E22 = REPO / "engine" / "spikes" / "out" / "e22"
E28B = REPO / "engine" / "spikes" / "out" / "e28b"
E28C = REPO / "engine" / "spikes" / "out" / "e28c"
PS5B = REPO / "engine" / "spikes" / "out" / "ps5b"
MOGE = "moge_2_vitl_normal_fp16.safetensors"                                 # roster moge2-vitl (MIT), F:/loom2-models/geometry_estimation
DEV = 1420
SIZE = (1024, 576)                                                           # the render frame (16:9, the Draft size's aspect)
IMAGES: dict[str, dict] = {
    "room": {"from": E22 / "stills" / "plate.png", "what": "E22's plate: a room with a crate, a stool block, a table and a big block"},
    "room_empty": {"from": E28B / "plate_empty.png", "what": "E28b's clean room: the same room with the things removed (D108)"},
    "bare": {"from": PS5B / "still.png", "what": "PS5b's still: a bare room, the window on the left"},
    "street": {"prompt": "An empty narrow cobbled alley at night after rain, old brick walls, a few neon shop signs, wet stones reflecting "
                         "the lights, no people, eye-level wide shot, cinematic.", "seed": 20261022,
               "what": "a Klein 9B still of an empty alley at night (made by `sources`)"},
}
THRESHOLDS = {"cut": 0.04, "sheet": 0.0}
PROPS = {"crate": "crate_up.glb", "block_stool": "block_stool_up.glb", "table": "table_up.glb", "block_big": "block_big_up.glb"}
SHEET = ["origin", "truck+0.5", "truck+1", "dolly-1", "orbit+10", "pan+10"]
CLEAN, OK = 1.0, 3.0                                                         # tear bars, % of the inner frame


def log(m: str) -> None:
    print(m, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "e30.log").open("a", encoding="utf-8") as f:
        f.write(time.strftime("%H:%M:%S ") + m + "\n")


# ---- sources ------------------------------------------------------------------------------------------------------------------------
def sources(a: argparse.Namespace) -> int:
    BENCH.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}
    for tag, spec in IMAGES.items():
        dest = BENCH / f"{tag}.jpg"                                                     # JPEG like bench/mesh (E14): the frozen input stays small
        if "from" in spec:
            Image.open(spec["from"]).convert("RGB").save(dest, quality=95)
            meta[tag] = {"from": str(spec["from"].relative_to(REPO)).replace("\\", "/"), "what": spec["what"]}
        else:
            eng = Engine(a.server)
            h, _, ex = eng.run(klein_t2i(spec["prompt"], spec["seed"]))
            eng.image(h, "10").save(dest, quality=95)
            meta[tag] = {"model": "flux-2-klein-9b", "seed": spec["seed"], "prompt": spec["prompt"], "what": spec["what"], "exec_s": round(ex, 1)}
            log(f"{tag}: Klein still in {ex:.1f} s")
        log(f"{tag}: {Image.open(dest).size} <- {meta[tag].get('from', 'Klein')}")
    (BENCH / "sets.json").write_text(json.dumps({"made_by": "engine/spikes/e30_set_from_image.py sources", "images": meta}, indent=1) + "\n", encoding="utf-8")
    return 0


# ---- relief (the engine) -------------------------------------------------------------------------------------------------------------
def relief_graph(image_name: str, thr: float, dec: int, tag: str) -> dict:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "LoadMoGeModel", "inputs": {"model_name": MOGE}},
        "3": {"class_type": "MoGeInference", "inputs": {"moge_model": ["2", 0], "image": ["1", 0], "resolution_level": 9, "fov_x_degrees": 0.0,
                                                        "batch_size": 1, "force_projection": True, "apply_mask": True, "refine_steps": 0}},
        "4": {"class_type": "MoGePointMapToMesh", "inputs": {"moge_geometry": ["3", 0], "batch_index": 0, "decimation": dec,
                                                             "discontinuity_threshold": thr, "texture": True}},
        "5": {"class_type": "GetMeshInfo", "inputs": {"mesh": ["4", 0]}},
        "6": {"class_type": "SaveGLB", "inputs": {"mesh": ["5", 0], "filename_prefix": f"e30/{tag}"}},
        "7": {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["3", 0], "output": "depth"}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": f"e30/{tag}_depth"}},
        "9": {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["3", 0], "output": "normal_opengl"}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": f"e30/{tag}_normal"}},
        "11": {"class_type": "MoGeRender", "inputs": {"moge_geometry": ["3", 0], "output": "mask"}},
        "12": {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"e30/{tag}_mask"}},
    }


def glb_read(path: Path) -> tuple[dict, bytes]:
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    doc = json.loads(b[20:20 + n])
    off = 20 + n
    bn = struct.unpack_from("<I", b, off)[0]
    return doc, b[off + 8:off + 8 + bn]


def glb_write(path: Path, doc: dict, binary: bytes) -> None:
    js = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


CTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


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
    """The first primitive's positions (glTF: X right, Y up, Z back; the camera at the origin), UVs and triangles."""
    prim = doc["meshes"][0]["primitives"][0]
    pos = accessor(doc, binary, prim["attributes"]["POSITION"]).astype(np.float32)
    uv = accessor(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in prim["attributes"] else None
    idx = accessor(doc, binary, prim["indices"]).reshape(-1, 3) if "indices" in prim else None
    return pos, uv, idx


def lens_of(pos: np.ndarray, uv: np.ndarray) -> dict:
    """MoGe's lens from the point map: a vertex at image position (u, v) sits at x / -z = (u - ½) / fx (fx normalised by the width),
    so fx is the median ratio over the vertices away from the centre; the same for fy; the median depth for the orbit's pivot."""
    z = -pos[:, 2]
    ok = np.isfinite(z) & (z > 1e-3)
    x, y, u, v = pos[ok, 0], pos[ok, 1], uv[ok, 0], uv[ok, 1]
    z = z[ok]
    mx = np.abs(x) > 0.05 * z
    my = np.abs(y) > 0.05 * z
    fx = float(np.median(np.abs((u[mx] - 0.5) * z[mx] / x[mx])))
    fy = float(np.median(np.abs((v[my] - 0.5) * z[my] / y[my])))
    return {"fx_norm": round(fx, 4), "fy_norm": round(fy, 4), "fov_x": round(math.degrees(2 * math.atan(0.5 / fx)), 2),
            "fov_y": round(math.degrees(2 * math.atan(0.5 / fy)), 2), "depth_median": round(float(np.median(z)), 3),
            "zrange": [round(float(np.percentile(z, 1)), 3), round(float(np.percentile(z, 99)), 3)],
            "y_floor": round(float(np.percentile(y, 2)), 3)}


def relief(a: argparse.Namespace) -> int:
    eng = Engine(a.server)
    RELIEF.mkdir(parents=True, exist_ok=True)
    rows = []
    for img in a.images.split(","):
        src = BENCH / f"{img}.jpg"
        name = eng.upload(src)
        for arm in a.arms.split(","):
            tag = f"{img}_{arm}" + (f"_d{a.dec}" if a.dec != 2 else "")
            g = relief_graph(name, THRESHOLDS[arm], a.dec, tag)
            h, wall, ex = eng.run(g, timeout=1800)
            st = h.get("status", {})
            if st.get("status_str") != "success":
                log(f"{tag}: FAILED {json.dumps(st.get('messages', [])[-1:])[:400]}")
                continue
            files = [f for o in h["outputs"].values() for v in o.values() if isinstance(v, list) for f in v if isinstance(f, dict) and str(f.get("filename", "")).endswith(".glb")]
            if not files:
                log(f"{tag}: no GLB in the outputs: {json.dumps(h['outputs'])[:300]}")
                continue
            f = files[0]
            glb = ENGINE_OUT / f.get("subfolder", "") / f["filename"]
            dest = RELIEF / f"{tag}.glb"
            shutil.copyfile(glb, dest)
            for node, kind in (("8", "depth"), ("10", "normal"), ("12", "mask")):
                eng.image(h, node).save(RELIEF / f"{tag}_{kind}.png")
            doc, binary = glb_read(dest)
            pos, uv, idx = mesh_arrays(doc, binary)
            lens = lens_of(pos, uv)
            stats = eng.http.get("/system_stats", timeout=30).json()
            dev = (stats.get("devices") or [{}])[0]
            row = {"tag": tag, "image": img, "arm": arm, "threshold": THRESHOLDS[arm], "decimation": a.dec, "exec_s": round(ex, 1), "wall_s": round(wall, 1),
                   "vertices": int(pos.shape[0]), "faces": int(idx.shape[0]) if idx is not None else 0, "bytes": dest.stat().st_size,
                   "image_size": list(Image.open(src).size), **lens,
                   "vram_used_gb": round((dev.get("vram_total", 0) - dev.get("vram_free", 0)) / 2**30, 2)}
            (RELIEF / f"{tag}.json").write_text(json.dumps(row, indent=1) + "\n", encoding="utf-8")
            rows.append(row)
            log(f"{tag}: {ex:.1f} s, {row['vertices']} vertices, {row['faces']} faces, {row['bytes'] / 2**20:.1f} MB, fov {lens['fov_x']}×{lens['fov_y']}°, "
                f"median depth {lens['depth_median']} m, floor y {lens['y_floor']} m")
    with (OUT / "relief.jsonl").open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return 0


# ---- props (offline) -----------------------------------------------------------------------------------------------------------------
def glb_bounds(path: Path) -> tuple[np.ndarray, np.ndarray]:
    doc, _ = glb_read(path)
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    node_of = {nd["mesh"]: nd for nd in doc.get("nodes", []) if "mesh" in nd}
    for mi, mesh in enumerate(doc.get("meshes", [])):
        nd = node_of.get(mi, {})
        sc, tr = np.array(nd.get("scale", [1, 1, 1])), np.array(nd.get("translation", [0, 0, 0]))
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            lo = np.minimum(lo, np.array(acc["min"]) * sc + tr)
            hi = np.maximum(hi, np.array(acc["max"]) * sc + tr)
    return lo, hi


def props(a: argparse.Namespace) -> int:
    """The things' footprints in the room's point map (E28b's masks over the `cut` relief's vertices), E28c's models scaled to the height
    the point map gives each and stood on the floor at the front edge of the mask; the room's relief with the things cut out."""
    tag = "room_cut"
    doc, binary = glb_read(RELIEF / f"{tag}.glb")
    pos, uv, idx = mesh_arrays(doc, binary)
    W, H = Image.open(BENCH / "room.jpg").size
    px = np.clip((uv[:, 0] * W).astype(int), 0, W - 1)
    py = np.clip((uv[:, 1] * H).astype(int), 0, H - 1)
    fit = json.loads((E28C / "state.json").read_text(encoding="utf-8")).get("fit", {})
    out: list[dict] = []
    union = np.zeros((H, W), bool)
    masks = {pid: np.asarray(Image.open(E28B / "masks" / f"{pid}.png").convert("L")) > 127 for pid in PROPS}
    anym = np.zeros((H, W), bool)
    for m in masks.values():
        anym |= m
    # the floor under a thing is the relief's, not the thing's own lowest pixels (MoGe puts a thing's front a little nearer than the floor
    # it stands on, so its bottom edge would float): a plane fitted to the floor pixels (the picture's lowest rows outside every mask)
    floor = ~anym[py, px] & (py > 0.62 * H) & np.isfinite(pos).all(axis=1)
    A = np.c_[pos[floor, 0], pos[floor, 2], np.ones(int(floor.sum()))]
    plane, *_ = np.linalg.lstsq(A, pos[floor, 1], rcond=None)
    floor_y = lambda x, z: float(plane[0] * x + plane[1] * z + plane[2])  # noqa: E731
    log(f"floor plane: y = {plane[0]:+.4f} x {plane[1]:+.4f} z {plane[2]:+.4f} over {int(floor.sum())} vertices (residual {np.abs(A @ plane - pos[floor, 1]).mean():.3f} m)")
    for pid, model in PROPS.items():
        m = np.asarray(Image.open(E28B / "masks" / f"{pid}.png").convert("L").filter(ImageFilter.MinFilter(7))) > 127
        union |= np.asarray(Image.open(E28B / "masks" / f"{pid}.png").convert("L").filter(ImageFilter.MaxFilter(5))) > 127
        inside = m[py, px] & np.isfinite(pos).all(axis=1)
        if inside.sum() < 50:
            log(f"{pid}: only {int(inside.sum())} vertices under its mask — skipped")
            continue
        p = pos[inside]
        rows = py[inside]
        if np.median(p[:, 1]) > 0:
            log(f"{pid}: the mask lands above the camera's height (median y {np.median(p[:, 1]):.2f}) — the UV rows look flipped")
        bottom = rows >= np.percentile(rows, 92)                                    # the silhouette's lowest rows: the front edge on the floor
        fx, fy0, fz = (float(np.median(p[bottom, k])) for k in range(3))
        fy = floor_y(fx, fz)                                                            # on the relief's floor at the front edge
        top = float(np.percentile(p[:, 1], 97))
        height = top - fy
        lo, hi = glb_bounds(E28C / "meshes" / model)
        width = float(np.percentile(p[bottom, 0], 95) - np.percentile(p[bottom, 0], 5))  # the front edge's width: measured at one depth, so the sounder size
        sc = width / max(1e-6, hi[0] - lo[0])
        centre = [fx - (lo[0] + hi[0]) / 2 * sc, fy - lo[1] * sc, fz - hi[2] * sc]           # the model's bottom on the floor, its front at the mask's front edge
        rec = {"tag": pid, "file": str(E28C / "meshes" / model), "pos": [round(v, 4) for v in centre], "scale": round(float(sc), 4), "yaw": 0.0, "floor_y": round(fy, 3), "own_y": round(fy0, 3),
               "height_m": round(height, 3), "width_m": round(width, 3), "model_height_m": round(float(hi[1] - lo[1]) * sc, 3),
               "front_m": round(fz, 3), "e28b_height_m": fit.get(pid, {}).get("size", [0, 0, 0])[1], "e28b_pos": fit.get(pid, {}).get("plate_pos"),
               "vertices": int(inside.sum())}
        out.append(rec)
        log(f"{pid}: front edge at x {fx:.2f} z {fz:.2f} m, the floor there y {fy:.2f} (its own lowest pixels {fy0:.2f}), height {height:.2f} m (E28b fitted "
            f"{rec['e28b_height_m']}), width {rec['width_m']} m, scale {sc:.3f} by the width (the model then {rec['model_height_m']} m tall)")
    (OUT / "props.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    # the room's own relief with the things cut out: the triangles touching a dilated mask dropped, the indices rewritten
    keep = ~union[py, px][idx].any(axis=1)
    new_idx = idx[keep].astype(np.uint32).reshape(-1)
    prim = doc["meshes"][0]["primitives"][0]
    old_acc = doc["accessors"][prim["indices"]]
    binary += b"\0" * (-len(binary) % 4)
    doc["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": new_idx.nbytes, "target": 34963})
    doc["accessors"].append({"bufferView": len(doc["bufferViews"]) - 1, "componentType": 5125, "count": int(new_idx.size), "type": "SCALAR",
                             "max": [int(new_idx.max())], "min": [int(new_idx.min())]})
    prim["indices"] = len(doc["accessors"]) - 1
    binary += new_idx.tobytes()
    doc["buffers"][0]["byteLength"] = len(binary)
    glb_write(RELIEF / "room_holes.glb", doc, binary)
    src = json.loads((RELIEF / f"{tag}.json").read_text(encoding="utf-8"))
    src.update({"tag": "room_holes", "faces": int(keep.sum()), "note": f"room_cut with the triangles under the four masks dropped ({int((~keep).sum())} of {old_acc['count'] // 3})"})
    (RELIEF / "room_holes.json").write_text(json.dumps(src, indent=1) + "\n", encoding="utf-8")
    log(f"room_holes: {int((~keep).sum())} triangles cut out of {old_acc['count'] // 3}")
    return 0


# ---- render (Edge) -------------------------------------------------------------------------------------------------------------------
def moves(d: float) -> list[dict]:
    m = [{"name": "origin", "pos": [0, 0, 0], "yaw": 0, "pitch": 0}]
    for x in (0.25, 0.5, 1.0):
        m += [{"name": f"truck+{x:g}", "pos": [x, 0, 0], "yaw": 0, "pitch": 0}, {"name": f"truck-{x:g}", "pos": [-x, 0, 0], "yaw": 0, "pitch": 0}]
    for y in (0.25, 0.5):
        m += [{"name": f"pedestal+{y:g}", "pos": [0, y, 0], "yaw": 0, "pitch": 0}, {"name": f"pedestal-{y:g}", "pos": [0, -y, 0], "yaw": 0, "pitch": 0}]
    for z in (0.5, 1.0):
        m.append({"name": f"dolly-{z:g}", "pos": [0, 0, -z], "yaw": 0, "pitch": 0})                     # forward: into the picture
    m.append({"name": "dolly+0.5", "pos": [0, 0, 0.5], "yaw": 0, "pitch": 0})
    for ang in (5, 10, 20):
        m += [{"name": f"pan+{ang}", "pos": [0, 0, 0], "yaw": ang, "pitch": 0}, {"name": f"pan-{ang}", "pos": [0, 0, 0], "yaw": -ang, "pitch": 0}]
    for ang in (5, 10):
        m += [{"name": f"tilt+{ang}", "pos": [0, 0, 0], "yaw": 0, "pitch": ang}, {"name": f"tilt-{ang}", "pos": [0, 0, 0], "yaw": 0, "pitch": -ang}]
    for ang in (10, 20):
        r = math.radians(ang)
        for s, name in ((1, f"orbit+{ang}"), (-1, f"orbit-{ang}")):
            m.append({"name": name, "pos": [round(s * d * math.sin(r), 4), 0, round(-d + d * math.cos(r), 4)], "yaw": s * ang, "pitch": 0})
    return m


def check(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def render(a: argparse.Namespace) -> int:
    if check("http://127.0.0.1:8188/system_stats"):
        print("the engine is still up on 8188 — stop it first (scripts/engine-stop.ps1): one GPU workload at a time (D97)")
        return 2
    if not check(f"http://127.0.0.1:{DEV}/spikes.html"):
        print(f"Vite dev is not on {DEV} (cd frontend; npx vite --host 127.0.0.1 --port {DEV} --strictPort)")
        return 2
    scenes = []
    for js in sorted(RELIEF.glob("*.json")):
        r = json.loads(js.read_text(encoding="utf-8"))
        if a.scenes != "all" and r["tag"] not in a.scenes.split(","):
            continue
        scenes.append({"tag": r["tag"], "relief": str(RELIEF / f"{r['tag']}.glb"), "fov_y": r["fov_y"], "zrange": r["zrange"], "y_floor": r["y_floor"],
                       "moves": moves(r["depth_median"]), "sheet": SHEET, "props": []})
    if (OUT / "props.json").exists() and (RELIEF / "room_empty_cut.json").exists() and (a.scenes == "all" or "room_props" in a.scenes.split(",")):
        r = json.loads((RELIEF / "room_empty_cut.json").read_text(encoding="utf-8"))
        scenes.append({"tag": "room_props", "relief": str(RELIEF / "room_empty_cut.glb"), "fov_y": r["fov_y"], "zrange": r["zrange"], "y_floor": r["y_floor"],
                       "moves": moves(r["depth_median"]), "sheet": SHEET, "props": json.loads((OUT / "props.json").read_text(encoding="utf-8"))})
    if not scenes:
        print("no reliefs to render (run `relief` first)")
        return 2
    VIEWS.mkdir(parents=True, exist_ok=True)
    (OUT / "scenes.json").write_text(json.dumps({"size": list(SIZE), "scenes": scenes}, indent=1) + "\n", encoding="utf-8")
    log(f"render: {len(scenes)} scenes × {len(scenes[0]['moves'])} moves in Edge")
    t0 = time.time()
    r = subprocess.run(["node", "e2e/spikes/e30.run.mjs"], cwd=REPO / "frontend", shell=True)
    log(f"render: {time.time() - t0:.0f} s, exit {r.returncode}")
    return r.returncode


# ---- score --------------------------------------------------------------------------------------------------------------------------
AXES = {"truck": ("truck+0.25", "truck+0.5", "truck+1", "truck-0.25", "truck-0.5", "truck-1"), "pedestal": ("pedestal+0.25", "pedestal+0.5", "pedestal-0.25", "pedestal-0.5"),
        "dolly in": ("dolly-0.5", "dolly-1"), "dolly out": ("dolly+0.5",), "pan": ("pan+5", "pan+10", "pan+20", "pan-5", "pan-10", "pan-20"),
        "tilt": ("tilt+5", "tilt+10", "tilt-5", "tilt-10"), "orbit": ("orbit+10", "orbit+20", "orbit-10", "orbit-20")}


def magnitude(name: str) -> float:
    return float(name.split("+")[-1].split("-")[-1])


def budget(res: dict[str, dict], names: tuple[str, ...], bar: float) -> str:
    """The largest magnitude on the axis whose every move (both signs) keeps the tear under the bar."""
    best = 0.0
    for mag in sorted({magnitude(n) for n in names}):
        if all(res[n]["tear"] <= bar for n in names if magnitude(n) == mag and n in res):
            best = mag
        else:
            break
    return f"{best:g}" if best else "—"


def sheet(scene: str, res: dict[str, dict]) -> None:
    cols = ["beauty", "clay", "depth"]
    moves_ = [m for m in SHEET if m in res and res[m].get("images")]
    if not moves_:
        return
    w, h = 384, 216
    im = Image.new("RGB", (16 + len(cols) * (w + 8), 24 + len(moves_) * (h + 22)), (24, 24, 28))
    d = ImageDraw.Draw(im)
    d.text((8, 4), f"E30 · {scene} — beauty (the plate re-projected, magenta = hole) · clay · depth", fill=(230, 230, 230))
    for i, mv in enumerate(moves_):
        y = 24 + i * (h + 22)
        r = res[mv]
        d.text((8, y + h + 4), f"{mv}: holes {r['holes_inner']:.1f} % · smear {r['smear']:.1f} % · tear {r['tear']:.1f} % · the picture's edge {r['holes_edge']:.1f} %", fill=(200, 200, 200))
        for j, c in enumerate(cols):
            p = r["images"].get(c)
            if p and Path(p).exists():
                im.paste(Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS), (8 + j * (w + 8), y))
    im.save(OUT / f"sheet_{scene}.jpg", quality=88)


def score(a: argparse.Namespace) -> int:
    views = json.loads((VIEWS / "views.json").read_text(encoding="utf-8"))
    lines = ["| scene | faces | truck ≤1 % | ≤3 % | pedestal ≤1 % | ≤3 % | dolly in ≤1 % | ≤3 % | pan ≤1 % | ≤3 % | tilt ≤1 % | ≤3 % | orbit ≤1 % | ≤3 % | worst move |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    summary = {}
    for scene, rec in views.items():
        if rec.get("error"):
            lines.append(f"| {scene} | — | ERROR {rec['error'][:60]} |")
            continue
        res = {m["name"]: m for m in rec["moves"]}
        worst = max(res.values(), key=lambda m: m["tear"])
        cells = []
        for ax in ("truck", "pedestal", "dolly in", "pan", "tilt", "orbit"):
            cells += [budget(res, AXES[ax], CLEAN), budget(res, AXES[ax], OK)]
        lines.append(f"| {scene} | {rec['faces']} | " + " | ".join(cells) + f" | {worst['name']} {worst['tear']:.1f} % |")
        summary[scene] = {"faces": rec["faces"], "budget_clean": {ax: budget(res, AXES[ax], CLEAN) for ax in AXES}, "budget_ok": {ax: budget(res, AXES[ax], OK) for ax in AXES},
                          "moves": {n: {k: v for k, v in m.items() if k != "images"} for n, m in res.items()}}
        sheet(scene, res)
    table = "\n".join(lines)
    (OUT / "results.md").write_text(table + "\n", encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(table)
    names = [m["name"] for m in next(iter(views.values()))["moves"]]
    for key, title in (("tear", "tear % (holes inside the picture + smear; the origin's own holes are the mask's — the sky — and the cut's seams)"),
                       ("holes_edge", "the picture's edge in the frame, % (what no image set can show; the same for every arm)")):
        print(f"\nper move — {title}:")
        print("| move | " + " | ".join(views) + " |")
        print("| --- | " + " | ".join("---" for _ in views) + " |")
        for n in names:
            print(f"| {n} | " + " | ".join(f"{next((m[key] for m in v['moves'] if m['name'] == n), float('nan')):.1f}" for v in views.values()) + " |")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["sources", "relief", "props", "render", "score"])
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--images", default=",".join(IMAGES))
    ap.add_argument("--arms", default=",".join(THRESHOLDS))
    ap.add_argument("--dec", type=int, default=2, help="MoGePointMapToMesh's vertex stride (1 = a vertex per pixel)")
    ap.add_argument("--scenes", default="all", help="render: the relief tags to render (default all, plus room_props when props.json exists)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    return {"sources": sources, "relief": relief, "props": props, "render": render, "score": score}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
