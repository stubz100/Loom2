"""D62: build PhotoCraft's content-aware fill / PatchMatch extension (orchestrator/native/pcalgo) as an abi3 wheel and commit it.

    python scripts/build_pcalgo.py           rebuild orchestrator/vendor/loom2_pcalgo-*.whl from the pinned PhotoCraft checkout
    python scripts/build_pcalgo.py --check   verify the committed wheel against pcalgo.pin.json (no Rust needed; CI runs this)

The crate depends on photocraft-algo by path: the PhotoCraft checkout must sit beside this repository, clean, at the pinned commit.
Needs Rust (MSVC) and uv (maturin runs through `uvx`)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "orchestrator" / "native" / "pcalgo"
VENDOR = ROOT / "orchestrator" / "vendor"
PIN = VENDOR / "pcalgo.pin.json"
PHOTOCRAFT = ROOT.parent / "photocraft"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    wheel = VENDOR / pin["wheel"] if pin.get("wheel") else None
    if "--check" in sys.argv:
        if not wheel or not wheel.is_file():
            print(f"build_pcalgo: the pinned wheel {pin.get('wheel')!r} is missing"); return 1
        got = sha256(wheel)
        if got != pin["sha256"]:
            print(f"build_pcalgo: {wheel.name} sha256 {got} != pinned {pin['sha256']}"); return 1
        print(f"build_pcalgo: {wheel.name} matches its pin (photocraft {pin['photocraft'][:8]}, {wheel.stat().st_size} B)")
        return 0
    head = subprocess.run(["git", "-C", str(PHOTOCRAFT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(PHOTOCRAFT), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    if head != pin["photocraft"] or dirty:
        print(f"build_pcalgo: {PHOTOCRAFT} is at {head}{' (dirty)' if dirty else ''}; the pin is {pin['photocraft']} — move the pin deliberately"); return 1
    out = CRATE / "target" / "wheels"
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run(["uvx", "maturin", "build", "--release", "-m", str(CRATE / "Cargo.toml")], check=True)
    built = sorted(out.glob("loom2_pcalgo-*.whl"))[-1]
    for old in VENDOR.glob("loom2_pcalgo-*.whl"):
        old.unlink()
    shutil.copyfile(built, VENDOR / built.name)
    pin.update(wheel=built.name, sha256=sha256(VENDOR / built.name), bytes=(VENDOR / built.name).stat().st_size)
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"build_pcalgo: wrote {VENDOR / built.name} ({pin['bytes']} B, sha256 {pin['sha256'][:12]}…) — then: uv lock --project orchestrator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
