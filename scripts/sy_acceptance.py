"""17 §12 (D85) acceptance of the Story workspace on the rig, through the app. SY1 (item 2): a hero → a character profile → Expand (one job per
coverage cell on D78's clay model, Klein 9B) → the candidates on the version's page with their cells → ≥ 25 added to the reference set
with every shot-size row covered → Lock (the album refuses) → `@Mara` resolves to the locked version with the hero first, and a Generate
job with the mention records the stamp. SY2 (item 3): a stage with a camera → "New shot from this camera" → the camera's clay frame
arrives on the shot's v1 as its frame (the finisher's link) → a draft clip is no longer refused (D125: any size), a Full-size clip
(1920×1080 → the model's grid) used as the clip is accepted → final → the stage moved → stale. SY5 (17 §12, the alpha): `world` (item 1:
two styles, a Generate job with style B stamps `style_id` and appends the fragment), `durability` inside SY1 (item 6: the orchestrator
killed mid-Expand and relaunched → the queue resumes paused with the rest queued, the records reopen at their revisions, release →
the rest run), `sy3` (item 4: five nodes with a Choice and a Condition through the API, the SY2 shot bound, a second bind refused,
Validate, Play through both branches with the job count unchanged), `sy4` (item 5: a sequence with the final shot stamped and a plain
clip, the checklist, EDL + FCPXML with a marker + markers.txt + the SRT with the node's line, the draft render as a clip).
`--part world,sy1,sy2,sy3,sy4` picks (`durability` is a part of its own).

Needs the frontend dev server on 1420 (`npx vite --host 127.0.0.1 --port 1420 --strictPort` in frontend/), a visible Edge, and port 8188
free: the orchestrator it starts launches the engine itself (a standalone engine writes its outputs elsewhere — stop it first,
`scripts/engine-stop.ps1`). It starts its own orchestrator (port 8774, a temp state, models on F:), drives the Story suite through
`window.__loom2Story` (the hook the smoke test uses) and checks every outcome through the API. Results: `engine/spikes/out/sy/results.jsonl`,
a contact sheet of the candidates (`candidates.jpg`) and of the kept set (`kept.jpg`), the orchestrator log.

Bars: every Expand job done with an asset on the candidates page carrying its cell; warm jobs ≤ 45 s each (the clay bar of st_acceptance:
the same model with one reference); the kept set ≥ 25 with all four shot-size rows covered; Lock → 423 on the page; the mention stamped.

    orchestrator/.venv/Scripts/python.exe scripts/sy_acceptance.py [--preset full] [--keep 30]
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
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):                                                 # the log and a cp1252 console take the ≤ and · of the check lines
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "scripts"))
from edit_headed_check import CDP, EDGE  # noqa: E402

PORT, TOKEN, DBG, DEV, ENGINE = 8774, "story", 9335, 1420, "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "sy"
HERO = ROOT / "bench" / "angles" / "07.jpg"
STUB = "Mara, a wiry courier in a long grey coat with a red scarf"
BARS = {"warm_s": 45.0, "kept_min": 25}


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def status_of(method: str, path: str, body=None) -> int:
    try:
        api(method, path, body)
        return 200
    except urllib.error.HTTPError as e:
        return e.code


def wait_jobs(ids: list[str], timeout_s: float = 3600, progress_s: float = 900) -> dict[str, dict]:
    """Every job of `ids` in a terminal state; returns them by id (progress printed as they finish). Gives up when nothing finishes for
    `progress_s` (a paused queue, a dead engine) — the caller sees fewer jobs than it asked for."""
    t0 = time.time()
    last = time.time()
    done: dict[str, dict] = {}
    while time.time() - t0 < timeout_s and len(done) < len(ids):
        for j in api("GET", "/jobs")["items"]:
            if j["id"] in ids and j["id"] not in done and j["status"] in ("done", "failed", "cancelled"):
                done[j["id"]] = j
                last = time.time()
                print(f"  job {len(done)}/{len(ids)} {j['status']} wall {j.get('wall_s')}", flush=True)
        if time.time() - last > progress_s:
            print(f"  no job finished for {progress_s:.0f} s — giving up on the rest ({len(done)}/{len(ids)})", flush=True)
            break
        time.sleep(1.0)
    return done


def sheet(ids: list[str], path: Path, cols: int = 8, cell: int = 192, labels: dict[str, str] | None = None) -> None:
    rows = max(1, (len(ids) + cols - 1) // cols)
    im = Image.new("RGB", (cols * cell, rows * (cell + 14)), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for i, aid in enumerate(ids):
        try:
            t = Image.open(io.BytesIO(api("GET", f"/thumbs/{aid}/256", raw=True))).convert("RGB")
        except Exception:
            continue
        t.thumbnail((cell, cell))
        x, y = (i % cols) * cell, (i // cols) * (cell + 14)
        im.paste(t, (x + (cell - t.width) // 2, y))
        d.text((x + 2, y + cell), (labels or {}).get(aid, aid)[:30], fill=(200, 200, 200))
    im.save(path, quality=85)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="full")
    ap.add_argument("--keep", type=int, default=30, help="how many candidates to add to the reference set (by cell order, every shot-size row first)")
    ap.add_argument("--part", default="world,sy1,durability,sy2,sy3,sy4", help="which slices to run")
    a = ap.parse_args()
    if not EDGE:
        print("Edge not found"); return 2
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print("frontend dev server not reachable on 1420 (npx vite --host 127.0.0.1 --port 1420 --strictPort)"); return 2
    try:
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1) — the orchestrator must launch its own"); return 2
    except Exception:
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-sy-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                              "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")                       # never a pipe: an unread pipe fills and stalls the server mid-job
    proc = {"orch": subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                                      stdout=orch_log, stderr=subprocess.STDOUT, text=True), "env": env, "log": orch_log, "state": tmp / "state", "project": tmp / "proj"}
    edge = None
    failures: list[str] = []
    rows: list[dict] = []

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "SY1", "size_cap_gb": 40})
        hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
        parts = [x for x in a.part.split(",") if x]
        caps = api("GET", "/capabilities")["story"]
        print("story caps:", {k: caps[k] for k in ("model_id", "health", "seconds")}, {k: v["cells"] for k, v in caps["presets"].items()})
        check(caps["model_id"] and caps["health"] != "missing", f"Expand's model {caps['model_id']} offered with its weights present")
        # the browser: the Story suite on the Cast tab
        url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=story&tab=cast"
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
        if not cdp.wait_for("!!window.__loom2Story", timeout=60, settle=0.5):
            check(False, f"the Story suite loaded (dev hook present) — page errors: {cdp.page_errors()[:3]}")
            return 1
        check(True, "the Story suite loaded (dev hook present)")
        ctx: dict = {"shot": None, "clip": None, "node": None}
        if "world" in parts:
            world(cdp, hero, caps, check, rows, failures)
        if "sy1" in parts:
            sy1(cdp, hero, caps, a, check, rows, failures, proc if "durability" in parts else None)
        if "sy2" in parts:
            sy2(cdp, hero, check, rows, failures, ctx)
        if "sy3" in parts:
            sy3(cdp, check, rows, failures, ctx)
        if "sy4" in parts:
            sy4(cdp, check, rows, failures, ctx)
    finally:
        code = finish(edge, proc, failures)                                                # every path, the early returns included
    return code


def restart_orchestrator(proc: dict, check) -> None:
    """17 §12 item 6: kill the orchestrator mid-work and relaunch it on the same state with the project reopened (the engine it launched
    stays up and is adopted)."""
    proc["orch"].kill()
    try:
        proc["orch"].wait(timeout=20)
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < 10:
        try:
            api("GET", "/health"); time.sleep(0.3)
        except Exception:
            break
    proc["orch"] = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(proc["state"]), "--project", str(proc["project"])],
                                    cwd=str(ROOT / "orchestrator"), env=proc["env"], stdout=proc["log"], stderr=subprocess.STDOUT, text=True)
    t0 = time.time()
    while time.time() - t0 < 90:
        try:
            if api("GET", "/project")["open"]:
                break
        except Exception:
            pass
        time.sleep(0.5)
    check(api("GET", "/project")["open"], "the orchestrator relaunched with the project open")


def world(cdp, hero, caps, check, rows, failures) -> None:
    """17 §12 item 1: two styles; a Generate job with style B stamps style_id and appends its fragment."""
    w = api("GET", "/story/world")
    styles = [{"id": "sty_ink", "name": "Ink wash", "fragment": "ink and wash storyboard, loose brush", "group_id": None},
              {"id": "sty_film", "name": "Film still", "fragment": "cinematic film still, 35 mm, shallow depth of field", "group_id": None}]
    w2 = api("PUT", "/story/world", {**w, "logline": "A courier must cross the city before dawn.", "styles": styles, "default_style": "sty_ink",
                                     "variables": [{"name": "met_mara", "type": "bool", "values": [], "default": False}]})
    check(w2["revision"] == w["revision"] + 1 and w2["default_style"] == "sty_ink", "the world holds two styles, the first the default")
    cdp.eval("window.__loom2Story.openTab('world')")
    check(cdp.wait_for("document.querySelectorAll('.world-editor .style-tile').length === 2", timeout=30, settle=0.5), "the World tab shows both styles")
    pv = api("POST", "/recipes/preview", {"recipe": {"kind": "t2i", "model_id": caps["model_id"], "prompt_mode": "text", "prompt_text": "a courier on a rooftop at dawn", "width": 960, "height": 544, "style_id": "sty_film"}})
    check(pv["style_text"] == styles[1]["fragment"] and pv["serialized_prompt"].endswith(styles[1]["fragment"]), "the preview appends style B's fragment")
    t0 = time.time()
    job = api("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": caps["model_id"], "prompt_mode": "text", "prompt_text": "a courier on a rooftop at dawn", "width": 960, "height": 544, "seeds": [5], "style_id": "sty_film"},
                                "stage": False, "origin": {"suite": "generate", "surface": "results"}})["jobs"][0]
    j = wait_jobs([job["id"]]).get(job["id"], {"status": "missing"})
    ok = j["status"] == "done" and bool(j.get("result", {}).get("asset_ids"))
    check(ok, f"a Generate job with style B done in {time.time() - t0:.0f} s")
    if ok:
        a = api("GET", f"/assets/{j['result']['asset_ids'][0]}")
        check(a["params"].get("style_id") == "sty_film" and a["params"].get("style_text") == styles[1]["fragment"] and a["prompt_text"].endswith(styles[1]["fragment"]), "the asset's manifest stamps style_id and the fragment that ran")
        (OUT / "style_result.jpg").write_bytes(api("GET", f"/assets/{a['id']}/file", raw=True))
    rows.append({"part": "world", "style_job_s": round(time.time() - t0, 1), "failures": list(failures)})


def sy1(cdp, hero, caps, a, check, rows, failures, proc: dict | None = None) -> None:
    if True:
        # 1. the profile from the hero
        p = cdp.eval(f"window.__loom2Story.createProfile('Mara', 'character', {json.dumps(hero)}, {json.dumps(STUB)})", timeout=30)
        check(bool(p) and p["versions"][0]["hero_asset_id"] == hero, "the profile Mara v1 made with the hero")
        pid, gid = p["id"], p["versions"][0]["group_id"]
        check(api("GET", f"/groups/{gid}")["group"]["cover_id"] == hero, "the hero is the reference page's cover")
        cdp.eval("window.__loom2Story.openTab('cast')")                                     # the world part may have left the suite on World
        cdp.eval(f"window.__loom2Story.selectProfile({json.dumps(pid)})")
        check(cdp.wait_for("!!document.querySelector('.cast-page h2') && document.querySelector('.cast-page h2').textContent.includes('Mara')", timeout=20, settle=1.0), "the Cast page shows Mara")
        # 2. Expand: one job per cell, timed
        t_exp = time.time()
        r = cdp.eval(f"window.__loom2Story.expand({json.dumps(a.preset)}, 1, 'draft')", timeout=120)
        check(bool(r) and r["cells"] == caps["presets"][a.preset]["cells"] and len(r["job_ids"]) == r["cells"], f"Expand {a.preset}: {r and r['cells']} jobs queued in one batch")
        if proc is not None:                                                             # 17 §12 item 6: killed mid-Expand, relaunched, resumed
            t_first = time.time()
            while time.time() - t_first < 600 and sum(1 for j in api("GET", "/jobs")["items"] if j["id"] in r["job_ids"] and j["status"] == "done") < 3:
                time.sleep(1.0)
            done_before = sum(1 for j in api("GET", "/jobs")["items"] if j["id"] in r["job_ids"] and j["status"] == "done")
            rev_before = api("GET", f"/story/profiles/{pid}")["revision"]
            restart_orchestrator(proc, check)
            q = api("GET", "/queue")
            left = [j for j in api("GET", "/jobs")["items"] if j["id"] in r["job_ids"] and j["status"] in ("queued", "running")]
            check(q["paused"] and len(left) >= r["cells"] - done_before - 1, f"after the relaunch the queue is paused with {len(left)} of the Expand's jobs still queued ({done_before} done before the kill)")
            check(api("GET", f"/story/profiles/{pid}")["revision"] == rev_before and api("GET", "/story/world")["revision"] >= 1, "the records reopened at their revisions")
            check(cdp.wait_for("!!window.__loom2Story", timeout=60, settle=1.0), "the page is back on the relaunched orchestrator")
            eng = api("GET", "/engine")
            print("engine after the relaunch:", {k: eng.get(k) for k in ("running", "responding", "pid", "port") if k in eng}, flush=True)
            q2 = api("POST", "/queue/unpause")                                             # the Resume the banner offers (a paused queue is not a staged one)
            check(not q2["paused"], "the queue resumed (unpause)")
        jobs = wait_jobs(r["job_ids"])
        exp_wall = time.time() - t_exp
        walls = [j.get("wall_s") or 0 for j in jobs.values()]
        order = {jid: i for i, jid in enumerate(r["job_ids"])}
        first = min(jobs.values(), key=lambda j: order[j["id"]])
        warm = sorted(j.get("wall_s") or 0 for j in jobs.values() if j["id"] != first["id"])
        check(len(jobs) == r["cells"] and all(j["status"] == "done" and j.get("result", {}).get("asset_ids") for j in jobs.values()), f"every job done with an asset ({len(jobs)}/{r['cells']}) in {exp_wall:.0f} s")
        check(bool(warm) and max(warm) <= BARS["warm_s"], f"warm jobs ≤ {BARS['warm_s']:.0f} s: first (cold) {first.get('wall_s')} s, warm min / median / max {warm[0] if warm else 0:.1f} / {warm[len(warm)//2] if warm else 0:.1f} / {warm[-1] if warm else 0:.1f} s")
        cand = api("GET", f"/groups/{r['group_id']}")
        cands = list(cand["assets"].values())
        check(len(cands) == r["cells"], f"{len(cands)} candidates on '{cand['group']['name']}'")
        check(all(x["suite"] == "story" and x["params"].get("coverage_cell", {}).get("shot") and x["parents"] == [hero] and x["origin"]["surface"] == "expand" for x in cands),
              "every candidate carries its cell, suite story, the hero as its parent and the expand origin")
        model_ids = {x["model_id"] for x in cands}
        check(model_ids == {caps["model_id"]}, f"all on {model_ids}")
        labels = {x["id"]: f"{x['params']['coverage_cell']['shot'][:6]} {x['params']['coverage_cell']['angle'][:9]} {x['params']['coverage_cell']['expression'][:4]}" for x in cands}
        sheet([x["id"] for x in sorted(cands, key=lambda x: x["created_at"])], OUT / "candidates.jpg", labels=labels)
        check(cdp.wait_for(f"document.querySelectorAll('.cand-card').length === {r['cells']}", timeout=30, settle=1.0), "the Cast page shows every candidate")
        # 3. the reference set: every shot-size row first, then by cell order, up to --keep (D122: added, nothing stamped)
        by_shot: dict[str, list[dict]] = {}
        for x in sorted(cands, key=lambda x: x["created_at"]):
            by_shot.setdefault(x["params"]["coverage_cell"]["shot"], []).append(x)
        keep: list[str] = []
        for shot in caps["coverage"]["shots"]:
            if by_shot.get(shot):
                keep.append(by_shot[shot][0]["id"])
        for x in sorted(cands, key=lambda x: x["created_at"]):
            if len(keep) >= a.keep:
                break
            if x["id"] not in keep:
                keep.append(x["id"])
        left = [x["id"] for x in cands if x["id"] not in keep][:3]
        ok = cdp.eval(f"window.__loom2Story.addRefs({json.dumps(keep)}).then(() => true)", timeout=120)
        ref = api("GET", f"/groups/{gid}")
        kept = [x for x in ref["assets"].values() if x["id"] != hero]
        rows_covered = {x["params"].get("coverage_cell", {}).get("shot") for x in kept}
        check(ok is True and len(kept) >= BARS["kept_min"], f"{len(kept)} kept in the reference set (bar ≥ {BARS['kept_min']})")
        check(set(caps["coverage"]["shots"]) <= rows_covered, f"every shot-size row covered: {sorted(rows_covered)}")
        check(all("state" not in x for x in kept), "nothing is stamped on the added ones (D122)")
        check(all(i in api("GET", f"/groups/{r['group_id']}")["assets"] for i in left), "the others stay on the candidates page")
        sheet([hero, *[x["id"] for x in kept]], OUT / "kept.jpg", labels=labels | {hero: "hero"})
        grid_ok = cdp.wait_for("document.querySelectorAll('.cov-grid td.one, .cov-grid td.full').length >= 4", timeout=30, settle=1.0)
        check(bool(grid_ok), "the coverage grid shows the kept cells")
        # 4. lock → the album refuses; the stub is read-only
        cdp.eval("window.__loom2Story.lock().then(() => true)", timeout=60)
        p2 = api("GET", f"/story/profiles/{pid}")
        check(p2["versions"][0]["state"] == "final", "v1 locked")
        check(status_of("POST", "/groups/move", {"items": [{"kind": "asset", "id": keep[0]}], "to": None}) == 423, "the album refuses a move off the locked page (423)")
        check(status_of("PATCH", f"/story/profiles/{pid}", {"revision": p2["revision"], "versions": [{"id": "v1", "stub": "changed"}]}) == 422, "the locked version's stub is read-only (422)")
        check(cdp.wait_for("!!document.querySelector('.story-strip .lock-badge')", timeout=20, settle=0.5), "the strip shows the lock")
        # 5. the mention: the preview resolves to v1 with the hero first and the stub on the note; a job records the stamp
        t2i = api("GET", "/capabilities")["defaults"]["t2i"]
        klein = caps["model_id"]
        pv = api("POST", "/recipes/preview", {"recipe": {"kind": "t2i", "model_id": klein, "prompt_mode": "text", "prompt_text": "@Mara waits at the city gate at dawn", "width": 960, "height": 544,
                                                          "mentions": [{"profile_id": pid, "name": "Mara"}]}})
        m = pv["mentions"][0]
        check(m["profile_id"] == pid and m["version"] == "v1" and m["group_id"] == gid and pv["ref_list"][0]["asset_id"] == hero, f"@Mara → v1's reference set, the hero first ({pv['refs']} references)")
        check(STUB.split(",")[1].strip()[:10] in pv["serialized_prompt"], f"the stub rides on the note: {pv['serialized_prompt'][:160]!r}")
        t0 = time.time()
        job = api("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": klein, "prompt_mode": "text", "prompt_text": "@Mara waits at the city gate at dawn", "width": 960, "height": 544, "seeds": [11],
                                               "mentions": [{"profile_id": pid, "name": "Mara"}]}, "stage": False, "origin": {"suite": "generate", "surface": "results"}})["jobs"][0]
        j = wait_jobs([job["id"]]).get(job["id"], {"status": "missing"})
        wall = time.time() - t0
        ok = j["status"] == "done" and bool(j.get("result", {}).get("asset_ids"))
        check(ok, f"a Generate job with @Mara done in {wall:.0f} s")
        if ok:
            asset = api("GET", f"/assets/{j['result']['asset_ids'][0]}")
            st = asset["params"]["recipe"]["mentions"][0]
            check(st["profile_id"] == pid and st["version"] == "v1" and st["asset_ids"][0] == hero and hero in asset["parents"], "the asset's manifest stamps profile, version and the images it took; the hero is a parent")
            (OUT / "mention_result.jpg").write_bytes(api("GET", f"/assets/{asset['id']}/file", raw=True))
        rows.append({"preset": a.preset, "cells": r["cells"], "expand_wall_s": round(exp_wall, 1), "first_job_s": first.get("wall_s"), "warm_min_s": warm[0] if warm else None,
                     "warm_median_s": warm[len(warm) // 2] if warm else None, "warm_max_s": warm[-1] if warm else None, "walls": walls, "kept": len(kept), "rows": sorted(rows_covered),
                     "model_id": caps["model_id"], "t2i_default": t2i, "mention_job_s": round(wall, 1), "failures": failures})
        (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(rows[-1]) + "\n")
        print(json.dumps({k: v for k, v in rows[-1].items() if k != "walls"}, indent=1))


def sy2(cdp, hero, check, rows, failures, ctx: dict | None = None) -> None:
    """17 §12 item 3: a stage camera → a shot; the clay frame lands on it; a draft clip is markable (D125: any size), a Full one is marked final; stale after a move."""
    fmt = api("GET", "/project")["format"]
    st = api("POST", "/stages", {"name": "SY2 gate"})
    cam = {**st["cameras"][0], "name": "Camera 1", "pos": [0.4, 1.5, 4.2], "target": [0.0, 1.0, 0.0], "focal_mm": 35}
    objs = [
        {"id": "set_room", "kind": "set", "name": "Set 1", "preset": "room", "asset_id": None, "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "parent": None, "locked": True, "visible": True, "colour_id": 1, "pose": None, "billboard": True},
        {"id": "fig_a", "kind": "mannequin", "name": "Figure 1", "preset": "adult", "asset_id": None, "transform": {"pos": [-0.3, 0, 0.3], "rot": [0, 20, 0], "scale": [1, 1, 1]}, "parent": None, "locked": False, "visible": True, "colour_id": 2, "pose": {"preset": "stand", "joints": {}}, "billboard": True},
    ]
    st = api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "active_camera": cam["id"]})
    cdp.eval("window.__loom2Story.loadShots().then(() => true)", timeout=30)
    shot = cdp.eval(f"window.__loom2Story.createShot('Gate', {json.dumps({'stage_id': st['id'], 'camera_id': cam['id']})})", timeout=30)
    check(bool(shot) and shot["versions"][0]["stage_id"] == st["id"] and shot["versions"][0]["stage_revision"] == st["revision"], "the shot Gate v1 points at the stage camera")
    # the Stage suite: open the stage, render the passes, generate the clay frame → the finisher records it on the shot
    cdp.eval("window.__loom2Session.getState().setSuite('stage')")
    check(cdp.wait_for("!!window.__loom2Stage", timeout=60, settle=0.5), "the Stage suite loaded")
    cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
    check(cdp.wait_for("!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === 2", timeout=30, settle=2.0), "the stage opened")
    ok = cdp.eval("window.__loom2Stage.renderPasses()", timeout=120)
    check(bool(ok), "the passes rendered")
    cdp.eval(f"window.__loom2Stage.setShot({json.dumps({'method': 'clay', 'refs': [{'asset_id': hero, 'note': 'the woman in the grey coat'}], 'prompt_text': 'a courier at a stone gate at dawn, cinematic film still', 'count': 1, 'use_as_is': True})})")
    time.sleep(0.5)
    jobs = cdp.eval("window.__loom2Stage.generateShot()", timeout=60)
    check(bool(jobs), "the clay shot queued")
    t0 = time.time()
    j = wait_jobs([jobs[0]["id"]])[jobs[0]["id"]]
    check(j["status"] == "done" and bool(j.get("result", {}).get("asset_ids")), f"the clay shot done in {time.time() - t0:.0f} s")
    frame = j["result"]["asset_ids"][0]
    s2 = api("GET", f"/story/shots/{shot['id']}")
    check(s2["versions"][0]["frame_asset_id"] == frame and [t["id"] for t in s2["versions"][0]["takes"]] == [frame], "the frame landed on the shot's v1 as its frame and first take (the finisher's link)")
    # a draft clip → used as the clip → nothing refuses it (D125: any size); a Full-size LTX clip → marked final
    i2v = api("GET", "/capabilities")["defaults"]["i2v"]
    rows_local: dict = {"shot": shot["id"], "frame": frame}
    for label, (w, h), frames in (("draft", (1024, 576), 25), ("full", (fmt["width"], fmt["height"]), 25)):
        t0 = time.time()
        jb = api("POST", "/jobs", {"recipe": {"kind": "i2v", "model_id": i2v, "start_asset": frame, "width": w, "height": h, "frames": frames, "fps": 24, "prompt_text": "the courier turns her head, slow dolly in"},
                                   "stage": False, "origin": {"suite": "animate", "surface": "clip"}})["jobs"][0]
        j = wait_jobs([jb["id"]])[jb["id"]]
        wall = time.time() - t0
        ok = j["status"] == "done" and bool(j.get("result", {}).get("clip_id"))
        check(ok, f"the {label} clip ({w}×{h} asked, {frames} f) done in {wall:.0f} s" + (f" — {j.get('error')}" if j.get("error") else ""))
        if not ok:
            continue
        clip = api("GET", f"/clips/{j['result']['clip_id']}")
        rows_local[label] = {"clip": clip["id"], "w": clip["w"], "h": clip["h"], "frames": clip["frames"], "wall_s": round(wall, 1)}
        if ctx is not None and label == "draft":
            ctx["draft_clip"] = clip["id"]
        cdp.eval(f"window.__loom2Story.openShots({json.dumps(shot['id'])})")                     # the Shots tab with the shot selected (the strip's badges)
        cdp.eval(f"window.__loom2Story.useTake('clip', {json.dumps(clip['id'])}).then(() => true)", timeout=30)
        s3 = api("GET", f"/story/shots/{shot['id']}")
        check(s3["versions"][0]["clip_id"] == clip["id"], f"the {label} clip is the version's clip")
        if label == "draft":                                                  # D125 (#6): not marked here — the Full clip is, below
            check(cdp.wait_for("!!document.querySelector('.story-strip button[aria-label^=\"Mark final\"]:not([disabled])')", timeout=20, settle=0.5),
                  f"Mark final is offered at {clip['w']}×{clip['h']} (D125: any size)")
        else:
            code = status_of("POST", f"/story/shots/{shot['id']}/versions/v1/finalize")
            check(code == 200, f"finalize accepted at {clip['w']}×{clip['h']} (the format {fmt['width']}×{fmt['height']} within the model's grid)")
            s4 = api("GET", f"/story/shots/{shot['id']}")
            check(s4["versions"][0]["state"] == "final" and s4["versions"][0]["clip_id"] == clip["id"], "v1 final with the Full clip")
            check(cdp.wait_for("!!document.querySelector('.story-strip .lock-badge')", timeout=20, settle=0.5), "the strip shows final")
    # stale: a camera move bumps the stage's revision past the version's
    st2 = api("GET", f"/stages/{st['id']}")
    api("PUT", f"/stages/{st['id']}", {**st2, "cameras": [{**st2["cameras"][0], "focal_mm": 50}]})
    cdp.eval("window.__loom2Story.loadShots().then(() => true)", timeout=30)
    check(cdp.wait_for("!!document.querySelector('.story-strip .stale-badge')", timeout=20, settle=0.5), "the version is marked stale after the stage moved (advisory)")
    if ctx is not None:
        ctx["shot"] = shot["id"]
        ctx["clip"] = rows_local.get("full", {}).get("clip")
        ctx["frame"] = frame
    rows.append({"part": "sy2", **rows_local, "failures": list(failures)})
    (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(rows[-1]) + "\n")
    print(json.dumps(rows[-1], indent=1))


def sy3(cdp, check, rows, failures, ctx: dict) -> None:
    """17 §12 item 4: five nodes with a Choice and a Condition, the SY2 shot bound (a second bind refused), Validate, Play through both
    branches without a job being queued."""
    shot = ctx.get("shot")
    jobs_before = len(api("GET", "/jobs")["items"])
    s = api("POST", "/story/flow/nodes", {"type": "start", "x": 0, "y": 0})
    d = api("POST", "/story/flow/nodes", {"type": "dialogue", "title": "At the gate", "x": 320, "y": 0})
    d = api("PATCH", f"/story/flow/nodes/{d['id']}", {"revision": d["revision"], "lines": [{"speaker": None, "text": "Let me through."}, {"speaker": None, "text": "The gate stays shut."}]})
    c = api("POST", "/story/flow/nodes", {"type": "choice", "title": "Push or wait", "x": 640, "y": 0})
    c = api("PATCH", f"/story/flow/nodes/{c['id']}", {"revision": c["revision"], "options": [{"id": "opt_push", "label": "Push through", "set": [{"var": "met_mara", "value": True}]}, {"id": "opt_wait", "label": "Wait"}]})
    q = api("POST", "/story/flow/nodes", {"type": "condition", "title": "Met her?", "x": 960, "y": 0})
    q = api("PATCH", f"/story/flow/nodes/{q['id']}", {"revision": q["revision"], "cond": {"var": "met_mara", "op": "eq", "value": True}})
    e1 = api("POST", "/story/flow/nodes", {"type": "shot", "title": "Dawn", "x": 1280, "y": -80})
    e2 = api("POST", "/story/flow/nodes", {"type": "shot", "title": "Dusk", "x": 1280, "y": 80})
    g = api("GET", "/story/flow")["graph"]
    g = api("PUT", "/story/flow/graph", {"revision": g["revision"], "nodes": g["nodes"], "start": s["id"],
                                        "edges": [{"from": s["id"], "port": "out", "to": d["id"]}, {"from": d["id"], "port": "out", "to": c["id"]}, {"from": c["id"], "port": "opt:opt_push", "to": q["id"]},
                                                  {"from": c["id"], "port": "opt:opt_wait", "to": q["id"]}, {"from": q["id"], "port": "then", "to": e1["id"]}, {"from": q["id"], "port": "else", "to": e2["id"]}]})
    check(len(g["edges"]) == 6 and g["start"] == s["id"], "six nodes and six edges saved, the Start the start")
    if shot:
        b = api("POST", f"/story/flow/nodes/{d['id']}/bind", {"shot_id": shot})
        check(b["shot"]["owner_node"] == d["id"], "the SY2 shot bound to the Dialogue (sole owner)")
        check(status_of("POST", f"/story/flow/nodes/{e1['id']}/bind", {"shot_id": shot}) == 422, "a second node cannot bind the same shot (422)")
    problems = api("POST", "/story/flow/validate")["problems"]
    codes = sorted(p["code"] for p in problems)
    check(codes == ["no_shot", "no_shot"], f"Validate lists only the two end shots without a shot: {codes}")
    cdp.eval("window.__loom2Story.openTab('flow')")
    cdp.eval("window.__loom2Story.loadFlow().then(() => true)", timeout=30)
    check(cdp.wait_for("document.querySelectorAll('.flow-node').length === 6", timeout=30, settle=1.0), "the canvas shows the six nodes")
    cdp.eval("window.__loom2Story.playStart()")
    st = cdp.eval("window.__loom2Story.flow().play")
    check(bool(st) and st["node"] == d["id"] and st["waiting"] == "next", "Play stops at the Dialogue")
    check(cdp.wait_for("!!document.querySelector('[data-testid=\"play-view\"] .play-lines') && document.querySelector('[data-testid=\"play-view\"]').textContent.includes('Let me through.')", timeout=20, settle=0.5), "the play view shows the lines (and the bound shot's clip)")
    cdp.eval("window.__loom2Story.playNext()")
    cdp.eval("window.__loom2Story.playNext('opt_push')")
    st = cdp.eval("window.__loom2Story.flow().play")
    check(bool(st) and st["node"] == e1["id"] and st["vars"].get("met_mara") is True, "Push sets the variable; the Condition takes then → Dawn")
    cdp.eval("window.__loom2Story.playNext()")
    st = cdp.eval("window.__loom2Story.flow().play")
    check(bool(st) and st["ended"], "the end after Dawn")
    cdp.eval("window.__loom2Story.playStart()"); cdp.eval("window.__loom2Story.playNext()"); cdp.eval("window.__loom2Story.playNext('opt_wait')")
    st = cdp.eval("window.__loom2Story.flow().play")
    check(bool(st) and st["node"] == e2["id"], "Wait leaves the variable; the Condition takes else → Dusk")
    cdp.eval("window.__loom2Story.playStop()")
    check(len(api("GET", "/jobs")["items"]) == jobs_before, "play queued no job (loom R143)")
    ctx["node"] = d["id"]
    rows.append({"part": "sy3", "nodes": 6, "edges": 6, "problems": codes, "failures": list(failures)})


def sy4(cdp, check, rows, failures, ctx: dict) -> None:
    """17 §12 item 5: a sequence with the final shot (stamped) and a plain clip, the checklist, the exports with a marker and the lines,
    the draft render as a clip."""
    shot, clip_id = ctx.get("shot"), ctx.get("clip")
    if not shot or not clip_id:
        check(False, "sy4 needs sy2's final shot and clip"); return
    clip = api("GET", f"/clips/{clip_id}")
    tl = api("POST", "/timelines", {"name": "SY5 alpha reel"})
    cdp.eval("window.__loom2Story.openTab('episode')")
    check(cdp.wait_for("!!window.__loom2Sequence", timeout=30, settle=0.5), "the Episode tab loaded")
    cdp.eval(f"window.__loom2Sequence.getState().load().then(() => window.__loom2Sequence.getState().open({json.dumps(tl['id'])})).then(() => true)", timeout=30)
    cdp.eval(f"window.__loom2Sequence.getState().addShot({json.dumps(clip)}, {json.dumps({'id': shot, 'version': 'v1', 'node': ctx.get('node')})})")
    draft = ctx.get("draft_clip")
    if draft:
        cdp.eval(f"window.__loom2Sequence.getState().addClip({json.dumps(api('GET', f'/clips/{draft}'))})")
    t0 = time.time()
    while time.time() - t0 < 20 and len(api("GET", f"/timelines/{tl['id']}")["clips"]) < (2 if draft else 1):
        time.sleep(0.5)
    doc = api("GET", f"/timelines/{tl['id']}")
    check(doc["clips"][0]["shot_id"] == shot and doc["clips"][0]["shot_version"] == "v1" and doc["clips"][0]["node_id"] == ctx.get("node"), "the lane's first clip is the final shot, stamped with its version and node")
    check(cdp.wait_for("document.querySelectorAll('.seq-clip').length >= 1", timeout=20, settle=0.5), "the lane shows the block")
    fx = api("POST", f"/timelines/{tl['id']}/export", {"format": "fcpxml"})
    check(fx["text"].count("<marker ") == 1 and 'value="At the gate"' in fx["text"], "the FCPXML carries one chapter marker named by the node")
    markers = (Path(api("GET", "/project")["path"]) / "timelines" / tl["id"] / "markers.txt").read_text(encoding="utf-8")
    check(markers.startswith("00:00:00:00\tAt the gate"), f"markers.txt: {markers.strip()!r}")
    srt = api("POST", f"/timelines/{tl['id']}/export", {"format": "srt"})
    check("Let me through." in srt["text"] and "The gate stays shut." in srt["text"] and srt["text"].count("-->") == 2, "the SRT carries the node's two lines, timed by the lane")
    edl = api("POST", f"/timelines/{tl['id']}/export", {"format": "edl"})
    check(edl["text"].startswith("TITLE: SY5 alpha reel"), "the EDL is written")
    t0 = time.time()
    jobs = api("POST", f"/timelines/{tl['id']}/render")["jobs"]
    j = wait_jobs([jobs[0]["id"]])[jobs[0]["id"]]
    check(j["status"] == "done" and bool(j.get("result", {}).get("clip_id")), f"the draft render (CPU) done in {time.time() - t0:.0f} s")
    rows.append({"part": "sy4", "timeline": tl["id"], "render_s": round(time.time() - t0, 1), "failures": list(failures)})


def finish(edge, proc: dict, failures) -> int:
    orch, orch_log = proc["orch"], proc["log"]
    if edge:
        edge.terminate()
    try:
        api("POST", "/shutdown")
    except Exception:
        pass
    try:
        orch.wait(timeout=60)
    except Exception:
        orch.kill()
    orch_log.close()
    try:                                                                                   # an engine left by a killed orchestrator (the durability part)
        urllib.request.urlopen(f"http://{ENGINE}/system_stats", timeout=2)
        pid = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-NetTCPConnection -LocalPort 8188 -State Listen | Select-Object -First 1).OwningProcess"], capture_output=True, text=True).stdout.strip()
        if pid.isdigit():
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
            print(f"stopped the leftover engine (pid {pid})")
    except Exception:
        pass
    print(f"{len(failures)} failure(s)" if failures else "all checks ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
