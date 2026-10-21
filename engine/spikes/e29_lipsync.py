"""Spike E29 — lip-sync in the clay route (proto01_animate 01 §11, 02 §3; D88's experimental S2V): can a Stage-performed character layer talk?

Three routes were proposed (01 §11); two run here on the PS5 rig's final (engine/spikes/out/ps5, the final "Rig": Mara's layer — her padded
animation reference `fig_m/reference.png`, Stage's pose pass `fig_m/pose.mp4` (81 f at 16 fps, 832×480) with its COCO-18 keypoints, and the
layer Wan Animate performed, `fig_m/frames/`, as the baseline); the line is E20's `en1_draft.wav` (English, a draft voice), fitted to the
77-frame window (4.8 s):

  L0  the baseline: PS5's performed layer (no speech)                                          — the PCK and FaceSim to hold
  L1  S2V as the layer: Wan 2.2 S2V-14B fp8 from the reference + the line (E18's graph, 77 f at 16 fps, 832×480, 20 steps)
      — the body moves its own way: PCK against Stage's pose is the question
  L2  S2V drives Wan Animate's face: an S2V talking head of the reference's face (512×512, the same line) is the Animate graph's
      `face_video` (the engine's own optional input, scaled to 512: the expressions come from it) while the body follows Stage's pose pass
  L3  a lip-sync post model — not run: a new custom node is a decision (house rule 2)

Measured per arm (E18's and E23's metrics): sync r (the mouth crop's motion energy against the line's RMS envelope at the best lag within
±3 frames; bar ≥ 0.5), PCK@0.1 against Stage's keypoints every 8th frame (SDPose; L2 must not drop more than 0.05 under L0), FaceSim at the
first, middle and last frame against the reference (bar ≥ 0.45), exec seconds. Outputs under engine/spikes/out/e29/: the frames, mp4s with
the line muxed, a sheet, results.jsonl, log.txt. Starts the pinned engine standalone on 8188 (free; D97: nothing else on the GPU) and
stops it after.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e29_lipsync.py [--arms l0,l1,l2] [--line en1] [--seed N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import e18_lipsync as E18  # noqa: E402  (the S2V graph, the audio fit, the sync metric, FaceSim helpers, mux, sheet)
import e23a_joins as A  # noqa: E402  (the Wan Animate batch graph, frames → mp4)
from e10_stage import pck, sdpose_graph  # noqa: E402
from e12_angles import Engine  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e29"
RESULTS = OUT / "results.jsonl"
FIN = REPO / "engine" / "spikes" / "out" / "ps5" / "project" / "finals" / "fin_0f41f551"
FIG = FIN / "fig_m"
W, H, FPS, FRAMES = 832, 480, 16, 77
SEED = 20261021
HEAD = {"w": 512, "h": 512, "frames": FRAMES, "fps": FPS, "steps": 20}
BARS = {"sync": 0.5, "facesim": 0.45, "pck_drop": 0.05}
PROMPT_L1 = "a woman in a grey wool coat with a black bob and round glasses walks across a plain grey room and turns, speaking the line, natural gestures, steady camera, soft light"
PROMPT_L2 = "the character performs the motion while speaking the line, her mouth moving with the words, natural expression, steady camera, soft light"


def log(msg: str) -> None:
    print(msg, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}\n")


def head_crop(fs: FaceSim, ref: Path, dest: Path, size: int = 512, grow: float = 1.9) -> Path | None:
    """The reference's face as a square head shot (the face box grown, clamped to the picture, resized), for the S2V talking head."""
    im = Image.open(ref).convert("RGB")
    a = np.asarray(im)
    faces = fs.detect(a)
    if not faces:
        return None
    f = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
    cx, cy = (f.bbox[0] + f.bbox[2]) / 2, (f.bbox[1] + f.bbox[3]) / 2
    side = max(f.bbox[2] - f.bbox[0], f.bbox[3] - f.bbox[1]) * grow
    side = min(side, im.width, im.height)
    x0 = int(max(0, min(im.width - side, cx - side / 2)))
    y0 = int(max(0, min(im.height - side, cy - side / 2 - side * 0.08)))     # a little room above the hair
    im.crop((x0, y0, x0 + int(side), y0 + int(side))).resize((size, size), Image.LANCZOS).save(dest)
    return dest


def pck_of(e: Engine, frames: list[Path], gt: list, step: int = 8) -> tuple[float | None, int]:
    hit = total = 0
    for i in range(0, min(len(frames), len(gt)), step):
        hp, _, _ = e.run(sdpose_graph(e.upload(frames[i])), timeout=600)
        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
        h_, t_ = pck([gt[i]], people)
        hit += h_
        total += t_
    return (round(hit / total, 3) if total else None), total


def facesim_of(fs: FaceSim, hero: np.ndarray | None, frames: list[Path]) -> list[float | None]:
    sims: list[float | None] = []
    for idx in (0, len(frames) // 2, len(frames) - 1):
        emb = E18.largest_face(fs, frames[idx])
        sims.append(round(float(fs.similarity(hero, emb)), 3) if hero is not None and emb is not None else None)
    return sims


def sync_of(fs: FaceSim, frames: list[Path], audio: np.ndarray, sr: int) -> tuple[float | None, int, bool]:
    motion, ok = E18.mouth_energy(fs, frames)
    env = E18.rms_envelope(audio, sr, FPS, len(frames))
    r, lag = E18.sync_score(motion[1:], env[1:]) if ok else (None, 0)
    return r, lag, bool(ok)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="l0,l1,l2")
    ap.add_argument("--line", default="en1")
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    if E18.engine_listening():
        print("an engine is already listening on 8188 — stop it first (D97: one GPU job at a time)"); return 2
    for p in (FIG / "reference.png", FIG / "pose.mp4", FIG / "keypoints.json"):
        if not p.is_file():
            print("missing", p); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    wav_src = E18.VOICE / E18.LINE_WAV[a.line]
    gt = json.load((FIG / "keypoints.json").open(encoding="utf-8"))["frames"][:FRAMES]
    base_frames = A.frames_of(FIG / "frames")[:FRAMES]
    fs = FaceSim(E18.MODELS)
    hero = E18.largest_face(fs, FIG / "reference.png")
    log(f"E29 start · arms {arms} · line {a.line} · seed {a.seed} · hero face {'found' if hero is not None else 'NOT found'}")
    eng_log = (OUT / "engine.log").open("a", encoding="utf-8")
    eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
    cells: list[tuple[Path, str]] = []
    rows: dict[str, dict] = {}
    try:
        t0 = time.time()
        while time.time() - t0 < 240 and not E18.engine_listening():
            time.sleep(1.0)
        if not E18.engine_listening():
            log("the engine did not come up"); return 1
        e = Engine(E18.ENGINE)
        ros = Roster(E18.MODELS, [], "full").scan()
        wav = OUT / f"{a.line}_{int(FRAMES / FPS * 1000)}ms.wav"
        audio, sr = E18.fit_audio(wav_src, FRAMES / FPS, wav)
        audio_name = e.upload(wav)
        ref_name = e.upload(FIG / "reference.png")

        def record(arm: str, frames: list[Path], exec_s: float | None, with_speech: bool, w: int, h: int) -> dict:
            r, lag, ok = sync_of(fs, frames, audio, sr) if with_speech else (None, 0, False)
            p, n = pck_of(e, frames, gt)
            sims = facesim_of(fs, hero, frames)
            if with_speech:
                E18.mux(frames, wav, OUT / f"{arm}.mp4", FPS, w, h)
            for idx in np.linspace(0, len(frames) - 1, 6).astype(int):
                cells.append((frames[idx], f"{arm} f{idx}"))
            row = {"arm": arm, "frames": len(frames), "exec_s": None if exec_s is None else round(exec_s, 1), "sync_r": r, "sync_lag": lag, "mouth_found": ok,
                   "pck": p, "pck_points": n, "facesim": sims, "stamp": time.strftime("%Y-%m-%d %H:%M")}
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            log(f"  {arm}: {len(frames)} f, exec {row['exec_s']} s, sync r {r} (lag {lag}, mouth {ok}), PCK {p} on {n} points, FaceSim {sims}")
            rows[arm] = row
            return row

        if "l0" in arms:
            record("l0", base_frames, None, False, W, H)
        if "l1" in arms:
            g, node = E18.s2v_graph(ref_name, audio_name, E18.SPEC["wan_s2v"], a.seed, "e29/l1")
            g["5"]["inputs"]["text"] = PROMPT_L1
            h_, wall, exec_s = e.run(g, timeout=3600)
            frames = E18.download_frames(e, h_, node, OUT / "l1")
            record("l1", frames, exec_s, True, W, H)
        if "l2" in arms:
            head = head_crop(fs, FIG / "reference.png", OUT / "head_ref.png")
            if head is None:
                log("  l2: no face found in the reference — skipped")
            else:
                g, node = E18.s2v_graph(e.upload(head), audio_name, HEAD, a.seed, "e29/l2_head")
                h_, wall, exec_head = e.run(g, timeout=3600)
                head_frames = E18.download_frames(e, h_, node, OUT / "l2_head")
                r_h, lag_h, ok_h = sync_of(fs, head_frames, audio, sr)
                E18.mux(head_frames, wav, OUT / "l2_head.mp4", FPS, HEAD["w"], HEAD["h"])
                log(f"  l2 head: {len(head_frames)} f, exec {exec_head:.0f} s, sync r {r_h} (lag {lag_h}, mouth {ok_h})")
                face_mp4 = OUT / "l2_face.mp4"
                A.encode(head_frames, face_mp4, FPS)
                pose_name = e.upload(FIG / "pose.mp4")
                g = A.batch_graph(ros, pose_name, ref_name, a.seed, 0, [], "e29/l2")
                g["5"]["inputs"]["text"] = PROMPT_L2
                g["70"] = {"class_type": "LoadVideo", "inputs": {"file": e.upload(face_mp4)}}
                g["71"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["70", 0]}}
                g["11"]["inputs"]["face_video"] = ["71", 0]
                h_, wall, exec_s = e.run(g, timeout=3600)
                frames = E18.download_frames(e, h_, "15", OUT / "l2")
                row = record("l2", frames, exec_s, True, W, H)
                row["head"] = {"exec_s": round(exec_head, 1), "sync_r": r_h, "sync_lag": lag_h, "mouth_found": ok_h}
        if cells:
            E18.sheet(cells, OUT / "sheet.jpg")
        # the verdict against the bars
        l0 = rows.get("l0", {}).get("pck")
        for arm in ("l1", "l2"):
            r = rows.get(arm)
            if not r:
                continue
            vals = [s for s in r["facesim"] if s is not None]
            verdict = {"sync": r["sync_r"] is not None and r["sync_r"] >= BARS["sync"],
                       "facesim": bool(vals) and min(vals) >= BARS["facesim"],
                       "pose": r["pck"] is not None and l0 is not None and r["pck"] >= l0 - BARS["pck_drop"]}
            log(f"  {arm} bars: {verdict} (L0 PCK {l0})")
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"arm": arm, "bars": verdict, "l0_pck": l0, "stamp": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
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
    log("E29 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
