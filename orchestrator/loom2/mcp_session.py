"""The sibling engines' sessions beside the orchestrator (AE1 for EffectCraft, D114; CE1 for FilmCraft, D126): a pinned `<engine>-cli mcp`
(JSON-RPC 2.0 over stdio, one message a line) driven as one long-lived process. One request at a time; started on first use, restarted when
it dies (a subclass opens its project again); its stderr in the state's logs; a request past the timeout kills it. A `.py` in the engine's
Settings `cli` runs under this interpreter (the tests' fakes). Moved here from effectcraft.py when FilmCraft became the second user.
"""
from __future__ import annotations

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


class McpSessionError(RuntimeError):
    """The session refused a request (the engine's own message), timed out, or is not available."""


class McpSession:
    name = "engine"                                 # the log file's prefix and the messages' name
    build_script = "scripts/build_<engine>.py"
    Error: type[McpSessionError] = McpSessionError

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
        self.project: str | None = None            # the project file the session holds open (opened again after a restart)
        self.calls = 0

    # ---- what runs (a subclass says) --------------------------------------------------------------
    @property
    def settings(self):
        raise NotImplementedError

    def argv(self) -> list[str]:
        raise NotImplementedError

    def env(self) -> dict[str, str]:
        return {**os.environ, "RAYON_NUM_THREADS": str(self.settings.threads), "PYTHONIOENCODING": "utf-8"}

    def _started_locked(self, want: str | None) -> None:
        """After `initialize`: the subclass's setup, and the project it held opened again."""

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
            raise self.Error(f"{self.name} is not built: {self.settings.cli} is missing ({self.build_script})")
        self.app.logs_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.app.logs_dir / f"{self.name.lower()}-{time.strftime('%Y%m%d-%H%M%S')}.log"
        self._log_fh = self.log_path.open("ab")
        self._log_fh.write(f"==== launch {utc_now()} {' '.join(self.argv())}\n".encode("utf-8"))
        self._log_fh.flush()
        self.proc = subprocess.Popen(self.argv(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log_fh, env=self.env(),
                                     text=True, encoding="utf-8", bufsize=1)
        _assign_to_job(self.proc)                                  # the orchestrator's job object: a kill takes the session along
        self._replies = queue.Queue()
        threading.Thread(target=self._read, args=(self.proc, self._replies), daemon=True).start()
        self.started_at = time.time()
        self._n = 0
        want = self.project
        self.project = None
        self._call_locked("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "loom2", "version": "0"}})
        self._started_locked(want)

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
            raise self.Error(f"the {self.name} session is not running")
        self._n += 1
        n = self._n
        limit = self.settings.timeout_s if timeout is None else timeout
        try:
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": n, "method": method, "params": params or {}}) + "\n")
            p.stdin.flush()
        except (OSError, ValueError) as e:
            self.last_error = f"{method}: the session's pipe closed ({e})"
            raise self.Error(self.last_error) from e
        deadline = time.monotonic() + limit
        while True:
            try:
                msg = self._replies.get(timeout=max(0.0, deadline - time.monotonic()))
            except queue.Empty:
                self.last_error = f"{method} timed out after {limit:g} s; the session was stopped"
                self._cleanup_after_death()
                raise self.Error(self.last_error) from None
            if msg is None:
                self.last_error = f"{method}: the session ended"
                self._cleanup_after_death()
                raise self.Error(self.last_error)
            if msg.get("id") != n:
                continue                                           # a notification, or a reply to a request given up on
            self.calls += 1
            if "error" in msg:
                err = msg["error"]
                raise self.Error(f"{method}: {err.get('message', err) if isinstance(err, dict) else err}")
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
            raise self.Error(f"{name}: {text[:1500] or 'refused'}")
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
        """One engine command (`command_run`): its result, or the session's error with the engine's message."""
        return self.tool("command_run", {"id": cid, "params": params or {}})
