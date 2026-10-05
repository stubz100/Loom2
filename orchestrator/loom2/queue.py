"""Durable job queue (06 §3b, §7 durability; loom's runner.py rules with the domain stripped): one engine job at
a time, admitted by a VRAM estimate, persisted atomically to `<project>/jobs/queue.json` after every change,
reloaded on restart with running jobs re-queued, warm-group ordering, cancel via `/interrupt`.
"""
from __future__ import annotations

import asyncio
import logging
import time
import traceback
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .catalogue import Catalogue
from .config import AppState
from .engine.client import EngineError, EngineEvent
from .engine.graphs import compile_recipe, estimate_vram_gb
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .fsio import atomic_write_json, new_id, read_json_or, utc_now
from .recipes import parse_recipe, warm_group
from .roster import Roster
from .workspace import Workspace

log = logging.getLogger("loom2.queue")
QUEUE_SCHEMA_VERSION = 1
JobStatus = Literal["staged", "queued", "running", "done", "failed", "cancelled"]
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

    # ---- persistence ------------------------------------------------------------------------------
    def load(self) -> None:
        data = read_json_or(self.ws.queue_path, {"schema_version": QUEUE_SCHEMA_VERSION, "paused": False, "jobs": []})
        self.paused = bool(data.get("paused"))
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
        self._task = asyncio.create_task(self._run_loop(), name="loom2-queue")

    async def stop(self) -> None:
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
        running = self.jobs.get(self._running_id or "")
        if running and running.status == "running":
            running.status = "queued"           # a clean shutdown re-queues the interrupted job explicitly
            running.progress, running.prompt_id = 0.0, None
            try:
                await self.engine.client.interrupt()
            except Exception:
                pass
        self.persist(clean_shutdown=True)

    # ---- API --------------------------------------------------------------------------------------
    def submit(self, recipe_data: dict) -> list[JobRecord]:
        recipe = parse_recipe(recipe_data)
        seeds = recipe.seeds or [0]
        batch_id = new_id("bat") if len(seeds) > 1 else None
        out: list[JobRecord] = []
        for seed in seeds:
            seed = int(seed) if int(seed) > 0 else int(time.time_ns() % (2**32))
            rec = JobRecord(kind=recipe.kind, recipe=recipe.model_dump(), seed=seed, batch_id=batch_id,
                            vram_estimate_gb=estimate_vram_gb(recipe), warm_group=warm_group(recipe), variant=self.app.settings.variant)
            if rec.vram_estimate_gb > self.app.settings.vram_budget_gb:
                rec.status, rec.error, rec.finished_at = "failed", f"VRAM estimate {rec.vram_estimate_gb} GB exceeds the budget {self.app.settings.vram_budget_gb} GB", utc_now()
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
            try:
                await self.engine.client.interrupt()
            except Exception as e:
                log.warning("interrupt failed: %s", e)
            return True
        rec.status, rec.finished_at = "cancelled", utc_now()
        self.persist()
        self.hub.broadcast("job.updated", rec.model_dump())
        return True

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
                "resumed_unclean": self.resumed_unclean}

    # ---- scheduling -------------------------------------------------------------------------------
    def _next(self) -> JobRecord | None:
        queued = [j for j in self.jobs.values() if j.status == "queued"]
        if not queued:
            return None
        queued.sort(key=lambda j: j.created_at)
        same = [j for j in queued if j.warm_group == self._last_group]
        return same[0] if same else queued[0]

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

    async def _run_one(self, job: JobRecord) -> None:
        self._running_id = job.id
        self._t0 = time.time()
        job.status, job.started_at, job.progress, job.progress_text = "running", utc_now(), 0.0, "starting engine"
        self.persist()
        self.hub.broadcast("job.updated", job.model_dump())
        try:
            await self.engine.ensure_running()
            await self._ensure_ws()
            object_info = await self._object_info_fresh()
            recipe = parse_recipe(job.recipe)
            self.roster.scan()
            compiled = compile_recipe(recipe, self.roster, object_info, job.seed, out_prefix=f"loom2/{job.id}")
            if compiled.problems:
                self._fail(job, "contract: " + "; ".join(compiled.problems)[:1500])
                return
            job.log_tail += [f"resolved {n}" for n in compiled.notes]
            job.result["compiled"] = compiled.summary | {"graph_hash": compiled.graph_hash}
            self.ws.engine_out_dir.mkdir(exist_ok=True)
            while not self._events.empty():
                self._events.get_nowait()
            job.prompt_id = await self.engine.client.queue_prompt(compiled.graph)
            job.progress_text = "queued on engine"
            self.hub.broadcast("job.updated", job.model_dump())
            ok = await self._follow(job)
            if job.id in self._cancel_requested or not ok and job.error == "interrupted":
                self._cancel_requested.discard(job.id)
                job.status, job.finished_at, job.error = "cancelled", utc_now(), None
                job.wall_s = round(time.time() - self._t0, 1)
                self.catalogue.record_job(job.model_dump())
                self.persist()
                self.hub.broadcast("job.updated", job.model_dump())
                return
            if not ok:
                self._fail(job, job.error or "engine reported an error")
                return
            hist = await self.engine.client.history(job.prompt_id)
            files = self._outputs_from_history(hist)
            if not files:
                self._fail(job, "the engine finished but produced no output files")
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
                    prompt_text=getattr(recipe, "prompt_text", None), prompt_json=getattr(recipe, "prompt_json", None),
                    params=compiled.summary, timings={"wall_s": round(time.time() - self._t0, 1), "node_s": job.node_times},
                    compiled_graph_hash=compiled.graph_hash, variant=job.variant, parents=list(getattr(recipe, "refs", []) or []))
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

    async def _follow(self, job: JobRecord, idle_timeout_s: float = 900.0) -> bool:
        """Consume engine events for this prompt until success / error / interrupt; poll history as a fallback."""
        node_t0: dict[str, float] = {}
        last_node: str | None = None
        t_last = time.time()
        while True:
            try:
                ev = await asyncio.wait_for(self._events.get(), timeout=5.0)
            except asyncio.TimeoutError:
                if time.time() - t_last > idle_timeout_s:
                    job.error = "engine went silent"
                    return False
                hist = await self.engine.client.history(job.prompt_id or "")
                if hist and hist.get("status", {}).get("completed"):
                    return hist["status"].get("status_str") == "success"
                if not await self.engine.client.is_up():
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
