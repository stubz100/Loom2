"""Delete weights loom2 no longer needs and drop them from roster.index.json (policy D30, 2026-10-05).

  engine/.venv/Scripts/python.exe scripts/prune_weights.py NAME [NAME ...] [--root F:/loom2-models] [--dry-run]

NAME is the file's basename as it appears under the models root (any sub-folder). Every deletion is
re-downloadable through scripts/fetch_weights.py (mark the manifest entry `retired=...` so routine fetches
skip it). Hard links: the bytes are freed only when the last link goes — the summary reports the link count.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--root", default=os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    index_path = root / "roster.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}
    by_name = {}
    for p in root.rglob("*"):
        if p.is_file() and "_incoming" not in p.parts and p.name != "roster.index.json":
            by_name.setdefault(p.name, []).append(p)
    freed = 0
    for name in a.names:
        paths = by_name.get(name, [])
        if not paths:
            print(f"[miss]  {name}: not under {root}")
            continue
        for p in paths:
            size = p.stat().st_size
            links = p.stat().st_nlink
            print(f"[{'would' if a.dry_run else 'del'}]   {p.relative_to(root)}  {size/2**30:.2f} GiB  links={links}")
            if not a.dry_run:
                p.unlink()
                if links <= 1:
                    freed += size
            before = len(index["files"])
            index["files"] = [f for f in index["files"] if Path(f["path"]).name != name]
            if before != len(index["files"]):
                print(f"        index entry removed")
    if not a.dry_run:
        index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"[prune] {'would free' if a.dry_run else 'freed'} {freed/2**30:.2f} GiB; index now lists {len(index['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
