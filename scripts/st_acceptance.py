"""P13 ST3 (D78 / D81, 16 §13) acceptance: E10's bars reproduced through the app, on the rig. Needs the frontend dev server on 1420
(`npx vite --host 127.0.0.1 --port 1420 --strictPort` in frontend/), a visible Edge (the passes are rendered by the Stage suite's own
viewport — three.js, WebGL2 — as a user would) and port 8188 free: the orchestrator it starts launches the engine itself, so the
outputs land in its own state (`engine_out`); a standalone engine (`scripts/engine-start.ps1`) writes elsewhere and every job would
finish with no asset — stop it first (`scripts/engine-stop.ps1`).

What it does: starts its own orchestrator (port 8771, a temp state, models on F:), makes a project, imports E12's source 07 as the
character reference, builds a stage through the API (the room, two figures — walk and point — a prop, a 35 mm camera), opens it in
the browser, renders the five passes through the Shot tab's path (`window.__loom2Stage.renderPasses`), then queues one `StageShot`
per method (clay reference, exact pose) twice — cold, then warm — through the store (`generateShot`, so the form's own recipe runs).
For every job: the model and method the server resolved to, the wall time, the result asset (lineage `stage-shot`, parents = the
pass + the reference). Scoring (evaluation only, as E10): SDPose on the results → PCK@0.1 against the pose pass's keypoints; a
contact sheet (clay · pose · clay result · exact-pose result) and `engine/spikes/out/st/results.jsonl`.

Bars (16 §13, 08 §7 E10 / D78): the blocking kept (the author's look at the sheet) and PCK@0.1 ≥ 0.8 on the exact-pose results (E10
0.86; both methods scored 1.0 on 2026-10-13); every job done, every result carrying its lineage. Time bars are set from the app-level
runs of 2026-10-13 (the engine's upload, finish and cache behaviour included): clay warm ≤ 45 s (measured 14–32 s, cold 41–47 s),
exact pose ≤ 150 s (measured 108–121 s; its cache is dropped after each job, so "warm" is a reload from the page cache — without
that, the second shot streamed the LoRA-patched base 9B from RAM at 15.7 s/it and took 474 s).

    orchestrator/.venv/Scripts/python.exe scripts/st_acceptance.py [--methods clay,refcontrol] [--rounds 2]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "engine" / "spikes"))
sys.path.insert(0, str(ROOT / "scripts"))
from e10_stage import pck, sdpose_graph  # noqa: E402
from e12_angles import Engine  # noqa: E402
from edit_headed_check import CDP, EDGE  # noqa: E402

PORT, TOKEN, DBG, DEV, ENGINE = 8771, "stage", 9334, 1420, "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "st"
HEROINE = ROOT / "bench" / "angles" / "07.jpg"
PROMPT = ("The figure on the left is a woman in a red coat walking in; the figure on the right is a man in a grey suit pointing at her; a dim brick "
          "room, a wooden crate, a single warm lamp, cinematic film still, shallow depth of field, 35 mm")
BARS = {"clay": {"warm_s": 45.0}, "refcontrol": {"warm_s": 150.0, "pck": 0.8}, "clip": {"wall_s": 300.0, "pck": 0.5}}   # clip: E11 (D76) — the pose followed at PCK ≥ 0.5, ≤ 2× plain LTX


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def wait_job(jid: str, timeout_s: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = api("GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1.0)
    raise TimeoutError(jid)


def stage_doc(st: dict, heroine_id: str) -> dict:
    """The blocking: the E10 room, a figure walking in from the left, one pointing from the right, a crate, the camera at eye level."""
    cam = {**st["cameras"][0], "name": "Camera 1", "pos": [0.4, 1.5, 4.2], "target": [0.0, 1.0, 0.0], "focal_mm": 35}
    objs = [
        {"id": "set_room", "kind": "set", "name": "Set 1", "preset": "room", "asset_id": None, "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "parent": None, "locked": True, "visible": True, "colour_id": 0, "pose": None, "billboard": False},
        {"id": "fig_a", "kind": "mannequin", "name": "Figure 1", "preset": "adult", "asset_id": None, "transform": {"pos": [-0.9, 0, 0.3], "rot": [0, 35, 0], "scale": [1, 1, 1]}, "parent": None, "locked": False, "visible": True, "colour_id": 1, "pose": {"preset": "walk", "joints": {}}, "billboard": False},
        {"id": "fig_b", "kind": "mannequin", "name": "Figure 2", "preset": "adult", "asset_id": None, "transform": {"pos": [1.0, 0, -0.4], "rot": [0, -30, 0], "scale": [1, 1, 1]}, "parent": None, "locked": False, "visible": True, "colour_id": 2, "pose": {"preset": "point", "joints": {}}, "billboard": False},
        {"id": "prop_box", "kind": "prop", "name": "Prop 1", "preset": "block", "asset_id": None, "transform": {"pos": [1.6, 0, 0.9], "rot": [0, 20, 0], "scale": [1, 0.6, 1]}, "parent": None, "locked": False, "visible": True, "colour_id": 3, "pose": None, "billboard": False},
    ]
    return {**st, "name": "ST3 acceptance", "objects": objs, "cameras": [cam], "active_camera": cam["id"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="clay,refcontrol")
    ap.add_argument("--rounds", type=int, default=2, help="jobs per method (the first is cold)")
    ap.add_argument("--no-clip", dest="clip", action="store_false", help="skip ST4's clip (the keyed dolly, the depth sequence, LTX + the IC-LoRA)")
    a = ap.parse_args()
    methods = [m for m in a.methods.split(",") if m]
    if not EDGE:
        print("Edge not found"); return 2
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("frontend dev server not reachable on 1420 (npx vite --host 127.0.0.1 --port 1420 --strictPort)"); return 2
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1) — the orchestrator must launch its own so the outputs land in its state"); return 2
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-st-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                              "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")                       # never a pipe: an unread pipe fills and stalls the server mid-job
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    edge = None
    failures: list[str] = []

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text)
        if not ok:
            failures.append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "ST3", "size_cap_gb": 20})
        heroine = api("POST", "/assets/import", {"paths": [str(HEROINE)]})["items"][0]["id"]
        st = api("POST", "/stages", {"name": "ST3 acceptance"})
        st = api("PUT", f"/stages/{st['id']}", stage_doc(st, heroine))
        caps = api("GET", "/capabilities")["stage"]
        print("methods:", {m: (v["model_id"], v["seconds"], v["health"]) for m, v in caps["methods"].items()})
        for m in methods:
            check(m in caps["methods"] and caps["methods"][m]["health"] != "missing", f"method {m} offered with its weights present")
        # the browser: the Stage suite renders the passes
        url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=stage"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                 "--window-size=1600,1000", "--window-position=40,40", "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                                 "--disable-backgrounding-occluded-windows", "--disable-features=CalculateNativeWinOcclusion", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 30 and not ws_url:
            try:
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json", timeout=3)):
                    if t.get("type") == "page" and f"127.0.0.1:{DEV}" in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.5)
        if not ws_url:
            print("no page target"); return 1
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable"); cdp.call("Log.enable")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
        cdp.call("Page.reload")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=1.0)
        if not cdp.wait_for("!!window.__loom2Stage", timeout=60, settle=0.5):
            check(False, f"the Stage suite loaded (dev hook present) — page errors: {cdp.page_errors()[:3]}")
            return 1
        check(True, "the Stage suite loaded (dev hook present)")
        cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
        check(cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 4", timeout=30, settle=2.0), "the stage opened with its four objects")
        t0 = time.time()
        ok = cdp.eval("window.__loom2Stage.renderPasses()", timeout=120)
        render_s = time.time() - t0
        check(bool(ok), f"the passes rendered and uploaded in {render_s:.1f} s")
        state = cdp.eval("window.__loom2Stage.state()") or {}
        entry = state.get("passes")
        if not entry:
            check(False, f"no passes on the document — page errors: {cdp.page_errors()[:3]}")
            return 1
        check(bool(entry) and set(entry["assets"]) == {"clay", "depth", "normal", "pose", "mask"}, "five pass assets on the document")
        check(bool(entry) and len(entry["keypoints"]) == 2 and all(len(k) == 18 for k in entry["keypoints"]), "two figures × COCO-18 keypoints")
        check(bool(entry) and entry["size"] == {"w": 1280, "h": 720}, "Draft size 1280×720")
        passes_dir = OUT / "passes"
        passes_dir.mkdir(exist_ok=True)
        for name, aid in entry["assets"].items():
            (passes_dir / f"{name}.png").write_bytes(api("GET", f"/assets/{aid}/file", raw=True))
        pose_asset = api("GET", f"/assets/{entry['assets']['pose']}")
        check(pose_asset["lineage_kind"] == "stage-pass" and pose_asset["params"]["pass"] == "pose" and len(pose_asset["params"]["keypoints"]) == 2, "the pose pass asset carries its keypoints")
        doc = api("GET", f"/stages/{st['id']}")
        check(bool(doc["group_id"]) and api("GET", f"/groups/{doc['group_id']}")["group"]["name"].startswith("Stage"), "the passes sit on the stage's album page")
        # the shots
        rows: list[dict] = []
        results: dict[str, list[Path]] = {}
        for m in methods:
            for rnd in range(a.rounds):
                cdp.eval(f"window.__loom2Stage.setShot({json.dumps({'method': m, 'refs': [{'asset_id': heroine, 'note': 'the woman in the red coat'}], 'prompt_text': PROMPT, 'count': 1, 'use_as_is': True})})")
                time.sleep(0.5)
                jobs = cdp.eval("window.__loom2Stage.generateShot()", timeout=60)
                if not jobs:
                    check(False, f"{m} round {rnd}: the shot was not queued ({cdp.page_errors()})"); continue
                jid = jobs[0]["id"]
                t0 = time.time()
                j = wait_job(jid)
                wall = time.time() - t0
                ok = j["status"] == "done" and bool(j.get("result", {}).get("asset_ids"))
                row = {"method": m, "round": rnd, "cold": rnd == 0, "job": jid, "status": j["status"], "error": j.get("error"), "wall_s": round(wall, 1), "job_wall_s": j.get("wall_s"),
                       "model_id": (j.get("recipe") or {}).get("model_id") or (j.get("params") or {}).get("model_id"), "asset_ids": j.get("result", {}).get("asset_ids")}
                check(ok, f"{m} round {rnd} ({'cold' if rnd == 0 else 'warm'}): job {j['status']} in {wall:.1f} s" + (f" — {j.get('error')}" if j.get("error") else ""))
                if ok:
                    aid = row["asset_ids"][0]
                    asset = api("GET", f"/assets/{aid}")
                    want_parent = entry["assets"]["pose" if m == "refcontrol" else "clay"]
                    check(asset["lineage_kind"] == "stage-shot" and asset["parents"][:1] == [want_parent] and heroine in asset["parents"] and asset["suite"] == "stage",
                          f"{m} round {rnd}: lineage stage-shot ← the {'pose' if m == 'refcontrol' else 'clay'} pass + the reference; suite stage")
                    check((asset.get("origin") or {}).get("suite") == "stage" and (asset.get("origin") or {}).get("ref") == st["id"], f"{m} round {rnd}: origin stage / shot / {st['id']}")
                    row["model_id"] = asset.get("model_id")
                    p = OUT / f"{m}_{rnd}.png"
                    p.write_bytes(api("GET", f"/assets/{aid}/file", raw=True))
                    results.setdefault(m, []).append(p)
                    if rnd > 0 and m in BARS:
                        check(wall <= BARS[m]["warm_s"], f"{m} warm {wall:.1f} s ≤ {BARS[m]['warm_s']} s")
                rows.append(row)
        # scoring: SDPose → PCK against the pose pass's keypoints (evaluation only; the engine has the spike's nodes)
        eng = Engine(ENGINE)
        gt = entry["keypoints"]
        for m, paths in results.items():
            for p in paths:
                try:
                    name = eng.upload(p)
                    h, _, _ = eng.run(sdpose_graph(name))
                    people = json.loads(h["outputs"]["6"]["text"][0])[0]["people"]
                    hit, tot = pck(gt, people)
                    score = hit / tot if tot else 0.0
                    for r in rows:
                        if r["method"] == m and r.get("asset_ids") and p.name == f"{m}_{r['round']}.png":
                            r.update(pck_hit=hit, pck_total=tot, pck=round(score, 3))
                    print(f"     {p.name}: PCK@0.1 {score:.3f} ({hit}/{tot})")
                    if m in BARS and "pck" in BARS[m]:
                        check(score >= BARS[m]["pck"], f"{m} {p.name}: PCK@0.1 {score:.3f} ≥ {BARS[m]['pck']}")
                except Exception as e:  # noqa: BLE001
                    check(False, f"scoring {p.name}: {e}")
        with RESULTS.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({**r, "at": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
        # the sheet: clay · pose · one result per method (the warm round when there is one)
        cells = [("clay pass", passes_dir / "clay.png"), ("pose pass", passes_dir / "pose.png")] + [(m, paths[-1]) for m, paths in results.items()]
        tw, th = 480, 270
        sheet = Image.new("RGB", (8 + (tw + 8) * len(cells), 30 + th + 8), (24, 24, 24))
        dr = ImageDraw.Draw(sheet)
        for j, (head, p) in enumerate(cells):
            dr.text((8 + j * (tw + 8), 8), head, fill=(230, 230, 230))
            if p.is_file():
                im = Image.open(p).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (8 + j * (tw + 8), 30))
        sheet.save(OUT / "sheet.jpg", quality=88)
        print(f"sheet: {OUT / 'sheet.jpg'} · results: {RESULTS}")
        # ---- ST4 (D76, 16 §8): the clip — a dolly in keyed on the camera over 49 frames (8·6 + 1 at 24 fps), the depth sequence rendered by the
        # viewport, LTX-2.3 + the IC-LoRA from the clay result; scored like E11 (SDPose on every 8th frame vs the guide's own keypoints)
        start_asset = next((r["asset_ids"][0] for r in reversed(rows) if r["method"] == "clay" and r.get("asset_ids")), None)
        if a.clip and start_asset:
            cam_id = st["cameras"][0]["id"]
            cdp.eval("window.__loom2Stage.setRange(0, 48)")
            cdp.eval("window.__loom2Stage.setFrame(0)"); cdp.eval("window.__loom2Stage.keyCamera()")
            cdp.eval("window.__loom2Stage.setFrame(48)")
            cdp.eval(f"window.__loom2Stage.updateCamera({json.dumps(cam_id)}, {{pos: [0.3, 1.4, 2.4], target: [0.0, 1.0, 0.0]}})")   # a keyed camera takes the move as a key
            cdp.eval("window.__loom2Stage.setFrame(0)")
            time.sleep(1.0)                                                                                       # the debounced save
            keys = (cdp.eval("window.__loom2Stage.state()") or {}).get("current", {}).get("keyframes", {}).get("camera", {}).get(cam_id, [])
            check([k["frame"] for k in keys] == [0, 48], f"the camera keyed at frames 0 and 48 ({[k['frame'] for k in keys]})")
            t0 = time.time()
            ok = cdp.eval("window.__loom2Stage.renderGuide()", timeout=600)
            check(bool(ok), f"the depth sequence rendered and uploaded in {time.time() - t0:.1f} s")
            guide = (cdp.eval("window.__loom2Stage.state()") or {}).get("guide")
            check(bool(guide) and guide["frames"] == 49, "49 frames of depth (8n + 1) as one video asset")
            if guide:
                gasset = api("GET", f"/assets/{guide['asset_id']}")
                check(gasset["kind"] == "video" and gasset["lineage_kind"] == "stage-pass" and gasset["frames"] == 49 and len(gasset["params"]["keypoints"]) == 49,
                      "the guide asset: video, stage-pass, 49 frames with keypoints")
                cdp.eval(f"window.__loom2Stage.setShotStart({json.dumps(start_asset)})")
                jobs = cdp.eval("window.__loom2Stage.animateShot()", timeout=60)
                if not jobs:
                    check(False, f"the clip was not queued ({cdp.page_errors()})")
                else:
                    t0 = time.time()
                    j = wait_job(jobs[0]["id"])
                    wall = time.time() - t0
                    ok = j["status"] == "done" and bool(j.get("result", {}).get("asset_ids"))
                    check(ok, f"clip job {j['status']} in {wall:.1f} s" + (f" — {j.get('error')}" if j.get("error") else ""))
                    row = {"method": "clip_depth", "round": 0, "cold": True, "job": jobs[0]["id"], "status": j["status"], "error": j.get("error"), "wall_s": round(wall, 1),
                           "frames": 49, "asset_ids": j.get("result", {}).get("asset_ids"), "clip_id": j.get("result", {}).get("clip_id")}
                    if ok:
                        check(wall <= BARS["clip"]["wall_s"], f"clip {wall:.1f} s ≤ {BARS['clip']['wall_s']} s (E11: 147 s for 121 frames)")
                        casset = api("GET", f"/assets/{row['asset_ids'][0]}")
                        check(casset["kind"] == "video" and casset["lineage_kind"] == "stage-shot" and casset["parents"] == [start_asset, guide["asset_id"]] and casset["suite"] == "stage",
                              "the clip: video, lineage stage-shot ← the start shot + the guide, suite stage")
                        check((casset.get("origin") or {}).get("surface") == "clip" and casset["frames"] == 49, "origin stage / clip, 49 frames")
                        kp_all = gasset["params"]["keypoints"]
                        hit = tot = 0
                        frames_dir = OUT / "clip"
                        frames_dir.mkdir(exist_ok=True)
                        for i in range(0, 49, 8):
                            p = frames_dir / f"{i:04d}.png"
                            p.write_bytes(api("GET", f"/clips/{row['clip_id']}/frames/{i}.png", raw=True))
                            try:
                                h, _, _ = eng.run(sdpose_graph(eng.upload(p)))
                                people = json.loads(h["outputs"]["6"]["text"][0])[0]["people"]
                                h_, t_ = pck(kp_all[i], people)
                                hit += h_; tot += t_
                            except Exception as e:  # noqa: BLE001
                                check(False, f"scoring clip frame {i}: {e}")
                        score = hit / tot if tot else 0.0
                        row.update(pck_hit=hit, pck_total=tot, pck=round(score, 3))
                        print(f"     clip: PCK@0.1 {score:.3f} ({hit}/{tot}) over frames 0, 8, … 48")
                        check(score >= BARS["clip"]["pck"], f"clip PCK@0.1 {score:.3f} ≥ {BARS['clip']['pck']} (E11's bar: the pose followed)")
                        cells = [(f"frame {i}", frames_dir / f"{i:04d}.png") for i in (0, 16, 32, 48)]
                        tw, th = 480, 270
                        csheet = Image.new("RGB", (8 + (tw + 8) * len(cells), 30 + th + 8), (24, 24, 24))
                        dr = ImageDraw.Draw(csheet)
                        for jx, (head, p) in enumerate(cells):
                            dr.text((8 + jx * (tw + 8), 8), head, fill=(230, 230, 230))
                            if p.is_file():
                                im = Image.open(p).convert("RGB"); im.thumbnail((tw, th)); csheet.paste(im, (8 + jx * (tw + 8), 30))
                        csheet.save(OUT / "clip_sheet.jpg", quality=88)
                        print(f"clip sheet: {OUT / 'clip_sheet.jpg'}")
                    with RESULTS.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({**row, "at": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
        errs = cdp.page_errors()
        check(not errs, f"no page errors ({errs[:3]})")
        try:
            cdp.call("Browser.close")
        except Exception:
            pass
    finally:
        if edge and edge.poll() is None:
            edge.kill()
        try:
            api("POST", "/shutdown")
            time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
        orch_log.close()
    print(f"\nst_acceptance: {'all checks passed' if not failures else f'{len(failures)} FAILED'}")
    for f_ in failures:
        print("  -", f_)
    return 1 if failures else 0


RESULTS = OUT / "results.jsonl"

if __name__ == "__main__":
    sys.exit(main())
