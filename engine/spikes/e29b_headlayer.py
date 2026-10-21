"""Spike E29b — the head as its own layer (D117, proto01_animate 01 §11): lip-sync on a small head in a full shot by cropping the head,
working at the models' own size and pasting back — the author's idea and the field's practice (journal 2026-10-21 21:37).

Material: the PS5 rig's final (engine/spikes/out/ps5): Mara's performed layer `fig_m/frames` (77 of 81 frames at 16 fps, 832×480), Stage's
keypoints `fig_m/keypoints.json` (COCO-18: the head box is tracked from the nose, eyes and ears, smoothed), the pose pass `fig_m/pose.mp4`,
her padded reference `fig_m/reference.png`; E29's S2V talking head `out/e29/l2_head` (77 frames, 512², the line en1) and its face video.

The head box per frame: centred on the head's keypoints, a square of 2.6 × the nose–neck distance (at least 1.8 × the ear spread),
smoothed over 9 frames, then clamped to the picture; the crop is resized to 512² (Lanczos) and pasted back with a feathered edge
(a rounded square, 12 % soft) — `paste()`.

Arms (the H ones need no download; the L3 ones run a standalone model in a spike venv, see --l3):
  H0    the baseline head crop of the performed layer (no speech)                       — the sync, articulation and FaceSim to compare
  L2c   E29's L2 with a calmer driving head: S2V on the reference's face with a quiet prompt → Wan Animate's `face_video` on the full
        layer (as E29) — measured on its head crop; the calmer head itself is also measured
  L2h   the head as a layer: Wan Animate on the head crop — the pose pass cropped by the same boxes, the reference's head crop as the
        reference, E29's S2V head as the face video — a 512² head clip pasted back onto the layer
  L2hc  L2h with the calmer head as the face video
  L3a   LatentSync (ByteDance, Apache-2.0 code; the 1.5 weights OpenRAIL++) on the head-crop clip at 25 fps, pasted back
        (--l3 "cmd" runs the model: a command line with {video} {audio} {out} placeholders; the result is resampled to 16 fps)

Measured per arm on the head crop (512²): sync r (E18's metric: the mouth's motion energy against the line's RMS envelope, best lag
±3 f; bar ≥ 0.5), articulation (the mouth's mean motion energy — the exaggeration proxy, against H0's and the head S2V's), FaceSim at
three frames against the reference's head (bar: ≥ H0's), and on the pasted frames PCK against Stage (must stay) and the paste seam
(the mean |Δ| of luma across the crop's edge band against the same band in the baseline). Outputs under engine/spikes/out/e29b/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e29b_headlayer.py [--arms h0,l2c,l2h,l2hc,l3a] [--l3 "<cmd>"] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e18_lipsync as E18  # noqa: E402
import e23a_joins as A  # noqa: E402
from e10_stage import pck, sdpose_graph  # noqa: E402
from e12_angles import Engine  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e29b"
RESULTS = OUT / "results.jsonl"
E29 = REPO / "engine" / "spikes" / "out" / "e29"
FIN = REPO / "engine" / "spikes" / "out" / "ps5" / "project" / "finals" / "fin_0f41f551"
FIG = FIN / "fig_m"
W, H, FPS, FRAMES, CROP = 832, 480, 16, 77, 512
SEED = 20261021
HEAD = {"w": 512, "h": 512, "frames": FRAMES, "fps": FPS, "steps": 20}
PROMPT_CALM = "a close-up of the character speaking the line softly to the camera, small natural mouth movements, a calm still face, steady camera, soft light"
PROMPT_HEAD = "the character's head and shoulders, she speaks the line with natural mouth movements, following the motion, sharp, soft light"


def log(msg: str) -> None:
    print(msg, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}\n")


# ---- the head box --------------------------------------------------------------------------------------------------------------
def head_boxes(kps: list, n: int) -> list[tuple[int, int, int]]:
    """(x0, y0, side) per frame from COCO-18 keypoints: the head's centre and size, smoothed, clamped to the picture."""
    cs, ss = [], []
    for i in range(n):
        k = np.array(kps[i], dtype=float)
        head = [j for j in (0, 14, 15, 16, 17) if k[j][2] > 0]
        pts = k[head, :2] if head else k[:1, :2]
        c = pts.mean(axis=0)
        nose_neck = np.hypot(*(k[0][:2] - k[1][:2])) if k[0][2] > 0 and k[1][2] > 0 else 40.0
        ears = np.hypot(*(k[16][:2] - k[17][:2])) if k[16][2] > 0 and k[17][2] > 0 else 0.0
        side = max(2.6 * nose_neck, 1.8 * ears, 48.0)
        cs.append(c)
        ss.append(side)
    cs_a, ss_a = np.array(cs), np.array(ss)
    k = 9
    pad = k // 2
    cs_s = np.array([cs_a[max(0, i - pad):i + pad + 1].mean(axis=0) for i in range(n)])
    ss_s = np.array([ss_a[max(0, i - pad):i + pad + 1].mean() for i in range(n)])
    boxes = []
    for i in range(n):
        side = int(round(min(ss_s[i], W, H)))
        x0 = int(round(max(0, min(W - side, cs_s[i][0] - side / 2))))
        y0 = int(round(max(0, min(H - side, cs_s[i][1] - side * 0.56))))   # the head sits in the upper part of the box
        boxes.append((x0, y0, side))
    return boxes


def crop(frames: list[Path], boxes: list[tuple[int, int, int]], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, (p, (x0, y0, s)) in enumerate(zip(frames, boxes)):
        q = dest / f"{i:04d}.png"
        Image.open(p).convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((CROP, CROP), Image.LANCZOS).save(q)
        out.append(q)
    return out


def feather_mask(size: int, soft: float = 0.12) -> np.ndarray:
    m = Image.new("L", (size, size), 0)
    r = int(size * 0.18)
    ImageDraw.Draw(m).rounded_rectangle([int(size * soft / 2), int(size * soft / 2), size - int(size * soft / 2), size - int(size * soft / 2)], radius=r, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size * soft / 2))
    return np.asarray(m, dtype=np.float32)[..., None] / 255.0


def paste(base: list[Path], heads: list[Path], boxes: list[tuple[int, int, int]], dest: Path) -> list[Path]:
    """The head clip back onto the layer frames at the boxes, a feathered edge (the crop's own size, resized with it)."""
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, (p, hp, (x0, y0, s)) in enumerate(zip(base, heads, boxes)):
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
        h = np.asarray(Image.open(hp).convert("RGB").resize((s, s), Image.LANCZOS), dtype=np.float32)
        m = np.asarray(Image.fromarray((feather_mask(CROP)[..., 0] * 255).astype(np.uint8)).resize((s, s), Image.BILINEAR), dtype=np.float32)[..., None] / 255.0
        region = a[y0:y0 + s, x0:x0 + s]
        a[y0:y0 + s, x0:x0 + s] = region * (1 - m) + h * m
        q = dest / f"{i:04d}.png"
        Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8)).save(q)
        out.append(q)
    return out


# ---- the measures ---------------------------------------------------------------------------------------------------------------
def luma(p: Path) -> np.ndarray:
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
    return a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114


def seam(frames: list[Path], base: list[Path], boxes: list[tuple[int, int, int]], band: int = 6) -> float | None:
    """The mean |Δ luma| in a band around the crop's edge, pasted against the baseline's own band (0 = no seam added)."""
    vals = []
    for i in range(0, min(len(frames), len(base)), 8):
        x0, y0, s = boxes[i]
        la, lb = luma(frames[i]), luma(base[i])
        m = np.zeros(la.shape, bool)
        m[max(0, y0 - band):y0 + s + band, max(0, x0 - band):x0 + s + band] = True
        m[y0 + band:y0 + s - band, x0 + band:x0 + s - band] = False
        if m.any():
            vals.append(float(np.abs(la - lb)[m].mean()))
    return round(float(np.mean(vals)), 2) if vals else None


def measure_head(name: str, heads: list[Path], audio: np.ndarray, sr: int, fs: FaceSim, hero: np.ndarray | None, with_speech: bool) -> dict:
    motion, ok = E18.mouth_energy(fs, heads)
    env = E18.rms_envelope(audio, sr, FPS, len(heads))
    r, lag = E18.sync_score(motion[1:], env[1:]) if ok and with_speech else (None, 0)
    artic = round(float(np.mean(motion[1:])), 3) if ok else None
    sims = []
    for idx in (0, len(heads) // 2, len(heads) - 1):
        emb = E18.largest_face(fs, heads[idx])
        sims.append(round(float(fs.similarity(hero, emb)), 3) if hero is not None and emb is not None else None)
    return {"sync_r": r, "sync_lag": lag, "mouth_found": bool(ok), "articulation": artic, "facesim": sims}


def record(row: dict) -> None:
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    log("  " + json.dumps({k: v for k, v in row.items() if k != "stamp"}))


def resample(frames: list[Path], src_fps: int, dst_fps: int, dest: Path) -> list[Path]:
    """Nearest-frame resampling between frame rates (16 ↔ 25) for the models that want 25 fps."""
    dest.mkdir(parents=True, exist_ok=True)
    n = int(round(len(frames) * dst_fps / src_fps))
    out = []
    for i in range(n):
        j = min(len(frames) - 1, int(round(i * src_fps / dst_fps)))
        q = dest / f"{i:04d}.png"
        shutil.copyfile(frames[j], q)
        out.append(q)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="h0,l2c,l2h,l2hc")
    ap.add_argument("--l3", default="", help="the L3 command with {video} {audio} {out} placeholders (a standalone model in its venv)")
    ap.add_argument("--l3-source", default="h0", help="the head clip the L3 model works on: h0 (the layer's own crop) or a head-layer arm's output (l2h, l2hc)")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    gpu_arms = [x for x in arms if x in ("l2c", "l2h", "l2hc")]
    if gpu_arms and E18.engine_listening():
        print("an engine is already listening on 8188 — stop it first (D97)"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    layer = A.frames_of(FIG / "frames")[:FRAMES]
    kps = json.load((FIG / "keypoints.json").open(encoding="utf-8"))["frames"][:FRAMES]
    boxes = head_boxes(kps, FRAMES)
    fs = FaceSim(E18.MODELS)
    head_ref = E29 / "head_ref.png"
    hero = E18.largest_face(fs, head_ref) if head_ref.is_file() else E18.largest_face(fs, FIG / "reference.png")
    wav = OUT / "en1.wav"
    audio, sr = E18.fit_audio(E18.VOICE / E18.LINE_WAV["en1"], FRAMES / FPS, wav)
    log(f"E29b start · arms {arms} · boxes {boxes[0]} … {boxes[-1]} · seed {a.seed}")
    h0 = crop(layer, boxes, OUT / "h0")
    A.encode(h0, OUT / "h0.mp4", FPS)
    if "h0" in arms:
        m = measure_head("h0", h0, audio, sr, fs, hero, False)
        record({"arm": "h0", **m, "pck": None, "seam": 0.0, "stamp": time.strftime("%Y-%m-%d %H:%M")})
    e29_heads = A.frames_of(E29 / "l2_head")[:FRAMES] if (E29 / "l2_head").is_dir() else []
    if e29_heads:
        m = measure_head("e29_head", e29_heads, audio, sr, fs, hero, True)
        record({"arm": "e29_head", **m, "stamp": time.strftime("%Y-%m-%d %H:%M")})
    cells: list[tuple[Path, str]] = []
    for idx in (0, 38, 76):
        cells.append((h0[idx], f"h0 f{idx}"))

    def finish(arm: str, heads: list[Path], exec_s: float, e: Engine | None, base_full: list[Path] | None = None) -> None:
        """A head clip measured, pasted back, the pasted frames measured (PCK, seam), the mp4s and the sheet cells."""
        m = measure_head(arm, heads, audio, sr, fs, hero, True)
        E18.mux(heads, wav, OUT / f"{arm}_head.mp4", FPS, CROP, CROP)
        pasted = paste(base_full or layer, heads, boxes, OUT / f"{arm}_pasted")
        E18.mux(pasted, wav, OUT / f"{arm}.mp4", FPS, W, H)
        p = None
        if e is not None:
            hit = total = 0
            for i in range(0, FRAMES, 8):
                hp, _, _ = e.run(sdpose_graph(e.upload(pasted[i])), timeout=600)
                people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                h_, t_ = pck([kps[i]], people)
                hit += h_
                total += t_
            p = round(hit / total, 3) if total else None
        record({"arm": arm, **m, "exec_s": round(exec_s, 1), "pck": p, "seam": seam(pasted, layer, boxes), "stamp": time.strftime("%Y-%m-%d %H:%M")})
        for idx in (0, 38, 76):
            cells.append((heads[idx], f"{arm} f{idx}"))

    if gpu_arms:
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
            audio_name = e.upload(wav)
            calm_heads: list[Path] = []
            if "l2c" in arms or "l2hc" in arms:
                g, node = E18.s2v_graph(e.upload(head_ref if head_ref.is_file() else FIG / "reference.png"), audio_name, HEAD, a.seed, "e29b/calm_head")
                g["5"]["inputs"]["text"] = PROMPT_CALM
                h, wall, exec_s = e.run(g, timeout=3600)
                calm_heads = E18.download_frames(e, h, node, OUT / "calm_head")
                m = measure_head("calm_head", calm_heads, audio, sr, fs, hero, True)
                E18.mux(calm_heads, wav, OUT / "calm_head.mp4", FPS, CROP, CROP)
                record({"arm": "calm_head", **m, "exec_s": round(exec_s, 1), "stamp": time.strftime("%Y-%m-%d %H:%M")})
                A.encode(calm_heads, OUT / "calm_face.mp4", FPS)
            if "l2c" in arms and calm_heads:
                pose_name = e.upload(FIG / "pose.mp4")
                g = A.batch_graph(ros, pose_name, e.upload(FIG / "reference.png"), a.seed, 0, [], "e29b/l2c")
                g["5"]["inputs"]["text"] = "the character performs the motion while speaking the line softly, small natural mouth movements, steady camera, soft light"
                g["70"] = {"class_type": "LoadVideo", "inputs": {"file": e.upload(OUT / "calm_face.mp4")}}
                g["71"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["70", 0]}}
                g["11"]["inputs"]["face_video"] = ["71", 0]
                h, wall, exec_s = e.run(g, timeout=3600)
                full = E18.download_frames(e, h, "15", OUT / "l2c_full")
                heads = crop(full, boxes, OUT / "l2c")
                m = measure_head("l2c", heads, audio, sr, fs, hero, True)
                E18.mux(full, wav, OUT / "l2c.mp4", FPS, W, H)
                E18.mux(heads, wav, OUT / "l2c_head.mp4", FPS, CROP, CROP)
                record({"arm": "l2c", **m, "exec_s": round(exec_s, 1), "pck": None, "seam": None, "stamp": time.strftime("%Y-%m-%d %H:%M")})
                for idx in (0, 38, 76):
                    cells.append((heads[idx], f"l2c f{idx}"))
            if "l2h" in arms or "l2hc" in arms:
                # the pose pass cropped by the head boxes and the reference's head crop: the head's own Animate run
                pose_frames = []
                with __import__("av").open(str(FIG / "pose.mp4")) as c:
                    for fr in c.decode(video=0):
                        pose_frames.append(fr.to_image())
                        if len(pose_frames) >= FRAMES:
                            break
                pose_dir = OUT / "pose_head"
                pose_dir.mkdir(exist_ok=True)
                pose_crops = []
                for i, (im, (x0, y0, s)) in enumerate(zip(pose_frames, boxes)):
                    q = pose_dir / f"{i:04d}.png"
                    im.convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((CROP, CROP), Image.LANCZOS).save(q)
                    pose_crops.append(q)
                A.encode(pose_crops, OUT / "pose_head.mp4", FPS)
                pose_head_name = e.upload(OUT / "pose_head.mp4")
                ref_head = OUT / "ref_head.png"
                x0, y0, s = boxes[0]
                Image.open(FIG / "reference.png").convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((CROP, CROP), Image.LANCZOS).save(ref_head)
                ref_head_name = e.upload(ref_head)
                for arm, face in (("l2h", E29 / "l2_face.mp4"), ("l2hc", OUT / "calm_face.mp4")):
                    if arm not in arms or not face.is_file():
                        continue
                    g = A.batch_graph(ros, pose_head_name, ref_head_name, a.seed, 0, [], f"e29b/{arm}")
                    g["5"]["inputs"]["text"] = PROMPT_HEAD
                    g["11"]["inputs"].update({"width": CROP, "height": CROP})       # the reference head and the pose crops are 512² already
                    g["70"] = {"class_type": "LoadVideo", "inputs": {"file": e.upload(face)}}
                    g["71"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["70", 0]}}
                    g["11"]["inputs"]["face_video"] = ["71", 0]
                    h, wall, exec_s = e.run(g, timeout=3600)
                    if "15" not in (h.get("outputs") or {}):
                        msgs = {m_[0]: m_[1] for m_ in h.get("status", {}).get("messages", [])}
                        log(f"  FAILED {arm}: {json.dumps(msgs.get('execution_error', {}))[:400]}")
                        continue
                    heads = E18.download_frames(e, h, "15", OUT / arm)
                    finish(arm, heads, exec_s, e)
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
    if "l3a" in arms and a.l3:
        # the head clip (the layer's own crop, or a head-layer arm's sharp output) at 25 fps for the model, its result back at 16 fps, pasted
        src_dir = OUT / a.l3_source if a.l3_source != "h0" else OUT / "h0"
        src = A.frames_of(src_dir)[:FRAMES] if src_dir.is_dir() else h0
        if not src:
            log(f"  l3a: no frames under {src_dir}"); src = h0
        h0_25 = resample(src, FPS, 25, OUT / "l3_in_25")
        A.encode(h0_25, OUT / "l3_in_25.mp4", 25)
        out_mp4 = OUT / "l3a_25.mp4"
        cmd = a.l3.format(video=str(OUT / "l3_in_25.mp4"), audio=str(wav), out=str(out_mp4))
        log(f"  l3a on {a.l3_source}: {cmd}")
        t0 = time.time()
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        exec_s = time.time() - t0
        (OUT / "l3a.log").write_text((r.stdout or "") + "\n" + (r.stderr or ""), encoding="utf-8")
        if r.returncode != 0 or not out_mp4.is_file():
            log(f"  FAILED l3a (rc {r.returncode}): {(r.stderr or r.stdout)[-600:]}")
        else:
            frames25 = []
            with __import__("av").open(str(out_mp4)) as c:
                d = OUT / "l3a_25"
                d.mkdir(exist_ok=True)
                for i, fr in enumerate(c.decode(video=0)):
                    q = d / f"{i:04d}.png"
                    fr.to_image().convert("RGB").resize((CROP, CROP), Image.LANCZOS).save(q)
                    frames25.append(q)
            heads = resample(frames25, 25, FPS, OUT / "l3a")[:FRAMES]
            finish("l3a", heads, exec_s, None)
    if cells:
        E18.sheet(cells, OUT / "sheet.jpg", cols=3, cell=256)
    log("E29b done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
