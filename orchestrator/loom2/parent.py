"""V54: a process that must not outlive its parent — the e2e runner starts the orchestrator and the fake engine without a job object
(Node has none), so a killed run left them behind; `--parent-pid` watches the parent and ends the process when it is gone."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

STILL_ACTIVE = 259
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def process_alive(pid: int) -> bool:
    """Whether `pid` is a running process (Windows: its exit code is STILL_ACTIVE; elsewhere: signal 0 reaches it)."""
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def watch_parent(pid: int, on_gone: Callable[[], None], interval_s: float = 1.0) -> threading.Thread:
    """A daemon thread that calls `on_gone` once, when `pid` is no longer running."""
    def run() -> None:
        while True:
            time.sleep(interval_s)
            if not process_alive(pid):
                on_gone()
                return
    t = threading.Thread(target=run, name="loom2-parent-watch", daemon=True)
    t.start()
    return t
