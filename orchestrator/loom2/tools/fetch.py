"""Weight fetch and verify (04 §1b, the roster tool): `hf_hub_download` into `<models>/_incoming`, sha256, move
into the ComfyUI folder, append to `roster.index.json` — the same ledger `scripts/fetch_weights.py` writes, so
both tools agree. Runs in a thread; progress is reported from the growing file size.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from ..events import EventHub
from ..fsio import replace
from ..roster import RosterEntry


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(16 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_ledger(models_root: Path, entry: RosterEntry, dest: Path, digest: str) -> None:
    index_path = models_root / "roster.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}
    index["files"] = [f for f in index["files"] if f["path"] != str(dest)] + [dict(
        path=str(dest), folder=entry.folder, repo=entry.repo, file=entry.file, size=dest.stat().st_size, sha256=digest,
        license=entry.license, spike="app", fetched=time.strftime("%Y-%m-%d %H:%M:%S"))]
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=1), encoding="utf-8")
    replace(tmp, index_path)


class FetchJob:
    def __init__(self, entry: RosterEntry, models_root: Path, hub: EventHub, hf_home: str | None = None) -> None:
        self.entry, self.models_root, self.hub, self.hf_home = entry, Path(models_root), hub, hf_home
        self.status = "queued"
        self.error: str | None = None
        self.bytes_done = 0
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self._task: asyncio.Task | None = None
        self.dest = self.models_root / entry.folder / entry.name

    def state(self) -> dict:
        total = int((self.entry.approx_gb or 0) * 2**30)
        return {"model_id": self.entry.id, "name": self.entry.name, "status": self.status, "error": self.error,
                "bytes_done": self.bytes_done, "bytes_total_est": total,
                "progress": round(min(1.0, self.bytes_done / total), 3) if total else None,
                "elapsed_s": round((self.finished_at or time.time()) - self.started_at, 1) if self.started_at else 0}

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"fetch-{self.entry.id}")

    def _download(self) -> Path:
        from huggingface_hub import hf_hub_download
        if self.hf_home:
            os.environ.setdefault("HF_HOME", self.hf_home)
        tmp = self.models_root / "_incoming"
        tmp.mkdir(parents=True, exist_ok=True)
        local = Path(hf_hub_download(self.entry.repo, self.entry.file, local_dir=str(tmp), token=True))  # type: ignore[arg-type]
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        if self.dest.exists():
            self.dest.unlink()
        shutil.move(str(local), str(self.dest))
        return self.dest

    async def _run(self) -> None:
        self.status, self.started_at = "downloading", time.time()
        self.hub.broadcast("model.fetch", self.state())
        if not self.entry.repo or not self.entry.file:
            self.status, self.error = "failed", "roster entry has no fetch source"
            self.hub.broadcast("model.fetch", self.state())
            return
        work = asyncio.create_task(asyncio.to_thread(self._download))
        incoming = self.models_root / "_incoming"
        try:
            while not work.done():
                await asyncio.sleep(2.0)
                try:
                    cand = [p for p in incoming.rglob("*") if p.is_file() and self.entry.name.split(".")[0] in p.name]
                    self.bytes_done = max((p.stat().st_size for p in cand), default=self.bytes_done)
                except OSError:
                    pass
                self.hub.broadcast("model.fetch", self.state())
            dest = await work
            self.status = "hashing"
            self.hub.broadcast("model.fetch", self.state())
            digest = await asyncio.to_thread(sha256_of, dest)
            await asyncio.to_thread(_append_ledger, self.models_root, self.entry, dest, digest)
            self.bytes_done = dest.stat().st_size
            self.status = "done"
        except Exception as e:
            self.status, self.error = "failed", f"{type(e).__name__}: {e}"
        finally:
            self.finished_at = time.time()
            self.hub.broadcast("model.fetch", self.state())
