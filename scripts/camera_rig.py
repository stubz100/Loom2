"""D156's rig: the camera move as Animate runs it — through the app (a temporary orchestrator, the real engine on 8188): the bench's alley
board as the start image, one Draft clip on the camera model with Pan Left (speed 1), the finisher's tone match on the way out. The clip's
master frames are read back: the pan by phase correlation (E41's measure), the first frame's distance from the start image (the match),
the seconds and the peak VRAM.

Bars: the job done with a clip; the pan the right way by ≥ 5 % of the width with ≥ 70 % of the pairs agreeing; the first frame within
MAE 12 of the start image (E41's lifted 17 matched back); peak ≤ 15.5 GB; ≤ 300 s.

    orchestrator/.venv/Scripts/python.exe scripts/camera_rig.py [--move pan_left] [--speed 1.0]

Results: engine/spikes/out/camera/results.json, sheet.jpg. One GPU job at a time (rule 10).
"""
from __future__ import annotations

import argparse
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
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]

PORT = 8783
TOKEN = "cameratoken"
OUT = ROOT / "engine" / "spikes" / "out" / "camera"
BOARD = next((ROOT / "bench" / "i2v" / "frames").glob("alley-rain_s*.png"))
PROMPT = "she stands still in the light rain holding the brass compass, looking at the viewer, neon signs flicker, rain falls softly"
BAR_SHARE, BAR_AGREE, BAR_MAE, BAR_PEAK_GB, BAR_S = 0.05, 0.7, 12.0, 15.5, 300.0


def api(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def wait_job(jid: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(2.0)
    raise TimeoutError(jid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--move", default="pan_left")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    import cr_acceptance as cr
    from e41_camera import EXPECT, measure, verdict
    from m1_acceptance import port_busy
    from loom2.config import AppState
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-camera-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "move": a.move, "speed": a.speed, "failures": []}
    vram = cr.VramSampler()

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "Camera", "size_cap_gb": 40})
        caps = api("GET", "/capabilities")
        cam = next((i for i, m in caps["i2v"]["models"].items() if m["recipes"].get("camera")), None)
        results["model"] = cam
        check(bool(cam) and caps["i2v"]["models"][cam]["health"] != "missing", f"the camera model is offered with its weights ({cam}: {caps['i2v']['models'].get(cam, {}).get('health')})")
        check(caps["defaults"]["i2v"] != cam, f"the plain model stays the default ({caps['defaults']['i2v']})")
        sid = api("POST", "/assets/import", {"paths": [str(BOARD)]})["items"][0]["id"]
        recipe = {"kind": "i2v", "model_id": cam, "start_asset": sid, "prompt_text": PROMPT, "frames": 81, "fps": 16, "width": 832, "height": 480, "preset": "draft", "seeds": [20261028],
                  "camera": {"move": a.move, "speed": a.speed}}
        prev = api("POST", "/recipes/preview", {"recipe": recipe})
        results["preview"] = prev.get("params") or prev
        vram.mark()
        t1 = time.time()
        job = api("POST", "/jobs", {"recipe": recipe})["jobs"][0]
        j = wait_job(job["id"])
        peak = vram.window()
        results["job"] = {"status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "peak_gb": peak, "error": j.get("error"), "log_tail": (j.get("log_tail") or [])[-4:], "result": j.get("result")}
        check(j["status"] == "done" and bool((j.get("result") or {}).get("clip_id")), f"the camera clip is done ({j['status']} in {j.get('wall_s')} s, peak {peak} GB) {j.get('error') or ''}")
        clip_id = (j.get("result") or {}).get("clip_id")
        if clip_id:
            rec = api("GET", f"/clips/{clip_id}")
            master = tmp / "proj" / rec["master_path"] if rec.get("master_path") else None
            frames = sorted(master.glob("*.png")) if master and master.is_dir() else sorted((tmp / "proj" / "clips" / clip_id).rglob("*.png"))
            results["frames"] = len(frames)
            tm = (rec.get("params") or {}).get("compiled", {}).get("tone_match") or (rec.get("params") or {}).get("tone_match")
            results["tone_match"] = tm
            if frames:
                m = measure(frames, Image.open(BOARD).convert("RGB"))
                results["measure"] = {k: v for k, v in m.items() if k != "pair_dx"}
                ok, text = verdict({"pan_left": "Pan Left", "pan_right": "Pan Right", "pan_up": "Pan Up", "pan_down": "Pan Down", "zoom_in": "Zoom In", "zoom_out": "Zoom Out", "static": "Static"}.get(a.move, a.move), m)
                check(ok, f"the clip moves as told — {text}")
                check(m["first_mae"] <= BAR_MAE, f"the first frame keeps the start image after the tone match (MAE {m['first_mae']} ≤ {BAR_MAE:g}; the finisher: {tm})")
                tiles = [Image.open(BOARD).convert("RGB").resize((416, 240))] + [Image.open(frames[i]).convert("RGB").resize((416, 240)) for i in (0, len(frames) // 2, len(frames) - 1)]
                sheet = Image.new("RGB", (4 * 422, 258), (24, 24, 24)); dr = ImageDraw.Draw(sheet)
                for i, (lbl, im) in enumerate(zip(["start image", "frame 0 (matched)", "middle", "last"], tiles)):
                    sheet.paste(im, (i * 422, 18)); dr.text((i * 422 + 3, 3), lbl, fill=(230, 230, 230))
                sheet.save(OUT / "sheet.jpg", quality=90)
            else:
                check(False, "no master frames found")
        check(peak <= BAR_PEAK_GB, f"peak VRAM ≤ {BAR_PEAK_GB} GB ({peak})")
        check(bool(j.get("wall_s")) and j["wall_s"] <= BAR_S, f"the clip inside {BAR_S:g} s ({j.get('wall_s')} s)")
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"{len(results['failures'])} failure(s) → {OUT / 'results.json'}", flush=True)
        return 1 if results["failures"] else 0
    finally:
        vram.stop = True
        try:
            api("POST", "/engine/stop")
            api("POST", "/shutdown")
            time.sleep(1.5)
        except Exception:  # noqa: BLE001
            pass
        if proc.poll() is None:
            proc.kill()
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
