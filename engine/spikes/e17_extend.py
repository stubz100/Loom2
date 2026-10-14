"""E17 — continuity across the join (19 §2, D87): can a clip be continued so the next segment keeps the motion and the face?

Methods, on the pinned engine's own nodes, no new weights:
  ltx_guide   LTX-2.3 distilled: the previous segment's last LEAD (9) frames as an `LTXVAddGuide` frame sequence at frame 0 of the next
              segment (strength 1.0, no IC-LoRA), the start image = the previous last frame; 121 f at 24 fps, 1024×576, the draft preset
  wan_weld    Wan 2.2 I2V Draft (Lightning 2 + 2): the previous segment's last frame as the next start (today's extract → first frame), then
              the join welded with rife-ncnn-vulkan (E9's tool): WELD bridging frames between the previous last frame and the next
              segment's second frame replace the duplicated first frame; 81 f at 16 fps, 832×480
Chains: three bench starts (bench/i2v) × three segments with a continuation prompt each. Scores per chain and method:
  seam        the mean absolute grey difference across the join (ltx_guide: the frame after the lead-in vs the last pinned one; wan_weld: the
              worst transition through the weld, and the raw cut before it) divided by the segment's own median consecutive difference —
              bar ≤ 1.5
  facesim     FaceSim of the start frame's largest face at the chain's first and last frame — bar ≥ 0.45 at both ends
  time        exec seconds per segment; an extended segment ≤ 1.3 × the plain first one (ltx_guide)
Outputs under engine/spikes/out/e17/: every segment and chain as mp4 (muxed by PyAV as E11), a join sheet per chain and method,
results.jsonl. Needs port 8188 free (starts the engine standalone, stops it after); the GPU idle otherwise.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e17_extend.py [--methods ltx_guide,wan_weld] [--chains alley,cabin,rooftop] [--segments 3]
"""
from __future__ import annotations

import argparse
import io
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
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine  # noqa: E402
from loom2.engine.graphs import build_i2v  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V  # noqa: E402
from loom2.roster import Roster  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "e17"
RESULTS = OUT / "results.jsonl"
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
ENGINE = "127.0.0.1:8188"
ROSTER = Roster(MODELS, [], "full").scan()
LTX = next(i for i, s in registry.SPECS.items() if s.graph == "ltx23")
WAN = registry.default_model("i2v")
RIFE = next(iter(sorted((REPO / "engine" / "tools").glob("rife-ncnn-vulkan-*/rife-ncnn-vulkan.exe"))), None)
LEAD, WELD, SEED = 9, 2, 20261014
BARS = {"seam": 1.5, "facesim": 0.45, "time": 1.3}
BENCH = REPO / "bench" / "i2v" / "frames"
CHAINS = {
    "alley": ("alley-rain_s20261004.png", ["she slowly turns to face the camera and lowers the compass, rain keeps falling, neon flickers, subtle handheld camera",
                                           "she looks past the camera down the alley, lifts the compass again and checks it, rain and neon steady, the camera holds",
                                           "she turns away and walks a few steps down the alley into the rain, the neon sign flickers, the camera stays"]),
    "cabin": ("captain-cabin_s20261004.png", ["slow dolly push-in toward the chart table, lamp flame flickers, the captain nods once",
                                              "the captain leans over the chart and traces a route with his finger, the lamp flame flickers, the camera holds",
                                              "he straightens up and looks at the other man, who shakes his head slowly, the lamp flickers, the camera holds"]),
    "rooftop": ("rooftop-night_s20261004.png", ["she rises from the crouch and stands at the roof edge looking out, cloak moves in the wind",
                                                "she stands at the edge, the cloak streams in the wind, she turns her head to the left scanning the city, the moon holds",
                                                "she steps back from the edge and turns toward the camera, the cloak settles, the roofline and the moon stay fixed"]),
}
SPEC = {"ltx_guide": {"model": LTX, "frames": 121, "fps": 24, "w": 1024, "h": 576}, "wan_weld": {"model": WAN, "frames": 81, "fps": 16, "w": 832, "h": 480},
        "wan_ltx": {"model": LTX, "frames": 121, "fps": 24, "w": 1024, "h": 576, "first": "wan_weld"}}   # the first segment Wan (identity), the rest LTX guide-frame extension


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def engine_listening() -> bool:
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def encode(frames: list[Path], path: Path, fps: int, w: int, h: int) -> None:
    with av.open(str(path), "w") as out:
        s = out.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt, s.time_base = w, h, "yuv420p", Fraction(1, fps)
        s.options = {"crf": "10", "preset": "veryfast", "g": str(fps)}
        for i, f in enumerate(frames):
            im = Image.open(f).convert("RGB")
            if im.size != (w, h):
                im = im.resize((w, h), Image.LANCZOS)
            vf = av.VideoFrame.from_ndarray(np.asarray(im), format="rgb24")
            vf.pts = i
            for p in s.encode(vf):
                out.mux(p)
        for p in s.encode():
            out.mux(p)


def grey(p: Path, size: tuple[int, int]) -> np.ndarray:
    return np.asarray(Image.open(p).convert("L").resize(size, Image.BILINEAR), dtype=np.float32)


def diff(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a - b)))


def within(frames: list[Path], size: tuple[int, int]) -> float:
    gs = [grey(f, size) for f in frames]
    return float(np.median([diff(gs[i], gs[i + 1]) for i in range(len(gs) - 1)]))


def largest_face(fs: FaceSim, p: Path) -> np.ndarray | None:
    a = np.asarray(Image.open(p).convert("RGB"))
    faces = fs.detect(a)
    return fs.embed(a, max(faces, key=lambda x: x.area).kps) if faces else None


def download_frames(e: Engine, h: dict, node: str, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, o in enumerate(h["outputs"][node]["images"]):
        r = e.http.get("/view", params={"filename": o["filename"], "subfolder": o.get("subfolder", ""), "type": o.get("type", "output")})
        p = dest / f"{i:06d}.png"
        p.write_bytes(r.content)
        out.append(p)
    return out


def ltx_extended_graph(prompt: str, start_name: str, lead_name: str | None, sp: dict, seed: int, prefix: str) -> tuple[dict, str]:
    """loom2's own LTX graph (build_i2v) with, for a continuation, the lead-in frames pinned at frame 0 by LTXVAddGuide — no IC-LoRA."""
    recipe = I2V(model_id=sp["model"], start_asset="start", prompt_text=prompt, frames=sp["frames"], fps=sp["fps"], width=sp["w"], height=sp["h"], preset="draft")
    c = build_i2v(recipe, ROSTER, seed, prefix, start_name)
    g = c.graph
    if lead_name:
        g["52"] = {"class_type": "LoadVideo", "inputs": {"file": lead_name}}
        g["53"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["52", 0]}}
        g["53s"] = {"class_type": "ImageScale", "inputs": {"image": ["53", 0], "upscale_method": "lanczos", "width": sp["w"], "height": sp["h"], "crop": "center"}}
        last = [k for k in g if k.startswith("guide")]
        pos, neg, lat = ([last[-1], 0], [last[-1], 1], [last[-1], 2]) if last else (["8", 0], ["8", 1], ["8", 2])
        g["54"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": pos, "negative": neg, "vae": ["3", 0], "latent": lat, "image": ["53s", 0], "frame_idx": 0, "strength": 1.0}}
        g["13"]["inputs"]["video_latent"] = ["54", 2]
        g["14"]["inputs"]["conditioning"] = ["54", 0]
        g["20"]["inputs"].update(positive=["54", 0], negative=["54", 1])
    return g, c.output_node


def wan_graph(prompt: str, start_name: str, sp: dict, seed: int, prefix: str) -> tuple[dict, str]:
    recipe = I2V(model_id=sp["model"], start_asset="start", prompt_text=prompt, frames=sp["frames"], fps=sp["fps"], width=sp["w"], height=sp["h"], preset="draft")
    c = build_i2v(recipe, ROSTER, seed, prefix, start_name)
    return c.graph, c.output_node


def weld(a_last: Path, b_second: Path, dest: Path) -> list[Path]:
    """WELD bridging frames between the previous segment's last frame and the next segment's second frame (rife-ncnn-vulkan, E9's tool)."""
    assert RIFE is not None, "rife-ncnn-vulkan.exe not found under engine/tools/"
    with tempfile.TemporaryDirectory(prefix="e17-weld-") as td:
        src, outd = Path(td) / "in", Path(td) / "out"
        src.mkdir(); outd.mkdir()
        shutil.copy2(a_last, src / "000000.png"); shutil.copy2(b_second, src / "000001.png")
        n = WELD + 2
        r = subprocess.run([str(RIFE), "-i", str(src), "-o", str(outd), "-n", str(n), "-m", str(RIFE.parent / "rife-v4.6"), "-f", "%06d.png", "-g", "0"], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"rife failed: {r.stderr[-600:]}")
        frames = sorted(outd.glob("*.png"))[1:-1]                                   # the bridging ones, not the two sources
        dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i, f in enumerate(frames):
            p = dest / f"weld{i}.png"
            shutil.copy2(f, p)
            out.append(p)
        return out


def sheet(cells: list[tuple[Path, str]], path: Path, cols: int = 6, cell: int = 256) -> None:
    rows = (len(cells) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell // 16 * 9 + 18)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, (p, label) in enumerate(cells):
        th = Image.open(p).convert("RGB"); th.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell // 16 * 9 + 18)
        im.paste(th, (x, y))
        d.text((x + 2, y + cell // 16 * 9 + 2), label[:40], fill=(220, 220, 220))
    im.save(path, quality=88)


def run_chain(e: Engine, fs: FaceSim, name: str, method: str, segments: int) -> dict:
    sp = SPEC[method]
    start_png, prompts = CHAINS[name]
    size = (sp["w"] // 4, sp["h"] // 4)
    hero = largest_face(fs, BENCH / start_png)
    start_name = e.upload(BENCH / start_png)
    seg_frames: list[list[Path]] = []
    execs: list[float] = []
    lead_name = None
    for k in range(segments):
        prompt = prompts[min(k, len(prompts) - 1)]
        prefix = f"e17/{name}_{method}_s{k + 1}"
        seg_sp = SPEC[sp["first"]] if (k == 0 and sp.get("first")) else sp
        if method == "ltx_guide" or (method == "wan_ltx" and k > 0):
            g, node = ltx_extended_graph(prompt, start_name, lead_name, seg_sp, SEED + k, prefix)
        else:
            g, node = wan_graph(prompt, start_name, seg_sp, SEED + k, prefix)
        h, wall, exec_s = e.run(g, timeout=3600)
        frames = download_frames(e, h, node, OUT / f"{name}_{method}_s{k + 1}")
        execs.append(round(exec_s, 1))
        seg_frames.append(frames)
        log(f"  {name} {method} segment {k + 1}: {len(frames)} frames in {exec_s:.0f} s")
        encode(frames, OUT / f"{name}_{method}_s{k + 1}.mp4", seg_sp["fps"], seg_sp["w"], seg_sp["h"])
        # the next segment starts on this one's last frame; ltx_guide (and the hybrid) also pins its last LEAD frames
        start_name = e.upload(frames[-1])
        if method in ("ltx_guide", "wan_ltx"):
            lead_mp4 = OUT / f"{name}_{method}_s{k + 1}_lead.mp4"
            encode(frames[-LEAD:], lead_mp4, seg_sp["fps"], seg_sp["w"], seg_sp["h"])
            lead_name = e.upload(lead_mp4)
    # the chain, the seams and the scores
    joins = []
    chain: list[Path] = list(seg_frames[0])
    cells: list[tuple[Path, str]] = [(seg_frames[0][0], "chain start")]
    for k in range(1, segments):
        prev, nxt = seg_frames[k - 1], seg_frames[k]
        w_prev = within(prev, size)
        if method in ("ltx_guide", "wan_ltx"):
            pinned = diff(grey(prev[-1], size), grey(nxt[LEAD - 1], size))            # the last lead-in frame should be the previous last frame
            seam = diff(grey(nxt[LEAD - 1], size), grey(nxt[LEAD], size))             # the first generated frame after the lead-in
            joins.append({"k": k, "seam": round(seam, 2), "within": round(w_prev, 2), "ratio": round(seam / max(1e-6, w_prev), 2), "pinned_diff": round(pinned, 2)})
            chain += nxt[LEAD:]
            cells += [(prev[-2], f"s{k} last-1"), (prev[-1], f"s{k} last"), (nxt[LEAD - 1], f"s{k + 1} lead end"), (nxt[LEAD], f"s{k + 1} first new"), (nxt[LEAD + 1], f"s{k + 1} +1"), (nxt[LEAD + 2], f"s{k + 1} +2")]
        else:
            raw = diff(grey(prev[-1], size), grey(nxt[1], size))                      # frame 0 of the next is the previous last frame itself
            bridges = weld(prev[-1], nxt[1], OUT / f"{name}_{method}_weld{k}")
            seq = [prev[-1], *bridges, nxt[1]]
            gs = [grey(p, size) for p in seq]
            welded = max(diff(gs[i], gs[i + 1]) for i in range(len(gs) - 1))
            joins.append({"k": k, "seam": round(welded, 2), "raw_cut": round(raw, 2), "within": round(w_prev, 2), "ratio": round(welded / max(1e-6, w_prev), 2),
                          "raw_ratio": round(raw / max(1e-6, w_prev), 2)})
            chain += bridges + nxt[1:]
            cells += [(prev[-2], f"s{k} last-1"), (prev[-1], f"s{k} last"), *[(b, f"weld {i + 1}") for i, b in enumerate(bridges)], (nxt[1], f"s{k + 1} 1"), (nxt[2], f"s{k + 1} 2")]
    cells.append((chain[-1], "chain end"))
    encode(chain, OUT / f"{name}_{method}_chain.mp4", sp["fps"], sp["w"], sp["h"])   # a Wan first segment is 832×480: encode() resizes
    sheet(cells, OUT / f"{name}_{method}_joins.jpg")
    first, last = largest_face(fs, chain[0]), largest_face(fs, chain[-1])
    sim_first = round(fs.similarity(hero, first), 3) if hero is not None and first is not None else None
    sim_last = round(fs.similarity(hero, last), 3) if hero is not None and last is not None else None
    worst = max((j["ratio"] for j in joins), default=0.0)
    time_ratio = round(max(execs[1:]) / execs[0], 2) if len(execs) > 1 and execs[0] else None
    row = {"chain": name, "method": method, "segments": segments, "frames": len(chain), "fps": sp["fps"], "exec_s": execs, "time_ratio": time_ratio, "joins": joins,
           "facesim_first": sim_first, "facesim_last": sim_last,
           "bars": {"seam": worst <= BARS["seam"], "facesim": sim_first is not None and sim_last is not None and min(sim_first, sim_last) >= BARS["facesim"],
                    "time": time_ratio is not None and time_ratio <= BARS["time"] if method == "ltx_guide" else None},   # the hybrid's first segment is Wan: no time ratio
           "stamp": time.strftime("%Y-%m-%d %H:%M")}
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    log(f"  {name} {method}: seam ratios {[j['ratio'] for j in joins]} (bar ≤ {BARS['seam']}), facesim {sim_first} → {sim_last}, time ratio {time_ratio}")
    return row


def face_at(fs: FaceSim, hero, frames: list[Path], idx: int, back: int = 24) -> tuple[float | None, int | None]:
    """FaceSim to the hero at `idx`, searching back up to `back` frames for one that holds a face."""
    for i in range(idx, max(-1, idx - back - 1), -1):
        emb = largest_face(fs, frames[i])
        if emb is not None and hero is not None:
            return round(fs.similarity(hero, emb), 3), i
    return None, None


def rescore() -> int:
    """FaceSim at the chain's last frame *with a face* (searching back up to 24 frames): a character who turns or walks away leaves the last
    frame faceless, which says nothing about drift; and the curve per segment (first and last frame with a face), so drift shows where it
    starts. Reads the saved frames, writes results_rescored.jsonl beside results.jsonl."""
    fs = FaceSim(MODELS)
    rows = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        if "error" in r:
            out.append(r)
            continue
        name, method = r["chain"], r["method"]
        hero = largest_face(fs, BENCH / CHAINS[name][0])
        segs = [d for d in sorted(OUT.glob(f"{name}_{method}_s*")) if d.is_dir() and not d.name.endswith("_lead")]
        curve = []
        for d in segs:
            frames = sorted(d.glob("*.png"))
            if not frames:
                continue
            s_first, i_first = face_at(fs, hero, frames, min(len(frames) - 1, LEAD + 1) if method == "ltx_guide" and d != segs[0] else 0, back=0)
            if s_first is None:
                s_first, i_first = face_at(fs, hero, frames, min(len(frames) - 1, 24), back=24)
            s_last, i_last = face_at(fs, hero, frames, len(frames) - 1, back=24)
            curve.append({"segment": d.name, "first": s_first, "first_frame": i_first, "last": s_last, "last_frame": i_last})
        last = curve[-1]["last"] if curve else None
        r2 = {**r, "facesim_last": last, "facesim_curve": curve}
        r2["bars"] = {**r["bars"], "facesim": r.get("facesim_first") is not None and last is not None and min(r["facesim_first"], last) >= BARS["facesim"]}
        out.append(r2)
        log(f"  {name} {method}: first {r.get('facesim_first')} → last-with-face {last}; per segment " + ", ".join(f"{c['first']}→{c['last']}" for c in curve))
    (OUT / "results_rescored.jsonl").write_text("".join(json.dumps(x) + chr(10) for x in out), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rescore", action="store_true", help="recompute the end-of-chain FaceSim on the last frame with a face, from the saved frames")
    ap.add_argument("--methods", default="ltx_guide,wan_weld")
    ap.add_argument("--chains", default="alley,cabin,rooftop")
    ap.add_argument("--segments", type=int, default=3)
    a = ap.parse_args()
    if a.rescore:
        return rescore()
    if engine_listening():
        print("an engine is already listening on 8188 — stop it (scripts/engine-stop.ps1): this spike starts its own and reads its log"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    eng_log = (OUT / "engine.log").open("a", encoding="utf-8")
    eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(REPO / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
    rows = []
    try:
        t0 = time.time()
        while time.time() - t0 < 180 and not engine_listening():
            time.sleep(1.0)
        if not engine_listening():
            print("the engine did not come up"); return 1
        e = Engine(ENGINE)
        fs = FaceSim(MODELS)
        for method in [m for m in a.methods.split(",") if m]:
            for name in [c for c in a.chains.split(",") if c]:
                log(f"chain {name} · {method}")
                try:
                    rows.append(run_chain(e, fs, name, method, a.segments))
                except Exception as ex:  # noqa: BLE001 — the other chains still run
                    log(f"  FAILED {name} {method}: {type(ex).__name__}: {str(ex)[:300]}")
                    with RESULTS.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"chain": name, "method": method, "error": f"{type(ex).__name__}: {str(ex)[:300]}", "stamp": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
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
    print(json.dumps([{k: v for k, v in r.items() if k != "joins"} for r in rows], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
