"""Record sha256 for roster files that are on disk but not in the fetch ledger (they show `present`, not `verified`).

Run (orchestrator venv: loom2 + huggingface_hub):
  orchestrator/.venv/Scripts/python.exe scripts/ledger_verify.py [--only <roster id> ...] [--list] [--no-hf]

For every roster entry whose health is `present` (D91 follow-up: Klein 4B and the files placed before the ledger existed), the file is
hashed read-only at background I/O priority (another job may be loading weights from the same disk), compared with the Hub's LFS oid of
the roster's `repo` / `file` when it has one, and appended to `<models>/roster.index.json` exactly as `scripts/fetch_weights.py` and
`loom2/tools/fetch.py` write it (path, folder, repo, file, size, sha256, license, spike, fetched) plus `hf_sha256` and `hf_match`. A
mismatch is recorded as `sha256: null` (the file stays `present`) and reported — never trusted silently.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "orchestrator"))

from loom2.fsio import atomic_write_text  # noqa: E402
from loom2.roster import ROSTER_BY_ID, Roster  # noqa: E402


def background_io() -> None:
    """Windows: PROCESS_MODE_BACKGROUND_BEGIN lowers this process's CPU, I/O and memory priority."""
    if os.name == "nt":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00100000)


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(16 * 2**20), b""):
            h.update(chunk)
    return h.hexdigest()


def hub_sha256(repo: str, file: str) -> str | None:
    from huggingface_hub import HfApi
    for info in HfApi().get_paths_info(repo, [file], token=True):
        lfs = getattr(info, "lfs", None)
        if lfs is not None:
            return lfs.sha256
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
    ap.add_argument("--only", action="append", help="roster id(s); default every `present` entry")
    ap.add_argument("--list", action="store_true", help="only list the present-but-unverified entries")
    ap.add_argument("--no-hf", action="store_true", help="do not ask the Hub for the LFS oid")
    a = ap.parse_args()
    os.environ.setdefault("HF_HOME", "F:/HF_HOME")
    root = Path(a.root)
    roster = Roster(root).scan()
    todo = [e for e in roster.listing(include_retired=True) if e["health"] == "present" and (not a.only or e["id"] in a.only)]
    for e in todo:
        print(f"[present] {e['id']:28} {e['size'] / 2**30:7.2f} GiB  {e['path']}")
    if a.list or not todo:
        return 0
    background_io()
    index_path = root / "roster.index.json"
    bad = 0
    for e in todo:
        path = Path(e["path"])
        t0 = time.time()
        digest = sha256_of(path)
        want = None
        if e.get("repo") and e.get("file") and not a.no_hf:
            try:
                want = hub_sha256(e["repo"], e["file"])
            except Exception as ex:   # offline, gated without a token …: record the local hash, say so
                print(f"[hub]     {e['id']}: {type(ex).__name__}: {ex}")
        match = None if want is None else want == digest
        bad += match is False
        print(f"[hash]    {e['id']:28} {digest}  {time.time() - t0:5.0f} s  hub={'-' if want is None else ('match' if match else 'MISMATCH ' + want)}")
        entry = ROSTER_BY_ID[e["id"]]
        index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"files": []}   # re-read per file
        index["files"] = [f for f in index["files"] if f["path"] != str(path)] + [dict(
            path=str(path), folder=entry.folder, repo=entry.repo, file=entry.file, size=path.stat().st_size,
            sha256=None if match is False else digest, license=entry.license, spike="ledger_verify",
            fetched=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)), hf_sha256=want, hf_match=match,
            recorded=time.strftime("%Y-%m-%d %H:%M:%S"))]
        atomic_write_text(index_path, json.dumps(index, indent=1))
    print(f"[ledger]  {len(todo)} recorded, {bad} mismatch(es) -> {index_path}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
