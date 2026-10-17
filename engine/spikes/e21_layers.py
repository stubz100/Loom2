"""E21 — two characters in one animated shot by layers (journal 2026-10-17 18:55; D76, D81, D87 / E19, D93 C).

The shot: a static camera, a two-shot in a simple room blocked like Stage does it (engine/spikes/e21_passes.mjs renders the passes through
the E10 page: Mara left standing, Ines right with her arms crossed, 2 m apart), Mara speaks and gestures, Ines listens and nods; Wan 2.2
I2V Draft (832×480, 81 f at 16 fps, Lightning 2 + 2) for every clip, so the arms differ only in how the two characters reach the frame.

  (a)  composite still → one clip: Stage's clay method with both figures bound (D93 C, Klein 9B, bound ranges — 5/6 right on the rig)
       → one I2V clip with a prompt naming both actions.
  (b)  layers: the plate (clay method on the empty set's pass, no references) → each character into its own copy of the plate (Klein 9B
       Fill-Match — the app's ICM graph, `graphs.build_inpaint` — with the plate + that figure's clay mannequin as image 1, the
       character's hero + first look chained as images 2–3 like `build_t2i` chains references, and the figure's silhouette (+ a shadow
       ellipse under the feet) as the mask) → each copy animated alone (Wan I2V, a one-character prompt) → SAM 3 video tracking of the
       character in its clip (core SAM3_VideoTrack, initial mask = the frame-0 difference to the plate inside the figure's silhouette)
       → merge in numpy: per frame the clip's colour locked to the plate on a ring around the character, alpha = max(SAM mask, the
       difference to the plate inside the dilated SAM mask ∪ silhouette ∪ shadow zone), feathered, composited over the steady plate.
  (b2) (b) + a light video-to-video pass: the merged frames VAE-encoded and re-sampled by Wan 2.2's low-noise expert (+ Lightning low)
       from σ 0.3 (ModelSamplingSD3 shift 1, KSampler denoise 0.3), conditioned on the merged first frame (WanImageToVideo).
  (banim) optional: (b) with the speaker by Wan Animate (E19's graph) on a pose sequence drawn from the Stage keypoints (stand → point
       gestures), the listener's I2V layer as in (b).

Everything runs through a private orchestrator (scratch state, a scratch copy of the D93-C project); the graphs the app has no route for
(references on inpaint, SAM 3 video tracking, v2v, Animate on a hand-drawn pose sequence) are posted raw to the engine that orchestrator
supervises, while it is idle. `run` makes everything (resumable — every step skips what is on disk); `score` measures and writes
results.jsonl, report tables, sheets and MP4s under engine/spikes/out/e21/.

  orchestrator/.venv/Scripts/python.exe engine/spikes/e21_layers.py run [--seeds 3] [--anim]
  orchestrator/.venv/Scripts/python.exe engine/spikes/e21_layers.py score
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import threading
import time
import urllib.request
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from m1_acceptance import Orch, port_busy  # noqa: E402
from e12_angles import Engine  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e21"
PASSES = OUT / "passes"
STATE = OUT / "state.json"
MODELS = Path("F:/loom2-models")
SRC = Path("F:/loom2-projects/d93c-stage-20261017-144418")
W0, H0 = 1280, 720                      # Stage's Draft render (the D93 C rig's size)
W, H, FRAMES, FPS = 832, 480, 81, 16    # Wan 2.2 I2V Draft
AFRAMES = 77                            # Wan Animate: one window
SEED0 = 20261017
ENGINE_PORT = 8188

SCENE = ("a quiet whitewashed room with bare plaster walls and a worn wooden floor, soft daylight from a window on the left, a small wooden "
         "crate and a low wooden table, natural colours, cinematic film still, 35 mm")
MARA_D = "a young woman with a black bob and round glasses in a grey wool coat"
INES_D = "a woman with long curly red hair in a yellow jacket"
STILL_TEXT = f"Mara is talking and gesturing; Ines listens with her arms crossed. {SCENE}"
PLATE_TEXT = f"The room is empty, there are no people in it. {SCENE}"
P_A = (f"Static camera, a two-shot in a quiet room. On the left, {MARA_D} talks to the woman on the right and gestures with her hands as she "
       f"speaks. On the right, {INES_D} listens with her arms crossed and nods slowly. Both stay where they stand; the camera does not move.")
P_L = (f"Static camera, a quiet room. {MARA_D[0].upper() + MARA_D[1:]} talks to someone off-screen to the right and gestures with her hands as "
       f"she speaks. She stays where she stands; the camera does not move.")
P_R = (f"Static camera, a quiet room. {INES_D[0].upper() + INES_D[1:]} listens to someone off-screen to the left with her arms crossed and "
       f"nods slowly. She stays where she stands; the camera does not move.")
P_V2V = P_A
CHARS = {"L": {"name": "Mara", "desc": MARA_D, "pose": "standing, her arms relaxed at her sides", "prompt": P_L, "pass": "left"},
         "R": {"name": "Ines", "desc": INES_D, "pose": "standing with her arms crossed", "prompt": P_R, "pass": "right"}}


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- small image maths (numpy, no OpenCV in the venvs)
def boxsum(a: np.ndarray, r: int) -> np.ndarray:
    """Sum over a (2r+1)² box, edges clamped (integral image)."""
    p = np.pad(a.astype(np.float64), r + 1, mode="edge") if a.ndim == 2 else None
    c = p.cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s[: a.shape[0], : a.shape[1]]


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    return boxsum(m.astype(np.float32), r) > 0.5 if r > 0 else m.astype(bool)


def erode(m: np.ndarray, r: int) -> np.ndarray:
    return boxsum(m.astype(np.float32), r) > (2 * r + 1) ** 2 - 0.5 if r > 0 else m.astype(bool)


def blur(a: np.ndarray, r: int) -> np.ndarray:
    """≈ Gaussian: three box passes."""
    if r <= 0:
        return a.astype(np.float32)
    out = a.astype(np.float32)
    k = (2 * r + 1) ** 2
    for _ in range(3):
        out = (boxsum(out, r) / k).astype(np.float32)
    return out


def fit_cover(im: Image.Image, w: int = W, h: int = H, resample=Image.LANCZOS) -> Image.Image:
    """ComfyUI's ImageScale(crop=center): crop the source to the target aspect, then scale — the I2V graphs' own transform."""
    sw, sh = im.size
    old, new = sw / sh, w / h
    if old > new:
        cw = round(sw * new / old); x = (sw - cw) // 2
        im = im.crop((x, 0, x + cw, sh))
    elif old < new:
        ch = round(sh * old / new); y = (sh - ch) // 2
        im = im.crop((0, y, sw, y + ch))
    return im.resize((w, h), resample)


def fit_points(pts: np.ndarray, src=(W0, H0), w: int = W, h: int = H) -> np.ndarray:
    sw, sh = src
    old, new = sw / sh, w / h
    p = np.array(pts, dtype=float).copy()
    if old > new:
        cw = round(sw * new / old); x = (sw - cw) // 2
        p[..., 0] = (p[..., 0] - x) * w / cw; p[..., 1] = p[..., 1] * h / sh
    else:
        ch = round(sh * old / new); y = (sh - ch) // 2
        p[..., 0] = p[..., 0] * w / sw; p[..., 1] = (p[..., 1] - y) * h / ch
    return p


def arr(p: Path | Image.Image) -> np.ndarray:
    im = p if isinstance(p, Image.Image) else Image.open(p)
    return np.asarray(im.convert("RGB")).astype(np.float32)


def lum(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def save_mask(m: np.ndarray, p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "L").convert("RGB").save(p)
    return p


def load_mask(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L")).astype(np.float32) / 255.0


def frames_of(d: Path) -> list[Path]:
    return sorted(d.glob("*.png"))


def encode_mp4(frames: list[np.ndarray] | list[Path], path: Path, fps: int = FPS, crf: int = 23) -> None:
    first = frames[0] if isinstance(frames[0], np.ndarray) else arr(frames[0])
    h, w = first.shape[:2]
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt, s.time_base = w, h, "yuv420p", Fraction(1, fps)
        s.options = {"crf": str(crf), "preset": "veryfast", "g": str(fps)}
        for i, f in enumerate(frames):
            a = f if isinstance(f, np.ndarray) else arr(f)
            vf = av.VideoFrame.from_ndarray(np.clip(a, 0, 255).astype(np.uint8), format="rgb24")
            vf.pts = i
            for pk in s.encode(vf):
                out.mux(pk)
        for pk in s.encode():
            out.mux(pk)


# ---------------------------------------------------------------- passes → silhouettes, copy masks, the speaker's pose sequence
def silhouettes() -> dict[str, np.ndarray]:
    plate = arr(PASSES / "plate_clay.png")
    out = {}
    for k, c in CHARS.items():
        d = np.abs(arr(PASSES / f"{c['pass']}_clay.png") - plate).max(axis=2)
        out[k] = erode(dilate(d > 4, 1), 1)
    return out


def feet(sil: np.ndarray) -> tuple[int, int, int, int]:
    """(x0, x1, y_bottom, x_centre) of a silhouette's lowest 6 % — the feet."""
    ys, xs = np.nonzero(sil)
    yb = int(ys.max())
    band = ys > yb - 0.06 * (ys.max() - ys.min())
    return int(xs[band].min()), int(xs[band].max()), yb, int(xs[band].mean())


def shadow_zone(sil: np.ndarray, grow: float = 1.0) -> np.ndarray:
    """An ellipse on the floor under the feet: 1.6× the stance wide, ±(0.035 × frame height) tall — where a contact shadow falls."""
    hh, ww = sil.shape
    x0, x1, yb, xc = feet(sil)
    rx = max(12.0, 0.8 * (x1 - x0) + 0.02 * ww) * grow
    ry = 0.035 * hh * grow
    yy, xx = np.mgrid[0:hh, 0:ww]
    return (((xx - xc) / rx) ** 2 + ((yy - (yb - 0.3 * ry)) / ry) ** 2) <= 1.0


def copy_mask(sil: np.ndarray) -> np.ndarray:
    m = dilate(sil, 24) | shadow_zone(sil, 1.2)
    return np.clip(blur(m.astype(np.float32), 3) * 1.15, 0, 1)


COCO_LIMBS = [(1, 2), (1, 5), (2, 3), (3, 4), (5, 6), (6, 7), (1, 8), (8, 9), (9, 10), (1, 11), (11, 12), (12, 13), (1, 0), (0, 14), (14, 16), (0, 15), (15, 17)]
COCO_COLOURS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
                (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]


def draw_pose(kp: np.ndarray, w: int = W, h: int = H, width: float = 3.0, dot: float = 3.0) -> Image.Image:
    """OpenPose COCO-18 as e10Stage.drawPose draws it (limbs as 60 % ellipses, joints as dots, on black)."""
    base = Image.new("RGB", (w, h), (0, 0, 0))
    for k, (a, b) in enumerate(COCO_LIMBS):
        if kp[a][2] <= 0 or kp[b][2] <= 0:
            continue
        x1, y1, x2, y2 = kp[a][0], kp[a][1], kp[b][0], kp[b][1]
        L, ang = np.hypot(x2 - x1, y2 - y1) / 2, np.arctan2(y2 - y1, x2 - x1)
        t = np.linspace(0, 2 * np.pi, 36)
        ex, ey = L * np.cos(t), width * np.sin(t)
        poly = [((x1 + x2) / 2 + ex[i] * np.cos(ang) - ey[i] * np.sin(ang), (y1 + y2) / 2 + ex[i] * np.sin(ang) + ey[i] * np.cos(ang)) for i in range(len(t))]
        layer = Image.new("RGB", (w, h), (0, 0, 0)); mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(layer).polygon(poly, fill=COCO_COLOURS[k]); ImageDraw.Draw(mask).polygon(poly, fill=153)
        base.paste(layer, (0, 0), mask)
    d = ImageDraw.Draw(base)
    for k, (x, y, v) in enumerate(kp):
        if v > 0:
            d.ellipse((x - dot, y - dot, x + dot, y + dot), fill=COCO_COLOURS[k])
    return base


def speaker_pose_sequence(dest: Path, n: int = AFRAMES) -> Path:
    """The speaker's gestures from two Stage keypoint sets of figure 1 (stand, point): the right arm (COCO 2–4) eased towards `point` in
    two beats (45 %, 65 %), a small head bob while talking — the pose pass a Stage pose animation would render, drawn in clip pixels."""
    kp = json.loads((PASSES / "keypoints.json").read_text(encoding="utf-8"))["scenes"]
    stand, point = np.array(kp["left"][0], dtype=float), np.array(kp["left_point"][0], dtype=float)
    stand[:, :2] = fit_points(stand[:, :2]); point[:, :2] = fit_points(point[:, :2])
    dest.mkdir(parents=True, exist_ok=True)

    def bump(f: float, a: float, b: float) -> float:
        if f <= a or f >= b:
            return 0.0
        x = (f - a) / (b - a)
        return float(np.sin(np.pi * x) ** 2)

    frames = []
    for f in range(n):
        amt = 0.45 * bump(f, 6, 36) + 0.65 * bump(f, 40, 74)
        k = stand.copy()
        k[2:5, :2] = stand[2:5, :2] + amt * (point[2:5, :2] - stand[2:5, :2])
        k[2:5, 2] = np.minimum(stand[2:5, 2], point[2:5, 2])
        bob = 1.2 * np.sin(f / n * 2 * np.pi * 5)
        for j in (0, 14, 15, 16, 17):
            k[j, 1] += bob
        im = draw_pose(k)
        im.save(dest / f"{f:04d}.png")
        frames.append(np.asarray(im).astype(np.float32))
    mp4 = dest.parent / "speaker_pose.mp4"
    encode_mp4(frames, mp4, crf=12)
    return mp4


# ---------------------------------------------------------------- the engine side
class Vram:
    """The engine's VRAM in use (total − free from /system_stats), sampled every 0.5 s; `lap()` returns and resets the peak."""
    def __init__(self, port: int) -> None:
        self.peak, self.port, self.stop = 0.0, port, False
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        while not self.stop:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/system_stats", timeout=2) as r:
                    d = json.loads(r.read())["devices"][0]
                self.peak = max(self.peak, (d["vram_total"] - d["vram_free"]) / 2**30)
            except Exception:
                pass
            time.sleep(0.5)

    def lap(self) -> float:
        p, self.peak = self.peak, 0.0
        return round(p, 2)


def roster():
    from loom2.roster import Roster
    return Roster(MODELS, []).scan()


def copy_graph(ros, seed: int, image_name: str, mask_name: str, ref_names: list[str], prompt: str, prefix: str) -> dict:
    """The app's Fill-Match graph (Klein 9B ICM, `build_inpaint`) with the character's references chained after image 1 as `build_t2i`
    chains them — loom2's inpaint takes no references today."""
    from loom2.engine.graphs import build_inpaint
    from loom2.recipes import Inpaint
    c = build_inpaint(Inpaint(model_id="klein-9b", mode="fill_match", prompt_text=prompt, seeds=[seed]), ros, seed, prefix, image_name, mask_name, W0, H0)
    g = c.graph
    cond: list = ["8", 0]
    nid = 40
    for name in ref_names:
        g[str(nid)] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g[str(nid + 1)] = {"class_type": "VAEEncode", "inputs": {"pixels": [str(nid), 0], "vae": ["3", 0]}}
        g[str(nid + 2)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": cond, "latent": [str(nid + 1), 0]}}
        cond = [str(nid + 2), 0]
        nid += 3
    g["9"]["inputs"]["positive"] = cond
    return g


def sam_track_graph(ros, video_name: str, mask_name: str, prefix: str) -> dict:
    _, ckpt = ros.require("sam3")
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "3": {"class_type": "GetVideoComponents", "inputs": {"video": ["2", 0]}},
        "4": {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}},
        "5": {"class_type": "SAM3_VideoTrack", "inputs": {"images": ["3", 0], "model": ["1", 0], "initial_mask": ["4", 0], "detection_threshold": 0.5,
                                                          "max_objects": 1, "detect_interval": 1}},
        "6": {"class_type": "SAM3_TrackToMask", "inputs": {"track_data": ["5", 0], "object_indices": ""}},
        "7": {"class_type": "MaskToImage", "inputs": {"mask": ["6", 0]}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }


def sam_box_graph(ros, video_name: str, box: list[int], prefix: str) -> dict:
    """The fallback for SAM3_VideoTrack (which fails on loom2's sam3.pt in v0.39.0: the non-multiplex tracker returns a tensor where the node
    expects a dict): SAM3_Detect on every frame of the clip with one fixed box around the figure's area — AI Select's box path (C32)."""
    _, ckpt = ros.require("sam3")
    x0, y0, x1, y1 = box
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "3": {"class_type": "GetVideoComponents", "inputs": {"video": ["2", 0]}},
        "4": {"class_type": "CreateBoundingBoxes", "inputs": {"bboxes": json.dumps([{"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}]), "width": W, "height": H,
                                                              "editor_state": {}}},
        "5": {"class_type": "SAM3_Detect", "inputs": {"model": ["1", 0], "image": ["3", 0], "bboxes": ["4", 1], "threshold": 0.4, "refine_iterations": 2,
                                                      "individual_masks": False}},
        "7": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }


def v2v_graph(ros, video_name: str, start_name: str, seed: int, prefix: str, denoise: float = 0.3, shift: float = 1.0) -> dict:
    """Wan 2.2's low-noise expert + Lightning low over the VAE-encoded merged clip from σ = denoise (shift 1), conditioned on its first frame."""
    from loom2.models import registry
    spec = registry.get("wan22-i2v-high-fp8")
    _, low = ros.require(spec.roles.extra["low_expert"])
    _, ll = ros.require(spec.roles.extra["lightning_low"])
    _, te = ros.require(spec.roles.te.default)
    _, vae = ros.require(spec.roles.vae)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": low, "weight_dtype": "default"}},
        "1l": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": ll, "strength_model": 1.0}},
        "1s": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1l", 0], "shift": shift}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": P_V2V, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": spec.video.negative, "clip": ["2", 0]}},
        "100": {"class_type": "LoadImage", "inputs": {"image": start_name}},
        "7": {"class_type": "WanImageToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": W, "height": H, "length": FRAMES,
                                                         "batch_size": 1, "start_image": ["100", 0]}},
        "20": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "21": {"class_type": "GetVideoComponents", "inputs": {"video": ["20", 0]}},
        "22": {"class_type": "VAEEncode", "inputs": {"pixels": ["21", 0], "vae": ["3", 0]}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["1s", 0], "seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                   "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["22", 0], "denoise": denoise}},
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": prefix}},
    }


def download_all(e: Engine, h: dict, node: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, o in enumerate(h["outputs"][node]["images"]):
        r = e.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        p = dest / f"{i:04d}.png"
        p.write_bytes(r.content)
        out.append(p)
    return out


# ---------------------------------------------------------------- the merge
def colour_lock(clip: np.ndarray, plate: np.ndarray, ring: np.ndarray) -> tuple[np.ndarray, list[float]]:
    g = [float(plate[..., c][ring].mean() / max(1e-3, clip[..., c][ring].mean())) for c in range(3)]
    return clip * np.array(g, dtype=np.float32), g


def layer_alpha(clip: np.ndarray, plate: np.ndarray, sam: np.ndarray, sil: np.ndarray, shadow: np.ndarray) -> tuple[np.ndarray, dict]:
    """alpha = max(SAM's soft mask, the difference to the plate inside the dilated SAM mask ∪ silhouette ∪ shadow zone), feathered."""
    region = dilate(sam > 0.5, 10) | dilate(sil, 10) | shadow
    ring = dilate(region, 28) & ~region
    clip_l, gain = colour_lock(clip, plate, ring)
    d = blur(np.abs(clip_l - plate).max(axis=2), 1)
    da = np.clip((d - 8.0) / 14.0, 0, 1) * region
    a = np.maximum(np.clip(sam, 0, 1), da)
    a = np.clip(blur(a, 2), 0, 1) * dilate(region, 3)
    return a.astype(np.float32), {"gain": [round(x, 3) for x in gain], "clip": clip_l}


def merge_clip(layers: list[dict], plate: np.ndarray, dest: Path, n: int) -> dict:
    """layers: [{frames, sam, sil, shadow}] far → near. Writes the merged frames and per-frame alphas (npz)."""
    dest.mkdir(parents=True, exist_ok=True)
    alphas = np.zeros((len(layers), n, H, W), dtype=np.float16)
    gains = [[] for _ in layers]
    for t in range(n):
        out = plate.copy()
        for k, L in enumerate(layers):
            clip = arr(L["frames"][t])
            sam = load_mask(L["sam"][t]) if L.get("sam") else np.zeros((H, W), np.float32)
            a, info = layer_alpha(clip, plate, sam, L["sil"], L["shadow"])
            out = out * (1 - a[..., None]) + info["clip"] * a[..., None]
            alphas[k, t] = a
            gains[k].append(info["gain"])
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dest / f"{t:04d}.png")
    np.savez_compressed(dest.parent / f"{dest.name}_alpha.npz", alpha=alphas)
    g = np.array(gains)          # layers × frames × 3
    return {"gain_min": [round(float(x), 3) for x in g.min(axis=(1, 2))], "gain_max": [round(float(x), 3) for x in g.max(axis=(1, 2))]}


# ---------------------------------------------------------------- run
def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")


def record(s: dict, step: str, wall: float, vram: float, **extra) -> None:
    s.setdefault("steps", {})[step] = {"wall_s": round(wall, 1), "vram_peak_gb": vram, **extra}
    save_state(s)
    log(f"  {step}: {wall:.1f} s, peak {vram} GB {json.dumps(extra)[:200] if extra else ''}")


def run(a: argparse.Namespace) -> int:
    s = load_state()
    if port_busy(ENGINE_PORT) and not a.adopt:
        print("engine port busy — stop the running engine first (or --adopt)"); return 2
    seeds = [SEED0 + i for i in range(a.seeds)]
    if "project" not in s:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        s["project"] = str(Path(a.projects) / f"e21-layers-{stamp}")
        s["state_dir"] = str(Path(a.projects) / f"_state-e21-layers-{stamp}")
        shutil.copytree(SRC, s["project"])                        # a scratch copy: D93 C's project stays as it was
        save_state(s)
    project = Path(s["project"])
    sils = silhouettes()
    for k, m in sils.items():
        save_mask(m.astype(np.float32), OUT / "masks" / f"sil_{k}.png")
        save_mask(copy_mask(m), OUT / "masks" / f"copymask_{k}.png")
        save_mask(np.asarray(fit_cover(Image.fromarray((m * 255).astype(np.uint8)), resample=Image.BILINEAR)) / 255.0, OUT / "masks" / f"sil832_{k}.png")
    o = Orch(Path(s["state_dir"]), a.port).start()
    vram = Vram(ENGINE_PORT)
    ros = roster()
    try:
        r = o.http.post("/project/open", json={"path": str(project)})
        assert r.status_code == 200, r.text[:200]
        profs = {p["name"]: p for p in o.http.get("/story/profiles").json()["items"]}
        mara, ines = profs["Mara"], profs["Ines"]
        prof = {"L": mara, "R": ines}
        for k, p in prof.items():
            hp = OUT / "heroes" / f"{k}.png"
            if not hp.is_file():
                hp.parent.mkdir(parents=True, exist_ok=True)
                hp.write_bytes(o.http.get(f"/assets/{p['versions'][0]['hero_asset_id']}/file").content)
        # ---- the stage and its passes (both figures; the empty set)
        if "stage_id" not in s:
            st = o.http.post("/stages", json={"name": "E21 two-shot"}).json()
            kpd = json.loads((PASSES / "keypoints.json").read_text(encoding="utf-8"))["doc"]
            fl, fr = kpd["scenes"][0]["figures"]
            doc = {**st, "objects": [
                {"id": "fig_left", "kind": "mannequin", "name": "Figure 1", "preset": "adult", "transform": {"pos": fl["pos"], "rot": [0, fl["yaw"], 0], "scale": [1, 1, 1]},
                 "pose": {"preset": "stand", "joints": {}}, "profile_id": mara["id"]},
                {"id": "fig_right", "kind": "mannequin", "name": "Figure 2", "preset": "adult", "transform": {"pos": fr["pos"], "rot": [0, fr["yaw"], 0], "scale": [1, 1, 1]},
                 "pose": {"preset": "arms_crossed", "joints": {}}, "profile_id": ines["id"]}],
                "cameras": [{"id": "cam_1", "name": "Camera 1", "pos": [0, 1.05, 4.3], "target": [0, 0.95, 0], "roll": 0, "focal_mm": 38, "sensor_mm": 36}],
                "active_camera": "cam_1"}
            st = o.http.put(f"/stages/{st['id']}", json=doc).json()
            for variant in ("both", "plate"):
                shas = {}
                for name in ("clay", "depth", "normal", "pose"):
                    data = (PASSES / f"{variant}_{name}.png").read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    o.http.put(f"/blobs/{sha}", content=data)
                    shas[name] = sha
                r = o.http.post(f"/stages/{st['id']}/passes", json={"camera_id": "cam_1", "revision": st["revision"], "size": {"w": W0, "h": H0}, "passes": shas})
                assert r.status_code == 200, r.text[:200]
                st = r.json()
                s[f"passes_{variant}"] = st["passes"][-1]["assets"]
            s["stage_id"] = st["id"]
            save_state(s)
        base = {"kind": "stage_shot", "stage_id": s["stage_id"], "camera_id": "cam_1", "method": "clay", "width": W0, "height": H0}

        def job(recipe: dict, step: str, timeout: float = 3600) -> dict:
            vram.lap()
            j = o.http.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]
            j = o.wait_job(j["id"], {"done", "failed", "cancelled"}, timeout)
            if j["status"] != "done":
                raise RuntimeError(f"{step}: {j['status']} {j.get('error')}")
            record(s, step, float(j.get("wall_s") or 0), vram.lap())
            return j

        def fetch_asset(aid: str, p: Path) -> Path:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(o.http.get(f"/assets/{aid}/file").content)
            return p

        def fetch_clip(cid: str, dest: Path) -> None:
            rec = o.http.get(f"/clips/{cid}").json()
            src = project / rec["master_dir"]
            dest.mkdir(parents=True, exist_ok=True)
            fr = sorted(src.glob("*.png"))
            for i, f in enumerate(fr):
                shutil.copyfile(f, dest / f"{i:04d}.png")

        # ---- (a) stills: the clay method, both figures bound with ranges (D93 C)
        mentions = [{"profile_id": mara["id"], "figure": "fig_left"}, {"profile_id": ines["id"], "figure": "fig_right"}]
        for sd in seeds:
            p = OUT / "stills" / f"a_s{sd}.png"
            if not p.is_file():
                rec = {**base, "passes": s["passes_both"], "prompt_text": STILL_TEXT, "mentions": mentions, "bind_refs": True, "seeds": [sd]}
                if "prompt_a_still" not in s:
                    s["prompt_a_still"] = o.http.post("/recipes/preview", json={"recipe": rec}).json()["params"]["prompt"]
                j = job(rec, f"a_still_s{sd}")
                s.setdefault("assets", {})[f"a_s{sd}"] = j["result"]["asset_ids"][0]
                fetch_asset(j["result"]["asset_ids"][0], p)
        # ---- (b1) the plate: the clay method on the empty set, no references; the first seed without a face
        if "plate" not in s:
            from loom2.tools.facesim import FaceSim
            fs = FaceSim(MODELS)
            for sd in seeds + [SEED0 + 100 + i for i in range(3)]:
                p = OUT / "stills" / f"plate_s{sd}.png"
                if not p.is_file():
                    j = job({**base, "passes": s["passes_plate"], "prompt_text": PLATE_TEXT, "seeds": [sd]}, f"plate_s{sd}")
                    s.setdefault("assets", {})[f"plate_s{sd}"] = j["result"]["asset_ids"][0]
                    fetch_asset(j["result"]["asset_ids"][0], p)
                nf = len(fs.detect(np.asarray(Image.open(p).convert("RGB"))))
                log(f"  plate seed {sd}: {nf} faces")
                if nf == 0:
                    s["plate"] = str(p); s["plate_seed"] = sd
                    shutil.copyfile(p, OUT / "stills" / "plate.png")
                    save_state(s)
                    break
            if "plate" not in s:
                raise RuntimeError("every plate seed drew a person")
        plate0 = Image.open(s["plate"]).convert("RGB")
        if not port_busy(ENGINE_PORT):                            # a resumed run with every app job cached: start the supervised engine
            o.http.post("/engine/start", timeout=300)
            t0 = time.time()
            while not port_busy(ENGINE_PORT) and time.time() - t0 < 300:
                time.sleep(2)
            time.sleep(5)
        e = Engine(f"127.0.0.1:{ENGINE_PORT}")
        # ---- (b2) each character into its own copy of the plate
        pa = np.asarray(plate0).astype(np.float32)
        refs_up: dict[str, list[str]] = {}
        for k, c in CHARS.items():
            gid = prof[k]["versions"][0]["group_id"]
            items = json.loads((project / "groups" / f"{gid}.json").read_text(encoding="utf-8"))["items"]
            names = []
            for it in [x for x in items if x["kind"] == "asset"][:2]:
                rp = fetch_asset(it["id"], OUT / "refs" / f"{k}_{it['id']}.png")
                im = Image.open(rp).convert("RGB"); im.thumbnail((1024, 1024), Image.LANCZOS); im.save(rp)
                names.append(e.upload(rp))
            refs_up[k] = names
            clay = arr(PASSES / f"{c['pass']}_clay.png")
            sil = sils[k]
            src = pa.copy()
            src[sil] = clay[sil]                                  # the mannequin of that figure, pasted on the plate
            sp = OUT / "copies" / f"src_{k}.png"
            sp.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(src.astype(np.uint8)).save(sp)
            img_name, mask_name = e.upload(sp), e.upload(OUT / "masks" / f"copymask_{k}.png")
            prompt = (f"Replace the grey clay mannequin in image 1 with the woman shown in image 2 and image 3: {c['desc']}, {c['pose']}, at exactly "
                      f"the mannequin's position, size and pose. She stands on the floor and casts a soft shadow on it. Keep everything else in image 1 "
                      f"exactly as it is: the room, the light, the camera.")
            s.setdefault("prompts", {})[f"copy_{k}"] = prompt
            for sd in seeds:
                p = OUT / "copies" / f"{k}_s{sd}.png"
                if p.is_file():
                    continue
                g = copy_graph(ros, sd, img_name, mask_name, names, prompt, f"e21/copy_{k}_s{sd}")
                vram.lap()
                h, wall, ex = e.run(g, timeout=1800)
                e.image(h, "99").save(p)
                record(s, f"copy_{k}_s{sd}", wall, vram.lap(), exec_s=round(ex, 1))
        # ---- clips: (a) and each copy, Wan 2.2 I2V Draft through the app
        i2v = {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "frames": FRAMES, "fps": FPS, "width": W, "height": H, "preset": "draft"}
        todo = [(f"a_s{sd}", OUT / "stills" / f"a_s{sd}.png", P_A, sd) for sd in seeds]
        todo += [(f"{k}_s{sd}", OUT / "copies" / f"{k}_s{sd}.png", CHARS[k]["prompt"], sd) for sd in seeds for k in CHARS]
        for name, still, prompt, sd in todo:
            dest = OUT / "clips" / name
            if len(frames_of(dest)) >= FRAMES:
                continue
            aid = s.get("assets", {}).get(name if name.startswith("a_") else f"copy_{name}")
            if not aid:
                aid = o.http.post("/assets/import", json={"paths": [str(still)], "suite": "import"}).json()["items"][0]["id"]
                s.setdefault("assets", {})[f"copy_{name}"] = aid
                save_state(s)
            j = job({**i2v, "start_asset": aid, "prompt_text": prompt, "seeds": [sd]}, f"clip_{name}")
            s.setdefault("clips", {})[name] = j["result"]["clip_id"]
            fetch_clip(j["result"]["clip_id"], dest)
        # ---- (banim) the speaker by Wan Animate on a drawn pose sequence (E19's graph)
        if a.anim:
            from e19_animate import animate_graph
            pose_mp4 = speaker_pose_sequence(OUT / "pose_seq")
            pose_name = e.upload(pose_mp4)
            for sd in seeds[: a.anim_seeds]:
                dest = OUT / "clips" / f"Lanim_s{sd}"
                if len(frames_of(dest)) >= AFRAMES:
                    continue
                refp = OUT / "copies" / f"L_s{sd}_832.png"
                fit_cover(Image.open(OUT / "copies" / f"L_s{sd}.png").convert("RGB")).save(refp)
                g, node = animate_graph(e.upload(refp), pose_name, sd, f"e21/Lanim_s{sd}")
                g["5"]["inputs"]["text"] = P_L
                vram.lap()
                h, wall, ex = e.run(g, timeout=3600)
                download_all(e, h, node, dest)
                record(s, f"clip_Lanim_s{sd}", wall, vram.lap(), exec_s=round(ex, 1))
        # ---- SAM 3 video tracking of each layer clip (initial mask: the frame-0 difference to the plate inside the silhouette)
        plate832 = np.asarray(fit_cover(plate0)).astype(np.float32)
        np.save(OUT / "plate832.npy", plate832)
        Image.fromarray(plate832.astype(np.uint8)).save(OUT / "stills" / "plate_832.png")
        layer_clips = [f"{k}_s{sd}" for sd in seeds for k in CHARS] + ([f"Lanim_s{sd}" for sd in seeds[: a.anim_seeds]] if a.anim else [])
        for name in layer_clips:
            k = name[0]
            dest = OUT / "sam" / name
            fr = frames_of(OUT / "clips" / name)
            if len(frames_of(dest)) >= len(fr):
                continue
            sil = load_mask(OUT / "masks" / f"sil832_{k}.png") > 0.5
            d0 = blur(np.abs(arr(fr[0]) - plate832).max(axis=2), 1)
            init = erode(dilate((d0 > 24) & dilate(sil, 8), 2), 2)
            save_mask(init.astype(np.float32), OUT / "sam" / f"{name}_init.png")
            mp4 = OUT / "sam" / f"{name}_src.mp4"
            encode_mp4(fr, mp4, crf=10)
            if a.sam_track:
                g = sam_track_graph(ros, e.upload(mp4), e.upload(OUT / "sam" / f"{name}_init.png"), f"e21/sam_{name}")
            else:
                ys, xs = np.nonzero(sil)
                wd = xs.max() - xs.min()
                box = [int(max(0, xs.min() - 0.45 * wd - 10)), int(max(0, ys.min() - 25)), int(min(W - 1, xs.max() + 0.45 * wd + 10)), int(min(H - 1, ys.max() + 8))]
                g = sam_box_graph(ros, e.upload(mp4), box, f"e21/sam_{name}")
            vram.lap()
            h, wall, ex = e.run(g, timeout=1800)
            download_all(e, h, "99", dest)
            record(s, f"sam_{name}", wall, vram.lap(), exec_s=round(ex, 1))
        # ---- merges
        for sd in seeds:
            for arm, lname in (("b", f"L_s{sd}"), ("banim", f"Lanim_s{sd}")):
                if arm == "banim" and not (a.anim and sd in seeds[: a.anim_seeds]):
                    continue
                dest = OUT / "merged" / f"{arm}_s{sd}"
                n = min(len(frames_of(OUT / "clips" / lname)), len(frames_of(OUT / "clips" / f"R_s{sd}")))
                if len(frames_of(dest)) >= n:
                    continue
                layers = []
                for nm in (lname, f"R_s{sd}"):
                    k = nm[0]
                    sil = load_mask(OUT / "masks" / f"sil832_{k}.png") > 0.5
                    layers.append({"frames": frames_of(OUT / "clips" / nm), "sam": frames_of(OUT / "sam" / nm), "sil": sil, "shadow": shadow_zone(sil, 1.3)})
                t0 = time.time()
                info = merge_clip(layers, plate832, dest, n)
                record(s, f"merge_{arm}_s{sd}", time.time() - t0, 0.0, **info)
        # ---- (b2) the light v2v pass over each merged clip
        for sd in seeds:
            src = OUT / "merged" / f"b_s{sd}"
            dest = OUT / "merged" / f"b2_s{sd}"
            if len(frames_of(dest)) >= FRAMES:
                continue
            mp4 = OUT / "merged" / f"b_s{sd}_src.mp4"
            encode_mp4(frames_of(src), mp4, crf=10)
            g = v2v_graph(ros, e.upload(mp4), e.upload(frames_of(src)[0]), sd, f"e21/b2_s{sd}", denoise=a.v2v_denoise)
            vram.lap()
            h, wall, ex = e.run(g, timeout=3600)
            download_all(e, h, "99", dest)
            record(s, f"v2v_b2_s{sd}", wall, vram.lap(), exec_s=round(ex, 1), denoise=a.v2v_denoise)
    finally:
        vram.stop = True
        o.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "score"])
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8774)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--anim", action="store_true")
    ap.add_argument("--anim-seeds", type=int, default=2)
    ap.add_argument("--v2v-denoise", type=float, default=0.3)
    ap.add_argument("--adopt", action="store_true")
    ap.add_argument("--sam-track", action="store_true", help="SAM3_VideoTrack (fails on sam3.pt in v0.39.0) instead of per-frame box detection")
    a = ap.parse_args()
    if a.cmd == "run":
        return run(a)
    from e21_score import score
    return score(a)


if __name__ == "__main__":
    raise SystemExit(main())
