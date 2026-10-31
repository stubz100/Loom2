"""Spike E49b (M6; journal 2026-10-31 11:31): E49 again with the people placed — the stall front's crop refined with shoppers in profile
in front of the counters and nobody facing the camera (SA), then the plain Wan 2.2 I2V from it on two seeds (N1, N2), N1 continued
through the app's extend route (N1x, lead 1). The same copy, stretch, measures and preview as E49 (e49_crowd.py). Outputs under
engine/spikes/out/e49b/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e49b_crowd.py
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
import e49_crowd as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e49b"
START = (f"{e.STALLS}; shoppers with bags and baskets walking left and right in front of the counters, seen in profile, stallholders in "
         "aprons behind the counters, nobody facing the camera, seen from the side at eye level, even light, no perspective")
MOTION = ("shoppers walk left and right along the counters, seen in profile, stallholders serve behind the counters; nobody walks toward "
          "the camera; a static locked-off camera")


def main() -> int:
    from m1_acceptance import port_busy
    if port_busy(8188) or port_busy(e.PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "arms": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{e.PORT}", headers={"X-Loom-Token": e.TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(e.PORT), "--state",
                             str(e.STATE), "--project", str(e.PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": e.TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def wait(jid: str, arm: str, t0: float) -> dict:
        while True:
            j = api.get(f"/jobs/{jid}").json()
            if j["status"] not in ("queued", "running", "staged"):
                break
            time.sleep(4)
        results["arms"][arm] = {"job": jid, "status": j["status"], "seconds": round(time.time() - t0), "error": j.get("error"),
                                "result": {k: v for k, v in (j.get("result") or {}).items() if k in ("asset_ids", "clip_id")}}
        print(f"{arm}: {results['arms'][arm]}", flush=True)
        if j["status"] != "done":
            raise RuntimeError(f"{arm} {j['status']}: {j.get('error')}")
        return j["result"]

    def run(recipe: dict, arm: str) -> dict:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": recipe})
        r.raise_for_status()
        return wait(r.json()["jobs"][0]["id"], arm, t0)

    def frames(clip_id: str) -> list[Image.Image]:
        rec = json.loads((e.PROJECT / "clips" / clip_id / "clip.json").read_text(encoding="utf-8"))
        return [Image.open(p).convert("RGB") for p in sorted((e.PROJECT / rec["master_dir"]).glob("*.png"))]

    clips: dict[str, list[Image.Image]] = {}
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        crop_id = api.post("/assets/import", json={"paths": [str(e.OUT / "crop.png")]}).json()["items"][0]["id"]
        doc = api.post("/documents", json={"from_asset": crop_id, "name": "E49b SA"}).json()["id"]
        run({"kind": "i2i", "document_id": doc, "source": "visible", "prompt_text": START, "strength": 0.6, "seeds": [21]}, "SA")
        r = api.post(f"/documents/{doc}/flatten", json={"to_catalogue": True, "name": "E49b SA"})
        r.raise_for_status()
        sa = r.json()["asset"]["id"]
        from loom2.catalogue import Catalogue
        from loom2.workspace import Workspace
        cat = Catalogue(Workspace(e.PROJECT))
        Image.open(cat.abs_path(cat.get(sa))).convert("RGB").save(OUT / "start_SA.png")
        base = {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "start_asset": sa, "prompt_text": MOTION, "frames": e.FRAMES, "fps": e.FPS,
                "width": e.W, "height": e.H, "preset": "draft"}
        ids = {}
        for arm, seed in (("N1", 21), ("N2", 22)):
            res = run({**base, "seeds": [seed]}, arm)
            ids[arm] = res["clip_id"]
            clips[arm] = frames(res["clip_id"])
        t0 = time.time()
        r = api.post(f"/clips/{ids['N1']}/extend", json={})
        r.raise_for_status()
        res = wait(r.json()["job_id"], "N1x", t0)
        clips["N1x"] = frames(res["clip_id"])
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    for arm, fr in clips.items():
        results["arms"][arm].update(e.measure(fr))
    if "N1" in clips and "N1x" in clips:
        dx, dy = e.shift(e.gray(clips["N1"][-1]), e.gray(clips["N1x"][0]))
        results["join_px"] = [round(dx, 1), round(dy, 1)]
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    rows = [(a, clips[a]) for a in ("N1", "N2", "N1x") if a in clips]
    tw, th = 544, 240
    sheet = Image.new("RGB", (tw * 3, (th + 18) * len(rows)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (arm, fr) in enumerate(rows):
        for j, k in enumerate((0, len(fr) // 2, len(fr) - 1)):
            sheet.paste(fr[k].resize((tw, th)), (j * tw, i * (th + 18) + 18))
            dr.text((j * tw + 4, i * (th + 18) + 3), f"{arm} frame {k} · drift max {results['arms'][arm]['drift_max_px']} px · zoom {results['arms'][arm]['zoom_last']}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=86)
    people = Image.new("RGB", (394 * 3, 166 * 4), (20, 20, 20))
    dp = ImageDraw.Draw(people)
    for r_, arm in enumerate(("N1", "N2")):
        if arm not in clips:
            continue
        for j, k in enumerate((0, 16, 32, 48, 64, 80)):
            x, y = (j % 3) * 394, (r_ * 2 + j // 3) * 166
            people.paste(clips[arm][k].crop((300, 120, 1088, 420)).resize((394, 150)), (x, y + 16))
            dp.text((x + 4, y + 2), f"{arm} frame {k}", fill=(230, 230, 230))
    people.save(OUT / "people.jpg", quality=88)
    for arm in ("N1", "N2"):
        if arm in clips:
            pv = e.preview(clips[arm], OUT / f"preview_{arm}.mp4")
            for k in (0, 32, 64):
                pv[k].save(OUT / f"preview_{arm}_{k}.png")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("seconds", "drift_max_px", "zoom_last", "status")} for k, v in results["arms"].items()}), flush=True)
    print("join", results.get("join_px"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
