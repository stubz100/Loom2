"""Spike E23a (proto01_animate 02 §3): one layer — which frame rate gives seamless W1 joins with the identity held, and how much do they drift?

The shot (≈ 10 s, one figure, a locked-off camera in E22's room): CA0's Mara (`out/ca0/refs/mara_v2.png`, the animation reference made by
CA0's own route: 16:9, full body, A-pose, her sheet's colours bound, plain grey ground) walks an S-shaped floor path — the CC0 starter set's
Walk_Loop applied along the path by the app's own CA1 code (retarget, foot lock, steering), on a Detailed ♀ figure so the pose pass draws
hands and feet (D101) — then turns to the camera and points (keys). Move mode (CN4): the result is Mara on the reference's grey ground; the
plate is E23b's business.

Arms (2 seeds each, the same seeds across arms), every batch one Wan Animate Draft window of 77 frames (4 steps, LightX2V, shift 8, as
CN4's graph), batch N+1 taking batch N's last 5 decoded frames as `continue_motion` with the pose window seeked by `video_frame_offset`
(the engine's own chaining), those 5 re-made frames dropped from N+1 (W1: a plain cut inside continuous motion, no crossfade):

  F16  the pose sequence sampled at 16 fps (161 frames), 3 batches, the chain conformed to 24 fps by RIFE v4.6 (D27's tool)
  F24  the pose sequence at 24 fps as Stage keys it (241 frames), 4 batches
  W3   the worst join of all runs healed: the ± 4 frames around it refined (Klein base 9B, partial denoise) with the start still and the
       animation reference as references, pasted back in the figure's mask (A6's healing patch)

Measured (score): PCK@0.1 against Stage's keypoints (SDPose, every 8th frame); FaceSim against the reference every 8th frame (the drop from
batch 1 to the last batch); at each join E17's seam ratio (the cut's grey difference ÷ the previous batch's median frame-to-frame
difference) and the drift — the mean colour (CIELab ΔE) of the figure's pixels over the 3 frames either side of the join against the same
across every other frame step in the batch (LPIPS is not installed; a colour shift is the drift a join shows); the carried frames' fidelity
(batch N's last 5 against N+1's re-made 5); time and peak VRAM per batch. For the author: compare.mp4 (both arms, both seeds, 24 fps), the
joins as strips (10 frames around each), a contact sheet (one frame a second).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e23a_joins.py guides      # visible Edge, needs Vite on 1420; no engine
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23a_joins.py run         # the arms, one GPU job at a time
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23a_joins.py score       # SDPose on the engine, FaceSim on the CPU, RIFE after
  orchestrator/.venv/Scripts/python.exe engine/spikes/e23a_joins.py heal        # W3 on the worst join
Outputs under engine/spikes/out/e23a/ (git-ignored).
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
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

OUT = ROOT / "engine" / "spikes" / "out" / "e23a"
STATE = OUT / "state.json"
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
REF = ROOT / "engine" / "spikes" / "out" / "ca0" / "refs" / "mara_v2.png"
RIFE = next(iter(sorted((ROOT / "engine" / "tools").glob("rife-ncnn-vulkan-*/rife-ncnn-vulkan.exe"))), None)
W, H = 832, 480                                    # Wan Animate's Draft size (/capabilities.stage.animate)
BATCH, CARRY = 77, 5                               # one window; continue_motion's 5 frames
ARMS = {"F16": {"fps": 16, "frames": 161}, "F24": {"fps": 24, "frames": 241}}   # 10 s of Stage at 24 fps
SEEDS = [20261019, 20261020]
PATH = [[1.3, -1.2], [0.2, -0.6], [-0.9, 0.0], [-1.1, 0.8], [-0.2, 1.3], [0.8, 1.2]]
CAM = {"pos": [0.0, 1.1, 5.0], "target": [0.0, 0.85, 0.3], "focal_mm": 36}
MODEL = "wan22-animate-fp8"
PROMPT = ("A young woman with long red braids, a cream blouse, a blue skirt and a brown leather satchel walks across the room, stops, turns "
          "to face the camera and points with her outstretched arm. Plain light grey studio background, static camera.")
HEAL_PROMPT = ("A young woman with long red braids, a cream blouse, a blue skirt and a brown leather satchel, on a plain light grey studio "
               "background, the same person and clothes as in the reference images.")
ENGINE_PORT, ORCH_PORT, DEV, DBG = 8188, 8786, 1420, 9338
BARS = {"pck": 0.8, "face_drop": 0.05, "seam": 1.5, "vram_gb": 14.5}
HEAL_STRENGTH = 0.35


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=1), encoding="utf-8")


def frames_of(d: Path) -> list[Path]:
    return sorted(d.glob("*.png"))


def encode(frames: list[Path] | list[np.ndarray], path: Path, fps: int, crf: int = 10) -> None:
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=fps)
        first = frames[0]
        w, h = (Image.open(first).size if isinstance(first, Path) else (first.shape[1], first.shape[0]))
        s.width, s.height, s.pix_fmt, s.time_base = w, h, "yuv420p", Fraction(1, fps)
        s.options = {"crf": str(crf), "preset": "veryfast", "g": str(fps)}
        for i, f in enumerate(frames):
            a = np.asarray(Image.open(f).convert("RGB")) if isinstance(f, Path) else f
            vf = av.VideoFrame.from_ndarray(np.ascontiguousarray(a), format="rgb24")
            vf.pts = i
            for p in s.encode(vf):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


# ---- 1 · the pose sequences, by the app's own code in a visible Edge ---------------------------------------------------------------
GUIDE_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const A = await import('/src/suites/stage/anim.ts')
  const M = await import('/src/suites/stage/motion/motionStore.ts')
  const lib = await import('/src/suites/stage/motion/library.ts')
  const st = S.st
  st().select('fig_a'); st().setFrame(0)
  await M.useMotion.getState().refresh()
  const file = M.useMotion.getState().files.find((f) => f.name === 'AnimationLibrary_Godot_Standard')
  if (!file) return { error: 'the starter library is not listed' }
  const clip = (await lib.clipsOf(file)).find((c) => c.name === 'Walk_Loop')
  M.useMotion.getState().pick(clip); M.useMotion.getState().set({ lock: true, alongPath: true, blend: 6 })
  await M.useMotion.getState().apply()
  let doc = st().current
  const walk = (doc.keyframes.objects.fig_a ?? []).slice()
  const end = walk[walk.length - 1].frame
  // stop, turn to the camera (yaw 0 faces +z) with the feet together, then point
  st().setFrame(end); st().keyObject('fig_a')
  const o = st().sampledDoc().objects.find((x) => x.id === 'fig_a')
  const y = o.transform.rot[1], to = y - ((((y % 360) + 540) % 360) - 180)
  st().setFrame(end + 16); st().setTransform('fig_a', { pos: o.transform.pos, rot: [0, to, 0], scale: o.transform.scale }); st().applyPose('fig_a', 'stand'); st().keyObject('fig_a')
  st().setFrame(end + 28); st().applyPose('fig_a', 'point'); st().keyObject('fig_a')
  st().setRange(0, 240); st().setFrame(0)
  await new Promise((r) => setTimeout(r, 1500))
  doc = st().current
  const R = st().sequenceRenderer
  if (!R) return { error: 'no sequence renderer' }
  const cam = doc.cameras[0]
  const b64 = (blob) => new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(blob) })
  window.__e23 = {}
  for (const [k, fps, n] of %ARMS%) {
    const seq = Array.from({ length: n }, (_, i) => { const d = A.sampleDoc(doc, (i * 24) / fps); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
    const out = await R(seq, %W%, %H%, 'pose', A.sampleDoc(doc, 0))
    window.__e23[k] = { png: await Promise.all(out.blobs.map(b64)), keypoints: out.keypoints }
  }
  return { walkEnd: end, turnEnd: end + 16, pointAt: end + 28, keys: (doc.keyframes.objects.fig_a ?? []).length }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def api(method: str, path: str, body=None, token: str = "e23a"):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{ORCH_PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": token})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def guides(a: argparse.Namespace) -> int:
    from edit_headed_check import CDP, EDGE
    from loom2.config import AppState
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e23a-"))
    AppState(tmp / "state").update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8199}})
    env = {**os.environ, "LOOM2_TOKEN": "e23a", "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(ORCH_PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=(OUT / "guides_orchestrator.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT, text=True)
    edge = None
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "E23a", "size_cap_gb": 20})
        st = api("POST", "/stages", {"name": "E23a"})
        cam = st["cameras"][0]
        cam.update(pos=CAM["pos"], target=CAM["target"], focal_mm=CAM["focal_mm"])
        fig = {"id": "fig_a", "kind": "mannequin", "name": "Mara", "preset": "adult", "transform": {"pos": [PATH[0][0], 0, PATH[0][1]], "rot": [0, 0, 0], "scale": [1, 1, 1]},
               "pose": {"preset": "stand", "joints": {}, "extra": {}}, "colour_id": 1, "detail": "female", "path": PATH}
        set_ = {"id": "set_a", "kind": "set", "name": "Floor", "preset": "empty", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "colour_id": 2}
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": [set_, fig], "cameras": [cam], "size": {**st["size"], "fps": 24}})
        url = f"http://127.0.0.1:{DEV}/?token=e23a&port={ORCH_PORT}&suite=stage"
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
        cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 2", timeout=30, settle=8.0)
        js = (GUIDE_JS.replace("%ARMS%", json.dumps([[k, v["fps"], v["frames"]] for k, v in ARMS.items()]))
              .replace("%W%", str(W)).replace("%H%", str(H)))
        r = cdp.eval(js, timeout=900) or {}
        log(f"in page: {r}")
        if not r or r.get("error"):
            print(r, cdp.page_errors()[:3]); return 1
        s = load_state()
        s["shot"] = r
        for k, v in ARMS.items():
            d = OUT / "guides" / k
            shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
            n = v["frames"]
            for i in range(0, n, 30):
                chunk = cdp.eval(f"window.__e23[{json.dumps(k)}].png.slice({i}, {i + 30})", timeout=120)
                for j, b in enumerate(chunk):
                    (d / f"{i + j:04d}.png").write_bytes(base64.b64decode(b))
            kp = cdp.eval(f"window.__e23[{json.dumps(k)}].keypoints", timeout=120)
            (OUT / "guides" / f"{k}_keypoints.json").write_text(json.dumps(kp), encoding="utf-8")
            encode(frames_of(d), OUT / "guides" / f"pose_{k}.mp4", v["fps"])
            # the framing: every visible keypoint inside the frame, the figure's height in pixels
            pts = [np.array([p for p in fig_ if p[2] > 0], float) for frame in kp for fig_ in frame if any(p[2] > 0 for p in fig_)]
            inside = all(((q[:, 0] >= 0) & (q[:, 0] < W) & (q[:, 1] >= 0) & (q[:, 1] < H)).all() for q in pts)
            heights = [float(np.ptp(q[:, 1])) for q in pts]
            s.setdefault("framing", {})[k] = {"frames": len(kp), "all_inside": bool(inside), "figure_px_min": round(min(heights)), "figure_px_max": round(max(heights))}
            log(f"{k}: {n} frames, framing {s['framing'][k]}")
        shot = cdp.call("Page.captureScreenshot", format="png")
        (OUT / "guides" / "viewport.png").write_bytes(base64.b64decode(shot["data"]))
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
    return 0


# ---- 2 · the arms on the engine ----------------------------------------------------------------------------------------------------
def roster():
    from loom2.roster import Roster
    return Roster(MODELS, [], "full").scan()


def pad_reference(src: Path, dest: Path) -> Path:
    """The app's CN4 padding (pipeline.pad_reference): fitted inside W × H on its own mean edge colour, never cropped."""
    im = Image.open(src).convert("RGB")
    im.thumbnail((W, H), Image.LANCZOS)
    a = np.asarray(im)
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]).mean(axis=0).astype(int)
    canvas = Image.new("RGB", (W, H), tuple(int(x) for x in edge))
    canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    canvas.save(dest)
    return dest


def batch_graph(ros, pose_name: str, ref_name: str, seed: int, offset: int, carry: list[str], prefix: str) -> dict:
    """CN4's Wan Animate graph (engine/graphs.py, wan_animate) with the engine's chaining inputs: continue_motion (the previous batch's last
    5 frames) and video_frame_offset (where the previous batch's window ended)."""
    from loom2.models import registry
    spec = registry.SPECS[MODEL]
    roles = spec.roles
    _, unet = ros.require(spec.id)
    _, lora = ros.require(roles.extra["lightning"])
    _, cv = ros.require(roles.extra["clip_vision"])
    _, te = ros.require(roles.te.default)
    _, vae = ros.require(roles.vae)
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "1l": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": 1.0}},
        "1s": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1l", 0], "shift": 8.0}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "4": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": cv}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": spec.video.negative, "clip": ["2", 0]}},
        "100": {"class_type": "LoadImage", "inputs": {"image": ref_name}},
        "8": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["4", 0], "image": ["100", 0], "crop": "center"}},
        "52": {"class_type": "LoadVideo", "inputs": {"file": pose_name}},
        "53": {"class_type": "GetVideoComponents", "inputs": {"video": ["52", 0]}},
        "11": {"class_type": "WanAnimateToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": W, "height": H, "length": BATCH,
                                                            "batch_size": 1, "clip_vision_output": ["8", 0], "reference_image": ["100", 0], "pose_video": ["53", 0],
                                                            "continue_motion_max_frames": CARRY, "video_frame_offset": offset}},
        "12": {"class_type": "KSampler", "inputs": {"model": ["1s", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["11", 0], "negative": ["11", 1], "latent_image": ["11", 2], "denoise": 1.0}},
        "13": {"class_type": "TrimVideoLatent", "inputs": {"samples": ["12", 0], "trim_amount": ["11", 3]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}},
    }
    if carry:
        for i, n in enumerate(carry):
            g[f"c{i}"] = {"class_type": "LoadImage", "inputs": {"image": n}}
        link = ["c0", 0]
        for i in range(1, len(carry)):
            g[f"cb{i}"] = {"class_type": "ImageBatch", "inputs": {"image1": link, "image2": [f"c{i}", 0]}}
            link = [f"cb{i}", 0]
        g["11"]["inputs"]["continue_motion"] = link
    return g


def download(e, h: dict, node: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, o in enumerate(h["outputs"][node]["images"]):
        r = e.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        p = dest / f"{i:04d}.png"
        p.write_bytes(r.content)
        out.append(p)
    return out


class Session:
    """A private orchestrator (D98's 5 GB headroom from its settings) that starts the engine; graphs go to the engine directly."""
    def __enter__(self):
        from m1_acceptance import Orch, port_busy
        from e12_angles import Engine
        from e21_layers import Vram
        from loom2.config import AppState
        if port_busy(ENGINE_PORT):
            raise SystemExit("the engine port is busy — one GPU job at a time: stop the running engine first")
        state = Path(tempfile.mkdtemp(prefix="loom2-e23a-run-")) / "state"
        AppState(state).update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full", "engine": {"port": ENGINE_PORT}})
        self.o = Orch(state, ORCH_PORT).start()
        r = self.o.http.post("/engine/start", timeout=600)
        log(f"engine: {r.status_code} {r.text[:160]}")
        self.e = Engine(f"127.0.0.1:{ENGINE_PORT}")
        self.vram = Vram(ENGINE_PORT)
        return self

    def __exit__(self, *exc):
        self.vram.stop = True
        try:
            self.o.http.post("/engine/stop", timeout=120)
            self.o.http.post("/shutdown", timeout=30)
        except Exception:
            pass
        time.sleep(2)
        if self.o.proc and self.o.proc.poll() is None:
            self.o.proc.kill()


def run_arm(x: Session, ros, arm: str, seed: int, ref_name: str, pose_name: str, s: dict) -> dict:
    n = ARMS[arm]["frames"]
    batches = 1 + -(-(n - BATCH) // (BATCH - CARRY))
    dest = OUT / "runs" / f"{arm}_s{seed}"
    rows, chain = [], []
    carry: list[str] = []
    for k in range(batches):
        offset = 0 if k == 0 else BATCH + (BATCH - CARRY) * (k - 1)
        g = batch_graph(ros, pose_name, ref_name, seed, offset, carry, f"e23a/{arm}_s{seed}_b{k + 1}")
        x.vram.lap()
        h, wall, exec_s = x.e.run(g, timeout=3600)
        if h.get("status", {}).get("status_str") == "error":
            raise RuntimeError(f"{arm} seed {seed} batch {k + 1}: {json.dumps(h['status'].get('messages', []))[-600:]}")
        fr = download(x.e, h, "15", dest / f"b{k + 1}")
        peak = x.vram.lap()
        new = fr if k == 0 else fr[CARRY:]
        chain_start = len(chain)
        chain += new
        rows.append({"batch": k + 1, "frames": len(fr), "new": len(new), "chain_start": chain_start, "offset": offset, "exec_s": round(exec_s, 1), "peak_vram_gb": peak})
        log(f"  {arm} s{seed} batch {k + 1}/{batches}: {len(fr)} frames ({len(new)} new) in {exec_s:.0f} s, peak {peak} GB")
        carry = [x.e.upload(p) for p in fr[-CARRY:]]
    cd = dest / "chain"
    shutil.rmtree(cd, ignore_errors=True); cd.mkdir(parents=True)
    for i, p in enumerate(chain[:n]):
        shutil.copy2(p, cd / f"{i:04d}.png")
    encode(frames_of(cd), dest / "chain.mp4", ARMS[arm]["fps"], crf=14)
    return {"arm": arm, "seed": seed, "batches": rows, "joins": [r["chain_start"] for r in rows[1:]], "frames": min(n, len(chain)),
            "stamp": time.strftime("%Y-%m-%d %H:%M")}


def run(a: argparse.Namespace) -> int:
    s = load_state()
    if "framing" not in s:
        print("draw the guides first (guides)"); return 2
    ros = roster()
    ref = pad_reference(REF, OUT / "ref_padded.png")
    done = {(r["arm"], r["seed"]) for r in s.get("runs", [])}
    order = [(arm, seed) for i, seed in enumerate(SEEDS) for arm in (("F16", "F24") if i % 2 == 0 else ("F24", "F16"))]
    with Session() as x:
        ref_name = x.e.upload(ref)
        poses = {arm: x.e.upload(OUT / "guides" / f"pose_{arm}.mp4") for arm in ARMS}
        for arm, seed in order:
            if (arm, seed) in done:
                continue
            log(f"{arm} seed {seed}")
            row = run_arm(x, ros, arm, seed, ref_name, poses[arm], s)
            s.setdefault("runs", []).append(row)
            save_state(s)
    return 0


# ---- 3 · the scores -----------------------------------------------------------------------------------------------------------------
def grey(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L").resize((W // 4, H // 4), Image.BILINEAR), dtype=np.float32)


def lab(a: np.ndarray) -> np.ndarray:
    """sRGB (uint8) → CIELab (D65)."""
    c = a.astype(np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def figure_mask(p: Path, kp: list | None) -> np.ndarray:
    """The figure on the reference's plain grey ground: pixels ΔE > 12 from the frame border's median colour, inside the pose's box
    (grown by 15 %) when the keypoints are known."""
    a = np.asarray(Image.open(p).convert("RGB"))
    L = lab(a)
    border = np.concatenate([L[0], L[-1], L[:, 0], L[:, -1]])
    m = np.linalg.norm(L - np.median(border, axis=0), axis=-1) > 12
    if kp:
        q = np.array([pt for fig in kp for pt in fig if pt[2] > 0], float)
        if len(q):
            x0, y0 = q[:, :2].min(0); x1, y1 = q[:, :2].max(0)
            gx, gy = 0.15 * (x1 - x0) + 20, 0.15 * (y1 - y0) + 30
            box = np.zeros_like(m)
            box[max(0, int(y0 - gy)):int(y1 + gy), max(0, int(x0 - gx)):int(x1 + gx)] = True
            m &= box
    return m


def mean_lab(p: Path, m: np.ndarray) -> np.ndarray | None:
    if m.sum() < 200:
        return None
    return lab(np.asarray(Image.open(p).convert("RGB")))[m].mean(axis=0)


def faces(fs, p: Path):
    a = np.asarray(Image.open(p).convert("RGB").resize((W * 2, H * 2), Image.BICUBIC))
    f = fs.detect(a)
    return fs.embed(a, max(f, key=lambda x: x.area).kps) if f else None


def score_run(r: dict, fs, eng, hero, kps: list) -> dict:
    from e10_stage import pck, sdpose_graph
    arm, seed = r["arm"], r["seed"]
    chain = frames_of(OUT / "runs" / f"{arm}_s{seed}" / "chain")
    n = len(chain)
    starts = [b["chain_start"] for b in r["batches"]] + [n]
    batch_of = lambda i: max(k for k in range(len(starts) - 1) if starts[k] <= i)   # noqa: E731
    # pose fidelity and identity, every 8th frame
    hit = tot = 0
    sims: dict[int, list[float]] = {}
    for i in range(0, n, 8):
        hp, _, _ = eng.run(sdpose_graph(eng.upload(chain[i])))
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        h_, t_ = pck(kps[i], people); hit += h_; tot += t_
        emb = faces(fs, chain[i])
        if emb is not None:
            sims.setdefault(batch_of(i), []).append(float(fs.similarity(hero, emb)))
    face = {f"b{k + 1}": round(float(np.mean(v)), 3) for k, v in sorted(sims.items())}
    first, last = sims.get(0), sims.get(len(starts) - 2)
    drop = round(float(np.mean(first) - np.mean(last)), 3) if first and last else None
    # joins
    gs = [grey(p) for p in chain]
    steps = np.array([float(np.mean(np.abs(gs[i] - gs[i + 1]))) for i in range(n - 1)])
    cols = []
    for i, p in enumerate(chain):
        cols.append(mean_lab(p, figure_mask(p, kps[i])))
    joins = []
    for k, j in enumerate(r["joins"]):
        if j >= n:
            continue
        prev = steps[starts[k]:j - 1]
        within = float(np.median(prev)) if len(prev) else 1e-6
        seam = float(steps[j - 1])
        before = [c for c in cols[max(0, j - 3):j] if c is not None]
        after = [c for c in cols[j:j + 3] if c is not None]
        drift = float(np.linalg.norm(np.mean(before, 0) - np.mean(after, 0))) if before and after else None
        # the same 3-vs-3 colour difference at every other position in the previous batch: the drift's baseline
        base = []
        for q in range(starts[k] + 3, j - 3):
            b_, a_ = [c for c in cols[q - 3:q] if c is not None], [c for c in cols[q:q + 3] if c is not None]
            if b_ and a_:
                base.append(float(np.linalg.norm(np.mean(b_, 0) - np.mean(a_, 0))))
        bmed = float(np.median(base)) if base else None
        # how faithfully batch k+1 re-made the carried frames
        bd = OUT / "runs" / f"{arm}_s{seed}"
        made = frames_of(bd / f"b{k + 2}")[:CARRY]
        orig = frames_of(bd / f"b{k + 1}")[-CARRY:]
        carry_diff = float(np.mean([np.mean(np.abs(grey(x) - grey(y))) for x, y in zip(orig, made)]))
        joins.append({"frame": j, "t_s": round(j / ARMS[arm]["fps"], 2), "seam": round(seam, 2), "within": round(within, 2), "ratio": round(seam / max(1e-6, within), 2),
                      "drift_dE": None if drift is None else round(drift, 2), "drift_base_dE": None if bmed is None else round(bmed, 2),
                      "drift_ratio": None if drift is None or not bmed else round(drift / bmed, 2), "carry_diff": round(carry_diff, 2), "within_step": round(within, 2)})
    out = {"arm": arm, "seed": seed, "frames": n, "pck": round(hit / tot, 3) if tot else None, "facesim": face, "face_drop": drop, "joins": joins,
           "exec_s": [b["exec_s"] for b in r["batches"]], "peak_vram_gb": max(b["peak_vram_gb"] for b in r["batches"])}
    worst = max((jn["ratio"] for jn in joins), default=0.0)
    out["bars"] = {"pck": out["pck"] is not None and out["pck"] >= BARS["pck"], "face_drop": drop is not None and drop <= BARS["face_drop"],
                   "seam": worst <= BARS["seam"], "vram": out["peak_vram_gb"] <= BARS["vram_gb"]}
    return out


def rife(arm_dir: Path, n_out: int) -> list[Path]:
    """D27's conform: rife-ncnn-vulkan v4.6 over the whole chain, to n_out frames (the GPU's only job: run after the engine stops)."""
    src, dst = arm_dir / "chain", arm_dir / "rife24"
    shutil.rmtree(dst, ignore_errors=True); dst.mkdir(parents=True)
    t0 = time.time()
    subprocess.run([str(RIFE), "-i", str(src), "-o", str(dst), "-n", str(n_out), "-m", str(RIFE.parent / "rife-v4.6"), "-f", "%04d.png", "-g", "0"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log(f"  RIFE {src.parent.name}: {n_out} frames in {time.time() - t0:.1f} s")
    return frames_of(dst)


def label(im: Image.Image, text: str) -> Image.Image:
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 8 + 7 * len(text), 16], fill=(0, 0, 0))
    d.text((4, 2), text, fill=(255, 255, 255))
    return im


def outputs(runs: list[dict], scores: list[dict]) -> None:
    """compare.mp4 (2 × 2: F16 after RIFE | F24, a row per seed, 24 fps), join strips, a contact sheet (one frame a second)."""
    seqs = {}
    for r in runs:
        d = OUT / "runs" / f"{r['arm']}_s{r['seed']}"
        seqs[(r["arm"], r["seed"])] = frames_of(d / "rife24") if r["arm"] == "F16" else frames_of(d / "chain")
    n = min(len(v) for v in seqs.values())
    tw, th = W // 2, H // 2
    grid = []
    for i in range(n):
        im = Image.new("RGB", (tw * 2, th * len(SEEDS)), (0, 0, 0))
        for row, seed in enumerate(SEEDS):
            for col, arm in enumerate(("F16", "F24")):
                p = seqs.get((arm, seed))
                if p:
                    t = Image.open(p[i]).convert("RGB").resize((tw, th), Image.LANCZOS)
                    im.paste(label(t, f"{arm}{' →24 RIFE' if arm == 'F16' else ''} · seed {seed} · {i / 24:.2f} s"), (col * tw, row * th))
        grid.append(np.asarray(im))
    encode(grid, OUT / "compare.mp4", 24, crf=16)
    # strips: the 10 frames around each join (5 before, 5 after), at native rate
    cw, ch = 166, 96
    rows = [(s_, j) for s_ in scores for j in s_["joins"]]
    sheet = Image.new("RGB", (8 + 10 * (cw + 2), 8 + len(rows) * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for ri, (s_, j) in enumerate(rows):
        chain = frames_of(OUT / "runs" / f"{s_['arm']}_s{s_['seed']}" / "chain")
        y = 8 + ri * (ch + 18)
        dr.text((8, y), f"{s_['arm']} seed {s_['seed']} · join at frame {j['frame']} ({j['t_s']} s) · seam ratio {j['ratio']} · drift ΔE {j['drift_dE']} (base {j['drift_base_dE']}) · | marks the cut", fill=(230, 230, 230))
        for c, i in enumerate(range(j["frame"] - 5, j["frame"] + 5)):
            if 0 <= i < len(chain):
                t = Image.open(chain[i]).convert("RGB").resize((cw, ch), Image.LANCZOS)
                sheet.paste(t, (8 + c * (cw + 2), y + 14))
        x = 8 + 5 * (cw + 2) - 2
        dr.line([x, y + 12, x, y + 14 + ch], fill=(255, 60, 60), width=2)
    sheet.save(OUT / "joins.jpg", quality=90)
    # contact sheet: a frame a second, a row per run
    cols = 11
    cs = Image.new("RGB", (8 + cols * (cw + 2), 8 + len(scores) * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(cs)
    for ri, s_ in enumerate(scores):
        chain = frames_of(OUT / "runs" / f"{s_['arm']}_s{s_['seed']}" / "chain")
        fps = ARMS[s_["arm"]]["fps"]
        y = 8 + ri * (ch + 18)
        dr.text((8, y), f"{s_['arm']} seed {s_['seed']} · PCK {s_['pck']} · FaceSim {s_['facesim']} · drop {s_['face_drop']}", fill=(230, 230, 230))
        for c in range(cols):
            i = min(len(chain) - 1, c * fps)
            cs.paste(Image.open(chain[i]).convert("RGB").resize((cw, ch), Image.LANCZOS), (8 + c * (cw + 2), y + 14))
    cs.save(OUT / "sheet.jpg", quality=90)


def score(a: argparse.Namespace) -> int:
    from loom2.tools.facesim import FaceSim
    s = load_state()
    runs = s.get("runs", [])
    if not runs:
        print("nothing to score (run)"); return 2
    fs = FaceSim(MODELS)
    a_ = np.asarray(Image.open(REF).convert("RGB"))
    f = fs.detect(a_)
    hero = fs.embed(a_, max(f, key=lambda x: x.area).kps)
    kps = {arm: json.loads((OUT / "guides" / f"{arm}_keypoints.json").read_text(encoding="utf-8")) for arm in ARMS}
    scores = []
    with Session() as x:
        for r in runs:
            sc = score_run(r, fs, x.e, hero, kps[r["arm"]])
            scores.append(sc)
            log(f"{sc['arm']} s{sc['seed']}: PCK {sc['pck']}, FaceSim {sc['facesim']} (drop {sc['face_drop']}), joins "
                + ", ".join(f"{j['frame']}: ratio {j['ratio']} drift {j['drift_dE']}/{j['drift_base_dE']} carry {j['carry_diff']}" for j in sc["joins"])
                + f", {sc['exec_s']} s, peak {sc['peak_vram_gb']} GB")
    # RIFE after the engine has stopped (one GPU job at a time)
    for r in runs:
        if r["arm"] == "F16":
            d = OUT / "runs" / f"F16_s{r['seed']}"
            fr = rife(d, ARMS["F24"]["frames"])
            encode(fr, d / "rife24.mp4", 24, crf=14)
            # the seams after RIFE: the conformed join sits between frames j·1.5 − 1 and j·1.5 (+ 1)
            gs = [grey(p) for p in fr]
            st = [float(np.mean(np.abs(gs[i] - gs[i + 1]))) for i in range(len(gs) - 1)]
            sc = next(x_ for x_ in scores if x_["arm"] == "F16" and x_["seed"] == r["seed"])
            for j in sc["joins"]:
                c = int(round(j["frame"] * 1.5))
                win = st[max(0, c - 40):c - 3]
                local = max(st[c - 2:c + 2])
                j["rife24"] = {"seam": round(local, 2), "within": round(float(np.median(win)), 2), "ratio": round(local / max(1e-6, float(np.median(win))), 2)}
    outputs(runs, scores)
    s["scores"] = scores
    s["scored_at"] = time.strftime("%Y-%m-%d %H:%M")
    save_state(s)
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f_:
        f_.write(json.dumps({"at": s["scored_at"], "scores": scores}) + "\n")
    for arm in ARMS:
        rs = [x_ for x_ in scores if x_["arm"] == arm]
        if rs:
            ratios = [j["ratio"] for x_ in rs for j in x_["joins"]]
            log(f"{arm}: PCK {np.mean([x_['pck'] for x_ in rs]):.3f}, face drop {[x_['face_drop'] for x_ in rs]}, seam ratios {ratios} (worst {max(ratios)}), "
                f"drift {[j['drift_ratio'] for x_ in rs for j in x_['joins']]}, batch s {[x_['exec_s'] for x_ in rs]}, peak {max(x_['peak_vram_gb'] for x_ in rs)} GB")
    return 0


# ---- 4 · W3: a healing patch on the worst join --------------------------------------------------------------------------------------
def heal_graph(ros, frame_name: str, refs: list[str], seed: int, prefix: str) -> dict:
    """The app's Refine (build_i2i: Klein base 9B, partial denoise) with the references chained as ReferenceLatent after the prompt, as
    E21's copy graph chains them."""
    from loom2.engine.graphs import build_i2i
    from loom2.recipes import I2I
    c = build_i2i(I2I(prompt_text=HEAL_PROMPT, strength=HEAL_STRENGTH, seeds=[seed]), ros, seed, prefix, frame_name, W, H)
    g = c.graph
    cond = g["9"]["inputs"]["positive"]
    nid = 40
    for name in refs:
        g[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[str(nid + 1)] = {"class_type": "VAEEncode", "inputs": {"pixels": [str(nid), 0], "vae": g["8"]["inputs"]["vae"]}}
        g[str(nid + 2)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": cond, "latent": [str(nid + 1), 0]}}
        cond = [str(nid + 2), 0]
        nid += 3
    g["9"]["inputs"]["positive"] = cond
    return g


def feathered(m: np.ndarray, grow: int = 8, feather: int = 6) -> np.ndarray:
    im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow * 2 + 1)).filter(ImageFilter.GaussianBlur(feather))
    return np.asarray(im, dtype=np.float32)[..., None] / 255.0


def heal(a: argparse.Namespace) -> int:
    from loom2.tools.facesim import FaceSim
    s = load_state()
    scores = s.get("scores")
    if not scores:
        print("score first"); return 2
    cands = [(j["ratio"], sc, j) for sc in scores for j in sc["joins"]]
    _, sc, j = max(cands, key=lambda t: (t[0], t[2].get("drift_ratio") or 0))
    arm, seed, jf = sc["arm"], sc["seed"], j["frame"]
    d = OUT / "runs" / f"{arm}_s{seed}"
    chain = frames_of(d / "chain")
    kps = json.loads((OUT / "guides" / f"{arm}_keypoints.json").read_text(encoding="utf-8"))
    idx = list(range(max(0, jf - 4), min(len(chain), jf + 5)))
    log(f"W3 on {arm} seed {seed}, the join at frame {jf} (ratio {j['ratio']}, drift ΔE {j['drift_dE']}): frames {idx[0]}–{idx[-1]}")
    hd = d / "healed"
    shutil.rmtree(hd, ignore_errors=True); hd.mkdir(parents=True)
    for p in chain:
        shutil.copy2(p, hd / p.name)
    ros = roster()
    times = []
    with Session() as x:
        refs = [x.e.upload(chain[0]), x.e.upload(pad_reference(REF, OUT / "ref_padded.png"))]   # the start still, the animation reference
        for i in idx:
            g = heal_graph(ros, x.e.upload(chain[i]), refs, SEEDS[0] + i, f"e23a/heal_{arm}_s{seed}_{i:04d}")
            h, wall, exec_s = x.e.run(g, timeout=1800)
            times.append(round(exec_s, 1))
            out = download(x.e, h, "99", OUT / "heal_raw" / f"{i:04d}")[0]
            src = np.asarray(Image.open(chain[i]).convert("RGB"), dtype=np.float32)
            ref_ = np.asarray(Image.open(out).convert("RGB").resize((W, H), Image.LANCZOS), dtype=np.float32)
            m = feathered(figure_mask(chain[i], kps[i]))
            Image.fromarray(np.clip(src * (1 - m) + ref_ * m, 0, 255).astype(np.uint8)).save(hd / chain[i].name)
            log(f"  frame {i}: {exec_s:.0f} s")
        peak = x.vram.lap()
    healed = frames_of(hd)
    fs = FaceSim(MODELS)
    a_ = np.asarray(Image.open(REF).convert("RGB"))
    hero = fs.embed(a_, max(fs.detect(a_), key=lambda q: q.area).kps)

    def around(fr: list[Path]) -> dict:
        gs = [grey(p) for p in fr[idx[0] - 1:idx[-1] + 2]]
        st = [float(np.mean(np.abs(gs[k] - gs[k + 1]))) for k in range(len(gs) - 1)]
        within = j["within"]
        cols = [mean_lab(p, figure_mask(p, kps[i])) for i, p in zip(range(idx[0] - 1, idx[-1] + 2), fr[idx[0] - 1:idx[-1] + 2])]
        bef = [c for c in cols[jf - (idx[0] - 1) - 3:jf - (idx[0] - 1)] if c is not None]
        aft = [c for c in cols[jf - (idx[0] - 1):jf - (idx[0] - 1) + 3] if c is not None]
        sims = [fs.similarity(hero, e_) for e_ in (faces(fs, p) for p in fr[idx[0]:idx[-1] + 1]) if e_ is not None]
        return {"seam_ratio": round(st[jf - idx[0]] / max(1e-6, within), 2), "worst_step_ratio": round(max(st) / max(1e-6, within), 2),
                "drift_dE": round(float(np.linalg.norm(np.mean(bef, 0) - np.mean(aft, 0))), 2) if bef and aft else None,
                "facesim": round(float(np.mean(sims)), 3) if sims else None}
    res = {"arm": arm, "seed": seed, "join": jf, "frames": [idx[0], idx[-1]], "strength": HEAL_STRENGTH, "before": around(chain), "after": around(healed),
           "exec_s": times, "peak_vram_gb": peak, "stamp": time.strftime("%Y-%m-%d %H:%M")}
    s["heal"] = res
    save_state(s)
    log(f"W3: before {res['before']}, after {res['after']}, {np.mean(times):.0f} s a frame, peak {peak} GB")
    # the strip: before over after, the 14 frames around the join
    cw, ch = 166, 96
    rng = range(jf - 7, jf + 7)
    sheet = Image.new("RGB", (8 + len(rng) * (cw + 2), 8 + 2 * (ch + 18)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for ri, (name, fr) in enumerate((("W1 as made", chain), ("W3 healed (frames ±4)", healed))):
        y = 8 + ri * (ch + 18)
        dr.text((8, y), f"{arm} seed {seed} · {name} · {res['before' if ri == 0 else 'after']}", fill=(230, 230, 230))
        for c, i in enumerate(rng):
            if 0 <= i < len(fr):
                sheet.paste(Image.open(fr[i]).convert("RGB").resize((cw, ch), Image.LANCZOS), (8 + c * (cw + 2), y + 14))
    sheet.save(OUT / "heal.jpg", quality=90)
    encode(healed, d / "healed.mp4", ARMS[arm]["fps"], crf=14)
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f_:
        f_.write(json.dumps({"heal": res}) + "\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["guides", "run", "score", "heal"])
    a = ap.parse_args()
    return {"guides": guides, "run": run, "score": score, "heal": heal}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
