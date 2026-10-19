"""D64: following one engine prompt — the WebSocket event pump, progress and node timings, the history poll fallback, the stall
watchdog that restarts a hung engine (06 §10), and the list of output files. Moved out of the queue unchanged; the queue keeps the
scheduling and the job states.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any, Callable

import httpx

from .client import EngineEvent

if TYPE_CHECKING:
    from ..queue import JobRecord

log = logging.getLogger("loom2.queue")


class EngineFollower:
    def __init__(self, engine: Any, hub: Any, settings: Callable[[], Any], on_stall: Callable[[], None]) -> None:
        self.engine, self.hub, self.settings, self.on_stall = engine, hub, settings, on_stall
        self.events: asyncio.Queue[EngineEvent] = asyncio.Queue()
        self._ws_task: asyncio.Task | None = None

    def stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None

    def drain(self) -> None:
        """Events left from an earlier prompt are not this job's."""
        while not self.events.empty():
            self.events.get_nowait()

    async def ensure_ws(self) -> None:
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._pump(), name="loom2-engine-ws")
            await asyncio.sleep(0.2)

    async def _pump(self) -> None:
        while True:
            try:
                async for ev in self.engine.client.events():
                    if ev.type == "ws_closed":
                        break
                    await self.events.put(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.debug("engine ws: %s", e)
            if not await self.alive():                 # C18: nothing to listen to — end the pump; ensure_ws restarts it with the next job
                return
            await asyncio.sleep(1.0)

    async def recover(self, job: JobRecord, why: str) -> None:
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
        self.on_stall()

    async def alive(self) -> bool:
        """Supervised: the process is alive. Adopted: it answers within 10 s (a slow answer counts as alive —
        ComfyUI's HTTP thread shares the GIL with a model load; a refused connection does not)."""
        proc = getattr(self.engine, "proc", None)
        if proc is not None:
            return proc.poll() is None
        try:
            return await asyncio.wait_for(self.engine.client.is_up(), 10.0)
        except asyncio.TimeoutError:
            return True

    async def free_cache(self) -> None:
        """After a document job: drop ComfyUI's cached outputs but keep the weights resident. Consecutive Klein jobs
        with alternating graphs (LanPaint / ICM) otherwise accumulate VRAM until the model streams from RAM."""
        try:
            await asyncio.wait_for(self.engine.client.free(unload_models=False, free_memory=True), 30.0)
        except Exception as e:  # noqa: BLE001
            log.warning("free_memory after job failed: %s", e)

    async def follow(self, job: JobRecord, idle_timeout_s: float | None = None) -> bool:
        """Consume engine events for this prompt until success / error / interrupt; poll history as a fallback.
        No event at all for `stall_timeout_s` (cold model loads take ≈ 2–3 min, a hung GPU never speaks again) fails
        the job and restarts the engine."""
        node_t0: dict[str, float] = {}
        last_node: str | None = None
        t_last = time.time()
        stall_s = float(idle_timeout_s or getattr(self.settings().engine, "stall_timeout_s", 420) or 420)
        poll_s = max(0.5, min(5.0, stall_s / 4))
        while True:
            try:
                ev = await asyncio.wait_for(self.events.get(), timeout=poll_s)
            except asyncio.TimeoutError:
                if time.time() - t_last > stall_s:
                    job.error = f"engine stalled: no progress for {int(stall_s)} s (GPU hang?) — engine restarted, queue paused"
                    await self.recover(job, job.error)
                    return False
                try:                                        # B4: a hung or refused poll is not a crash of the queue
                    hist = await asyncio.wait_for(self.engine.client.history(job.prompt_id or ""), 30.0)
                except (asyncio.TimeoutError, httpx.HTTPError, OSError) as e:
                    if not await self.alive():
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
                if not await self.alive():
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
    def outputs(hist: dict | None, text: bool = False) -> list[dict]:
        files: list[dict] = []
        for node_out in ((hist or {}).get("outputs") or {}).values():
            for key in ("images", "gifs", "videos", "3d", "meshes", "files"):                # P18: Save3DAdvanced reports its GLB under "3d" …
                for f in node_out.get(key, []) or []:
                    if isinstance(f, dict) and f.get("filename") and f.get("type", "output") == "output":   # … and a bare path list under "result" (skipped)
                        files.append({"filename": f["filename"], "subfolder": f.get("subfolder", "")})
            for t in (node_out.get("text", []) or []) if text else []:                     # CA1b: PreviewAny's text (the keypoints job only)
                if isinstance(t, str):
                    files.append({"text": t})
        return files
