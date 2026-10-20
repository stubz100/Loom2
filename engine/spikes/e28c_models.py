"""Spike E28c (D109; the author, 2026-10-20: "props should be real 3d objects - very similar to characters, but without the human skeleton").
E28 and E28b's props were clay stand-ins in Stage with a flat picture (a cut-out, or a clip guided by the stand-in's depth). Here every
prop is its reference's **3D model** (Pixal3D, P18 / D84 — the app's `image_to_mesh` job), placed in E28b's clean room at E21's camera:
the four room props where E28b fitted them (the crate moved), the chest sliding and turning a quarter (its other sides must show), the door
opening about its hinge. Its picture, two ways:

  R1  the textured model rendered by Stage under the window light (the `beauty` sequence kind, D109) — no generation
  R2  drawn by a generator on the model's passes, as Wan Animate draws a character on its pose: the app's Stage clip path per moving prop
      (a Klein Stage shot of the first frame on the clay pass, the prop's reference and the empty room as references, then LTX-2.3 on the
      model's depth, D76); the standing props keep the old plate's pixels (E28b)

Both laid on E28b's empty room with Stage's shadows (the models now cast them). Steps:

  refs      the room props cut from the old plate (their SAM 3 masks, E28b) onto grey, square; the chest and the door are E28's references
  meshes    one `image_to_mesh` job per prop, one at a time (GPU)
  orient    each model alone from four sides in Stage (`models.jpg`, beside its reference): which way it faces
  stage     the shot (121 frames, 24 fps): the props' beauty, depth and lit clay; the chest's and the door's own depth; the bare room; then
            R2's shots and clips (Edge, the engine stopped while it renders; then the app's queue)
  assemble  R1 and R2 over the empty room → compare.mp4
  score     the colour against each reference (ΔE of the mean), R2's shape against Stage's masks (SAM 3, IoU), time

  orchestrator/.venv/Scripts/python.exe engine/spikes/e28c_models.py refs|meshes|orient|stage|assemble|score
Outputs under engine/spikes/out/e28c/ (git-ignored).
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e28c"
E28, E28B = ROOT / "engine" / "spikes" / "out" / "e28", ROOT / "engine" / "spikes" / "out" / "e28b"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28b_room as R  # noqa: E402  (sets E23c's e23b_layers up)
import e28_props as P  # noqa: E402

A, B = R.A, R.B
P.OUT = OUT
SEED = 20261021
W, H = B.W, B.H
FRAMES = 121                                      # LTX-2.3: 5 s at 24 fps (R2's clips); R1 renders the same frames
DBG = 9344
# the props: where the reference comes from, the target height (m; the model is scaled uniformly to it), and how it moves
PROPS = {
    "crate": {"src": "plate", "name": "Crate", "desc": "an old wooden slatted crate"},
    "table": {"src": "plate", "name": "Table", "desc": "a small wooden side table with a drawer"},
    "block_big": {"src": "plate", "name": "Big block", "desc": "a large rough grey concrete block, open at the top"},
    "block_stool": {"src": "plate", "name": "Stool block", "desc": "a rough grey concrete cube"},
    "chest": {"src": E28 / "refs" / "chest.png", "name": "Chest", "height": 0.5, "desc": P.PROPS["Chest"]},
    "door": {"src": E28 / "refs" / "door.png", "name": "Door", "height": P.DOOR_H, "desc": P.PROPS["Door"]},
}
MOVING = ("chest", "door")
CHEST_YAW = (20.0, 110.0)                         # a quarter turn over the slide: the chest's other sides must show


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


# ---- refs --------------------------------------------------------------------------------------------------------------------------
def refs(a: argparse.Namespace) -> int:
    """A room prop's reference: its pixels in the old plate inside its SAM 3 mask, on light grey (a grey block on mid grey defeats a matte), padded square to 1024 (Pixal3D mattes it
    again with BiRefNet); the chest and the door are E28's Cast references."""
    (OUT / "refs").mkdir(parents=True, exist_ok=True)
    plate = np.asarray(Image.open(R.PLATE).convert("RGB"), dtype=np.float32)
    for pid, p in PROPS.items():
        dst = OUT / "refs" / f"{pid}.png"
        if p["src"] != "plate":
            shutil.copy2(p["src"], dst)
            continue
        m = R.B.soft(R.gray(E28B / "masks" / f"{pid}.png"), 0.7)
        ys, xs = np.nonzero(m > 0.5)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = plate[y0:y1, x0:x1] * m[y0:y1, x0:x1, None] + 225 * (1 - m[y0:y1, x0:x1, None])
        side = int(max(y1 - y0, x1 - x0) * 1.3)
        sq = np.full((side, side, 3), 225, np.float32)
        oy, ox = (side - (y1 - y0)) // 2, (side - (x1 - x0)) // 2
        sq[oy:oy + y1 - y0, ox:ox + x1 - x0] = crop
        Image.fromarray(np.clip(sq, 0, 255).astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(dst)
        log(f"{pid}: {x1 - x0} × {y1 - y0} px from the plate → {dst.name}")
    return 0


# ---- meshes ------------------------------------------------------------------------------------------------------------------------
def meshes(a: argparse.Namespace) -> int:
    s = load_state()
    s["project"] = str(OUT / "project")
    (OUT / "meshes").mkdir(parents=True, exist_ok=True)
    app = P.App(Path(s["project"]))
    try:
        for pid in PROPS:
            if pid in s.get("meshes", {}) and (OUT / "meshes" / f"{pid}.glb").is_file():
                continue
            src = P.api("POST", "/assets/import", {"paths": [str(OUT / "refs" / f"{pid}.png")]})["items"][0]["id"]
            t0 = time.time()
            j = P.wait_job(P.api("POST", "/jobs", {"recipe": {"kind": "image_to_mesh", "asset_id": src, "seeds": [SEED]}})["jobs"][0]["id"])
            if j["status"] != "done":
                print(pid, j["status"], j.get("error")); return 1
            aid = j["result"]["asset_ids"][0]
            (OUT / "meshes" / f"{pid}.glb").write_bytes(P.api("GET", f"/assets/{aid}/file", raw=True))
            s.setdefault("meshes", {})[pid] = {"asset": aid, "ref_asset": src, "wall_s": round(time.time() - t0, 1), "job_wall_s": j.get("wall_s"),
                                               "bytes": (OUT / "meshes" / f"{pid}.glb").stat().st_size, "bounds": glb_bounds(OUT / "meshes" / f"{pid}.glb")}
            save_state(s)
            log(f"{pid}: the model in {time.time() - t0:.0f} s ({s['meshes'][pid]['bytes'] / 2**20:.1f} MiB), bounds {s['meshes'][pid]['bounds']}")
    finally:
        app.close()
    return 0


def glb_bounds(path: Path) -> list[list[float]]:
    """The model's bounds (min, max) from its POSITION accessors (glTF requires their min / max), through the node transforms' scale and
    translation (Pixal3D's are plain; a rotation is reported, not applied)."""
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    doc = json.loads(b[20:20 + n])
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    node_of = {nd["mesh"]: nd for nd in doc.get("nodes", []) if "mesh" in nd}
    for mi, mesh in enumerate(doc.get("meshes", [])):
        nd = node_of.get(mi, {})
        if "rotation" in nd or "matrix" in nd:
            log(f"{path.name}: node {mi} has a rotation/matrix (not applied to the bounds)")
        sc, tr = np.array(nd.get("scale", [1, 1, 1])), np.array(nd.get("translation", [0, 0, 0]))
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            lo = np.minimum(lo, np.array(acc["min"]) * sc + tr)
            hi = np.maximum(hi, np.array(acc["max"]) * sc + tr)
    return [[round(float(v), 4) for v in lo], [round(float(v), 4) for v in hi]]


# ---- upright -----------------------------------------------------------------------------------------------------------------------
def glb_parts(path: Path) -> tuple[dict, bytes]:
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


def glb_points(doc: dict, binary: bytes) -> np.ndarray:
    pts = []
    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            bv = doc["bufferViews"][acc["bufferView"]]
            start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = bv.get("byteStride", 12)
            raw = np.frombuffer(binary, np.uint8, count=stride * (acc["count"] - 1) + 12, offset=start)
            pts.append(np.lib.stride_tricks.as_strided(raw.view(np.uint8), shape=(acc["count"], 12), strides=(stride, 1)).copy().view(np.float32).reshape(-1, 3))
    return np.concatenate(pts)


def euler(a: float, b: float, c: float) -> np.ndarray:
    """Rz(c) · Ry(b) · Rx(a), degrees."""
    a, b, c = (math.radians(v) for v in (a, b, c))
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx


def quat(m: np.ndarray) -> list[float]:
    """A rotation matrix as glTF's [x, y, z, w]."""
    t = np.trace(m)
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


def upright_of(pts: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """The tilt (about x and z, within ±45°: never laid on a side) and turn (±45°) giving the smallest upright bounding box — a model
    made from a view from above stands tilted by that view's elevation (Pixal3D works in the reference camera's frame)."""
    rng = np.random.default_rng(0)
    p = pts[rng.choice(len(pts), min(4000, len(pts)), replace=False)].astype(np.float64)
    best = (np.inf, (0.0, 0.0, 0.0))
    for step, centre, span in ((5.0, (0.0, 0.0, 0.0), 45.0), (1.0, None, 5.0)):
        c0 = centre if centre is not None else best[1]
        grid = [np.arange(c0[n] - span, c0[n] + span + 1e-6, step) for n in range(3)]
        for a in grid[0]:
            for b in grid[1]:
                for c in grid[2]:
                    q = p @ euler(a, b, c).T
                    v = float(np.prod(q.max(axis=0) - q.min(axis=0)))
                    if v < best[0]:
                        best = (v, (float(a), float(b), float(c)))
    return euler(*best[1]), [round(x, 1) for x in best[1]]


def upright(a: argparse.Namespace) -> int:
    s = load_state()
    app = P.App(Path(s["project"]))
    try:
        for pid in PROPS:
            doc, binary = glb_parts(OUT / "meshes" / f"{pid}.glb")
            pts = glb_points(doc, binary)
            m, angles = upright_of(pts)
            for nd in doc["nodes"]:
                if "mesh" in nd:
                    if "rotation" in nd or "matrix" in nd:
                        print(f"{pid}: a node already turned; not handled"); return 1
                    nd["rotation"] = [round(float(v), 6) for v in quat(m)]
            dst = OUT / "meshes" / f"{pid}_up.glb"
            glb_write(dst, doc, binary)
            q = pts @ m.T
            bounds = [[round(float(v), 4) for v in q.min(axis=0)], [round(float(v), 4) for v in q.max(axis=0)]]
            aid = P.api("POST", "/assets/import", {"paths": [str(dst)]})["items"][0]["id"]
            s["meshes"][pid].update({"asset_raw": s["meshes"][pid].get("asset_raw", s["meshes"][pid]["asset"]), "bounds_raw": s["meshes"][pid].get("bounds_raw", s["meshes"][pid]["bounds"]),
                                     "asset": aid, "bounds": bounds, "upright_deg": angles})
            save_state(s)
            lo, hi = bounds
            log(f"{pid}: turned {angles} (x, y, z °) → {hi[0] - lo[0]:.3f} × {hi[1] - lo[1]:.3f} × {hi[2] - lo[2]:.3f}")
    finally:
        app.close()
    return 0


# ---- the stage document ------------------------------------------------------------------------------------------------------------
YAW: dict[str, float] = {}                        # each model's turn so it faces the camera as its reference did (from `orient`)


def scale_of(s: dict, pid: str) -> float:
    lo, hi = s["meshes"][pid]["bounds"]
    target = PROPS[pid].get("height") or s["fit"][pid]["size"][1]
    return target / max(1e-6, hi[1] - lo[1])


def width_of(s: dict, pid: str) -> float:
    lo, hi = s["meshes"][pid]["bounds"]
    return (hi[0] - lo[0]) * scale_of(s, pid)


def door_at(f: float, width: float) -> tuple[list[float], list[float]]:
    """E28's door swing for the model's own width: the centre and turn at Stage frame f, hinged at E28's hinge."""
    a0, a1, ang = P.DOOR_OPEN
    t = min(1.0, max(0.0, (f - a0) / (a1 - a0)))
    th = ang * (t * t * (3 - 2 * t))
    r = math.radians(th)
    return [round(P.HINGE[0] + math.cos(r) * width / 2, 4), 0.0, round(P.HINGE[2] - math.sin(r) * width / 2, 4)], [0.0, round(th + YAW.get("door", 0.0), 3), 0.0]


def stage_objects(s: dict) -> list[dict]:
    import e23c_white as C
    objs = [{"id": "set_a", "kind": "set", "name": "Room", "preset": "room", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
             "colour_id": 1, "locked": True}, C.LIGHT]
    for k, pid in enumerate(PROPS):
        sc = scale_of(s, pid)
        if pid == "chest":
            pos, rot = P.BOX0, [0.0, CHEST_YAW[0] + YAW.get(pid, 0.0), 0.0]
        elif pid == "door":
            pos, rot = door_at(0, width_of(s, "door"))
        else:
            pos, rot = s["fit"][pid]["pos"], [0.0, YAW.get(pid, 0.0), 0.0]
        objs.append({"id": pid, "kind": "mesh", "name": PROPS[pid]["name"], "asset_id": s["meshes"][pid]["asset"],
                     "transform": {"pos": list(pos), "rot": rot, "scale": [sc, sc, sc]}, "colour_id": 10 + k})
    return objs


class Edge:
    """A visible Edge on the app's Stage suite for the private orchestrator (P.App), driven over CDP; the stage opened and its models loaded."""
    def __init__(self, app, st_id: str, n_objects: int):
        from edit_headed_check import CDP, EDGE
        url = f"http://127.0.0.1:{P.DEV}/?token={P.TOKEN}&port={P.PORT}&suite=stage"
        self.proc = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={app.tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                      "--window-size=1600,1000", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 30 and not ws_url:
            try:
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json", timeout=3)):
                    if t.get("type") == "page" and f"127.0.0.1:{P.DEV}" in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.5)
        self.cdp = c = CDP(ws_url)
        c.call("Page.enable"); c.call("Runtime.enable")
        c.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
        c.call("Page.reload")
        c.wait_for("document.readyState === 'complete' && !!window.__loom2Stage", timeout=60, settle=1.0)
        c.eval(f"window.__loom2Stage.open({json.dumps(st_id)})")
        c.wait_for(f"!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === {n_objects}", timeout=30, settle=1.0)
        c.wait_for(f"window.__loom2Stage.meshes().loaded.length + Object.keys(window.__loom2Stage.meshes().failed).length >= {len(PROPS)}", timeout=120, settle=2.0)
        failed = c.eval("window.__loom2Stage.meshes().failed")
        if failed:
            raise RuntimeError(f"models failed to load: {failed}")

    def pull(self, expr: str, n: int, dest: Path) -> None:
        """Fetch `n` base64 PNGs from a page array in slices (CDP message size)."""
        dest.mkdir(parents=True, exist_ok=True)
        for i in range(0, n, 30):
            for j, b in enumerate(self.cdp.eval(f"{expr}.slice({i}, {i + 30})", timeout=120)):
                (dest / f"{i + j:04d}.png").write_bytes(base64.b64decode(b))

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.kill()


def open_stage(app, s: dict, name: str) -> tuple[dict, list[dict]]:
    P.drain(); P.api("POST", "/engine/stop")                        # D97: nothing on the GPU while Edge renders
    st = P.api("POST", "/stages", {"name": name})
    cam = {**st["cameras"][0], **B.C0}
    objs = stage_objects(s)
    st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}})
    return st, objs


def check_dev() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{P.DEV}/", timeout=3)
        return True
    except Exception:
        print("the frontend dev server is not on 1420")
        return False


# ---- orient ------------------------------------------------------------------------------------------------------------------------
ORIENT_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const doc = S.st().current, R = S.st().sequenceRenderer
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  const ids = %IDS%, heights = %HEIGHTS%
  const frames = []
  for (const pid of ids) for (const yaw of [0, 90, 180, 270]) {
    const h = heights[pid]
    const cam = { ...doc.cameras[0], pos: [0, h * 0.55 + 0.35, h * 1.5 + 1.3], target: [0, h * 0.45, 0], focal_mm: 38 }
    frames.push({ cam, doc: { ...doc, objects: doc.objects.map((o) => o.id === pid ? { ...o, visible: true, transform: { ...o.transform, pos: [0, 0, 0], rot: [0, yaw, 0] } }
                                                             : (ids.includes(o.id) || o.kind === 'set') ? { ...o, visible: false } : o) } })
  }
  window.__e28c = await Promise.all((await R(frames, 384, 384, 'beauty', doc)).blobs.map(b64))
  return { ok: true, n: frames.length }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def orient(a: argparse.Namespace) -> int:
    """Each model alone at the origin, turned 0 / 90 / 180 / 270°, from a camera in front (+z, as E21's), beside its reference."""
    s = load_state()
    if not check_dev():
        return 2
    app = P.App(Path(s["project"]))
    edge = None
    try:
        st, objs = open_stage(app, s, "E28c orient")
        edge = Edge(app, st["id"], len(objs))
        heights = {pid: scale_of(s, pid) * (s["meshes"][pid]["bounds"][1][1] - s["meshes"][pid]["bounds"][0][1]) for pid in PROPS}
        r = edge.cdp.eval(ORIENT_JS.replace("%IDS%", json.dumps(list(PROPS))).replace("%HEIGHTS%", json.dumps(heights)), timeout=300) or {}
        if r.get("error"):
            print(r); return 1
        d = OUT / "orient"
        shutil.rmtree(d, ignore_errors=True)
        edge.pull("window.__e28c", r["n"], d)
    finally:
        if edge:
            edge.close()
        app.close()
    rows = []
    for k, pid in enumerate(PROPS):
        ref = Image.open(OUT / "refs" / f"{pid}.png").convert("RGB")
        ref = ref.resize((int(384 * ref.width / ref.height), 384))
        if ref.width > 384:
            ref = ref.crop(((ref.width - 384) // 2, 0, (ref.width + 384) // 2, 384))
        row = Image.new("RGB", (384 * 5, 384), (0, 0, 0))
        row.paste(A.label(ref, f"{pid}: the reference"), (0, 0))
        for n, yaw in enumerate((0, 90, 180, 270)):
            row.paste(A.label(Image.open(d / f"{k * 4 + n:04d}.png").convert("RGB"), f"the model, turned {yaw}°"), (384 * (n + 1), 0))
        rows.append(row)
    sheet = Image.new("RGB", (384 * 5, 384 * len(rows)))
    for k, row in enumerate(rows):
        sheet.paste(row, (0, 384 * k))
    sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS).save(OUT / "models.jpg", quality=90)
    log(f"the models from four sides: {OUT / 'models.jpg'}")
    return 0


# ---- stage -------------------------------------------------------------------------------------------------------------------------
STAGE_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const An = await import('/src/suites/stage/anim.ts')
  const st = S.st
  const key = (id, f, pos, rot, scale) => { st().setFrame(f); st().setTransform(id, { pos, rot, scale }); st().keyObject(id) }
  for (const [id, f, pos, rot, scale] of %KEYS%) key(id, f, pos, rot, scale)
  st().setRange(0, %LAST%); st().setFrame(0)
  await new Promise((r) => setTimeout(r, 1500))
  const doc = st().current, R = st().sequenceRenderer
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  const ids = %IDS%
  const only = (d, keep) => ({ ...d, objects: d.objects.map((x) => (ids.includes(x.id) && !keep.includes(x.id) ? { ...x, visible: false } : x)) })
  const frames = Array.from({ length: %N% }, (_, i) => An.sampleDoc(doc, i))
  const seq = (keep, n) => frames.slice(0, n).map((d) => ({ cam: d.cameras[0], doc: only(d, keep) }))
  const run = async (keep, n, kind) => Promise.all((await R(seq(keep, n), %W%, %H%, kind, An.sampleDoc(doc, 0))).blobs.map(b64))
  window.__e28c = { props: { beauty: await run(ids, %N%, 'beauty'), depth: await run(ids, %N%, 'depth'), clay: await run(ids, %N%, 'clay') },
                    bare: { depth: await run([], 1, 'depth'), clay: await run([], 1, 'clay') } }
  for (const pid of ids) window.__e28c[pid] = { depth: await run([pid], %MOVING%.includes(pid) ? %N% : 1, 'depth') }
  return { ok: true }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""

R2_PROMPT = ("The room is empty, there are no people in it. A quiet whitewashed room with bare plaster walls and a worn wooden floor, soft daylight "
             "from a window on the left; {what}. Natural colours, cinematic film still, 35 mm.")
R2_WHAT = {"chest": "a small red-painted wooden chest with iron corners stands on the floor",
           "door": "against the back wall stands a closed green panelled wooden door with a brass handle"}


def stage(a: argparse.Namespace) -> int:
    s = load_state()
    if not check_dev():
        return 2
    app = P.App(Path(s["project"]))
    edge = None
    try:
        st, objs = open_stage(app, s, "E28c models")
        edge = Edge(app, st["id"], len(objs))
        sc_chest, w_door, sc_door = scale_of(s, "chest"), width_of(s, "door"), scale_of(s, "door")
        last = FRAMES - 1
        keys = [["chest", 0, P.BOX0, [0, CHEST_YAW[0] + YAW.get("chest", 0.0), 0], [sc_chest] * 3],
                ["chest", last, P.BOX1, [0, CHEST_YAW[1] + YAW.get("chest", 0.0), 0], [sc_chest] * 3]]
        for f in sorted(set(list(range(P.DOOR_OPEN[0], P.DOOR_OPEN[1] + 1, 6)) + [0, last])):
            pos, rot = door_at(f, w_door)
            keys.append(["door", f, pos, rot, [sc_door] * 3])
        js = (STAGE_JS.replace("%KEYS%", json.dumps(keys)).replace("%LAST%", str(last)).replace("%IDS%", json.dumps(list(PROPS)))
              .replace("%N%", str(FRAMES)).replace("%MOVING%", json.dumps(list(MOVING))).replace("%W%", str(W)).replace("%H%", str(H)))
        t0 = time.time()
        r = edge.cdp.eval(js, timeout=1800) or {}
        if r.get("error"):
            print(r, edge.cdp.page_errors()[:3]); return 1
        g = OUT / "stage"
        shutil.rmtree(g, ignore_errors=True)
        for kind in ("beauty", "depth", "clay"):
            edge.pull(f"window.__e28c.props.{kind}", FRAMES, g / "props" / kind)
        for kind in ("depth", "clay"):
            edge.pull(f"window.__e28c.bare.{kind}", 1, g / "bare" / kind)
        for pid in PROPS:
            edge.pull(f"window.__e28c.{pid}.depth", FRAMES if pid in MOVING else 1, g / pid / "depth")
        s["stage_s"] = round(time.time() - t0, 1)
        log(f"the sequences rendered in {s['stage_s']} s (beauty, depth, lit clay; the moving props' own depth)")
        # R2: per moving prop, the app's Stage clip path with the other props hidden
        plate = P.api("POST", "/assets/import", {"paths": [str(E28B / "plate_empty.png")]})["items"][0]["id"]
        for mp in MOVING:
            vis = json.dumps({pid: pid == mp for pid in PROPS})
            edge.cdp.eval(f"(async () => {{ const S = await import('/src/suites/stage/stageStore.ts'); for (const [id, v] of Object.entries({vis})) S.st().updateObject(id, {{ visible: v }}); S.st().setFrame(0) }})()")
            time.sleep(1.5)
            refs_ = [{"asset_id": s["meshes"][mp]["ref_asset"], "note": f"the {mp}"}, {"asset_id": plate, "note": "the room"}]
            edge.cdp.eval(f"window.__loom2Stage.setShot({json.dumps({'method': 'clay', 'refs': refs_, 'prompt_text': R2_PROMPT.format(what=R2_WHAT[mp]), 'count': 1, 'use_as_is': True})})")
            if not edge.cdp.eval("window.__loom2Stage.renderPasses()", timeout=180):
                print("the passes were not rendered", edge.cdp.page_errors()[:3]); return 1
            t0 = time.time()
            j = P.wait_job((edge.cdp.eval("window.__loom2Stage.generateShot()", timeout=120) or [])[0]["id"])
            if j["status"] != "done":
                print("shot", j["status"], j.get("error")); return 1
            shot = j["result"]["asset_ids"][0]
            (OUT / f"r2_{mp}_shot.png").write_bytes(P.api("GET", f"/assets/{shot}/file", raw=True))
            shot_s = round(time.time() - t0, 1)
            edge.cdp.eval(f"(async () => {{ const S = await import('/src/suites/stage/stageStore.ts'); S.st().setGuideKind('depth'); S.st().setRange(0, {last}) }})()")
            time.sleep(1.0)
            if not edge.cdp.eval("window.__loom2Stage.renderGuide()", timeout=900):
                print("the guide was not rendered", edge.cdp.page_errors()[:3]); return 1
            edge.cdp.eval(f"window.__loom2Stage.setShotStart({json.dumps(shot)})")
            t0 = time.time()
            j = P.wait_job((edge.cdp.eval("window.__loom2Stage.animateShot()", timeout=120) or [])[0]["id"])
            if j["status"] != "done":
                print("clip", j["status"], j.get("error")); return 1
            clip = j["result"]["clip_id"]
            cd = OUT / "r2" / mp
            shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
            for k, p in enumerate(sorted((Path(s["project"]) / "clips" / clip / "master").glob("*.png"))):
                shutil.copy2(p, cd / f"{k:04d}.png")
            s.setdefault("r2", {})[mp] = {"shot_s": shot_s, "clip_s": round(time.time() - t0, 1), "job_wall_s": j.get("wall_s"), "frames": len(list(cd.glob("*.png"))),
                                         "model": j["recipe"].get("model_id")}
            save_state(s)
            log(f"R2 {mp}: shot {shot_s} s, clip {s['r2'][mp]['clip_s']} s ({s['r2'][mp]['frames']} frames)")
            P.drain(); P.api("POST", "/engine/stop")
        save_state(s)
    finally:
        if edge:
            edge.close()
        app.close()
    return 0


# ---- assemble ----------------------------------------------------------------------------------------------------------------------
def lum(p: Path) -> np.ndarray:
    return R.gray(p)


def assemble(a: argparse.Namespace) -> int:
    g = OUT / "stage"
    empty = np.asarray(Image.open(E28B / "plate_empty.png").convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
    bare_d, bare_c = lum(g / "bare" / "depth" / "0000.png"), lum(g / "bare" / "clay" / "0000.png")
    old_layers = R.prop_layers()                                  # E28b: the standing props' plate pixels (the crate moved)
    statics = [pid for pid in PROPS if pid not in MOVING]
    for arm in ("R1", "R2"):
        d = OUT / "runs" / arm
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    for i in range(FRAMES):
        dep = lum(g / "props" / "depth" / f"{i:04d}.png")
        mask = np.abs(dep - bare_d) > 0.5 / 255
        al = B.soft(mask.astype(np.float32), 0.7)
        shadow = np.where(B.dilate(mask, 1), 1.0, np.clip(lum(g / "props" / "clay" / f"{i:04d}.png") / np.maximum(8 / 255, bare_c), 0, 1))
        room = empty * shadow[..., None]
        beauty = B.arr(g / "props" / "beauty" / f"{i:04d}.png")
        r1 = room * (1 - al[..., None]) + beauty * al[..., None]
        r2 = room.copy()
        for pid in statics:
            pa = old_layers[pid]["alpha"][..., None]
            r2 = r2 * (1 - pa) + old_layers[pid]["image"] * pa
        for mp in MOVING:
            md = lum(g / mp / "depth" / f"{i:04d}.png")
            mm = (np.abs(md - bare_d) > 0.5 / 255) & (md >= dep - 1.5 / 255)      # the prop where it is the nearest prop
            ma = B.soft(B.dilate(mm, 1).astype(np.float32), 0.8)[..., None]
            clip = Image.open(OUT / "r2" / mp / f"{min(i, len(list((OUT / 'r2' / mp).glob('*.png'))) - 1):04d}.png").convert("RGB").resize((W, H), Image.LANCZOS)
            r2 = r2 * (1 - ma) + np.asarray(clip, dtype=np.float32) * ma
        Image.fromarray(np.clip(r1, 0, 255).astype(np.uint8)).save(OUT / "runs" / "R1" / f"{i:04d}.png")
        Image.fromarray(np.clip(r2, 0, 255).astype(np.uint8)).save(OUT / "runs" / "R2" / f"{i:04d}.png")
    grid = []
    for i in range(FRAMES):
        im = Image.new("RGB", (W, H // 2), (0, 0, 0))
        for k, (arm, lab) in enumerate((("R1", "R1 · the 3D models rendered"), ("R2", "R2 · drawn on the 3D models (chest, door)"))):
            t = Image.open(OUT / "runs" / arm / f"{i:04d}.png").convert("RGB").resize((W // 2, H // 2), Image.LANCZOS)
            im.paste(A.label(t, f"{lab} · {i / 24:.2f} s"), (k * (W // 2), 0))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    A.encode(B.frames_of(OUT / "runs" / "R1"), OUT / "r1.mp4", 24, crf=14)
    A.encode(B.frames_of(OUT / "runs" / "R2"), OUT / "r2.mp4", 24, crf=14)
    log(f"compare: {OUT / 'compare.mp4'} (and r1.mp4, r2.mp4 full size)")
    return 0


# ---- score -------------------------------------------------------------------------------------------------------------------------
def ref_lab(pid: str) -> np.ndarray:
    if PROPS[pid]["src"] == "plate":
        m = R.gray(E28B / "masks" / f"{pid}.png") > 0.5
        return A.lab(np.asarray(Image.open(R.PLATE).convert("RGB")))[m].mean(axis=0)
    img, al = P.cutout(E28 / "refs" / f"{pid}.png")
    return A.lab(img)[al > 0.5].mean(axis=0)


def score(a: argparse.Namespace) -> int:
    s = load_state()
    g = OUT / "stage"
    bare_d = lum(g / "bare" / "depth" / "0000.png")
    res: dict = {"R1": {}, "R2": {}}
    beauty0 = np.asarray(Image.open(g / "props" / "beauty" / "0000.png").convert("RGB"))
    for pid in PROPS:
        m = np.abs(lum(g / pid / "depth" / "0000.png") - bare_d) > 0.5 / 255
        m = m & ~B.dilate(~m, 2)                                    # inside, off the antialiased edge
        res["R1"][pid] = {"dE": round(float(np.linalg.norm(A.lab(beauty0)[m].mean(axis=0) - ref_lab(pid))), 1)}
    from e22_layers import sam_text_graph
    ros = A.roster()
    with A.Session() as x:
        for mp, text in (("chest", "wooden chest"), ("door", "door")):
            frames = sorted((OUT / "r2" / mp).glob("*.png"))
            A.encode(frames, OUT / f"r2_{mp}.mp4", 24, crf=12)
            h, _, _ = x.e.run(sam_text_graph(ros, x.e.upload(OUT / f"r2_{mp}.mp4"), text, f"e28c/sam_{mp}"), timeout=1800)
            sam = A.download(x.e, h, "99", OUT / "sam" / mp)
            ious, des = [], []
            for k in range(0, len(frames), 4):
                cw, ch = Image.open(frames[k]).size
                sm = np.abs(lum(g / mp / "depth" / f"{min(k, FRAMES - 1):04d}.png") - bare_d) > 0.5 / 255
                sm = np.asarray(Image.fromarray((sm * 255).astype(np.uint8)).resize((cw, ch), Image.NEAREST)) > 127
                gm = np.asarray(Image.open(sam[k]).convert("L")) > 127
                if sm.sum() > 50:
                    ious.append(float((sm & gm).sum() / max(1, (sm | gm).sum())))
                inside = sm & ~B.dilate(~sm, 2)
                if inside.sum() > 50:
                    des.append(float(np.linalg.norm(A.lab(np.asarray(Image.open(frames[k]).convert("RGB")))[inside].mean(axis=0) - ref_lab(mp))))
            res["R2"][mp] = {"iou_vs_stage": round(float(np.mean(ious)), 3), "iou_min": round(float(np.min(ious)), 3), "dE": round(float(np.median(des)), 1),
                             **s.get("r2", {}).get(mp, {})}
    res["meshes"] = {pid: {"wall_s": v["wall_s"], "MiB": round(v["bytes"] / 2**20, 1)} for pid, v in s.get("meshes", {}).items()}
    s["scores"] = res
    save_state(s)
    log(f"scores: {json.dumps(res)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["refs", "meshes", "upright", "orient", "stage", "assemble", "score"])
    a = ap.parse_args()
    s = load_state()
    if "fit" not in s and (E28B / "state.json").is_file():   # E28b's fitted places (the crate moved)
        s["fit"] = json.loads((E28B / "state.json").read_text(encoding="utf-8"))["fit"]
        save_state(s)
    YAW.update(s.get("yaw", {}))
    return {"refs": refs, "meshes": meshes, "upright": upright, "orient": orient, "stage": stage, "assemble": assemble, "score": score}[a.step](a)


if __name__ == "__main__":
    raise SystemExit(main())
