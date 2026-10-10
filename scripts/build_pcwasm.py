"""D59: build PhotoCraft's Quick Selection / Magnetic Lasso WebAssembly module and commit it with its pin and checksum.

    python scripts/build_pcwasm.py           rebuild frontend/src/suites/edit/smartselect/pcwasm.wasm from the pinned PhotoCraft checkout
    python scripts/build_pcwasm.py --check   verify the committed module against pcwasm.pin.json (no Rust needed; CI runs this)

The crate (frontend/wasm/pcwasm) depends on photocraft-algo by path: the PhotoCraft checkout must sit beside this repository
(../photocraft), clean, at the pinned commit. Needs `rustup target add wasm32-unknown-unknown`."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "frontend" / "wasm" / "pcwasm"
OUT = ROOT / "frontend" / "src" / "suites" / "edit" / "smartselect"
PIN = OUT / "pcwasm.pin.json"
WASM = OUT / "pcwasm.wasm"
PHOTOCRAFT = ROOT.parent / "photocraft"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    if "--check" in sys.argv:
        if not WASM.is_file():
            print(f"build_pcwasm: {WASM} missing"); return 1
        got = sha256(WASM)
        if got != pin["sha256"]:
            print(f"build_pcwasm: {WASM.name} sha256 {got} != pinned {pin['sha256']}"); return 1
        print(f"build_pcwasm: {WASM.name} matches its pin (photocraft {pin['photocraft'][:8]}, {WASM.stat().st_size} B)")
        return 0
    head = subprocess.run(["git", "-C", str(PHOTOCRAFT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(PHOTOCRAFT), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip()
    if head != pin["photocraft"] or dirty:
        print(f"build_pcwasm: {PHOTOCRAFT} is at {head}{' (dirty)' if dirty else ''}; the pin is {pin['photocraft']} — move the pin deliberately"); return 1
    subprocess.run(["cargo", "build", "--release", "--target", "wasm32-unknown-unknown", "--manifest-path", str(CRATE / "Cargo.toml")], check=True)
    built = CRATE / "target" / "wasm32-unknown-unknown" / "release" / "loom2_pcwasm.wasm"
    shutil.copyfile(built, WASM)
    pin["sha256"] = sha256(WASM)
    pin["bytes"] = WASM.stat().st_size
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"build_pcwasm: wrote {WASM} ({pin['bytes']} B, sha256 {pin['sha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
