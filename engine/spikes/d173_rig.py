"""D173's acceptance on the rig (journal 2026-10-31 15:07): the market walk's right stall front gets a crowd through the app's own route
(POST …/set/crowd, 3.2–14.4 m — the stretch the shot's v2 sees), on E47's copy, alone on the GPU: the start's refine, then the loop; the
face's crowd, the loop's seam and largest step (from the clip's record), the seconds. The final and Clay's viewport are checked in the app
afterwards (no engine job). Outputs under engine/spikes/out/d173/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d173_rig.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PID, PROJECT, STATE, VID  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "d173"
PORT, TOKEN = 8766, "devtoken"
FACE, FROM, TO = "facade_right", 3.2, 14.4
WORDS = ("shoppers with bags and baskets walking left and right in front of the counters, seen in profile, stallholders in aprons behind "
         "the counters, nobody facing the camera")


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(STATE), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    res: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "face": FACE, "from_m": FROM, "to_m": TO}

    def wait(jid: str) -> dict:
        while True:
            j = api.get(f"/jobs/{jid}").json()
            if j["status"] not in ("queued", "running", "staged"):
                return j
            time.sleep(4)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        t0 = time.time()
        r = api.post(f"/story/profiles/{PID}/versions/{VID}/set/crowd", json={"face": FACE, "from_m": FROM, "to_m": TO, "words": WORDS})
        print("crowd:", r.status_code, r.text[:300], flush=True)
        r.raise_for_status()
        j1 = wait(r.json()["job_id"])
        res["start"] = {"job": j1["id"], "status": j1["status"], "seconds": round(time.time() - t0), "error": j1.get("error"), "log": j1.get("log_tail", [])[-3:]}
        print("start:", res["start"], flush=True)
        nxt = (j1.get("result") or {}).get("next_job_id")
        if nxt:
            t1 = time.time()
            j2 = wait(nxt)
            res["loop"] = {"job": j2["id"], "status": j2["status"], "seconds": round(time.time() - t1), "error": j2.get("error"), "log": j2.get("log_tail", [])[-4:],
                           "recipe": {k: j2["recipe"].get(k) for k in ("model_id", "width", "height", "frames", "fps", "seeds", "prompt_text")}}
            print("loop:", res["loop"], flush=True)
        p = api.get(f"/story/profiles/{PID}").json()
        face = next(f for f in next(v for v in p["versions"] if v["id"] == VID)["place_set"]["faces"] if f["id"] == FACE)
        res["crowd"] = face["crowd"]
        print("crowd now:", face["crowd"], flush=True)
        if face["crowd"] and face["crowd"].get("clip_id"):
            rec = json.loads((PROJECT / "clips" / face["crowd"]["clip_id"] / "clip.json").read_text(encoding="utf-8"))
            res["tone"] = (rec.get("params") or {}).get("compiled", {}).get("tone_match")
            fr = sorted((PROJECT / rec["master_dir"]).glob("*.png"))
            for k in (0, 20, 40, 60):
                Image.open(fr[k]).convert("RGB").save(OUT / f"loop_{k}.png")
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({"tone": res.get("tone"), "start_s": res.get("start", {}).get("seconds"), "loop_s": res.get("loop", {}).get("seconds")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
