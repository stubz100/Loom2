"""Spike E28b (D108; the author, 2026-10-20: "We need to clean up the room, all objects should be props and not part of the background").
E22's plate has four objects baked in: the crate and the table the model drew, and the two grey blocks of the old room preset. Here the
room is cleaned and each object becomes a prop on its own layer, in E23c's shot (the locked camera, the window light, Mara and Ines as
E23c's M0 layers nudged onto their shadows by E23e's constant offsets, D107).

  masks     the objects in the plate: SAM 3 by text for the crate and the table; the blocks where Stage's boxes project (the plate was made
            from Stage's clay, so they are exact), kept to SAM 3's "grey block"
  remove    the app's own Remove (Klein ICM, the hole pre-filled by content-aware fill, D62) on the plate, the objects and their floor
            shadows selected → the empty room (a document, its selection, an `inpaint` job, as the D62 rig drives it)
  fit       the crate and the table as Stage props: their feet on the floor (the masks' lowest rows cast through E21's camera), their
            widths there, their heights against an assumed depth; the blocks where they stood (D108's migration)
  stage     Stage (a visible Edge; the engine stopped, D97) renders the bare room, the four props and each prop alone at frame 0: depth
            (each prop's mask and its distance) and the lit clay (the props' shadows under E23c's window light)
  assemble  the shot again, layered: the empty plate, the props' shadows, the props (their own pixels from the old plate, a still each),
            the figures' Stage shadows (E23c's, cast in the old room whose blocks stood where these props stand), the characters; a
            character is hidden where a prop is nearer the camera (Stage's depth, the figure's own depth grown over her matte). Two arms
            for the props' shadows: S, Stage's (the prop boxes under the window light) and O, their own (the old plate over the empty one,
            blurred, outside the object — the model's shadows, carried by the prop's layer)
  score     the objects left in the empty plate (SAM 3 by text), the layered still against the old plate (ΔE, everywhere and in the shadow
            zones), the occlusions (frames where a character and a prop overlap, and who is in front), time

  orchestrator/.venv/Scripts/python.exe engine/spikes/e28b_room.py masks|remove|fit|stage|assemble|score
Outputs under engine/spikes/out/e28b/ (git-ignored). For the author: compare.mp4 (before | Stage's shadows | the props' own shadows),
layers.jpg (the old plate · the empty room · the props · the layered still).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e28b"
E22, E23C, E23E = (ROOT / "engine" / "spikes" / "out" / n for n in ("e22", "e23c", "e23e"))
PLATE = E22 / "stills" / "plate.png"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
os.environ["LOOM2_E23B_OUT"] = str(E23C)
os.environ["LOOM2_E23B_BODIES"] = str(E23C / "bodies.json")
import e23a_joins as A  # noqa: E402
import e23b_layers as B  # noqa: E402
import e28_props as P  # noqa: E402

P.OUT = OUT                                       # the App's log and the project live here
SEED = 20261021
M0 = E23C / "runs" / f"M0_s{SEED}"
PW, PH = 1280, 720                                # the plate
W, H = B.W, B.H                                   # the shot (832 × 480)
# the props: id, Stage preset, how it is found in the plate, its assumed depth (m) for the fit
PROPS = {
    "crate": {"preset": "crate", "text": "wooden crate", "depth": 0.45, "name": "Crate", "move": [-0.7, 0.0, 0.0]},
    "table": {"preset": "table", "text": "small wooden table", "depth": 0.6, "name": "Table"},
    "block_big": {"preset": "block", "box": B.ROOM_BOXES[3], "name": "Big block"},
    "block_stool": {"preset": "block", "box": B.ROOM_BOXES[4], "name": "Stool block"},
}
PRESET_SIZE = {"crate": (0.6, 0.6, 0.6), "table": (1.4, 0.775, 0.8), "block": (1.0, 1.0, 1.0)}   # builders.ts prop(): the unscaled bounds
# the crate is moved 0.7 m left as a P1 prop: the model drew it where E23b's blocking (made before Stage knew of any crate) walks Mara
# through it, and the first assembly hid her boots behind its corner in a few frames. Stage seeing every object is what D108 brings.
REMOVE_PROMPT = "an empty room: bare whitewashed plaster walls and a worn wooden plank floor, nothing standing on the floor"
DBG = 9343


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def gray(p: Path, size: tuple[int, int] | None = None) -> np.ndarray:
    im = Image.open(p).convert("L")
    if size and im.size != size:
        im = im.resize(size, Image.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def box_mask(box, w: int, h: int) -> np.ndarray:
    """Where one of the old room's blocks is the nearest surface through E21's camera."""
    o, rd = B.rays(B.C0, w, h)
    hit = B.cast_boxes(o, rd)
    size, c = box
    lo, hi = np.array(c) - np.array(size) / 2 - 1e-3, np.array(c) + np.array(size) / 2 + 1e-3
    return np.all((hit >= lo) & (hit <= hi), axis=-1)


# ---- masks -------------------------------------------------------------------------------------------------------------------------
def sam_still(x, ros, img_name: str, text: str, prefix: str) -> np.ndarray:
    _, ckpt = ros.require("sam3")
    g = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
         "2": {"class_type": "LoadImage", "inputs": {"image": img_name}},
         "4": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["1", 1]}},
         "5": {"class_type": "SAM3_Detect", "inputs": {"model": ["1", 0], "image": ["2", 0], "conditioning": ["4", 0], "threshold": 0.4,
                                                       "refine_iterations": 2, "individual_masks": False}},
         "7": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
         "99": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}}}
    h, _, _ = x.e.run(g)
    d = OUT / "tmp_sam"
    p = A.download(x.e, h, "99", d)[0]
    m = np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0
    shutil.rmtree(d, ignore_errors=True)
    return m


def removal_mask(objs: dict[str, np.ndarray]) -> np.ndarray:
    """The objects grown 14 px, and their shadows: under the window light (left, high) a shadow falls to the right of an object, along the
    floor and up the wall behind it — a band from half-way up the object to 6 % of the frame below its foot reaching 1.5 times its width
    further right, and beside it from its top down, 0.4 of its width wide (the first tries, half and 0.9 of its width, left
    the big block's shadow on the right wall and the stool's on the floor)."""
    m = np.zeros((PH, PW), bool)
    for o in objs.values():
        ob = o > 0.5
        m |= B.dilate(ob, 14)
        ys, xs = np.nonzero(ob)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        band = np.zeros_like(m)
        band[int(y0 + (y1 - y0) / 2):min(PH, int(y1 + 0.06 * PH)), max(0, int(x0 - 0.06 * (x1 - x0))):min(PW, int(x1 + 1.5 * (x1 - x0)))] = True
        band[max(0, y0 - 8):min(PH, int(y1 + 0.06 * PH)), x1:min(PW, int(x1 + 0.4 * (x1 - x0)) + 1)] = True
        m |= band
    return m


def masks(a: argparse.Namespace) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "masks").mkdir(exist_ok=True)
    ros = A.roster()
    objs: dict[str, np.ndarray] = {}
    if a.reuse:                                     # the objects as found before; only the removal mask again
        objs = {pid: gray(OUT / "masks" / f"{pid}.png") for pid in PROPS}
    else:
        with A.Session() as x:
            name = x.e.upload(PLATE)
            for pid, p in PROPS.items():
                if "text" in p:
                    objs[pid] = sam_still(x, ros, name, p["text"], f"e28b/{pid}")
            grey = sam_still(x, ros, name, "grey concrete block", "e28b/grey")
        for pid, p in PROPS.items():
            if "box" in p:                          # the projected block, refined by SAM where they agree (the model softened the edges)
                pm = box_mask(p["box"], PW, PH)
                objs[pid] = grey * B.dilate(pm, 6)
                if objs[pid].sum() < 0.6 * pm.sum():
                    objs[pid] = pm.astype(np.float32)
    for pid, m in objs.items():
        Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(OUT / "masks" / f"{pid}.png")
        log(f"{pid}: {int((m > 0.5).sum())} px")
    rm = removal_mask(objs)
    Image.fromarray((rm * 255).astype(np.uint8)).save(OUT / "masks" / "remove.png")
    ov = np.asarray(Image.open(PLATE).convert("RGB"), dtype=np.float32).copy()
    ov[rm] = ov[rm] * 0.5 + np.array([255, 0, 0]) * 0.5
    for m in objs.values():
        e = (m > 0.5) ^ B.dilate(m > 0.5, 1)
        ov[e] = [0, 255, 0]
    Image.fromarray(ov.astype(np.uint8)).save(OUT / "masks.jpg", quality=90)
    log(f"the removal mask: {int(rm.sum())} px ({rm.mean() * 100:.1f} % of the plate); {OUT / 'masks.jpg'}")
    return 0


# ---- remove ------------------------------------------------------------------------------------------------------------------------
def layer_pixels(did: str, lid: str, kind: str) -> np.ndarray:
    """A document layer's raw pixels (as pe3_blend_rig reads them): its size in the response's headers."""
    req = urllib.request.Request(f"http://127.0.0.1:{P.PORT}/documents/{did}/layers/{lid}/pixels?kind={kind}&raw=1", headers={"X-Loom-Token": P.TOKEN})
    with urllib.request.urlopen(req, timeout=120) as r:
        data, h = r.read(), r.headers
    w, hh, ch = int(h["x-loom-width"]), int(h["x-loom-height"]), int(h.get("x-loom-channels", "4" if kind == "image" else "1"))
    return np.frombuffer(data, np.uint8).reshape(hh, w, ch) if ch > 1 else np.frombuffer(data, np.uint8).reshape(hh, w)


def remove(a: argparse.Namespace) -> int:
    s = load_state()
    s["project"] = str(OUT / "project")
    mask = np.asarray(Image.open(OUT / "masks" / "remove.png").convert("L"))
    original = np.asarray(Image.open(PLATE).convert("RGB"), dtype=np.float32)
    app = P.App(Path(s["project"]))
    try:
        asset = P.api("POST", "/assets/import", {"paths": [str(PLATE)]})["items"][0]
        did = P.api("POST", "/documents", {"from_asset": asset["id"], "name": "e28b room"})["id"]
        req = urllib.request.Request(f"http://127.0.0.1:{P.PORT}/documents/{did}/selection?w={PW}&h={PH}", data=mask.tobytes(), method="PUT",
                                     headers={"Content-Type": "application/octet-stream", "X-Loom-Token": P.TOKEN})
        urllib.request.urlopen(req, timeout=60).read()
        recipe = {"kind": "inpaint", "mode": a.mode, "model_id": "klein-9b", "prompt_text": REMOVE_PROMPT, "prefill": a.prefill,
                  "seeds": [SEED], "feather": 8}
        t0 = time.time()
        j = P.wait_job(P.api("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]["id"])
        if j["status"] != "done":
            print("remove", j["status"], j.get("error")); return 1
        lid = j["result"]["layers"][0]
        d = P.api("GET", f"/documents/{did}")
        node = next(n for g in d["layers"] if g["kind"] == "group" for n in g["children"] if n["id"] == lid)
        px, m = layer_pixels(did, lid, "image").astype(np.float32), layer_pixels(did, lid, "mask").astype(np.float32) / 255.0
        x0, y0 = node["x"], node["y"]
        al = np.zeros((PH, PW)); al[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m
        rgb = original.copy(); rgb[y0:y0 + px.shape[0], x0:x0 + px.shape[1]] = px[..., :3]
        empty = original * (1 - al[..., None]) + rgb * al[..., None]
        tag = f"{a.mode}{'_prefill' if a.prefill else ''}"
        Image.fromarray(np.clip(empty, 0, 255).astype(np.uint8)).save(OUT / f"plate_empty_{tag}.png")
        shutil.copy2(OUT / f"plate_empty_{tag}.png", OUT / "plate_empty.png")
        s.setdefault("remove_tries", {})[tag] = {"wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t0, 1), "model": j["recipe"].get("model_id"), "mask_pct": round(float((mask > 127).mean() * 100), 1)}
        s["remove"] = {"tag": tag, **s["remove_tries"][tag]}
        save_state(s)
        log(f"the empty room ({tag}) in {time.time() - t0:.0f} s: {OUT / 'plate_empty.png'}")
    finally:
        app.close()
    return 0


# ---- fit ---------------------------------------------------------------------------------------------------------------------------
def floor_at(o: np.ndarray, rd: np.ndarray, x: float, y: float) -> np.ndarray:
    d = rd[int(round(y)), int(round(x))]
    return o + d * (-o[1] / d[1])


def fit_prop(m: np.ndarray, depth: float) -> dict:
    """A box standing on the floor that the mask outlines: its front foot where the mask's lowest rows meet the floor, its width there,
    its height where the mask's top ray meets the box's back face (the camera looks down on the top: the top row is the back edge)."""
    o, rd = B.rays(B.C0, PW, PH)
    ys, xs = np.nonzero(m > 0.5)
    yb = float(np.percentile(ys, 99.7))
    band = xs[ys >= yb - 4]
    xl, xr = float(np.percentile(band, 1)), float(np.percentile(band, 99))
    fl, fr = floor_at(o, rd, xl, yb), floor_at(o, rd, xr, yb)
    zf = (fl[2] + fr[2]) / 2
    width = abs(fr[0] - fl[0])
    xc = (fl[0] + fr[0]) / 2
    cols = ys[np.abs(xs - (xl + xr) / 2) < 0.15 * (xr - xl)]
    yt = float(np.percentile(cols, 0.5))
    d = rd[int(round(yt)), int(round((xl + xr) / 2))]
    zb = zf - depth
    height = float(o[1] + d[1] * ((zb - o[2]) / d[2]))
    return {"pos": [round(float(xc), 3), 0.0, round(float(zf - depth / 2), 3)], "size": [round(float(width), 3), round(height, 3), depth]}


def box_corners(pos, size) -> np.ndarray:
    x, z = pos[0], pos[2]
    w, h, d = size
    return np.array([[x + sx * w / 2, y, z + sz * d / 2] for sx in (-1, 1) for y in (0, h) for sz in (-1, 1)])


def fit(a: argparse.Namespace) -> int:
    s = load_state()
    fits = {}
    for pid, p in PROPS.items():
        if "box" in p:
            size, c = p["box"]
            fits[pid] = {"pos": [c[0], 0.0, c[2]], "size": list(size)}
        else:
            fits[pid] = fit_prop(gray(OUT / "masks" / f"{pid}.png"), p["depth"])
        fits[pid]["plate_pos"] = list(fits[pid]["pos"])
        if "move" in p:
            fits[pid]["pos"] = [round(fits[pid]["pos"][n] + p["move"][n], 3) for n in range(3)]
        log(f"{pid}: at {fits[pid]['plate_pos']}, {fits[pid]['size']} m" + (f"; moved to {fits[pid]['pos']}" if "move" in p else ""))
    s["fit"] = fits
    save_state(s)
    im = Image.open(PLATE).convert("RGB")
    dr = ImageDraw.Draw(im)
    edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    for f in fits.values():
        for key, col in (("plate_pos", (255, 40, 40)), ("pos", (255, 210, 0))):
            if key == "pos" and f["pos"] == f["plate_pos"]:
                continue
            px, py = B.project(B.C0, box_corners(f[key], f["size"]), PW, PH)
            for i, j in edges:
                dr.line([(px[i], py[i]), (px[j], py[j])], fill=col, width=2)
    im.save(OUT / "fit.jpg", quality=90)
    log(f"the boxes over the plate (red; a moved prop's new place in yellow): {OUT / 'fit.jpg'}")
    return 0


def stage_objects(fits: dict) -> list[dict]:
    import e23c_white as C
    tf = lambda pos, sc: {"pos": list(pos), "rot": [0, 0, 0], "scale": list(sc)}   # noqa: E731
    objs = [{"id": "set_a", "kind": "set", "name": "Room", "preset": "room", "transform": tf((0, 0, 0), (1, 1, 1)), "colour_id": 1, "locked": True}, C.LIGHT]
    for k, (pid, p) in enumerate(PROPS.items()):
        base = PRESET_SIZE[p["preset"]]
        sc = [fits[pid]["size"][n] / base[n] for n in range(3)]
        objs.append({"id": pid, "kind": "prop", "name": p["name"], "preset": p["preset"], "transform": tf(fits[pid]["pos"], sc), "colour_id": 10 + k})
    return objs


# ---- stage -------------------------------------------------------------------------------------------------------------------------
STAGE_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const st = S.st
  await new Promise((r) => setTimeout(r, 1000))
  const doc = st().current, R = st().sequenceRenderer
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  const ids = %IDS%
  const only = (keep) => ({ ...doc, objects: doc.objects.map((x) => (ids.includes(x.id) && !keep.includes(x.id) ? { ...x, visible: false } : x)) })
  window.__e28b = {}
  for (const [name, keep] of %RUNS%) {
    const f = [{ cam: doc.cameras[0], doc: only(keep) }]
    window.__e28b[name] = { depth: await b64((await R(f, %W%, %H%, 'depth', doc)).blobs[0]), clay: await b64((await R(f, %W%, %H%, 'clay', doc)).blobs[0]) }
  }
  return { ok: true }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def stage(a: argparse.Namespace) -> int:
    from edit_headed_check import CDP, EDGE
    s = load_state()
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{P.DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    s.setdefault("project", str(OUT / "project"))
    app = P.App(Path(s["project"]))
    edge = None
    try:
        P.drain(); P.api("POST", "/engine/stop")                    # D97: nothing on the GPU while Edge renders
        st = P.api("POST", "/stages", {"name": "E28b clean room"})
        cam = {**st["cameras"][0], **B.C0}
        objs = stage_objects(s["fit"])
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}})
        url = f"http://127.0.0.1:{P.DEV}/?token={P.TOKEN}&port={P.PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={app.tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
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
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
        cdp.call("Page.reload")
        cdp.wait_for("document.readyState === 'complete' && !!window.__loom2Stage", timeout=60, settle=1.0)
        cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
        cdp.wait_for(f"!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === {len(objs)}", timeout=30, settle=4.0)
        ids = list(PROPS)
        runs = [["bare", []], ["props", ids]] + [[pid, [pid]] for pid in ids]
        r = cdp.eval(STAGE_JS.replace("%IDS%", json.dumps(ids)).replace("%RUNS%", json.dumps(runs)).replace("%W%", str(W)).replace("%H%", str(H)), timeout=600) or {}
        if not r or r.get("error"):
            print(r, cdp.page_errors()[:3]); return 1
        g = OUT / "stage"
        shutil.rmtree(g, ignore_errors=True); g.mkdir(parents=True)
        for name, _ in runs:
            for kind in ("depth", "clay"):
                (g / f"{name}_{kind}.png").write_bytes(base64.b64decode(cdp.eval(f"window.__e28b.{name}.{kind}", timeout=60)))
        log(f"the bare room, the props and each prop rendered (depth, lit clay): {g}")
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        app.close()
    return 0


# ---- assemble ------------------------------------------------------------------------------------------------------------------------
def foot(m: np.ndarray) -> tuple[float, float, float]:
    """A silhouette's foot (the mean column, the lowest row) and height, in px."""
    ys, xs = np.nonzero(m)
    return float(xs.mean()), float(ys.max()), float(ys.max() - ys.min())


def warp(a: np.ndarray, f0: tuple, f1: tuple, fill: float) -> np.ndarray:
    """Move a still from one foot to another, scaled by the heights (P1: a prop moved along the floor; the camera does not move)."""
    sc = f1[2] / max(1.0, f0[2])
    X, Y = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    px, py = f0[0] + (X - f1[0]) / sc, f0[1] + (Y - f1[1]) / sc
    inside = (px >= 0) & (px <= W - 1) & (py >= 0) & (py <= H - 1)
    v = B.sample(a if a.ndim == 3 else a[..., None], px, py)
    v = v if a.ndim == 3 else v[..., 0]
    return np.where(inside[..., None] if a.ndim == 3 else inside, v, fill)


def prop_layers() -> dict:
    """Per prop: its image (the old plate's pixels; a moved prop's warped to its Stage foot), its alpha (the plate's mask, kept to Stage's
    silhouette grown 6 px), its Stage mask and depth."""
    g = OUT / "stage"
    bare = gray(g / "bare_depth.png")
    old = np.asarray(Image.open(PLATE).convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
    out = {}
    for pid in PROPS:
        dep = gray(g / f"{pid}_depth.png")
        sm = np.abs(dep - bare) > 0.5 / 255
        al = gray(OUT / "masks" / f"{pid}.png", (W, H))
        img, mv = old, None
        if "move" in PROPS[pid]:
            mv = (foot(al > 0.5), foot(sm))
            img, al = warp(old, *mv, 0.0), warp(al, *mv, 0.0)
        al = B.soft(al * B.dilate(sm, 6), 0.8)
        out[pid] = {"image": img, "alpha": al, "stage": sm, "depth": np.where(sm, dep, 0.0), "moved": mv,
                    "median": float(np.median(dep[sm])) if sm.any() else 0.0}
    return out


def shadows(props: dict) -> dict[str, np.ndarray]:
    """The props' shadows on the empty room, two ways (ratios <= 1, 1 on the props themselves)."""
    g = OUT / "stage"
    on_props = np.zeros((H, W), bool)
    for p in props.values():
        on_props |= p["alpha"] > 0.05
    stage_r = np.clip(gray(g / "props_clay.png") / np.maximum(8 / 255, gray(g / "bare_clay.png")), 0, 1)
    old = np.asarray(Image.open(PLATE).convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32).mean(axis=2)
    emp = np.asarray(Image.open(OUT / "plate_empty.png").convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32).mean(axis=2)
    # the old plate over the empty one, blurred without the objects' own pixels (a normalised blur: the first try blurred them in, a dark
    # band round each prop with a bright seam at its edge); each prop's own shadow is that ratio in its own zone, moved with the prop
    plate_objs = np.zeros((H, W), bool)
    for pid in PROPS:
        plate_objs |= gray(OUT / "masks" / f"{pid}.png", (W, H)) > 0.5
    keep = (~B.dilate(plate_objs, 3)).astype(np.float32)
    blur = lambda v: np.asarray(Image.fromarray(np.clip(v * 200, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)), dtype=np.float32) / 200   # noqa: E731
    r = np.clip(old / np.maximum(8, emp), 0, 1.2)
    ratio = np.clip(blur(r * keep / 1.2) * 1.2 / np.maximum(1e-3, blur(keep)), 0, 1)
    ratio = np.where(blur(keep) > 0.05, ratio, 1.0)
    own = np.ones((H, W), np.float32)
    for pid, p in props.items():
        zone = np.asarray(Image.fromarray((removal_mask({pid: gray(OUT / "masks" / f"{pid}.png")}) * 255).astype(np.uint8)).resize((W, H)), dtype=np.float32) > 127
        mine = np.where(zone, ratio, 1.0)
        if p["moved"]:
            mine = warp(mine, *p["moved"], 1.0)
        own = np.minimum(own, mine)
    return {"S": np.where(on_props, 1.0, stage_r), "O": np.where(on_props, 1.0, own)}


def max_filter(a: np.ndarray, r: int) -> np.ndarray:
    """A (2r+1)² max filter, separable: the running maximum of shifted copies along each axis."""
    for ax in (0, 1):
        p = np.pad(a, [(r, r) if k == ax else (0, 0) for k in range(2)], mode="edge")
        n = a.shape[ax]
        a = np.max([np.take(p, range(k, k + n), axis=ax) for k in range(2 * r + 1)], axis=0)
    return a


def fig_depth(f: str, i: int) -> np.ndarray:
    """The figure's Stage depth, grown over the character's matte (a max filter: the nearest part of her body wins at the edge)."""
    d = gray(E23C / "stage" / f / "depth" / f"{i:04d}.png")
    m = B.stage_mask(f, i)
    dd = np.where(m, d, 0.0)
    grown = max_filter(dd, 15)
    return np.where(grown > 0, grown, float(np.median(d[m])) if m.any() else 0.0)


def assemble(a: argparse.Namespace) -> int:
    import e23d_proxy as D
    from e23e_snap import shift
    s = load_state()
    props = prop_layers()
    sh = shadows(props)
    old = np.asarray(Image.open(PLATE).convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
    empty = np.asarray(Image.open(OUT / "plate_empty.png").convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
    nudge = json.loads((E23E / "state.json").read_text(encoding="utf-8"))["nudge_px"]
    run = next(r for r in json.loads((E23C / "state.json").read_text(encoding="utf-8"))["runs"] if r["arm"] == "M0" and r["seed"] == SEED)
    m0 = {f: B.kept_mattes(M0, f, 36, json.loads(json.dumps(run["layers"][f]))) for f in B.FIGS}
    dist = json.loads((E23C / "stage" / "dist.json").read_text(encoding="utf-8"))
    far_to_near = sorted(props, key=lambda k: props[k]["median"])
    stills = {}
    occl = {f: {"frames": 0, "behind_px": 0, "overlap_px": 0} for f in B.FIGS}
    for arm in ("S", "O"):
        room = empty * sh[arm][..., None]
        for pid in far_to_near:
            al = props[pid]["alpha"][..., None]
            room = room * (1 - al) + props[pid]["image"] * al
        stills[arm] = room
        shutil.rmtree(OUT / "runs" / arm / "merged", ignore_errors=True); (OUT / "runs" / arm / "merged").mkdir(parents=True)
    for i in range(B.N):
        moved = {}
        for f in B.FIGS:
            dx, dy = nudge[B.FIGS[f]]
            al = B.soft(m0[f][i], 1.2) * B.dilate(m0[f][i] > 0.5, 3)
            moved[f] = (shift(B.arr(B.frames_of(M0 / f / "chain")[i]), dx, dy), np.clip(shift(al, dx, dy), 0, 1), shift(fig_depth(f, i), dx, dy))
        fig_r = {f: np.where(moved[f][1] > 0.3, 1.0, D.ratio_from_clay(E23C / "stage", f, i, B)) for f in B.FIGS}
        for arm in ("S", "O"):
            d = OUT / "runs" / arm / "merged"
            out = stills[arm].copy()
            for f in B.FIGS:                                        # the figures' Stage shadows, on the room and on the props
                out *= fig_r[f][..., None]
            for f in sorted(B.FIGS, key=lambda x: -dist[min(i, len(dist) - 1)][x]):
                img, al, fd = moved[f]
                front = np.ones((H, W), np.float32)
                for pid, p in props.items():                       # a prop nearer the camera than her hides her there
                    nearer = (p["alpha"] > 0.05) & (p["depth"] > fd + 1.5 / 255)
                    front = np.minimum(front, np.where(nearer, 1 - p["alpha"], 1.0))
                    if arm == "S":
                        ov = (al > 0.5) & (p["alpha"] > 0.5)
                        if ov.any():
                            occl[f]["overlap_px"] += int(ov.sum()); occl[f]["behind_px"] += int((ov & nearer).sum())
                            occl[f]["frames"] += 1
                al = al * front
                out = out * (1 - al[..., None]) + img * al[..., None]
            Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png")
        if i % 40 == 0:
            log(f"frame {i} / {B.N}")
    for arm, im in stills.items():
        Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).save(OUT / f"room_{arm}.png")
    s["occlusion"] = {B.FIGS[f]: v for f, v in occl.items()}
    save_state(s)
    # the compare at 24 fps (RIFE, D102): before (E23e's nudge on the old plate) | Stage's shadows | the props' own shadows
    seqs = {}
    before = E23E / "runs" / "MS_nc" / "merged"
    for name, src in (("before", before), ("S", OUT / "runs" / "S" / "merged"), ("O", OUT / "runs" / "O" / "merged")):
        dd = OUT / "runs" / f"rife_{name}"
        shutil.rmtree(dd, ignore_errors=True); (dd / "chain").parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dd / "chain")
        seqs[name] = A.rife(dd, 241)
    labels = {"before": "before: the objects in the plate", "S": "props as layers · Stage's shadows", "O": "props as layers · their own shadows"}
    grid = []
    for i in range(min(len(v) for v in seqs.values())):
        im = Image.new("RGB", (W * 3 // 2, H), (0, 0, 0))
        for k, name in enumerate(("before", "S", "O")):
            t = Image.open(seqs[name][i]).convert("RGB").resize((W // 2, H // 2), Image.LANCZOS)
            im.paste(A.label(t, f"{labels[name]} · {i / 24:.2f} s"), (k * (W // 2), 0))
        grid.append(np.asarray(im.crop((0, 0, W * 3 // 2, H // 2))))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    # the layers, as a sheet
    lay = np.full((H, W, 3), 40, np.float32)
    for pid in far_to_near:
        al = props[pid]["alpha"][..., None]
        lay = lay * (1 - al) + props[pid]["image"] * al
    tiles = [(old, "the old plate (the objects baked in)"), (empty, "the empty room (Remove)"), (lay, "the props, each its own layer"), (stills["S"], "layered, Stage's shadows (the crate moved)")]
    sheet = Image.new("RGB", (W, H), (0, 0, 0))
    for k, (t, lab) in enumerate(tiles):
        sheet.paste(A.label(Image.fromarray(np.clip(t, 0, 255).astype(np.uint8)).resize((W // 2, H // 2), Image.LANCZOS), lab), ((k % 2) * (W // 2), (k // 2) * (H // 2)))
    sheet.save(OUT / "layers.jpg", quality=92)
    log(f"compare: {OUT / 'compare.mp4'}; the layers: {OUT / 'layers.jpg'}")
    return 0


# ---- score -------------------------------------------------------------------------------------------------------------------------
def score(a: argparse.Namespace) -> int:
    s = load_state()
    ros = A.roster()
    left = {}
    with A.Session() as x:
        name = x.e.upload(OUT / "plate_empty.png")
        for pid, p in PROPS.items():
            text = p.get("text", "grey concrete block")
            if text in left:
                continue
            m = sam_still(x, ros, name, text, f"e28b/left_{pid}")
            Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(OUT / "masks" / f"left_{pid}.png")
            where = np.zeros((PH, PW), bool)                   # where the objects SAM is asked for stood (the blocks share one text)
            for q, pp in PROPS.items():
                if pp.get("text", "grey concrete block") == text:
                    where |= B.dilate(gray(OUT / "masks" / f"{q}.png") > 0.5, 10)
            left[text] = {"there_px": int(((m > 0.5) & where).sum()), "of_px": int(where.sum()), "anywhere_px": int((m > 0.5).sum())}
    old = np.asarray(Image.open(PLATE).convert("RGB").resize((W, H), Image.LANCZOS))
    zone = gray(OUT / "masks" / "remove.png", (W, H)) > 0.5
    objs = np.zeros((H, W), bool)
    for pid in PROPS:
        objs |= gray(OUT / "masks" / f"{pid}.png", (W, H)) > 0.5
    shade = zone & ~B.dilate(objs, 3)
    res = {"objects_left_px": left}
    for arm in ("S", "O"):
        de = np.linalg.norm(A.lab(np.asarray(Image.open(OUT / f"room_{arm}.png").convert("RGB"))) - A.lab(old), axis=-1)
        res[f"dE_{arm}"] = {"all": round(float(de.mean()), 2), "shadow_zone": round(float(de[shade].mean()), 2), "outside": round(float(de[~zone].mean()), 2)}
    res["occlusion"] = s.get("occlusion")
    res["remove"] = s.get("remove")
    s["scores"] = res
    save_state(s)
    log(f"scores: {json.dumps(res)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["masks", "remove", "fit", "stage", "assemble", "score"])
    ap.add_argument("--mode", default="fill", choices=["remove", "fill", "fill_match"])     # remove: the Inpaint recipe's modes (10 §4)
    ap.add_argument("--prefill", action="store_true")
    ap.add_argument("--reuse", action="store_true")                                         # masks: keep the objects found, redo the removal mask                                       # D62: the hole pre-filled by content-aware fill
    a = ap.parse_args()
    return {"masks": masks, "remove": remove, "fit": fit, "stage": stage, "assemble": assemble, "score": score}[a.step](a)


if __name__ == "__main__":
    raise SystemExit(main())
