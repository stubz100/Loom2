"""P18 (D79 / D84) acceptance: the five E14 inputs become posable props in a Stage scene through the app, on the rig. Needs the frontend
dev server on 1420, a visible Edge and port 8188 free (the orchestrator it starts launches the engine, like scripts/st_acceptance.py).

What it does: starts an orchestrator (port 8773, a temp state, models on F:), makes a project, imports bench/mesh/01–05.jpg, queues one
`ImageToMesh` job per image through `POST /jobs` (serially — a background job of some minutes each; the first is cold), records the wall
time, the GLB's size and triangle count (read from the glTF JSON chunk), the licences in the asset's manifest and the thumbnail; then opens
the Stage suite in Edge, makes a stage with the room and places the five props through the Library's cards (`__loom2Stage` dev hook),
waits until every GLB is loaded in the viewport, selects and moves one, and saves a screenshot.

Bars (08 §9 P18, D79): every job done with a `mesh` asset (≤ 50k faces + a few per cent — DecimateMesh's target), licences present
(DINOv3's named), the five props loaded and posable in the viewport. Time is recorded, not a bar (D79 accepted the cost as shown):
the GPU stages take seconds, the CPU stages (remesh at 768, unwrap, bake) vary with the prop — 344–538 s on 2026-10-13 against E14's
243 s median; a 600 s ceiling catches a runaway.

    orchestrator/.venv/Scripts/python.exe scripts/p18_acceptance.py [--props 01,02] [--faces 50000]
"""
from __future__ import annotations

import argparse
import json
import os
import struct
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

PORT, TOKEN, DBG, DEV, ENGINE = 8773, "props", 9335, 1420, "127.0.0.1:8188"
OUT = ROOT / "engine" / "spikes" / "out" / "p18"
RESULTS = OUT / "results.jsonl"
BENCH = ROOT / "bench" / "mesh"
BARS = {"warm_s": 600.0, "cold_s": 600.0, "faces_max": 52500}   # time: a runaway ceiling only — the GPU stages take seconds; remesh / unwrap / bake on the CPU vary with the prop (rig 2026-10-13: 344–538 s)


def api(method: str, path: str, body=None, raw: bool = False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if raw else json.loads(r.read().decode("utf-8") or "null")


def wait_job(jid: str, timeout_s: float = 3600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = api("GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(2.0)
    raise TimeoutError(jid)


def glb_info(data: bytes) -> dict:
    """Magic, version, the JSON chunk; the triangle count from the first mesh's accessors (indexed or not)."""
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67:
        raise ValueError("not a GLB")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    tris = 0
    for mesh in js.get("meshes", []):
        for prim in mesh.get("primitives", []):
            acc = js["accessors"][prim["indices"]] if "indices" in prim else js["accessors"][prim["attributes"]["POSITION"]]
            tris += acc["count"] // 3
    return {"version": version, "bytes": length, "meshes": len(js.get("meshes", [])), "triangles": tris, "images": len(js.get("images", [])), "materials": len(js.get("materials", []))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--props", default="01,02,03,04,05")
    ap.add_argument("--faces", type=int, default=50000)
    a = ap.parse_args()
    props = [p for p in a.props.split(",") if p]
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
    tmp = Path(tempfile.mkdtemp(prefix="loom2-p18-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full",
                                              "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
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
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "P18", "size_cap_gb": 40})
        mc = api("GET", "/capabilities")["mesh"]
        print("mesh model:", mc["model_id"], mc["health"], mc["seconds"], mc["cold_seconds"], mc["licences"])
        check(bool(mc["model_id"]) and mc["health"] != "missing", f"{mc['label']} offered with its weights present")
        imported = {p: api("POST", "/assets/import", {"paths": [str(BENCH / f"{p}.jpg")]})["items"][0]["id"] for p in props}
        meshes: dict[str, str] = {}
        for i, p in enumerate(props):
            jobs = api("POST", "/jobs", {"recipe": {"kind": "image_to_mesh", "asset_id": imported[p], "faces": a.faces}, "stage": False, "origin": {"suite": "api", "surface": "p18_acceptance"}})
            jid = jobs["jobs"][0]["id"]
            t0 = time.time()
            j = wait_job(jid)
            wall = time.time() - t0
            ok = j["status"] == "done" and bool(j.get("result", {}).get("asset_ids"))
            row = {"prop": p, "job": jid, "status": j["status"], "error": j.get("error"), "wall_s": round(wall, 1), "cold": i == 0, "asset_ids": j.get("result", {}).get("asset_ids")}
            check(ok, f"prop {p} ({'cold' if i == 0 else 'warm'}): job {j['status']} in {wall:.1f} s" + (f" — {j.get('error')}" if j.get("error") else ""))
            if ok:
                check(wall <= (BARS["cold_s"] if i == 0 else BARS["warm_s"]), f"prop {p}: {wall:.1f} s ≤ {BARS['cold_s'] if i == 0 else BARS['warm_s']} s")
                aid = row["asset_ids"][0]
                asset = api("GET", f"/assets/{aid}")
                data = api("GET", f"/assets/{aid}/file", raw=True)
                (OUT / f"{p}.glb").write_bytes(data)
                info = glb_info(data)
                row.update(info)
                check(asset["kind"] == "mesh" and asset["lineage_kind"] == "image-to-mesh" and asset["parents"] == [imported[p]], f"prop {p}: a mesh asset with lineage image-to-mesh ← the photo")
                check(asset["thumb_status"] == "done", f"prop {p}: thumbnail from the RenderMesh view")
                lic = asset["params"].get("licences", {})
                check("dinov3-l" in lic and lic["dinov3-l"].startswith("dinov3") and lic.get("pixal3d-int8") == "mit", f"prop {p}: licences in the manifest ({len(lic)} weights)")
                check(info["triangles"] <= BARS["faces_max"] and info["materials"] >= 1, f"prop {p}: {info['triangles']} triangles ≤ {BARS['faces_max']}, {info['images']} textures, {info['bytes'] / 2**20:.1f} MiB")
                meshes[p] = aid
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps({**row, "at": time.strftime("%Y-%m-%d %H:%M")}) + "\n")
        # the Stage: the props placed through the Library, loaded in the viewport, one of them moved
        if meshes:
            st = api("POST", "/stages", {"name": "Props"})
            st = api("PUT", f"/stages/{st['id']}", {**st, "objects": [{"id": "set_room", "kind": "set", "name": "Set 1", "preset": "room", "asset_id": None, "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}, "parent": None, "locked": True, "visible": True, "colour_id": 0, "pose": None, "billboard": False}]})
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
                check(False, "no page target"); return 1
            cdp = CDP(ws_url)
            cdp.call("Page.enable"); cdp.call("Runtime.enable"); cdp.call("Log.enable")
            cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
            cdp.call("Page.reload")
            cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=1.0)
            check(cdp.wait_for("!!window.__loom2Stage", timeout=60, settle=0.5), "the Stage suite loaded")
            cdp.eval(f"window.__loom2Stage.open({json.dumps(st['id'])})")
            check(cdp.wait_for("!!document.querySelector('canvas.stage-canvas')", timeout=30, settle=1.5), "the stage opened")
            check(cdp.wait_for(f"document.querySelectorAll('.lib-grid .mesh-card').length >= {len(meshes)}", timeout=20, settle=0.5), f"the Library lists {len(meshes)} meshes")
            for k in range(len(meshes)):
                cdp.eval(f"document.querySelectorAll('.lib-grid .mesh-card')[{k}].click()")
                time.sleep(0.4)
            loaded = cdp.wait_for(f"window.__loom2Stage.meshes().loaded.length >= {len(meshes)}", timeout=120, settle=1.0)
            state = cdp.eval("window.__loom2Stage.meshes()") or {}
            check(loaded, f"{len(state.get('loaded', []))} / {len(meshes)} GLBs loaded in the viewport (failed: {state.get('failed')})")
            # spread them out and move one with the store (the gizmo path is the same store call)
            ids = cdp.eval("window.__loom2Stage.state().current.objects.filter((o) => o.kind === 'mesh').map((o) => o.id)") or []
            for k, oid in enumerate(ids):
                cdp.eval(f"window.__loom2Stage.setTransform({json.dumps(oid)}, {{pos: [{-2 + k * 1.0}, 0, {0.3 * (k % 2)}], rot: [0, {k * 30}, 0], scale: [1, 1, 1]}})")
            time.sleep(1.0)
            moved = cdp.eval("window.__loom2Stage.state().current.objects.filter((o) => o.kind === 'mesh').map((o) => o.transform.pos[0])") or []
            check(len(moved) == len(ids) and all(abs(x - (-2 + k)) < 1e-6 for k, x in enumerate(moved)), "the props take transforms (posable)")
            cdp.eval("window.__loom2Stage.frameAll && window.__loom2Stage.frameAll()")
            time.sleep(1.5)
            shot = cdp.call("Page.captureScreenshot", format="png")
            import base64
            (OUT / "stage.png").write_bytes(base64.b64decode(shot["data"]))
            print(f"screenshot: {OUT / 'stage.png'}")
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
    print(f"\np18_acceptance: {'all checks passed' if not failures else f'{len(failures)} FAILED'}")
    for f_ in failures:
        print("  -", f_)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
