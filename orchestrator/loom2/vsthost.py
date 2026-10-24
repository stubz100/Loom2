"""D127 (proto01_animate 30 §16, AU3): loom2's own VST3 host as a sidecar — `loom2-vsthost` (engine/vsthost/, on Steinberg's MIT-licensed
VST 3 SDK; built by scripts/build_vsthost.py), one process per request, in the orchestrator's job object: a plug-in that crashes ends that
process, never loom2, and its end is said in loom2's words.

- `plugins()`: the installed effects — the system's VST3 folders and the author's own (Settings › Audio) — each bundle scanned in a process
  of its own, the answers kept by path and modification time in the state folder (`vst-scan.json`); an instrument is left out, a bundle that
  fails is listed with its reason.
- `render()`: a WAV through a chain offline (each effect's latency taken off, a bypassed one skipped).
- `editor()`: a plug-in's own editor in a window of the host's; it returns when the author closes the window, the state in a file.
- `params()` / `state()`: an effect's parameters, and its state with parameters set (normalised) — the tests' and the rig's.

An effect's state is the host's file (component and controller state, `L2VS`); loom2 keeps it with the cut (AU4). A `.py` in Settings ›
vsthost › cli runs under this interpreter (tests/fake_vsthost.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from .config import AppState
from .engine.supervisor import _assign_to_job
from .fsio import atomic_write_json, read_json_or
from .mcp_session import cli_head

SCAN_CACHE = "vst-scan.json"
SCAN_VERSION = 1


class VstHostError(RuntimeError):
    """The host refused (its message), stopped without an answer (a plug-in crashed), timed out, or is not built here."""


class VstHost:
    def __init__(self, app: AppState) -> None:
        self.app = app
        self._scan_lock = threading.Lock()

    @property
    def settings(self):
        return self.app.settings.vsthost

    def available(self) -> bool:
        return Path(self.settings.cli).is_file()

    def _run(self, args: list[str], timeout: float | None) -> dict:
        if not self.available():
            raise VstHostError("loom2's VST3 host is not built here (python scripts/build_vsthost.py)")
        proc = subprocess.Popen([*cli_head(self.settings), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _assign_to_job(proc)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise VstHostError(f"the plug-in host took longer than {timeout:.0f} s and was stopped")
        line = next((x for x in reversed(out.splitlines()) if x.strip().startswith("{")), None)
        if line is None:
            crash = proc.returncode not in (0, 1)
            raise VstHostError(f"the plug-in host stopped without an answer (exit code {proc.returncode}{' — a plug-in crashed' if crash else ''}); "
                               f"loom2 is fine{': ' + err.strip().splitlines()[-1] if err.strip() else ''}")
        res = json.loads(line)
        if not res.get("ok"):
            raise VstHostError(res.get("error") or "the plug-in host refused")
        return res

    # ---- the installed effects -------------------------------------------------------------------------------------------------
    def bundles(self) -> list[str]:
        """The system's VST3 bundles (the SDK's own list) and those in the author's folders."""
        found = list(self._run(["paths"], self.settings.scan_timeout_s).get("paths", []))
        for folder in self.settings.folders:
            d = Path(folder)
            if d.is_dir():
                found += [str(p) for p in sorted(d.rglob("*.vst3")) if not any(q.suffix.lower() == ".vst3" for q in p.parents)]
        out, seen = [], set()
        for b in found:
            if os.path.normcase(b) not in seen:
                seen.add(os.path.normcase(b))
                out.append(b)
        return out

    def plugins(self, rescan: bool = False) -> dict:
        """{plugins: [{bundle, uid, name, vendor, version, sub}], failed: [{bundle, error}]} — the effects, scanned once per bundle change."""
        with self._scan_lock:
            cache_path = self.app.state_dir / SCAN_CACHE
            cache = read_json_or(cache_path, {})
            if cache.get("version") != SCAN_VERSION or rescan:
                cache = {"version": SCAN_VERSION, "bundles": {}}
            known: dict[str, Any] = cache["bundles"]
            now: dict[str, Any] = {}
            for b in self.bundles():
                try:
                    mtime = Path(b).stat().st_mtime
                except OSError:
                    continue
                hit = known.get(b)
                if hit and hit.get("mtime") == mtime:
                    now[b] = hit
                    continue
                try:
                    now[b] = {"mtime": mtime, "classes": self._run(["scan", b], self.settings.scan_timeout_s)["classes"]}
                except VstHostError as e:
                    now[b] = {"mtime": mtime, "error": str(e)}
            cache["bundles"] = now
            atomic_write_json(cache_path, cache)
        plugins = [{"bundle": b, **c} for b, v in now.items() for c in v.get("classes", []) if "instrument" not in c.get("sub", "").lower()]
        return {"plugins": sorted(plugins, key=lambda p: (p["vendor"].lower(), p["name"].lower())),
                "failed": [{"bundle": b, "error": v["error"]} for b, v in now.items() if "error" in v]}

    # ---- an effect --------------------------------------------------------------------------------------------------------------
    def params(self, bundle: str, uid: str, state: Path | None) -> dict:
        return self._run(["params", bundle, uid, str(state) if state else "-"], self.settings.scan_timeout_s)

    def state(self, bundle: str, uid: str, state_in: Path | None, state_out: Path, values: dict[int, float] | None = None) -> dict:
        state_out.parent.mkdir(parents=True, exist_ok=True)
        return self._run(["state", bundle, uid, str(state_in) if state_in else "-", str(state_out), *(f"{k}={v}" for k, v in (values or {}).items())],
                         self.settings.scan_timeout_s)

    def editor(self, bundle: str, uid: str, state_in: Path | None, state_out: Path, title: str) -> dict:
        """The plug-in's own editor; returns when the author closes its window (no time limit: it is the author's)."""
        state_out.parent.mkdir(parents=True, exist_ok=True)
        return self._run(["editor", bundle, uid, str(state_in) if state_in else "-", str(state_out), title], None)

    def render(self, chain: list[dict], wav_in: Path, wav_out: Path, gain_db: float = 0.0) -> dict:
        """`wav_in` through the chain ([{bundle, uid, state: Path | None, bypass}], in order) into `wav_out` (stereo float at the same rate);
        `gain_db` first, in float (AU4: a print's gain — FilmCraft's WAV is 16-bit, so the gain is not baked into it)."""
        wav_out.parent.mkdir(parents=True, exist_ok=True)
        tsv = wav_out.with_suffix(".chain.tsv")
        lines = [f"@gain\t{gain_db:g}\n"] if gain_db else []
        lines += [f"{e['bundle']}\t{e['uid']}\t{e.get('state') or '-'}\t{1 if e.get('bypass') else 0}\n" for e in chain]
        tsv.write_text("".join(lines), encoding="utf-8")
        try:
            return self._run(["render", str(tsv), str(wav_in), str(wav_out)], self.settings.render_timeout_s)
        finally:
            tsv.unlink(missing_ok=True)
