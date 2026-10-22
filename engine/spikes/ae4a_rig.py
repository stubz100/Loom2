"""AE4a rig (D118, proto01_animate 20 §6): the passes through the app on the real engine — the clean-up pass on Mara's layer and the creative
pass on the Room (the plate) of the PS5 rig's final, the takes recorded as the layers' sources, the composition's footage swapped on the
pinned EffectCraft (file.replaceFootage), a frame before and after each, the plate's source set back (Mara's take stays shown for the
author's look, doc 21 §4). A private orchestrator on its own state with the rig's project; one GPU job at a time (D97): the engine free.
Outputs under engine/spikes/out/ae4a/: before.png, after_<layer>.png, sheet.jpg, results.json, log.txt.

    orchestrator/.venv/Scripts/python.exe engine/spikes/ae4a_rig.py [--arms fig_m:cleanup:0.10,plate:creative:0.35]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):                                  # the job logs carry arrows: never let cp1252 stop the rig
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
from m1_acceptance import Orch  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ae4a"
PROJECT = ROOT / "engine" / "spikes" / "out" / "ps5" / "project"
FID = "fin_0f41f551"
PORT = 8794


def log(m: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
    print(line, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="fig_m:cleanup:0.10,plate:creative:0.35")
    a = ap.parse_args()
    arms = [(x.split(":")[0], x.split(":")[1], float(x.split(":")[2])) for x in a.arms.split(",") if x]
    OUT.mkdir(parents=True, exist_ok=True)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    o = Orch(state, PORT, PROJECT).start(timeout=180)
    results: dict = {}
    try:
        h = o.http
        f = h.get(f"/finals/{FID}").json()
        comp = h.get(f"/finals/{FID}/composition").json()
        log(f"final {f['name']} rev {f['revision']} · composition rev {comp['revision']} sources {comp.get('sources')} stale {comp.get('stale')}")

        def frame(t: float = 1.0) -> bytes:
            r = h.get(f"/finals/{FID}/composition/frame", params={"t": t, "side": 0}, timeout=120)
            r.raise_for_status()
            return r.content
        before = frame()
        (OUT / "before.png").write_bytes(before)
        cells: list[tuple[Path, str]] = [(OUT / "before.png", "before")]
        c1 = h.post(f"/finals/{FID}/composition/sync", timeout=300).json()        # a take landed before (an earlier run): the composition takes it first
        if c1.get("sources") != comp.get("sources"):
            after0 = frame()
            (OUT / "after_sync.png").write_bytes(after0)
            cells.append((OUT / "after_sync.png", "after sync"))
            log(f"sync: composition rev {c1.get('revision')} sources {c1.get('sources')}; frame changed {after0 != before}")
            results["sync"] = {"sources": c1.get("sources"), "comp_revision": c1.get("revision"), "changed": after0 != before}
            before = after0
        for lid, preset, strength in arms:
            t0 = time.time()
            r = h.post(f"/finals/{FID}/layers/{lid}/pass", json={"preset": preset, "strength": strength})
            if r.status_code != 200:
                log(f"{preset} on {lid}: refused {r.status_code} {r.text[:300]}")
                results[lid] = {"refused": r.text[:300]}
                continue
            jid = r.json()["job_id"]
            log(f"{preset} on {lid} at {strength:g}: job {jid} queued")
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=3600)
            wall = time.time() - t0
            log(f"  {j['status']} in {wall:.0f} s (job wall {j.get('wall_s')}); {j.get('error') or ''} {j.get('log_tail', [])[-2:]}")
            if j["status"] != "done":
                results[lid] = {"status": j["status"], "error": j.get("error"), "wall_s": round(wall)}
                continue
            f = h.get(f"/finals/{FID}").json()
            layer = next(x for x in f["layers"] if x["id"] == lid)
            c = h.post(f"/finals/{FID}/composition/sync", timeout=300).json()
            after = frame()
            p = OUT / f"after_{lid}.png"
            p.write_bytes(after)
            cells.append((p, f"{preset} {lid}"))
            log(f"  take {layer['source']} ({len(layer['takes'])} takes); composition rev {c.get('revision')} sources {c.get('sources')} stale {c.get('stale')}; frame changed {after != before}")
            results[lid] = {"take": layer["source"], "preset": preset, "strength": strength, "wall_s": round(wall), "job_wall_s": j.get("wall_s"),
                            "comp_revision": c.get("revision"), "sources": c.get("sources"), "changed": after != before}
            before = after
        # the plate back to its original frames (Mara's take stays shown for the author)
        if any(lid == "plate" and "take" in results.get("plate", {}) for lid, _, _ in arms):
            r = h.post(f"/finals/{FID}/layers/plate/source", json={"take": None}, timeout=300)
            log(f"plate back to the original: {r.status_code} composition rev {(r.json().get('composition') or {}).get('revision')}")
            results["plate_back"] = r.status_code
        # a sheet: the middle of each frame at 1:1
        if len(cells) > 1:
            w = 420
            im = Image.new("RGB", (w * len(cells), 480 + 18), (24, 24, 24))
            d = ImageDraw.Draw(im)
            for i, (p, label) in enumerate(cells):
                src = Image.open(p).convert("RGB")
                x0 = max(0, min(src.width - w, src.width // 2 - w // 2 - 120))
                im.paste(src.crop((x0, 0, x0 + w, 480)), (i * w, 18))
                d.text((i * w + 4, 2), label, fill=(230, 230, 230))
            im.save(OUT / "sheet.jpg", quality=90)
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        log(f"done: {json.dumps(results)[:600]}")
    finally:
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
