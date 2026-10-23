"""LT2 (18 §3c, D86): the `train_lora` job — ai-toolkit in its own venv (`trainers/.venv`, scripts/trainer-setup.ps1) on an album page
(D122: a Cast version's reference album, or any other), with the engine stopped for it (16 GB first); progress from the trainer's own lines, VRAM from Windows' GPU adapter
counter, a kill resumed by ai-toolkit's own checkpoints (the run dir is the job's, so a requeued job continues), the adapter promoted
into the project's registry (`story/loras/`, loras.py) and the version's `lora` + `trigger`. E16 (`engine/spikes/e16_klein_lora.py`,
journal 2026-10-14) is the record of the recipe: 1 000 steps of Klein base-4B on 37 refs at 512 → 1.07 s/it, 13.6 GB.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from PIL import Image

from .fsio import new_id, utc_now
from .loras import LoraRecord, LoraRegistry, model_base, publish
from .models import registry
from .recipes import TrainLora
from .story import StoryStore, cell_sentence, compose_sheet

if TYPE_CHECKING:
    from .config import Settings
    from .queue import JobQueue, JobRecord

MIN_REFS = 4                                        # 18 §3d: Train is offered from four references (ai-toolkit's floor is one)
STEP_RE = re.compile(r"(\d+)/(\d+) \[")
RATE_RE = re.compile(r"([\d.]+)(s/it|it/s)")
LOSS_RE = re.compile(r"loss: ([\d.e+-]+)")
RESUME_RE = re.compile(r"Found step (\d+) in metadata")
MAX_PX = 1024                                        # the dataset's PNGs: ≤ 1024 on the long side (the trainer buckets to `resolution`)


# ---- what the submission checks -----------------------------------------------------------------------------------------------------
def trainer_available(settings: "Settings") -> str | None:
    """None when the trainer can run; else the sentence (the venv, the pinned run.py)."""
    t = settings.trainer
    if not Path(t.python).is_file():
        return f"the trainer venv is missing ({t.python}) — run scripts/trainer-setup.ps1"
    if not Path(t.run).is_file():
        return f"ai-toolkit is missing ({t.run}) — git submodule update --init trainers/ai-toolkit, then scripts/trainer-setup.ps1"
    return None


def validate_train(q: "JobQueue", recipe: TrainLora) -> None:
    """B11 for a training job: the base, the variant, the weights, the venv, the version and its reference count — a sentence at submission."""
    spec = registry.get(recipe.model_id)
    if spec is None or spec.recipes.train is None:
        raise ValueError(f"{recipe.model_id!r} is not a trainable base (18 §2: Klein base-4B, base-9B with offloading)")
    variant = q.app.settings.variant
    if not registry.offered(spec, variant):
        raise ValueError(f"{spec.label} is not part of the {variant} variant (D26)")
    if q.roster.resolve(recipe.model_id).path is None:
        raise ValueError(f"the base weights of {spec.label} are not on disk")
    why = trainer_available(q.app.settings)
    if why:
        raise ValueError(why)
    if not recipe.trigger.strip():
        raise ValueError("a trigger word is required (the Cast tab makes one from the profile's name)")
    if q.groups is None:
        raise ValueError("no album store")
    _, _, gid = train_target(StoryStore(q.ws), q.groups, recipe)
    n = len(album_images(q.groups, gid))
    if n < MIN_REFS:
        raise ValueError(f"the album has {n} image{'s' if n != 1 else ''}; training needs at least {MIN_REFS}")


def train_target(store: StoryStore, groups: Any, recipe: TrainLora) -> tuple[Any, Any, str]:
    """D122: (profile, version, album) — the Cast version the adapter goes to (None, None for an album's own) and the album page trained
    on: the recipe's `group_id`, else the version's reference album."""
    p = v = None
    if recipe.profile_id:
        p = store.profile(recipe.profile_id)
        if p is None:
            raise ValueError(f"profile {recipe.profile_id!r} not found")
        try:
            v = p.version(recipe.version)
        except KeyError as e:
            raise ValueError(str(e))
    gid = recipe.group_id or (v.group_id if v is not None else None)
    if not gid:
        raise ValueError("a training job names its album (group_id) or a Cast version")
    if gid not in groups.groups:
        raise ValueError(f"album page {gid!r} not found")
    return p, v, gid


def album_images(groups: Any, group_id: str) -> list[dict[str, Any]]:
    """D122: what a job trains on — every image on the album page that is not in the Trash, in page order."""
    page = groups.page(group_id)
    return [a for a in page.get("assets", {}).values() if a.get("kind", "image") == "image" and not a.get("trashed_at")]


# ---- the dataset and the config ----------------------------------------------------------------------------------------------------
def set_dir(ws: Any, job_id: str) -> Path:
    return ws.temp_dir / "train" / job_id / "set"


def run_dir(ws: Any, job_id: str) -> Path:
    return ws.temp_dir / "train" / job_id / "out"


def caption_for(recipe: TrainLora, asset: dict[str, Any], stub: str, hero_id: str | None) -> str:
    """`<trigger>, <coverage sentence | the stub>[, <setting>]` — the cell of an Expand result, the stub for the hero and any plain image."""
    cell = (asset.get("params") or {}).get("coverage_cell")
    body = cell_sentence(cell) if isinstance(cell, dict) and cell.get("shot") else stub
    parts = [recipe.trigger.strip(), body.strip().rstrip(".")]
    if recipe.setting.strip():
        parts.append(recipe.setting.strip().rstrip("."))
    return ", ".join(x for x in parts if x)


def materialise(ws: Any, catalogue: Any, groups: Any, store: StoryStore, recipe: TrainLora, out: Path) -> dict[str, Any]:
    """The reference set as ai-toolkit reads it: `<n>_<asset>.png` + `.txt` captions under `out`; the same names every launch, so the
    trainer's latent cache in the folder stays valid across a resume."""
    p, v, gid = train_target(store, groups, recipe)
    stub = compose_sheet(v, name=p.name) if v is not None else ""      # D93 (B4): the version's sheet, composed; an album's own: the trigger alone
    refs = album_images(groups, gid)
    if len(refs) < MIN_REFS:
        raise ValueError(f"the album has {len(refs)} images; training needs at least {MIN_REFS}")
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.png"):
        stale.unlink()
    for stale in out.glob("*.txt"):
        stale.unlink()
    h = hashlib.sha256()
    ids = []
    for i, a in enumerate(refs, 1):
        rec = catalogue.get(a["id"])
        if rec is None:
            continue
        src = catalogue.abs_path(rec)
        name = f"{i:03d}_{a['id']}"
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > MAX_PX or im.height > MAX_PX:
                im.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
            im.save(out / f"{name}.png", "PNG")
        cap = caption_for(recipe, a, stub, v.hero_asset_id if v is not None else None)
        (out / f"{name}.txt").write_text(cap, encoding="utf-8")
        h.update(f"{name}\n{cap}\n".encode("utf-8"))
        ids.append(a["id"])
    return {"group_id": gid, "asset_ids": ids, "count": len(ids), "captions_sha256": h.hexdigest(), "setting": recipe.setting.strip(), "stub": stub}


def train_config(recipe: TrainLora, name: str, set_path: Path, out_path: Path, models_root: Path, vae: str, quantize: str) -> dict[str, Any]:
    """ai-toolkit's config in loom P2's exercised shape, with E16's Klein values: the base read from the models root's folder, the hub's
    autoencoder, qfloat8 Quanto on the transformer and the encoder, low_vram, gradient checkpointing, AdamW, sampling off (Generate samples)."""
    spec = registry.get(recipe.model_id)
    assert spec is not None and spec.recipes.train is not None
    tr = spec.recipes.train
    return {"job": "extension", "config": {"name": name, "process": [{
        "type": "diffusion_trainer", "training_folder": str(out_path), "sqlite_db_path": str(out_path / "aitk_db.sqlite"), "device": "cuda:0",
        "trigger_word": recipe.trigger, "performance_log_every": 50,
        "network": {"type": "lora", "linear": int(recipe.rank), "linear_alpha": int(recipe.rank)},
        "save": {"dtype": "bf16", "save_every": 250, "max_step_saves_to_keep": 2, "push_to_hub": False},
        "datasets": [{"folder_path": str(set_path), "caption_ext": "txt", "caption_dropout_rate": 0.05, "shuffle_tokens": False, "cache_latents_to_disk": True,
                      "resolution": [int(recipe.resolution)], "num_repeats": 1}],
        "train": {"batch_size": 1, "steps": int(recipe.steps), "gradient_accumulation": 1, "train_unet": True, "train_text_encoder": False,
                  "gradient_checkpointing": True, "noise_scheduler": "flowmatch", "optimizer": "adamw", "optimizer_params": {"weight_decay": 0.0001},
                  "lr": float(recipe.lr), "timestep_type": "weighted", "content_or_style": "balanced", "unload_text_encoder": False, "cache_text_embeddings": False,
                  "ema_config": {"use_ema": False, "ema_decay": 0.99}, "skip_first_sample": True, "force_first_sample": False, "disable_sampling": True, "dtype": "bf16"},
        "logging": {"log_every": 10, "use_ui_logger": False},
        "model": {"name_or_path": str(models_root / "diffusion_models"), "arch": tr.arch, "vae_path": vae, "quantize": True, "qtype": quantize,
                  "quantize_te": True, "qtype_te": quantize, "low_vram": True, "layer_offloading": bool(tr.offload), "compile": False,
                  "model_kwargs": {"match_target_res": False}},
        "sample": {"sampler": "flowmatch", "sample_every": 100000, "width": int(recipe.resolution), "height": int(recipe.resolution),
                   "prompts": [f"{recipe.trigger}, a close-up of the face, a front view, neutral expression"], "neg": "", "seed": int(recipe.seed),
                   "walk_seed": False, "guidance_scale": 1.0, "sample_steps": 4},
    }]}, "meta": {"name": "[name]", "version": "loom2-lt2"}}


def vae_path(settings: "Settings") -> str:
    """The Flux.2 autoencoder as ai-toolkit reads it: a local file when `Settings.trainer.vae` names one (the tests' and the e2e's stand-in),
    else the hub repo's `ae.safetensors` from HF_HOME (E16 — loom2's own `vae/flux2-vae.safetensors` is the diffusers-named repack its loader
    rejects), fetched once when absent (0.3 GB, the Apache Klein repos' VAE); a sentence when neither works (CI has no F:)."""
    v = settings.trainer.vae
    if Path(v).is_file():
        return str(Path(v))
    os.environ.setdefault("HF_HOME", settings.hf_home)
    from huggingface_hub import hf_hub_download
    try:
        return hf_hub_download(v, "ae.safetensors", local_files_only=True)
    except Exception:  # noqa: BLE001 — not cached yet
        pass
    try:
        return hf_hub_download(v, "ae.safetensors")
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"the Flux.2 autoencoder (ae.safetensors from {v}) is neither a file nor cached in {settings.hf_home}, and could not be fetched: {e}")


# ---- the run -------------------------------------------------------------------------------------------------------------------------
class VramSampler(threading.Thread):
    """Windows' GPU adapter counter (dedicated usage), the largest adapter, every `every` seconds — no CUDA context of its own (E16)."""

    def __init__(self, every: float = 10.0) -> None:
        super().__init__(daemon=True)
        self.every, self.peak, self._stop = every, 0, threading.Event()

    def run(self) -> None:
        if os.name != "nt":
            return
        cmd = "((Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples | Sort-Object CookedValue -Descending | Select-Object -First 1).CookedValue"
        while not self._stop.is_set():
            try:
                v = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=20).stdout.strip()
                self.peak = max(self.peak, int(float(v)) if v else 0)
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(self.every)

    def stop(self) -> None:
        self._stop.set()


def parse_progress(chunk: str) -> dict[str, Any]:
    """The newest step / total, rate and loss in a chunk of the trainer's log (tqdm writes with \\r); the resume step when printed."""
    out: dict[str, Any] = {}
    steps = STEP_RE.findall(chunk)
    if steps:
        out["step"], out["total"] = int(steps[-1][0]), int(steps[-1][1])
    rates = RATE_RE.findall(chunk)
    if rates:
        val, unit = float(rates[-1][0]), rates[-1][1]
        out["s_per_it"] = round(val if unit == "s/it" else (1.0 / val if val else 0.0), 3)
    losses = LOSS_RE.findall(chunk)
    if losses:
        try:
            out["loss"] = float(losses[-1])
        except ValueError:
            pass
    m = RESUME_RE.findall(chunk)
    if m:
        out["resumed_from"] = int(m[-1])
    return out


def _kill(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def run_train(job: "JobRecord", recipe: TrainLora, q: "JobQueue") -> bool:
    """The job: the engine stopped, the set and the yaml written, ai-toolkit run with its log in a file and its progress on the job card,
    a cancel killing the process tree, an exit ≠ 0 failing the job (resumable: a requeue continues from the newest save), the adapter
    promoted into the registry and the version. Returns True."""
    from .engine.pipeline import JobCancelled
    settings = q.app.settings
    why = trainer_available(settings)
    if why:
        raise ValueError(why)
    if q.groups is None:
        raise ValueError("no album store")
    spec = registry.get(recipe.model_id)
    if spec is None or spec.recipes.train is None:
        raise ValueError(f"{recipe.model_id!r} is not a trainable base")
    store = StoryStore(q.ws)
    q.progress(job, "training: stopping the engine")
    await q.engine.stop()                                               # 16 GB first: the trainer needs the whole card; the next engine job restarts it
    q.check_cancel(job)
    sdir, odir = set_dir(q.ws, job.id), run_dir(q.ws, job.id)
    q.progress(job, "training: preparing the reference set")
    meta = await asyncio.to_thread(materialise, q.ws, q.catalogue, q.groups, store, recipe, sdir)
    vae = await asyncio.to_thread(vae_path, settings)
    odir.mkdir(parents=True, exist_ok=True)
    name = job.id.replace("-", "_")
    cfg = train_config(recipe, name, sdir, odir, Path(settings.models_root), vae, settings.trainer.quantize)
    yaml_path = odir.parent / "train.yaml"
    yaml_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    log_path = q.app.logs_dir / f"train-{job.id}.log"
    env = {**os.environ, "HF_HOME": settings.hf_home, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "DISABLE_TELEMETRY": "1"}
    q.check_cancel(job)
    t0 = time.time()
    state: dict[str, Any] = {"step": 0, "total": int(recipe.steps)}
    sampler = VramSampler()
    sampler.start()
    from .engine.supervisor import _assign_to_job
    with log_path.open("ab") as lf:
        lf.write(f"==== launch {utc_now()} job {job.id} {spec.id} {recipe.steps} steps\n".encode("utf-8"))
        lf.flush()
        start_pos = lf.tell()
        proc = subprocess.Popen([settings.trainer.python, settings.trainer.run, str(yaml_path)], cwd=settings.trainer.cwd, env=env, stdout=lf, stderr=subprocess.STDOUT)
        in_job = _assign_to_job(proc)                                   # LT3: the orchestrator's job object — a kill takes the trainer along (one trainer per card)
    job.log_tail.append(f"trainer pid {proc.pid}" + (" in the job object" if in_job else ""))
    q.progress(job, "training: loading the base")
    pos = start_pos
    last_text = ""
    try:
        while True:
            done = proc.poll() is not None
            if not done:
                await asyncio.sleep(2.0)
                done = proc.poll() is not None
            try:
                with log_path.open("rb") as rf:
                    rf.seek(pos)
                    chunk = rf.read()
                pos += len(chunk)
            except OSError:
                chunk = b""
            if chunk:
                got = parse_progress(chunk.decode("utf-8", "replace"))
                state.update(got)
                if "step" in got:
                    step, total = state["step"], max(1, state.get("total") or recipe.steps)
                    job.progress = min(1.0, step / total)
                    rate = state.get("s_per_it")
                    eta = f" · {max(0, int((total - step) * rate)) // 60} min left" if rate else ""
                    loss = f" · loss {state['loss']:.3f}" if "loss" in state else ""
                    text = f"step {step} / {total}{loss}{f' · {rate} s/it' if rate else ''}{eta}"
                    if text != last_text:
                        last_text = text
                        q.progress(job, text)
            if done:
                break
            if job.id in q._cancel_requested:
                _kill(proc.pid)
                await asyncio.to_thread(proc.wait)
                raise JobCancelled(job.id)
    finally:
        sampler.stop()
    rc = proc.returncode
    text = log_path.read_text(encoding="utf-8", errors="replace").split("==== launch")[-1]
    if rc != 0:
        tail = [ln.strip() for ln in text.replace("\r", "\n").splitlines() if ln.strip()][-6:]
        raise ValueError(f"the trainer exited with {rc}: " + " | ".join(tail)[-900:])
    adapter = odir / name / f"{name}.safetensors"
    if not adapter.is_file():
        raise ValueError(f"the trainer finished but wrote no adapter ({adapter})")
    await q.irreversible(job)                                           # C8: the promotion below must never run twice
    p = store.profile(recipe.profile_id) if recipe.profile_id else None
    v = p.version(recipe.version) if p else None
    album = q.groups.groups.get(meta["group_id"]) if q.groups else None
    reg = LoraRegistry(q.ws)
    rec = LoraRecord(id=new_id("lora"), name=recipe.name.strip() or (f"{p.name} {recipe.version}" if p else album.name if album else "LoRA"), profile_id=recipe.profile_id,
                     version=recipe.version, base=model_base(recipe.model_id) or spec.family, model_id=recipe.model_id, trigger=recipe.trigger.strip(),
                     steps=int(recipe.steps), rank=int(recipe.rank), resolution=int(recipe.resolution), lr=float(recipe.lr), seed=int(recipe.seed),
                     dataset=meta, job_id=job.id, sha256=await asyncio.to_thread(_sha256, adapter), size=adapter.stat().st_size,
                     measured={"s_per_it": state.get("s_per_it"), "peak_vram_gb": round(sampler.peak / 2**30, 2) if sampler.peak else None,
                               "wall_s": round(time.time() - t0, 1), "resumed_from": state.get("resumed_from")},
                     previous=[v.lora] if v and v.lora else [])
    reg.dir.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(shutil.copy2, adapter, reg.file(rec.id))
    reg.save(rec)
    p = store.set_version_lora(recipe.profile_id, recipe.version, rec.id, rec.trigger) if p else None   # D122: an album's own adapter stays in the registry
    project_id = (q.ws.info() or {}).get("id") or q.ws.path.name
    await asyncio.to_thread(publish, q.roster, reg, Path(settings.models_root), project_id)
    job.result = {"lora_id": rec.id, "trigger": rec.trigger, "steps": rec.steps, "profile_id": rec.profile_id, "version": rec.version,
                  "s_per_it": rec.measured.get("s_per_it"), "peak_vram_gb": rec.measured.get("peak_vram_gb"), "resumed_from": rec.measured.get("resumed_from"),
                  "refs": meta["count"], "group_id": meta["group_id"], "log": str(log_path)}
    if p is not None:
        q.hub.broadcast("story.changed", {"kind": "profile", "id": p.id, "revision": p.revision})
    q.hub.broadcast("lora.changed", {"id": rec.id, "profile_id": rec.profile_id, "version": rec.version})
    shutil.rmtree(odir.parent, ignore_errors=True)                      # the set, the saves and the optimizer state; the log stays
    return True
