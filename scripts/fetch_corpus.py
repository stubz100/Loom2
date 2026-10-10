"""Fetch the pinned psd-tools test PSDs for the compose.py Photoshop oracle (D40).

    python scripts/fetch_corpus.py            # downloads what is missing into bench/corpus/psd-tools/, verifies every SHA-256
    python scripts/fetch_corpus.py --check    # verify only; exit 1 when a file is missing or differs

The files come from https://github.com/psd-tools/psd-tools/tree/<commit>/tests/psd_files (MIT), pinned by commit and hash in
bench/corpus/psd-tools.sha256; they are never committed (gitignored). Stdlib only, so CI can run it before installing anything.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "bench" / "corpus" / "psd-tools.sha256"
DEST = REPO / "bench" / "corpus" / "psd-tools"
COMMIT = "96eb134c17b2c65edf4c4151c0f00b802ada86c2"
RAW = f"https://raw.githubusercontent.com/psd-tools/psd-tools/{COMMIT}"


def pins() -> list[tuple[str, str]]:
    out = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            sha, name = line.split(None, 1)
            out.append((sha, name.strip()))
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    check_only = "--check" in sys.argv
    files = pins()
    bad = []
    if not check_only:
        DEST.mkdir(parents=True, exist_ok=True)
        lic = DEST / "LICENSE"
        if not lic.is_file():
            urllib.request.urlretrieve(f"{RAW}/LICENSE", lic)
    for sha, name in files:
        path = DEST / name
        if not path.is_file() or sha256(path) != sha:
            if check_only:
                bad.append(name); continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            urllib.request.urlretrieve(f"{RAW}/tests/psd_files/{name}", tmp)
            if sha256(tmp) != sha:
                tmp.unlink(missing_ok=True)
                bad.append(name); continue
            tmp.replace(path)
    print(f"fetch_corpus: {len(files) - len(bad)}/{len(files)} psd-tools files verified in {DEST.relative_to(REPO).as_posix()}")
    for name in bad:
        print(f"  missing or wrong hash: {name}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
