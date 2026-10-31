"""Spike E49c (M6; journal 2026-10-31 11:53): the crowd clip as a loop — E49b's start (SA, read from N1's job on E47's copy) given as
the first and the last frame (Wan 2.2's first/last-frame mode, the plain model), two seeds (L1, L2). E49's measures, the loop's seam
(the last frame against the first), how far each sampled frame is from the first, and a preview of the shot's plate with the loop played
on the facade. Outputs under engine/spikes/out/e49c/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e49c_loop.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e49_crowd as e  # noqa: E402
from e49b_crowd import MOTION  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e49c"


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(8188) or port_busy(e.PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    prev = json.loads((ROOT / "engine" / "spikes" / "out" / "e49b" / "results.json").read_text(encoding="utf-8"))
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "arms": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{e.PORT}", headers={"X-Loom-Token": e.TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(e.PORT), "--state",
                             str(e.STATE), "--project", str(e.PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": e.TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    clips: dict[str, list[Image.Image]] = {}
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        start = api.get("/jobs/" + prev["arms"]["N1"]["job"]).json()["recipe"]["start_asset"]
        results["start_asset"] = start
        for arm, seed in (("L1", 31), ("L2", 32)):
            t0 = time.time()
            recipe = {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "start_asset": start, "end_asset": start, "prompt_text": MOTION,
                      "frames": e.FRAMES, "fps": e.FPS, "width": e.W, "height": e.H, "preset": "draft", "seeds": [seed]}
            r = api.post("/jobs", json={"recipe": recipe})
            r.raise_for_status()
            jid = r.json()["jobs"][0]["id"]
            while True:
                j = api.get(f"/jobs/{jid}").json()
                if j["status"] not in ("queued", "running", "staged"):
                    break
                time.sleep(4)
            results["arms"][arm] = {"job": jid, "status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"),
                                    "clip_id": (j.get("result") or {}).get("clip_id")}
            print(f"{arm}: {results['arms'][arm]}", flush=True)
            if j["status"] != "done":
                raise RuntimeError(f"{arm} {j['status']}: {j.get('error')}")
            rec = json.loads((e.PROJECT / "clips" / j["result"]["clip_id"] / "clip.json").read_text(encoding="utf-8"))
            clips[arm] = [Image.open(p).convert("RGB") for p in sorted((e.PROJECT / rec["master_dir"]).glob("*.png"))]
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    for arm, fr in clips.items():
        a, b = np.asarray(fr[0], dtype=np.float64), np.asarray(fr[-1], dtype=np.float64)
        change = [round(float(np.abs(np.asarray(fr[k], dtype=np.float64) - a).mean()), 1) for k in range(0, len(fr), 8)]
        results["arms"][arm].update(e.measure(fr), seam_mae=round(float(np.abs(a - b).mean()), 2), change_from_first=change)
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    people = Image.new("RGB", (394 * 3, 166 * 2 * max(1, len(clips))), (20, 20, 20))
    dp = ImageDraw.Draw(people)
    for r_, (arm, fr) in enumerate(clips.items()):
        for j, k in enumerate((0, 16, 32, 48, 64, 80)):
            x, y = (j % 3) * 394, (r_ * 2 + j // 3) * 166
            people.paste(fr[k].crop((300, 120, 1088, 420)).resize((394, 150)), (x, y + 16))
            dp.text((x + 4, y + 2), f"{arm} frame {k} · seam {results['arms'][arm]['seam_mae']}", fill=(230, 230, 230))
    people.save(OUT / "people.jpg", quality=88)
    for arm, fr in clips.items():
        pv = e.preview(fr, OUT / f"preview_{arm}.mp4")
        for k in (0, 32, 64):
            pv[k].save(OUT / f"preview_{arm}_{k}.png")
    keys = ("seconds", "drift_max_px", "zoom_last", "seam_mae", "change_from_first")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in keys} for k, v in results["arms"].items()}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
