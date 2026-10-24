"""CE1 (proto01_animate 30 §10, D126): build the pinned FilmCraft CLI — the cut editor's engine — and keep its pin.

    python scripts/build_filmcraft.py           build filmcraft-cli from the checkout beside this repository (../filmcraft, clean, at the
                                                pinned commit) into engine/tools/filmcraft/ (git-ignored, like RIFE) and record its sha256
                                                and size in engine/filmcraft.pin.json
    python scripts/build_filmcraft.py --check   the pin is well formed and, when the binary is here, matches it (CI runs this; the binary is
                                                never in git, so CI only sees the pin)

Needs rustc >= 1.95 (the checkout's rust-version) and about 3 minutes the first time (E32: 2 min 31 s); later builds are
incremental. The pin moves deliberately: edit `commit`, move the checkout, build, commit the new hash with a D-number.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "engine" / "filmcraft.pin.json"
TOOLS = ROOT / "engine" / "tools" / "filmcraft"
FILMCRAFT = ROOT.parent / "filmcraft"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(pin: dict, binary: Path) -> tuple[bool, str]:
    """The pin's fields are well formed; the binary, when it is here, has the pinned hash and size."""
    for k in ("repository", "commit", "version", "binary", "sha256", "bytes"):
        if k not in pin:
            return False, f"the pin lacks `{k}`"
    if not re.fullmatch(r"[0-9a-f]{40}", str(pin["commit"])):
        return False, f"the pin's commit is not a full sha: {pin['commit']!r}"
    if not re.fullmatch(r"[0-9a-f]{64}", str(pin["sha256"])):
        return False, f"the pin's sha256 is not 64 hex digits: {pin['sha256']!r}"
    if not isinstance(pin["bytes"], int) or pin["bytes"] <= 0:
        return False, f"the pin's size is not a positive number: {pin['bytes']!r}"
    if not binary.is_file():
        return True, f"{binary.name} is not built here (engine/tools/ is git-ignored); the pin is well formed (filmcraft {pin['version']} at {pin['commit'][:8]})"
    got, size = sha256(binary), binary.stat().st_size
    if got != pin["sha256"] or size != pin["bytes"]:
        return False, f"{binary.name} sha256 {got[:12]}... / {size} B != pinned {pin['sha256'][:12]}... / {pin['bytes']} B - rebuild, or move the pin deliberately"
    return True, f"{binary.name} matches its pin (filmcraft {pin['version']} at {pin['commit'][:8]}, {size} B)"


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    binary = TOOLS / pin.get("binary", "filmcraft-cli.exe")
    if "--check" in sys.argv:
        ok, msg = check(pin, binary)
        print(f"build_filmcraft: {msg}")
        return 0 if ok else 1
    if not (FILMCRAFT / "Cargo.toml").is_file():
        print(f"build_filmcraft: no FilmCraft checkout at {FILMCRAFT} — clone {pin['repository']} beside this repository at {pin['commit'][:8]}"); return 1
    head = subprocess.run(["git", "-C", str(FILMCRAFT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(FILMCRAFT), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    if head != pin["commit"] or dirty:
        print(f"build_filmcraft: {FILMCRAFT} is at {head[:8]}{' (dirty)' if dirty else ''}; the pin is {pin['commit'][:8]} — move the pin deliberately"); return 1
    subprocess.run(["cargo", "build", "--release", "--locked", "-p", "filmcraft-cli"], cwd=str(FILMCRAFT), check=True)
    built = FILMCRAFT / "target" / "release" / pin["binary"]
    TOOLS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, binary)
    pin["sha256"] = sha256(binary)
    pin["bytes"] = binary.stat().st_size
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"build_filmcraft: wrote {binary} ({pin['bytes']} B, sha256 {pin['sha256'][:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
