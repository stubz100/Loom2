"""CA1 step 2 (01 §9a, D101) headed check: the Detailed level with the **real** starter set's mannequins (Quaternius UAL2, male and female)
in the Stage's own renderer — a stage with a Simple figure (walk), a Detailed male (point, a fist on the left hand) and a Detailed female
(sit, the right hand pointing), its passes rendered through the Shot path in a visible Edge (WebGL; no GPU job runs beside it), and the
clay, depth, mask and pose passes saved under engine/spikes/out/ca1/ for a look: the mannequins posed like their figures (not in their
bind pose: the depth shader skins), their masks, and — D101 — hands and feet in the pose pass for the Detailed figures only.

Needs the frontend dev server on 1420 (`npx vite --host 127.0.0.1 --port 1420 --strictPort` in frontend/) and the starter set in
<models root>/motion. The engine is not started.

    orchestrator/.venv/Scripts/python.exe scripts/ca1_detailed_check.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "scripts"))
from edit_headed_check import CDP, EDGE  # noqa: E402

PORT, TOKEN, DEV, DBG = 8783, "ca1", 1420, 9336
OUT = ROOT / "engine" / "spikes" / "out" / "ca1"


def api(method, path, body=None, raw=False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def figure(oid, name, x, preset, joints=None, detail=None, extra=None):
    return {"id": oid, "kind": "mannequin", "name": name, "preset": "adult", "transform": {"pos": [x, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
            "pose": {"preset": preset, "joints": joints or {}, "extra": extra or {}}, "colour_id": 1, "detail": detail}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    tmp = Path(tempfile.mkdtemp(prefix="loom2-ca1-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8199}})                          # no engine: a port nothing listens on
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=(OUT / "orchestrator.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT, text=True)
    edge = None
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CA1", "size_cap_gb": 20})
        st = api("POST", "/stages", {"name": "Detailed check"})
        cam = st["cameras"][0]
        cam.update(pos=[0, 1.2, 5.2], target=[0, 0.95, 0])
        objs = [figure("fig_simple", "Simple", -1.4, "walk"),
                figure("fig_male", "Detailed male", 0.0, "point", detail="male"),
                figure("fig_female", "Detailed female", 1.4, "wave", detail="female")]
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam]})
        url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check", "--window-size=1600,1000",
                                 "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 30 and not ws_url:
            try:
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json", timeout=3)):
                    if t.get("type") == "page" and f"127.0.0.1:{DEV}" in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.5)
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
        cdp.call("Page.reload")                                                           # as st_acceptance: the first load settles, then a clean one
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame') && !!window.__loom2Stage", timeout=60, settle=1.0)
        cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
        cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 3", timeout=30, settle=8.0)   # the mannequins load
        # hands through the app's own path (the viewport's Detailed figures): a fist on the male's left, the female's right pointing
        for oid, side, preset in (("fig_male", "l", "fist"), ("fig_female", "r", "point")):
            extra = cdp.eval(f"(async () => {{ const m = await import('/src/suites/stage/stageCommands.ts'); return m.viewport.handPreset?.({json.dumps(oid)}, {json.dumps(side)}, {json.dumps(preset)}) ?? null }})()")
            print(oid, side, preset, "→", len(extra or {}), "finger bones")
            if extra:
                cdp.eval(f"(async () => {{ const m = await import('/src/suites/stage/stageStore.ts'); m.st().setExtra({json.dumps(oid)}, {json.dumps(extra)}) }})()")
        cdp.wait_for("true", timeout=5, settle=2.0)
        cdp.call("Page.captureScreenshot")
        shot = cdp.call("Page.captureScreenshot", format="png")
        import base64
        (OUT / "viewport.png").write_bytes(base64.b64decode(shot["data"]))
        ok = cdp.eval("window.__loom2Stage.renderPasses()", timeout=120)
        state = cdp.eval("window.__loom2Stage.state()") or {}
        assets = (state.get("passes") or {}).get("assets") or {}
        print("passes rendered:", ok, sorted(assets))
        for name, aid in assets.items():
            (OUT / f"pass_{name}.png").write_bytes(api("GET", f"/assets/{aid}/file", raw=True))
        print("errors:", cdp.page_errors()[:3])
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        try:
            api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
    print(f"outputs: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
