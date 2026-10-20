"""Spike E27 (proto01_animate 03 §5.2a, D112): EffectCraft as the engine of the final shot's finishing.

The composition is the PS5 rig's final shot (engine/spikes/out/ps5, fin_*): its layers rebuilt in EffectCraft from D111's PNG sequences —
the projected plate; Stage's shadows as a Multiply layer softened by a Gaussian blur and limited by a mask; the stool (its beauty with an
alpha from its Stage depth); Ines and Mara, each her performance over her matte as a luma track matte, moved by her contact offset (D107).
832×480 at 16 fps, 81 frames. Built through EffectCraft's own commands over `effectcraft-cli mcp` (JSON-RPC over stdio, one headless
session) and saved as an .ecproj.

Measured (the tiers of 03 §5.2a, with what the headless session offers — `render_frame` scales by max_side; draft quality is not on it):
  T2  a full-size frame (max_side 0), cold and warm, CPU and GPU (Vulkan)              bar ≤ 150 ms
  T1  half (416) and quarter (208) frames while "scrubbing" (a frame each step)          bar ≥ 12 fps
  T3  playback: every frame of the shot in order, at half and full                      bar real time (16 fps here)
  busy  the CPU renderer while the app's queue runs a GPU job (D97: the server leaves the GPU)
  R2  `effectcraft-cli render` (Best, PNG sequence) on the CPU and the GPU against the T2 frames   bar ≤ 1/255
  R3  the composition as assembled against final_assembly's own frames                    bar ≤ 1/255
  app the desktop app opened on the shot (its control channel): time to the project, frames, a screenshot
  memory: the server's working set, and its dedicated GPU memory with --gpu

  orchestrator/.venv/Scripts/python.exe engine/spikes/e27_effectcraft.py comp|bench|busy|app|final
Outputs under engine/spikes/out/e27/ (git-ignored).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e27"
PS5 = ROOT / "engine" / "spikes" / "out" / "ps5"
EC = Path(r"F:\source\repos\effectcraft")
CLI = EC / "target" / "release" / "effectcraft-cli.exe"
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
FPS, W, H = 16, 832, 480


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save_state(s: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


class Mcp:
    """`effectcraft-cli mcp` over stdio: one JSON-RPC request per line, one reply per line."""
    def __init__(self, gpu: bool = False, project: Path | None = None, bridge: int | None = None, threads: int | None = None, priority: int = 0):
        if bridge:                                                             # the desktop app's control channel
            args = [str(CLI), "mcp", "--bridge", str(bridge)]
        else:
            args = [str(CLI), "mcp"] + (["--gpu"] if gpu else []) + (["--project", str(project)] if project else ["--empty"])
        env = {**os.environ, "WGPU_BACKEND": "vulkan"}                       # the survey: D3D12 cannot compile a kernel on Windows (#613)
        if threads:
            env["RAYON_NUM_THREADS"] = str(threads)                            # the renderer's pool
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8", bufsize=1,
                                  creationflags=priority)                      # 0x4000 below normal, 0x40 idle (Windows)
        self.n = 0
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "loom2-e27", "version": "0"}})

    def call(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"the server closed: {self.p.stderr.read()[-2000:]}")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg["result"]

    def tool(self, name: str, args: dict) -> dict | list:
        r = self.call("tools/call", {"name": name, "arguments": args})
        if r.get("isError"):
            raise RuntimeError(f"{name}: {json.dumps(r)[:1500]}")
        content = r.get("content") or []
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                return {"text": content[0]["text"]}
        return content

    def run(self, cid: str, params: dict | None = None) -> dict:
        return self.tool("command_run", {"id": cid, "params": params or {}})

    def frame(self, time_s: float, max_side: int) -> Image.Image:
        c = self.tool("render_frame", {"time": time_s, "max_side": max_side})
        img = next(x for x in c if x.get("type") == "image")
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGBA")

    def pid(self) -> int:
        return self.p.pid

    def close(self) -> None:
        try:
            self.p.stdin.close()
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def final_dir() -> Path:
    t = json.loads((PS5 / "timings.json").read_text(encoding="utf-8"))
    return PS5 / "project" / "finals" / t["final"], t


# ---- comp ------------------------------------------------------------------------------------------------------------------------------
def prepare_sequences() -> dict:
    """What EffectCraft imports — what *Make the final shot* would hand it (D112): the plate's frames as they are; the shadows as Stage's
    ratio (a grey image to Multiply); the stool as its beauty with the alpha from its Stage depth; each character's frames as they are
    and her alpha as a grey matte (her SAM 3 matte inside her figure's grown mask, softened, a nearer prop's cut baked in — the assembly's
    own rules, final_assembly), unmoved: her contact offset is the layer's position, for the author to drag. Also the stack's order (the
    assembly sorts every frame by depth; a composition has one order) and the assembly's own frames at 16 fps, the R3 reference."""
    from types import SimpleNamespace
    from loom2 import final_assembly as FA
    from loom2.finals import FinalStore
    d, t = final_dir()
    store = FinalStore(SimpleNamespace(path=PS5 / "project"))
    f = store.get(d.name)
    n = f.frames
    ref = OUT / "assembly"
    if len(list(ref.glob("*.png"))) != n:
        t0 = time.time()
        FA.assemble_frames(store, f, ref)
        log(f"the assembly's own frames in {time.time() - t0:.1f} s")
    seq = OUT / "seq"
    figs = [x.id for x in f.layers if x.kind == "figure"]
    props = [x.id for x in f.layers if x.kind == "prop"]
    for k in ["shadow", *props, *(f"{x}_matte" for x in figs)]:
        shutil.rmtree(seq / k, ignore_errors=True)
        (seq / k).mkdir(parents=True)
    pd = lambda lid, name: sorted((d / lid / name).glob("*.png"))   # noqa: E731
    bare_d, bare_c, shad = pd("plate", "depth"), pd("plate", "clay"), pd("shadows", "clay")
    offsets = {k: tuple(v) for k, v in t["assembly"]["offsets_px"].items()}
    orders = []
    for i in range(n):
        bd = FA.gray(bare_d[i])
        actors = np.zeros((H, W), bool)
        lay = {}
        for x in props:
            dep = FA.gray(pd(x, "depth")[i])
            m = np.abs(dep - bd) > FA.DEPTH_EPS
            actors |= m
            al = FA.soft(m.astype(np.float32), 0.7)
            lay[x] = {"kind": "prop", "alpha": al, "depth": np.where(m, dep, 0.0), "order": float(np.median(dep[m])) if m.any() else 0.0}
            rgba = np.dstack([FA.rgb(pd(x, "beauty")[i]), al * 255])
            Image.fromarray(np.clip(rgba + 0.5, 0, 255).astype(np.uint8), "RGBA").save(seq / x / f"{x}_{i:04d}.png")
        for x in figs:
            dep = FA.gray(pd(x, "depth")[i])
            sm = np.abs(dep - bd) > FA.DEPTH_EPS
            actors |= sm
            mt = FA.gray(pd(x, "matte")[i]) * FA.dilate(sm, FA.GROW)
            al = FA.soft(mt, 1.2) * FA.dilate(mt > 0.5, 3)
            dx, dy = offsets[x]
            grown = FA.max_filter(np.where(sm, dep, 0.0), 15)
            fill = float(np.median(dep[sm])) if sm.any() else 0.0
            lay[x] = {"kind": "figure", "alpha": np.clip(FA.shift(al, dx, dy), 0, 1), "depth": FA.shift(np.where(grown > 0, grown, fill), dx, dy), "order": fill}
        for x in figs:                                                          # a nearer prop's cut, then back to her own place
            al = lay[x]["alpha"]
            for p in props:
                nearer = (lay[p]["alpha"] > 0.05) & (lay[p]["depth"] > lay[x]["depth"] + 1.5 / 255)
                al = np.minimum(al, np.where(nearer, 1 - lay[p]["alpha"], 1.0))
            dx, dy = offsets[x]
            Image.fromarray((np.clip(FA.shift(al, -dx, -dy), 0, 1) * 255 + 0.5).astype(np.uint8)).save(seq / f"{x}_matte" / f"{x}_matte_{i:04d}.png")
        r = np.clip(FA.gray(shad[i]) / np.maximum(8 / 255, FA.gray(bare_c[i])), 0, 1)
        r[FA.dilate(actors, 2)] = 1.0
        Image.fromarray((r * 255 + 0.5).astype(np.uint8)).convert("RGB").save(seq / "shadow" / f"shadow_{i:04d}.png")
        orders.append(tuple(k for k, _ in sorted(lay.items(), key=lambda kv: kv[1]["order"])))
    stack = max(set(orders), key=orders.count)
    src = {"n": n, "plate": d / "plate" / "frames" / "0000.png", "shadow": seq / "shadow" / "shadow_0000.png", "offsets": offsets,
           "stack": list(stack), "stack_frames": orders.count(stack), "figs": figs, "props": props, "reference": ref}
    for x in props:
        src[x] = seq / x / f"{x}_0000.png"
    for x in figs:
        src[x] = d / x / "frames" / "0000.png"
        src[f"{x}_matte"] = seq / f"{x}_matte" / f"{x}_matte_0000.png"
    return src


def compare(a_: Image.Image, b_: Path | Image.Image) -> dict:
    a = np.asarray(a_.convert("RGB"), dtype=np.int16)
    b = np.asarray((Image.open(b_) if isinstance(b_, Path) else b_).convert("RGB"), dtype=np.int16)
    d = np.abs(a - b).max(axis=-1)
    return {"max": int(d.max()), "mean": round(float(d.mean()), 3), "p99": int(np.percentile(d, 99)), "over_2": round(float((d > 2).mean() * 100), 3)}


def comp(a: argparse.Namespace) -> int:
    """The composition as the assembly made it (R3: EffectCraft's frames against the assembly's), saved; then the hand finishing a
    compositor would add (the shadows softened and limited to the floor by a feathered mask, Mara nudged), saved as the bench's project."""
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src = prepare_sequences()
    s = load_state()
    s["prepare_s"] = round(time.time() - t0, 1)
    log(f"sequences ready in {s['prepare_s']} s; the stack {src['stack']} on {src['stack_frames']}/{src['n']} frames")
    keys = ["plate", "shadow", *src["props"], *(k for x in src["figs"] for k in (x, f"{x}_matte"))]
    if a.ext != "png":                                                          # the same frames in another still format (decode cost)
        for k in keys:
            d = OUT / f"seq_{a.ext}" / k
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
            for i, f in enumerate(sorted(Path(src[k]).parent.glob("*.png"))):
                Image.open(f).save(d / f"{k}_{i:04d}.{a.ext}")
            src[k] = d / f"{k}_0000.{a.ext}"
    m = Mcp()
    try:
        t0 = time.time()
        c = m.run("comp.new", {"name": "Final", "width": W, "height": H, "frameRate": FPS, "duration": src["n"] / FPS})
        items = {}
        for k in keys:
            r = m.run("file.import", {"paths": [str(src[k])], "sequence": True, "frameRate": FPS})
            if r.get("errors"):
                raise RuntimeError(f"import {k}: {r['errors']}")
            items[k] = r["items"][0]
        L = {}
        order = ["plate", "shadow"] + [k for x in src["stack"] for k in ((f"{x}_matte", x) if x in src["figs"] else (x,))]
        for k in order:                                                         # bottom first: each new layer goes on top
            L[k] = m.run("layer.addItem", {"item": items[k], "time": 0})["layer"]
            m.run("layer.rename", {"layer": L[k], "name": k})
        m.run("layer.setBlendMode", {"layers": [L["shadow"]], "mode": "Multiply"})
        for x in src["figs"]:
            m.run("layer.setTrackMatte", {"layer": L[x], "matte": L[f"{x}_matte"], "kind": "luma"})
            dx, dy = src["offsets"][x]
            m.tool("set_property", {"layer": L[x], "path": "transform/position", "value": [W / 2 + dx, H / 2 + dy]})
            m.tool("set_property", {"layer": L[f"{x}_matte"], "path": "transform/position", "value": [W / 2 + dx, H / 2 + dy]})
            m.run("layer.setParent", {"layers": [L[f"{x}_matte"]], "parent": L[x]})  # drag her and her matte follows
        build_s = round(time.time() - t0, 2)
        m.tool("save_project", {"path": str(OUT / ("assembled.ecproj" if a.ext == "png" else f"assembled_{a.ext}.ecproj"))})
        r3 = {}
        for i in (0, src["n"] // 2, src["n"] - 1):
            img = m.frame(i / FPS, 0)
            img.save(OUT / f"r3_ec_{i:04d}.png")
            r3[str(i)] = compare(img, src["reference"] / f"{i:06d}.png")
        log(f"R3 (EffectCraft vs the assembly, full size): {json.dumps(r3)}")
        # the hand finishing: the shadows softened, kept to the floor; Mara 4 px further left
        t0 = time.time()
        fx = m.tool("add_effect", {"layer": L["shadow"], "effect": "Gaussian Blur", "values": {"blurriness": 3}})
        m.run("layer.addMask", {"layer": L["shadow"], "shape": "rect", "rect": [0, int(H * 0.45), W, H - int(H * 0.45)]})
        m.run("layer.mask.set", {"layer": L["shadow"], "field": "feather", "value": 40})
        if "fig_m" in L:
            dx, dy = src["offsets"]["fig_m"]
            m.tool("set_property", {"layer": L["fig_m"], "path": "transform/position", "value": [W / 2 + dx - 4, H / 2 + dy]})
        finish_s = round(time.time() - t0, 2)
        proj = OUT / ("final.ecproj" if a.ext == "png" else f"final_{a.ext}.ecproj")
        m.tool("save_project", {"path": str(proj)})
        (OUT / "comp.json").write_text(json.dumps(m.tool("get_comp", {}), indent=1), encoding="utf-8")
        m.frame(1.0, 0).save(OUT / "finished_t1.png")
        s.setdefault("projects", {})[a.ext] = str(proj)
        if a.ext == "png":
            s.update({"comp": c, "items": items, "layers": L, "stack": src["stack"], "stack_frames": src["stack_frames"], "build_s": build_s,
                      "finish_s": finish_s, "effect": fx.get("path") if isinstance(fx, dict) else None, "r3": r3, "project": str(proj), "frames": src["n"]})
        else:
            s[f"r3_{a.ext}"] = r3
        save_state(s)
        log(f"built in {build_s} s, finished in {finish_s} s, saved: {proj}")
    finally:
        m.close()
    return 0


# ---- bench -----------------------------------------------------------------------------------------------------------------------------
def working_set(pid: int) -> dict:
    """The server's working set (MB) and, on the GPU, its dedicated GPU memory (MB) — Windows' own counters."""
    ps = (f"$p = Get-Process -Id {pid}; $ws = [math]::Round($p.WorkingSet64 / 1MB); "
          f"$g = (Get-Counter '\\GPU Process Memory(pid_{pid}*)\\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples | Measure-Object -Property CookedValue -Sum; "
          "\"$ws;$([math]::Round($g.Sum / 1MB))\"")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    try:
        ws, gpu = r.stdout.strip().split(";")
        return {"working_set_mb": int(float(ws)), "gpu_dedicated_mb": int(float(gpu or 0))}
    except Exception:
        return {"raw": r.stdout.strip()[-200:]}


def measure(gpu: bool, n: int, project: Path) -> dict:
    """Every test on a fresh server, so each frame it asks for is a cold one (the footage decoded, the layers rendered): T1/T2 scrubbing
    (every 4th frame), the same with the PNG kept on the server's side (`inline: false`: what the pipe and the client's decode cost), and
    T3 playback (every frame in order, then again)."""
    res: dict = {"gpu": gpu}
    stat = lambda ms: {"median": round(statistics.median(ms), 1), "p90": round(float(np.percentile(ms, 90)), 1), "fps": round(1000 / statistics.median(ms), 1)}  # noqa: E731
    for side, key in ((208, "quarter"), (416, "half"), (0, "full")):
        m = Mcp(gpu=gpu, project=project)
        try:
            t0 = time.perf_counter()
            m.frame(0.0, side)
            res[f"{key}_first_ms"] = round((time.perf_counter() - t0) * 1000, 1)       # the session's first frame
            ms, raw = [], []
            for i in range(4, n, 4):
                t0 = time.perf_counter()
                m.frame(i / FPS, side)
                ms.append((time.perf_counter() - t0) * 1000)
            for i in range(2, n, 4):
                t0 = time.perf_counter()
                m.tool("render_frame", {"time": i / FPS, "max_side": side, "inline": False})
                raw.append((time.perf_counter() - t0) * 1000)
            res[f"scrub_{key}"] = stat(ms)
            res[f"scrub_{key}_not_inline"] = stat(raw)
        finally:
            m.close()
        m = Mcp(gpu=gpu, project=project)
        try:
            for run in ("play", "play_again"):
                t0 = time.perf_counter()
                for i in range(n):
                    m.frame(i / FPS, side)
                el = time.perf_counter() - t0
                res[f"{run}_{key}"] = {"fps": round(n / el, 1), "seconds": round(el, 2)}
            if side == 0:
                res["memory_full"] = working_set(m.pid())
                m.frame(1.0, 0).save(OUT / f"t2_{'gpu' if gpu else 'cpu'}_t1.png")
        finally:
            m.close()
    return res


def bench(a: argparse.Namespace) -> int:
    s = load_state()
    n, key, proj = s["frames"], "bench" if a.ext == "png" else f"bench_{a.ext}", Path(s["projects"][a.ext])
    s[key] = {"cpu": measure(False, n, proj)}
    log(f"CPU ({a.ext}): {json.dumps(s[key]['cpu'])}")
    save_state(s)
    s[key]["gpu"] = measure(True, n, proj)
    log(f"GPU ({a.ext}): {json.dumps(s[key]['gpu'])}")
    save_state(s)
    return 0


# ---- busy: the CPU renderer while the queue runs a GPU job --------------------------------------------------------------------------
def busy(a: argparse.Namespace) -> int:
    """D97: while a generation runs, EffectCraft renders on its CPU. The app's default image model on its queue (a private orchestrator,
    the engine on 8188; FLUX.2 dev, 20 steps): three images alone, then the same job while the CPU renderer plays the shot over and over (half, then
    full) under each cap — its threads (RAYON_NUM_THREADS) and its process priority — then alone again (the drift); the job's time against
    its time alone, the frames' against bench's."""
    import e28_props as P
    P.OUT = OUT
    s = load_state()
    caps = [("all threads", None, 0), ("8 threads", 8, 0), ("4 threads", 4, 0), ("2 threads", 2, 0),
            ("all threads, below normal", None, 0x4000), ("all threads, idle", None, 0x40)]
    app = P.App(OUT / "app_project")
    res: dict = {"cores": os.cpu_count(), "runs": {}}
    try:
        recipe = {"kind": "t2i", "prompt_mode": "text", "prompt_text": "a quiet whitewashed room, soft daylight, cinematic still", "seeds": [1],
                  "width": 1024, "height": 576}
        seed = iter(range(2, 1000))
        def job(m: Mcp | None) -> tuple[float, list[tuple[int, float]]]:
            ms: list[tuple[int, float]] = []
            if m:
                m.frame(0.0, 416)
            t0 = time.time()
            ids = {j["id"] for j in P.api("POST", "/jobs", {"recipe": {**recipe, "seeds": [next(seed) for _ in range(3)]}})["jobs"]}  # a job per seed
            k = 0
            while time.time() - t0 < 1800:
                if (k % 16 == 0 or not m) and all(x["status"] in ("done", "failed", "cancelled") for x in P.api("GET", "/jobs")["items"] if x["id"] in ids):
                    break
                if not m:
                    time.sleep(0.5)
                    continue
                side = 416 if (k // s["frames"]) % 2 == 0 else 0
                t1 = time.perf_counter()
                m.frame((k % s["frames"]) / FPS, side)
                ms.append((side, (time.perf_counter() - t1) * 1000))
                k += 1
            return time.time() - t0, ms
        P.wait_job(P.api("POST", "/jobs", {"recipe": recipe})["jobs"][0]["id"])   # the model loaded, the prompt encoded
        res["alone_s"] = [round(job(None)[0], 1)]
        log(f"alone: {res['alone_s'][0]} s")
        for name, threads, prio in caps:
            m = Mcp(gpu=False, project=Path(s["project"]), threads=threads, priority=prio)
            try:
                el, ms = job(m)
            finally:
                m.close()
            half = [x for sd, x in ms if sd == 416]
            full = [x for sd, x in ms if sd == 0]
            res["runs"][name] = {"job_s": round(el, 1), "slowdown": round(el / res["alone_s"][0], 2), "frames": len(ms),
                                 "half_ms": round(statistics.median(half), 1) if half else None, "full_ms": round(statistics.median(full), 1) if full else None}
            log(f"{name}: {json.dumps(res['runs'][name])}")
            s["busy"] = res
            save_state(s)
        res["alone_s"].append(round(job(None)[0], 1))
        s["busy"] = res
        save_state(s)
        log(f"busy: {json.dumps(res)}")
    finally:
        app.close()
    return 0


# ---- app: the desktop app on the shot ------------------------------------------------------------------------------------------------
def app(a: argparse.Namespace) -> int:
    """*Finish in EffectCraft* as the author would see it: the desktop app opened on the shot's project (its control channel on 9877, the
    route PhotoCraft's and FilmCraft's agents use), timed until the project is loaded; frames through it; a screenshot of the window for
    the look; its memory; then quit."""
    s = load_state()
    exe = EC / "target" / "release" / "effectcraft.exe"
    t0 = time.time()
    proc = subprocess.Popen([str(exe), "--control", "9877", s["project"]], env={**os.environ, "WGPU_BACKEND": "vulkan"},
                            stdout=(OUT / "app.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)
    res: dict = {}
    m = None
    try:
        while time.time() - t0 < 120:
            try:
                m = Mcp(bridge=9877)
                p = m.tool("get_project", {})
                if str(p.get("path", "")).lower().endswith("final.ecproj"):
                    break
            except Exception:
                if m:
                    m.close()
                m = None
            time.sleep(0.25)
        res["open_s"] = round(time.time() - t0, 2)
        m.run("comp.open", {"comp": "Final"})
        for side, key in ((0, "full"), (416, "half")):
            ms = []
            for i in range(1, s["frames"], 8):
                t1 = time.perf_counter()
                m.frame(i / FPS, side)
                ms.append((time.perf_counter() - t1) * 1000)
            res[f"frame_{key}_ms"] = round(statistics.median(ms), 1)
        m.run("time.go", {"to": "start"})
        for _ in range(16):                                                   # 1 s in: both women in the room
            m.run("time.nextFrame", {})
        time.sleep(1.0)
        m.tool("screenshot", {"path": str(OUT / "app_window.png")})
        res["memory"] = working_set(proc.pid)
        log(f"app: {json.dumps(res)}")
        m.tool("control", {"method": "app.quit", "params": {"force": True}})
        proc.wait(timeout=30)
    finally:
        if m:
            m.close()
        if proc.poll() is None:
            proc.kill()
    s["app"] = res
    save_state(s)
    return 0


# ---- final: the CLI render against the preview --------------------------------------------------------------------------------------
def final(a: argparse.Namespace) -> int:
    """R2: the shot rendered by `effectcraft-cli render` (Best, a PNG sequence), on the CPU and on the GPU, against the session's frames
    (render_frame at full size) — the same engine, so it should be the same picture."""
    s = load_state()
    res: dict = {}
    for name, extra in (("cpu", []), ("gpu", ["--gpu"])):
        dst = OUT / f"r2_{name}"
        shutil.rmtree(dst, ignore_errors=True)
        dst.mkdir(parents=True)
        t0 = time.time()
        r = subprocess.run([str(CLI), "render", "--project", s["project"], "--comp", "Final", "--out", str(dst / "f_[####].png"), "--format", "png",
                            "--quality", "best", "--channels", "rgb", *extra], capture_output=True, text=True, timeout=3600,
                           env={**os.environ, "WGPU_BACKEND": "vulkan"})
        frames = sorted(dst.glob("*.png"))
        res[name] = {"seconds": round(time.time() - t0, 1), "frames": len(frames), "rc": r.returncode, "out": (r.stdout + r.stderr)[-300:]}
    cpu, gpu = sorted((OUT / "r2_cpu").glob("*.png")), sorted((OUT / "r2_gpu").glob("*.png"))
    if cpu:
        m = Mcp(gpu=False, project=Path(s["project"]))
        try:
            res["cli_vs_session"] = {str(i): compare(m.frame(i / FPS, 0), cpu[i]) for i in (0, len(cpu) // 2, len(cpu) - 1)}
        finally:
            m.close()
    if cpu and len(gpu) == len(cpu):
        res["gpu_vs_cpu"] = {str(i): compare(Image.open(gpu[i]), cpu[i]) for i in (0, len(cpu) // 2, len(cpu) - 1)}
    s["r2"] = res
    save_state(s)
    log(f"R2: {json.dumps(res)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["comp", "bench", "busy", "app", "final"])
    ap.add_argument("--ext", default="png", choices=["png", "tif"], help="comp/bench: the layers' still format")
    a = ap.parse_args()
    if not CLI.is_file():
        print(f"build EffectCraft first: cargo build --release -p effectcraft-cli in {EC}")
        return 2
    return {"comp": comp, "bench": bench, "busy": busy, "app": app, "final": final}[a.step](a)


if __name__ == "__main__":
    raise SystemExit(main())
