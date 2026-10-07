"""Durable job queue (06 §3b, §7 durability; loom's runner.py rules with the domain stripped): one engine job at
a time, admitted by a VRAM estimate, persisted atomically to `<project>/jobs/queue.json` after every change,
reloaded on restart with running jobs re-queued, warm-group ordering, cancel via `/interrupt`.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from .catalogue import Catalogue
from .config import AppState
from .engine.client import EngineError, EngineEvent
from .clips import ClipStore, compute_identity
from .tools import facesim
from .engine.graphs import I2V_WEIGHTS, PRESETS, compile_recipe, estimate_seconds, estimate_vram_gb, recipe_weights
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .fsio import StateError, atomic_write_json, free_space_gb, new_id, read_json_or, utc_now
from .recipes import T2I, I2I, I2V, Inpaint, Segment, Upscale, parse_recipe, warm_group
from .documents import DocumentStore, GroupLayer, RasterLayer
from .edit_ai import RegionPlan, assemble_layer, combine_selection, crop_inputs, dilate, layer_plan, mask_from_engine, outpaint_inputs, outpaint_plan, plan_region, whole_plan
import numpy as np
from PIL import Image
from .roster import ROSTER_BY_ID, Roster
from .workspace import Workspace

log = logging.getLogger("loom2.queue")
QUEUE_SCHEMA_VERSION = 1
MAX_WARM_SKIP_S = 600.0


def _age_s(iso: str) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds()
    except ValueError:
        return 0.0
JobStatus = Literal["staged", "queued", "running", "done", "failed", "cancelled"]
MIN_FREE_GB = 2.0                            # disk guard: refuse new jobs below this much free space
TERMINAL = {"done", "failed", "cancelled"}


class JobRecord(BaseModel):
    schema_version: int = QUEUE_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("job"))
    batch_id: str | None = None
    kind: str
    recipe: dict
    seed: int = 0
    engine: str = "comfyui"
    status: JobStatus = "queued"
    progress: float = 0.0
    progress_text: str = ""
    vram_estimate_gb: float = 0.0
    warm_group: str = ""
    created_at: str = Field(default_factory=utc_now)
    started_at: str | None = None
    finished_at: str | None = None
    wall_s: float | None = None
    result: dict = Field(default_factory=dict)
    error: str | None = None
    log_tail: list[str] = Field(default_factory=list)
    retry_count: int = 0
    resumable: bool = True
    prompt_id: str | None = None
    node_times: dict[str, float] = Field(default_factory=dict)
    variant: str = "full"


class JobQueue:
    def __init__(self, ws: Workspace, app: AppState, engine: EngineSupervisor, roster: Roster, catalogue: Catalogue, hub: EventHub) -> None:
        self.documents: DocumentStore | None = None      # set by Services once the project is open (M5 edit jobs)
        self.ws, self.app, self.engine, self.roster, self.catalogue, self.hub = ws, app, engine, roster, catalogue, hub
        self.jobs: dict[str, JobRecord] = {}
        self.paused = False
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._running_id: str | None = None
        self._last_group: str | None = None
        self._object_info: dict | None = None
        self._object_info_at: float | None = None
        self._ws_task: asyncio.Task | None = None
        self._events: asyncio.Queue[EngineEvent] = asyncio.Queue()
        self._cancel_requested: set[str] = set()
        self.resumed_unclean = False
        self.recovery: list[str] = []            # M7: what was quarantined on load (shown as a banner)

    # ---- persistence ------------------------------------------------------------------------------
    def load(self) -> None:
        empty = {"schema_version": QUEUE_SCHEMA_VERSION, "paused": False, "jobs": []}
        try:
            data = read_json_or(self.ws.queue_path, empty)
        except StateError as e:                      # M7: a torn queue.json is quarantined — never fatal, never silently reset
            q = self.ws.queue_path.with_name(f"queue.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
            try:
                self.ws.queue_path.replace(q)
            except OSError:
                q = self.ws.queue_path
            log.error("queue.json unreadable (%s); moved aside as %s", e, q.name)
            self.recovery.append(f"The job queue file was unreadable and was moved aside as {q.name}; jobs that were in flight are lost (their finished outputs are still in the Catalogue).")
            self.paused = True
            data = dict(empty)
        self.paused = bool(data.get("paused")) or bool(self.recovery)          # a quarantined queue file starts paused
        for j in data.get("jobs", []):
            try:
                rec = JobRecord.model_validate(j)
            except Exception as e:
                log.warning("dropping unreadable job record: %s", e)
                continue
            if rec.status == "running":
                if rec.resumable and not data.get("clean_shutdown", False):
                    rec.status, rec.progress, rec.prompt_id = "queued", 0.0, None
                    rec.retry_count += 1
                    rec.log_tail.append("re-queued after an unclean shutdown")
                    self.paused = True          # 12 M1 acceptance: relaunch resumes *paused* with the job queued
                    self.resumed_unclean = True
                else:
                    rec.status, rec.error, rec.finished_at = "failed", "interrupted by shutdown", utc_now()
            self.jobs[rec.id] = rec
        self.persist()

    def persist(self, clean_shutdown: bool = False) -> None:
        atomic_write_json(self.ws.queue_path, {"schema_version": QUEUE_SCHEMA_VERSION, "paused": self.paused, "clean_shutdown": clean_shutdown,
                                               "saved_at": utc_now(), "jobs": [j.model_dump() for j in self.jobs.values()]})

    # ---- lifecycle --------------------------------------------------------------------------------
    async def start(self) -> None:
        self.load()
        self._reconcile_leftovers()
        self._task = asyncio.create_task(self._run_loop(), name="loom2-queue")

    def _reconcile_leftovers(self) -> int:
        """B6 (06 §7): engine outputs and crop inputs that belong to no queued or running job — left by a crash or a
        kill — are removed when the project opens. Jobs that were running were re-queued by load() and render again."""
        live = {j.id for j in self.jobs.values() if j.status in ("queued", "running")}
        removed = 0
        out = self.app.state_dir / "engine_out" / "loom2"
        if out.is_dir():
            for p in out.iterdir():
                if p.is_file() and not any(p.name.startswith(j) for j in live):
                    p.unlink(missing_ok=True)
                    removed += 1
        ai = self.ws.temp_dir / "ai"
        if ai.is_dir():
            for d in ai.iterdir():
                if d.is_dir() and d.name not in live:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
        if removed:
            log.info("reconciled %d leftover engine file(s) from earlier runs", removed)
        return removed

    async def stop(self) -> None:
        running = self.jobs.get(self._running_id or "")      # B2: read before the cancelled task's `finally` clears it
        if running is not None and running.status == "running" and not running.resumable:
            was_paused, self.paused = self.paused, True        # C8: the engine is done; the move-in / paste-back / proxy encode is
            t0 = time.time()                                   # seconds of local work — let it finish rather than render twice
            while running.status == "running" and time.time() - t0 < 30.0:
                await asyncio.sleep(0.05)
            self.paused = was_paused
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None
        if running and running.status == "running":
            if not running.resumable:                        # C8: outputs may be half written — never render this one again
                running.status, running.error, running.finished_at = "failed", "interrupted while its outputs were being written", utc_now()
                self.catalogue.record_job(running.model_dump())
            else:
                submitted = running.prompt_id is not None
                running.status = "queued"           # a clean shutdown re-queues the interrupted job explicitly
                running.progress, running.prompt_id, running.progress_text = 0.0, None, ""
                running.log_tail.append("re-queued by a clean shutdown")
                if submitted:                       # the engine is still rendering it: stop that work now
                    try:
                        await asyncio.wait_for(self.engine.client.interrupt(), 5.0)
                    except Exception:
                        pass
            self.hub.broadcast("job.updated", running.model_dump())
        self.persist(clean_shutdown=True)

    # ---- API --------------------------------------------------------------------------------------
    def submit(self, recipe_data: dict, stage: bool = False) -> list[JobRecord]:
        recipe = parse_recipe(recipe_data)
        self._validate_models(recipe)
        self._disk_guard()
        seeds = recipe.seeds or [0]
        batch_id = new_id("bat") if len(seeds) > 1 else None
        out: list[JobRecord] = []
        for seed in seeds:
            seed = int(seed) if int(seed) > 0 else int(time.time_ns() % (2**32))
            rec = JobRecord(kind=recipe.kind, recipe=recipe.model_dump(), seed=seed, batch_id=batch_id, status="staged" if stage else "queued",
                            vram_estimate_gb=estimate_vram_gb(recipe, self.app.settings.variant), warm_group=warm_group(recipe, self.app.settings.variant),
                            variant=self.app.settings.variant)
            if rec.vram_estimate_gb > self.app.settings.vram_budget_gb:
                rec.status, rec.error, rec.finished_at = "failed", f"VRAM estimate {rec.vram_estimate_gb} GB exceeds the budget {self.app.settings.vram_budget_gb} GB", utc_now()
                self.catalogue.record_job(rec.model_dump())                 # C16: a refused job is still a job in the index
            self.jobs[rec.id] = rec
            out.append(rec)
            self.hub.broadcast("job.created", rec.model_dump())
        self.persist()
        self._wake.set()
        return out

    async def cancel(self, job_id: str) -> bool:
        rec = self.jobs.get(job_id)
        if rec is None or rec.status in TERMINAL:
            return False
        if rec.status == "running":
            self._cancel_requested.add(job_id)
            if rec.prompt_id:                   # B5: before submission there is nothing to interrupt; _run_one checks the flag
                try:
                    await self.engine.client.interrupt()
                except Exception as e:
                    log.warning("interrupt failed: %s", e)
            return True
        rec.status, rec.finished_at = "cancelled", utc_now()
        self.persist()
        self.hub.broadcast("job.updated", rec.model_dump())
        return True

    def release(self, job_id: str | None = None) -> list[JobRecord]:
        """Staged → queued (one job, or every staged job when no id is given) — 09 §3 'Stage' for overnight runs."""
        out = []
        for rec in self.jobs.values():
            if rec.status == "staged" and (job_id is None or rec.id == job_id):
                rec.status = "queued"
                out.append(rec)
                self.hub.broadcast("job.updated", rec.model_dump())
        if out:
            self.persist()
            self._wake.set()
        return out

    def timing_history(self) -> list[dict]:
        rows = []
        for j in self.jobs.values():
            if j.status == "done" and j.wall_s and j.kind == "t2i":
                comp = j.result.get("compiled") or {}
                rows.append({"model_id": j.recipe.get("model_id"), "px": (comp.get("width") or 0) * (comp.get("height") or 0), "steps": comp.get("steps"), "wall_s": j.wall_s})
        return rows

    def estimate(self, recipe: T2I) -> dict:
        est = estimate_seconds(recipe, self.timing_history())
        vram = estimate_vram_gb(recipe, self.app.settings.variant)
        budget = self.app.settings.vram_budget_gb
        est.update({"vram_gb": vram, "vram_budget_gb": budget, "vram_fit": "ok" if vram <= budget * 0.85 else "tight" if vram <= budget else "over"})
        return est

    def delete(self, job_id: str) -> bool:
        rec = self.jobs.get(job_id)
        if rec is None or rec.status not in TERMINAL:
            return False
        del self.jobs[job_id]
        self.persist()
        self.hub.broadcast("job.deleted", {"id": job_id})
        return True

    def pause(self) -> None:
        self.paused = True
        self.persist()
        self.hub.broadcast("queue.state", self.state())

    def unpause(self) -> None:
        self.paused = False
        self.persist()
        self.hub.broadcast("queue.state", self.state())
        self._wake.set()

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)

    def list(self, status: str | None = None) -> list[dict]:
        rows = [j.model_dump() for j in self.jobs.values() if not status or j.status == status]
        return sorted(rows, key=lambda j: j["created_at"], reverse=True)

    def counts(self) -> dict:
        c: dict[str, int] = {}
        for j in self.jobs.values():
            c[j.status] = c.get(j.status, 0) + 1
        return c

    def state(self) -> dict:
        return {"paused": self.paused, "running": self._running_id, "counts": self.counts(), "last_warm_group": self._last_group,
                "resumed_unclean": self.resumed_unclean, "recovery": list(self.recovery) + list(getattr(self.catalogue, "recovery", []) or [])}

    def _validate_models(self, recipe: Any) -> None:
        """B11: an unknown roster id fails at submission (HTTP 422), not minutes later after the engine has started.
        C3 (D26): under the `open` variant every weight the recipe would load must carry the `open` tag — the UI hides them, the
        queue is the gate."""
        for mid in [recipe.model_id, *[l.model_id for l in getattr(recipe, "loras", [])]]:
            if mid not in ROSTER_BY_ID:
                raise ValueError(f"unknown model id {mid!r}")
        if isinstance(recipe, T2I) and recipe.model_id not in PRESETS:
            raise ValueError(f"no t2i preset for {recipe.model_id!r}")
        if isinstance(recipe, I2V):
            if recipe.model_id not in I2V_WEIGHTS:
                raise ValueError(f"{recipe.model_id!r} is not an image-to-video model (Wan 2.2 or LTX-2.3)")
            if recipe.beats and ROSTER_BY_ID[recipe.model_id].family != "ltx23":
                raise ValueError("keyframe beats need LTX-2.3; Wan takes a start and an end frame")
        variant = self.app.settings.variant
        if variant == "open":
            for mid in recipe_weights(recipe, variant):
                entry = ROSTER_BY_ID.get(mid)
                if entry is not None and "open" not in entry.variants:
                    raise ValueError(f"{mid!r} ({entry.license}) is not part of the open variant (D26)")

    def _disk_guard(self) -> None:
        """03 §6 / 06 §4: refuse new work before the engine starts when the work disk is nearly full or the project is over
        its size cap — a clear 422 at submission instead of a torn output half-way through a clip."""
        free = free_space_gb(self.ws.path)
        if free < MIN_FREE_GB:
            raise ValueError(f"disk guard: only {free:.1f} GB free on the project drive (minimum {MIN_FREE_GB:g} GB) — free space or move the project")
        cap = float((self.ws.info() or {}).get("size_cap_gb") or 0)
        if cap:
            used = self.catalogue.usage_bytes() / 2**30
            if used > cap:
                raise ValueError(f"disk guard: the project holds {used:.1f} GB of assets, over its {cap:g} GB cap — empty the trash or raise the cap in project.json")

    # ---- scheduling -------------------------------------------------------------------------------
    def _next(self) -> JobRecord | None:
        queued = [j for j in self.jobs.values() if j.status == "queued"]
        if not queued:
            return None
        queued.sort(key=lambda j: j.created_at)
        oldest = queued[0]
        same = [j for j in queued if j.warm_group == self._last_group]
        if same and same[0] is not oldest and _age_s(oldest.created_at) > MAX_WARM_SKIP_S:
            return oldest                      # B11: warm-group affinity never starves another model for more than 10 min
        return same[0] if same else oldest

    async def _run_loop(self) -> None:
        while True:
            try:
                job = None if self.paused else self._next()
                if job is None:
                    self._wake.clear()
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass
                    continue
                await self._run_one(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # the loop must survive anything a job does
                log.error("queue loop error: %s\n%s", e, traceback.format_exc())
                await asyncio.sleep(1.0)

    def engine_enum(self, cls: str, key: str) -> list[str] | None:
        """An input's enum from the last `/object_info` the engine answered (None before the first job)."""
        try:
            spec = (self._object_info or {})[cls]["input"]["required"][key]
            return list(spec[0]) if isinstance(spec[0], list) else None
        except (KeyError, TypeError, IndexError):
            return None

    async def _object_info_fresh(self) -> dict:
        if self._object_info is None or (self.engine.started_at and (self._object_info_at or 0) < self.engine.started_at):
            self._object_info = await self.engine.client.object_info()
            self._object_info_at = time.time()
        return self._object_info

    async def _ensure_ws(self) -> None:
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._pump_events(), name="loom2-engine-ws")
            await asyncio.sleep(0.2)

    async def _pump_events(self) -> None:
        while True:
            try:
                async for ev in self.engine.client.events():
                    if ev.type == "ws_closed":
                        break
                    await self._events.put(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.debug("engine ws: %s", e)
            await asyncio.sleep(1.0)

    def _fail(self, job: JobRecord, msg: str) -> None:
        job.status, job.error, job.finished_at = "failed", msg, utc_now()
        job.wall_s = round(time.time() - self._t0, 1) if hasattr(self, "_t0") else None
        job.log_tail.append(msg)
        self.catalogue.record_job(job.model_dump())
        self.persist()
        self.hub.broadcast("job.updated", job.model_dump())

    def _finish_cancelled(self, job: JobRecord) -> None:
        self._cancel_requested.discard(job.id)
        job.status, job.finished_at, job.error = "cancelled", utc_now(), None
        job.wall_s = round(time.time() - self._t0, 1)
        self.catalogue.record_job(job.model_dump())
        self.persist()
        self.hub.broadcast("job.updated", job.model_dump())

    def _cancelled(self, job: JobRecord) -> bool:
        """B5: a cancel that arrived while the job was still preparing (engine start, uploads, region crop)."""
        if job.id in self._cancel_requested:
            self._finish_cancelled(job)
            return True
        return False

    def _cleanup_job_files(self, job: JobRecord) -> None:
        """B6: the engine's files for this job (prefix `loom2/<job_id>`) and the job's crop inputs are transient."""
        try:
            out = self.app.state_dir / "engine_out" / "loom2"
            if out.is_dir():
                for p in out.glob(f"{job.id}*"):
                    p.unlink(missing_ok=True)
            tmp = self.ws.temp_dir / "ai" / job.id
            if tmp.is_dir():
                shutil.rmtree(tmp, ignore_errors=True)
        except OSError as e:  # noqa: BLE001
            log.debug("cleanup after %s: %s", job.id, e)

    def _engine_unavailable(self, job: JobRecord, why: str) -> None:
        """C2: the engine failed to launch — that is the engine's problem, not this job's. The job goes back to queued, the queue
        pauses and the banners say why, instead of every queued job failing in turn, a health timeout each."""
        log.error("job %s: %s — pausing the queue", job.id, why)
        job.status, job.started_at, job.progress, job.progress_text = "queued", None, 0.0, ""
        job.log_tail.append(why)
        self.paused = True
        self.persist()
        self.hub.broadcast("job.updated", job.model_dump())
        self.hub.broadcast("queue.state", self.state())

    async def _run_one(self, job: JobRecord) -> None:
        self._running_id = job.id
        self._t0 = time.time()
        job.status, job.started_at, job.progress, job.progress_text = "running", utc_now(), 0.0, "starting engine"
        try:
            self.persist()
        except OSError as e:                        # B12 (review): a full disk must not leave a phantom running job
            job.status, job.started_at = "queued", None
            self._running_id = None
            log.error("cannot persist the queue (%s); pausing", e)
            self.paused = True
            return
        self.hub.broadcast("job.updated", job.model_dump())
        try:
            try:
                await self.engine.ensure_running()
            except (RuntimeError, OSError) as e:                # C2: launch failure → hold the queue, keep the job
                self._engine_unavailable(job, f"engine could not start: {e}")
                return
            await self._ensure_ws()
            if self._cancelled(job):
                return
            object_info = await self._object_info_fresh()
            recipe = parse_recipe(job.recipe)
            await asyncio.to_thread(self.roster.scan)                  # C7: the mounted trees can be large
            ref_files: dict[str, str] = {}
            for ref in getattr(recipe, "refs", []) or []:
                key = ref.asset_id or ref.blob or ""
                src = None
                if ref.asset_id:
                    a = self.catalogue.get(ref.asset_id)
                    src = self.catalogue.abs_path(a) if a else None
                elif ref.blob:
                    src = self.ws.temp_dir / "blobs" / ref.blob
                if not src or not Path(src).is_file():
                    self._fail(job, f"reference image {key} is missing")
                    return
                fitted = await asyncio.to_thread(self._fit_reference, Path(src), int(getattr(recipe, "ref_max_px", 0) or 0), key)
                ref_files[key] = await self.engine.client.upload_image(fitted)   # top level: LoadImage's enum ignores sub-folders
            if ref_files:                                   # uploaded names appear in LoadImage's enum only after a refresh (E8)
                object_info = await self.engine.client.object_info()
                self._object_info, self._object_info_at = object_info, time.time()
            if self._cancelled(job):
                return
            inputs: dict[str, Any] | None = None
            if isinstance(recipe, (Inpaint, I2I, Upscale, Segment)):   # M5: crops of the document go in through /upload/image
                job.progress_text = "preparing region"
                self.hub.broadcast("job.updated", job.model_dump())
                inputs = await self._prepare_document_inputs(job, recipe)
                object_info = await self.engine.client.object_info()
                self._object_info, self._object_info_at = object_info, time.time()
                if self._cancelled(job):
                    return
            if isinstance(recipe, I2V):                                # M6: start / end / beat frames go in through /upload/image
                job.progress_text = "uploading frames"
                self.hub.broadcast("job.updated", job.model_dump())
                inputs = await self._prepare_i2v_inputs(job, recipe)
                object_info = await self.engine.client.object_info()
                self._object_info, self._object_info_at = object_info, time.time()
                if self._cancelled(job):
                    return
            compiled = compile_recipe(recipe, self.roster, object_info, job.seed, out_prefix=f"loom2/{job.id}", ref_files=ref_files, inputs=inputs,
                                      variant=self.app.settings.variant)
            if compiled.problems:
                self._fail(job, "contract: " + "; ".join(compiled.problems)[:1500])
                return
            job.log_tail += [f"resolved {n}" for n in compiled.notes]
            job.result["compiled"] = compiled.summary | {"graph_hash": compiled.graph_hash}
            job.result["serialized_prompt"] = compiled.serialized_prompt
            while not self._events.empty():
                self._events.get_nowait()
            if self._cancelled(job):
                return
            job.prompt_id = await self.engine.client.queue_prompt(compiled.graph)
            if job.id in self._cancel_requested:            # cancel() saw no prompt_id yet: interrupt what we just queued
                try:
                    await self.engine.client.interrupt()
                except Exception as e:  # noqa: BLE001
                    log.warning("interrupt failed: %s", e)
            job.progress_text = "queued on engine"
            self.hub.broadcast("job.updated", job.model_dump())
            ok = await self._follow(job)
            if job.id in self._cancel_requested or not ok and job.error == "interrupted":
                self._finish_cancelled(job)
                return
            if not ok:
                self._fail(job, job.error or "engine reported an error")
                return
            job.resumable = False                            # C8: the engine's work is done; what follows must never run twice
            self.persist()
            hist = await self.engine.client.history(job.prompt_id)
            files = self._outputs_from_history(hist)
            if not files:
                self._fail(job, "the engine finished but produced no output files")
                return
            if isinstance(recipe, I2V):
                await self._finish_i2v_job(job, recipe, files, compiled)
                await self._free_engine_cache()
                job.status, job.finished_at, job.progress, job.progress_text = "done", utc_now(), 1.0, "done"
                job.wall_s = round(time.time() - self._t0, 1)
                self.catalogue.record_job(job.model_dump())
                self.persist()
                self.hub.broadcast("job.updated", job.model_dump())
                self.engine.jobs_since_start += 1
                self._last_group = job.warm_group
                return
            if isinstance(recipe, (Inpaint, I2I, Upscale, Segment)):
                await self._finish_document_job(job, recipe, files, inputs or {})
                await self._free_engine_cache()
                job.status, job.finished_at, job.progress, job.progress_text = "done", utc_now(), 1.0, "done"
                job.wall_s = round(time.time() - self._t0, 1)
                self.catalogue.record_job(job.model_dump())
                self.persist()
                self.hub.broadcast("job.updated", job.model_dump())
                self.engine.jobs_since_start += 1
                self._last_group = job.warm_group
                return
            assets = []
            for f in files:
                src = self.app.state_dir / "engine_out" / f["subfolder"] / f["filename"] if f["subfolder"] else self.app.state_dir / "engine_out" / f["filename"]
                if not src.is_file():
                    job.log_tail.append(f"missing output {src}")
                    continue
                rec = await asyncio.to_thread(
                    self.catalogue.ingest_file, src, kind="video" if src.suffix.lower() in (".mp4", ".webm", ".mov") else "image", move=True,
                    job_id=job.id, batch_id=job.batch_id, suite="generate", model_id=recipe.model_id, seed=job.seed,
                    prompt_text=compiled.serialized_prompt or getattr(recipe, "prompt_text", None), prompt_json=getattr(recipe, "prompt_json", None),
                    params=compiled.summary | {"recipe": recipe.model_dump()}, timings={"wall_s": round(time.time() - self._t0, 1), "node_s": job.node_times},
                    compiled_graph_hash=compiled.graph_hash, variant=job.variant, parents=[r.asset_id for r in (getattr(recipe, "refs", []) or []) if getattr(r, "asset_id", None)])
                assets.append(rec)
                self.hub.broadcast("asset.created", rec.model_dump())
            job.progress_text = "thumbnails"
            for i, rec in enumerate(assets):
                assets[i] = await asyncio.to_thread(self.catalogue.make_thumbs, rec)
                self.hub.broadcast("asset.updated", assets[i].model_dump())
            job.result["asset_ids"] = [a.id for a in assets]
            job.status, job.finished_at, job.progress, job.progress_text = "done", utc_now(), 1.0, "done"
            job.wall_s = round(time.time() - self._t0, 1)
            self.catalogue.record_job(job.model_dump())
            self.persist()
            self.hub.broadcast("job.updated", job.model_dump())
            self.engine.jobs_since_start += 1
            self._last_group = job.warm_group
        except NotImplementedError as e:
            self._fail(job, str(e))
        except (EngineError, FileNotFoundError, ValueError) as e:
            self._fail(job, str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("job %s crashed: %s\n%s", job.id, e, traceback.format_exc())
            self._fail(job, f"{type(e).__name__}: {e}")
        finally:
            self._running_id = None
            if job.status in TERMINAL:
                self._cleanup_job_files(job)

    # ---- M5 document jobs (10 §4, D7): region in, layer out ------------------------------------------
    async def _prepare_document_inputs(self, job: JobRecord, recipe: Inpaint | I2I | Upscale | Segment) -> dict[str, Any]:
        """Crop/scale the document's composite (and mask) for the engine, upload them and keep the plan (edit_ai)."""
        if self.documents is None:
            raise ValueError("documents are not available (no project open)")
        od = await asyncio.to_thread(self.documents.get, recipe.document_id)
        tmp = self.ws.temp_dir / "ai" / job.id
        tmp.mkdir(parents=True, exist_ok=True)
        # B3: candidates of one batch are alternatives — the engine must not see the candidate layers already pasted back
        exclude = {f"grp_{job.batch_id or job.id}"}

        def work() -> dict[str, Any]:
            comp = od.flatten(exclude=exclude)
            out: dict[str, Any] = {}
            if isinstance(recipe, Inpaint):
                if recipe.mode == "outpaint":
                    plan = outpaint_plan(od.doc.w, od.doc.h, recipe.outpaint or {}, max_pixels=recipe.max_pixels)
                    if plan.w == od.doc.w and plan.h == od.doc.h:
                        raise ValueError("outpaint needs at least one side to grow")
                    img, msk, strips = outpaint_inputs(comp, plan)
                    out["alpha_mask"] = strips
                else:
                    sel = od.selection
                    if sel is None or not sel.any():
                        raise ValueError("inpaint needs a selection (the region to repaint)")
                    mask = dilate(sel, recipe.expand) if recipe.expand else sel
                    plan = plan_region(mask, od.doc.w, od.doc.h, recipe.margin_pct, recipe.min_size, max_pixels=recipe.max_pixels)
                    if plan is None:
                        raise ValueError("the selection is empty")
                    img, msk = crop_inputs(comp, mask, plan)
                    out["alpha_mask"] = mask
                Image.fromarray(img, "RGB").save(tmp / "image.png")
                Image.fromarray(msk, "L").save(tmp / "mask.png")          # type: ignore[arg-type]
                out["mask_path"] = tmp / "mask.png"
            elif isinstance(recipe, Segment):
                # AI Select reads the whole visible composite at ≤ max_size; prompts are scaled into engine pixels
                plan = whole_plan(od.doc.w, od.doc.h, max_size=recipe.max_size)
                img, _ = crop_inputs(comp, None, plan)
                sx, sy = plan.ew / od.doc.w, plan.eh / od.doc.h
                out["points"] = [{"x": int(round(p["x"] * sx)), "y": int(round(p["y"] * sy)), "label": int(p.get("label", 1))} for p in recipe.points]
                out["box"] = [int(round(recipe.box[0] * sx)), int(round(recipe.box[1] * sy)), int(round(recipe.box[2] * sx)), int(round(recipe.box[3] * sy))] if recipe.box else None
                out["alpha_mask"] = None
                Image.fromarray(img, "RGB").save(tmp / "image.png")
            elif isinstance(recipe, I2I):
                if recipe.source == "active":
                    node = od.doc.find(recipe.layer_id or "")
                    px = od.pixels.get(recipe.layer_id or "")
                    if node is None or px is None or not isinstance(node, RasterLayer):
                        raise ValueError("refine on the active layer needs a raster layer with pixels")
                    plan = layer_plan(node.x, node.y, int(px.shape[1]), int(px.shape[0]))
                    img = np.ascontiguousarray(px[..., :3])
                    if (plan.ew, plan.eh) != (plan.w, plan.h):
                        img = np.asarray(Image.fromarray(img).resize((plan.ew, plan.eh), Image.Resampling.LANCZOS))
                    out["alpha_mask"] = np.ascontiguousarray(px[..., 3])
                elif recipe.source == "selection":
                    sel = od.selection
                    if sel is None or not sel.any():
                        raise ValueError("refine on the selection needs a selection")
                    plan = plan_region(sel, od.doc.w, od.doc.h, recipe.margin_pct, 0)
                    if plan is None:
                        raise ValueError("the selection is empty")
                    img, _ = crop_inputs(comp, None, plan)
                    out["alpha_mask"] = sel
                else:
                    plan = whole_plan(od.doc.w, od.doc.h)
                    img, _ = crop_inputs(comp, None, plan)
                    out["alpha_mask"] = None
                Image.fromarray(img, "RGB").save(tmp / "image.png")
            else:
                if recipe.source == "active":
                    node = od.doc.find(recipe.layer_id or "")
                    px = od.pixels.get(recipe.layer_id or "")
                    if node is None or px is None or not isinstance(node, RasterLayer):
                        raise ValueError("upscale of the active layer needs a raster layer with pixels")
                    plan = layer_plan(node.x, node.y, int(px.shape[1]), int(px.shape[0]), max_size=0)
                    Image.fromarray(px, "RGBA").save(tmp / "image.png")
                    out["alpha_mask"] = np.ascontiguousarray(px[..., 3])         # C4: the engine returns RGB; the layer keeps its alpha
                else:
                    plan = whole_plan(od.doc.w, od.doc.h, max_size=0)
                    Image.fromarray(comp, "RGBA").save(tmp / "image.png")
                    out["alpha_mask"] = np.ascontiguousarray(comp[..., 3])
            out["plan"] = plan
            out["image_path"] = tmp / "image.png"
            return out

        inputs = await asyncio.wait_for(asyncio.to_thread(work), 300.0)      # B4: region preparation is bounded too
        plan: RegionPlan = inputs["plan"]
        inputs["image"] = await self.engine.client.upload_image(inputs["image_path"])
        if inputs.get("mask_path"):
            inputs["mask"] = await self.engine.client.upload_image(inputs["mask_path"])
        inputs["w"], inputs["h"] = plan.ew, plan.eh
        job.result["region"] = plan.to_dict()
        job.log_tail.append(f"region {plan.w}×{plan.h} at {plan.x},{plan.y} → engine {plan.ew}×{plan.eh} (×{plan.scale:.2f})")
        return inputs

    async def _finish_document_job(self, job: JobRecord, recipe: Inpaint | I2I | Upscale | Segment, files: list[dict], inputs: dict[str, Any]) -> None:
        """Paste the engine result back as a new layer (or a Catalogue asset for upscale)."""
        assert self.documents is not None
        f = files[0]
        src = self.app.state_dir / "engine_out" / f["subfolder"] / f["filename"] if f["subfolder"] else self.app.state_dir / "engine_out" / f["filename"]
        if not src.is_file():
            raise ValueError(f"missing output {src}")
        od = await asyncio.to_thread(self.documents.get, recipe.document_id)
        plan: RegionPlan = inputs["plan"]
        job.progress_text = "paste-back"
        self.hub.broadcast("job.updated", job.model_dump())
        arr = await asyncio.to_thread(lambda: np.asarray(Image.open(src).convert("RGBA")))
        if isinstance(recipe, Segment):
            # the mask image → document-sized selection, joined with the current one per `op`; saved so the ORA keeps it
            def apply() -> float:
                m = mask_from_engine(arr[..., 0], od.doc.w, od.doc.h, recipe.expand, recipe.feather)
                od.selection = combine_selection(od.selection, m, recipe.op)
                od.doc.has_selection = True
                od.dirty = True
                od.save()
                return float(od.selection.mean() / 255.0)
            coverage = await asyncio.to_thread(apply)
            job.result["selection"] = {"w": od.doc.w, "h": od.doc.h, "coverage": round(coverage, 4), "op": recipe.op}
            job.log_tail.append(f"selection {recipe.op}: {coverage * 100:.1f} % of the canvas")
            self.hub.broadcast("document.changed", {"id": od.doc.id, "job_id": job.id, "selection": True, "coverage": round(coverage, 4)})
            return
        if isinstance(recipe, Upscale):
            parents = [od.doc.source_asset_id] if od.doc.source_asset_id else []
            rec = await asyncio.to_thread(self.catalogue.ingest_file, src, kind="image", move=True, job_id=job.id, batch_id=job.batch_id, suite="edit",
                                          model_id=recipe.model_id, seed=job.seed, params={"recipe": recipe.model_dump(), "document_id": od.doc.id},
                                          timings={"wall_s": round(time.time() - self._t0, 1), "node_s": job.node_times}, parents=parents)
            rec = await asyncio.to_thread(self.catalogue.make_thumbs, rec)
            self.hub.broadcast("asset.created", rec.model_dump())
            job.result["asset_ids"] = [rec.id]
            if recipe.as_layer:
                factor = max(1, round(arr.shape[1] / max(1, plan.w)))
                rgba = assemble_layer(arr, plan, inputs.get("alpha_mask"), 0)     # C4: back to 1× with the source's alpha
                await self._add_result_layer(job, od, recipe, rgba, plan.x, plan.y, f"upscale ×{factor} at 1×")
            return
        if isinstance(recipe, Inpaint) and recipe.mode == "outpaint":
            p = plan.pad or {}
            left, top = int(p.get("left", 0)), int(p.get("top", 0))
            job.result["shift"] = {"left": left, "top": top}          # C20: the editor shifts its own layers the same way
            for n in od.doc.walk():
                if isinstance(n, RasterLayer):
                    n.x += left; n.y += top
                if n.mask is not None and not n.mask.linked:
                    n.mask.x += left; n.mask.y += top
            old_w, old_h = od.doc.w, od.doc.h
            od.doc.w, od.doc.h = plan.w, plan.h
            if od.selection is not None:
                od.selection = np.pad(od.selection, ((top, plan.h - old_h - top), (left, plan.w - old_w - left)))
            rgba = assemble_layer(arr, plan, inputs.get("alpha_mask"), recipe.feather)
            await self._add_result_layer(job, od, recipe, rgba, 0, 0, "outpaint")
            return
        feather_px = recipe.feather if isinstance(recipe, Inpaint) or recipe.source == "selection" else 0
        rgba = assemble_layer(arr, plan, inputs.get("alpha_mask"), feather_px)
        label = recipe.mode.replace("_", " ") if isinstance(recipe, Inpaint) else f"refine {recipe.strength:.2f}"
        await self._add_result_layer(job, od, recipe, rgba, plan.x, plan.y, label)

    async def _add_result_layer(self, job: JobRecord, od: Any, recipe: Inpaint | I2I | Upscale, rgba: np.ndarray, x: int, y: int, label: str) -> None:
        """Candidates of one batch share a group at the top of the stack; only the first is visible (10 §4 variant strip)."""
        gid = f"grp_{job.batch_id or job.id}"
        group = od.doc.find(gid)
        if not isinstance(group, GroupLayer):
            prompt = str(getattr(recipe, "prompt_text", "") or "")
            group = GroupLayer(id=gid, name=f"AI {label}" + (f": {prompt[:28]}" if prompt else ""), passthrough=True)
            od.doc.layers.insert(0, group)
        n = len(group.children) + 1
        lid = new_id("lyr")
        multi = len(getattr(recipe, "seeds", [0])) > 1
        layer = RasterLayer(id=lid, name=f"candidate {n}" if multi else label, x=int(x), y=int(y), w=int(rgba.shape[1]), h=int(rgba.shape[0]), visible=(n == 1),
                            recipe={**recipe.model_dump(), "seed": job.seed, "job_id": job.id, "batch_id": job.batch_id, "region": job.result.get("region")},
                            lineage_asset_id=od.doc.source_asset_id)
        group.children.append(layer)
        od.set_pixels(lid, np.ascontiguousarray(rgba))
        od.dirty = True
        od.doc.revision += 1                                 # C1: a client stack based on the previous revision is now stale
        await asyncio.to_thread(od.save)
        job.result.setdefault("layers", []).append(lid)
        job.result["group"] = gid
        self.hub.broadcast("document.changed", {"id": od.doc.id, "job_id": job.id, "batch_id": job.batch_id, "added": [lid], "group": gid, "w": od.doc.w, "h": od.doc.h, "candidate": n,
                                                 "shift": job.result.get("shift"), "revision": od.doc.revision})

    # ---- M6 video jobs (11 §10): frames in through /upload/image, a clip out -------------------------
    async def _prepare_i2v_inputs(self, job: JobRecord, recipe: I2V) -> dict[str, Any]:
        """Upload the start, end and beat frames as PNG (the graph's ImageScale fits them to the clip size)."""
        names: dict[str, Any] = {"beats": {}}

        async def up(asset_id: str, what: str) -> str:
            a = self.catalogue.get(asset_id)
            src = self.catalogue.abs_path(a) if a else None
            if not src or not Path(src).is_file():
                raise ValueError(f"the {what} frame ({asset_id}) is missing from the Catalogue")
            fitted = await asyncio.to_thread(self._fit_reference, Path(src), 0, f"i2v-{asset_id}")
            return await self.engine.client.upload_image(fitted)

        names["start"] = await up(recipe.start_asset, "start")
        names["end"] = await up(recipe.end_asset, "end") if recipe.end_asset else None
        for b in recipe.beats:
            names["beats"][b.asset_id] = await up(b.asset_id, f"beat {b.frame}")
        job.log_tail.append("frames uploaded: start" + (", end" if names["end"] else "") + (f", {len(recipe.beats)} beat(s)" if recipe.beats else ""))
        return names

    async def _finish_i2v_job(self, job: JobRecord, recipe: I2V, files: list[dict], compiled: Any) -> None:
        """The decoded frames become `clips/<id>/master`, the proxy is encoded, and the proxy is the Catalogue asset."""
        paths: list[Path] = []
        for f in sorted(files, key=lambda x: x["filename"]):
            src = self.app.state_dir / "engine_out" / f["subfolder"] / f["filename"] if f["subfolder"] else self.app.state_dir / "engine_out" / f["filename"]
            if src.is_file():
                paths.append(src)
        if not paths:
            raise ValueError("the engine produced no frames")
        clips = ClipStore(self.ws)
        ep = compiled.summary
        job.progress_text = "writing the master"
        self.hub.broadcast("job.updated", job.model_dump())
        rec = await asyncio.to_thread(clips.create, paths, job_id=job.id, batch_id=job.batch_id, model_id=recipe.model_id, preset=recipe.preset, prompt=recipe.prompt_text,
                                      seed=job.seed, fps=int(ep.get("fps", recipe.fps)), start_asset_id=recipe.start_asset, end_asset_id=recipe.end_asset,
                                      beats=[b.model_dump() for b in recipe.beats], params={"recipe": recipe.model_dump(), "compiled": ep | {"graph_hash": compiled.graph_hash}},
                                      timings={"engine_wall_s": round(time.time() - self._t0, 1), "node_s": job.node_times})
        job.progress_text = "encoding the proxy"
        self.hub.broadcast("job.updated", job.model_dump())
        rec = await asyncio.to_thread(clips.encode_proxy, rec)
        parents = [recipe.start_asset] + ([recipe.end_asset] if recipe.end_asset else []) + [b.asset_id for b in recipe.beats]
        parents = list(dict.fromkeys(parents))
        asset = await asyncio.to_thread(self.catalogue.ingest_file, self.ws.path / rec.proxy_path, kind="video", in_place=True, job_id=job.id, batch_id=job.batch_id,
                                        suite="animate", model_id=recipe.model_id, seed=job.seed, prompt_text=recipe.prompt_text,
                                        params={"clip_id": rec.id, "preset": recipe.preset, "recipe": recipe.model_dump(), **ep},
                                        timings={"wall_s": round(time.time() - self._t0, 1), "node_s": job.node_times}, compiled_graph_hash=compiled.graph_hash,
                                        parents=parents, frames=rec.frames, w=rec.w, h=rec.h, variant=job.variant)
        asset = await asyncio.to_thread(self.catalogue.make_thumbs, asset, clips.frame_path(rec.id, 0))
        rec.asset_id = asset.id
        rec.timings["wall_s"] = round(time.time() - self._t0, 1)
        clips.save(rec)
        self.hub.broadcast("asset.created", asset.model_dump())
        job.result["asset_ids"] = [asset.id]
        job.result["clip_id"] = rec.id
        job.log_tail.append(f"clip {rec.id}: {rec.frames} frames @ {rec.fps} fps, {rec.w}×{rec.h}, proxy {rec.proxy_bytes / 2**20:.1f} MiB")
        self.hub.broadcast("clip.ready", {"clip_id": rec.id, "asset_id": asset.id, "job_id": job.id, "frames": rec.frames, "fps": rec.fps, "w": rec.w, "h": rec.h})
        if facesim.available(self.app.settings.models_root):             # advisory, off the job's critical path
            self._side(self._identity_task(rec.id))

    def _side(self, coro: Any) -> None:
        tasks: set = getattr(self, "_side_tasks", None) or set()
        self._side_tasks = tasks
        t = asyncio.get_running_loop().create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    async def _identity_task(self, clip_id: str) -> None:
        clips = ClipStore(self.ws)
        rec = clips.get(clip_id)
        if not rec:
            return
        start = self.catalogue.get(rec.start_asset_id)
        ref = self.catalogue.abs_path(start) if start else None
        try:
            result = await asyncio.wait_for(asyncio.to_thread(compute_identity, self.app.settings.models_root, clips, rec, ref), 240)
        except Exception as e:  # noqa: BLE001
            result = {"status": f"error: {type(e).__name__}: {e}", "sampled": 0, "with_face": 0}
        rec = clips.get(clip_id)
        if rec:
            rec.identity = result
            clips.save(rec)
            self.hub.broadcast("clip.updated", {"clip_id": clip_id, "identity": result})

    def _fit_reference(self, src: Path, max_px: int, key: str) -> Path:
        """References are downscaled to ≤ max_px² before upload (09 §3d); PNG so the engine's LoadImage is exact."""
        from PIL import Image
        out_dir = self.ws.temp_dir / "refs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"loom2ref-{key[:24]}.png"                 # unique in the engine's input dir
        with Image.open(src) as im:
            im = im.convert("RGB")
            if max_px and (im.width > max_px or im.height > max_px):
                im.thumbnail((max_px, max_px), Image.LANCZOS)
            im.save(out, "PNG")
        return out

    async def _recover_engine(self, job: JobRecord, why: str) -> None:
        """A stalled job means a hung GPU context (the 2026-10-05 TDR): interrupt, restart the engine, pause the queue
        so the next job does not walk into the same wall (06 §10)."""
        log.error("job %s: %s — restarting the engine and pausing the queue", job.id, why)
        job.log_tail.append(why)
        try:
            await asyncio.wait_for(self.engine.client.interrupt(), 5.0)
        except Exception:
            pass
        try:
            await asyncio.wait_for(self.engine.restart(), 90.0)
        except Exception as e:  # noqa: BLE001
            job.log_tail.append(f"engine restart failed: {e}")
        self.pause()

    async def _engine_alive(self) -> bool:
        """Supervised: the process is alive. Adopted: it answers within 10 s (a slow answer counts as alive —
        ComfyUI's HTTP thread shares the GIL with a model load; a refused connection does not)."""
        proc = getattr(self.engine, "proc", None)
        if proc is not None:
            return proc.poll() is None
        try:
            return await asyncio.wait_for(self.engine.client.is_up(), 10.0)
        except asyncio.TimeoutError:
            return True

    async def _free_engine_cache(self) -> None:
        """After a document job: drop ComfyUI's cached outputs but keep the weights resident. Consecutive Klein jobs
        with alternating graphs (LanPaint / ICM) otherwise accumulate VRAM until the model streams from RAM."""
        try:
            await asyncio.wait_for(self.engine.client.free(unload_models=False, free_memory=True), 30.0)
        except Exception as e:  # noqa: BLE001
            log.warning("free_memory after job failed: %s", e)

    async def _follow(self, job: JobRecord, idle_timeout_s: float | None = None) -> bool:
        """Consume engine events for this prompt until success / error / interrupt; poll history as a fallback.
        No event at all for `stall_timeout_s` (cold model loads take ≈ 2–3 min, a hung GPU never speaks again) fails
        the job and restarts the engine."""
        node_t0: dict[str, float] = {}
        last_node: str | None = None
        t_last = time.time()
        stall_s = float(idle_timeout_s or getattr(self.app.settings.engine, "stall_timeout_s", 420) or 420)
        poll_s = max(0.5, min(5.0, stall_s / 4))
        while True:
            try:
                ev = await asyncio.wait_for(self._events.get(), timeout=poll_s)
            except asyncio.TimeoutError:
                if time.time() - t_last > stall_s:
                    job.error = f"engine stalled: no progress for {int(stall_s)} s (GPU hang?) — engine restarted, queue paused"
                    await self._recover_engine(job, job.error)
                    return False
                try:                                        # B4: a hung or refused poll is not a crash of the queue
                    hist = await asyncio.wait_for(self.engine.client.history(job.prompt_id or ""), 30.0)
                except (asyncio.TimeoutError, httpx.HTTPError, OSError) as e:
                    if not await self._engine_alive():
                        job.error = f"engine process died ({type(e).__name__})"
                        return False
                    continue                                # wedged but alive: the stall timer decides
                if hist and hist.get("status", {}).get("completed"):
                    if hist["status"].get("status_str") == "success":
                        return True
                    msgs = [m for m in hist["status"].get("messages", []) if isinstance(m, list) and len(m) == 2]   # C15: keep the engine's words
                    err = next((m[1] for m in msgs if m[0] == "execution_error" and isinstance(m[1], dict)), None)
                    if any(m[0] == "execution_interrupted" for m in msgs):
                        job.error = "interrupted"
                    elif err:
                        job.error = f"{err.get('node_type')}: {err.get('exception_message')}"
                        job.log_tail += (err.get("traceback") or [])[-8:]
                    return False
                if not await self._engine_alive():
                    job.error = "engine process died"
                    return False
                continue
            t_last = time.time()
            if ev.type == "preview" and ev.binary:
                self.hub.broadcast_binary({"type": "job.preview", "job_id": job.id, "format": ev.data.get("format")}, ev.binary)
                continue
            if ev.prompt_id and ev.prompt_id != job.prompt_id:
                continue
            d = ev.data
            if ev.type == "executing":
                node = d.get("node")
                now = time.time()
                if last_node is not None and last_node in node_t0:
                    job.node_times[last_node] = round(job.node_times.get(last_node, 0) + now - node_t0[last_node], 2)
                if node is None:
                    last_node = None
                else:
                    node_t0[node] = now
                    last_node = node
                    job.progress_text = f"node {node}"
            elif ev.type == "progress":
                v, m = d.get("value", 0), d.get("max", 1) or 1
                job.progress = round(min(1.0, v / m), 3)
                job.progress_text = f"step {v}/{m}"
                self.hub.broadcast("job.progress", {"id": job.id, "progress": job.progress, "text": job.progress_text, "node": d.get("node")})
            elif ev.type == "execution_error":
                job.error = f"{d.get('node_type')}: {d.get('exception_message')}"
                job.log_tail += (d.get("traceback") or [])[-8:]
                return False
            elif ev.type == "execution_interrupted":
                job.error = "interrupted"
                return False
            elif ev.type == "execution_success":
                return True

    @staticmethod
    def _outputs_from_history(hist: dict | None) -> list[dict]:
        files: list[dict] = []
        for node_out in ((hist or {}).get("outputs") or {}).values():
            for key in ("images", "gifs", "videos"):
                for f in node_out.get(key, []) or []:
                    if f.get("type", "output") == "output":
                        files.append({"filename": f["filename"], "subfolder": f.get("subfolder", "")})
        return files
