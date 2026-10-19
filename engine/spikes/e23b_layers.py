"""Spike E23b (proto01_animate 02 §3): two layers — which Wan Animate mode does the app use, Move or Replace? At D102's frame rate (F16,
RIFE to 24 at the end) with W1 chaining (continue_motion 5, the re-made frames dropped).

The shot (≈ 10 s), E22's set and characters: E21's `room` set and plate (`out/e22/stills/plate.png`, made from the Stage clay render at
E21's camera); Mara (black bob, round glasses, grey wool coat) and Ines (long curly red hair, yellow jacket), recreated as Cast profiles from
E22's hero images with their animation references made by CA0's own route. Blocked in the app's Stage (a visible Edge, the CC0 starter
set through CA1's code, Detailed ♀ figures so the pose passes carry hands and feet, D101):

  Mara  walks a curved floor path towards the front (Walk_Loop, feet locked, steered), then turns to face Ines
  Ines  stands in front of the stool (the set's block at the origin), sits down on it (Sitting_Enter), then points at Mara (arm keys)
  camera  a slow dolly-in (0.5 m) with a slight pan to the left, keyed at the first and last frame

Per figure, Stage renders (that figure alone visible) its pose sequence and its depth sequence, and the empty set's depth sequence; a
figure's mask in a frame is where its render differs from the empty set's and is not behind the other figure's (8-bit inverse depth).
The plate moves with the camera by 2.5D projection (01 step 3: "the plate projected onto the set's blocks"): each output pixel's ray is cast
onto the room's blocks (builders.ts `room`) and the hit is looked up in the plate through E21's camera — exact projective texturing; where
the camera sees behind a block the plate stretches. Stage has no shadow pass yet: M's shadows are contact shadows drawn under each figure's
ankles (a soft ellipse multiplied onto the plate), noted as a stand-in.

Arms (2 seeds each, the same seeds across arms):
  M  Move: each figure performs its pose sequence on its animation reference (grey ground, CN4's padding), 3 chained batches; a SAM 3 matte
     per frame (E22's SAM3_Detect by text, kept inside the figure's Stage mask grown by 36 px — E21's one-box path returned noise here);
     stacked over the moving plate far → near by camera distance, the contact shadows first
  R  Replace: `background_video` = the moving plate (then the previous layer's result) with the figure's region (its Stage mask dilated
     12 px) set to black, Wan 2.2's own replace preprocessing + `character_mask` = that region, far → near; the model draws the character
     but leaves the black where she does not cover the region, so only her own SAM 3 matte (inside the region) is pasted back each time.
     `rtest` tried the region's fill on one batch: the plate's own pixels → no one inserted; mid grey or a clay dummy → kept as they are
  (R2, a depth-guided plate video, is left out: LTX-2.3's Render clip covers 5 s, the shot 10 s — noted for the decision.)

Measured (score): PCK@0.1 per figure on the merged clip (SDPose, every 8th frame); FaceSim per character every 8th frame (faces assigned
to the nearest head keypoint), its drop from batch 1 to batch 3; the joins' local seam ratio (E23a); background flicker outside the figures
against the plate's own; under R, the drift of the plate inside the pasted region around the figure; E21's band step at the layer edge
(the merged clip's gradient in the alpha band ÷ the layer clip's); time and peak VRAM per run. For the author: compare.mp4 (M | R, a row
per seed, 24 fps after RIFE), a contact sheet, the joins.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e23b_layers.py refs     # the two animation references (GPU, the app's route)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23b_layers.py stage    # visible Edge, Vite on 1420; no engine
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23b_layers.py plate    # CPU
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23b_layers.py run      # the arms, one GPU job at a time
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23b_layers.py score    # SDPose on the engine, then RIFE, sheets, compare.mp4
Outputs under engine/spikes/out/e23b/ (git-ignored).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e23a_joins as A  # noqa: E402  (shared: encode, grey, lab, Session, download, pad_reference, rife, label)

OUT = Path(os.environ.get("LOOM2_E23B_OUT") or ROOT / "engine" / "spikes" / "out" / "e23b")     # CA1b re-run: its own folder
STATE = OUT / "state.json"
MODELS = A.MODELS
PLATE = ROOT / "engine" / "spikes" / "out" / "e22" / "stills" / "plate.png"
HEROES = ROOT / "engine" / "spikes" / "out" / "e22" / "heroes"
W, H = A.W, A.H
FPS, N = 16, 161                               # D102: F16, 10 s
BATCH, CARRY = A.BATCH, A.CARRY
SEEDS = [int(x) for x in os.environ.get("LOOM2_E23B_SEEDS", "20261021,20261022").split(",")]
ARMS = os.environ.get("LOOM2_E23B_ARMS", "M,R").split(",")
WITH_CLAY = False                                             # E23c: also the lit clay sequences
EXTRA_OBJECTS: list[dict] = []                                # E23c: a light object
PREPARE = None                                                # E23d: (api) -> {name: extra figure fields} after the project opens (the proxies' assets)
BODIES = os.environ.get("LOOM2_E23B_BODIES")                  # CA1b: the fitted bodies (scripts/ca1b_acceptance.py), by character name
C0 = {"pos": [0.0, 1.05, 4.3], "target": [0.0, 0.95, 0.0], "focal_mm": 38, "sensor_mm": 36}      # E21's camera: the plate's
C1 = {"pos": [-0.2, 1.03, 3.8], "target": [-0.3, 0.93, 0.0], "focal_mm": 38, "sensor_mm": 36}    # 0.5 m in, a slight pan left
PLATE_W, PLATE_H = 1280, 720
MARA_PATH = [[-0.9, -2.8], [-1.8, -2.0], [-1.8, -1.0], [-1.3, -0.5]]
INES_AT = [0.0, 0.0, 0.42]                      # in front of the stool (builders.ts room: a 0.45 × 0.48 × 0.45 block at the origin)
SIT_AT = 24                                     # Stage frames (24 fps)
FIGS = {"fig_m": "Mara", "fig_i": "Ines"}
CAST = {
    "Mara": {"hero": "L.png", "appearance": "Mara, a young woman with a black bob and round glasses", "outfit": "a grey wool coat, black trousers, black shoes",
             "colours": [{"hex": "#7A7A7A", "object": "wool coat"}], "desc": "a young woman with a black bob and round glasses in a grey wool coat",
             "act": "walks across the room towards the front, stops and turns to face the woman on the right"},
    "Ines": {"hero": "R.png", "appearance": "Ines, a woman with long curly red hair and freckles", "outfit": "a mustard-yellow work jacket, dark jeans, brown boots",
             "colours": [{"hex": "#D9A82B", "object": "jacket"}], "desc": "a woman with long curly red hair in a yellow jacket",
             "act": "sits down on a low grey block behind her, then points with her outstretched arm at someone on the left"},
}
SCENE = "a quiet whitewashed room with bare plaster walls and a worn wooden floor, soft daylight from a window on the left"
ROOM_BOXES = [  # builders.ts `room`: box(w, h, d, x, y, z) — centre and size
    ((9, 0.02, 9), (0, -0.01, 0)), ((9, 3.2, 0.2), (0, 1.6, -3.2)), ((0.2, 3.2, 9), (-4, 1.6, 0)),
    ((1.2, 0.8, 0.8), (1.9, 0.4, -1.8)), ((0.45, 0.48, 0.45), (0, 0.24, 0))]
ORCH_PORT, DEV, DBG = 8787, 1420, 9339
R_BG = "black"                                   # what R's background shows where the figure goes (rtest)
BARS = {"pck": 0.8, "face_drop": 0.05, "seam": 1.5, "vram_gb": 14.5, "shot_min": 45}


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def frames_of(d: Path) -> list[Path]:
    return sorted(d.glob("*.png"))


def arr(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)


# ---- 1 · the animation references, by CA0's route ----------------------------------------------------------------------------------
def refs(a: argparse.Namespace) -> int:
    from loom2.config import AppState
    from m1_acceptance import Orch, port_busy
    if port_busy(A.ENGINE_PORT):
        print("the engine port is busy — one GPU job at a time"); return 2
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e23b-refs-"))
    AppState(tmp / "state").update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full", "engine": {"port": A.ENGINE_PORT}})
    o = Orch(tmp / "state", ORCH_PORT).start()
    s = load_state()
    d = OUT / "refs"
    d.mkdir(parents=True, exist_ok=True)
    try:
        r = o.http.post("/project", json={"path": str(tmp / "proj"), "name": "E23b refs", "size_cap_gb": 20}); assert r.status_code == 200, r.text[:200]
        for name, c in CAST.items():
            hero = o.http.post("/assets/import", json={"paths": [str(HEROES / c["hero"])]}).json()["items"][0]["id"]
            p = o.http.post("/story/profiles", json={"name": name, "cls": "character", "hero_asset_id": hero, "appearance": c["appearance"], "outfit": c["outfit"],
                                                     "colours": c["colours"], "label": "E22"}).json()
            t0 = time.time()
            q = o.http.post(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "front", "count": 1}, timeout=120).json()
            jid = q["job_ids"][0]
            while True:
                j = next((x for x in o.http.get("/jobs").json()["items"] if x["id"] == jid), None)
                if j and j["status"] in ("done", "failed", "cancelled"):
                    break
                time.sleep(1.0)
            if j["status"] != "done":
                print(name, j["status"], j.get("error")); return 1
            v = next(x for x in o.http.get(f"/story/profiles/{p['id']}").json()["versions"] if x["id"] == "v1")
            (d / f"{name.lower()}.png").write_bytes(o.http.get(f"/assets/{v['anim_ref_asset_id']}/file").content)
            s.setdefault("refs", {})[name] = {"asset": v["anim_ref_asset_id"], "wall_s": round(time.time() - t0, 1), "model": q.get("model_id")}
            log(f"{name}: animation reference in {time.time() - t0:.0f} s ({q.get('model_id')})")
    finally:
        try:
            o.http.post("/engine/stop", timeout=120); o.http.post("/shutdown", timeout=30)
        except Exception:
            pass
        time.sleep(2)
        if o.proc and o.proc.poll() is None:
            o.proc.kill()
    save_state(s)
    return 0


# ---- 2 · the blocking and its sequences, by the app's own code in a visible Edge ----------------------------------------------------
STAGE_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const An = await import('/src/suites/stage/anim.ts')
  const M = await import('/src/suites/stage/motion/motionStore.ts')
  const lib = await import('/src/suites/stage/motion/library.ts')
  const st = S.st, mm = () => M.useMotion.getState()
  await mm().refresh()
  const file = mm().files.find((f) => f.name === 'AnimationLibrary_Godot_Standard')
  if (!file) return { error: 'the starter library is not listed' }
  const clips = await lib.clipsOf(file), clip = (n) => clips.find((c) => c.name === n)
  const sampled = (id) => st().sampledDoc().objects.find((x) => x.id === id)
  // the camera: keyed at the first and the last frame
  const camId = st().current.cameras[0].id
  st().setFrame(0); st().updateCamera(camId, %C0%); st().keyCamera()
  st().setFrame(240); st().updateCamera(camId, %C1%); st().keyCamera()
  // Mara: the walk along her path, then a turn to face Ines with the feet together
  st().select('fig_m'); st().setFrame(0)
  mm().pick(clip('Walk_Loop')); mm().set({ lock: true, alongPath: true, blend: 6 }); await mm().apply()
  let ks = st().current.keyframes.objects.fig_m; const mEnd = ks[ks.length - 1].frame
  st().setFrame(mEnd); st().keyObject('fig_m')
  let o = sampled('fig_m')
  const want = Math.atan2(%INES%[0] - o.transform.pos[0], %INES%[2] - o.transform.pos[2]) * 180 / Math.PI
  const y = o.transform.rot[1], to = y + ((((want - y) % 360) + 540) % 360) - 180
  st().setFrame(mEnd + 16); st().setTransform('fig_m', { pos: o.transform.pos, rot: [0, to, 0], scale: o.transform.scale }); st().applyPose('fig_m', 'stand'); st().keyObject('fig_m')
  // Ines: sits down at SIT_AT, then points at Mara with her right arm (her right is the screen's left)
  st().select('fig_i'); st().setFrame(%SIT%)
  mm().pick(clip('Sitting_Enter')); mm().set({ lock: true, alongPath: false, blend: 0 }); await mm().apply()
  ks = st().current.keyframes.objects.fig_i; const iEnd = ks[ks.length - 1].frame
  st().setFrame(iEnd + 8); st().keyObject('fig_i')
  st().setFrame(iEnd + 26); o = sampled('fig_i')
  st().setJoints('fig_i', { ...o.pose.joints, r_shoulder: [0, 0, -82], r_elbow: [0, 0, 0] })
  st().setRange(0, 240); st().setFrame(0)
  await new Promise((r) => setTimeout(r, %CLAY% ? 8000 : 2000))
  const doc = st().current
  const R = st().sequenceRenderer
  if (!R) return { error: 'no sequence renderer' }
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  const frames = Array.from({ length: %N% }, (_, i) => An.sampleDoc(doc, (i * 24) / %FPS%))
  const only = (d, keep) => ({ ...d, objects: d.objects.map((x) => (x.kind === 'mannequin' && !keep.includes(x.id) ? { ...x, visible: false } : x)) })
  const seq = (keep) => frames.map((d) => ({ cam: d.cameras[0], doc: only(d, keep) }))
  window.__e23b = { cams: frames.map((d) => d.cameras[0]),
    dist: frames.map((d) => Object.fromEntries(d.objects.filter((x) => x.kind === 'mannequin').map((x) => [x.id, Math.hypot(...x.transform.pos.map((v, k) => v - d.cameras[0].pos[k]))]))) }
  for (const id of ['fig_m', 'fig_i']) {
    const p = await R(seq([id]), %W%, %H%, 'pose', An.sampleDoc(doc, 0))
    const dd = await R(seq([id]), %W%, %H%, 'depth', An.sampleDoc(doc, 0))
    window.__e23b[id] = { pose: await Promise.all(p.blobs.map(b64)), keypoints: p.keypoints, depth: await Promise.all(dd.blobs.map(b64)) }
  }
  const e = await R(seq([]), %W%, %H%, 'depth', An.sampleDoc(doc, 0))
  window.__e23b.set = { depth: await Promise.all(e.blobs.map(b64)) }
  if (%CLAY%) {                                                  // E23c: the lit clay — the set alone, and each figure alone (its shadow)
    window.__e23b.set.clay = await Promise.all((await R(seq([]), %W%, %H%, 'clay', An.sampleDoc(doc, 0))).blobs.map(b64))
    for (const id of ['fig_m', 'fig_i']) window.__e23b[id].clay = await Promise.all((await R(seq([id]), %W%, %H%, 'clay', An.sampleDoc(doc, 0))).blobs.map(b64))
    // E23d: the proxies seen (when the figures carry one), three frames each, to check their fit
    for (const id of ['fig_m', 'fig_i']) window.__e23b[id].proxy = await Promise.all((await R([0, 80, 160].map((i) => seq([id])[i]), %W%, %H%, 'proxy', An.sampleDoc(doc, 0))).blobs.map(b64))
  }
  // E23c: the empty set's clay pass from the first frame's camera (the white set is made from it)
  st().setFrame(0)
  for (const id of ['fig_m', 'fig_i']) st().updateObject(id, { visible: false })
  await new Promise((r) => setTimeout(r, 800))
  const P = st().passRenderer
  if (P) { const pr = await P(An.sampleDoc(st().current, 0).cameras[0], %W%, %H%); window.__e23b.setClay = await b64(pr.blobs.clay) }
  return { mEnd, mTurn: mEnd + 16, iSit: %SIT%, iSat: iEnd, iPoint: iEnd + 26, keys: Object.fromEntries(Object.entries(doc.keyframes.objects).map(([k, v]) => [k, v.length])) }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def body_of(name: str) -> dict:
    """CA1b: a figure's fitted body when LOOM2_E23B_BODIES names the file; the default dummy otherwise (E23b's first run)."""
    if not BODIES:
        return {}
    b = json.loads(Path(BODIES).read_text(encoding="utf-8")).get(name)
    return {"body": b} if b else {}


def stage(a: argparse.Namespace) -> int:
    from edit_headed_check import CDP, EDGE
    from loom2.config import AppState
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e23b-"))
    AppState(tmp / "state").update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8199}})
    env = {**os.environ, "LOOM2_TOKEN": "e23b", "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(ORCH_PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=(OUT / "stage_orchestrator.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT, text=True)

    def api(method, path, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{ORCH_PORT}{path}", data=None if body is None else json.dumps(body).encode("utf-8"), method=method,
                                     headers={"Content-Type": "application/json", "X-Loom-Token": "e23b"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode("utf-8") or "null")
    edge = None
    s = load_state()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "E23b", "size_cap_gb": 20})
        extra = PREPARE(api) if PREPARE else {}
        st = api("POST", "/stages", {"name": "E23b"})
        cam = {**st["cameras"][0], **C0}
        tf = lambda pos, yaw=0: {"pos": pos, "rot": [0, yaw, 0], "scale": [1, 1, 1]}   # noqa: E731
        objs = [{"id": "set_a", "kind": "set", "name": "Room", "preset": "room", "transform": tf([0, 0, 0]), "colour_id": 3},
                {"id": "fig_m", "kind": "mannequin", "name": "Mara", "preset": "adult", "transform": tf([MARA_PATH[0][0], 0, MARA_PATH[0][1]]),
                 "pose": {"preset": "stand", "joints": {}, "extra": {}}, "colour_id": 1, "detail": "female", "path": MARA_PATH, **body_of("Mara"), **extra.get("Mara", {})},
                {"id": "fig_i", "kind": "mannequin", "name": "Ines", "preset": "adult", "transform": tf(INES_AT),
                 "pose": {"preset": "stand", "joints": {}, "extra": {}}, "colour_id": 2, "detail": "female", **body_of("Ines"), **extra.get("Ines", {})}, *EXTRA_OBJECTS]
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}})
        url = f"http://127.0.0.1:{DEV}/?token=e23b&port={ORCH_PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                 "--window-size=1600,1000", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 30 and not ws_url:
            try:
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json", timeout=3)):
                    if t.get("type") == "page" and f"127.0.0.1:{DEV}" in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.5)
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
        cdp.call("Page.reload")
        cdp.wait_for("document.readyState === 'complete' && !!window.__loom2Stage", timeout=60, settle=1.0)
        cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
        cdp.wait_for(f"!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === {3 + len(EXTRA_OBJECTS)}", timeout=30, settle=10.0)
        js = (STAGE_JS.replace("%CLAY%", "true" if WITH_CLAY else "false").replace("%C0%", json.dumps(C0)).replace("%C1%", json.dumps(C1)).replace("%INES%", json.dumps(INES_AT)).replace("%SIT%", str(SIT_AT))
              .replace("%N%", str(N)).replace("%FPS%", str(FPS)).replace("%W%", str(W)).replace("%H%", str(H)))
        r = cdp.eval(js, timeout=1800) or {}
        log(f"in page: {r}")
        if not r or r.get("error"):
            print(r, cdp.page_errors()[:3]); return 1
        s["blocking"] = r
        g = OUT / "stage"
        shutil.rmtree(g, ignore_errors=True)

        def pull(expr: str, dest: Path) -> None:
            dest.mkdir(parents=True, exist_ok=True)
            for i in range(0, N, 30):
                for j, b in enumerate(cdp.eval(f"{expr}.slice({i}, {i + 30})", timeout=120)):
                    (dest / f"{i + j:04d}.png").write_bytes(base64.b64decode(b))
        for fid in FIGS:
            pull(f"window.__e23b.{fid}.pose", g / fid / "pose")
            pull(f"window.__e23b.{fid}.depth", g / fid / "depth")
            kp = cdp.eval(f"window.__e23b.{fid}.keypoints", timeout=120)
            k = list(FIGS).index(fid)
            kp = [fr[k] if len(fr) == 2 else (fr[0] if fr else []) for fr in kp]       # one figure visible: its own 18 points
            (g / fid / "keypoints.json").write_text(json.dumps(kp), encoding="utf-8")
            A.encode(frames_of(g / fid / "pose"), g / f"pose_{fid}.mp4", FPS)
        pull("window.__e23b.set.depth", g / "set" / "depth")
        if WITH_CLAY:
            pull("window.__e23b.set.clay", g / "set" / "clay")
            for fid in FIGS:
                pull(f"window.__e23b.{fid}.clay", g / fid / "clay")
                (g / fid / "proxy").mkdir(parents=True, exist_ok=True)
                for k, b in enumerate(cdp.eval(f"window.__e23b.{fid}.proxy || []", timeout=60)):
                    (g / fid / "proxy" / f"{(0, 80, 160)[k]:04d}.png").write_bytes(base64.b64decode(b))
        clay = cdp.eval("window.__e23b.setClay || null", timeout=60)
        if clay:
            (g / "set_clay.png").write_bytes(base64.b64decode(clay))
        (g / "cams.json").write_text(json.dumps(cdp.eval("window.__e23b.cams", timeout=60)), encoding="utf-8")
        (g / "dist.json").write_text(json.dumps(cdp.eval("window.__e23b.dist", timeout=60)), encoding="utf-8")
        for f in (0, 60, 120, 240):
            cdp.eval(f"window.__loom2Stage.setFrame({f})"); cdp.wait_for("true", timeout=5, settle=0.8)
            (g / f"viewport_{f:03d}.png").write_bytes(base64.b64decode(cdp.call("Page.captureScreenshot", format="png")["data"]))
        save_state(s)
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        try:
            api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
    masks(s)
    return 0


def masks(s: dict) -> None:
    """Each figure's visible silhouette per frame from the three depth sequences (bright = near): the set is in every render, so the figure
    is where its render differs from the set's, and not behind the other figure; the framing."""
    g = OUT / "stage"
    dep = {k: [np.asarray(Image.open(p).convert("L"), dtype=np.int16) for p in frames_of(g / k / "depth")] for k in (*FIGS, "set")}
    for fid in FIGS:
        other = next(k for k in FIGS if k != fid)
        d = g / fid / "mask"
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        px = []
        for i in range(N):
            me = dep[fid][i]
            m = (me != dep["set"][i]) & (me >= dep[other][i])          # the set stays in each figure's render: the figure is where it differs
            Image.fromarray((m * 255).astype(np.uint8)).save(d / f"{i:04d}.png")
            px.append(int(m.sum()))
        kp = json.loads((g / fid / "keypoints.json").read_text(encoding="utf-8"))
        pts = [np.array([p for p in f if p[2] > 0], float) for f in kp if f]
        inside = all(len(q) == 0 or (((q[:, 0] >= 0) & (q[:, 0] < W) & (q[:, 1] >= 0) & (q[:, 1] < H)).all()) for q in pts)
        hts = [float(np.ptp(q[:, 1])) for q in pts if len(q)]
        s.setdefault("framing", {})[fid] = {"frames": len(kp), "points_all_inside": bool(inside), "figure_px": [round(min(hts)), round(max(hts))],
                                            "mask_px": [min(px), max(px)], "visible_points_min": min(len(q) for q in pts)}
        log(f"{FIGS[fid]}: framing {s['framing'][fid]}")
    save_state(s)


# ---- 3 · the plate along the camera path (2.5D projection onto the room's blocks) --------------------------------------------------
def basis(cam: dict, w: int, h: int):
    pos, tgt = np.array(cam["pos"], float), np.array(cam["target"], float)
    f = tgt - pos; f /= np.linalg.norm(f)
    r = np.cross(f, [0.0, 1.0, 0.0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    aspect = w / h
    th = (cam["sensor_mm"] / aspect) / (2 * cam["focal_mm"])                       # tan(vfov / 2), three's vfovFor
    return pos, f, r, u, th, aspect


def rays(cam: dict, w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    pos, f, r, u, th, aspect = basis(cam, w, h)
    xs = ((np.arange(w) + 0.5) / w) * 2 - 1
    ys = 1 - ((np.arange(h) + 0.5) / h) * 2
    X, Y = np.meshgrid(xs, ys)
    d = f[None, None] + r[None, None] * (X[..., None] * th * aspect) + u[None, None] * (Y[..., None] * th)
    return pos, d / np.linalg.norm(d, axis=-1, keepdims=True)


def cast_boxes(o: np.ndarray, d: np.ndarray) -> np.ndarray:
    """The nearest hit of each ray with the room's blocks (slab test); returns world points."""
    best = np.full(d.shape[:-1], np.inf)
    for size, c in ROOM_BOXES:
        lo, hi = np.array(c) - np.array(size) / 2, np.array(c) + np.array(size) / 2
        with np.errstate(divide="ignore", invalid="ignore"):
            t1, t2 = (lo - o) / d, (hi - o) / d
        tmin, tmax = np.nanmax(np.minimum(t1, t2), axis=-1), np.nanmin(np.maximum(t1, t2), axis=-1)
        hit = (tmax >= np.maximum(tmin, 1e-3))
        t = np.where(tmin > 1e-3, tmin, tmax)
        best = np.where(hit & (t < best), t, best)
    best = np.where(np.isfinite(best), best, 50.0)
    return o + d * best[..., None]


def project(cam: dict, pts: np.ndarray, w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    pos, f, r, u, th, aspect = basis(cam, w, h)
    v = pts - pos
    z = v @ f
    x = (v @ r) / (z * th * aspect)
    y = (v @ u) / (z * th)
    return (x + 1) / 2 * w - 0.5, (1 - y) / 2 * h - 0.5


def sample(img: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    hh, ww = img.shape[:2]
    px, py = np.clip(px, 0, ww - 1.001), np.clip(py, 0, hh - 1.001)
    x0, y0 = np.floor(px).astype(int), np.floor(py).astype(int)
    fx, fy = (px - x0)[..., None], (py - y0)[..., None]
    a, b, c, d = img[y0, x0], img[y0, x0 + 1], img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy


def plate(a: argparse.Namespace) -> int:
    cams = json.loads((OUT / "stage" / "cams.json").read_text(encoding="utf-8"))
    src = np.asarray(Image.open(PLATE).convert("RGB"), dtype=np.float32)
    d = OUT / "plate"
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    t0 = time.time()
    for i, cam in enumerate(cams):
        cam = {**C0, **cam}
        o, rd = rays(cam, W, H)
        p = cast_boxes(o, rd)
        px, py = project(C0, p, PLATE_W, PLATE_H)
        Image.fromarray(np.clip(sample(src, px, py), 0, 255).astype(np.uint8)).save(d / f"{i:04d}.png")
    A.encode(frames_of(d), OUT / "plate.mp4", FPS, crf=12)
    # a check: the blocks' edges drawn over the plate through E21's camera
    o, rd = rays(C0, PLATE_W, PLATE_H)
    hit = cast_boxes(o, rd)
    lab = np.zeros(hit.shape[:2], int)
    for k, (size, c) in enumerate(ROOM_BOXES):
        lo, hi = np.array(c) - np.array(size) / 2 - 1e-3, np.array(c) + np.array(size) / 2 + 1e-3
        lab[np.all((hit >= lo) & (hit <= hi), axis=-1)] = k + 1
    edge = (np.abs(np.diff(lab, axis=0, prepend=0)) + np.abs(np.diff(lab, axis=1, prepend=0))) > 0
    ov = src.copy(); ov[edge] = [255, 0, 0]
    Image.fromarray(ov.astype(np.uint8)).save(OUT / "plate_blocks.jpg", quality=90)
    log(f"plate: {len(cams)} frames in {time.time() - t0:.0f} s; the blocks over the plate: {OUT / 'plate_blocks.jpg'}")
    return 0


# ---- 4 · the arms ------------------------------------------------------------------------------------------------------------------
def animate_graph(ros, ref_name: str, pose_name: str, seed: int, offset: int, carry: list[str], prompt: str, prefix: str,
                  bg_name: str | None = None, mask_name: str | None = None) -> dict:
    g = A.batch_graph(ros, pose_name, ref_name, seed, offset, carry, prefix)
    g["5"]["inputs"]["text"] = prompt
    if bg_name:
        g["60"] = {"class_type": "LoadVideo", "inputs": {"file": bg_name}}
        g["61"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["60", 0]}}
        g["62"] = {"class_type": "LoadVideo", "inputs": {"file": mask_name}}
        g["63"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["62", 0]}}
        g["64"] = {"class_type": "ImageToMask", "inputs": {"image": ["63", 0], "channel": "red"}}
        g["11"]["inputs"]["background_video"] = ["61", 0]
        g["11"]["inputs"]["character_mask"] = ["64", 0]
    return g


def chain(x, ros, ref_name: str, pose_name: str, seed: int, prompt: str, dest: Path, tag: str, bg: str | None = None, mask: str | None = None) -> dict:
    batches = 1 + -(-(N - BATCH) // (BATCH - CARRY))
    frames, rows, carry = [], [], []
    for k in range(batches):
        offset = 0 if k == 0 else BATCH + (BATCH - CARRY) * (k - 1)
        g = animate_graph(ros, ref_name, pose_name, seed, offset, carry, prompt, f"e23b/{tag}_b{k + 1}", bg, mask)
        x.vram.lap()
        h, _, exec_s = x.e.run(g, timeout=3600)
        if h.get("status", {}).get("status_str") == "error":
            raise RuntimeError(f"{tag} batch {k + 1}: {json.dumps(h['status'].get('messages', []))[-800:]}")
        fr = A.download(x.e, h, "15", dest / f"b{k + 1}")
        rows.append({"batch": k + 1, "chain_start": len(frames), "exec_s": round(exec_s, 1), "peak_vram_gb": x.vram.lap()})
        frames += fr if k == 0 else fr[CARRY:]
        carry = [x.e.upload(p) for p in fr[-CARRY:]]
        log(f"  {tag} batch {k + 1}/{batches}: {exec_s:.0f} s, peak {rows[-1]['peak_vram_gb']} GB")
    cd = dest / "chain"
    shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
    for i, p in enumerate(frames[:N]):
        shutil.copy2(p, cd / f"{i:04d}.png")
    return {"batches": rows, "joins": [r["chain_start"] for r in rows[1:]]}


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    """A square dilation by r px through a summed-area table (a 2r+1 max filter, without PIL's per-pixel cost at large r)."""
    a = (m > 0).astype(np.int32)
    if r <= 0:
        return a > 0
    c = np.pad(a, ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
    k = 2 * r + 1
    box = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return box > 0


def soft(m: np.ndarray, r: float) -> np.ndarray:
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255.0


def stage_mask(fid: str, i: int) -> np.ndarray:
    return np.asarray(Image.open(OUT / "stage" / fid / "mask" / f"{i:04d}.png").convert("L")) > 127


def order() -> list[str]:
    """Far → near over the shot (the mean camera distance)."""
    dist = json.loads((OUT / "stage" / "dist.json").read_text(encoding="utf-8"))
    return sorted(FIGS, key=lambda f: -np.mean([d[f] for d in dist]))


def contact_shadow(kp: list) -> np.ndarray:
    """The stand-in for Stage's shadow pass: a soft ellipse under the ankles (COCO 10, 13), its width a third of the figure's height."""
    s = np.zeros((H, W), np.float32)
    pts = [p for p in kp if p[2] > 0]
    if len(pts) < 4 or kp[10][2] <= 0 or kp[13][2] <= 0:
        return s
    ys = [p[1] for p in pts]
    fh = max(ys) - min(ys)
    cx, cy = (kp[10][0] + kp[13][0]) / 2, max(kp[10][1], kp[13][1]) + 0.02 * fh
    rw, rh = max(abs(kp[10][0] - kp[13][0]) / 2 + 0.12 * fh, 0.14 * fh), 0.035 * fh + 2
    im = Image.new("L", (W, H), 0)
    ImageDraw.Draw(im).ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=255)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(max(2, rh * 0.8))), dtype=np.float32) / 255.0


def matte(x, ros, dest: Path, fid: str, layer: dict) -> None:
    """E22's per-frame SAM 3 detection by text ("woman:2", the union), on the layer's own clip. One fixed box over the clip (E21's box
    path) returned noise here."""
    from e22_layers import sam_text_graph
    A.encode(frames_of(dest / fid / "chain"), dest / f"{fid}.mp4", FPS, crf=12)
    x.vram.lap()
    h, _, sam_s = x.e.run(sam_text_graph(ros, x.e.upload(dest / f"{fid}.mp4"), "woman:2", f"e23b/sam_{dest.name}_{fid}"), timeout=1800)
    shutil.rmtree(dest / fid / "sam", ignore_errors=True)
    A.download(x.e, h, "99", dest / fid / "sam")
    layer["sam_s"] = round(sam_s, 1)
    layer["sam_peak_vram_gb"] = x.vram.lap()
    log(f"  SAM 3 matte {FIGS[fid]}: {sam_s:.0f} s")


def kept_mattes(dest: Path, f: str, grow: int, layer: dict) -> list[np.ndarray]:
    """A layer's SAM 3 matte kept inside its Stage mask grown by `grow` px (a second figure elsewhere — the reference left standing, a
    ghost — is cut away and counted); a frame whose matte lost more than 60 % of the median area (a missed detection) reuses the previous
    frame's (E22)."""
    sams = [np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0 for p in frames_of(dest / f / "sam")]
    inside, outside, held = [], [], 0
    keep = [s_ * dilate(stage_mask(f, i), grow) for i, s_ in enumerate(sams)]
    med = float(np.median([k.sum() for k in keep]))
    for i in range(N):
        if i and keep[i].sum() < 0.4 * med:
            keep[i] = keep[i - 1]; held += 1
        inside.append(float(keep[i].sum())); outside.append(float((sams[i] * ~dilate(stage_mask(f, i), grow)).sum()))
    layer["matte_held_frames"] = held
    layer["ghost_frames"] = int(sum(1 for a, b in zip(inside, outside) if b > 0.3 * max(a, 1.0)))
    log(f"  {FIGS[f]}: matte held {held} frames, a second figure outside the blocking in {layer['ghost_frames']} of {N} frames")
    return keep


def assemble_m(dest: Path, kps: dict, plate_fr: list, layers: dict) -> None:
    """The plate, the contact shadows, then the layers far → near per frame by camera distance. A layer's alpha is its SAM matte inside its
    Stage mask grown by 36 px (a second figure elsewhere in the layer — the reference left standing, a ghost — is cut away and measured);
    a frame whose matte lost more than 60 % of the median area (a missed detection) reuses the previous frame's (E22)."""
    dist = json.loads((OUT / "stage" / "dist.json").read_text(encoding="utf-8"))
    md = dest / "merged"
    shutil.rmtree(md, ignore_errors=True); md.mkdir(parents=True)
    sams = {f: kept_mattes(dest, f, 36, layers[f]) for f in FIGS}
    alphas = {f: [] for f in FIGS}
    for i in range(N):
        out = plate_fr[i].copy()
        sh = np.clip(sum(contact_shadow(kps[f][i]) for f in FIGS), 0, 1)
        out *= (1 - 0.45 * sh)[..., None]
        for fid in sorted(FIGS, key=lambda f: -dist[min(i, len(dist) - 1)][f]):
            layer = arr(frames_of(dest / fid / "chain")[i])
            al = soft(sams[fid][i], 1.2) * dilate(sams[fid][i] > 0.5, 3)
            out = out * (1 - al[..., None]) + layer * al[..., None]
            alphas[fid].append(al.astype(np.float16))
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(md / f"{i:04d}.png")
    np.savez_compressed(dest / "alpha.npz", **{f: np.stack(v) for f, v in alphas.items()})


def r_background(cur: list, fid: str, variant: str) -> list[np.ndarray]:
    """What R's background shows where the figure goes: `grey` the dilated region blanked to mid grey (the first fix — the model kept it, a
    flat cut-out); `black` the same in black; `clay` the figure itself as a shaded dummy (Stage's figure-only depth, the set's subtracted,
    mapped to a clay grey) inside its exact mask, the plate around it — Replace swaps a person who is in the video for the character."""
    out = []
    for i, fr in enumerate(cur):
        b = fr.copy()
        m = stage_mask(fid, i)
        if variant == "clay":
            d = np.asarray(Image.open(OUT / "stage" / fid / "depth" / f"{i:04d}.png").convert("L"), dtype=np.float32)
            v = d[m]
            if v.size:
                t = (d - v.min()) / max(1.0, float(v.max() - v.min()))
                b[m] = (95 + 120 * t[m])[..., None] * np.array([1.0, 0.97, 0.93])
        else:
            b[dilate(m, 12)] = 127.5 if variant == "grey" else 0.0
        out.append(b)
    return out


def rtest(a: argparse.Namespace) -> int:
    """One batch of Mara's R layer per background variant, the same seed: does the character appear?"""
    s = load_state()
    ros = A.roster()
    plate_fr = [arr(p) for p in frames_of(OUT / "plate")]
    fid = "fig_m"
    c = CAST[FIGS[fid]]
    prompt = f"{SCENE}. {c['desc'][0].upper() + c['desc'][1:]} {c['act']}. The camera slowly moves in."
    with A.Session() as x:
        ref = x.e.upload(A.pad_reference(OUT / "refs" / "mara.png", OUT / "refs" / "mara_padded.png"))
        pose = x.e.upload(OUT / "stage" / f"pose_{fid}.mp4")
        mask = x.e.upload(OUT / "stage" / f"mask_{fid}.mp4")
        for variant in a.variants.split(","):
            d = OUT / "rtest" / variant
            shutil.rmtree(d, ignore_errors=True); (d / "bg").mkdir(parents=True)
            for i, b in enumerate(r_background(plate_fr, fid, variant)[:BATCH]):
                Image.fromarray(np.clip(b, 0, 255).astype(np.uint8)).save(d / "bg" / f"{i:04d}.png")
            A.encode(frames_of(d / "bg"), d / "bg.mp4", FPS, crf=12)
            g = animate_graph(ros, ref, pose, SEEDS[0], 0, [], prompt, f"e23b/rtest_{variant}", x.e.upload(d / "bg.mp4"), mask)
            h, _, ex = x.e.run(g, timeout=3600)
            A.download(x.e, h, "15", d / "out")
            s.setdefault("rtest", {})[variant] = {"exec_s": round(ex, 1)}
            log(f"rtest {variant}: {ex:.0f} s")
    save_state(s)
    return 0



def rematte(a: argparse.Namespace) -> int:
    """Re-matte and re-assemble the M runs already made (no new Wan generation)."""
    s = load_state()
    ros = A.roster()
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in FIGS}
    plate_fr = [arr(p) for p in frames_of(OUT / "plate")]
    with A.Session() as x:
        for r in s.get("runs", []):
            if r["arm"] != "M":
                continue
            dest = OUT / "runs" / f"M_s{r['seed']}"
            log(f"M seed {r['seed']}: re-matte")
            for fid in r["order"]:
                matte(x, ros, dest, fid, r["layers"][fid])
            assemble_m(dest, kps, plate_fr, r["layers"])
            A.encode(frames_of(dest / "merged"), dest / "merged.mp4", FPS, crf=12)
            r["peak_vram_gb"] = max(r["peak_vram_gb"], *[L.get("sam_peak_vram_gb", 0) for L in r["layers"].values()])
            save_state(s)
    return 0



def run(a: argparse.Namespace) -> int:
    s = load_state()
    if "framing" not in s or not (OUT / "plate.mp4").is_file() or "refs" not in s:
        print("refs, stage and plate first"); return 2
    ros = A.roster()
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in FIGS}
    far_near = order()
    s["order"] = far_near
    # the masks as videos (R's character_mask, dilated 12 px) and the union boxes for SAM (M)
    for fid in FIGS:
        ms = [dilate(stage_mask(fid, i), 12) for i in range(N)]
        A.encode([np.repeat((m * 255).astype(np.uint8)[..., None], 3, axis=2) for m in ms], OUT / "stage" / f"mask_{fid}.mp4", FPS, crf=0)
        ys, xs = np.nonzero(np.any(np.stack(ms), axis=0))
        s.setdefault("boxes", {})[fid] = [int(max(0, xs.min() - 30)), int(max(0, ys.min() - 30)), int(min(W, xs.max() + 30)), int(min(H, ys.max() + 30))]
    save_state(s)
    done = {(r["arm"], r["seed"]) for r in s.get("runs", [])}
    plan = [(arm, seed) for i, seed in enumerate(SEEDS) for arm in (("M", "R") if i % 2 == 0 else ("R", "M")) if arm in ARMS]
    with A.Session() as x:
        refs_ = {f: x.e.upload(A.pad_reference(OUT / "refs" / f"{FIGS[f].lower()}.png", OUT / "refs" / f"{FIGS[f].lower()}_padded.png")) for f in FIGS}
        poses = {f: x.e.upload(OUT / "stage" / f"pose_{f}.mp4") for f in FIGS}
        masks_ = {f: x.e.upload(OUT / "stage" / f"mask_{f}.mp4") for f in FIGS}
        plate_name = x.e.upload(OUT / "plate.mp4")
        plate_fr = [arr(p) for p in frames_of(OUT / "plate")]
        for arm, seed in plan:
            if (arm, seed) in done:
                continue
            t0 = time.time()
            dest = OUT / "runs" / f"{arm}_s{seed}"
            log(f"{arm} seed {seed}")
            layers = {}
            if arm == "M":
                for fid in far_near:
                    c = CAST[FIGS[fid]]
                    prompt = f"{c['desc'][0].upper() + c['desc'][1:]} {c['act']}. Plain light grey studio background, static camera."
                    layers[fid] = chain(x, ros, refs_[fid], poses[fid], seed, prompt, dest / fid, f"M_s{seed}_{fid}")
                    matte(x, ros, dest, fid, layers[fid])
                assemble_m(dest, kps, plate_fr, layers)
            else:
                bg_name, cur = plate_name, [p.copy() for p in plate_fr]
                alphas = {}
                for li, fid in enumerate(far_near):
                    c = CAST[FIGS[fid]]
                    prompt = f"{SCENE}. {c['desc'][0].upper() + c['desc'][1:]} {c['act']}. The camera slowly moves in."
                    # the background the character goes into: the plate (or the previous layer's result) with the figure's region (dilated 12 px)
                    # set to black — Wan 2.2's own replace preprocessing (src_bg = frame · (1 − mask)); rtest: the plate's pixels there inserted no
                    # one, mid grey or a clay dummy were kept as they are
                    bd = dest / f"bg_{li + 1}"; bd.mkdir(parents=True, exist_ok=True)
                    for i, b in enumerate(r_background(cur, fid, R_BG)):
                        Image.fromarray(np.clip(b, 0, 255).astype(np.uint8)).save(bd / f"{i:04d}.png")
                    A.encode(frames_of(bd), dest / f"bg_{li + 1}.mp4", FPS, crf=12)
                    bg_name = x.e.upload(dest / f"bg_{li + 1}.mp4")
                    layers[fid] = chain(x, ros, refs_[fid], poses[fid], seed, prompt, dest / fid, f"R_s{seed}_{fid}", bg_name, masks_[fid])
                    # the model leaves the black where the character does not cover the region: only her own SAM 3 matte is pasted back
                    matte(x, ros, dest, fid, layers[fid])
                    keep = kept_mattes(dest, fid, 12, layers[fid])
                    al_all = []
                    for i, p in enumerate(frames_of(dest / fid / "chain")):
                        al = soft(keep[i], 1.2) * dilate(keep[i] > 0.5, 3)
                        cur[i] = cur[i] * (1 - al[..., None]) + arr(p) * al[..., None]
                        al_all.append(al.astype(np.float16))
                    alphas[fid] = np.stack(al_all)
                    ld = dest / f"after_{li + 1}"; ld.mkdir(parents=True, exist_ok=True)
                    for i, fr in enumerate(cur):
                        Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).save(ld / f"{i:04d}.png")
                    A.encode(frames_of(ld), dest / f"after_{li + 1}.mp4", FPS, crf=12)   # the next layer goes into this layer's result
                md = dest / "merged"
                shutil.rmtree(md, ignore_errors=True)
                shutil.copytree(dest / f"after_{len(far_near)}", md)
                np.savez_compressed(dest / "alpha.npz", **alphas)
            A.encode(frames_of(dest / "merged"), dest / "merged.mp4", FPS, crf=12)
            row = {"arm": arm, "seed": seed, "layers": layers, "wall_min": round((time.time() - t0) / 60, 1), "order": far_near,
                   "peak_vram_gb": max([b["peak_vram_gb"] for L in layers.values() for b in L["batches"]] + [L.get("sam_peak_vram_gb", 0) for L in layers.values()]),
                   "stamp": time.strftime("%Y-%m-%d %H:%M")}
            s.setdefault("runs", []).append(row)
            save_state(s)
            log(f"{arm} seed {seed}: {row['wall_min']} min, peak {row['peak_vram_gb']} GB")
    return 0


# ---- 5 · the scores ----------------------------------------------------------------------------------------------------------------
def grad(a: np.ndarray) -> np.ndarray:
    L = a.mean(axis=2) if a.ndim == 3 else a
    gx, gy = np.zeros_like(L), np.zeros_like(L)
    gx[:, 1:-1] = L[:, 2:] - L[:, :-2]; gy[1:-1] = L[2:] - L[:-2]
    return np.hypot(gx, gy)


def score_run(r: dict, eng, fs, heroes: dict, kps: dict) -> dict:
    from e10_stage import pck, sdpose_graph
    dest = OUT / "runs" / f"{r['arm']}_s{r['seed']}"
    merged = frames_of(dest / "merged")
    plate_fr = frames_of(OUT / "plate")
    alpha = np.load(dest / "alpha.npz")
    joins = next(iter(r["layers"].values()))["joins"]
    starts = [0] + joins + [N]
    batch_of = lambda i: max(k for k in range(len(starts) - 1) if starts[k] <= i)   # noqa: E731
    hits = {f: [0, 0] for f in FIGS}
    sims = {f: {} for f in FIGS}
    for i in range(0, N, 8):
        hp, _, _ = eng.run(sdpose_graph(eng.upload(merged[i])))
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        for f in FIGS:
            h_, t_ = pck([kps[f][i]], people); hits[f][0] += h_; hits[f][1] += t_
        im = np.asarray(Image.open(merged[i]).convert("RGB").resize((W * 2, H * 2), Image.BICUBIC))
        for face in fs.detect(im):
            cx, cy = (face.bbox[0] + face.bbox[2]) / 4, (face.bbox[1] + face.bbox[3]) / 4        # back to frame pixels (detected at 2×)
            near = min(FIGS, key=lambda f: np.hypot(kps[f][i][0][0] - cx, kps[f][i][0][1] - cy) if kps[f][i][0][2] > 0 else 1e9)
            if kps[near][i][0][2] > 0 and np.hypot(kps[near][i][0][0] - cx, kps[near][i][0][1] - cy) < 40:
                sims[near].setdefault(batch_of(i), []).append(float(fs.similarity(heroes[near], fs.embed(im, face.kps))))
    # joins (local ratio, E23a) on the merged clip, background flicker outside the figures, R's drift around the figure, the band step
    gs = [A.grey(p) for p in merged]
    st = np.array([float(np.mean(np.abs(gs[i] - gs[i + 1]))) for i in range(N - 1)])
    jr = []
    for j in joins:
        loc = np.r_[st[j - 7:j - 1], st[j:j + 6]]
        jr.append({"frame": j, "seam": round(float(st[j - 1]), 2), "local": round(float(np.median(loc)), 2), "ratio": round(float(st[j - 1] / max(1e-6, np.median(loc))), 2)})
    fl_m, fl_p, drift, band = [], [], [], []
    for i in range(0, N - 1, 4):
        fig = np.zeros((H, W), bool)
        for f in FIGS:
            fig |= dilate(stage_mask(f, i) | stage_mask(f, i + 1), 24) | (alpha[f][i] > 0.02) | (alpha[f][i + 1] > 0.02)
        bgm = ~fig
        a0, a1, p0, p1 = arr(merged[i]), arr(merged[i + 1]), arr(plate_fr[i]), arr(plate_fr[i + 1])
        fl_m.append(float(np.abs(a0 - a1).mean(axis=2)[bgm].mean())); fl_p.append(float(np.abs(p0 - p1).mean(axis=2)[bgm].mean()))
        for f in FIGS:
            al = alpha[f][i].astype(np.float32)
            ring = (al > 0.02) & ~dilate(stage_mask(f, i), 4)
            if ring.sum() > 50:
                drift.append(float(np.abs(a0 - p0).mean(axis=2)[ring].mean()))
            b = dilate((al > 0.05) & (al < 0.95), 1)
            if b.sum() > 20:
                layer = arr(frames_of(dest / f / "chain")[i])
                band.append(float(grad(a0)[b].mean() / max(1e-6, grad(layer)[b].mean())))
    face = {FIGS[f]: {f"b{k + 1}": round(float(np.mean(v)), 3) for k, v in sorted(sims[f].items())} for f in FIGS}
    drops = {}
    for f in FIGS:
        b1, bl = sims[f].get(0), sims[f].get(len(starts) - 2)
        drops[FIGS[f]] = round(float(np.mean(b1) - np.mean(bl)), 3) if b1 and bl else None
    out = {"arm": r["arm"], "seed": r["seed"], "pck": {FIGS[f]: round(h / t, 3) if t else None for f, (h, t) in hits.items()}, "facesim": face, "face_drop": drops,
           "joins": jr, "bg_flicker": round(float(np.mean(fl_m)), 3), "plate_flicker": round(float(np.mean(fl_p)), 3),
           "ring_drift": round(float(np.mean(drift)), 2) if drift else None, "band_grad_ratio": round(float(np.median(band)), 3) if band else None,
           "wall_min": r["wall_min"], "peak_vram_gb": r["peak_vram_gb"],
           "exec_s": {FIGS[f]: [b["exec_s"] for b in L["batches"]] + ([L["sam_s"]] if "sam_s" in L else []) for f, L in r["layers"].items()}}
    out["bars"] = {"pck": all(v is not None and v >= BARS["pck"] for v in out["pck"].values()),
                   "face_drop": all(v is None or v <= BARS["face_drop"] for v in drops.values()),
                   "seam": all(j["ratio"] <= BARS["seam"] for j in jr), "vram": out["peak_vram_gb"] <= BARS["vram_gb"], "time": out["wall_min"] <= BARS["shot_min"],
                   "background": out["bg_flicker"] <= out["plate_flicker"] * 1.1}
    return out


def score(a: argparse.Namespace) -> int:
    from loom2.tools.facesim import FaceSim
    s = load_state()
    if not s.get("runs"):
        print("run first"); return 2
    fs = FaceSim(MODELS)
    heroes = {}
    for f, name in FIGS.items():
        im = np.asarray(Image.open(OUT / "refs" / f"{name.lower()}.png").convert("RGB"))
        heroes[f] = fs.embed(im, max(fs.detect(im), key=lambda q: q.area).kps)
    kps = {f: json.loads((OUT / "stage" / f / "keypoints.json").read_text(encoding="utf-8")) for f in FIGS}
    scores = []
    with A.Session() as x:
        for r in s["runs"]:
            sc = score_run(r, x.e, fs, heroes, kps)
            scores.append(sc)
            log(f"{sc['arm']} s{sc['seed']}: PCK {sc['pck']}, FaceSim {sc['facesim']} drop {sc['face_drop']}, joins {[(j['frame'], j['ratio']) for j in sc['joins']]}, "
                f"bg flicker {sc['bg_flicker']} (plate {sc['plate_flicker']}), ring drift {sc['ring_drift']}, band {sc['band_grad_ratio']}, {sc['wall_min']} min, "
                f"peak {sc['peak_vram_gb']} GB")
    for r in s["runs"]:                                          # RIFE after the engine stops (one GPU job at a time)
        d = OUT / "runs" / f"{r['arm']}_s{r['seed']}"
        src = d / "chain"
        if src.exists() and not src.is_dir():
            src.unlink()
        shutil.rmtree(src, ignore_errors=True); shutil.copytree(d / "merged", src)
        fr = A.rife(d, 241)
        A.encode(fr, d / "merged24.mp4", 24, crf=14)
        shutil.rmtree(src, ignore_errors=True)
    outputs(s["runs"], scores)
    s["scores"] = scores
    s["scored_at"] = time.strftime("%Y-%m-%d %H:%M")
    save_state(s)
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f_:
        f_.write(json.dumps({"at": s["scored_at"], "scores": scores}) + "\n")
    return 0


def outputs(runs: list[dict], scores: list[dict]) -> None:
    seqs = {(r["arm"], r["seed"]): frames_of(OUT / "runs" / f"{r['arm']}_s{r['seed']}" / "rife24") for r in runs}
    if not seqs:
        return
    n = min(len(v) for v in seqs.values())
    tw, th = W // 2, H // 2
    grid = []
    for i in range(n):
        im = Image.new("RGB", (tw * 2, th * len(SEEDS)), (0, 0, 0))
        for row, seed in enumerate(SEEDS):
            for col, arm in enumerate(("M", "R")):
                p = seqs.get((arm, seed))
                if p:
                    t = Image.open(p[i]).convert("RGB").resize((tw, th), Image.LANCZOS)
                    im.paste(A.label(t, f"{'Move' if arm == 'M' else 'Replace'} · seed {seed} · {i / 24:.2f} s"), (col * tw, row * th))
        grid.append(np.asarray(im))
    A.encode(grid, OUT / "compare.mp4", 24, crf=16)
    cw, ch, cols = 166, 96, 11
    cs = Image.new("RGB", (8 + cols * (cw + 2), 8 + len(scores) * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(cs)
    for ri, sc in enumerate(scores):
        merged = frames_of(OUT / "runs" / f"{sc['arm']}_s{sc['seed']}" / "merged")
        y = 8 + ri * (ch + 18)
        dr.text((8, y), f"{sc['arm']} seed {sc['seed']} · PCK {sc['pck']} · FaceSim drop {sc['face_drop']} · joins {[j['ratio'] for j in sc['joins']]} · {sc['wall_min']} min", fill=(230, 230, 230))
        for c in range(cols):
            cs.paste(Image.open(merged[min(len(merged) - 1, c * FPS)]).convert("RGB").resize((cw, ch), Image.LANCZOS), (8 + c * (cw + 2), y + 14))
    cs.save(OUT / "sheet.jpg", quality=90)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["refs", "stage", "masks", "plate", "run", "rematte", "rtest", "score"])
    ap.add_argument("--variants", default="clay,black")
    a = ap.parse_args()
    if a.step == "masks":
        masks(load_state()); return 0
    return {"refs": refs, "stage": stage, "plate": plate, "run": run, "rematte": rematte, "rtest": rtest, "score": score}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
