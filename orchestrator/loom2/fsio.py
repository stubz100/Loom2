"""Persistence core (06 §4 rules, ported from loom's workspace.py): stable ids, atomic fsync'd writes, readers
that refuse partial JSON.

- `new_id("ast")` → `ast_3f9a2c1d` — references use ids, never paths.
- `atomic_write_*` write temp → fsync → `replace`; a crash leaves the old file or the new one, never a
  truncated one. `replace` retries a `PermissionError` with backoff (D42): on Windows antivirus and the search indexer
  briefly hold files open, and a one-shot `os.replace` then fails a save. The temp name is per writer, so two writers of the same file race benignly (last wins whole).
- `read_json` raises `StateError` on a missing or corrupt record instead of degrading to an empty one.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateError(Exception):
    """A durable-state validation or I/O failure that the API surfaces as 4xx/5xx."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str, n: int = 8) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:n]}"


def slugify(name: str, fallback: str = "item") -> str:
    out = "".join(c if c.isalnum() else "-" for c in name.strip().lower())
    out = "-".join(p for p in out.split("-") if p)
    return out or fallback


# D42: 7 tries from 10 ms, doubling (≤ 0.63 s of waiting) — PhotoCraft's crates/format/src/atomic.rs rule
REPLACE_TRIES = 7
REPLACE_FIRST_DELAY_S = 0.01


def replace(src: Path | str, dst: Path | str) -> None:
    """`os.replace` that retries a transient `PermissionError` (a file briefly held open by another process); any other error,
    or the last failure, propagates."""
    delay = REPLACE_FIRST_DELAY_S
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2


def _tmp_for(path: Path) -> Path:
    return path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(path)
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, data: Any, indent: int | None = 1) -> None:
    atomic_write_bytes(path, json.dumps(data, indent=indent, default=str, ensure_ascii=False).encode("utf-8"))


def atomic_copy(src: Path, dst: Path) -> None:
    """Copy whole-or-not-at-all: full copy to a temp beside `dst`, fsync, replace."""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_for(dst)
    try:
        shutil.copy2(src, tmp)
        with open(tmp, "rb+") as f:
            os.fsync(f.fileno())
        replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_move(src: Path, dst: Path) -> None:
    """Move across or within volumes with the same whole-or-nothing contract (same volume: rename)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        replace(src, dst)
    except OSError:                                       # another volume (or still locked): copy, then remove
        atomic_copy(src, dst)
        src.unlink()


def read_json(path: Path) -> Any:
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise StateError(f"missing record: {path}") from e
    except (json.JSONDecodeError, OSError) as e:
        raise StateError(f"corrupt or partial record (refused): {path} — {e}") from e


def read_json_or(path: Path, default: Any) -> Any:
    """Absent → default; corrupt → still raises (a torn record must be noticed, never silently reset)."""
    if not Path(path).exists():
        return default
    return read_json(path)


def free_space_gb(path: Path) -> float:
    probe = Path(path)
    while not probe.exists():
        if probe.parent == probe:
            break
        probe = probe.parent
    return shutil.disk_usage(probe).free / 1024**3


def dir_size_bytes(path: Path) -> int:
    total = 0
    for p in Path(path).rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total
