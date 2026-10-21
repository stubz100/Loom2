"""Spike E24 — post-processing, the first slice (proto01_animate 01 step 8, 02 §3): which pass makes the performance the final without
flicker, while staying faithful and keeping the shadows and light? Run on the PS5 rig's final (engine/spikes/out/ps5, "Rig": E23b's Move
arm as the product made it — Mara's performed layer `fig_m/frames` with her matte, and the final assembled afresh by `final_assembly`).

Arms of this slice — the one mechanism both stages share, measured first (the others of 02 §3 wait on its numbers):
  A0   the layer as performed                                                            — the baseline of stage A
  A2a  Wan 2.2 I2V's low-noise expert over the layer as a video, denoise 0.10              (the undistilled expert, 20-step schedule → the
  A2b  the same at denoise 0.20                                                             last 2 / 4 steps; CFG 3.5, shift 8; the first
                                                                                            frame as WanImageToVideo's anchor; the clip's
                                                                                            own latent in place of the empty one)
  C0   the assembled final as is                                                          — the baseline of stage C
  C1a  the low expert over the flattened shot at 0.10
  C1b  the same at 0.20

Measured per arm against its baseline (numpy only, on every frame or every 8th): flicker — the mean absolute change between consecutive
frames in the still background (outside the figure, from the matte grown 24 px) and inside the figure; faithfulness — SSIM to the input
outside the face box (bar ≥ 0.90); detail — the variance of the Laplacian inside the figure (higher is sharper); identity — FaceSim of the
face against Mara's reference every 8th frame (bar ≥ 0.45, the minimum); the shadows (stage C) — the luminance of the shadow pass's
regions against the input; exec seconds. Outputs under engine/spikes/out/e24/: frames per arm, mp4s, a sheet of frame 40 crops,
results.jsonl, log.txt. The pinned engine standalone on 8188 (D97: nothing else on the GPU), stopped after.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e24_post.py [--arms a0,a2a,a2b,c0,c1a,c1b] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e18_lipsync as E18  # noqa: E402  (engine_listening, download_frames, largest_face, MODELS, ENGINE)
import e23a_joins as A  # noqa: E402  (encode, frames_of)
from e12_angles import Engine  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e24"
RESULTS = OUT / "results.jsonl"
PROJECT = REPO / "engine" / "spikes" / "out" / "ps5" / "project"
FID = "fin_0f41f551"
FIN = PROJECT / "finals" / FID
FIG = FIN / "fig_m"
W, H, FPS = 832, 480, 16
SEED = 20261021
LOW, TE, VAE = "wan22-i2v-low-fp8", "umt5-xxl-fp8", "wan21-vae"
NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，"
       "画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")
PROMPT_A = "a woman in a grey wool coat with a black bob and round glasses walks and turns on a plain grey ground, natural motion, sharp, detailed, steady camera, soft light"
PROMPT_C = "two women in a plain room, one in a grey wool coat with a black bob and round glasses walking and turning, one in a yellow jacket with long curly red hair sitting on a stool, a wooden stool, soft shadows on the floor, natural motion, sharp, detailed, steady camera"
BARS = {"ssim": 0.90, "facesim": 0.45}
ARMS = {"a2a": ("a", 0.10), "a2b": ("a", 0.20), "c1a": ("c", 0.10), "c1b": ("c", 0.20)}


def log(msg: str) -> None:
    print(msg, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}\n")


# ---- the graph: the low expert over a video latent ---------------------------------------------------------------------------------
def v2v_graph(ros: Roster, video_name: str, first_name: str, prompt: str, denoise: float, seed: int, prefix: str, frames: int) -> tuple[dict, str]:
    """The I2V low-noise expert refining a clip: WanImageToVideo's conditioning from the clip's first frame (the model's concat channels
    stay what it was trained on), the clip itself VAE-encoded as the latent, KSampler at `denoise` on the 20-step schedule."""
    _, low = ros.require(LOW)
    _, te = ros.require(TE)
    _, vae = ros.require(VAE)
    g: dict = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": low, "weight_dtype": "default"}},
        "1s": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": te, "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["2", 0]}},
        "20": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "21": {"class_type": "GetVideoComponents", "inputs": {"video": ["20", 0]}},
        "22": {"class_type": "VAEEncode", "inputs": {"pixels": ["21", 0], "vae": ["3", 0]}},
        "100": {"class_type": "LoadImage", "inputs": {"image": first_name}},
        "7": {"class_type": "WanImageToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "width": W, "height": H, "length": frames, "batch_size": 1,
                                                          "start_image": ["100", 0]}},
        "12": {"class_type": "KSampler", "inputs": {"model": ["1s", 0], "seed": seed, "steps": 20, "cfg": 3.5, "sampler_name": "euler", "scheduler": "simple",
                                                    "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["22", 0], "denoise": denoise}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": prefix}},
    }
    return g, "14"


# ---- the measures ---------------------------------------------------------------------------------------------------------------
def arr(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)


def luma(a: np.ndarray) -> np.ndarray:
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    out = m.copy()
    for _ in range(r):
        p = np.pad(out, 1, constant_values=False)
        out = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return out


def gauss1d(sigma: float = 1.5, radius: int = 5) -> np.ndarray:
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-x * x / (2 * sigma * sigma))
    return k / k.sum()


def blur(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Separable convolution with edge padding (numpy only)."""
    r = len(k) // 2
    p = np.pad(a, ((r, r), (r, r)), mode="edge")
    tmp = np.zeros_like(a)
    for i, kv in enumerate(k):
        tmp += kv * p[r:r + a.shape[0], i:i + a.shape[1]]
    p = np.pad(tmp, ((r, r), (r, r)), mode="edge")
    out = np.zeros_like(a)
    for i, kv in enumerate(k):
        out += kv * p[i:i + a.shape[0], r:r + a.shape[1]]
    return out


def ssim(x: np.ndarray, y: np.ndarray, mask: np.ndarray | None = None) -> float:
    """SSIM on luma (Wang et al., gaussian window σ 1.5), averaged where `mask` is true."""
    k = gauss1d()
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = blur(x, k), blur(y, k)
    sxx, syy, sxy = blur(x * x, k) - mx * mx, blur(y * y, k) - my * my, blur(x * y, k) - mx * my
    s = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    return float(s[mask].mean() if mask is not None and mask.any() else s.mean())


def lap_var(x: np.ndarray, mask: np.ndarray) -> float:
    p = np.pad(x, 1, mode="edge")
    lap = p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] - 4 * p[1:-1, 1:-1]
    return float(lap[mask].var()) if mask.any() else 0.0


def face_mask(fs: FaceSim, a: np.ndarray) -> np.ndarray:
    m = np.zeros(a.shape[:2], bool)
    for f in fs.detect(a.astype(np.uint8)):
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        m[max(0, y1 - 10):y2 + 10, max(0, x1 - 10):x2 + 10] = True
    return m


def face_in(fs: FaceSim, a: np.ndarray, matte: np.ndarray) -> np.ndarray | None:
    """The embedding of the face whose box centre lies on the figure's matte (in the composite the largest face may be the other
    character's), detected at 2× like E23b (the faces are small at 832×480)."""
    up = np.asarray(Image.fromarray(a.astype(np.uint8)).resize((a.shape[1] * 2, a.shape[0] * 2), Image.BICUBIC))
    best = None
    for f in fs.detect(up):
        cx, cy = int((f.bbox[0] + f.bbox[2]) / 4), int((f.bbox[1] + f.bbox[3]) / 4)
        if 0 <= cy < matte.shape[0] and 0 <= cx < matte.shape[1] and dilate(matte, 8)[cy, cx]:
            if best is None or f.area > best.area:
                best = f
    return fs.embed(up, best.kps) if best is not None else None


def measure(name: str, frames: list[Path], base: list[Path], mattes: list[np.ndarray], fs: FaceSim, hero: np.ndarray | None,
            shadow: list[np.ndarray] | None, exec_s: float | None) -> dict:
    n = min(len(frames), len(base), len(mattes))
    fl_bg, fl_fig, ss, det, sims, sh = [], [], [], [], [], []
    prev = None
    for i in range(n):
        a = arr(frames[i])
        la = luma(a)
        fig = dilate(mattes[i], 24)
        bg = ~fig
        if prev is not None:
            d = np.abs(la - prev)
            fl_bg.append(float(d[bg].mean()) if bg.any() else 0.0)
            fl_fig.append(float(d[fig].mean()) if fig.any() else 0.0)
        prev = la
        if i % 8 == 0:
            b = arr(base[i])
            lb = luma(b)
            nf = ~face_mask(fs, b)
            ss.append(ssim(la, lb, nf))
            det.append(lap_var(la, mattes[i]))
            emb = face_in(fs, a, mattes[i])
            sims.append(round(float(fs.similarity(hero, emb)), 3) if hero is not None and emb is not None else None)
            if shadow is not None:
                reg = shadow[i] > 0.5
                if reg.any():
                    sh.append(float(la[reg].mean() / max(1e-6, lb[reg].mean())))
    vals = [s for s in sims if s is not None]
    row = {"arm": name, "frames": n, "exec_s": None if exec_s is None else round(exec_s, 1),
           "flicker_bg": round(float(np.mean(fl_bg)), 3) if fl_bg else None, "flicker_fig": round(float(np.mean(fl_fig)), 3) if fl_fig else None,
           "ssim": round(float(np.mean(ss)), 4) if ss else None, "detail": round(float(np.mean(det)), 1) if det else None,
           "facesim": sims, "facesim_min": min(vals) if vals else None, "shadow_ratio": round(float(np.mean(sh)), 3) if sh else None,
           "stamp": time.strftime("%Y-%m-%d %H:%M")}
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    log(f"  {name}: {n} f, exec {row['exec_s']} s, flicker bg {row['flicker_bg']} fig {row['flicker_fig']}, SSIM {row['ssim']}, detail {row['detail']}, "
        f"FaceSim min {row['facesim_min']}, shadows {row['shadow_ratio']}")
    return row


def assembled(out_dir: Path) -> tuple[list[Path], list[np.ndarray]]:
    """The final assembled afresh by the product's code (CPU, deterministic): its frames and the shadow strength per frame."""
    from loom2 import final_assembly
    from loom2.finals import FinalStore
    from loom2.workspace import Workspace
    store = FinalStore(Workspace(PROJECT))
    f = store.get(FID)
    comp = out_dir / "comp"
    final_assembly.assemble_frames(store, f, out_dir, None, comp)
    frames = A.frames_of(out_dir)
    shadow = [np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0 for p in A.frames_of(comp / "shadow")]
    return frames, shadow


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="a0,a2a,a2b,c0,c1a,c1b")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    if any(x in ARMS for x in arms) and E18.engine_listening():
        print("an engine is already listening on 8188 — stop it first (D97)"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    layer = A.frames_of(FIG / "frames")
    mattes = [np.asarray(Image.open(p).convert("L")) >= 128 for p in A.frames_of(FIG / "matte")]
    n = min(len(layer), len(mattes))
    fs = FaceSim(E18.MODELS)
    hero = E18.largest_face(fs, FIG / "reference.png")
    log(f"E24 start · arms {arms} · {n} frames · seed {a.seed}")
    comp_frames, shadow = (assembled(OUT / "assembled") if any(x.startswith("c") for x in arms) else ([], []))
    # the matte in the composite is where Mara's layer lands: her contact offset moves it (D107)
    fin = json.load((FIN / "final.json").open(encoding="utf-8"))
    off = (fin.get("assembly") or {}).get("offsets_px", {}).get("fig_m", [0, 0])
    comp_mattes = [np.roll(np.roll(m, int(round(off[1])), axis=0), int(round(off[0])), axis=1) for m in mattes]
    sheet_cells: list[tuple[str, Path]] = []
    if "a0" in arms:
        measure("a0", layer[:n], layer[:n], mattes, fs, hero, None, None)
        sheet_cells.append(("a0", layer[40]))
    if "c0" in arms and comp_frames:
        measure("c0", comp_frames[:n], comp_frames[:n], comp_mattes, fs, hero, shadow, None)
        sheet_cells.append(("c0", comp_frames[40]))
    gpu = [x for x in arms if x in ARMS]
    if gpu:
        eng_log = (OUT / "engine.log").open("a", encoding="utf-8")
        eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
        try:
            t0 = time.time()
            while time.time() - t0 < 240 and not E18.engine_listening():
                time.sleep(1.0)
            if not E18.engine_listening():
                log("the engine did not come up"); return 1
            e = Engine(E18.ENGINE)
            ros = Roster(E18.MODELS, [], "full").scan()
            names: dict[str, tuple[str, str]] = {}
            for stage, src in (("a", layer), ("c", comp_frames)):
                if src and any(ARMS[x][0] == stage for x in gpu):
                    mp4 = OUT / f"in_{stage}.mp4"
                    A.encode(src[:n], mp4, FPS)
                    names[stage] = (e.upload(mp4), e.upload(src[0]))
            for arm in gpu:
                stage, dn = ARMS[arm]
                if stage not in names:
                    continue
                vid, first = names[stage]
                g, node = v2v_graph(ros, vid, first, PROMPT_A if stage == "a" else PROMPT_C, dn, a.seed, f"e24/{arm}", n)
                try:
                    h, wall, exec_s = e.run(g, timeout=3600)
                except Exception as ex:  # noqa: BLE001
                    log(f"  FAILED {arm}: {type(ex).__name__}: {str(ex)[:400]}")
                    with RESULTS.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"arm": arm, "error": f"{type(ex).__name__}: {str(ex)[:400]}", "stamp": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
                    continue
                frames = E18.download_frames(e, h, node, OUT / arm)
                src = layer if stage == "a" else comp_frames
                measure(arm, frames, src[:n], mattes if stage == "a" else comp_mattes, fs, hero, shadow if stage == "c" else None, exec_s)
                A.encode(frames, OUT / f"{arm}.mp4", FPS)
                if len(frames) > 40:
                    sheet_cells.append((arm, frames[40]))
        finally:
            try:
                subprocess.run(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-stop.ps1")], capture_output=True, timeout=60)
            except Exception:
                pass
            try:
                eng.wait(timeout=30)
            except Exception:
                eng.kill()
            eng_log.close()
    if sheet_cells:                                                      # frame 40, Mara's region at 1:1 with a label, one cell per arm
        cell_w, cell_h = 360, 300
        im = Image.new("RGB", (cell_w * len(sheet_cells), cell_h + 18), (24, 24, 24))
        d = ImageDraw.Draw(im)
        for i, (name, p) in enumerate(sheet_cells):
            src = Image.open(p).convert("RGB")
            m = mattes[40]
            ys, xs = np.nonzero(m)
            cx, cy = (int(xs.mean()), int(ys.mean())) if len(xs) else (W // 2, H // 2)
            if name.startswith("c"):
                cx, cy = cx + int(round(off[0])), cy + int(round(off[1]))
            x0, y0 = max(0, min(W - cell_w, cx - cell_w // 2)), max(0, min(H - cell_h, cy - cell_h // 2))
            im.paste(src.crop((x0, y0, x0 + cell_w, y0 + cell_h)), (i * cell_w, 18))
            d.text((i * cell_w + 4, 2), name, fill=(230, 230, 230))
        im.save(OUT / "sheet.jpg", quality=90)
    log("E24 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
