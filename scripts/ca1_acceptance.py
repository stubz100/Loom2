"""CA1 (proto01_animate 02 §5) acceptance with the real CC0 starter set, in a visible Edge through the app's own code (no engine, no GPU
job): a Detailed figure gets a curved floor path; the library's Walk_Loop is applied along it with the feet locked (a loop repeats to the
path's end); then a turn on the spot (two rotation keys) and the `point` preset are keyed after it. Measured from the stage document's keys:
the planted foot's largest drift over the walk (keySlide, the bar ≤ 2 cm), the farthest the figure strays from the path, how close it
ends to the path's end; the pose pass sequence of the whole move is rendered (the D101 hands and feet in it) and saved with a strip of the
viewport for a look. The "< 2 min of clicks" and the Mixamo import are the author's (.docs/proto01_animate/08-testing-ca1.md).

Needs the frontend dev server on 1420 and the starter set in <models root>/motion.

    orchestrator/.venv/Scripts/python.exe scripts/ca1_acceptance.py
"""
from __future__ import annotations

import base64
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

PORT, TOKEN, DEV, DBG = 8785, "ca1a", 1420, 9337
OUT = ROOT / "engine" / "spikes" / "out" / "ca1"
PATH = [[0.0, 0.0], [0.0, 1.6], [1.2, 2.8], [2.6, 3.2]]
BARS = {"slide_m": 0.02}


def api(method, path, body=None, raw=False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const M = await import('/src/suites/stage/motion/motionStore.ts')
  const F = await import('/src/suites/stage/motion/footlock.ts')
  const P = await import('/src/suites/stage/motion/path.ts')
  const st = S.st, m = M.useMotion.getState()
  st().select('fig_a'); st().setFrame(0)
  await m.refresh()
  const file = M.useMotion.getState().files.find((f) => f.name === 'AnimationLibrary_Godot_Standard')
  if (!file) return { error: 'the starter library is not listed' }
  const lib = await import('/src/suites/stage/motion/library.ts')
  const clip = (await lib.clipsOf(file)).find((c) => c.name === 'Walk_Loop')
  M.useMotion.getState().pick(clip); M.useMotion.getState().set({ lock: true, alongPath: true, blend: 6 })
  const t0 = performance.now()
  await M.useMotion.getState().apply()
  const applyMs = performance.now() - t0
  const doc = st().current
  const walk = (doc.keyframes.objects.fig_a ?? []).slice()
  const end = walk[walk.length - 1].frame
  // a turn on the spot: the figure's yaw keyed a quarter turn over 16 frames, then the point preset keyed 12 frames later
  st().setFrame(end); st().keyObject('fig_a')
  const o = st().sampledDoc().objects.find((x) => x.id === 'fig_a')
  st().setFrame(end + 16); st().setTransform('fig_a', { pos: o.transform.pos, rot: [0, o.transform.rot[1] + 90, 0], scale: o.transform.scale }); st().keyObject('fig_a')
  st().setFrame(end + 28); st().applyPose('fig_a', 'point'); st().keyObject('fig_a')
  st().setRange(0, end + 40)
  // measures: the planted foot over the walk, the path's distance
  const m2 = P.measure(%PATH%)
  const seg = (x, z) => Math.min(...m2.points.slice(1).map(([bx, bz], i) => { const [ax, az] = m2.points[i]; const vx = bx - ax, vz = bz - az, l2 = vx * vx + vz * vz; const t = l2 ? Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / l2)) : 0; return Math.hypot(x - ax - vx * t, z - az - vz * t) }))
  const dense = []
  for (let f = 0; f <= end; f++) { const s = (await import('/src/suites/stage/anim.ts')).sampleObject(doc.objects.find((x) => x.id === 'fig_a'), walk, f); dense.push({ transform: s.transform, pose: s.pose }) }
  const last = walk[walk.length - 1].transform.pos, goal = %PATH%[%PATH%.length - 1]
  return { applyMs: Math.round(applyMs), keys: walk.length, frames: end + 1, slide: F.keySlide(dense), offPath: Math.max(...dense.map((d) => seg(d.transform.pos[0], d.transform.pos[2]))),
    toEnd: Math.hypot(last[0] - goal[0], last[2] - goal[1]), turnEnd: end + 16, pointAt: end + 28 }
} catch (e) { return { error: String(e && e.stack || e) } } })()""".replace("%PATH%", json.dumps(PATH))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    tmp = Path(tempfile.mkdtemp(prefix="loom2-ca1a-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8199}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=(OUT / "acceptance_orchestrator.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT, text=True)
    edge = None
    failures: list[str] = []
    result: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M")}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CA1", "size_cap_gb": 20})
        st = api("POST", "/stages", {"name": "CA1 acceptance"})
        cam = st["cameras"][0]
        cam.update(pos=[5.5, 2.4, -1.5], target=[1.2, 0.9, 1.8], focal_mm=28)
        fig = {"id": "fig_a", "kind": "mannequin", "name": "Walker", "preset": "adult", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
               "pose": {"preset": "stand", "joints": {}, "extra": {}}, "colour_id": 1, "detail": "male", "path": PATH}
        set_ = {"id": "set_a", "kind": "set", "name": "Floor", "preset": "empty", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "colour_id": 2}
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": [set_, fig], "cameras": [cam]})
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
        cdp.call("Page.reload")
        cdp.wait_for("document.readyState === 'complete' && !!window.__loom2Stage", timeout=60, settle=1.0)
        cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
        cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 2", timeout=30, settle=6.0)
        r = cdp.eval(JS, timeout=300) or {}
        print("measures:", r)
        result.update(r)
        if not r:
            failures.append(f"the in-page run returned nothing ({cdp.page_errors()[:3]})")
        elif r.get("error"):
            failures.append(r["error"])
        else:
            if r["slide"] > BARS["slide_m"]:
                failures.append(f"the planted foot drifts {r['slide'] * 100:.1f} cm (bar ≤ {BARS['slide_m'] * 100:.0f} cm)")
            if r["toEnd"] > 0.6:
                failures.append(f"the walk ends {r['toEnd']:.2f} m from the path's end")
        # a look: the viewport through the camera at four moments, and the pose sequence of the whole move
        cdp.eval("window.__loom2Stage.setFrame(0)")
        shots = []
        for f in (0, max(1, r.get("frames", 40) // 2), r.get("frames", 40) - 1, r.get("pointAt", 40) + 4):
            cdp.eval(f"window.__loom2Stage.setFrame({f})")
            cdp.wait_for("true", timeout=5, settle=0.6)
            shot = cdp.call("Page.captureScreenshot", format="png")
            p = OUT / f"acceptance_frame_{f:03d}.png"
            p.write_bytes(base64.b64decode(shot["data"]))
            shots.append(str(p))
        result["shots"] = shots
        cdp.eval("(async () => { const S = await import('/src/suites/stage/stageStore.ts'); S.st().setGuideKind('pose') })()")
        ok = cdp.eval("window.__loom2Stage.renderGuide()", timeout=600)
        guide = (cdp.eval("window.__loom2Stage.state()") or {}).get("guide")
        if ok and guide:
            (OUT / "acceptance_pose.mp4").write_bytes(api("GET", f"/assets/{guide['asset_id']}/file", raw=True))
            result["pose_frames"] = guide.get("frames")
        else:
            failures.append(f"the pose sequence was not rendered ({cdp.page_errors()[:2]})")
        errs = cdp.page_errors()
        if errs:
            failures.append(f"page errors: {errs[:3]}")
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        try:
            api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
    result["failures"] = failures
    with (OUT / "acceptance.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result, indent=1))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
