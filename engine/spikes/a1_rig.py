"""D125 A1 rig (proto01_UIcomp 04 §8): the clay final shot made *for* a Story shot, through the product path, to its take. PS5's scene on a
fresh project (Mara and Ines as Cast characters bound to Detailed figures, 5 s at F16), with one difference at the start: a Shot node's
shot is linked to the stage camera and Animate's For chip names its v1 when *Make the final shot* runs (finalShot.makeFinal reads it). Then
the plate, each character performed (Wan Animate, chained), matted (SAM 3), the assembly — which must land as a take of v1 without filling
its clip (`use` False) — and the composition rendered by EffectCraft, which fills v1's empty clip (`use` None). Results in
engine/spikes/out/a1/results.json.

  orchestrator/.venv/Scripts/python.exe engine/spikes/a1_rig.py            # Vite on 1420; the engine free (one GPU job at a time, D97)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
import e28c_models as C  # noqa: E402
import ps5_rig as R  # noqa: E402
from e23b_layers import C0, INES_AT, MARA_PATH, SIT_AT  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "a1"
P.OUT = OUT
checks: list[tuple[str, bool]] = []


def check(ok: bool, what: str) -> None:
    checks.append((what, bool(ok)))
    R.log(f"{'PASS' if ok else 'FAIL'}  {what}")


def open_edge(edge, app, st_id: str, n_objects: int) -> None:
    """ps5_rig's Edge start, with the background throttling off — a hidden or occluded rig window otherwise renders the passes at a crawl
    (the first A1 run split in 740 s against PS5's 26 s)."""
    import subprocess
    import urllib.request
    from edit_headed_check import CDP, EDGE
    url = f"http://127.0.0.1:{P.DEV}/?token={P.TOKEN}&port={P.PORT}&suite=stage"
    edge.proc = subprocess.Popen([EDGE, f"--remote-debugging-port={C.DBG}", f"--user-data-dir={app.tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                  "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
                                  "--window-size=1600,1000", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws_url = None
    t0 = time.time()
    while time.time() - t0 < 30 and not ws_url:
        try:
            for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{C.DBG}/json", timeout=3)):
                if t.get("type") == "page" and f"127.0.0.1:{P.DEV}" in t.get("url", ""):
                    ws_url = t["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.5)
    edge.cdp = c = CDP(ws_url)
    c.call("Page.enable"); c.call("Runtime.enable")
    c.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)
    c.call("Page.reload")
    c.wait_for("document.readyState === 'complete' && !!window.__loom2Stage", timeout=60, settle=1.0)
    c.eval(f"window.__loom2Stage.open({json.dumps(st_id)})")
    c.wait_for(f"!!document.querySelector('canvas.stage-canvas') && window.__loom2Stage.state().current?.objects.length === {n_objects}", timeout=30, settle=8.0)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    project = OUT / "project"
    app = P.App(project)
    edge = None
    timings: dict = {}
    try:
        cast = {}
        for name, (hero, ref, look, outfit) in R.CAST.items():
            h = P.api("POST", "/assets/import", {"paths": [str(R.E22 / "heroes" / hero)]})["items"][0]["id"]
            r = P.api("POST", "/assets/import", {"paths": [str(R.E23B / "refs" / ref)]})["items"][0]["id"]
            p = P.api("POST", "/story/profiles", {"name": name, "cls": "character", "hero_asset_id": h, "appearance": look, "outfit": outfit})
            P.api("PUT", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "asset_id": r})
            j = P.wait_job(P.api("POST", f"/story/profiles/{p['id']}/versions/v1/body/fit")["job_id"])
            cast[name] = p["id"]
            R.log(f"{name}: profile {p['id']}, body fitted ({j['status']})")
        P.drain(); P.api("POST", "/engine/stop")                                # D97: the GPU free while Edge renders
        st = P.api("POST", "/stages", {"name": "A1 rig"})
        cam = {**st["cameras"][0], **C0}
        tf = lambda pos, yaw=0: {"pos": list(pos), "rot": [0, yaw, 0], "scale": [1, 1, 1]}   # noqa: E731
        objs = [{"id": "set_a", "kind": "set", "name": "Room", "preset": "room", "transform": tf((0, 0, 0)), "colour_id": 1, "locked": True},
                {"id": "light_key", "kind": "light", "name": "Window", "transform": tf((-3.4, 2.8, 0.2)), "colour_id": 2,
                 "light": {"intensity": 2.4, "colour": "#fff1dc", "softness": 0.6, "shadows": True, "target": [0, 1, 0]}},
                {"id": "stool", "kind": "prop", "name": "Stool", "preset": "block", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [0.45, 0.48, 0.45]}, "colour_id": 3},
                {"id": "fig_m", "kind": "mannequin", "name": "Mara", "preset": "adult", "transform": tf((MARA_PATH[0][0], 0, MARA_PATH[0][1])), "colour_id": 4,
                 "pose": {"preset": "stand", "joints": {}, "extra": {}}, "detail": "female", "path": MARA_PATH, "profile_id": cast["Mara"]},
                {"id": "fig_i", "kind": "mannequin", "name": "Ines", "preset": "adult", "transform": tf(INES_AT), "colour_id": 5,
                 "pose": {"preset": "stand", "joints": {}, "extra": {}}, "detail": "female", "profile_id": cast["Ines"]}]
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}, "range": {"start": 0, "end": R.END}})
        # the Story shot: a Shot node's own shot, its v1 pointed at the stage camera (S11) — no second shot
        node = P.api("POST", "/story/flow/nodes", {"type": "shot", "title": "Mara comes in", "text": "Mara walks in; Ines sits down by the window"})
        sid = node["shot_id"]
        P.api("PUT", f"/story/shots/{sid}/versions/v1/source", {"stage_id": st["id"], "camera_id": st["cameras"][0]["id"]})
        R.log(f"shot {sid} (node {node['id']}) on {st['id']} · {st['cameras'][0]['id']}")
        edge = C.Edge.__new__(C.Edge)
        open_edge(edge, app, st["id"], len(objs))
        cdp = edge.cdp
        r = cdp.eval(R.MOTION_JS.replace("%SIT%", str(SIT_AT)).replace("%END%", str(R.END)), timeout=300) or {}
        if r.get("error"):
            print(r); return 1
        R.log(f"motion keyed: {r['keys']}")
        # the For chip on the shot's v1, then Make the final shot (A1: it carries the shot and the version)
        cdp.eval("(async () => { const O = await import('/src/store/origin.ts'); O.useMakeFor.getState().set('animate', "
                 + json.dumps({"kind": "shot", "shot_id": sid, "version": "v1", "name": "Mara comes in", "node_id": node["id"]}) + ") })()")
        t0 = time.time()                                                           # the product's verb: it reads the chip and asks first
        cdp.eval("(async () => { const F = await import('/src/suites/stage/finalShot.ts'); window.__a1 = F.useFinals.getState().make(16).then((f) => f ?? { error: 'make returned nothing' }, (e) => ({ error: String(e) })) })()")
        cdp.wait_for("!!document.querySelector('.modal.ask button.primary')", timeout=60, settle=0.5)
        ask = cdp.eval("document.querySelector('.modal.ask .ask-text')?.textContent ?? ''") or ""
        check("becomes a take of Mara comes in" in ask, "Make the final shot says the finished shot becomes a take of the chip's shot")
        cdp.eval("document.querySelector('.modal.ask button.primary').click()")
        fin = cdp.eval("window.__a1", timeout=1800)
        if not fin or fin.get("error"):
            print(fin, cdp.page_errors()[:3]); return 1
        timings["split_s"] = round(time.time() - t0, 1)
        check(fin.get("shot_id") == sid and fin.get("shot_version") == "v1", f"the final carries the For chip's shot and version ({fin.get('shot_id')} {fin.get('shot_version')})")
        R.log(f"final {fin['id']}: {[x['id'] for x in fin['layers']]} × {fin['frames']} frames in {timings['split_s']} s")
        # the plate
        cdp.eval(f"(async () => {{ const S = await import('/src/suites/stage/stageStore.ts'); S.st().setShot({{ prompt_text: {json.dumps(R.PLATE_PROMPT)} }}) }})()")
        t0 = time.time()
        cdp.eval(f"(async () => {{ const F = await import('/src/suites/stage/finalShot.ts'); await F.makePlate({json.dumps(fin)}) }})()", timeout=120)
        while not next(x for x in P.api("GET", f"/finals/{fin['id']}")["layers"] if x["id"] == "plate")["still_asset_id"]:
            time.sleep(2)
        timings["plate_still_s"] = round(time.time() - t0, 1)
        P.drain(); P.api("POST", "/engine/stop")
        f = P.api("GET", f"/finals/{fin['id']}")
        r = cdp.eval(f"(async () => {{ const F = await import('/src/suites/stage/finalShot.ts'); try {{ return await F.projectPlate({json.dumps(f)}) }} catch (e) {{ return {{ error: String(e) }} }} }})()", timeout=600)
        if r.get("error"):
            print(r); return 1
        R.log(f"the plate: still {timings['plate_still_s']} s, projected")
        edge.close(); edge = None                                                  # the browser's part is done
        # the character layers, one after the other on the queue; their mattes
        for lid in ("fig_m", "fig_i"):
            t0 = time.time()
            q = P.api("POST", f"/finals/{fin['id']}/layers/{lid}/run", {"seed": 20261021})
            layer = R.wait_layer(fin["id"], lid)
            timings[lid] = {"wall_s": round(time.time() - t0, 1), "batches": q["batches"], "status": layer["status"], "error": layer.get("error")}
            R.log(f"{lid}: {timings[lid]}")
            if layer["status"] != "done":
                return 1
        for lid in ("fig_m", "fig_i"):
            if not (project / "finals" / fin["id"] / lid / "matte").is_dir():
                t0 = time.time()
                j = P.wait_job(P.api("POST", f"/finals/{fin['id']}/layers/{lid}/matte", {"text": "person"})["job_id"])
                timings[f"matte_{lid}_s"] = round(time.time() - t0, 1)
                R.log(f"{lid}: matte {j['status']} in {timings[f'matte_{lid}_s']} s")
        # the assembly: a take of v1, its clip slot left alone
        t0 = time.time()
        j = P.wait_job(P.api("POST", f"/finals/{fin['id']}/assemble")["job_id"])
        timings["assemble_s"] = round(time.time() - t0, 1)
        if j["status"] != "done":
            print("assemble", j["status"], j.get("error"), j.get("log_tail", [])[-3:]); return 1
        asm = j["result"]["clip_id"]
        v1 = P.api("GET", f"/story/shots/{sid}")["versions"][0]
        check(any(t["kind"] == "clip" and t["id"] == asm for t in v1["takes"]), f"the assembly {asm} is a take of v1")
        check(v1["clip_id"] is None, "the assembly did not fill v1's clip by itself")
        check(len(P.api("GET", "/story/shots")["items"]) == 1, "one shot in the project (no second shot made)")
        # the finished shot: the composition rendered — it fills v1's empty clip
        P.drain(); P.api("POST", "/engine/stop")
        P.api("POST", f"/finals/{fin['id']}/composition")
        t0 = time.time()
        j = P.wait_job(P.api("POST", f"/finals/{fin['id']}/composition/render")["job_id"])
        timings["render_s"] = round(time.time() - t0, 1)
        if j["status"] != "done":
            print("render", j["status"], j.get("error"), j.get("log_tail", [])[-3:]); return 1
        ren = j["result"]["clip_id"]
        v1 = P.api("GET", f"/story/shots/{sid}")["versions"][0]
        check(any(t["kind"] == "clip" and t["id"] == ren for t in v1["takes"]), f"the render {ren} is a take of v1")
        check(v1["clip_id"] == ren, "the render filled v1's empty clip")
        clip = P.api("GET", f"/clips/{ren}")
        timings["render_clip"] = {"frames": clip["frames"], "fps": clip["fps"], "w": clip["w"], "h": clip["h"]}
        (OUT / "final.mp4").write_bytes((project / "clips" / ren / "proxy.mp4").read_bytes())
    finally:
        if edge and getattr(edge, "proc", None):
            edge.close()
        app.close()
        (OUT / "results.json").write_text(json.dumps({"timings": timings, "checks": [{"what": w, "ok": ok} for w, ok in checks]}, indent=1), encoding="utf-8")
    R.log(f"timings: {json.dumps(timings)}")
    R.log(f"{sum(ok for _, ok in checks)}/{len(checks)} checks pass")
    return 0 if checks and all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
