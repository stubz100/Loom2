"""Spike E28 (proto01_animate 01 §10, 02 §3): props — "exactly like characters, except the skeleton" (the author). In E22's room with E23c's
locked camera and window light. Three props, three ways to perform one:

  P1  the BOX — a rigid prop moved by keys (a small red-painted wooden chest slid across the floor): its animation reference cut out and
      placed in each frame where Stage's stand-in block is (the block's mask: its height and foot), with the block's own shadow (Stage's
      lit clay). No generation.
  P2  the DOOR — a prop that turns (a green panelled door against the back wall, opening about its hinge): the app's own Stage clip path —
      a Stage shot of the first frame (Klein 9B on the clay pass, the door's reference and the room plate as images 2 and 3), then
      LTX-2.3 guided by the door's depth sequence (the IC-LoRA, D76) from that shot.
  P1 vs P3, the CUP — a held prop: (P1) a white mug's cut-out put at Mara's hand in every frame (her right wrist as SDPose found it in
      E23c's Move layer — the anchor pin of D107) against (P3) Mara's animation reference made holding the mug, so Wan Animate draws it in
      her layer.

Measured: the shape kept (the door: SAM 3 "door" in the clip against Stage's door mask, IoU, while it opens; the box: by construction),
the prop's colour against its reference (ΔE of the mean), the cup's presence and its distance from the hand (P3: SAM 3 "white mug" and
SDPose's right wrist in every 4th frame), time. For the author: box.mp4, door.mp4 (the clip | Stage's depth), cup.mp4 (P1 | P3).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e28_props.py refs     # the props' and Mara-with-the-mug's references (the app's route; GPU)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e28_props.py stage    # the blocking, the sequences, the door's shot and clip (Edge + the app's queue)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e28_props.py cup      # P3's Move layer (GPU)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e28_props.py mattes   # the references' BiRefNet mattes (the cut-outs; a white mug on light grey defeats a colour key)
  orchestrator/.venv/Scripts/python.exe engine/spikes/e28_props.py score    # SAM 3 / SDPose (GPU), the clips, the measures
Outputs under engine/spikes/out/e28/ (git-ignored).
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e28"
E23C, E23E = ROOT / "engine" / "spikes" / "out" / "e23c", ROOT / "engine" / "spikes" / "out" / "e23e"
E22 = ROOT / "engine" / "spikes" / "out" / "e22"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
SEED = 20261021
PORT, TOKEN, DEV, DBG = 8792, "e28", 1420, 9342
PROPS = {
    "Chest": "a small red-painted wooden chest with iron corners",
    "Door": "a green panelled wooden door with a brass handle",
    "Mug": "a plain white ceramic mug",
}
BOX0, BOX1 = [1.5, 0.0, -0.4], [0.5, 0.0, 0.7]                   # the chest slides from the right towards the front over the shot
HINGE, DOOR_W, DOOR_H = [-0.45, 0.0, -2.98], 0.9, 2.0             # the door against the back wall (z −3.1), opening into the room
DOOR_OPEN = (24, 96, -80.0)                                       # Stage frames (24 fps): opening from 24 to 96, to −80° (towards the camera)
CLIP_FRAMES = 121                                                 # LTX-2.3: 5 s at 24 fps


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        b = r.read()
        return b if raw else json.loads(b.decode("utf-8") or "null")


def wait_job(jid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        if api("GET", "/queue").get("paused"):
            raise RuntimeError(f"the queue is paused while {jid} waits")
        time.sleep(1.5)
    raise TimeoutError(jid)


def drain(timeout: float = 600) -> None:
    """Wait until nothing is queued or running (the auto body fit, CA1b, follows a character's first reference)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not [x for x in api("GET", "/jobs")["items"] if x["status"] in ("queued", "running", "preparing")]:
            return
        time.sleep(1.5)


class App:
    """A private orchestrator on its own project (engine on 8188: it runs the jobs, one at a time)."""
    def __init__(self, project: Path):
        from loom2.config import AppState
        from m1_acceptance import port_busy
        if port_busy(8188):
            raise SystemExit("the engine port is busy — one GPU job at a time")
        self.tmp = Path(tempfile.mkdtemp(prefix="loom2-e28-"))
        AppState(self.tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [],
                                                      "variant": "full", "engine": {"port": 8188}})
        self.proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(self.tmp / "state")], cwd=str(ROOT / "orchestrator"),
                                     env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"},
                                     stdout=(OUT / "orchestrator.log").open("a", encoding="utf-8"), stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        if project.exists():
            api("POST", "/project/open", {"path": str(project)})
        else:
            api("POST", "/project", {"path": str(project), "name": "E28", "size_cap_gb": 30})
        if api("GET", "/queue").get("paused"):                       # an earlier run stopped unclean: the queue reopens paused
            api("POST", "/queue/unpause")

    def close(self) -> None:
        try:
            drain()
            api("POST", "/engine/stop"); api("POST", "/shutdown"); time.sleep(1.5)
        except Exception:
            pass
        if self.proc.poll() is None:
            self.proc.kill()


def refs(a: argparse.Namespace) -> int:
    """The three props' animation references (Cast props, CA0's route: the object alone, a three-quarter view) and Mara holding the mug
    (E22's Mara as a Cast character, her outfit naming the mug)."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "refs").mkdir(exist_ok=True)
    s = load_state()
    s["project"] = str(OUT / "project")
    app = App(Path(s["project"]))
    try:
        jobs = {}
        for name, desc in PROPS.items():
            p = api("POST", "/story/profiles", {"name": name, "cls": "prop", "appearance": desc})
            jobs[name] = (p["id"], api("POST", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "count": 1})["job_ids"][0])
        hero = api("POST", "/assets/import", {"paths": [str(E22 / "heroes" / "L.png")]})["items"][0]["id"]
        p = api("POST", "/story/profiles", {"name": "Mara", "cls": "character", "hero_asset_id": hero, "appearance": "Mara, a young woman with a black bob and round glasses",
                                            "outfit": "a grey wool coat, black trousers, black shoes; she holds a plain white ceramic mug in her right hand",
                                            "colours": [{"hex": "#7A7A7A", "object": "wool coat"}, {"hex": "#F4F4F2", "object": "mug"}]})
        jobs["Mara_mug"] = (p["id"], api("POST", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "count": 1})["job_ids"][0])
        for name, (pid, jid) in jobs.items():
            j = wait_job(jid)
            if j["status"] != "done":
                print(name, j["status"], j.get("error")); return 1
            v = next(x for x in api("GET", f"/story/profiles/{pid}")["versions"] if x["id"] == "v1")
            (OUT / "refs" / f"{name.lower()}.png").write_bytes(api("GET", f"/assets/{v['anim_ref_asset_id']}/file", raw=True))
            s.setdefault("refs", {})[name] = {"profile": pid, "asset": v["anim_ref_asset_id"], "job_wall_s": j.get("wall_s")}
            log(f"{name}: reference in {j.get('wall_s')} s")
        save_state(s)
    finally:
        app.close()
    return 0


# ---- the blocking: the chest's slide, the door's swing; the sequences; the door's shot and clip ------------------------------------
def door_at(f: float) -> tuple[list[float], list[float]]:
    """The door's centre and turn at Stage frame f: hinged at HINGE, opening from DOOR_OPEN[0] to [1] (eased) to DOOR_OPEN[2] degrees."""
    a0, a1, ang = DOOR_OPEN
    t = min(1.0, max(0.0, (f - a0) / (a1 - a0)))
    th = ang * (t * t * (3 - 2 * t))
    r = math.radians(th)
    cx, cz = HINGE[0] + math.cos(r) * DOOR_W / 2, HINGE[2] - math.sin(r) * DOOR_W / 2
    return [round(cx, 4), 0.0, round(cz, 4)], [0.0, round(th, 3), 0.0]


STAGE_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const An = await import('/src/suites/stage/anim.ts')
  const st = S.st
  const key = (id, f, pos, rot, scale) => { st().setFrame(f); st().setTransform(id, { pos, rot, scale }); st().keyObject(id) }
  key('box', 0, %BOX0%, [0, 20, 0], [1, 1, 1]); key('box', 240, %BOX1%, [0, 20, 0], [1, 1, 1])
  for (const [f, pos, rot] of %DOORKEYS%) key('door', f, pos, rot, [%DW%, %DH% , 0.05])
  st().setRange(0, 240); st().setFrame(0)
  await new Promise((r) => setTimeout(r, 1500))
  const doc = st().current, R = st().sequenceRenderer
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  const frames = Array.from({ length: 161 }, (_, i) => An.sampleDoc(doc, (i * 24) / 16))
  const only = (d, keep) => ({ ...d, objects: d.objects.map((x) => (['box', 'door'].includes(x.id) && !keep.includes(x.id) ? { ...x, visible: false } : x)) })
  const seq = (keep) => frames.map((d) => ({ cam: d.cameras[0], doc: only(d, keep) }))
  window.__e28 = {}
  for (const [name, keep] of [['set', []], ['box', ['box']], ['door', ['door']]]) {
    window.__e28[name] = { depth: await Promise.all((await R(seq(keep), %W%, %H%, 'depth', An.sampleDoc(doc, 0))).blobs.map(b64)),
                           clay: await Promise.all((await R(seq(keep), %W%, %H%, 'clay', An.sampleDoc(doc, 0))).blobs.map(b64)) }
  }
  return { ok: true }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def stage(a: argparse.Namespace) -> int:
    from edit_headed_check import CDP, EDGE
    import e23b_layers as B
    import e23c_white as C
    s = load_state()
    if "refs" not in s:
        print("refs first"); return 2
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    app = App(Path(s["project"]))
    edge = None
    try:
        drain()                                                     # nothing on the GPU while the browser renders (D97): the queue empty,
        api("POST", "/engine/stop")                                 # the engine stopped — the shot job starts it again
        st = api("POST", "/stages", {"name": "E28 props"})
        cam = {**st["cameras"][0], **B.C0}
        tf = lambda pos, rot=(0, 0, 0), sc=(1, 1, 1): {"pos": list(pos), "rot": list(rot), "scale": list(sc)}   # noqa: E731
        d0 = door_at(0)
        objs = [{"id": "set_a", "kind": "set", "name": "Room", "preset": "room", "transform": tf((0, 0, 0)), "colour_id": 3},
                C.LIGHT,
                {"id": "box", "kind": "prop", "name": "Chest", "preset": "crate", "transform": tf(BOX0, (0, 20, 0)), "colour_id": 4},
                {"id": "door", "kind": "prop", "name": "Door", "preset": "block", "transform": tf(d0[0], d0[1], (DOOR_W, DOOR_H, 0.05)), "colour_id": 5}]
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}})
        url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={app.tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
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
        cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 4", timeout=30, settle=6.0)
        door_keys = [[f, *door_at(f)] for f in list(range(DOOR_OPEN[0], DOOR_OPEN[1] + 1, 6)) + [0, 240]]
        js = (STAGE_JS.replace("%BOX0%", json.dumps(BOX0)).replace("%BOX1%", json.dumps(BOX1)).replace("%DOORKEYS%", json.dumps(sorted(door_keys)))
              .replace("%DW%", str(DOOR_W)).replace("%DH%", str(DOOR_H)).replace("%W%", str(B.W)).replace("%H%", str(B.H)))
        r = cdp.eval(js, timeout=1800) or {}
        if not r or r.get("error"):
            print(r, cdp.page_errors()[:3]); return 1
        g = OUT / "stage"
        shutil.rmtree(g, ignore_errors=True)
        for name in ("set", "box", "door"):
            for kind in ("depth", "clay"):
                d = g / name / kind; d.mkdir(parents=True)
                for i in range(0, 161, 30):
                    for j, b in enumerate(cdp.eval(f"window.__e28.{name}.{kind}.slice({i}, {i + 30})", timeout=120)):
                        (d / f"{i + j:04d}.png").write_bytes(base64.b64decode(b))
        log("the sequences rendered (the set, the chest, the door; depth and lit clay)")
        # P2: the door's clip by the app's own Stage path — the chest hidden; a shot of the first frame, the depth guide, the guided clip
        plate = api("POST", "/assets/import", {"paths": [str(E22 / "stills" / "plate.png")]})["items"][0]["id"]
        cdp.eval("(async () => { const S = await import('/src/suites/stage/stageStore.ts'); S.st().updateObject('box', { visible: false }); S.st().setFrame(0) })()")
        time.sleep(1.5)
        prompt = ("The room is empty, there are no people in it. A quiet whitewashed room with bare plaster walls and a worn wooden floor, soft daylight "
                  "from a window on the left; against the back wall stands a closed green panelled wooden door with a brass handle. Natural colours, "
                  "cinematic film still, 35 mm.")                     # the first try (without "empty") drew two men, one of whom opened the door
        cdp.eval(f"window.__loom2Stage.setShot({json.dumps({'method': 'clay', 'refs': [{'asset_id': s['refs']['Door']['asset'], 'note': 'the door'}, {'asset_id': plate, 'note': 'the room'}], 'prompt_text': prompt, 'count': 1, 'use_as_is': True})})")
        if not cdp.eval("window.__loom2Stage.renderPasses()", timeout=180):
            print("the passes were not rendered", cdp.page_errors()[:3]); return 1
        t0 = time.time()
        jobs = cdp.eval("window.__loom2Stage.generateShot()", timeout=120) or []
        j = wait_job(jobs[0]["id"])
        if j["status"] != "done":
            print("shot", j["status"], j.get("error")); return 1
        shot = j["result"]["asset_ids"][0]
        (OUT / "door_shot.png").write_bytes(api("GET", f"/assets/{shot}/file", raw=True))
        s["door_shot"] = {"asset": shot, "wall_s": round(time.time() - t0, 1)}
        log(f"the door's first frame (Stage shot, Klein) in {time.time() - t0:.0f} s")
        cdp.eval(f"(async () => {{ const S = await import('/src/suites/stage/stageStore.ts'); S.st().setGuideKind('depth'); S.st().setRange(0, {CLIP_FRAMES - 1}) }})()")
        time.sleep(1.0)
        if not cdp.eval("window.__loom2Stage.renderGuide()", timeout=900):
            print("the guide was not rendered", cdp.page_errors()[:3]); return 1
        guide = (cdp.eval("window.__loom2Stage.state()") or {}).get("guide") or {}
        (OUT / "door_depth.mp4").write_bytes(api("GET", f"/assets/{guide['asset_id']}/file", raw=True))
        cdp.eval(f"window.__loom2Stage.setShotStart({json.dumps(shot)})")
        t0 = time.time()
        jobs = cdp.eval("window.__loom2Stage.animateShot()", timeout=120) or []
        j = wait_job(jobs[0]["id"])
        if j["status"] != "done":
            print("clip", j["status"], j.get("error")); return 1
        clip = j["result"]["clip_id"]
        s["door_clip"] = {"clip": clip, "wall_s": round(time.time() - t0, 1), "job_wall_s": j.get("wall_s"), "frames": guide.get("frames"), "model": j["recipe"].get("model_id")}
        cd = OUT / "door_clip"
        shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
        for k, p in enumerate(sorted((Path(s["project"]) / "clips" / clip / "master").glob("*.png"))):
            shutil.copy2(p, cd / f"{k:04d}.png")
        log(f"the door's clip ({s['door_clip']['model']}, {len(list(cd.glob('*.png')))} frames) in {time.time() - t0:.0f} s")
        save_state(s)
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        app.close()
    return 0


# ---- P3: Mara holding the mug, her Move layer --------------------------------------------------------------------------------------
def cup(a: argparse.Namespace) -> int:
    import e23a_joins as A
    os.environ["LOOM2_E23B_OUT"] = str(E23C)
    import e23b_layers as B
    ros = A.roster()
    s = load_state()
    dest = OUT / "runs" / "P3"
    shutil.rmtree(dest, ignore_errors=True)
    # the reference placed where she starts (E23c, D105: the reference's standing ghost is gone so; the first P3 run, with the reference
    # centred, put the mug in the ghost's hand and left the walking Mara without it) — on the reference's own grey ground
    kp0 = np.array(json.loads((E23C / "stage" / "fig_m" / "keypoints.json").read_text(encoding="utf-8"))[0], float)
    src = np.asarray(Image.open(OUT / "refs" / "mara_mug.png").convert("RGB"))
    ground = tuple(int(v) for v in np.median(np.concatenate([src[0], src[-1], src[:, 0], src[:, -1]]), axis=0))
    img, al = cutout(OUT / "refs" / "mara_mug.png")
    h = float(np.linalg.norm(kp0[0, :2] - (kp0[10, :2] + kp0[13, :2]) / 2))
    placed = paste(np.full((B.H, B.W, 3), ground, np.float32), img, al, float((kp0[8, 0] + kp0[11, 0]) / 2),
                   float((kp0[10, 1] + kp0[13, 1]) / 2 + 0.045 * h), h / 0.86)
    Image.fromarray(np.clip(placed, 0, 255).astype(np.uint8)).save(OUT / "refs" / "mara_mug_placed.png")
    t0 = time.time()
    with A.Session() as x:
        ref = x.e.upload(OUT / "refs" / "mara_mug_placed.png")
        pose = x.e.upload(E23C / "stage" / "pose_fig_m.mp4")
        c = B.CAST["Mara"]
        prompt = f"{c['desc'][0].upper() + c['desc'][1:]}, holding a white ceramic mug in her right hand, {c['act']}. Plain light grey studio background, static camera."
        layer = B.chain(x, ros, ref, pose, SEED, prompt, dest / "fig_m", "e28_P3")
        B.matte(x, ros, dest, "fig_m", layer)
    s["P3"] = {"layer": layer, "wall_min": round((time.time() - t0) / 60, 1)}
    save_state(s)
    return 0


# ---- the clips and the measures --------------------------------------------------------------------------------------------------
def subject_mattes() -> None:
    """The props' and Mara's cut-outs by the app's subject matte (BiRefNet, core nodes): a colour key cannot part a white mug from a light
    grey ground (its shaded side matches the ground). One short engine job per reference."""
    import e23a_joins as A
    with A.Session() as x:
        for name in ("chest", "door", "mug", "mara_mug"):
            g = {"1": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}},
                 "2": {"class_type": "LoadImage", "inputs": {"image": x.e.upload(OUT / "refs" / f"{name}.png")}},
                 "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["2", 0]}},
                 "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
                 "99": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": f"e28/matte_{name}"}}}
            h, _, _ = x.e.run(g)
            p = A.download(x.e, h, "99", OUT / "refs" / f"matte_{name}")[0]
            shutil.move(str(p), OUT / "refs" / f"{name}_matte.png")
            shutil.rmtree(OUT / "refs" / f"matte_{name}", ignore_errors=True)


def cutout(ref: Path) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(Image.open(ref).convert("RGB"))
    m = np.asarray(Image.open(ref.with_name(ref.stem + "_matte.png")).convert("L").resize((a.shape[1], a.shape[0])), dtype=np.float32) / 255.0
    ys, xs = np.nonzero(m > 0.5)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def paste(out: np.ndarray, img: np.ndarray, al: np.ndarray, cx: float, bottom: float, height: float) -> np.ndarray:
    """The cut-out scaled to `height` px, its foot centred at (cx, bottom), feathered 0.8 px."""
    h = max(4, int(height)); w = max(4, int(img.shape[1] * h / img.shape[0]))
    pi = np.asarray(Image.fromarray(img).resize((w, h), Image.LANCZOS), dtype=np.float32)
    pa = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32)[..., None] / 255.0
    x0, y0 = int(cx - w / 2), int(bottom - h)
    H, W = out.shape[:2]
    sx0, sy0, sx1, sy1 = max(0, -x0), max(0, -y0), min(w, W - x0), min(h, H - y0)
    if sx1 <= sx0 or sy1 <= sy0:
        return out
    reg = out[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
    out[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1] = reg * (1 - pa[sy0:sy1, sx0:sx1]) + pi[sy0:sy1, sx0:sx1] * pa[sy0:sy1, sx0:sx1]
    return out


def score(a: argparse.Namespace) -> int:
    import e23a_joins as A
    os.environ["LOOM2_E23B_OUT"] = str(E23C)
    import e23b_layers as B
    from e10_stage import sdpose_graph
    from e22_layers import sam_text_graph
    from loom2.tools.facesim import FaceSim  # noqa: F401  (the session's imports)
    s = load_state()
    g = OUT / "stage"
    plate = [B.arr(p) for p in B.frames_of(E23C / "plate")]
    lum = lambda p: np.asarray(Image.open(p).convert("L"), dtype=np.float32)   # noqa: E731
    mask_of = lambda name, i: np.abs(lum(g / name / "depth" / f"{i:04d}.png") - lum(g / "set" / "depth" / f"{i:04d}.png")) > 0.5   # noqa: E731
    ratio_of = lambda name, i: np.where(mask_of(name, i), 1.0, np.clip(lum(g / name / "clay" / f"{i:04d}.png") / np.maximum(8.0, lum(g / "set" / "clay" / f"{i:04d}.png")), 0, 1))   # noqa: E731
    # P1 · the chest: the cut-out where Stage's block stands, with the block's shadow
    img, al = cutout(OUT / "refs" / "chest.png")
    bd = OUT / "runs" / "box"; shutil.rmtree(bd, ignore_errors=True); bd.mkdir(parents=True)
    for i in range(161):
        out = plate[i] * ratio_of("box", i)[..., None]
        ys, xs = np.nonzero(mask_of("box", i))
        if len(ys):
            out = paste(out, img, al, float(xs.mean()), float(ys.max()), float(ys.max() - ys.min()) * 1.02)
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(bd / f"{i:04d}.png")
    A.encode(B.frames_of(bd), OUT / "box.mp4", 16, crf=14)
    # the colours against the references (ΔE of the mean colour of the object)
    def mean_lab(img_: np.ndarray, m: np.ndarray) -> np.ndarray:
        return A.lab(img_.astype(np.uint8))[m > 0.5].mean(axis=0)
    ref_lab = {n: mean_lab(*cutout(OUT / "refs" / f"{n.lower()}.png")) for n in ("Chest", "Door", "Mug")}
    res: dict = {}
    clip = sorted((OUT / "door_clip").glob("*.png"))
    with A.Session() as x:
        ros = A.roster()
        # P2 · the door: SAM 3 "door" in the clip against Stage's door mask (24 fps, the clip's own frames), IoU while it opens
        cw, ch = Image.open(clip[0]).size
        A.encode(clip, OUT / "door_clip.mp4", 24, crf=12)
        h, _, _ = x.e.run(sam_text_graph(ros, x.e.upload(OUT / "door_clip.mp4"), "door", "e28/sam_door"), timeout=1800)
        sam = A.download(x.e, h, "99", OUT / "door_sam")
        ious, des = [], []
        for k in range(0, len(clip), 4):
            f16 = min(160, int(round(k * 16 / 24)))                   # the Stage mask at the same moment (F16 sequences)
            sm = np.asarray(Image.fromarray((mask_of("door", f16) * 255).astype(np.uint8)).resize((cw, ch), Image.NEAREST)) > 127
            gm = np.asarray(Image.open(sam[k]).convert("L")) > 127
            if sm.sum() > 50:
                ious.append(float((sm & gm).sum() / max(1, (sm | gm).sum())))
            if gm.sum() > 200:
                des.append(float(np.linalg.norm(A.lab(np.asarray(Image.open(clip[k]).convert("RGB")))[gm].mean(axis=0) - ref_lab["Door"])))
        res["door"] = {"iou_vs_stage": round(float(np.mean(ious)), 3) if ious else None, "iou_min": round(float(np.min(ious)), 3) if ious else None,
                       "dE_vs_reference": round(float(np.median(des)), 1) if des else None, "clip": s.get("door_clip")}
        # P3 · the mug in Mara's layer: SAM 3 "white mug" per frame, its centre against her right wrist (SDPose), every 4th frame
        p3 = sorted((OUT / "runs" / "P3" / "fig_m" / "chain").glob("*.png"))
        A.encode(p3, OUT / "p3_layer.mp4", 16, crf=12)
        h, _, _ = x.e.run(sam_text_graph(ros, x.e.upload(OUT / "p3_layer.mp4"), "white mug", "e28/sam_mug"), timeout=1800)
        mug = A.download(x.e, h, "99", OUT / "mug_sam")
        kp = json.loads((E23C / "stage" / "fig_m" / "keypoints.json").read_text(encoding="utf-8"))
        seen, dist, mde = 0, [], []
        frames_checked = list(range(0, 161, 4))
        own = B.kept_mattes(OUT / "runs" / "P3", "fig_m", 36, json.loads(json.dumps(s["P3"]["layer"])))   # only her own mug (not a ghost's)
        for i in frames_checked:
            m = (np.asarray(Image.open(mug[i]).convert("L")) > 127) & B.dilate(own[i] > 0.5, 12)
            hp, _, _ = x.e.run(sdpose_graph(x.e.upload(p3[i])))
            people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
            near = np.array(kp[i], float)
            q = None
            for p in people:
                qq = np.array(p["pose_keypoints_2d"], float).reshape(-1, 3)
                if qq[4, 2] > 0.3 and (q is None or np.linalg.norm(qq[1, :2] - near[1, :2]) < np.linalg.norm(q[1, :2] - near[1, :2])):
                    q = qq
            if m.sum() > 30:
                seen += 1
                ys, xs = np.nonzero(m)
                if q is not None:
                    hh = float(np.linalg.norm(q[0, :2] - (q[10, :2] + q[13, :2]) / 2)) or 1.0
                    dist.append(float(np.hypot(xs.mean() - q[4, 0], ys.mean() - q[4, 1])) / hh)
                mde.append(float(np.linalg.norm(A.lab(np.asarray(Image.open(p3[i]).convert("RGB")))[m].mean(axis=0) - ref_lab["Mug"])))
        res["mug_P3"] = {"present": f"{seen} / {len(frames_checked)} frames", "to_hand_of_height_median": round(float(np.median(dist)), 3) if dist else None,
                         "to_hand_90": round(float(np.percentile(dist, 90)), 3) if dist else None, "dE_vs_reference": round(float(np.median(mde)), 1) if mde else None}
    # the cup clips: P1 (the mug's cut-out at Mara's hand in E23c's Move layer, the wrist SDPose found there) | P3 (drawn in her layer)
    det = json.loads((E23E / "detected.json").read_text(encoding="utf-8"))["M0"]["fig_m"]
    mimg, mal = cutout(OUT / "refs" / "mug.png")
    run0 = next(r for r in json.loads((E23C / "state.json").read_text(encoding="utf-8"))["runs"] if r["arm"] == "M0" and r["seed"] == SEED)
    m0 = B.kept_mattes(E23C / "runs" / f"M0_s{SEED}", "fig_m", 36, json.loads(json.dumps(run0["layers"]["fig_m"])))
    p3m = B.kept_mattes(OUT / "runs" / "P3", "fig_m", 36, json.loads(json.dumps(s["P3"]["layer"])))
    cd = OUT / "runs" / "cup"; shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
    for i in range(161):
        q = np.array(det[i], float) if det[i] else None
        left = plate[i].copy()
        a0 = B.soft(m0[i], 1.2) * B.dilate(m0[i] > 0.5, 3)
        left = left * (1 - a0[..., None]) + B.arr(B.frames_of(E23C / "runs" / f"M0_s{SEED}" / "fig_m" / "chain")[i]) * a0[..., None]
        if q is not None and q[4, 2] > 0.3:
            hh = float(np.linalg.norm(q[0, :2] - (q[10, :2] + q[13, :2]) / 2))
            left = paste(left, mimg, mal, float(q[4, 0]), float(q[4, 1] + 0.055 * hh), 0.065 * hh)   # a 10 cm mug, its foot just under the wrist
        right = plate[i].copy()
        a3 = B.soft(p3m[i], 1.2) * B.dilate(p3m[i] > 0.5, 3)
        right = right * (1 - a3[..., None]) + B.arr(B.frames_of(OUT / "runs" / "P3" / "fig_m" / "chain")[i]) * a3[..., None]
        both = np.concatenate([np.asarray(A.label(Image.fromarray(np.clip(left, 0, 255).astype(np.uint8)), "P1: the mug's cut-out at her hand")),
                               np.asarray(A.label(Image.fromarray(np.clip(right, 0, 255).astype(np.uint8)), "P3: the mug drawn in her layer"))], axis=1)
        Image.fromarray(both).save(cd / f"{i:04d}.png")
    A.encode(B.frames_of(cd), OUT / "cup.mp4", 16, crf=14)
    # the door: the clip beside Stage's depth guide
    dd = OUT / "runs" / "door"; shutil.rmtree(dd, ignore_errors=True); dd.mkdir(parents=True)
    import av
    depth = [f.to_ndarray(format="rgb24") for f in av.open(str(OUT / "door_depth.mp4")).decode(video=0)]
    for k, p in enumerate(clip):
        c_ = Image.open(p).convert("RGB").resize((B.W, B.H), Image.LANCZOS)
        d_ = Image.fromarray(depth[min(k, len(depth) - 1)]).resize((B.W, B.H), Image.LANCZOS)
        Image.fromarray(np.concatenate([np.asarray(A.label(c_, "P2: the clip (LTX-2.3, depth-guided)")), np.asarray(A.label(d_, "Stage's depth guide"))], axis=1)).save(dd / f"{k:04d}.png")
    A.encode(B.frames_of(dd), OUT / "door.mp4", 24, crf=14)
    s["scores"] = res
    s["scored_at"] = time.strftime("%Y-%m-%d %H:%M")
    save_state(s)
    log(f"scores: {json.dumps(res)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["refs", "mattes", "stage", "cup", "score"])
    a = ap.parse_args()
    if a.step == "mattes":
        subject_mattes(); return 0
    return {"refs": refs, "stage": stage, "cup": cup, "score": score}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
