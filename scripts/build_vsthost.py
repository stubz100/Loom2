"""D127 (proto01_animate 30 §16, AU3): build loom2's own VST3 host — engine/vsthost/, C++ on Steinberg's MIT-licensed VST 3 SDK — and keep
its pin.

    python scripts/build_vsthost.py           fetch the SDK at the pinned tag into engine/tools/vst3sdk (with only the submodules a host needs:
                                              base, cmake, pluginterfaces, public.sdk), build loom2-vsthost and two of the SDK's sample effects
                                              (again-sample-accurate, adelay: the tests' plug-ins) with CMake and Visual Studio 2022 (x64,
                                              Release, the static runtime), copy them into engine/tools/vsthost/ (git-ignored) and record the
                                              binary's sha256 and size and the host source's hash in engine/vsthost.pin.json
    python scripts/build_vsthost.py --check   the pin is well formed, its source hash is engine/vsthost/'s and, when the binary is here, it
                                              matches (CI runs this; the binary is never in git)

Nothing is installed into the system's VST3 folders (SMTG_CREATE_PLUGIN_LINK off). The pin moves deliberately: edit `sdk.tag` and
`sdk.commit`, delete engine/tools/vst3sdk, build, commit the new pin with a D-number.
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
PIN = ROOT / "engine" / "vsthost.pin.json"
SRC = ROOT / "engine" / "vsthost"
SDK = ROOT / "engine" / "tools" / "vst3sdk"
BUILD = ROOT / "engine" / "tools" / "vsthost-build"
TOOLS = ROOT / "engine" / "tools" / "vsthost"
SUBMODULES = ("base", "cmake", "pluginterfaces", "public.sdk")
TEST_PLUGINS = ("again-sample-accurate", "adelay")        # the SDK's target names (and their bundles')


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_hash() -> str:
    """The host's source (CMakeLists.txt and every file under src/, by its path and its bytes with line endings made LF; notes are not source)."""
    h = hashlib.sha256()
    for p in sorted([SRC / "CMakeLists.txt", *(x for x in (SRC / "src").rglob("*") if x.is_file())]):
        h.update(p.relative_to(SRC).as_posix().encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def check(pin: dict, binary: Path) -> tuple[bool, str]:
    sdk = pin.get("sdk", {})
    for k in ("repository", "tag", "commit"):
        if k not in sdk:
            return False, f"the pin's sdk lacks `{k}`"
    if not re.fullmatch(r"[0-9a-f]{40}", str(sdk["commit"])):
        return False, f"the pin's sdk commit is not a full sha: {sdk['commit']!r}"
    for k in ("binary", "sha256", "bytes", "source"):
        if k not in pin:
            return False, f"the pin lacks `{k}` — build it"
    if pin["source"] != source_hash():
        return False, "engine/vsthost/ changed since the pin — rebuild"
    if not binary.is_file():
        return True, f"{binary.name} is not built here (engine/tools/ is git-ignored); the pin is well formed (VST 3 SDK {sdk['tag']})"
    got, size = sha256(binary), binary.stat().st_size
    if got != pin["sha256"] or size != pin["bytes"]:
        return False, f"{binary.name} sha256 {got[:12]}... / {size} B != pinned {pin['sha256'][:12]}... / {pin['bytes']} B - rebuild, or move the pin deliberately"
    return True, f"{binary.name} matches its pin (VST 3 SDK {sdk['tag']}, {size} B)"


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True, text=True, check=True).stdout.strip()


def fetch(sdk: dict) -> None:
    if not (SDK / ".git").exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", sdk["tag"], sdk["repository"], str(SDK)], check=True)
    have = git("rev-parse", "HEAD", cwd=SDK)
    if have != sdk["commit"]:
        raise SystemExit(f"build_vsthost: {SDK} is at {have[:8]}; the pin is {sdk['commit'][:8]} ({sdk['tag']}) — delete it to fetch again")
    subprocess.run(["git", "submodule", "update", "--init", "--depth", "1", *SUBMODULES], cwd=str(SDK), check=True)


def main() -> int:
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    binary = TOOLS / pin.get("binary", "loom2-vsthost.exe")
    if "--check" in sys.argv:
        ok, msg = check(pin, binary)
        print(f"build_vsthost: {msg}")
        return 0 if ok else 1
    fetch(pin["sdk"])
    subprocess.run(["cmake", "-S", str(SRC), "-B", str(BUILD), "-G", "Visual Studio 17 2022", "-A", "x64", f"-DVST3_SDK_ROOT={SDK.as_posix()}"], check=True)
    for target in ("loom2-vsthost", *TEST_PLUGINS):              # one at a time: MSBuild took the native flags for a project with several targets
        subprocess.run(["cmake", "--build", str(BUILD), "--config", "Release", "--target", target, "--parallel"], check=True)
    TOOLS.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BUILD / "Release" / "loom2-vsthost.exe", binary)
    plugins = TOOLS / "test-plugins"
    shutil.rmtree(plugins, ignore_errors=True)
    for name in TEST_PLUGINS:
        bundle = BUILD / "VST3" / "Release" / f"{name}.vst3"
        if not bundle.exists():
            raise SystemExit(f"build_vsthost: {bundle} was not built")
        shutil.copytree(bundle, plugins / f"{name}.vst3")
    pin.update({"binary": binary.name, "sha256": sha256(binary), "bytes": binary.stat().st_size, "source": source_hash()})
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(f"build_vsthost: wrote {binary} ({pin['bytes']} B, sha256 {pin['sha256'][:12]}...) and {len(TEST_PLUGINS)} test plug-ins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
