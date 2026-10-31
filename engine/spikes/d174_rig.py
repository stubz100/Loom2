"""D174's acceptance on the rig (journal 2026-10-31 16:58): two walkers' segments on the market walk's right stall front through the app's
own route (POST …/set/walkers: 3.2–8.8 m and 8.8–14.4 m, each its own loop), on E47's copy, alone on the GPU — each segment's steps and
seconds, the walkers kept and dropped; a sheet of each packed clip's colour and mask. The final and Clay are checked in the app afterwards.
Outputs under engine/spikes/out/d174/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d174_rig.py [--e53]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PID, PROJECT, STATE, VID  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / ("d174_e53" if "--e53" in sys.argv else "d174")
PORT, TOKEN = 8766, "devtoken"
FACE = "facade_right"
SEGMENTS = ((3.2, 8.8), (8.8, 14.4))
SEGMENTS_E53 = ((3.2, 8.8),)                      # after E53: one segment through the product path, the earlier ones removed first


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
    res: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "segments": []}

    def face() -> dict:
        p = api.get(f"/story/profiles/{PID}").json()
        return next(f for f in next(v for v in p["versions"] if v["id"] == VID)["place_set"]["faces"] if f["id"] == FACE)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        segments = SEGMENTS
        if "--e53" in sys.argv:                                                  # the walkers' start painted into places (E53, experimental)
            segments = SEGMENTS_E53
            for w_ in face()["walkers"]:
                api.delete(f"/story/profiles/{PID}/versions/{VID}/set/walkers/{FACE}/{w_['id']}").raise_for_status()
        for a, b in segments:
            done = next((w for w in face()["walkers"] if w["from_m"] == a and w["to_m"] == b and w["status"] == "done"), None)
            if done:                                                             # made by an earlier run of this script
                res["segments"].append({"from_m": a, "to_m": b, "segment": done, "earlier": True})
                print("already:", json.dumps(done)[:300], flush=True)
                continue
            t0 = time.time()
            r = api.post(f"/story/profiles/{PID}/versions/{VID}/set/walkers", json={"face": FACE, "from_m": a, "to_m": b})
            print("walkers:", r.status_code, r.text[:200], flush=True)
            r.raise_for_status()
            start_job = r.json()["job_id"]
            seg_id = next(w["id"] for w in face()["walkers"] if w["job_id"] == start_job)
            while True:
                seg = next(w for w in face()["walkers"] if w["id"] == seg_id)
                if seg["status"] != "making":
                    break
                time.sleep(6)
            jobs = [j for j in api.get("/jobs").json()["items"] if (((j.get("origin") or {}).get("payload")) or {}).get("layer") == seg_id]
            row = {"from_m": a, "to_m": b, "seconds": round(time.time() - t0), "segment": seg,
                   "steps": [(j["recipe"]["kind"], j["status"], j.get("wall_s")) for j in jobs], "logs": [x for j in jobs for x in j.get("log_tail", [])[-2:]]}
            res["segments"].append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "logs"})[:900], flush=True)
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    rows = []
    for row in res["segments"]:
        seg = row["segment"]
        if seg.get("status") != "done":
            continue
        packed = next((json.loads(c.read_text(encoding="utf-8")) for c in (PROJECT / "clips").glob("*/clip.json")
                       if json.loads(c.read_text(encoding="utf-8")).get("asset_id") == seg["asset_id"]), None)
        if packed:
            fr = sorted((PROJECT / packed["master_dir"]).glob("*.png"))
            rows.append((f"{seg['from_m']}–{seg['to_m']} m · {seg['kept']} kept · {seg['dropped']} dropped", [Image.open(fr[k]).convert("RGB") for k in (0, 40)]))
    if rows:
        W = 1200
        sheet = Image.new("RGB", (W, 330 * len(rows) * 2), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        y = 0
        for label, ims in rows:
            for k, im in zip((0, 40), ims):
                d.text((4, y + 2), f"{label} · frame {k} (colour | mask)", fill=(230, 230, 230))
                sheet.paste(im.resize((W, round(W * im.height / im.width))), (0, y + 18))
                y += 330
        sheet.save(OUT / "packed.jpg", quality=86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
