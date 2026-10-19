"""CA1b (D104) — Stage's side of the skeleton check, in a visible Edge through the app's own code (no engine, no GPU job): figures at the
Detailed level (♀ and ♂) and one Simple figure, each given a CC0 clip from the starter set (Walk_Loop in place, Sitting_Enter, Idle_Loop),
the pose sequence rendered from a front camera at 832×480. Per frame it measures, from the 18 keypoints and the D101 hand and foot
markers the pose pass draws:

- **feet on their ankles**: the largest distance from a heel marker to its own ankle point, as a fraction of the leg's length in the frame
  (a seated figure's nose → ankles shrinks; the leg does not), and how far the toes reach sideways (a foot turned out shows here);
- the **proportions** E23b compared with the characters' references (nose → neck, shoulders, hips, leg, arm, hand, foot), as ratios of the
  height, on frames where the figure stands facing the camera.

With `--bodies <json>` the figures take those bodies (the fitted ones) and the ratios are compared with `--targets <json>` (the
references' ratios, from engine/spikes/e23b_proportions.py): the bar is ±10 %.

Needs the frontend dev server on 1420 and the starter set in <models root>/motion.

    orchestrator/.venv/Scripts/python.exe scripts/ca1b_skeleton_check.py [--bodies b.json --targets t.json]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "scripts"))
from edit_headed_check import CDP, EDGE  # noqa: E402

PORT, TOKEN, DEV, DBG = 8788, "ca1b", 1420, 9340
OUT = ROOT / "engine" / "spikes" / "out" / "ca1b"
W, H = 832, 480
BARS = {"foot_off": 0.15, "ratio": 0.10}
FIGS = [  # id, level, clip, x
    ("fig_f", "female", "Idle_Loop", -1.2), ("fig_m", "male", "Sitting_Enter", 0.0), ("fig_s", None, "Walk_Loop", 1.2)]


def api(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8") or "null")


JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const An = await import('/src/suites/stage/anim.ts')
  const M = await import('/src/suites/stage/motion/motionStore.ts')
  const lib = await import('/src/suites/stage/motion/library.ts')
  const st = S.st, mm = () => M.useMotion.getState()
  await mm().refresh()
  const file = mm().files.find((f) => f.name === 'AnimationLibrary_Godot_Standard')
  const clips = await lib.clipsOf(file), clip = (n) => clips.find((c) => c.name === n)
  for (const [id, , name] of %FIGS%) {
    st().select(id); st().setFrame(0)
    mm().pick(clip(name)); mm().set({ lock: name !== 'Walk_Loop', alongPath: false, blend: 0, inPlace: true }); await mm().apply()
  }
  st().setRange(0, 72); st().setFrame(0)
  await new Promise((r) => setTimeout(r, 2500))
  const doc = st().current, R = st().sequenceRenderer
  const out = {}
  for (const [id] of %FIGS%) {
    const seq = Array.from({ length: 73 }, (_, i) => { const d = An.sampleDoc(doc, i); return { cam: d.cameras[0], doc: { ...d, objects: d.objects.map((x) => (x.kind === 'mannequin' && x.id !== id ? { ...x, visible: false } : x)) } } })
    const r = await R(seq, %W%, %H%, 'pose', An.sampleDoc(doc, 0))
    out[id] = { keypoints: r.keypoints.map((k) => k[0] ?? []), wholebody: (r.wholebody ?? []).map((k) => k[0] ?? null) }
    if (id === %FIGS%[0][0]) out.png = await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(',')[1]); fr.readAsDataURL(r.blobs[0]) })
  }
  return out
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def ratios(b: list, wb: dict | None) -> dict | None:
    b = np.array(b, float)
    if len(b) < 18 or (b[[0, 1, 8, 11, 10, 13], 2] <= 0).any():
        return None
    d = lambda i, j: float(np.linalg.norm(b[i, :2] - b[j, :2]))  # noqa: E731
    ank = (b[10, :2] + b[13, :2]) / 2
    h = float(np.linalg.norm(b[0, :2] - ank))
    hip = (b[8, :2] + b[11, :2]) / 2
    r = {"height_px": h, "head_neck": d(0, 1) / h, "torso": float(np.linalg.norm(b[1, :2] - hip)) / h, "shoulders": d(2, 5) / h, "hips": d(8, 11) / h,
         "leg": (d(8, 9) + d(9, 10) + d(11, 12) + d(12, 13)) / 2 / h, "arm": (d(2, 3) + d(3, 4) + d(5, 6) + d(6, 7)) / 2 / h}
    if b[16, 2] > 0 and b[17, 2] > 0:
        r["head_w"] = d(16, 17) / h                                    # ear to ear
    if wb:
        hs = [float(np.linalg.norm(np.array(hand[0][:2]) - np.array(hand[12][:2]))) for hand in (wb["left"], wb["right"]) if hand and hand[0][2] > 0 and hand[12][2] > 0]
        if hs:
            r["hand"] = float(np.median(hs)) / h
        ps = [float(np.linalg.norm(np.array(hand[0][:2]) - np.array(hand[9][:2]))) for hand in (wb["left"], wb["right"]) if hand and hand[0][2] > 0 and hand[9][2] > 0]
        if ps:
            r["palm"] = float(np.median(ps)) / h                       # wrist → the middle finger's base (what the fit matches)
        f = np.array(wb["feet"], float)
        fl = [float(np.linalg.norm(f[k, :2] - f[k + 2, :2])) for k in (0, 3) if f[k, 2] > 0 and f[k + 2, 2] > 0]
        if fl:
            r["foot"] = float(np.median(fl)) / h
        # each heel against its own ankle (COCO-WholeBody: the left foot first; COCO-18: 13 = left ankle, 10 = right ankle) — a turned foot is
        # long in the frame, but its heel stays under its ankle
        leg2d = r["leg"] * h                                            # the heel against the leg's length (a seated figure's nose → ankles shrinks)
        r["foot_off"] = max(float(np.linalg.norm(f[side + 2, :2] - b[ank_i, :2])) for side, ank_i in ((0, 13), (3, 10))) / leg2d
        # how far the toes turn from the figure's facing, seen from the front: the toe's sideways reach against the foot's length
        r["toe_side"] = max(abs(float(f[side, 0] - f[side + 2, 0])) for side in (0, 3)) / h
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", type=Path)
    ap.add_argument("--targets", type=Path)
    ap.add_argument("--as", dest="as_", default=None, help="the character in bodies.json / targets.json to put on the standing ♀ figure (fig_f)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("the frontend dev server is not on 1420"); return 2
    bodies = json.loads(a.bodies.read_text(encoding="utf-8")) if a.bodies else {}
    if a.as_:
        bodies = {"fig_f": bodies[a.as_]}
    tmp = Path(tempfile.mkdtemp(prefix="loom2-ca1b-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8199}})
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"),
                            env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=(OUT / "orchestrator.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)
    edge = None
    failures: list[str] = []
    result: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "bodies": bodies}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CA1b", "size_cap_gb": 20})
        st = api("POST", "/stages", {"name": "CA1b"})
        cam = {**st["cameras"][0], "pos": [0, 1.0, 5.2], "target": [0, 0.9, 0], "focal_mm": 32}
        objs = [{"id": "set_a", "kind": "set", "name": "Floor", "preset": "empty", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "colour_id": 4}]
        for fid, level, _, x in FIGS:
            objs.append({"id": fid, "kind": "mannequin", "name": fid, "preset": "adult", "transform": {"pos": [x, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]},
                         "pose": {"preset": "stand", "joints": {}, "extra": {}}, "colour_id": 1, "detail": level, **({"body": bodies[fid]} if fid in bodies else {})})
        st = api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}})
        url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                 "--window-size=1600,1000", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        cdp.wait_for(f"!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === {len(objs)}", timeout=30, settle=10.0)
        r = cdp.eval(JS.replace("%FIGS%", json.dumps([[f, lv, c] for f, lv, c, _ in FIGS])).replace("%W%", str(W)).replace("%H%", str(H)), timeout=900) or {}
        if not r or r.get("error"):
            failures.append(str(r.get("error") if r else cdp.page_errors()[:3]))
        else:
            if r.get("png"):
                (OUT / "pose_f_000.png").write_bytes(base64.b64decode(r.pop("png")))
            (OUT / "sequences.json").write_text(json.dumps(r), encoding="utf-8")
            targets = json.loads(a.targets.read_text(encoding="utf-8")) if a.targets else {}
            if a.as_:
                targets = {"fig_f": targets[a.as_]}
            for fid, level, clip, _ in FIGS:
                rows = [ratios(k, wb) for k, wb in zip(r[fid]["keypoints"], r[fid]["wholebody"])]
                rows = [x for x in rows if x]
                if not rows:
                    failures.append(f"{fid}: no measurable frame"); continue
                summ = {k: round(float(np.median([x[k] for x in rows if k in x])), 3) for k in rows[0] if k not in ("foot_off", "toe_side")}
                if level:
                    summ["foot_off_max"] = round(max(x.get("foot_off", 0) for x in rows), 3)
                    summ["toe_side_max"] = round(max(x.get("toe_side", 0) for x in rows), 3)
                    if summ["foot_off_max"] > BARS["foot_off"]:
                        worst = max(range(len(rows)), key=lambda i: rows[i].get("foot_off", 0))
                        failures.append(f"{fid} ({level}, {clip}): a heel {summ['foot_off_max']:.3f} of the leg from its ankle (frame {worst}; bar {BARS['foot_off']})")
                result[fid] = {"level": level, "clip": clip, **summ}
                print(fid, level, clip, summ)
                for k, want in (targets.get(fid) or {}).items():
                    if k in summ and want:
                        off = summ[k] / want - 1
                        if abs(off) > BARS["ratio"]:
                            failures.append(f"{fid}: {k} {summ[k]:.3f} against the reference's {want:.3f} ({off:+.0%}; bar ±{BARS['ratio']:.0%})")
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
    with (OUT / "check.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    for x in failures:
        print("FAIL", x)
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
