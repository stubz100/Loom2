"""17 §12 (D85) acceptance of the Story workspace on the rig, through the app. SY1 (item 2): a hero → a character profile → Expand (one job per
coverage cell on D78's clay model, Klein 9B) → the candidates on the version's page with their cells → curate ≥ 25 into the reference set
with every shot-size row covered → Lock (the album refuses) → `@Mara` resolves to the locked version with the hero first, and a Generate
job with the mention records the stamp. Later slices add their items here.

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


def wait_jobs(ids: list[str], timeout_s: float = 3600) -> dict[str, dict]:
    """Every job of `ids` in a terminal state; returns them by id (progress printed as they finish)."""
    t0 = time.time()
    done: dict[str, dict] = {}
    while time.time() - t0 < timeout_s and len(done) < len(ids):
        for j in api("GET", "/jobs")["items"]:
            if j["id"] in ids and j["id"] not in done and j["status"] in ("done", "failed", "cancelled"):
                done[j["id"]] = j
                print(f"  job {len(done)}/{len(ids)} {j['status']} wall {j.get('wall_s')}", flush=True)
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
    ap.add_argument("--keep", type=int, default=30, help="how many candidates to keep (by cell order, every shot-size row first)")
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
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=orch_log, stderr=subprocess.STDOUT, text=True)
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
        # 1. the profile from the hero
        p = cdp.eval(f"window.__loom2Story.createProfile('Mara', 'character', {json.dumps(hero)}, {json.dumps(STUB)})", timeout=30)
        check(bool(p) and p["versions"][0]["hero_asset_id"] == hero, "the profile Mara v1 made with the hero")
        pid, gid = p["id"], p["versions"][0]["group_id"]
        check(api("GET", f"/groups/{gid}")["group"]["cover_id"] == hero, "the hero is the reference page's cover")
        check(cdp.wait_for("!!document.querySelector('.cast-page h2') && document.querySelector('.cast-page h2').textContent.includes('Mara')", timeout=20, settle=1.0), "the Cast page shows Mara")
        # 2. Expand: one job per cell, timed
        t_exp = time.time()
        r = cdp.eval(f"window.__loom2Story.expand({json.dumps(a.preset)}, 1, 'draft')", timeout=120)
        check(bool(r) and r["cells"] == caps["presets"][a.preset]["cells"] and len(r["job_ids"]) == r["cells"], f"Expand {a.preset}: {r and r['cells']} jobs queued in one batch")
        jobs = wait_jobs(r["job_ids"])
        exp_wall = time.time() - t_exp
        walls = [j.get("wall_s") or 0 for j in jobs.values()]
        order = {jid: i for i, jid in enumerate(r["job_ids"])}
        first = min(jobs.values(), key=lambda j: order[j["id"]])
        warm = sorted(j.get("wall_s") or 0 for j in jobs.values() if j["id"] != first["id"])
        check(all(j["status"] == "done" and j.get("result", {}).get("asset_ids") for j in jobs.values()), f"every job done with an asset ({len(jobs)}/{r['cells']}) in {exp_wall:.0f} s")
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
        # 3. curate: every shot-size row first, then by cell order, up to --keep
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
        reject = [x["id"] for x in cands if x["id"] not in keep][:3]
        ok = cdp.eval(f"window.__loom2Story.curate({json.dumps(keep)}, 'keep').then(() => true)", timeout=120)
        cdp.eval(f"window.__loom2Story.curate({json.dumps(reject)}, 'reject').then(() => true)", timeout=60)
        ref = api("GET", f"/groups/{gid}")
        kept = [x for x in ref["assets"].values() if x["id"] != hero]
        rows_covered = {x["params"].get("coverage_cell", {}).get("shot") for x in kept}
        check(ok is True and len(kept) >= BARS["kept_min"], f"{len(kept)} kept in the reference set (bar ≥ {BARS['kept_min']})")
        check(set(caps["coverage"]["shots"]) <= rows_covered, f"every shot-size row covered: {sorted(rows_covered)}")
        check(all(x["state"] == "keep" for x in kept), "the kept ones are marked keep")
        check(all(api("GET", f"/assets/{i}")["state"] == "reject" for i in reject) and all(i in api("GET", f"/groups/{r['group_id']}")["assets"] for i in reject), "the rejected ones stay on the candidates page, marked reject")
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
        j = wait_jobs([job["id"]])[job["id"]]
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
    finally:
        if edge:
            edge.terminate()
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=30)
        except Exception:
            orch.kill()
        orch_log.close()
    print(f"{len(failures)} failure(s)" if failures else "all checks ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
