"""D91 follow-up: `scripts/fetch_weights.py`'s stall watchdog — a transfer whose partial file stops growing is stopped and started again
(hf_hub_download resumes from its `.incomplete`), at most `--stall-retries` times, each one logged. Offline: fake downloads that stall."""
from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _fw():
    spec = importlib.util.spec_from_file_location("fetch_weights", REPO / "scripts" / "fetch_weights.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


fw = _fw()


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s


class Scripted:
    """A worker whose bytes follow a script per poll; `None` = finished. Stalls repeat the last value."""

    def __init__(self, sizes: list[int | None], disk: dict) -> None:
        self.sizes, self.disk, self.stopped = list(sizes), disk, False

    def alive(self) -> bool:
        if self.stopped:
            return False
        if self.sizes and self.sizes[0] is None:
            return False
        if self.sizes:
            self.disk["n"] = self.sizes.pop(0)
        return True

    def stop(self) -> None:
        self.stopped = True

    def result(self) -> str:
        return "done"


def test_no_stall_returns_the_result():
    clock, disk, logs = Clock(), {"n": 0}, []
    w = Scripted([10, 20, 30, None], disk)
    assert fw.watch(lambda: w, lambda: disk["n"], stall_s=120, poll_s=5, log=logs.append, clock=clock, sleep=clock.sleep) == "done"
    assert logs == []


def test_a_stall_restarts_and_the_resume_finishes():
    clock, disk, logs = Clock(), {"n": 0}, []
    # first attempt grows then sits at 8 for ever (open connection, no bytes); the second resumes from 8 and completes
    workers = iter([Scripted([4, 8] + [8] * 1000, disk), Scripted([12, 16, None], disk)])
    made = []

    def start():
        made.append(next(workers))
        return made[-1]

    assert fw.watch(start, lambda: disk["n"], stall_s=120, retries=3, poll_s=5, log=logs.append, clock=clock, sleep=clock.sleep) == "done"
    assert len(made) == 2 and made[0].stopped and not made[1].stopped
    assert len(logs) == 1 and "restart 1/3" in logs[0]
    assert 120 <= clock.t <= 140 + 15     # stopped once the window passed, not before


def test_gives_up_after_the_retries():
    clock, disk, logs = Clock(), {"n": 5}, []
    made = []

    def start():
        made.append(Scripted([5] * 1000, disk))
        return made[-1]

    with pytest.raises(fw.Stalled):
        fw.watch(start, lambda: disk["n"], stall_s=60, retries=2, poll_s=5, log=logs.append, clock=clock, sleep=clock.sleep)
    assert len(made) == 3 and all(w.stopped for w in made)
    assert [("restart 1/2" in m, "restart 2/2" in m, "giving up" in m) for m in logs] == [(True, False, False), (False, True, False), (False, False, True)]


def test_slow_growth_is_not_a_stall():
    clock, disk = Clock(), {"n": 0}
    w = Scripted([i // 30 for i in range(1, 400)] + [None], disk)    # one byte every 30 polls (150 s between changes would stall; 30 × 5 = 150)
    with pytest.raises(fw.Stalled):
        fw.watch(lambda: w, lambda: disk["n"], stall_s=120, retries=0, poll_s=5, log=lambda m: None, clock=clock, sleep=clock.sleep)
    w2 = Scripted([i // 20 for i in range(1, 400)] + [None], disk)   # a change every 100 s stays inside a 120 s window
    assert fw.watch(lambda: w2, lambda: disk["n"], stall_s=120, retries=0, poll_s=5, log=lambda m: None, clock=clock, sleep=clock.sleep) == "done"


class FileDownload:
    """A real thread writing a partial file in the staging folder: the first attempt stalls after half (the socket stays open), a restart
    resumes from the partial file's size — as hf_hub_download does from `.incomplete`."""

    attempts = 0

    def __init__(self, tmp: Path, total: int, stall_first: bool) -> None:
        FileDownload.attempts += 1
        self.part = tmp / ".cache" / "huggingface" / "download" / "abc.etag.incomplete"
        self.part.parent.mkdir(parents=True, exist_ok=True)
        self.final, self.total, self.halt = tmp / "model.safetensors", total, threading.Event()
        self.stall = stall_first and FileDownload.attempts == 1
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self) -> None:
        have = self.part.stat().st_size if self.part.exists() else 0
        with self.part.open("ab") as f:
            while have < self.total and not self.halt.is_set():
                if self.stall and have >= self.total // 2:
                    self.halt.wait()          # hangs until stopped
                    return
                f.write(b"x" * 1024)
                f.flush()
                have += 1024
                time.sleep(0.002)
        if have >= self.total:
            self.part.replace(self.final)

    def alive(self) -> bool:
        return self.t.is_alive()

    def stop(self) -> None:
        self.halt.set()
        self.t.join(5)

    def result(self) -> Path:
        assert self.final.is_file()
        return self.final


def test_file_backed_stall_resumes_from_the_partial_file(tmp_path):
    FileDownload.attempts = 0
    logs: list[str] = []
    out = fw.watch(lambda: FileDownload(tmp_path, 64 * 1024, stall_first=True), lambda: fw.staged_bytes(tmp_path),
                   stall_s=0.4, retries=2, poll_s=0.05, log=logs.append)
    assert out.stat().st_size == 64 * 1024                 # resumed, not restarted from zero (nothing appended twice)
    assert FileDownload.attempts == 2 and len(logs) == 1 and "restart 1/2" in logs[0]


def test_cli_has_the_flags():
    src = (REPO / "scripts" / "fetch_weights.py").read_text(encoding="utf-8")
    assert '"--stall-s"' in src and '"--stall-retries"' in src and "default=120.0" in src
