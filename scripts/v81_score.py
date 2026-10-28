"""V81's pose score, after the fact: PCK@0.1 of saved Wan Animate clips (480×848) against E11's walk_dolly guide made portrait the way
`v81_final_size_rig.py --portrait-guide` makes it (scaled to the clip's height, cropped to its width — the cover mapping, which is also
how a landscape guide lands in a portrait clip). SDPose runs on the orchestrator's engine (started here, nothing else on the GPU).

    orchestrator/.venv/Scripts/python.exe scripts/v81_score.py <clip master dir> [<clip master dir> ...]

Results: engine/spikes/out/v81/pck.json — per clip the PCK, the sampled frames' people counts and mean distances.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

PORT = 8773
TOKEN = "v81score"
OUT = ROOT / "engine" / "spikes" / "out" / "v81"
E11 = ROOT / "engine" / "spikes" / "out" / "e11" / "walk_dolly"


def api(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]]
    if not dirs:
        raise SystemExit("give the clips' master folders")
    from m1_acceptance import port_busy
    from loom2.config import AppState
    from e10_stage import pck, sdpose_graph
    from e12_angles import Engine
    if port_busy(8188):
        raise SystemExit("the engine port is busy — one GPU job at a time (rule 10)")
    tmp = Path(tempfile.mkdtemp(prefix="loom2-v81s-"))
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [],
                                             "variant": "full", "engine": {"port": 8188}})
    log = (OUT / "score.log").open("a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state"), "--parent-pid", str(os.getpid())],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}, stdout=log, stderr=subprocess.STDOUT)
    results: dict = {"guide": "E11 walk_dolly scaled to the height, cropped to the width", "clips": {}}
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "V81s", "size_cap_gb": 20})
        api("POST", "/engine/start")
        t1 = time.time()
        while time.time() - t1 < 300:
            if api("GET", "/engine").get("running") and api("GET", "/engine").get("responding", True):
                break
            time.sleep(2.0)
        kp = json.loads((E11 / "keypoints.json").read_text(encoding="utf-8"))
        gw, gh = kp["size"]
        eng = Engine("127.0.0.1:8188")
        for d in dirs:
            frames = sorted(d.glob("*.png"))
            W, H = Image.open(frames[0]).size
            s = H / gh
            ox = (gw * s - W) / 2
            rows = []
            hit = tot = 0
            for idx in range(0, len(frames), 10):
                hp, _, _ = eng.run(sdpose_graph(eng.upload(frames[idx])))
                people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                figs = [[[x_ * s - ox, y_ * s, (v if 0 <= x_ * s - ox < W else 0)] for x_, y_, v in fig] for fig in kp["frames"][idx]]
                h_, t_ = pck(figs, people)
                hit += h_
                tot += t_
                g = np.array(figs[0], dtype=float)
                vis = g[:, 2] > 0
                span = float(max(np.ptp(g[vis, 0]), np.ptp(g[vis, 1]))) if vis.sum() else 0.0
                det = [np.array(p["pose_keypoints_2d"], dtype=float).reshape(-1, 3) for p in people]
                dist = None
                if det and vis.sum():
                    p = det[0]
                    ok = vis & (p[:, 2] >= 0.3)
                    dist = float(np.linalg.norm(p[ok, :2] - g[ok, :2], axis=1).mean()) if ok.sum() else None
                rows.append({"frame": idx, "people": len(people), "hit": h_, "of": t_, "guide_span_px": round(span, 1), "mean_dist_px": None if dist is None else round(dist, 1),
                             "guide_centre": [round(float(g[vis, 0].mean()), 1), round(float(g[vis, 1].mean()), 1)] if vis.sum() else None,
                             "person_centre": [round(float(det[0][det[0][:, 2] >= 0.3, 0].mean()), 1), round(float(det[0][det[0][:, 2] >= 0.3, 1].mean()), 1)] if det and (det[0][:, 2] >= 0.3).any() else None})
            results["clips"][d.parent.name] = {"frames": len(frames), "size": [W, H], "pck": round(hit / tot, 3) if tot else None, "rows": rows}
            print(d.parent.name, "PCK", results["clips"][d.parent.name]["pck"], [(r["frame"], r["people"], r["mean_dist_px"]) for r in rows], flush=True)
        (OUT / "pck.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
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
