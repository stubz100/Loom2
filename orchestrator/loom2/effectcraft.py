"""AE1 (proto01_animate 20 §2, D114): the EffectCraft session beside the orchestrator — the pinned `effectcraft-cli mcp` (JSON-RPC 2.0 over
stdio, one message a line) driven as the animation editor's engine: every engine command, a frame as PNG at any size, the project saved
through a copy. One request at a time (the session is single-threaded and a frame is ≈ 60 ms, E27); started on first use, restarted when
it dies (the project it held is opened again); its stderr in the state's logs. The binary comes from engine/effectcraft.pin.json through
scripts/build_effectcraft.py (engine/tools/, never in git); a `.py` in Settings › effectcraft.cli runs under this interpreter (the tests'
fake, orchestrator/tests/fake_effectcraft.py).
"""
from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .config import AppState
from .engine.supervisor import _assign_to_job
from .fsio import utc_now

PROTOCOL = "2025-06-18"


def cli_head(settings) -> list[str]:
    """The pinned CLI, or the tests' fake under this interpreter."""
    cli = settings.cli
    return [sys.executable, cli] if cli.lower().endswith(".py") else [cli]


def render_argv(settings, project: Path, comp: str, out_pattern: Path) -> list[str]:
    """`effectcraft-cli render`: the composition at Best and Full as a PNG sequence (E27's R2, equal to the preview to 0/255)."""
    if not Path(settings.cli).is_file():
        raise ValueError(f"EffectCraft is not built: {settings.cli} is missing (scripts/build_effectcraft.py)")
    return [*cli_head(settings), "render", "--project", str(project), "--comp", comp, "--out", str(out_pattern), "--format", "png", "--quality", "best",
            "--resolution", "full", "--channels", "rgb"]


class EffectCraftError(RuntimeError):
    """The session refused a request (the engine's own message), timed out, or is not available."""


class EffectCraft:
    def __init__(self, app: AppState) -> None:
        self.app = app
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._replies: queue.Queue = queue.Queue()
        self._n = 0
        self.started_at: float | None = None
        self.restarts = 0
        self.last_error: str | None = None
        self.log_path: Path | None = None
        self._log_fh = None
        self.project: str | None = None            # the .ecproj the session holds open (opened again after a restart)
        self.calls = 0

    # ---- what runs --------------------------------------------------------------------------------
    @property
    def settings(self):
        return self.app.settings.effectcraft

    def argv(self) -> list[str]:
        return [*cli_head(self.settings), "mcp", "--empty"]

    def available(self) -> bool:
        return Path(self.settings.cli).is_file()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def state(self) -> dict:
        alive = self.alive()
        return {"running": alive, "pid": self.proc.pid if alive and self.proc else None, "available": self.available(), "project": self.project,
                "started_at": self.started_at, "restarts": self.restarts, "calls": self.calls, "threads": self.settings.threads,
                "last_error": self.last_error, "log": str(self.log_path) if self.log_path else None}

    # ---- lifecycle --------------------------------------------------------------------------------
    def ensure(self) -> None:
        """Start the session when it is not running (the first use, or after it died)."""
        with self._lock:
            self._ensure_locked()

    def _ensure_locked(self) -> None:
        if self.alive():
            return
        if self.proc is not None:                                  # it died (or was killed after a timeout): note it, start again
            self.restarts += 1
            self._cleanup()
        if not self.available():
            raise EffectCraftError(f"EffectCraft is not built: {self.settings.cli} is missing (scripts/build_effectcraft.py)")
        env = {**os.environ, "RAYON_NUM_THREADS": str(self.settings.threads), "WGPU_BACKEND": "vulkan", "PYTHONIOENCODING": "utf-8"}
        self.app.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.app.logs_dir / f"effectcraft-{time.strftime('%Y%m%d-%H%M%S')}.log"
        self._log_fh = self.log_path.open("ab")
        self._log_fh.write(f"==== launch {utc_now()} {' '.join(self.argv())}\n".encode("utf-8"))
        self._log_fh.flush()
        self.proc = subprocess.Popen(self.argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log_fh, env=env,
                                     text=True, encoding="utf-8", bufsize=1)
        _assign_to_job(self.proc)                                  # the orchestrator's job object: a kill takes the session along
        self._replies = queue.Queue()
        threading.Thread(target=self._read, args=(self.proc, self._replies), daemon=True).start()
        self.started_at = time.time()
        self._n = 0
        want = self.project
        self.project = None
        self._call_locked("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "loom2", "version": "0"}})
        if want:
            self._tool_locked("open_project", {"path": want})
            self.project = want

    @staticmethod
    def _read(proc: subprocess.Popen, out: queue.Queue) -> None:
        try:
            for line in proc.stdout:                               # type: ignore[union-attr]
                line = line.strip()
                if not line:
                    continue
                try:
                    out.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        finally:
            out.put(None)                                          # EOF: the session is gone

    def _cleanup(self) -> None:
        if self.proc is not None:
            try:
                if self.proc.poll() is None:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        self.proc = None
        if self._log_fh:
            try:
                self._log_fh.close()
            except OSError:
                pass
            self._log_fh = None

    def stop(self) -> None:
        """End the session (the orchestrator's shutdown); not counted as a death."""
        with self._lock:
            p = self.proc
            if p is None:
                return
            try:
                if p.poll() is None and p.stdin:
                    p.stdin.close()                                # closing stdin lets the server finish and exit
                    p.wait(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            self._cleanup()
            self.project = None

    # ---- requests ---------------------------------------------------------------------------------
    def _call_locked(self, method: str, params: dict | None, timeout: float | None = None) -> Any:
        p = self.proc
        if p is None or p.stdin is None:
            raise EffectCraftError("the EffectCraft session is not running")
        self._n += 1
        n = self._n
        limit = self.settings.timeout_s if timeout is None else timeout
        try:
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": n, "method": method, "params": params or {}}) + "\n")
            p.stdin.flush()
        except (OSError, ValueError) as e:
            self.last_error = f"{method}: the session's pipe closed ({e})"
            raise EffectCraftError(self.last_error) from e
        deadline = time.monotonic() + limit
        while True:
            try:
                msg = self._replies.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                self.last_error = f"{method} timed out after {limit:g} s; the session was stopped"
                self._cleanup_after_death()
                raise EffectCraftError(self.last_error) from None
            if msg is None:
                self.last_error = f"{method}: the session ended"
                self._cleanup_after_death()
                raise EffectCraftError(self.last_error)
            if msg.get("id") != n:
                continue                                           # a notification, or a reply to a request given up on
            self.calls += 1
            if "error" in msg:
                err = msg["error"]
                raise EffectCraftError(f"{method}: {err.get('message', err) if isinstance(err, dict) else err}")
            return msg.get("result")

    def _cleanup_after_death(self) -> None:
        """Leave the dead process noted so the next `ensure` counts the restart."""
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def _tool_locked(self, name: str, args: dict) -> Any:
        r = self._call_locked("tools/call", {"name": name, "arguments": args})
        content = (r or {}).get("content") or []
        text = next((c.get("text", "") for c in content if c.get("type") == "text"), "")
        if (r or {}).get("isError"):
            raise EffectCraftError(f"{name}: {text[:1500] or 'refused'}")
        if any(c.get("type") == "image" for c in content):
            return content
        try:
            return json.loads(text) if text else {}
        except json.JSONDecodeError:
            return {"text": text}

    def call(self, method: str, params: dict | None = None, timeout: float | None = None) -> Any:
        with self._lock:
            self._ensure_locked()
            return self._call_locked(method, params, timeout)

    def tool(self, name: str, args: dict | None = None) -> Any:
        with self._lock:
            self._ensure_locked()
            return self._tool_locked(name, args or {})

    def command(self, cid: str, params: dict | None = None) -> Any:
        """One engine command (`command_run`): its result, or an EffectCraftError with the engine's message."""
        return self.tool("command_run", {"id": cid, "params": params or {}})

    def open(self, path: str | Path) -> None:
        """Hold this .ecproj open in the session (a no-op when it already is)."""
        path = str(path)
        with self._lock:
            self._ensure_locked()
            if self.project == path:
                return
            self._tool_locked("open_project", {"path": path})
            self.project = path

    def frame(self, time_s: float, max_side: int = 0, comp: str | int | None = None, transparent: bool = False) -> bytes:
        """A frame of the open project's composition as PNG (`max_side` 0 = full size)."""
        args: dict[str, Any] = {"time": float(time_s), "max_side": int(max_side), "transparent": bool(transparent)}
        if comp is not None:
            args["comp"] = comp
        content = self.tool("render_frame", args)
        img = next((c for c in content if c.get("type") == "image"), None) if isinstance(content, list) else None
        if not img:
            raise EffectCraftError("render_frame returned no image")
        return base64.b64decode(img["data"])

    def save_copy(self, path: str | Path) -> None:
        """Write the session's project to `path` without changing which file it holds (the caller replaces atomically, fsio)."""
        self.command("file.saveCopy", {"path": str(path)})
