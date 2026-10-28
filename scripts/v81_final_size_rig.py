"""V81 (review 2026-10-27, journal 08:21): the final's layers at the project's aspect, on the rig. `finalSize()` used to be the pose-driven
model's own 832×480 whatever the project (a 9:16 project's final came out landscape); it is the model's short side on its 16-grid at the
project's aspect now — 848×480 for 16:9 (the CN rig ran it, 2026-10-15), 480×848 for 9:16. This runs the portrait case through the
queue as the CN rig runs the landscape one: E11's walk_dolly pose guide uploaded on a stage, the hero (bench/angles/07.jpg) as the
character, one Wan Animate `i2v` job at 480×848 — its wall time, VRAM and PCK@0.1 against the guide (cover-fitted, as the clip pads).

    orchestrator/.venv/Scripts/python.exe scripts/v81_final_size_rig.py [--size 480x848]

Results: engine/spikes/out/v81/results.json, the clip beside it and a sheet of its first, middle and last frames. One GPU job at a time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
from PIL import Image  # noqa: E402

PORT = 8772
TOKEN = "v81token"
OUT = ROOT / "engine" / "spikes" / "out" / "v81"
E11 = ROOT / "engine" / "spikes" / "out" / "e11" / "walk_dolly"
HERO = ROOT / "bench" / "angles" / "07.jpg"


def api(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def put_blob(data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/blobs/{sha}", data=data, method="PUT", headers={"X-Loom-Token": TOKEN})
    urllib.request.urlopen(req, timeout=60).read()
    return sha


def wait_job(jid: str, timeout: float = 3600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == jid), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        if api("GET", "/queue").get("paused"):
            raise RuntimeError(f"the queue is paused while {jid} waits")
        time.sleep(2.0)
    raise TimeoutError(jid)


def guide_frames(tmp: Path, n: int) -> list[bytes]:
    pngs = sorted((E11 / "pose").glob("*.png")) if (E11 / "pose").is_dir() else []
    if pngs:
        return [p.read_bytes() for p in pngs[:n]]
    import av
    out = []
    with av.open(str(E11 / "pose.mp4")) as c:
        for i, fr in enumerate(c.decode(video=0)):
            if i >= n:
                break
            buf = tmp / f"pose_{i:03d}.png"
            fr.to_image().save(buf)
            out.append(buf.read_bytes())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="480x848", help="WxH of the clip (the portrait case by default)")
    ap.add_argument("--portrait-guide", action="store_true", help="the guide made portrait first: E11's frames scaled to the clip's height and cropped to its "
                    "width (cover), the keypoints moved the same way — a 9:16 stage's own pose pass, in effect; the PCK is then measured 1:1")
    a = ap.parse_args()
    W, H = (int(x) for x in a.size.lower().split("x"))
    from m1_acceptance import port_busy
    from loom2.config import AppState
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="loom2-v81-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [],
                                             "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"size": [W, H]}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "V81", "size_cap_gb": 40})
        caps = api("GET", "/capabilities")["stage"].get("animate")
        if not caps or caps["health"] == "missing":
            raise SystemExit(f"the Stage's animate method is not offered with its weights: {caps}")
        results["model"] = caps["model_id"]
        hero = api("POST", "/assets/import", {"paths": [str(HERO)]})["items"][0]["id"]
        st = api("POST", "/stages", {"name": "V81 walk"})
        cam = st["cameras"][0]["id"]
        kp = json.loads((E11 / "keypoints.json").read_text(encoding="utf-8"))
        n = min(int(caps["frames_max"] or 77), len(kp["frames"]))
        frames_b = guide_frames(tmp, n)
        gw, gh = kp["size"]
        keypoints = kp["frames"][:n]
        results["guide"] = "landscape"
        if a.portrait_guide:                                                   # the guide as a 9:16 stage would render it: scaled to the clip's height, the sides cropped
            import io
            s = H / gh
            ox = (gw * s - W) / 2

            def portrait(b: bytes) -> bytes:
                with Image.open(io.BytesIO(b)) as im:
                    im = im.convert("RGB").resize((round(gw * s), H), Image.LANCZOS).crop((round(ox), 0, round(ox) + W, H))
                    buf = io.BytesIO()
                    im.save(buf, "PNG")
                    return buf.getvalue()
            frames_b = [portrait(b) for b in frames_b]
            keypoints = [[[[x_ * s - ox, y_ * s, (v if 0 <= x_ * s - ox < W else 0)] for x_, y_, v in fig] for fig in fr] for fr in keypoints]
            gw, gh = W, H
            results["guide"] = "portrait (E11 scaled to the height, cropped to the width)"
        shas = [put_blob(b) for b in frames_b]
        doc = api("POST", f"/stages/{st['id']}/guide", {"camera_id": cam, "revision": st["revision"], "kind": "pose", "fps": int(kp.get("fps") or 24), "size": {"w": gw, "h": gh},
                                                         "range": {"start": 0, "end": n - 1}, "frames": shas, "keypoints": keypoints})
        kp = {**kp, "size": [gw, gh], "frames": keypoints}
        entry = next(x for x in doc["passes"] if x["camera_id"] == cam)
        guide = entry["guides"]["pose"]
        recipe = {"kind": "i2v", "model_id": caps["model_id"], "start_asset": hero, "prompt_text": "the character walks towards the camera through a bright empty room, steady camera",
                  "frames": n, "fps": 24, "width": W, "height": H, "preset": "draft", "guide": {"asset_id": guide["asset_id"], "kind": "pose"}}
        t1 = time.time()
        job = api("POST", "/jobs", {"recipe": recipe, "origin": {"suite": "stage", "surface": "clip", "ref": st["id"], "payload": {"camera_id": cam}}})["jobs"][0]
        j = wait_job(job["id"])
        results["job"] = {"status": j["status"], "wall_s": j.get("wall_s"), "elapsed_s": round(time.time() - t1, 1), "error": j.get("error"),
                          "node_times": j.get("node_times"), "log_tail": (j.get("log_tail") or [])[-4:], "timings": j.get("timings")}
        print(f"job {j['status']}: wall {j.get('wall_s')} s · {results['job']['log_tail']}", flush=True)
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        if j["status"] != "done":
            return 1
        clip_id = j["result"]["clip_id"]
        asset = api("GET", f"/assets/{j['result']['asset_ids'][0]}")
        shutil.copy2(tmp / "proj" / asset["path"], OUT / f"walk_{W}x{H}.mp4")
        frames = sorted((tmp / "proj" / "clips" / clip_id / "master").glob("*.png"))
        fw, fh = Image.open(frames[0]).size
        results["clip"] = {"frames": len(frames), "size": [fw, fh], "asset": asset["id"]}
        # the sheet: first, middle, last
        picks = [frames[0], frames[len(frames) // 2], frames[-1]]
        ims = [Image.open(p).convert("RGB") for p in picks]
        sheet = Image.new("RGB", (sum(i.width for i in ims) + 20, max(i.height for i in ims)), (24, 24, 24))
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width + 10
        sheet.save(OUT / f"sheet_{W}x{H}.jpg", quality=88)
        # PCK against the guide, fitted inside the clip as the pipeline fits the reference and the guide (`pad_reference`: never cropped —
        # a landscape guide in a portrait clip sits in a band, the bars above and below)
        try:
            from e10_stage import pck, sdpose_graph
            from e12_angles import Engine
            eng = Engine("127.0.0.1:8188")
            s = min(fw / gw, fh / gh)
            ox, oy = (fw - gw * s) / 2, (fh - gh * s) / 2
            hit = tot = 0
            for idx in range(0, len(frames), 10):
                hp, _, _ = eng.run(sdpose_graph(eng.upload(frames[idx])))
                people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                figs = [[[x_ * s + ox, y_ * s + oy, v] for x_, y_, v in fig] for fig in kp["frames"][idx]]
                h_, t_ = pck(figs, people)
                hit += h_
                tot += t_
            results["pck"] = round(hit / tot, 3) if tot else None
        except Exception as e:  # noqa: BLE001
            results["pck"] = None
            results["pck_error"] = str(e)[:300]
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(json.dumps({k: results[k] for k in ("size", "clip", "pck") if k in results}), flush=True)
        return 0
    finally:
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
