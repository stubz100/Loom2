"""Assets, manifests, lineage, collections, trash and the rebuildable SQLite index (06 §4–§5, 08 §7).

The files and their sidecar manifests are the truth; `catalogue.sqlite` is an index that `rebuild()` regenerates
from the sidecars. Group headers and smart-folder counts are computed here (08 §8), full-text search runs in
FTS5 over prompt text, prompt JSON and tags.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from PIL import Image
from pydantic import BaseModel, Field

from .fsio import StateError, atomic_copy, atomic_move, atomic_write_json, new_id, read_json, utc_now
from .workspace import Workspace

ASSET_SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = 2
AssetKind = Literal["image", "video", "mask", "document-render"]
AssetState = Literal["none", "keep", "reject"]
GroupMode = Literal["none", "batch", "lineage", "session", "model"]
Folder = Literal["all", "today", "last_session", "images", "clips", "documents", "imported", "rejected", "trash"]
Sort = Literal["created_desc", "created_asc", "rating_desc", "model", "size_desc"]


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
    session_id: str | None = None
    root_id: str | None = None                  # lineage root (self when the asset has no parents)
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
    has_document: bool = False
    thumb_status: Literal["pending", "done", "failed"] = "pending"
    trashed_at: str | None = None
    bytes: int | None = None
    sha256: str | None = None


GROUP_KEY = {"batch": "COALESCE(batch_id, job_id, id)", "lineage": "COALESCE(root_id, id)", "session": "COALESCE(session_id, '')", "model": "COALESCE(model_id, '')"}


class AssetQuery(BaseModel):
    folder: Folder = "all"
    kind: AssetKind | None = None
    suite: str | None = None
    state: AssetState | Literal["all"] = "all"
    model_id: str | None = None
    rating_min: int = 0
    tags_any: list[str] = Field(default_factory=list)
    tags_all: list[str] = Field(default_factory=list)
    has_document: bool | None = None
    has_children: bool | None = None
    aspect: Literal["landscape", "portrait", "square"] | None = None
    min_px: int | None = None
    created_from: str | None = None
    created_to: str | None = None
    search: str | None = None
    seed: int | None = None
    batch_id: str | None = None
    root_id: str | None = None
    session_id: str | None = None
    collection_id: str | None = None
    job_id: str | None = None
    sort: Sort = "created_desc"
    group: GroupMode = "none"
    group_by: GroupMode | None = None            # with group_key: the items of one group, using the same key expression as groups()
    group_key: str | None = None
    limit: int = 200
    cursor: str | None = None


class GroupHeader(BaseModel):
    key: str
    label: str
    count: int
    first_created: str
    last_created: str
    cover_id: str
    model_id: str | None = None
    prompt_excerpt: str | None = None


class AssetPage(BaseModel):
    items: list[AssetRecord]
    next_cursor: str | None = None
    total: int | None = None


class CollectionRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("col"))
    name: str
    kind: Literal["manual", "smart"] = "manual"
    filter: dict | None = None                  # AssetQuery fields for smart collections
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    count: int = 0


_DDL = """
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY, kind TEXT, path TEXT, w INTEGER, h INTEGER, aspect REAL, frames INTEGER, created_at TEXT, job_id TEXT, batch_id TEXT,
  session_id TEXT, root_id TEXT, model_id TEXT, seed INTEGER, prompt_text TEXT, suite TEXT, state TEXT, rating INTEGER, tags TEXT,
  has_document INTEGER DEFAULT 0, trashed_at TEXT, bytes INTEGER, thumb_status TEXT, manifest TEXT
);
CREATE INDEX IF NOT EXISTS assets_created ON assets(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS assets_job ON assets(job_id);
CREATE INDEX IF NOT EXISTS assets_batch ON assets(batch_id);
CREATE INDEX IF NOT EXISTS assets_root ON assets(root_id);
CREATE INDEX IF NOT EXISTS assets_session ON assets(session_id);
CREATE INDEX IF NOT EXISTS assets_model ON assets(model_id);
CREATE INDEX IF NOT EXISTS assets_trashed ON assets(trashed_at);
CREATE TABLE IF NOT EXISTS lineage (from_id TEXT, to_id TEXT, via_job TEXT, kind TEXT, created_at TEXT, PRIMARY KEY (from_id, to_id, via_job));
CREATE INDEX IF NOT EXISTS lineage_to ON lineage(to_id);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT, status TEXT, created_at TEXT, finished_at TEXT, record TEXT);
CREATE TABLE IF NOT EXISTS collections (id TEXT PRIMARY KEY, name TEXT, kind TEXT, filter TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS collection_assets (collection_id TEXT, asset_id TEXT, added_at TEXT, PRIMARY KEY (collection_id, asset_id));
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""
_FTS = "CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2')"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def _flatten_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, list):
        return " ".join(_flatten_text(x) for x in v)
    if isinstance(v, dict):
        return " ".join(f"{k} {_flatten_text(x)}" for k, x in v.items())
    return str(v)


def fts_query(search: str) -> str:
    """Turn free text into an FTS5 query: each token quoted, prefix-matched, ANDed (quotes and operators neutralised)."""
    tokens = [t for t in re.split(r"[^\w\-]+", search.strip()) if t]
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens[:12])


class Catalogue:
    def __init__(self, ws: Workspace, thumb_sizes: list[int] | None = None, session_id: str | None = None) -> None:
        self.ws = ws
        self.thumb_sizes = thumb_sizes or [256, 512, 1024]
        self.session_id = session_id
        self._lock = threading.RLock()
        self._closed = False
        self._db = sqlite3.connect(str(ws.catalogue_db), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self.fts = True
        with self._lock:
            # an index from an older schema is dropped and rebuilt from the sidecars (the files are the truth)
            cols = {r[1] for r in self._db.execute("PRAGMA table_info(assets)").fetchall()}
            stale = bool(cols) and "root_id" not in cols
            if stale:
                self._db.executescript("DROP TABLE IF EXISTS assets; DROP TABLE IF EXISTS lineage; DROP TABLE IF EXISTS assets_fts; DROP TABLE IF EXISTS meta;")
            self._db.executescript(_DDL)
            try:
                self._db.execute(_FTS)
            except sqlite3.OperationalError:
                self.fts = False
            self._db.commit()
            version = self._meta("index_schema")
            if stale or version != str(INDEX_SCHEMA_VERSION):
                if stale or version is not None or self.count() > 0:
                    self.rebuild()
                self._meta("index_schema", str(INDEX_SCHEMA_VERSION))

    def _meta(self, k: str, v: str | None = None) -> str | None:
        with self._lock:
            if v is None:
                row = self._db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
                return row["v"] if row else None
            self._db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, v))
            self._db.commit()
            return v

    def close(self) -> None:
        with self._lock:
            self._closed = True            # B11: a worker thread finishing an ingest after the project closed writes nothing
            self._db.close()

    # ---- paths ------------------------------------------------------------------------------------
    def abs_path(self, rec: AssetRecord) -> Path:
        return self.ws.path / rec.path

    def manifest_path(self, rec: AssetRecord) -> Path:
        return self.abs_path(rec).with_suffix(".json")

    # ---- ingest -----------------------------------------------------------------------------------
    def ingest_file(self, src: Path, *, kind: AssetKind = "image", move: bool = True, in_place: bool = False, **fields: Any) -> AssetRecord:
        """Move (or copy) a produced file into `assets/<yyyy-mm>/`, write its manifest, index it. `in_place` indexes a
        file that already lives inside the project where it is (M6 clip proxies stay in `clips/<id>/`)."""
        src = Path(src)
        asset_id = fields.pop("id", None) or new_id("ast")
        lineage_kind = fields.pop("lineage_kind", None)              # e.g. "frame-extract"; default = the suite
        ext = src.suffix.lower().lstrip(".") or "bin"
        if in_place:
            dest = src
            dest.relative_to(self.ws.path)                            # must be inside the project
        else:
            dest = self.ws.asset_path(asset_id, ext, datetime.now())
            if move:
                atomic_move(src, dest)
            else:
                atomic_copy(src, dest)
        fields.setdefault("session_id", self.session_id)
        rec = AssetRecord(id=asset_id, kind=kind, path=dest.relative_to(self.ws.path).as_posix(), **fields)
        rec.bytes = dest.stat().st_size
        rec.sha256 = sha256_file(dest)
        if kind == "image" and (rec.w is None or rec.h is None):
            try:
                with Image.open(dest) as im:
                    rec.w, rec.h = im.size
            except Exception:
                pass
        if rec.parents:
            parent = self.get(rec.parents[0])
            rec.root_id = (parent.root_id or parent.id) if parent else rec.parents[0]
        else:
            rec.root_id = rec.id
        atomic_write_json(self.manifest_path(rec), rec.model_dump())
        self._index(rec)
        for parent in rec.parents:
            self.add_lineage(parent, rec.id, rec.job_id or "", kind=lineage_kind or rec.suite)
        return rec

    def make_thumbs(self, rec: AssetRecord, source: Path | None = None) -> AssetRecord:
        """Thumbnails from the asset file, or from `source` (a clip's first master frame stands in for its mp4)."""
        src = source or self.abs_path(rec)
        if source is None and rec.kind == "video":
            cid = (rec.params or {}).get("clip_id")
            poster = self.ws.clips_dir / str(cid) / "master" / "000000.png" if cid else None
            if poster and poster.is_file():
                src = poster
        try:
            with Image.open(src) as im:
                # B11: transparent sources (edit flattens) keep their alpha in WebP; opaque ones stay RGB (smaller)
                im = im.convert("RGBA" if im.mode in ("RGBA", "LA") or "transparency" in im.info else "RGB")
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
        aspect = (rec.w / rec.h) if rec.w and rec.h else None
        with self._lock:
            if self._closed:
                return
            self._db.execute(
                "INSERT OR REPLACE INTO assets (id, kind, path, w, h, aspect, frames, created_at, job_id, batch_id, session_id, root_id, model_id, seed, prompt_text,"
                " suite, state, rating, tags, has_document, trashed_at, bytes, thumb_status, manifest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rec.id, rec.kind, rec.path, rec.w, rec.h, aspect, rec.frames, rec.created_at, rec.job_id, rec.batch_id, rec.session_id, rec.root_id, rec.model_id,
                 rec.seed, rec.prompt_text, rec.suite, rec.state, rec.rating, json.dumps(rec.tags), int(rec.has_document), rec.trashed_at, rec.bytes, rec.thumb_status,
                 json.dumps(rec.model_dump(), default=str)))
            if self.fts:
                text = " ".join(x for x in (rec.prompt_text or "", _flatten_text(rec.prompt_json), " ".join(rec.tags), rec.model_id or "", str(rec.seed or "")) if x)
                self._db.execute("DELETE FROM assets_fts WHERE id=?", (rec.id,))
                self._db.execute("INSERT INTO assets_fts (id, text) VALUES (?,?)", (rec.id, text))
            self._db.commit()

    def add_lineage(self, from_id: str, to_id: str, via_job: str, kind: str = "generate") -> None:
        with self._lock:
            if self._closed:
                return
            self._db.execute("INSERT OR REPLACE INTO lineage VALUES (?,?,?,?,?)", (from_id, to_id, via_job, kind, utc_now()))
            self._db.commit()

    def record_job(self, job: dict) -> None:
        with self._lock:
            if self._closed:
                return
            self._db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?)",
                             (job["id"], job.get("kind"), job.get("status"), job.get("created_at"), job.get("finished_at"), json.dumps(job, default=str)))
            self._db.commit()

    def jobs_indexed(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    def get(self, asset_id: str) -> AssetRecord | None:
        with self._lock:
            row = self._db.execute("SELECT manifest FROM assets WHERE id=?", (asset_id,)).fetchone()
        return AssetRecord.model_validate(json.loads(row["manifest"])) if row else None

    def get_many(self, ids: list[str]) -> list[AssetRecord]:
        if not ids:
            return []
        with self._lock:
            rows = self._db.execute(f"SELECT manifest FROM assets WHERE id IN ({','.join('?' * len(ids))})", ids).fetchall()
        by = {json.loads(r["manifest"])["id"]: AssetRecord.model_validate(json.loads(r["manifest"])) for r in rows}
        return [by[i] for i in ids if i in by]

    # ---- querying ---------------------------------------------------------------------------------
    def _where(self, q: AssetQuery) -> tuple[str, list]:
        where, args = [], []
        trash = q.folder == "trash"
        where.append("trashed_at IS NOT NULL" if trash else "trashed_at IS NULL")
        if q.folder == "today":
            # B11: the user's local day, in the UTC ISO form created_at uses (an EU morning's day starts at 22:00 Z the evening before)
            local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            where.append("created_at >= ?"); args.append(local_midnight.astimezone(timezone.utc).isoformat(timespec="seconds"))
        elif q.folder == "last_session":
            last = self.last_session_id()
            where.append("session_id = ?"); args.append(last or "")
        elif q.folder == "images":
            where.append("kind = 'image'")
        elif q.folder == "clips":
            where.append("kind = 'video'")
        elif q.folder == "documents":
            where.append("(kind = 'document-render' OR has_document = 1)")
        elif q.folder == "imported":
            where.append("suite = 'import'")
        elif q.folder == "rejected":
            where.append("state = 'reject'")
        if q.kind:
            where.append("kind = ?"); args.append(q.kind)
        if q.suite:
            where.append("suite = ?"); args.append(q.suite)
        if q.state != "all":
            where.append("state = ?"); args.append(q.state)
        if q.model_id:
            where.append("model_id = ?"); args.append(q.model_id)
        if q.rating_min > 0:
            where.append("rating >= ?"); args.append(q.rating_min)
        for t in q.tags_all:
            where.append("tags LIKE ?"); args.append(f'%"{t}"%')
        if q.tags_any:
            where.append("(" + " OR ".join("tags LIKE ?" for _ in q.tags_any) + ")"); args += [f'%"{t}"%' for t in q.tags_any]
        if q.has_document is not None:
            where.append("has_document = ?"); args.append(int(q.has_document))
        if q.has_children is not None:
            where.append(("EXISTS" if q.has_children else "NOT EXISTS") + " (SELECT 1 FROM lineage l WHERE l.from_id = assets.id)")
        if q.aspect == "landscape":
            where.append("aspect > 1.05")
        elif q.aspect == "portrait":
            where.append("aspect < 0.95")
        elif q.aspect == "square":
            where.append("aspect BETWEEN 0.95 AND 1.05")
        if q.min_px:
            where.append("(w * h) >= ?"); args.append(q.min_px)
        if q.created_from:
            where.append("created_at >= ?"); args.append(q.created_from)
        if q.created_to:
            where.append("created_at <= ?"); args.append(q.created_to)
        if q.seed is not None:
            where.append("seed = ?"); args.append(q.seed)
        for col, val in (("batch_id", q.batch_id), ("root_id", q.root_id), ("session_id", q.session_id), ("job_id", q.job_id)):
            if val:
                where.append(f"{col} = ?"); args.append(val)
        if q.collection_id:
            where.append("id IN (SELECT asset_id FROM collection_assets WHERE collection_id = ?)"); args.append(q.collection_id)
        if q.group_by and q.group_by != "none" and q.group_key is not None:
            where.append(f"{GROUP_KEY[q.group_by]} = ?"); args.append(q.group_key)
        if q.search:
            if self.fts and fts_query(q.search):
                where.append("id IN (SELECT id FROM assets_fts WHERE assets_fts MATCH ?)"); args.append(fts_query(q.search))
            else:
                where.append("(prompt_text LIKE ? OR tags LIKE ?)"); args += [f"%{q.search}%", f"%{q.search}%"]
        return " AND ".join(where), args

    @staticmethod
    def _order(sort: Sort) -> tuple[str, str]:
        return {
            "created_desc": ("created_at DESC, id DESC", "<"), "created_asc": ("created_at ASC, id ASC", ">"),
            "rating_desc": ("rating DESC, created_at DESC, id DESC", "<"), "model": ("model_id IS NULL, model_id ASC, created_at DESC, id DESC", "<"),
            "size_desc": ("bytes DESC, created_at DESC, id DESC", "<"),
        }[sort]

    def list(self, q: AssetQuery | None = None, **kw: Any) -> AssetPage:
        q = q or AssetQuery(**{k: v for k, v in kw.items() if v is not None})
        where, args = self._where(q)
        order, _ = self._order(q.sort)
        if q.cursor and q.sort in ("created_desc", "created_asc"):
            if "|" not in q.cursor:
                raise StateError(f"malformed cursor {q.cursor!r}")           # B11: 400, not 500
            c_at, c_id = q.cursor.split("|", 1)
            op = "<" if q.sort == "created_desc" else ">"
            where += f" AND (created_at {op} ? OR (created_at = ? AND id {op} ?))"
            args += [c_at, c_at, c_id]
        offset = 0
        if q.cursor and q.sort not in ("created_desc", "created_asc"):
            if not q.cursor.isdigit():
                raise StateError(f"malformed cursor {q.cursor!r}")
            offset = int(q.cursor)
        limit = max(1, min(q.limit, 2000))
        sql = f"SELECT manifest, created_at, id FROM assets WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?"
        with self._lock:
            rows = self._db.execute(sql, [*args, limit + 1, offset]).fetchall()
            total = self._db.execute(f"SELECT COUNT(*) FROM assets WHERE {where}", args).fetchone()[0] if not q.cursor else None
        items = [AssetRecord.model_validate(json.loads(r["manifest"])) for r in rows[:limit]]
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = f"{last['created_at']}|{last['id']}" if q.sort in ("created_desc", "created_asc") else str(offset + limit)
        return AssetPage(items=items, next_cursor=next_cursor, total=total)

    def groups(self, q: AssetQuery) -> list[GroupHeader]:
        """Server-side group headers for the Stage (08 §3b): one row per batch / lineage root / session / model."""
        col = GROUP_KEY.get(q.group)
        if col is None:
            return []
        where, args = self._where(q)
        sql = (f"WITH f AS (SELECT {col} AS k, id, rating, created_at, model_id, prompt_text FROM assets WHERE {where}), "
               "r AS (SELECT k, id, model_id, prompt_text, ROW_NUMBER() OVER (PARTITION BY k ORDER BY rating DESC, created_at ASC) AS rn FROM f), "
               "g AS (SELECT k, COUNT(*) AS n, MIN(created_at) AS first_c, MAX(created_at) AS last_c FROM f GROUP BY k) "
               "SELECT g.k, g.n, g.first_c, g.last_c, r.id AS cover, r.model_id, r.prompt_text AS prompt FROM g JOIN r ON r.k = g.k AND r.rn = 1 ORDER BY g.last_c DESC")
        with self._lock:
            rows = self._db.execute(sql, args).fetchall()
        out = []
        for r in rows:
            key = r["k"] or ""
            label = {"batch": f"Batch {key[-8:]}", "lineage": f"Lineage {key[-8:]}", "session": f"Session {key[-8:] or '—'}", "model": key or "no model"}[q.group]
            out.append(GroupHeader(key=key, label=label, count=r["n"], first_created=r["first_c"], last_created=r["last_c"], cover_id=r["cover"] or "",
                                   model_id=r["model_id"], prompt_excerpt=(r["prompt"] or "")[:80] or None))
        return out

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for folder in ("all", "today", "last_session", "images", "clips", "documents", "imported", "rejected", "trash"):
            where, args = self._where(AssetQuery(folder=folder))  # type: ignore[arg-type]
            with self._lock:
                out[folder] = self._db.execute(f"SELECT COUNT(*) FROM assets WHERE {where}", args).fetchone()[0]
        return out

    def last_session_id(self) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT session_id FROM assets WHERE session_id IS NOT NULL AND session_id != ? ORDER BY created_at DESC LIMIT 1", (self.session_id or "",)).fetchone()
        return row["session_id"] if row else None

    def tags(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT tags FROM assets WHERE trashed_at IS NULL AND tags != '[]'").fetchall()
        counts: dict[str, int] = {}
        for r in rows:
            for t in json.loads(r["tags"]):
                counts[t] = counts.get(t, 0) + 1
        return [{"tag": t, "count": n} for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM assets").fetchone()[0]

    # ---- edits ------------------------------------------------------------------------------------
    def patch(self, asset_id: str, changes: dict) -> AssetRecord | None:
        rec = self.get(asset_id)
        if rec is None:
            return None
        allowed = {"state", "rating", "tags", "collection_ids", "has_document"}
        data = rec.model_dump()
        for k, v in changes.items():
            if k in allowed:
                data[k] = v
        rec = AssetRecord.model_validate(data)
        atomic_write_json(self.manifest_path(rec), rec.model_dump())
        self._index(rec)
        return rec

    def patch_many(self, ids: list[str], changes: dict) -> list[AssetRecord]:
        out = []
        for i in ids:
            r = self.patch(i, changes)
            if r:
                out.append(r)
        return out

    def trash(self, ids: list[str]) -> list[AssetRecord]:
        out = []
        now = utc_now()
        for rec in self.get_many(ids):
            rec.trashed_at = now
            atomic_write_json(self.manifest_path(rec), rec.model_dump())
            self._index(rec)
            out.append(rec)
        return out

    def restore(self, ids: list[str]) -> list[AssetRecord]:
        out = []
        for rec in self.get_many(ids):
            rec.trashed_at = None
            atomic_write_json(self.manifest_path(rec), rec.model_dump())
            self._index(rec)
            out.append(rec)
        return out

    def purge(self, ids: list[str] | None = None, older_than_days: int | None = None) -> list[str]:
        """Permanently delete trashed assets (files, manifests, thumbs, index rows, lineage edges)."""
        if ids is None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days or 0)).isoformat(timespec="seconds")
            with self._lock:
                ids = [r["id"] for r in self._db.execute("SELECT id FROM assets WHERE trashed_at IS NOT NULL AND trashed_at <= ?", (cutoff,)).fetchall()]
        gone = []
        for rec in self.get_many(ids):
            if rec.trashed_at is None:
                continue
            self._delete_files(rec)
            gone.append(rec.id)
        return gone

    def delete(self, asset_id: str) -> bool:
        rec = self.get(asset_id)
        if rec is None:
            return False
        self._delete_files(rec)
        return True

    def _delete_files(self, rec: AssetRecord) -> None:
        for p in (self.abs_path(rec), self.manifest_path(rec)):
            p.unlink(missing_ok=True)
        tdir = self.ws.thumb_path(rec.id, 1).parent
        if tdir.is_dir():
            for t in tdir.iterdir():
                t.unlink(missing_ok=True)
            tdir.rmdir()
        with self._lock:
            self._db.execute("DELETE FROM assets WHERE id=?", (rec.id,))
            self._db.execute("DELETE FROM lineage WHERE from_id=? OR to_id=?", (rec.id, rec.id))
            self._db.execute("DELETE FROM collection_assets WHERE asset_id=?", (rec.id,))
            if self.fts:
                self._db.execute("DELETE FROM assets_fts WHERE id=?", (rec.id,))
            self._db.commit()

    # ---- lineage ----------------------------------------------------------------------------------
    def lineage(self, asset_id: str) -> dict:
        with self._lock:
            up = [dict(r) for r in self._db.execute("SELECT * FROM lineage WHERE to_id=?", (asset_id,)).fetchall()]
            down = [dict(r) for r in self._db.execute("SELECT * FROM lineage WHERE from_id=?", (asset_id,)).fetchall()]
        rec = self.get(asset_id)
        return {"id": asset_id, "root_id": rec.root_id if rec else None, "parents": up, "children": down}

    def lineage_tree(self, root_id: str) -> dict:
        """Every asset under a root with its edges, for the Lineage group view."""
        with self._lock:
            rows = self._db.execute("SELECT manifest FROM assets WHERE root_id=? AND trashed_at IS NULL ORDER BY created_at", (root_id,)).fetchall()
            ids = [json.loads(r["manifest"])["id"] for r in rows]
            edges = [dict(r) for r in self._db.execute(f"SELECT from_id, to_id, via_job, kind FROM lineage WHERE to_id IN ({','.join('?' * len(ids)) or 'NULL'})", ids).fetchall()] if ids else []
        return {"root_id": root_id, "items": [json.loads(r["manifest"]) for r in rows], "edges": edges}

    # ---- collections ------------------------------------------------------------------------------
    def collections(self) -> list[CollectionRecord]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM collections ORDER BY created_at").fetchall()
            counts = {r["collection_id"]: r["n"] for r in self._db.execute("SELECT collection_id, COUNT(*) AS n FROM collection_assets GROUP BY collection_id").fetchall()}
        out = []
        for r in rows:
            rec = CollectionRecord(id=r["id"], name=r["name"], kind=r["kind"], filter=json.loads(r["filter"]) if r["filter"] else None, created_at=r["created_at"], updated_at=r["updated_at"])
            rec.count = counts.get(rec.id, 0) if rec.kind == "manual" else self.list(AssetQuery(**(rec.filter or {}), limit=1)).total or 0
            out.append(rec)
        return out

    def collection_create(self, name: str, kind: str = "manual", filter_: dict | None = None) -> CollectionRecord:
        rec = CollectionRecord(name=name, kind=kind, filter=filter_)  # type: ignore[arg-type]
        with self._lock:
            self._db.execute("INSERT INTO collections VALUES (?,?,?,?,?,?)", (rec.id, rec.name, rec.kind, json.dumps(rec.filter) if rec.filter else None, rec.created_at, rec.updated_at))
            self._db.commit()
        return rec

    def collection_update(self, cid: str, *, name: str | None = None, kind: str | None = None, filter_: dict | None = None) -> CollectionRecord | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
            if not row:
                return None
            new_name = name if name is not None else row["name"]
            new_kind = kind if kind is not None else row["kind"]
            new_filter = json.dumps(filter_) if filter_ is not None else row["filter"]
            if new_kind == "manual" and row["kind"] == "smart":          # convert smart → manual: freeze the members
                q = AssetQuery(**(json.loads(row["filter"]) if row["filter"] else {}), limit=2000)
                for a in self.list(q).items:
                    self._db.execute("INSERT OR IGNORE INTO collection_assets VALUES (?,?,?)", (cid, a.id, utc_now()))
                new_filter = None
            self._db.execute("UPDATE collections SET name=?, kind=?, filter=?, updated_at=? WHERE id=?", (new_name, new_kind, new_filter, utc_now(), cid))
            self._db.commit()
        return next((c for c in self.collections() if c.id == cid), None)

    def collection_delete(self, cid: str) -> bool:
        with self._lock:
            n = self._db.execute("DELETE FROM collections WHERE id=?", (cid,)).rowcount
            self._db.execute("DELETE FROM collection_assets WHERE collection_id=?", (cid,))
            self._db.commit()
        return n > 0

    def collection_add(self, cid: str, ids: list[str]) -> int:
        with self._lock:
            for i in ids:
                self._db.execute("INSERT OR IGNORE INTO collection_assets VALUES (?,?,?)", (cid, i, utc_now()))
            self._db.commit()
            return self._db.execute("SELECT COUNT(*) FROM collection_assets WHERE collection_id=?", (cid,)).fetchone()[0]

    def collection_remove(self, cid: str, ids: list[str]) -> int:
        with self._lock:
            self._db.execute(f"DELETE FROM collection_assets WHERE collection_id=? AND asset_id IN ({','.join('?' * len(ids)) or 'NULL'})", [cid, *ids])
            self._db.commit()
            return self._db.execute("SELECT COUNT(*) FROM collection_assets WHERE collection_id=?", (cid,)).fetchone()[0]

    # ---- maintenance ------------------------------------------------------------------------------
    def rebuild(self) -> int:
        """Regenerate the index from the sidecar manifests (the files are the truth). Collections survive."""
        n = 0
        with self._lock:
            self._db.execute("DELETE FROM assets")
            self._db.execute("DELETE FROM lineage")
            if self.fts:
                self._db.execute("DELETE FROM assets_fts")
            self._db.commit()
        manifests = sorted(self.ws.assets_dir.rglob("*.json")) + sorted(self.ws.clips_dir.glob("*/proxy.json"))     # M6: clip proxies are indexed in place
        for m in manifests:
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

    def usage_bytes(self) -> int:
        with self._lock:
            row = self._db.execute("SELECT COALESCE(SUM(bytes), 0) FROM assets").fetchone()
        return int(row[0])
