"""E11 Stage → video spike (ArtCraft 08 §7, D74): can a pass sequence drive i2v?

Inputs: five animated blockings rendered by frontend/e2e/spikes/e11.run.mjs into engine/spikes/out/e11/<shot>/ (pose/ and depth/ PNG
sequences, 121 frames at 24 fps, 1024 × 576; clay0.png; keypoints.json). Steps:
  guides   encode pose.mp4 / depth.mp4 per shot (h264, near-lossless) — the IC-LoRA guide videos
  starts   the first frame of each shot: E10's method 1 (Klein 9B + the clay frame as reference) → start.png
  run      ltx_plain (loom2's own LTX-2.3 i2v graph, graphs.build_i2v, Draft 8 steps) · ltx_ic_pose · ltx_ic_depth (the same + LTX-2.3's
           IC-LoRA Union through core GetICLoRAParameters + LTXVAddGuide on the guide video at frame 0)
  score    SDPose on every 20th frame vs the rendered keypoints (PCK@0.1) per clip; timings; a frame sheet per method
Pass bars (08 §7): no OOM; ≤ 2 × plain LTX (141 s for 5 s, E5); pose followed in ≥ 4 / 5 clips (PCK@0.1 ≥ 0.5 over the sampled frames,
checked on the sheets).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e11_video.py guides|starts|run|score [--methods ...] [--shots ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e10_stage import klein_clay, pck, sdpose_graph  # noqa: E402
from e12_angles import Engine  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
from loom2.engine.graphs import build_i2v  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V  # noqa: E402
from loom2.roster import Roster  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e11"
RESULTS = OUT / "results.jsonl"
MODELS = Path("F:/loom2-models")
LTX = next(i for i, s in registry.SPECS.items() if s.graph == "ltx23")
ROSTER = Roster(MODELS, [], "full").scan()                                # D80: F:/loom2-models only (D: is a backup drive)
IC_LORA = "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors"
SEED, FRAMES, FPS, W, H = 20261013, 121, 24, 1024, 576


def shots(arg: str) -> list[str]:
    return arg.split(",") if arg else sorted(p.name for p in OUT.iterdir() if p.is_dir() and (p / "keypoints.json").is_file())


def encode(frames: list[Path], path: Path) -> None:
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=FPS)
        s.width, s.height, s.pix_fmt, s.time_base = W, H, "yuv420p", Fraction(1, FPS)
        s.options = {"crf": "10", "preset": "veryfast", "g": "24"}
        for i, f in enumerate(frames):
            vf = av.VideoFrame.from_ndarray(np.asarray(Image.open(f).convert("RGB")), format="rgb24"); vf.pts = i
            for p in s.encode(vf):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


def ltx_graph(prompt: str, start: str, guide: str | None) -> tuple[dict, str]:
    recipe = I2V(model_id=LTX, start_asset="start", prompt_text=prompt, frames=FRAMES, fps=FPS, width=W, height=H, preset="draft")
    c = build_i2v(recipe, ROSTER, SEED, "e11/ltx", start)
    g = c.graph
    if guide:
        g["50"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": IC_LORA, "strength_model": 1.0}}
        g["51"] = {"class_type": "GetICLoRAParameters", "inputs": {"iclora_model": ["50", 0]}}
        g["52"] = {"class_type": "LoadVideo", "inputs": {"file": guide}}
        g["53"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["52", 0]}}
        last = [k for k in g if k.startswith("guide")]
        pos, neg, lat = ([last[-1], 0], [last[-1], 1], [last[-1], 2]) if last else (["8", 0], ["8", 1], ["8", 2])
        g["54"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": ["53", 0],
                                                          "frame_idx": 0, "strength": 1.0, "iclora_parameters": ["51", 0]}}
        g["13"]["inputs"]["video_latent"] = ["54", 2]
        g["14"]["inputs"].update(model=["50", 0], conditioning=["54", 0])
        g["20"]["inputs"].update(positive=["54", 0], negative=["54", 1])
    return g, c.output_node


METHODS = {"ltx_plain": None, "ltx_ic_pose": "pose", "ltx_ic_depth": "depth"}


def frames_of(h: dict, node: str) -> list[dict]:
    return h["outputs"][node]["images"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["guides", "starts", "run", "score"])
    ap.add_argument("--server", default="127.0.0.1:8188")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--shots", default="")
    a = ap.parse_args()
    if a.step == "guides":
        for sid in shots(a.shots):
            for kind in ("pose", "depth"):
                encode(sorted((OUT / sid / kind).glob("*.png")), OUT / sid / f"{kind}.mp4")
            print(f"{sid}: guides encoded")
        return 0
    eng = Engine(a.server)
    if a.step == "starts":
        for sid in shots(a.shots):
            kp = json.loads((OUT / sid / "keypoints.json").read_text(encoding="utf-8"))
            h, _, ex = eng.run(klein_clay(prompt=kp["prompt"], seed=SEED, up={"clay": eng.upload(OUT / sid / "clay0.png")}))
            eng.image(h, "90").save(OUT / sid / "start.png")
            print(f"{sid}: start frame {ex:.1f} s")
        return 0
    if a.step == "run":
        for m in a.methods.split(","):
            first = True
            for sid in shots(a.shots):
                kp = json.loads((OUT / sid / "keypoints.json").read_text(encoding="utf-8"))
                start = eng.upload(OUT / sid / "start.png")
                guide = None
                if METHODS[m]:
                    p = OUT / sid / f"{METHODS[m]}.mp4"
                    r = eng.http.post("/upload/image", files={"image": (f"e11_{sid}_{METHODS[m]}.mp4", p.read_bytes(), "video/mp4")}, data={"overwrite": "true", "type": "input"})
                    r.raise_for_status(); guide = r.json()["name"]
                try:
                    g, node = ltx_graph(kp["prompt"], start, guide)
                    h, wall, ex = eng.run(g)
                    dst = OUT / m / sid
                    dst.mkdir(parents=True, exist_ok=True)
                    imgs = frames_of(h, node)
                    for i in range(0, len(imgs), 20):
                        o = imgs[i]
                        rr = eng.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
                        (dst / f"{i:04d}.png").write_bytes(rr.content)
                    row = {"method": m, "shot": sid, "ok": True, "exec_s": round(ex, 1), "wall_s": round(wall, 1), "frames": len(imgs), "cold": first}
                except Exception as e:  # noqa: BLE001 — an OOM is a result
                    row = {"method": m, "shot": sid, "ok": False, "error": str(e)[:400], "cold": first}
                first = False
                row["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                with RESULTS.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                print(f"[{m} {sid}] {row.get('exec_s', row.get('error'))}")
        return 0
    # score
    rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    latest = {(r["method"], r["shot"]): r for r in rows}
    summary: dict = {}
    for (m, sid), r in sorted(latest.items()):
        if not r.get("ok"):
            continue
        gt = json.loads((OUT / sid / "keypoints.json").read_text(encoding="utf-8"))["frames"]
        hit = tot = 0
        for f in sorted((OUT / m / sid).glob("*.png")):
            idx = int(f.stem)
            if idx >= len(gt):
                continue
            hp, _, _ = eng.run(sdpose_graph(eng.upload(f)))
            people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
            h_, t_ = pck(gt[idx], people)
            hit += h_; tot += t_
        r.update(pck=round(hit / tot, 3) if tot else None)
        d = summary.setdefault(m, {"pck": [], "warm": [], "cold": []})
        d["pck"].append(r["pck"] or 0.0)
        (d["cold"] if r["cold"] else d["warm"]).append(r["exec_s"])
    plain = float(np.median(summary.get("ltx_plain", {}).get("warm") or [float("nan")]))
    for m, d in summary.items():
        w = float(np.median(d["warm"])) if d["warm"] else float("nan")
        print(f"{m}: PCK per clip {d['pck']} · followed (≥ 0.5) {sum(1 for x in d['pck'] if x >= 0.5)}/{len(d['pck'])} · warm {w:.1f} s"
              f" ({w / plain:.2f}× plain) · cold {d['cold']}")
    (OUT / "scored.json").write_text(json.dumps(list(latest.values()), indent=1), encoding="utf-8")
    for m in summary:                                                    # sheet: rows = shots, columns = the pose guide and sampled frames
        sids = shots(a.shots)
        tw, th = 256, 144
        sheet = Image.new("RGB", (40 + 8 * (tw + 4), len(sids) * (th + 4)), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for i, sid in enumerate(sids):
            dr.text((4, i * (th + 4) + th // 2), sid[:6], fill=(240, 180, 60))
            cells = [OUT / sid / "pose" / "0060.png"] + sorted((OUT / m / sid).glob("*.png"))[:7]
            for j, p in enumerate(cells):
                im = Image.open(p).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (40 + j * (tw + 4), i * (th + 4)))
        sheet.save(OUT / f"sheet_{m}.jpg", quality=84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
