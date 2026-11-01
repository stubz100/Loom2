"""D180's rig, again after its first run (journal 2026-11-01 06:26): the kept ferry is what the clicks touch (`place_things.clicked`) — the
first keep's box was 2.6× too wide from SAM 3's specks over the sky. On the same copy, alone on the GPU: find, keep as "Ferry", its model,
the first thing removed. Outputs beside the first run's (engine/spikes/out/d180, `results2.json`).

    orchestrator/.venv/Scripts/python.exe engine/spikes/d180_rig2.py
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path


from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d180_rig as r  # noqa: E402


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(r.PORT) or port_busy(8188):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    res: dict = {}
    proc, api = r.orchestrator(r.OUT / "orchestrator.log")
    try:
        pier = next(p for p in api.get("/story/profiles").json()["items"] if p["name"] == "Harbour pier")
        pid, vid = pier["id"], pier["current"]
        base = f"/story/profiles/{pid}/versions/{vid}/set/things"
        old = [t["id"] for t in next(v for v in pier["versions"] if v["id"] == vid)["place_set"]["things"]]
        f = api.post(f"{base}/find", json={"points": r.POINTS}).json()
        j = r.wait(api, f["job_id"])
        res["find"] = j["status"]
        p = api.post(base, json={"name": "Ferry", "points": r.POINTS}).json()
        ps = next(v for v in p["versions"] if v["id"] == vid)["place_set"]
        thing, cam = ps["things"][-1], ps["sources"][0]["camera"]
        res["thing"] = {k: thing[k] for k in ("id", "base", "width_m", "height_m", "yaw_deg", "card_asset_id", "mask_asset_id")}
        res["distance_m"] = round(math.dist(thing["base"], cam["pos"]), 1)
        print("kept:", res["thing"], "distance:", res["distance_m"], flush=True)
        t1 = time.time()
        j = r.wait(api, api.post(f"{base}/{thing['id']}/model").json()["job_id"])
        res["model"] = {"status": j["status"], "seconds": round(time.time() - t1), "assets": (j.get("result") or {}).get("asset_ids")}
        for tid in old:
            api.delete(f"{base}/{tid}")
        p = api.get(f"/story/profiles/{pid}").json()
        res["things"] = [(t["name"], t["mesh_asset_id"]) for t in next(v for v in p["versions"] if v["id"] == vid)["place_set"]["things"]]
        (r.OUT / "card2.png").write_bytes(api.get(f"/assets/{thing['card_asset_id']}/file").content)
        api.post("/engine/stop")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            proc.kill()
    (r.OUT / "results2.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    c = Image.open(r.OUT / "card2.png")
    res["card_px"] = list(c.size)
    print(json.dumps(res), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
