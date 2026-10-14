"""E16 — ai-toolkit on torch 2.13 ROCm 10 with FLUX.2 Klein base (18 §2, D86): does a character LoRA train on the RX 9070 XT, and does it
load on the distilled Klein that Generate runs?

Parts (`--part refs,train,load`; `all` = the three in order):
  refs   the dataset the product will use: loom2's own orchestrator (a temp state, port 8775) → the hero (bench/angles/07.jpg) → the
         profile Mara → Expand `full` (36 cells on D78's clay model, Klein 9B) → every candidate as a PNG under out/e16/refs/ with the caption
         "<trigger>, <cell sentence>" (the hero with the stub); refs.json records the cells. The orchestrator and its engine are stopped after.
  train  trainers/.venv runs trainers/ai-toolkit/run.py on a generated yaml (loom P2's exercised shape: rank / alpha 16, qfloat8 Quanto on
         the transformer and the encoder, low_vram, gradient checkpointing, AdamW 1e-4, batch 1, sampling off) for --steps on --base 4b | 9b
         at --res; the log is a file, progress is parsed from it, VRAM is sampled from Windows' GPU adapter counter every 5 s; --kill-at N
         kills the trainer at step ≥ N and relaunches it on the same yaml (the resume bar). Results: out/e16/train_<tag>/… and results.jsonl.
  load   the adapter copied to <models_root>/loras/e16/, the engine started standalone (scripts/engine-start.ps1), loom2's Klein t2i graph +
         LoraLoaderModelOnly on klein-4b (4 steps) and klein-base-4b (20 steps): 8 coverage prompts × {lora 1.0, lora 0.8, trigger without
         the LoRA, the stub without the LoRA}; FaceSim (ArcFace) of every result against the hero, the refs' own band for scale; the engine
         log's "lora key not loaded" count; contact sheets; results.jsonl. The engine is stopped after.

Bars (18 §2): E16b peak VRAM ≤ 15 GB and ≤ 2.0 s/it with a resume; E16c 0 unmatched keys, FaceSim ≥ 0.30 with the LoRA and ≥ the
trigger-only control + 0.20. Needs port 8188 free (no engine running) and the trainer venv (scripts/trainer-setup.ps1).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e16_klein_lora.py --part refs
  orchestrator/.venv/Scripts/python.exe engine/spikes/e16_klein_lora.py --part train --base 4b --steps 1000 --kill-at 300
  orchestrator/.venv/Scripts/python.exe engine/spikes/e16_klein_lora.py --part load --tag 4b_1000
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e12_angles import Engine, flux2_loaders, klein_te  # noqa: E402
from loom2.story import cell_sentence, preset_cells  # noqa: E402
from loom2.tools.facesim import FaceSim  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e16"
RESULTS = OUT / "results.jsonl"
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
HF_HOME = os.environ.get("HF_HOME", "F:/HF_HOME")
TRAINER_PY = ROOT / "trainers" / ".venv" / "Scripts" / "python.exe"
AITK = ROOT / "trainers" / "ai-toolkit"
HERO = ROOT / "bench" / "angles" / "07.jpg"
STUB = "Mara, a wiry courier in a long grey coat with a red scarf"
TRIGGER = "mara_e16"
PORT, TOKEN, ENGINE = 8775, "e16", "127.0.0.1:8188"
BASES = {"4b": {"arch": "flux2_klein_4b", "file": "flux-2-klein-base-4b.safetensors", "te": "Qwen/Qwen3-4B"},
         "9b": {"arch": "flux2_klein_9b", "file": "flux-2-klein-base-9b.safetensors", "te": "Qwen/Qwen3-8B"}}
BARS = {"vram_gb": 15.0, "s_per_it": 2.0, "facesim": 0.30, "over_control": 0.20}
W, H, SEED = 1024, 576, 20261014
# eight coverage cells, the vocabulary the captions use (17 §3b)
CHECK_CELLS = [{"shot": "close-up", "angle": "front", "expression": "neutral"}, {"shot": "medium", "angle": "three-quarter left", "expression": "smiling"},
               {"shot": "full body", "angle": "profile right", "expression": "neutral"}, {"shot": "close-up", "angle": "three-quarter right", "expression": "angry"},
               {"shot": "medium", "angle": "front", "expression": "surprised"}, {"shot": "cowboy", "angle": "back", "expression": "neutral"},
               {"shot": "close-up", "angle": "profile left", "expression": "sad"}, {"shot": "medium", "angle": "three-quarter left", "expression": "neutral"}]


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def record(row: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def engine_listening() -> bool:
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def kill_engine_on_8188() -> None:
    pid = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 8188 -State Listen | Select-Object -First 1).OwningProcess"],
                         capture_output=True, text=True).stdout.strip()
    if pid.isdigit():
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
        log(f"stopped the engine (pid {pid})")


# ---------------------------------------------------------------- refs: the dataset through loom2's own orchestrator
def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def wait_jobs(ids: list[str], timeout_s: float = 3600) -> dict[str, dict]:
    t0, last_done, t_prog = time.time(), -1, time.time()
    while time.time() - t0 < timeout_s:
        jobs = {j["id"]: j for j in api("GET", "/jobs")["items"] if j["id"] in ids}
        done = [j for j in jobs.values() if j["status"] in ("done", "failed", "cancelled")]
        if len(done) != last_done:
            last_done, t_prog = len(done), time.time()
            log(f"  jobs {len(done)}/{len(ids)} finished")
        if len(done) >= len(ids):
            return jobs
        if time.time() - t_prog > 900:
            raise TimeoutError("no job progress for 15 min")
        time.sleep(2.0)
    raise TimeoutError("jobs")


def refs(preset: str, reuse: Path | None = None) -> None:
    if engine_listening():
        raise SystemExit("an engine is listening on 8188: stop it (scripts/engine-stop.ps1) — the orchestrator launches its own")
    refs_dir = OUT / "refs"
    if refs_dir.is_dir():
        shutil.rmtree(refs_dir)
    refs_dir.mkdir(parents=True)
    tmp = reuse or Path(tempfile.mkdtemp(prefix="loom2-e16-"))
    from loom2.config import AppState
    if reuse is None:
        AppState(tmp / "state").update_settings({"models_root": str(MODELS), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    argv = [sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")] + (["--project", str(tmp / "proj")] if reuse else [])
    orch = subprocess.Popen(argv, cwd=str(ROOT / "orchestrator"), env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    log(f"orchestrator on {PORT}, state {tmp} ({'reused' if reuse else 'new'})")
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        caps = api("GET", "/capabilities")["story"]
        t_exp = time.time()
        if reuse is None:
            api("POST", "/project", {"path": str(tmp / "proj"), "name": "E16", "size_cap_gb": 40})
            hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
            log(f"Expand's model: {caps['model_id']} ({caps['health']}), preset {preset} = {caps['presets'][preset]['cells']} cells")
            p = api("POST", "/story/profiles", {"name": "Mara", "cls": "character", "hero_asset_id": hero, "stub": STUB})
            pid, vid = p["id"], p["versions"][0]["id"]
            r = api("POST", f"/story/profiles/{pid}/expand", {"preset": preset, "seeds_per_cell": 1, "tier": "draft"})
            log(f"Expand queued {len(r['job_ids'])} jobs")
            jobs = wait_jobs(r["job_ids"])
            walls = sorted(j.get("wall_s") or 0 for j in jobs.values())
            group_id = r["group_id"]
        else:
            p = api("GET", "/story/profiles")["items"][0]
            pid, vid = p["id"], p["versions"][0]["id"]
            hero, group_id = p["versions"][0]["hero_asset_id"], p["versions"][0]["candidates_group_id"]
            walls = sorted(j.get("wall_s") or 0 for j in api("GET", "/jobs")["items"] if j["status"] == "done" and j.get("origin", {}).get("surface") == "expand")
        cand = api("GET", f"/groups/{group_id}")
        cands = sorted(cand["assets"].values(), key=lambda x: x["created_at"])
        log(f"{len(cands)} candidates in {time.time() - t_exp:.0f} s (job walls min / median / max {walls[0]:.1f} / {walls[len(walls) // 2]:.1f} / {walls[-1]:.1f})")
        api("POST", f"/story/profiles/{pid}/versions/{vid}/curate", {"asset_ids": [x["id"] for x in cands], "verdict": "keep"})
        rows = []
        hero_png = refs_dir / "00_hero.png"
        Image.open(HERO).convert("RGB").save(hero_png)
        (refs_dir / "00_hero.txt").write_text(f"{TRIGGER}, {STUB.split(',', 1)[1].strip()}", encoding="utf-8")
        rows.append({"file": hero_png.name, "asset_id": hero, "cell": None})
        for i, x in enumerate(cands, 1):
            cell = x["params"].get("coverage_cell") or {}
            name = f"{i:02d}_{cell.get('shot', 'x').replace(' ', '-')}_{cell.get('angle', 'x').replace(' ', '-')}_{cell.get('expression', 'x')}"
            png = refs_dir / f"{name}.png"
            Image.open(io.BytesIO(api("GET", f"/assets/{x['id']}/file", raw=True))).convert("RGB").save(png)
            (refs_dir / f"{name}.txt").write_text(f"{TRIGGER}, {cell_sentence(cell)}", encoding="utf-8")
            rows.append({"file": png.name, "asset_id": x["id"], "cell": cell, "model_id": x["model_id"], "w": x["w"], "h": x["h"]})
        (OUT / "refs.json").write_text(json.dumps({"trigger": TRIGGER, "stub": STUB, "hero": str(HERO), "preset": preset, "model_id": caps["model_id"], "refs": rows}, indent=1), encoding="utf-8")
        record({"part": "refs", "preset": preset, "cells": len(cands), "expand_wall_s": round(time.time() - t_exp, 1), "walls": walls, "model_id": caps["model_id"], "stamp": time.strftime("%Y-%m-%d %H:%M")})
        log(f"refs written: {len(rows)} files under {refs_dir}")
    finally:
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=60)
        except Exception:
            orch.kill()
        orch_log.close()
        if engine_listening():
            kill_engine_on_8188()


# ---------------------------------------------------------------- train
class VramSampler(threading.Thread):
    """Windows' GPU adapter counter (dedicated usage, bytes), the largest adapter, every `every` seconds — no CUDA context of its own."""

    def __init__(self, every: float = 5.0) -> None:
        super().__init__(daemon=True)
        self.every, self.peak, self.samples, self._stop = every, 0, [], threading.Event()

    def run(self) -> None:
        cmd = "((Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | Sort-Object CookedValue -Descending | Select-Object -First 1).CookedValue"
        while not self._stop.is_set():
            try:
                v = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=20).stdout.strip()
                b = int(float(v)) if v else 0
                self.samples.append((time.time(), b))
                self.peak = max(self.peak, b)
            except Exception:
                pass
            self._stop.wait(self.every)

    def stop(self) -> None:
        self._stop.set()


def vae_file() -> str:
    """The Flux.2 autoencoder as ai-toolkit reads it (BFL key names): loom2's own `vae/flux2-vae.safetensors` is the diffusers-named repack
    (`decoder.conv_norm_out…`, 251 tensors) its loader does not accept, so E16 takes the hub's `ae.safetensors` (0.3 GB, cached in HF_HOME;
    the same VAE the Apache Klein repos ship). LT2 remaps loom2's file instead of carrying two copies."""
    from huggingface_hub import hf_hub_download
    os.environ.setdefault("HF_HOME", HF_HOME)
    return hf_hub_download("ai-toolkit/flux2_vae", "ae.safetensors")


STEP_RE = re.compile(r"(\d+)/(\d+) \[")


def train_config(tag: str, base: str, steps: int, res: int, rank: int, lr: float, offload: bool = False) -> dict:
    b = BASES[base]
    run_dir = OUT / f"train_{tag}"
    return {"job": "extension", "config": {"name": tag, "process": [{
        "type": "diffusion_trainer", "training_folder": str(run_dir), "sqlite_db_path": str(run_dir / "aitk_db.sqlite"), "device": "cuda:0",
        "trigger_word": TRIGGER, "performance_log_every": 50,
        "network": {"type": "lora", "linear": rank, "linear_alpha": rank},
        "save": {"dtype": "bf16", "save_every": 250, "max_step_saves_to_keep": 2, "push_to_hub": False},
        "datasets": [{"folder_path": str(OUT / "refs"), "caption_ext": "txt", "caption_dropout_rate": 0.05, "shuffle_tokens": False, "cache_latents_to_disk": True,
                      "resolution": [res], "num_repeats": 1}],
        "train": {"batch_size": 1, "steps": steps, "gradient_accumulation": 1, "train_unet": True, "train_text_encoder": False, "gradient_checkpointing": True,
                  "noise_scheduler": "flowmatch", "optimizer": "adamw", "optimizer_params": {"weight_decay": 0.0001}, "lr": lr, "timestep_type": "weighted",
                  "content_or_style": "balanced", "unload_text_encoder": False, "cache_text_embeddings": False, "ema_config": {"use_ema": False, "ema_decay": 0.99},
                  "skip_first_sample": True, "force_first_sample": False, "disable_sampling": True, "dtype": "bf16"},
        "logging": {"log_every": 10, "use_ui_logger": False},
        "model": {"name_or_path": str(MODELS / "diffusion_models"), "arch": b["arch"], "vae_path": vae_file(),
                  "quantize": True, "qtype": "qfloat8", "quantize_te": True, "qtype_te": "qfloat8", "low_vram": True, "layer_offloading": offload, "compile": False,
                  "model_kwargs": {"match_target_res": False}},
        "sample": {"sampler": "flowmatch", "sample_every": 100000, "width": res, "height": res, "prompts": [f"{TRIGGER}, close-up, front, neutral expression"],
                   "neg": "", "seed": 42, "walk_seed": False, "guidance_scale": 1.0, "sample_steps": 4},
    }]}, "meta": {"name": "[name]", "version": "e16"}}


def run_trainer(yaml_path: Path, log_path: Path, kill_at: int | None, total: int) -> dict:
    """One launch of run.py; returns {exit, wall_s, first_step, last_step, step_times} — `kill_at` ends it at that step."""
    env = {**os.environ, "HF_HOME": HF_HOME, "HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "DISABLE_TELEMETRY": "1"}
    with log_path.open("a", encoding="utf-8") as lf:
        lf.write(f"\n==== launch {time.strftime('%Y-%m-%d %H:%M:%S')} kill_at={kill_at}\n"); lf.flush()
        proc = subprocess.Popen([str(TRAINER_PY), "run.py", str(yaml_path)], cwd=str(AITK), env=env, stdout=lf, stderr=subprocess.STDOUT, text=True)
        t0, pos, first, last, times, killed = time.time(), log_path.stat().st_size, None, None, [], False
        while proc.poll() is None:
            time.sleep(2.0)
            try:
                with log_path.open("rb") as rf:
                    rf.seek(pos)
                    chunk = rf.read()
                pos += len(chunk)
            except OSError:
                chunk = b""
            for m in STEP_RE.finditer(chunk.decode("utf-8", "replace")):
                step = int(m.group(1))
                if first is None:
                    first = step
                if step != last:
                    last = step
                    times.append((time.time(), step))
            if kill_at and last is not None and last >= kill_at and not killed:
                killed = True
                log(f"  killing the trainer at step {last} (pid {proc.pid})")
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return {"exit": proc.returncode, "wall_s": round(time.time() - t0, 1), "first_step": first, "last_step": last, "killed": killed, "step_times": times}


def s_per_it(times: list[tuple[float, int]]) -> float | None:
    """Seconds per step over the steady part (after the first 10 % of the launch's steps)."""
    if len(times) < 10:
        return None
    k = max(1, len(times) // 10)
    (t0, s0), (t1, s1) = times[k], times[-1]
    return round((t1 - t0) / max(1, s1 - s0), 3) if s1 > s0 else None


def train(tag: str, base: str, steps: int, res: int, rank: int, lr: float, kill_at: int | None, offload: bool = False) -> None:
    if engine_listening():
        raise SystemExit("an engine is listening on 8188: stop it first — training needs the whole card")
    if not TRAINER_PY.is_file():
        raise SystemExit(f"trainer venv missing: {TRAINER_PY} (scripts/trainer-setup.ps1)")
    if not (OUT / "refs.json").is_file():
        raise SystemExit("no refs: run --part refs first")
    cfg = train_config(tag, base, steps, res, rank, lr, offload)
    run_dir = OUT / f"train_{tag}"
    if run_dir.is_dir():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    yaml_path = OUT / f"train_{tag}.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    log_path = OUT / f"train_{tag}.log"
    n_refs = len(list((OUT / "refs").glob("*.png")))
    log(f"train {tag}: {BASES[base]['arch']} · {n_refs} refs at {res} · rank {rank} · {steps} steps · lr {lr} · log {log_path.name}")
    sampler = VramSampler(); sampler.start()
    launches = []
    t_all = time.time()
    r = run_trainer(yaml_path, log_path, kill_at, steps)
    launches.append(r)
    log(f"  launch 1: exit {r['exit']} after {r['wall_s']} s, steps {r['first_step']}→{r['last_step']}, {s_per_it(r['step_times'])} s/it")
    if r["killed"]:
        time.sleep(5)
        r2 = run_trainer(yaml_path, log_path, None, steps)
        launches.append(r2)
        log(f"  launch 2 (resume): exit {r2['exit']} after {r2['wall_s']} s, steps {r2['first_step']}→{r2['last_step']}, {s_per_it(r2['step_times'])} s/it")
    sampler.stop()
    final = launches[-1]
    adapter = run_dir / tag / f"{tag}.safetensors"
    ok_adapter = adapter.is_file()
    text = log_path.read_text(encoding="utf-8", errors="replace")
    # the resume evidence is ai-toolkit's own line ("RESUMING FROM <step save>", "Found step N in metadata") in the second launch's log;
    # tqdm prints a 0/N bar before the first update, so the first parsed step is not it
    second = text.split("==== launch")[2] if text.count("==== launch") >= 2 else ""
    m_res = re.search(r"Found step (\d+) in metadata", second)
    resumed = "RESUMING FROM" in second and m_res is not None
    resume_step = int(m_res.group(1)) if m_res else None
    peak_gb = round(sampler.peak / 2**30, 2)
    rates = [s_per_it(l["step_times"]) for l in launches]
    rate = min([x for x in rates if x] or [0]) or None
    row = {"part": "train", "tag": tag, "base": base, "arch": BASES[base]["arch"], "refs": n_refs, "res": res, "rank": rank, "steps": steps, "lr": lr, "layer_offloading": offload,
           "launches": [{k: v for k, v in l.items() if k != "step_times"} for l in launches], "wall_s": round(time.time() - t_all, 1), "s_per_it": rate,
           "peak_vram_gb": peak_gb, "adapter": str(adapter) if ok_adapter else None, "adapter_sha256": sha256(adapter) if ok_adapter else None,
           "adapter_bytes": adapter.stat().st_size if ok_adapter else None, "resumed": resumed if kill_at else None, "resume_step": resume_step,
           "bars": {"vram": peak_gb <= BARS["vram_gb"], "rate": bool(rate) and rate <= BARS["s_per_it"], "finished": final["exit"] == 0 and ok_adapter,
                    "resume": (resumed if kill_at else None)},
           "errors": [ln.strip()[:300] for ln in text.split("==== launch")[-1].splitlines() if "Error" in ln or "error:" in ln.lower()][-5:],
           "stamp": time.strftime("%Y-%m-%d %H:%M")}
    record(row)
    print(json.dumps({k: v for k, v in row.items() if k not in ("launches",)}, indent=1))


# ---------------------------------------------------------------- load
def klein_graph(model: str, prompt: str, seed: int, lora: str | None, strength: float, prefix: str) -> dict:
    distilled = model == "klein-4b"
    g: dict = {}
    flux2_loaders(g, "flux-2-klein-4b.safetensors" if distilled else "flux-2-klein-base-4b.safetensors")
    g["2"] = klein_te("klein-4b")
    model_link = ["1", 0]
    if lora:
        g["4"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": lora, "strength_model": strength}}
        model_link = ["4", 0]
    g["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}}
    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": "" if distilled else "blurry, low quality, deformed, text, watermark", "clip": ["2", 0]}}
    g["7"] = {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}}
    g["8"] = {"class_type": "KSampler", "inputs": {"model": model_link, "seed": seed, "steps": 4 if distilled else 20, "cfg": 1.0 if distilled else 3.5,
                                                   "sampler_name": "euler", "scheduler": "simple", "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "denoise": 1.0}}
    g["9"] = {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}}
    g["10"] = {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefix}}
    return g


def largest_face(fs: FaceSim, img: Image.Image) -> np.ndarray | None:
    a = np.asarray(img.convert("RGB"))
    faces = fs.detect(a)
    if not faces:
        return None
    return fs.embed(a, max(faces, key=lambda x: x.area).kps)


def sheet(cells: list[tuple[Image.Image, str]], path: Path, cols: int = 8, cell: int = 224) -> None:
    rows = (len(cells) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 16)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, (img, label) in enumerate(cells):
        th = img.copy(); th.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        im.paste(th, (x, y))
        d.text((x + 2, y + cell + 2), label[:36], fill=(220, 220, 220))
    im.save(path, quality=88)


def load(tag: str, models: list[str], strengths: list[float]) -> None:
    rows_train = [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()] if RESULTS.is_file() else []
    tr = next((r for r in reversed(rows_train) if r.get("part") == "train" and r.get("tag") == tag and r.get("adapter")), None)
    if tr is None:
        raise SystemExit(f"no trained adapter for tag {tag} in results.jsonl")
    src = Path(tr["adapter"])
    dest_dir = MODELS / "loras" / "e16"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{tag}.safetensors"
    shutil.copy2(src, dest)
    lora_name = os.path.join("e16", f"{tag}.safetensors")       # ComfyUI lists a subfolder's files with the OS separator (E10: "flux1\ae.safetensors")
    if engine_listening():
        raise SystemExit("an engine is already listening on 8188 — stop it so this part's log holds the LoRA key report")
    eng_log = (OUT / f"engine_{tag}.log").open("w", encoding="utf-8")
    eng = subprocess.Popen(["pwsh", "-NoProfile", "-File", str(ROOT / "scripts" / "engine-start.ps1")], stdout=eng_log, stderr=subprocess.STDOUT, text=True)
    try:
        t0 = time.time()
        while time.time() - t0 < 180 and not engine_listening():
            time.sleep(1.0)
        if not engine_listening():
            raise SystemExit("the engine did not come up")
        e = Engine(ENGINE)
        fs = FaceSim(MODELS)
        hero_img = Image.open(HERO)
        hero_emb = largest_face(fs, hero_img)
        assert hero_emb is not None, "no face in the hero"
        # the refs' own band: every ref's largest face against the hero
        band = []
        for p in sorted((OUT / "refs").glob("*.png")):
            if p.name.startswith("00_"):
                continue
            emb = largest_face(fs, Image.open(p))
            if emb is not None:
                band.append(fs.similarity(hero_emb, emb))
        band_s = sorted(band)
        band_stats = {"n": len(band_s), "p10": round(band_s[len(band_s) // 10], 3), "median": round(band_s[len(band_s) // 2], 3), "p90": round(band_s[(len(band_s) * 9) // 10], 3)} if band_s else None
        log(f"refs' own band vs the hero: {band_stats}")
        variants = [(f"lora{str(s).replace('.', '')}", lora_name, s, f"{TRIGGER}, {{cell}}") for s in strengths] + [("trig", None, 0.0, f"{TRIGGER}, {{cell}}"), ("stub", None, 0.0, f"{STUB}, {{cell}}")]
        results = {}
        cells = []
        for model in models:
            for vname, lora, strength, tmpl in variants:
                sims, walls, imgs = [], [], []
                for i, c in enumerate(CHECK_CELLS):
                    prompt = tmpl.format(cell=cell_sentence(c))
                    prefix = f"e16/{tag}_{model}_{vname}_{i:02d}"
                    h, wall, exec_s = e.run(klein_graph(model, prompt, SEED + i, lora, strength, prefix))
                    img = e.image(h, "10")
                    img.save(OUT / f"load_{tag}_{model}_{vname}_{i:02d}.png")
                    emb = largest_face(fs, img)
                    sim = fs.similarity(hero_emb, emb) if emb is not None else None
                    sims.append(sim); walls.append(round(exec_s, 1)); imgs.append(img)
                    cells.append((img, f"{model[:9]} {vname} {i} {'' if sim is None else f'{sim:.2f}'}"))
                vals = [s for s in sims if s is not None]
                results[f"{model}/{vname}"] = {"mean": round(float(np.mean(vals)), 3) if vals else None, "min": round(min(vals), 3) if vals else None,
                                               "faces": len(vals), "sims": [None if s is None else round(s, 3) for s in sims], "exec_s": walls}
                log(f"  {model} {vname}: mean {results[f'{model}/{vname}']['mean']} over {len(vals)}/8 faces, exec {walls[0]}…{walls[-1]} s")
        sheet(cells, OUT / f"load_{tag}.jpg")
    finally:
        try:
            subprocess.run(["pwsh", "-NoProfile", "-File", str(ROOT / "scripts" / "engine-stop.ps1")], capture_output=True, timeout=60)
        except Exception:
            pass
        if engine_listening():
            kill_engine_on_8188()
        try:
            eng.wait(timeout=30)
        except Exception:
            eng.kill()
        eng_log.close()
    text = (OUT / f"engine_{tag}.log").read_text(encoding="utf-8", errors="replace")
    unmatched = len(re.findall(r"lora key not loaded", text))
    bars = {}
    for model in models:
        best = max((results[f"{model}/lora{str(s).replace('.', '')}"]["mean"] or 0) for s in strengths)
        ctrl = results[f"{model}/trig"]["mean"] or 0
        bars[model] = {"facesim": best >= BARS["facesim"], "over_control": best >= ctrl + BARS["over_control"], "best": round(best, 3), "control": round(ctrl, 3)}
    row = {"part": "load", "tag": tag, "lora_name": lora_name, "lora_sha256": sha256(dest), "models": models, "strengths": strengths, "unmatched_keys": unmatched,
           "refs_band": band_stats, "results": results, "bars": bars, "keys_ok": unmatched == 0, "stamp": time.strftime("%Y-%m-%d %H:%M")}
    record(row)
    print(json.dumps({k: v for k, v in row.items() if k != "results"}, indent=1))
    for k, v in results.items():
        print(f"  {k:26s} mean {v['mean']}  min {v['min']}  faces {v['faces']}/8  sims {v['sims']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", help="refs,train,load | all")
    ap.add_argument("--base", default="4b", choices=list(BASES))
    ap.add_argument("--steps", type=int, default=1000)
    ap.add_argument("--res", type=int, default=512)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--kill-at", type=int, default=None, help="kill the trainer at this step and relaunch (the resume bar)")
    ap.add_argument("--tag", default=None, help="run tag; default <base>_<steps>")
    ap.add_argument("--offload", action="store_true", help="ai-toolkit layer_offloading (the transformer's blocks paged from the CPU) — the 9B stretch")
    ap.add_argument("--preset", default="full")
    ap.add_argument("--reuse", default=None, help="a previous refs run's temp dir (loom2-e16-*): export its candidates again without a new Expand")
    ap.add_argument("--models", default="klein-4b,klein-base-4b")
    ap.add_argument("--strengths", default="1.0,0.8")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tag = a.tag or f"{a.base}_{a.steps}"
    parts = ["refs", "train", "load"] if a.part == "all" else [p for p in a.part.split(",") if p]
    if "refs" in parts:
        refs(a.preset, Path(a.reuse) if a.reuse else None)
    if "train" in parts:
        train(tag, a.base, a.steps, a.res, a.rank, a.lr, a.kill_at, a.offload)
    if "load" in parts:
        load(tag, [m for m in a.models.split(",") if m], [float(s) for s in a.strengths.split(",") if s])
    return 0


if __name__ == "__main__":
    sys.exit(main())
