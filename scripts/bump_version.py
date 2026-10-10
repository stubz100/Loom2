"""One version for the whole app (D36). `VERSION` at the repository root is the source; this script writes it into every
other place a version lives, or checks that they agree (CI).

    python scripts/bump_version.py --check            # exit 1 when any location disagrees with VERSION
    python scripts/bump_version.py patch|minor|major  # bump VERSION and rewrite every location
    python scripts/bump_version.py 0.3.0 [--dry-run]  # set an explicit version

Locations: VERSION, orchestrator/pyproject.toml (+ its entry in orchestrator/uv.lock), orchestrator/loom2/__init__.py,
frontend/package.json, frontend/package-lock.json (root + packages[""]), frontend/src-tauri/tauri.conf.json,
frontend/src-tauri/Cargo.toml and the `app` entry of frontend/src-tauri/Cargo.lock. Stdlib only; files keep their line endings.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
NL = r"\r?\n"               # working copies may carry CRLF


@dataclass(frozen=True)
class Location:
    path: str
    pattern: str            # regex with three groups: prefix, version, suffix
    count: int = 1          # how many matches must exist (and are rewritten)


LOCATIONS = [
    Location("VERSION", r"^()(\d+\.\d+\.\d+)(\s*)$"),
    Location("orchestrator/pyproject.toml", r'(?m)^(version = ")([^"]+)(")'),
    Location("orchestrator/uv.lock", r'(name = "loom2-orchestrator"' + NL + r'version = ")([^"]+)(")'),
    Location("orchestrator/loom2/__init__.py", r'(?m)^(__version__ = ")([^"]+)(")'),
    Location("frontend/package.json", r'(?m)^(  "version": ")([^"]+)(")'),
    Location("frontend/package-lock.json", r'(?m)^(  "version": ")([^"]+)(")'),
    Location("frontend/package-lock.json", r'("": \{' + NL + r'(?:      [^\r\n]*' + NL + r')*?      "version": ")([^"]+)(")'),
    Location("frontend/src-tauri/tauri.conf.json", r'(?m)^(  "version": ")([^"]+)(")'),
    Location("frontend/src-tauri/Cargo.toml", r'(?m)^(version = ")([^"]+)(")'),
    Location("frontend/src-tauri/Cargo.lock", r'(name = "app"' + NL + r'version = ")([^"]+)(")'),
]


def read_versions(root: Path = REPO) -> list[tuple[Location, str | None]]:
    """The version found at each location (None when the pattern does not match)."""
    out = []
    for loc in LOCATIONS:
        text = _read(root / loc.path)
        m = re.search(loc.pattern, text) if text is not None else None
        out.append((loc, m.group(2) if m else None))
    return out


def mismatches(root: Path = REPO) -> list[str]:
    found = read_versions(root)
    source = found[0][1]
    if source is None or not SEMVER.match(source):
        return [f"VERSION: {source!r} is not X.Y.Z"]
    return [f"{loc.path}: {v!r} (VERSION says {source})" for loc, v in found[1:] if v != source]


def write_version(new: str, root: Path = REPO, dry_run: bool = False) -> list[str]:
    """Rewrite every location to `new`; returns the paths changed."""
    if not SEMVER.match(new):
        raise ValueError(f"not a semantic version: {new}")
    texts: dict[str, str] = {}
    for loc in LOCATIONS:
        text = texts[loc.path] if loc.path in texts else _read(root / loc.path)
        if text is None:
            raise FileNotFoundError(root / loc.path)
        replaced, n = re.subn(loc.pattern, lambda m: m.group(1) + new + m.group(3), text, count=loc.count)
        if n != loc.count:
            raise ValueError(f"{loc.path}: expected {loc.count} match(es) for {loc.pattern!r}, found {n}")
        texts[loc.path] = replaced
    changed = []
    for rel, text in texts.items():
        path = root / rel
        if _read(path) != text:
            changed.append(rel)
            if not dry_run:
                path.write_bytes(text.encode("utf-8"))
    return changed


def bumped(current: str, part: str) -> str:
    major, minor, patch = (int(x) for x in current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return part


def _read(path: Path) -> str | None:
    try:
        return path.read_bytes().decode("utf-8")      # bytes, so the file's own line endings survive a rewrite
    except FileNotFoundError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help="patch | minor | major | X.Y.Z")
    ap.add_argument("--check", action="store_true", help="only check that every location matches VERSION")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.check or not args.target:
        problems = mismatches()
        for p in problems:
            print(p)
        print(f"bump_version: {len(LOCATIONS)} locations, {len(problems)} mismatch(es)")
        return 1 if problems else 0
    current = read_versions()[0][1] or "0.0.0"
    new = bumped(current, args.target)
    changed = write_version(new, dry_run=args.dry_run)
    print(f"bump_version: {current} -> {new}; {'would change' if args.dry_run else 'changed'}: {', '.join(changed) or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
