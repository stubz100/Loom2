"""E56 (D180, W60): does a thing of a built set come out of the app's image → 3D usable — the ferry painted into the Last Ferry's pier?

The ferry cropped from the pier's set picture (read-only), enlarged ×4 (it is under 200 px), ingested into E47's copy (a copy already),
and made a 3D model by the app's own job (`image_to_mesh`: Pixal3D, its own BiRefNet cut-out), alone on the GPU. The GLB is drawn on the
CPU from the front, the side and three-quarters (a z-buffered triangle raster, the texture sampled at each triangle's centre, Lambert
light), beside the crop.

Bars, set before the run: usable when (1) the hull, the cabin and the mast read from the side and from three-quarters; (2) its length to
its height is a ferry's (about 2–5 : 1), not a slab; (3) no large hole or wall of fog baked into it. Timing reported.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e56_ferry.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e54_side as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e56"
FERRY = Path("F:/loom2-projects/ux-walk2-last-ferry")
PIER_PICTURE = "ast_7d42a22b"
BOX = (540, 128, 732, 330)                         # the ferry on the 960×544 set picture, with its margin
UP = 4


def crop() -> Path:
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    cat = Catalogue(Workspace(FERRY))
    im = Image.open(cat.abs_path(cat.get(PIER_PICTURE))).convert("RGB").crop(BOX)
    im = im.resize((im.width * UP, im.height * UP), Image.Resampling.LANCZOS)
    path = OUT / "ferry_crop.png"
    im.save(path)
    return path


# ---- the GLB on the CPU -------------------------------------------------------------------------------------------------------------
def load(glb: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, Image.Image | None]:
    from loom2.relief import accessor, glb_read
    from loom2.tools.upright import quat_to_matrix
    import io
    doc, binary = glb_read(glb)
    nodes = doc.get("nodes", [])
    verts, tris, uvs = [], [], []

    def local(nd: dict) -> np.ndarray:
        if "matrix" in nd:
            return np.asarray(nd["matrix"], float).reshape(4, 4).T
        m = np.eye(4)
        r = quat_to_matrix(nd["rotation"]) if "rotation" in nd else np.eye(3)
        m[:3, :3] = r @ np.diag(nd.get("scale", [1.0, 1.0, 1.0]))
        m[:3, 3] = nd.get("translation", [0.0, 0.0, 0.0])
        return m

    def walk(i: int, parent: np.ndarray) -> None:
        nd = nodes[i]
        m = parent @ local(nd)
        if "mesh" in nd:
            for prim in doc["meshes"][nd["mesh"]]["primitives"]:
                v = accessor(doc, binary, prim["attributes"]["POSITION"]).astype(float)
                v = (np.c_[v, np.ones(len(v))] @ m.T)[:, :3]
                idx = accessor(doc, binary, prim["indices"]).astype(int).reshape(-1, 3) + sum(len(x) for x in verts)
                uv = accessor(doc, binary, prim["attributes"]["TEXCOORD_0"]).astype(float) if "TEXCOORD_0" in prim["attributes"] else np.zeros((len(v), 2))
                verts.append(v); tris.append(idx); uvs.append(uv)
        for c in nd.get("children", []):
            walk(c, m)
    for r in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(r, np.eye(4))
    tex = None
    if doc.get("images"):
        im = doc["images"][0]
        bv = doc["bufferViews"][im["bufferView"]]
        tex = Image.open(io.BytesIO(binary[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]])).convert("RGB")
    return np.concatenate(verts), np.concatenate(tris), np.concatenate(uvs), tex


def draw(v: np.ndarray, f: np.ndarray, uv: np.ndarray, tex: Image.Image | None, yaw_deg: float, size: int = 360) -> Image.Image:
    c = (v.min(0) + v.max(0)) / 2
    p = v - c
    a = np.radians(yaw_deg)
    rot = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    p = p @ rot.T
    span = max(np.ptp(p[:, 0]), np.ptp(p[:, 1])) * 1.1
    xy = (p[:, :2] / span + 0.5) * size
    xy[:, 1] = size - xy[:, 1]
    z = p[:, 2]
    img = np.full((size, size, 3), 235, np.uint8)
    zb = np.full((size, size), -np.inf)
    t = np.asarray(tex) if tex is not None else None
    tri = p[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    light = np.clip(np.abs(n @ np.array([0.3, 0.5, 0.8]) / np.linalg.norm([0.3, 0.5, 0.8])), 0.25, 1.0)
    for k in np.argsort(z[f].mean(1)):                                        # far to near
        a2 = xy[f[k]]
        x0, y0 = np.floor(a2.min(0)).astype(int)
        x1, y1 = np.ceil(a2.max(0)).astype(int)
        if x1 < 0 or y1 < 0 or x0 >= size or y0 >= size or (x1 - x0) * (y1 - y0) > 4000:
            continue
        if t is not None:
            u, w = uv[f[k]].mean(0)
            col = t[int(np.clip(w, 0, 1) * (t.shape[0] - 1)), int(np.clip(u, 0, 1) * (t.shape[1] - 1))].astype(float)
        else:
            col = np.array([180.0, 180.0, 180.0])
        xs, ys = np.meshgrid(np.arange(max(0, x0), min(size, x1 + 1)), np.arange(max(0, y0), min(size, y1 + 1)))
        if not xs.size:
            continue
        (ax, ay), (bx, by), (cx, cy) = a2
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        zz = z[f[k]].mean()
        hit = inside & (zz > zb[ys, xs])
        zb[ys[hit], xs[hit]] = zz
        img[ys[hit], xs[hit]] = np.clip(col * light[k], 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def main() -> int:
    from loom2.catalogue import Catalogue
    from loom2.workspace import Workspace
    from m1_acceptance import port_busy
    if port_busy(e.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    src = crop()
    cat = Catalogue(Workspace(e.PROJECT))
    rec = cat.ingest_file(src, kind="image", move=False, suite="catalogue", params={"e56": "the pier's ferry, ×4"})
    res: dict = {"crop": rec.id}
    proc, api = e.orchestrator(OUT / "orchestrator.log")
    try:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": {"kind": "image_to_mesh", "asset_id": rec.id}, "stage": False, "origin": {"suite": "catalogue", "surface": "mesh", "ref": rec.id}})
        print("submit:", r.status_code, r.text[:200], flush=True)
        r.raise_for_status()
        j = e.wait(api, r.json()["jobs"][0]["id"])
        res["job"] = {"status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"), "assets": (j.get("result") or {}).get("asset_ids")}
        print("job:", res["job"], flush=True)
        api.post("/engine/stop")
    finally:
        e.stop(proc)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    mid = (res["job"].get("assets") or [None])[0]
    if not mid:
        return 1
    glb = Catalogue(Workspace(e.PROJECT)).abs_path(Catalogue(Workspace(e.PROJECT)).get(mid))
    shutil.copy(glb, OUT / "ferry.glb")
    v, f, uv, tex = load(glb)
    ext = np.ptp(v, 0)
    res["extent"] = [round(float(x), 3) for x in ext]
    res["faces"] = int(len(f))
    views = [draw(v, f, uv, tex, yaw) for yaw in (0, 90, 45)]
    c = Image.open(src).convert("RGB")
    c.thumbnail((360, 360))
    sheet = Image.new("RGB", (360 * 4, 380), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate([(c, "the crop (×4)"), (views[0], "front"), (views[1], "side"), (views[2], "three-quarters")]):
        sheet.paste(im, (i * 360, 20))
        d.text((i * 360 + 4, 4), label, fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=88)
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
