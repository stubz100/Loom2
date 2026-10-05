"""Persistence core (06 §4 rules, ported from loom's workspace.py): stable ids, atomic fsync'd writes, readers
that refuse partial JSON.

- `new_id("ast")` → `ast_3f9a2c1d` — references use ids, never paths.
- `atomic_write_*` write temp → fsync → `os.replace`; a crash leaves the old file or the new one, never a
  truncated one. The temp name is per writer, so two writers of the same file race benignly (last wins whole).
- `read_json` raises `StateError` on a missing or corrupt record instead of degrading to an empty one.
"""
from __future__ import annotations

import json
import os
import shutil
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
        os.replace(tmp, path)
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
        os.replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_move(src: Path, dst: Path) -> None:
    """Move across or within volumes with the same whole-or-nothing contract (same volume: rename)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(src, dst)
    except OSError:
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
