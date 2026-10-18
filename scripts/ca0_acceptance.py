"""CA0 (proto01_animate 02 §5) acceptance on the rig, through the app's API: three characters × two versions (costumes) get an animation
reference each — full body, a neutral A-pose, 16:9, plain ground — made by the clay-reference model from the version's sheet and references.

`ref`: the references are made (one each, `count` 1), checked for size (16:9 at the Draft height) and lineage, saved under
engine/spikes/out/ca0/refs/ with a contact sheet for the author's look (full body, A-pose, nothing cropped, the costume's colours). The
figure is measured with SDPose on each reference: every one of the 18 COCO points found inside the frame with a margin means the whole
body is there (no crop), and the wrists below the shoulders and away from the hips is the A-pose.
`test` (step 3): the app draws each version's turn on the spot in a visible Edge (Cast's own code, the version's body, the Stage's pose
renderer), every turn queued staged and the queue released only when all are drawn (the page's WebGL never beside a GPU job, D97); the
pose-driven model performs each with the reference; scored with SDPose on every 8th frame against the turn's own keypoints (CA0's bar:
PCK@0.1 ≥ 0.8) and for a ghost (a second person in any scored frame); a contact sheet of the turn's quarters. Needs `--parts ref,test`
(the references come first) and the frontend dev server on 1420 (`npx vite --host 127.0.0.1 --port 1420 --strictPort` in frontend/).

Needs port 8188 free (the orchestrator launches the engine; scripts/engine-stop.ps1 first). One GPU job at a time (D97).

    orchestrator/.venv/Scripts/python.exe scripts/ca0_acceptance.py --parts ref,test
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))

PORT, TOKEN, DEV, DBG = 8779, "ca0", 1420, 9335
BARS = {"pck": 0.8}
OUT = ROOT / "engine" / "spikes" / "out" / "ca0"
HERO = ROOT / "bench" / "angles" / "07.jpg"
OGRE = {"height_m": 2.4, "build": "heavy", "head": 1.2, "torso": 1.1, "shoulders": 1.4, "arms": 1.2, "legs": 0.9,
        "attachments": [{"kind": "horns", "joint": None, "size": 1.2, "note": "curled"}]}
CAST = [
    {"name": "Mara", "hero": True, "appearance": "Mara, a young woman with long red hair in two braids, freckles, green eyes",
     "versions": [{"label": "cloak", "outfit": "a dark green hooded wool cloak over a brown tunic, leather boots", "colours": [{"hex": "#2E4A2F", "object": "hooded cloak"}]},
                  {"label": "market", "outfit": "a cream linen blouse, a blue skirt, a brown leather satchel", "colours": [{"hex": "#2F5D8A", "object": "skirt"}]}]},
    {"name": "Bram", "hero": False, "appearance": "Bram, an old sea captain, weathered face, a short white beard, broad shoulders",
     "versions": [{"label": "watch", "outfit": "a navy wool pea coat, a navy captain's cap, dark trousers, black boots", "colours": [{"hex": "#1F2A44", "object": "pea coat"}]},
                  {"label": "storm", "outfit": "a yellow oilskin coat and sou'wester hat, rubber boots", "colours": [{"hex": "#F2A93B", "object": "oilskin coat"}]}]},
    {"name": "Grak", "hero": False, "appearance": "Grak, a hulking grey-green ogre with small curled horns, a heavy jaw and tusks, kind eyes", "body": OGRE,
     "versions": [{"label": "smith", "outfit": "a scorched leather apron over bare arms, rough canvas trousers", "colours": [{"hex": "#6B4226", "object": "leather apron"}]},
                  {"label": "feast", "outfit": "a dark red tabard with a rope belt, fur boots", "colours": [{"hex": "#8E1B1B", "object": "tabard"}]}]},
]


def api(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def wait_job(job_id: str, timeout_s: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == job_id), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1.0)
    raise TimeoutError(job_id)


def cast(failures: list[str]) -> list[dict]:
    """The three characters with two versions each (v1 and a copy relabelled), their sheets and Grak's body."""
    out = []
    hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
    for c in CAST:
        v1 = c["versions"][0]
        p = api("POST", "/story/profiles", {"name": c["name"], "cls": "character", **({"hero_asset_id": hero} if c["hero"] else {}),
                                            "appearance": c["appearance"], "outfit": v1["outfit"], "colours": v1["colours"], "label": v1["label"]})
        if c.get("body"):
            p = api("PATCH", f"/story/profiles/{p['id']}", {"revision": p["revision"], "versions": [{"id": "v1", "body": c["body"]}]})
        p = api("POST", f"/story/profiles/{p['id']}/versions")
        v2 = c["versions"][1]
        p = api("PATCH", f"/story/profiles/{p['id']}", {"revision": p["revision"], "versions": [{"id": "v2", "label": v2["label"], "outfit": v2["outfit"], "colours": v2["colours"]}]})
        out.append(p)
    return out


def part_ref(profiles: list[dict], failures: list[str]) -> list[dict]:
    from PIL import Image, ImageDraw
    refs_dir = OUT / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in profiles:
        for v in ("v1", "v2"):
            t0 = time.time()
            r = api("POST", f"/story/profiles/{p['id']}/versions/{v}/anim-ref", {"side": "front", "count": 1})
            j = wait_job(r["job_ids"][0])
            wall = round(time.time() - t0, 1)
            if j["status"] != "done":
                failures.append(f"{p['name']} {v}: the job {j['status']} ({j.get('error')})")
                continue
            prof = api("GET", f"/story/profiles/{p['id']}")
            ver = next(x for x in prof["versions"] if x["id"] == v)
            aid = ver["anim_ref_asset_id"]
            a = api("GET", f"/assets/{aid}") if aid else None
            ok = bool(a) and a["w"] * 9 == a["h"] * 16
            if not ok:
                failures.append(f"{p['name']} {v}: the reference is not set or not 16:9 ({a and (a["w"], a["h"])})")
            dst = refs_dir / f"{p['name'].lower()}_{v}.png"
            if a:
                with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/assets/{aid}/file", headers={"X-Loom-Token": TOKEN})) as f:
                    dst.write_bytes(f.read())
            rows.append({"name": p["name"], "version": v, "label": ver["label"], "asset": aid, "size": a and [a["w"], a["h"]], "wall_s": wall,
                         "job_wall_s": j.get("wall_s"), "model": r["model_id"], "parents": a and a.get("parents"), "file": str(dst)})
            log(f"{p['name']} {v} ({ver['label']}): {a and (a["w"], a["h"])} in {wall} s")
    score_refs(rows, failures)
    tw, th = 384, 216
    sheet = Image.new("RGB", (8 + (tw + 8) * 2, 8 + (th + 22) * len(profiles)), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, row in enumerate(rows):
        x, y = 8 + (i % 2) * (tw + 8), 8 + (i // 2) * (th + 22)
        dr.text((x, y), f"{row['name']} {row['version']} · {row['label']} · {row.get('pose', '')}", fill=(230, 230, 230))
        if Path(row["file"]).is_file():
            im = Image.open(row["file"]).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (x, y + 16))
    sheet.save(OUT / "refs_sheet.jpg", quality=88)
    log(f"contact sheet: {OUT / 'refs_sheet.jpg'}")
    return rows


def keypoints_of(eng, path: Path):
    """SDPose through the running engine (the spike's nodes, evaluation only — as st_acceptance scores): the most confident person's
    COCO-18 points [(x, y, conf)], or None."""
    from e10_stage import sdpose_graph
    h, _, _ = eng.run(sdpose_graph(eng.upload(path)))
    people = json.loads(h["outputs"]["6"]["text"][0])[0]["people"]
    if not people:
        return None
    import numpy as np
    best = max(people, key=lambda q: float(np.array(q["pose_keypoints_2d"], dtype=float).reshape(-1, 3)[:, 2].sum()))
    return [tuple(r) for r in np.array(best["pose_keypoints_2d"], dtype=float).reshape(-1, 3)[:18]]


def score_refs(rows: list[dict], failures: list[str]) -> None:
    """SDPose on each reference: the whole body in the frame (≥ 16 of the 18 COCO points found, all 3 % inside the edges) and an A-pose
    (both wrists below their shoulders and a little out from the hips — reported, the bar is the whole body)."""
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from e12_angles import Engine
    from PIL import Image
    eng = Engine("127.0.0.1:8188")
    for row in rows:
        if not Path(row["file"]).is_file():
            continue
        w, h = Image.open(row["file"]).size
        try:
            kp = keypoints_of(eng, Path(row["file"]))
        except Exception as e:  # noqa: BLE001
            failures.append(f"scoring {row['name']} {row['version']}: {e}")
            continue
        if not kp:
            row["pose"] = "no figure found"
            failures.append(f"{row['name']} {row['version']}: no figure found in the reference")
            continue
        found = [(x, y) for x, y, c in kp if c > 0.3]
        inside = all(0.03 * w <= x <= 0.97 * w and 0.03 * h <= y <= 0.97 * h for x, y in found)
        whole = len(found) >= 16 and inside

        def pt(i):
            x, y, c = kp[i]
            return (x, y) if c > 0.3 else None
        r_sh, l_sh, r_wr, l_wr, r_hip, l_hip = pt(2), pt(5), pt(4), pt(7), pt(8), pt(11)
        apose = all((r_sh, l_sh, r_wr, l_wr, r_hip, l_hip)) and r_wr[1] > r_sh[1] and l_wr[1] > l_sh[1]             and abs(r_wr[0] - r_hip[0]) > 0.02 * w and abs(l_wr[0] - l_hip[0]) > 0.02 * w
        row["pose"] = f"{len(found)}/18 points{'' if inside else ', at the edge'}{', A-pose' if apose else ', not an A-pose'}"
        row["whole_body"], row["a_pose"] = bool(whole), bool(apose)
        log(f"{row['name']} {row['version']}: {row['pose']}")
        if not whole:
            failures.append(f"{row['name']} {row['version']}: the whole body is not in the frame ({row['pose']})")


def part_test(profiles: list[dict], failures: list[str], tmp: Path) -> list[dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "engine" / "spikes"))
    from edit_headed_check import CDP, EDGE
    from e10_stage import pck, sdpose_graph
    from e12_angles import Engine
    from PIL import Image, ImageDraw
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        failures.append("the frontend dev server is not on 1420 (npx vite --host 127.0.0.1 --port 1420 --strictPort)")
        return []
    url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=story"
    edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                             "--window-size=1600,1000", "--window-position=40,40", "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                             "--disable-backgrounding-occluded-windows", "--disable-features=CalculateNativeWinOcclusion", "--new-window", url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows: list[dict] = []
    try:
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
            failures.append("no page target in Edge")
            return []
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable")
        if not cdp.wait_for("document.readyState === 'complete' && !!window.__loom2Story && !!window.__loom2Story.animTest", timeout=60, settle=2.0):
            failures.append(f"the Story hook did not load ({cdp.page_errors()[:3]})")
            return []
        cdp.eval("window.__loom2Story.loadProfiles()", timeout=60)
        cdp.wait_for("true", timeout=5, settle=3.0)                                  # the capabilities and profiles in
        queued = []
        for p in profiles:
            for v in ("v1", "v2"):
                t0 = time.time()
                r = cdp.eval(f"window.__loom2Story.animTest({json.dumps(p['id'])}, {json.dumps(v)}, true)", timeout=300)
                if not r or not r.get("job_id"):
                    failures.append(f"{p['name']} {v}: the turn was not queued ({cdp.page_errors()[:3]})")
                    continue
                log(f"{p['name']} {v}: the turn drawn and queued staged in {time.time() - t0:.1f} s")
                queued.append({"name": p["name"], "pid": p["id"], "version": v, **r})
        errs = cdp.page_errors()
        if errs:
            failures.append(f"page errors while drawing: {errs[:3]}")
        try:
            cdp.call("Browser.close")
        except Exception:
            pass
    finally:
        if edge.poll() is None:
            edge.kill()
    api("POST", "/queue/release")                                                  # every turn drawn: the GPU takes the jobs, one at a time
    eng = Engine("127.0.0.1:8188")
    test_dir = OUT / "test"
    test_dir.mkdir(parents=True, exist_ok=True)
    for q in queued:
        j = wait_job(q["job_id"], timeout_s=1800)
        row = {"name": q["name"], "version": q["version"], "job": q["job_id"], "status": j["status"], "wall_s": j.get("wall_s"), "error": j.get("error")}
        rows.append(row)
        if j["status"] != "done":
            failures.append(f"{q['name']} {q['version']}: the test {j['status']} ({j.get('error')})")
            continue
        clip = j["result"]["clip_id"]
        prof = api("GET", f"/story/profiles/{q['pid']}")
        rec = next(x for x in prof["versions"] if x["id"] == q["version"]).get("anim_test_clip_id")
        if rec != clip:
            failures.append(f"{q['name']} {q['version']}: the clip is not recorded on the version")
        guide = api("GET", f"/assets/{q['guide_asset_id']}")
        kps = guide["params"]["keypoints"]
        n = guide["frames"]
        hit = tot = ghosts = 0
        for i in range(0, n, 8):
            fp = test_dir / f"{q['name'].lower()}_{q['version']}_{i:03d}.png"
            with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/clips/{clip}/frames/{i}.png", headers={"X-Loom-Token": TOKEN})) as f:
                fp.write_bytes(f.read())
            h_, _, _ = eng.run(sdpose_graph(eng.upload(fp)))
            people = json.loads(h_["outputs"]["6"]["text"][0])[0]["people"]
            a, b = pck(kps[i], people)
            hit += a; tot += b
            seen = 0
            for person in people:
                pts = person["pose_keypoints_2d"]
                if sum(1 for k in range(2, len(pts), 3) if pts[k] > 0.3) >= 8:
                    seen += 1
            ghosts += 1 if seen > 1 else 0
        score = hit / tot if tot else 0.0
        row.update(clip=clip, frames=n, pck=round(score, 3), ghost_frames=ghosts)
        log(f"{q['name']} {q['version']}: PCK@0.1 {score:.3f} ({hit}/{tot}), ghost frames {ghosts}, {j.get('wall_s')} s")
        if score < BARS["pck"]:
            failures.append(f"{q['name']} {q['version']}: PCK@0.1 {score:.3f} < {BARS['pck']}")
        if ghosts:
            failures.append(f"{q['name']} {q['version']}: a second figure in {ghosts} scored frame(s)")
        # the turn's quarters for the sheet
        for i in (0, n // 4, n // 2, 3 * n // 4, n - 1):
            fp = test_dir / f"{q['name'].lower()}_{q['version']}_q{i:03d}.png"
            with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/clips/{clip}/frames/{i}.png", headers={"X-Loom-Token": TOKEN})) as f:
                fp.write_bytes(f.read())
            row.setdefault("quarters", []).append(str(fp))
    tw, th = 208, 120
    sheet = Image.new("RGB", (8 + (tw + 4) * 5, 8 + (th + 18) * max(1, len(rows))), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for r_i, row in enumerate(rows):
        y = 8 + r_i * (th + 18)
        dr.text((8, y), f"{row['name']} {row['version']} · PCK {row.get('pck')} · ghosts {row.get('ghost_frames')}", fill=(230, 230, 230))
        for c_i, fp in enumerate(row.get("quarters", [])):
            im = Image.open(fp).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (8 + c_i * (tw + 4), y + 14))
    sheet.save(OUT / "test_sheet.jpg", quality=88)
    log(f"contact sheet: {OUT / 'test_sheet.jpg'}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="ref")
    a = ap.parse_args()
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)")
        return 2
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-ca0-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                             "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    failures: list[str] = []
    result: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "parts": a.parts}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CA0", "size_cap_gb": 20})
        profiles = cast(failures)
        if "ref" in a.parts:
            result["ref"] = part_ref(profiles, failures)
        if "test" in a.parts:
            result["test"] = part_test(profiles, failures, tmp)
    finally:
        try:
            api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
        orch_log.close()
    result["failures"] = failures
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result, indent=1)[:4000])
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
