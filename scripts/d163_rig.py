"""D163 rig (E43's follow-up, proto01_UI2 12): a character layer performed in its own window, through the app's own route, on the GPU, alone.

On the E43 copy of the walkthrough's project (F:/loom2-projects/_e43/last-ferry-copy), whose finals were made before D163 (their windows
are decided at the run):
- T: Arrival's Final 2, Tomas (W46, 50 px): `POST /finals/{fid}/layers/{lid}/run`, then the assembly;
- I: The seal's Final 4, Ines (W58, cut by the frame), all 169 frames (3 batches), then the assembly.

Bars (journal, set before the run): each run replies a window (× ≥ 1); the layer is done with its matte checked — it strays on ≤ 5 % of its
frames; Tomas's clip keeps his face (identity ≥ 0.35 where measured); both assemble.

    orchestrator/.venv/Scripts/python.exe scripts/d163_rig.py [--parts T,I] [--state <scratch state dir>]

The orchestrator (8766, the copy as its project) is started here and stopped at the end; the engine starts with the first job and is
stopped too. One GPU job at a time (rule 10): the queue runs them in turn.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
PROJECT = Path("F:/loom2-projects/_e43/last-ferry-copy")
PORT, TOKEN = 8766, "devtoken"
OUT = ROOT / "engine" / "spikes" / "out" / "d163"
PARTS = {"T": ("Arrival · Tomas (W46)", "fin_b608e3d8", "fig_04370fc0"), "I": ("The seal · Ines (W58)", "fin_47a428a0", "fig_q98kue1v")}
BAR_STRAYS, BAR_ID = 0.05, 0.35


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="T,I")
    ap.add_argument("--state", default=str(Path(os.environ.get("TEMP", ".")) / "loom2-d163-state"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from m1_acceptance import port_busy
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "project": str(PROJECT), "parts": {}, "failures": []}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    def save() -> None:
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state", a.state, "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)
    rows: list[tuple[str, list[Image.Image]]] = []
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)

        def layer_of(fid: str, lid: str) -> dict:
            return next(x for x in api.get(f"/finals/{fid}").json()["layers"] if x["id"] == lid)

        def job(jid: str) -> dict:
            return api.get(f"/jobs/{jid}").json()

        for key in [p.strip() for p in a.parts.split(",") if p.strip() in PARTS]:
            name, fid, lid = PARTS[key]
            t0 = time.time()
            r = api.post(f"/finals/{fid}/layers/{lid}/run", json={})
            r.raise_for_status()
            reply = r.json()
            print(f"{key} {name}: {reply}", flush=True)
            lay = layer_of(fid, lid)
            while time.time() - t0 < 3600:
                lay = layer_of(fid, lid)
                if lay["status"] == "failed" or (lay["status"] == "done" and lay.get("matte_check") is not None):
                    break
                time.sleep(5)
            secs = time.time() - t0
            jobs = [job(b["job_id"]) for b in lay["batches"] if b.get("job_id")]
            batch_s = [j.get("wall_s") for j in jobs]
            ident = None
            for _ in range(40):                                              # FaceSim measures each batch's clip after its proxy
                clips = [api.get(f"/clips/{b['clip_id']}").json() for b in lay["batches"] if b.get("clip_id")]
                ids = [c.get("identity") for c in clips]
                if all(ids):
                    ident = ids
                    break
                time.sleep(3)
            means = [i.get("mean") for i in (ident or []) if i and i.get("mean") is not None]
            a0 = time.time()
            ja = api.post(f"/finals/{fid}/assemble", json={}).json()["job_id"]
            while time.time() - a0 < 900 and job(ja)["status"] in ("queued", "running"):
                time.sleep(3)
            asm = job(ja)
            mc = lay.get("matte_check") or {}
            res = {"name": name, "reply": reply, "status": lay["status"], "error": lay.get("error"), "seconds": round(secs), "batch_s": batch_s, "window": (lay.get("window") or [[None, None, None]])[0],
                   "matte_check": mc, "identity": means, "assembled": asm["status"], "assemble_s": asm.get("wall_s")}
            results["parts"][key] = res
            save()
            check(bool(reply.get("window")) and reply["window"] >= 1, f"{key}: performed in its window (×{reply.get('window')})")
            check(lay["status"] == "done" and mc.get("frames"), f"{key}: done and its matte checked ({mc.get('frames')} frames, {round(secs)} s, batches {batch_s} s)")
            check(len(mc.get("strays") or []) <= BAR_STRAYS * max(1, mc.get("frames") or 1), f"{key}: the matte strays on {len(mc.get('strays') or [])} of {mc.get('frames')} frames (≤ {BAR_STRAYS:.0%}); cover ≥ {mc.get('cover_min')}, ≤ {mc.get('ratio_max')}×")
            if key == "T":
                check(bool(means) and min(means) >= BAR_ID, f"T: Tomas keeps his face (identity {means})")
            check(asm["status"] == "done", f"{key}: assembled ({asm.get('wall_s')} s)")
            clip = (asm.get("result") or {}).get("clip_id")
            if clip:
                d = PROJECT / "clips" / clip / "master"
                fr = sorted(d.glob("*.png"))
                if fr:
                    rows.append((f"{key} {name} · window ×{reply.get('window')} · matte strays {len(mc.get('strays') or [])}/{mc.get('frames')} · identity {means}",
                                 [Image.open(fr[i]) for i in (0, len(fr) // 3, 2 * len(fr) // 3, len(fr) - 1)]))
    finally:
        try:
            api.post("/engine/stop")
        except Exception:  # noqa: BLE001
            pass
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
        if rows:
            w, h = 424, 240
            im = Image.new("RGB", (w * 4, (h + 22) * len(rows)), (24, 24, 24))
            dr = ImageDraw.Draw(im)
            for i, (label, ims) in enumerate(rows):
                dr.text((6, i * (h + 22) + 4), label, fill=(230, 230, 230))
                for j, x in enumerate(ims):
                    im.paste(x.convert("RGB").resize((w, h)), (j * w, i * (h + 22) + 22))
            im.save(OUT / "sheet.jpg", quality=88)
        save()
    return 0 if not results["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
