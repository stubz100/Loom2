"""The managed ComfyUI process (06 §3b): start with the pinned flags, probe health, restart on failure or every N
jobs, and make sure it dies with the orchestrator (Windows Job Object with kill-on-close; `taskkill /T` as the
belt to the braces because the uv venv launcher spawns the real interpreter as a child).
"""
from __future__ import annotations

import asyncio
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from ..config import AppState
from .client import ComfyClient, wait_for_engine

IS_WINDOWS = sys.platform.startswith("win")


def _make_kill_on_close_job():
    """A Job Object whose processes are killed when the last handle closes (i.e. when we die)."""
    if not IS_WINDOWS:
        return None
    try:
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                           "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32), ("SchedulingClass", ctypes.c_uint32)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # JobObjectExtendedLimitInformation
            k32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


_JOB = _make_kill_on_close_job()


def _assign_to_job(proc: subprocess.Popen) -> bool:
    if _JOB is None or not IS_WINDOWS:
        return False
    try:
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        return bool(k32.AssignProcessToJobObject(_JOB, int(proc._handle)))  # type: ignore[attr-defined]
    except Exception:
        return False


def _kill_tree(pid: int) -> None:
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


class EngineSupervisor:
    def __init__(self, app: AppState, on_state: Callable[[dict], None] | None = None) -> None:
        self.app = app
        self.on_state = on_state
        self.proc: subprocess.Popen | None = None
        self.client = ComfyClient(app.settings.engine.host, app.settings.engine.port)
        self.started_at: float | None = None
        self.jobs_since_start = 0
        self.restarts = 0
        self.last_error: str | None = None
        self.log_path: Path | None = None
        self._log_fh = None
        self._lock = asyncio.Lock()
        self.version: dict | None = None
        self.in_job_object = False

    # ---- state ------------------------------------------------------------------------------------
    def state(self) -> dict:
        alive = self.proc is not None and self.proc.poll() is None
        return {
            "running": alive, "pid": self.proc.pid if alive and self.proc else None,
            "port": self.app.settings.engine.port, "started_at": self.started_at, "uptime_s": round(time.time() - self.started_at, 1) if alive and self.started_at else None,
            "jobs_since_start": self.jobs_since_start, "restarts": self.restarts, "last_error": self.last_error,
            "log": str(self.log_path) if self.log_path else None, "version": self.version, "job_object": alive and self.in_job_object,
        }

    def _emit(self) -> None:
        if self.on_state:
            self.on_state(self.state())

    # ---- lifecycle --------------------------------------------------------------------------------
    def _argv(self) -> list[str]:
        e = self.app.settings.engine
        state = self.app.state_dir
        reserve = [] if "--reserve-vram" in e.flags or not e.reserve_vram_gb else ["--reserve-vram", str(float(e.reserve_vram_gb))]
        return [e.python, e.main, "--listen", e.host, "--port", str(e.port), *e.flags, *reserve, "--log-stdout",
                "--extra-model-paths-config", e.extra_model_paths,
                "--output-directory", str(state / "engine_out"), "--temp-directory", str(state / "engine_tmp"),
                "--user-directory", str(state / "engine_user")]

    async def start(self) -> dict:
        async with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                return self.state()
            if await self.client.is_up():
                # an engine already listens on our port (e.g. started by a script) — adopt it read-only
                self.last_error = "adopted an engine that was already listening; not supervised"
                self.version = (await self.client.system_stats()).get("system")
                self._emit()
                return self.state()
            e = self.app.settings.engine
            for d in ("engine_out", "engine_tmp", "engine_user"):
                (self.app.state_dir / d).mkdir(parents=True, exist_ok=True)
            self.log_path = self.app.logs_dir / f"engine-{time.strftime('%Y%m%d-%H%M%S')}.log"
            self._log_fh = self.log_path.open("ab")
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "HF_HUB_OFFLINE": "1"}
            try:
                self.proc = subprocess.Popen(self._argv(), cwd=str(Path(e.main).parent), stdout=self._log_fh, stderr=subprocess.STDOUT, env=env,
                                             creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if IS_WINDOWS else 0))
            except Exception as ex:
                self._log_fh.close()
                self._log_fh = None
                self.last_error = f"engine could not be launched: {ex}"
                self._emit()
                raise
            self.in_job_object = _assign_to_job(self.proc)
            self.started_at = time.time()
            self.jobs_since_start = 0
            self.last_error = None
            self._emit()
            ok = await wait_for_engine(self.client, timeout_s=e.health_timeout_s)
            if not ok:
                self.last_error = f"engine did not answer within {e.health_timeout_s:.0f} s (see {self.log_path})"
                await self._stop_locked()        # B1: never re-enter the lock we hold (asyncio.Lock is not reentrant)
                raise RuntimeError(self.last_error)
            self.version = (await self.client.system_stats()).get("system")
            self._emit()
            return self.state()

    async def stop(self, grace_s: float = 10.0) -> dict:
        async with self._lock:
            return await self._stop_locked(grace_s)

    async def _stop_locked(self, grace_s: float = 10.0) -> dict:
        """The body of `stop()`; callers must hold `self._lock`."""
        proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                await asyncio.wait_for(asyncio.to_thread(self._stop_proc, proc, grace_s), timeout=grace_s + 15)
            except asyncio.TimeoutError:
                _kill_tree(proc.pid)
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None
        self.started_at = None
        self.in_job_object = False
        self._emit()
        return self.state()

    def reconfigure(self) -> None:
        """Settings changed (B7): follow a new engine host/port while no supervised process is alive."""
        e = self.app.settings.engine
        alive = self.proc is not None and self.proc.poll() is None
        if not alive and (self.client.host, self.client.port) != (e.host, e.port):
            old, self.client = self.client, ComfyClient(e.host, e.port)
            asyncio.get_running_loop().create_task(old.aclose())

    @staticmethod
    def _stop_proc(proc: subprocess.Popen, grace_s: float) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=grace_s)
        except Exception:
            pass
        _kill_tree(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    async def restart(self) -> dict:
        await self.stop()
        self.restarts += 1
        return await self.start()

    async def ensure_running(self) -> None:
        """Called by the queue before every job: (re)start if dead or if the restart-every-N policy says so."""
        e = self.app.settings.engine
        alive = self.proc is not None and self.proc.poll() is None
        if alive and e.restart_every_jobs and self.jobs_since_start >= e.restart_every_jobs:
            await self.restart()
            return
        if not alive and not await self.client.is_up():
            if self.proc is not None:
                self.restarts += 1
            await self.start()

    async def health(self) -> dict:
        up = await self.client.is_up()
        s = self.state()
        s["responding"] = up
        if up:
            try:
                stats = await self.client.system_stats()
                dev = (stats.get("devices") or [{}])[0]
                s["vram_free_gb"] = round(dev.get("vram_free", 0) / 2**30, 2)
                s["vram_total_gb"] = round(dev.get("vram_total", 0) / 2**30, 2)
            except Exception:
                pass
        return s
