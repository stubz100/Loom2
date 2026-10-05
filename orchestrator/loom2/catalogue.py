"""Assets, manifests, lineage and the rebuildable SQLite index (06 §4–§5). The files and their sidecar manifests
are the truth; `catalogue.sqlite` is an index that `rebuild()` can regenerate from the sidecars.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, Field

from .fsio import atomic_move, atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

ASSET_SCHEMA_VERSION = 1
AssetKind = Literal["image", "video", "mask", "document-render"]
AssetState = Literal["none", "keep", "reject"]


class AssetRecord(BaseModel):
    schema_version: int = ASSET_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("ast"))
    kind: AssetKind = "image"
    path: str                                   # project-relative, forward slashes
    w: int | None = None
    h: int | None = None
    frames: int | None = None
    fps: float | None = None
    created_at: str = Field(default_factory=utc_now)
    job_id: str | None = None
    batch_id: str | None = None
    parents: list[str] = Field(default_factory=list)
    suite: str = "generate"
    model_id: str | None = None
    format: str | None = None
    seed: int | None = None
    prompt_text: str | None = None
    prompt_json: dict | None = None
    params: dict = Field(default_factory=dict)
    timings: dict = Field(default_factory=dict)
    compiled_graph_hash: str | None = None
    variant: str = "full"
    state: AssetState = "none"
    rating: int = 0
    tags: list[str] = Field(default_factory=list)
    collection_ids: list[str] = Field(default_factory=list)
    thumb_status: Literal["pending", "done", "failed"] = "pending"
    bytes: int | None = None
    sha256: str | None = None


_DDL = """
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, kind TEXT, path TEXT, w INTEGER, h INTEGER, frames INTEGER, created_at TEXT, job_id TEXT, batch_id TEXT,
  model_id TEXT, seed INTEGER, prompt_text TEXT, suite TEXT, state TEXT, rating INTEGER, tags TEXT, bytes INTEGER, thumb_status TEXT, manifest TEXT
);
CREATE INDEX IF NOT EXISTS assets_created ON assets(created_at DESC);
CREATE INDEX IF NOT EXISTS assets_job ON assets(job_id);
CREATE TABLE IF NOT EXISTS lineage (from_id TEXT, to_id TEXT, via_job TEXT, kind TEXT, created_at TEXT, PRIMARY KEY (from_id, to_id, via_job));
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT, status TEXT, created_at TEXT, finished_at TEXT, record TEXT);
"""


def sha256_file(path: Path, limit: int | None = None) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


class Catalogue:
    def __init__(self, ws: Workspace, thumb_sizes: list[int] | None = None) -> None:
        self.ws = ws
        self.thumb_sizes = thumb_sizes or [256, 512, 1024]
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(ws.catalogue_db), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_DDL)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---- paths ------------------------------------------------------------------------------------
    def abs_path(self, rec: AssetRecord) -> Path:
        return self.ws.path / rec.path

    def manifest_path(self, rec: AssetRecord) -> Path:
        return self.abs_path(rec).with_suffix(".json")

    # ---- ingest -----------------------------------------------------------------------------------
    def ingest_file(self, src: Path, *, kind: AssetKind = "image", move: bool = True, **fields: Any) -> AssetRecord:
        """Move (or copy) a produced file into `assets/<yyyy-mm>/`, write its manifest, index it, make thumbnails."""
        src = Path(src)
        asset_id = fields.pop("id", None) or new_id("ast")
        ext = src.suffix.lower().lstrip(".") or "bin"
        dest = self.ws.asset_path(asset_id, ext, datetime.now())
        if move:
            atomic_move(src, dest)
        else:
            from .fsio import atomic_copy
            atomic_copy(src, dest)
        rec = AssetRecord(id=asset_id, kind=kind, path=dest.relative_to(self.ws.path).as_posix(), **fields)
        rec.bytes = dest.stat().st_size
        rec.sha256 = sha256_file(dest)
        if kind == "image":
            try:
                with Image.open(dest) as im:
                    rec.w, rec.h = im.size
            except Exception:
                pass
        atomic_write_json(self.manifest_path(rec), rec.model_dump())
        self._index(rec)
        for parent in rec.parents:
            self.add_lineage(parent, rec.id, rec.job_id or "", kind=fields.get("suite", "generate"))
        return rec

    def make_thumbs(self, rec: AssetRecord) -> AssetRecord:
        src = self.abs_path(rec)
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                for size in self.thumb_sizes:
                    t = im.copy()
                    t.thumbnail((size, size), Image.LANCZOS)
                    out = self.ws.thumb_path(rec.id, size)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    tmp = out.with_suffix(".tmp.webp")
                    t.save(tmp, "WEBP", quality=82, method=4)
                    tmp.replace(out)
            rec.thumb_status = "done"
        except Exception:
            rec.thumb_status = "failed"
        atomic_write_json(self.manifest_path(rec), rec.model_dump())
        self._index(rec)
        return rec

    # ---- index ------------------------------------------------------------------------------------
    def _index(self, rec: AssetRecord) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO assets (id, kind, path, w, h, frames, created_at, job_id, batch_id, model_id, seed, prompt_text, suite, state, rating, tags, bytes, thumb_status, manifest)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rec.id, rec.kind, rec.path, rec.w, rec.h, rec.frames, rec.created_at, rec.job_id, rec.batch_id, rec.model_id, rec.seed,
                 rec.prompt_text, rec.suite, rec.state, rec.rating, json.dumps(rec.tags), rec.bytes, rec.thumb_status, json.dumps(rec.model_dump(), default=str)))
            self._db.commit()

    def add_lineage(self, from_id: str, to_id: str, via_job: str, kind: str = "generate") -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO lineage VALUES (?,?,?,?,?)", (from_id, to_id, via_job, kind, utc_now()))
            self._db.commit()

    def record_job(self, job: dict) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)",
                             (job["id"], job.get("kind"), job.get("status"), job.get("created_at"), job.get("finished_at"), json.dumps(job, default=str)))
            self._db.commit()

    def get(self, asset_id: str) -> AssetRecord | None:
        with self._lock:
            row = self._db.execute("SELECT manifest FROM assets WHERE id=?", (asset_id,)).fetchone()
        return AssetRecord.model_validate(json.loads(row["manifest"])) if row else None

    def list(self, *, state: str | None = None, suite: str | None = None, model_id: str | None = None, job_id: str | None = None,
             search: str | None = None, sort: str = "created_desc", limit: int = 200, cursor: str | None = None) -> dict:
        where, args = [], []
        if state:
            where.append("state=?"); args.append(state)
        if suite:
            where.append("suite=?"); args.append(suite)
        if model_id:
            where.append("model_id=?"); args.append(model_id)
        if job_id:
            where.append("job_id=?"); args.append(job_id)
        if search:
            where.append("(prompt_text LIKE ? OR tags LIKE ?)"); args += [f"%{search}%", f"%{search}%"]
        order = {"created_desc": "created_at DESC, id DESC", "created_asc": "created_at ASC, id ASC", "rating_desc": "rating DESC, created_at DESC"}.get(sort, "created_at DESC, id DESC")
        if cursor:
            c_at, c_id = cursor.split("|", 1)
            where.append("(created_at < ? OR (created_at = ? AND id < ?))" if "DESC" in order else "(created_at > ? OR (created_at = ? AND id > ?))")
            args += [c_at, c_at, c_id]
        sql = "SELECT manifest, created_at, id FROM assets" + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {order} LIMIT ?"
        args.append(limit + 1)
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        items = [json.loads(r["manifest"]) for r in rows[:limit]]
        next_cursor = f"{rows[limit - 1]['created_at']}|{rows[limit - 1]['id']}" if len(rows) > limit else None
        return {"items": items, "next_cursor": next_cursor}

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]

    def patch(self, asset_id: str, changes: dict) -> AssetRecord | None:
        rec = self.get(asset_id)
        if rec is None:
            return None
        allowed = {"state", "rating", "tags", "collection_ids"}
        data = rec.model_dump()
        for k, v in changes.items():
            if k in allowed:
                data[k] = v
        rec = AssetRecord.model_validate(data)
        atomic_write_json(self.manifest_path(rec), rec.model_dump())
        self._index(rec)
        return rec

    def delete(self, asset_id: str) -> bool:
        rec = self.get(asset_id)
        if rec is None:
            return False
        for p in (self.abs_path(rec), self.manifest_path(rec)):
            p.unlink(missing_ok=True)
        tdir = self.ws.thumb_path(rec.id, 1).parent
        if tdir.is_dir():
            for t in tdir.iterdir():
                t.unlink(missing_ok=True)
            tdir.rmdir()
        with self._lock:
            self._db.execute("DELETE FROM assets WHERE id=?", (asset_id,))
            self._db.execute("DELETE FROM lineage WHERE from_id=? OR to_id=?", (asset_id, asset_id))
            self._db.commit()
        return True

    def lineage(self, asset_id: str) -> dict:
        with self._lock:
            up = [dict(r) for r in self._db.execute("SELECT * FROM lineage WHERE to_id=?", (asset_id,)).fetchall()]
            down = [dict(r) for r in self._db.execute("SELECT * FROM lineage WHERE from_id=?", (asset_id,)).fetchall()]
        return {"id": asset_id, "parents": up, "children": down}

    def rebuild(self) -> int:
        """Regenerate the index from the sidecar manifests (the files are the truth)."""
        n = 0
        with self._lock:
            self._db.execute("DELETE FROM assets")
            self._db.execute("DELETE FROM lineage")
            self._db.commit()
        for m in sorted(self.ws.assets_dir.rglob("*.json")):
            try:
                rec = AssetRecord.model_validate(read_json(m))
            except Exception:
                continue
            if not self.abs_path(rec).is_file():
                continue
            self._index(rec)
            for parent in rec.parents:
                self.add_lineage(parent, rec.id, rec.job_id or "", kind=rec.suite)
            n += 1
        return n

    def jobs_indexed(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def usage_bytes(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(SUM(bytes), 0) FROM assets").fetchone()
        return int(row[0])
