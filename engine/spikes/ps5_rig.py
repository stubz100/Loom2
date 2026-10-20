"""D111 PS5 rig (proto01_animate 16): E23's shot made through the product's final-shot path on a fresh project — Mara and Ines as Cast
characters (E22's heroes, E23b's animation references, bodies fitted by the app's own job) bound to Detailed figures, Mara walking her
path and Ines sitting on the stool stand-in under the window light, 5 s (81 frames at F16: two chained batches per character).
Make the final shot (Stage's passes) → the plate (Klein) and its projection → each character layer performed (Wan Animate, chained) →
(later steps: mattes, assembly). Frames, sheets and timings in engine/spikes/out/ps5/.

  orchestrator/.venv/Scripts/python.exe engine/spikes/ps5_rig.py            # Vite on 1420; the engine free
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
import e28c_models as C  # noqa: E402
from e23b_layers import C0, INES_AT, MARA_PATH, SIT_AT  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ps5"
E22, E23B, E23C = (ROOT / "engine" / "spikes" / "out" / n for n in ("e22", "e23b", "e23c"))
P.OUT = OUT
END = 120                                          # 5 s of Stage frames: 81 at F16 → two batches (77 + 72 new)
PLATE_PROMPT = "a quiet whitewashed room with bare plaster walls and a worn wooden plank floor, soft daylight from a window on the left. Natural colours, cinematic film still, 35 mm."
CAST = {"Mara": ("L.png", "mara.png", "Mara, a young woman with a black bob and round glasses", "a grey wool coat, black trousers, black shoes"),
        "Ines": ("R.png", "ines.png", "Ines, a woman with long curly red hair and freckles", "a mustard-yellow work jacket, dark jeans, brown boots")}

MOTION_JS = """(async () => { try {
  const S = await import('/src/suites/stage/stageStore.ts')
  const M = await import('/src/suites/stage/motion/motionStore.ts')
  const lib = await import('/src/suites/stage/motion/library.ts')
  const st = S.st, mm = () => M.useMotion.getState()
  await mm().refresh()
  const file = mm().files.find((f) => f.name === 'AnimationLibrary_Godot_Standard')
  if (!file) return { error: 'the starter library is not listed' }
  const clips = await lib.clipsOf(file), clip = (n) => clips.find((c) => c.name === n)
  st().select('fig_m'); st().setFrame(0)
  mm().pick(clip('Walk_Loop')); mm().set({ lock: true, alongPath: true, blend: 6 }); await mm().apply()
  st().select('fig_i'); st().setFrame(%SIT%)
  mm().pick(clip('Sitting_Enter')); mm().set({ lock: true, alongPath: false, blend: 0 }); await mm().apply()
  st().setRange(0, %END%); st().setFrame(0); st().select(null)
  await st().flush()
  return { ok: true, keys: Object.fromEntries(Object.entries(st().current.keyframes.objects).map(([k, v]) => [k, v.length])) }
} catch (e) { return { error: String(e && e.stack || e) } } })()"""


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def wait_layer(fid: str, lid: str, timeout: float = 3600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        f = P.api("GET", f"/finals/{fid}")
        layer = next(x for x in f["layers"] if x["id"] == lid)
        if layer["status"] in ("done", "failed"):
            return layer
        time.sleep(3)
    raise TimeoutError(lid)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    project = OUT / "project"
    app = P.App(project)
    edge = None
    timings: dict = {}
    try:
        # the cast: heroes, animation references set by hand, bodies fitted by the app's keypoints job
        cast = {}
        for name, (hero, ref, look, outfit) in CAST.items():
            h = P.api("POST", "/assets/import", {"paths": [str(E22 / "heroes" / hero)]})["items"][0]["id"]
            r = P.api("POST", "/assets/import", {"paths": [str(E23B / "refs" / ref)]})["items"][0]["id"]
            p = P.api("POST", "/story/profiles", {"name": name, "cls": "character", "hero_asset_id": h, "appearance": look, "outfit": outfit})
            P.api("PUT", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "asset_id": r})
            j = P.wait_job(P.api("POST", f"/story/profiles/{p['id']}/versions/v1/body/fit")["job_id"])
            cast[name] = p["id"]
            log(f"{name}: profile {p['id']}, body fitted ({j['status']})")
        P.drain(); P.api("POST", "/engine/stop")                                # D97: the GPU free while Edge renders
        st = P.api("POST", "/stages", {"name": "PS5 rig"})
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
        st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": objs, "cameras": [cam], "size": {**st["size"], "fps": 24}, "range": {"start": 0, "end": END}})
        edge = C.Edge.__new__(C.Edge)                                              # the Edge helper without the models' wait (no meshes here)
        _open_edge(edge, app, st["id"], len(objs))
        cdp = edge.cdp
        r = cdp.eval(MOTION_JS.replace("%SIT%", str(SIT_AT)).replace("%END%", str(END)), timeout=300) or {}
        if r.get("error"):
            print(r); return 1
        log(f"motion keyed: {r['keys']}")
        t0 = time.time()
        fin = cdp.eval("(async () => { const F = await import('/src/suites/stage/finalShot.ts'); try { return await F.makeFinal({ rate: 16, name: 'Rig' }) } catch (e) { return { error: String(e) } } })()", timeout=900)
        if not fin or fin.get("error"):
            print(fin, cdp.page_errors()[:3]); return 1
        timings["split_s"] = round(time.time() - t0, 1)
        log(f"final {fin['id']}: {[x['id'] for x in fin['layers']]} × {fin['frames']} frames in {timings['split_s']} s")
        # the plate
        cdp.eval(f"(async () => {{ const S = await import('/src/suites/stage/stageStore.ts'); S.st().setShot({{ prompt_text: {json.dumps(PLATE_PROMPT)} }}) }})()")
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
        log(f"the plate: still {timings['plate_still_s']} s, projected")
        # the character layers, one after the other on the queue
        for lid in ("fig_m", "fig_i"):
            t0 = time.time()
            q = P.api("POST", f"/finals/{fin['id']}/layers/{lid}/run", {"seed": 20261021})
            layer = wait_layer(fin["id"], lid)
            timings[lid] = {"wall_s": round(time.time() - t0, 1), "batches": q["batches"], "placed": q["placed"], "status": layer["status"], "error": layer.get("error")}
            log(f"{lid}: {timings[lid]}")
        d = project / "finals" / fin["id"]
        for lid in ("fig_m", "fig_i"):
            picks = [0, 40, 76, 77, 80]
            if not (d / lid / "frames").is_dir():
                continue
            row = [Image.open(d / lid / "frames" / f"{i:04d}.png").convert("RGB") for i in picks]
            pose = [Image.open(d / lid / "pose" / f"{i:04d}.png").convert("RGB") for i in picks]
            w, h = row[0].size
            sheet = Image.new("RGB", (w * len(picks), h * 2))
            for k, (a, b) in enumerate(zip(row, pose)):
                sheet.paste(a, (k * w, 0)); sheet.paste(b, (k * w, h))
            sheet.resize((sheet.width // 2, sheet.height // 2)).save(OUT / f"{lid}_sheet.jpg", quality=88)
        (OUT / "timings.json").write_text(json.dumps({"final": fin["id"], **timings}, indent=1), encoding="utf-8")
        log(f"timings: {json.dumps(timings)}")
    finally:
        if edge and getattr(edge, "proc", None):
            edge.close()
        app.close()
    return 0


def _open_edge(edge, app, st_id: str, n_objects: int) -> None:
    """C.Edge's start without waiting for mesh props."""
    import subprocess
    import urllib.request
    from edit_headed_check import CDP, EDGE
    url = f"http://127.0.0.1:{P.DEV}/?token={P.TOKEN}&port={P.PORT}&suite=stage"
    edge.proc = subprocess.Popen([EDGE, f"--remote-debugging-port={C.DBG}", f"--user-data-dir={app.tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
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


def finish() -> int:
    """PS5d–e on the rig's final: each character layer matted (SAM 3), then the assembly (a CPU job) into the shot; a sheet and the clip."""
    timings = json.loads((OUT / "timings.json").read_text(encoding="utf-8"))
    fid = timings["final"]
    project = OUT / "project"
    app = P.App(project)
    try:
        f = P.api("GET", f"/finals/{fid}")
        for x in f["layers"]:
            if x["kind"] == "figure" and not (project / "finals" / fid / x["id"] / "matte").is_dir():
                t0 = time.time()
                j = P.wait_job(P.api("POST", f"/finals/{fid}/layers/{x['id']}/matte", {"text": "person"})["job_id"])
                timings[f"matte_{x['id']}_s"] = round(time.time() - t0, 1)
                log(f"{x['id']}: matte {j['status']} in {timings[f'matte_{x['id']}_s']} s")
        t0 = time.time()
        j = P.wait_job(P.api("POST", f"/finals/{fid}/assemble")["job_id"])
        timings["assemble_s"] = round(time.time() - t0, 1)
        if j["status"] != "done":
            print("assemble", j["status"], j.get("error"), j.get("log_tail", [])[-3:]); return 1
        f = P.api("GET", f"/finals/{fid}")
        timings["assembly"] = f["assembly"]
        clip = j["result"]["clip_id"]
        frames = sorted((project / "clips" / clip / "master").glob("*.png"))
        picks = [0, len(frames) // 3, 2 * len(frames) // 3, len(frames) - 1]
        ims = [Image.open(frames[i]).convert("RGB") for i in picks]
        w, h = ims[0].size
        sheet = Image.new("RGB", (w * 2, h * 2))
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % 2) * w, (k // 2) * h))
        sheet.save(OUT / "final_sheet.jpg", quality=90)
        (OUT / "final.mp4").write_bytes((project / "clips" / clip / "proxy.mp4").read_bytes())
        (OUT / "timings.json").write_text(json.dumps(timings, indent=1), encoding="utf-8")
        log(f"assembled {clip}: {len(frames)} frames in {timings['assemble_s']} s; {json.dumps(f['assembly'])}")
    finally:
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(finish() if sys.argv[1:] == ["finish"] else main())
