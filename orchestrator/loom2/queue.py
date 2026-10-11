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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .catalogue import Catalogue
from .config import AppState
from .engine.client import EngineError
from .engine.follow import EngineFollower
from .engine.finishers import finisher_for, run_quick_remove
from .engine.graphs import CompileError, estimate_vram_gb, recipe_te_id, recipe_weights
from .models import registry
from .engine.pipeline import JobCancelled, finalize, plan
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .fsio import StateError, atomic_write_json, free_space_gb, new_id, read_json_or, utc_now
from .recipes import T2I, I2V, Inpaint, parse_recipe, warm_group
from .documents import DocumentStore
from . import native
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
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
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
        self.follower = EngineFollower(engine, hub, lambda: self.app.settings, self.pause)    # D64: engine/follow.py
        self._cancel_requested: set[str] = set()
        self._t0 = time.time()
        self._pending: dict | None = None        # D64: the newest queue snapshot waiting for the writer
        self._writer: asyncio.Task | None = None
        self._write_error: OSError | None = None
        self._roster_stamp: tuple | None = None   # D64: the model roots' mtimes at the last scan
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
        self.persist(sync=True)

    def persist(self, clean_shutdown: bool = False, sync: bool = False) -> None:
        """D64: the queue is written off the event loop. The snapshot is taken now (write order is call order); one writer task writes
        the newest snapshot in a thread (`fsio.replace` may retry for ~0.6 s under antivirus locks). Without a running loop, and for the
        shutdown mark and `sync` (the load at start, before any writer exists), the write is synchronous. `await flush()` where the state
        must be on disk before going on."""
        snap = {"schema_version": QUEUE_SCHEMA_VERSION, "paused": self.paused, "clean_shutdown": clean_shutdown, "saved_at": utc_now(),
                "jobs": [j.model_dump() for j in self.jobs.values()]}
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None or clean_shutdown or (sync and (self._writer is None or self._writer.done())):
            self._pending = None
            atomic_write_json(self.ws.queue_path, snap)
            return
        self._pending = snap
        if self._writer is None or self._writer.done():
            self._writer = loop.create_task(self._write_pending(), name="loom2-queue-writer")

    async def _write_pending(self) -> None:
        while self._pending is not None:
            snap, self._pending = self._pending, None
            try:
                await asyncio.to_thread(atomic_write_json, self.ws.queue_path, snap)
                self._write_error = None
            except OSError as e:
                self._write_error = e
                log.error("cannot write the queue file: %s", e)

    async def flush(self) -> None:
        """Wait until every persist() so far is on disk; raises the writer's OSError (a full disk) once."""
        while self._writer is not None and not self._writer.done():
            await asyncio.shield(self._writer)
        if self._write_error is not None:
            e, self._write_error = self._write_error, None
            raise e

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
        self.follower.stop()
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
        try:
            await self.flush()
        except OSError:
            pass
        self.persist(clean_shutdown=True)

    # ---- API --------------------------------------------------------------------------------------
    def submit(self, recipe_data: dict, stage: bool = False) -> list[JobRecord]:
        recipe = parse_recipe(recipe_data)
        self._validate_models(recipe)
        plan(recipe, self.app.settings.variant)          # D65: a size off the grid (size_policy error), a bad sampler … → 422 here
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

    def estimate(self, recipe: Any) -> dict:
        p = plan(recipe, self.app.settings.variant, self.timing_history())
        est, vram = dict(p.estimate), p.vram_gb
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
        if isinstance(recipe, Inpaint) and (recipe.mode == "quick_remove" or recipe.prefill) and not native.available():
            # R9: a missing native extension is refused at submission (HTTP 422), not when the job runs
            what = "Quick Remove" if recipe.mode == "quick_remove" else "the content-aware pre-fill"
            raise ValueError(f"{what} needs the native extension (uv sync --project orchestrator --extra native)")
        if isinstance(recipe, Inpaint) and recipe.mode == "quick_remove":
            return                       # R3: CPU only — no model is loaded, so neither the roster nor the open-variant gate applies
        for mid in [recipe.model_id, *[l.model_id for l in getattr(recipe, "loras", [])], *([recipe.te_id] if getattr(recipe, "te_id", None) else [])]:
            if mid not in ROSTER_BY_ID:
                raise ValueError(f"unknown model id {mid!r}")
        spec = registry.get(recipe.model_id)
        if isinstance(recipe, T2I) and (spec is None or not spec.recipes.t2i):
            raise ValueError(f"no t2i preset for {recipe.model_id!r}")
        if getattr(recipe, "te_id", None):
            try:
                recipe_te_id(recipe, self.app.settings.variant)          # the encoder must pair with the model (TE_ALTERNATES)
            except CompileError as e:
                raise ValueError(str(e))
        if isinstance(recipe, I2V):
            if spec is None or not spec.recipes.i2v:
                raise ValueError(f"{recipe.model_id!r} is not an image-to-video model (Wan 2.2 or LTX-2.3)")
            if recipe.beats and not spec.recipes.beats:
                raise ValueError(f"keyframe beats need a model that takes them ({', '.join(s.label for s in registry.video_specs() if s.recipes.beats)}); {spec.label} takes a start and an end frame")
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

    async def object_info_fresh(self) -> dict:
        if self._object_info is None or (self.engine.started_at and (self._object_info_at or 0) < self.engine.started_at):
            self._object_info = await self.engine.client.object_info()
            self._object_info_at = time.time()
        return self._object_info

    async def object_info_refresh(self) -> dict:
        """After uploads: the new names appear in LoadImage's enum only after a refresh (E8)."""
        self._object_info = await self.engine.client.object_info()
        self._object_info_at = time.time()
        return self._object_info

    def object_info_cached(self) -> dict | None:
        """The engine's last answer, for /recipes/preview's contract check (None before the first job)."""
        return self._object_info

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

    # ---- helpers the pipeline and the finishers call (D64) ------------------------------------------
    def wall_s(self) -> float:
        return round(time.time() - self._t0, 1)

    def progress(self, job: JobRecord, text: str) -> None:
        job.progress_text = text
        self.hub.broadcast("job.updated", job.model_dump())

    def check_cancel(self, job: JobRecord) -> None:
        """B5: a cancel that arrived while the job was preparing ends it here."""
        if job.id in self._cancel_requested:
            raise JobCancelled(job.id)

    async def irreversible(self, job: JobRecord) -> None:
        """C8: from here the job's work must never run twice — on disk before its outputs are written."""
        job.resumable = False
        self.persist()
        await self.flush()

    def side(self, coro: Any) -> None:
        tasks: set = getattr(self, "_side_tasks", None) or set()
        self._side_tasks = tasks
        t = asyncio.get_running_loop().create_task(coro)
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    def _complete(self, job: JobRecord, engine: bool = True) -> None:
        """The one completion tail (D64): done fields, the index, the queue file, the event, the warm group."""
        job.status, job.finished_at, job.progress, job.progress_text = "done", utc_now(), 1.0, "done"
        job.wall_s = self.wall_s()
        self.catalogue.record_job(job.model_dump())
        self.persist()
        self.hub.broadcast("job.updated", job.model_dump())
        if engine:
            self.engine.jobs_since_start += 1
            self._last_group = job.warm_group

    async def _scan_roster(self) -> None:
        """D64: the model trees are walked at the first job and whenever a root's mtime changed (a fetch, a delete), not per job."""
        def stamp_now() -> tuple:
            out = []
            for root in [self.roster.models_root, *self.roster.mounted]:     # a weight lands in a folder: that folder's mtime moves
                if root.is_dir():
                    out += [(str(d), d.stat().st_mtime_ns) for d in [root, *root.iterdir()] if d.is_dir()]
            return tuple(out)
        stamp = await asyncio.to_thread(stamp_now)
        if stamp != self._roster_stamp or self.roster.scanned_at is None:
            await asyncio.to_thread(self.roster.scan)                  # C7: the mounted trees can be large
            self._roster_stamp = stamp

    async def _run_one(self, job: JobRecord) -> None:
        """plan → finalize → submit → follow → finish → complete (D64)."""
        self._running_id = job.id
        self._t0 = time.time()
        job.status, job.started_at, job.progress, job.progress_text = "running", utc_now(), 0.0, "starting engine"
        try:
            self.persist()
            await self.flush()
        except OSError as e:                        # B12 (review): a full disk must not leave a phantom running job
            job.status, job.started_at = "queued", None
            self._running_id = None
            log.error("cannot persist the queue (%s); pausing", e)
            self.paused = True
            return
        self.hub.broadcast("job.updated", job.model_dump())
        try:
            recipe = parse_recipe(job.recipe)
            if not plan(recipe, job.variant).engine:                    # D62 Quick Remove: CPU only — the engine is not started
                await run_quick_remove(job, recipe, self)
                self._complete(job, engine=False)
                return
            try:
                await self.engine.ensure_running()
            except (RuntimeError, OSError) as e:                        # C2: launch failure → hold the queue, keep the job
                self._engine_unavailable(job, f"engine could not start: {e}")
                return
            await self.follower.ensure_ws()
            self.check_cancel(job)
            await self._scan_roster()
            sub = await finalize(job, recipe, self)
            if sub.compiled.problems:
                self._fail(job, "contract: " + "; ".join(sub.compiled.problems)[:1500])
                return
            job.log_tail += [f"resolved {n}" for n in sub.compiled.notes]
            job.result["compiled"] = sub.compiled.summary | {"graph_hash": sub.compiled.graph_hash}
            job.result["serialized_prompt"] = sub.compiled.serialized_prompt
            self.follower.drain()
            self.check_cancel(job)
            job.prompt_id = await self.engine.client.queue_prompt(sub.compiled.graph)
            if job.id in self._cancel_requested:            # cancel() saw no prompt_id yet: interrupt what we just queued
                try:
                    await self.engine.client.interrupt()
                except Exception as e:  # noqa: BLE001
                    log.warning("interrupt failed: %s", e)
            self.progress(job, "queued on engine")
            ok = await self.follower.follow(job)
            if job.id in self._cancel_requested or not ok and job.error == "interrupted":
                self._finish_cancelled(job)
                return
            if not ok:
                self._fail(job, job.error or "engine reported an error")
                return
            await self.irreversible(job)                     # C8: the engine's work is done; what follows must never run twice
            files = self.follower.outputs(await self.engine.client.history(job.prompt_id))
            if not files:
                self._fail(job, "the engine finished but produced no output files")
                return
            fin = finisher_for(recipe)
            await fin.finish(job, recipe, files, sub, self)
            if fin.frees_cache:
                await self.follower.free_cache()
            self._complete(job)
        except JobCancelled:
            self._finish_cancelled(job)
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
                self._cancel_requested.discard(job.id)       # R4: a cancel that lost the race to the end of the job is not kept
                self._cleanup_job_files(job)

