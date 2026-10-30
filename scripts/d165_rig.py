"""D165 rig: a character layer performed in a window adjusted by hand, then its face pass on a head box set by hand — through the app's
own routes, alone on the GPU, on the E43 copy of the walkthrough's project (F:/loom2-projects/_e43/last-ferry-copy).

The layer: The seal's 77-frame copy (`fin_47a428a0-e43ib`), Tomas (55 px head, E45's case C).

- W: the window's automatic keys offered by `GET /finals/{fid}/boxes`, made 25 % taller and moved 15 px right on every key, then sent as
  the author's (`PUT …/boxes`). `POST …/run`, then wait for the layer to be done with its matte checked.
- H: the head box's automatic keys made 10 % larger, sent as the author's. `POST …/pass {"preset": "face"}`, then its chain.
- At the end the layer's window and head box are given back to the automatic rule (the copy is scratch).

Bars (journal, set before the run):

- W: the run replies the keys' window (its smallest scale within 1 % of the keys'); the layer is done, its matte straying on ≤ 5 % of its
  frames; its performance is stamped with that window, and a key changed afterwards shows as changed.
- H: the face take is made with the keys' head boxes (its signature), and its FaceSim is no worse than the take it ran on − 0.05.

    orchestrator/.venv/Scripts/python.exe scripts/d165_rig.py [--state <scratch state dir>]
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
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts")]
PROJECT = Path("F:/loom2-projects/_e43/last-ferry-copy")
MODELS = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models"))
PORT, TOKEN = 8766, "devtoken"
OUT = ROOT / "engine" / "spikes" / "out" / "d165"
FID, LID = "fin_47a428a0-e43ib", "fig_04370fc0"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=str(Path(os.environ.get("TEMP", ".")) / "loom2-d165-state"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from m1_acceptance import port_busy
    from loom2.boxes import heads_from, sig, windows_from
    from loom2.catalogue import Catalogue
    from loom2.finals import WINDOW, FinalStore
    from loom2.heads import box_crop
    from loom2.story import StoryStore
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "final": FID, "layer": LID, "failures": []}

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
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)

        def mine() -> dict:
            return next(x for x in api.get(f"/finals/{FID}/boxes").json()["layers"] if x["id"] == LID)

        def layer() -> dict:
            return next(x for x in api.get(f"/finals/{FID}").json()["layers"] if x["id"] == LID)

        api.put(f"/finals/{FID}/layers/{LID}/boxes", json={"window": "auto", "head": "auto"}).raise_for_status()
        b = mine()
        n = api.get(f"/finals/{FID}/boxes").json()["frames"]
        # W: the window by hand
        keys = [{**k, "h": round(k["h"] * 1.25, 2), "cx": round(k["cx"] + 15, 2)} for k in b["window"]["offer"]]
        api.put(f"/finals/{FID}/layers/{LID}/boxes", json={"window": "keys", "window_keys": keys}).raise_for_status()
        want = windows_from(keys, n)
        t0 = time.time()
        r = api.post(f"/finals/{FID}/layers/{LID}/run", json={})
        r.raise_for_status()
        reply = r.json()
        print(f"run: {reply}", flush=True)
        lay = layer()
        while time.time() - t0 < 2400:
            lay = layer()
            if lay["status"] == "failed" or (lay["status"] == "done" and lay.get("matte_check") is not None):
                break
            time.sleep(5)
        mc = lay.get("matte_check") or {}
        results["W"] = {"keys": keys, "reply": reply, "status": lay["status"], "seconds": round(time.time() - t0), "matte_check": mc, "window_sig": lay.get("window_sig"),
                        "misses": len(mine()["window"]["misses"])}
        save()
        smallest = min(w[2] for w in want)
        check(reply.get("window") is not None and abs(reply["window"] - smallest) <= 0.01 * smallest, f"W: the run's window ×{reply.get('window')} is the keys' ×{round(smallest, 2)}")
        check(lay["status"] == "done" and len(mc.get("strays") or []) <= 0.05 * max(1, mc.get("frames") or 1),
              f"W: done ({round(time.time() - t0)} s), the matte strays on {len(mc.get('strays') or [])} of {mc.get('frames')} frames")
        check(lay.get("window_sig") == sig(want) and not mine()["window"]["changed"], "W: the performance is stamped with that window, not changed")
        # H: the head box by hand, then the face pass
        hk = [{**k, "side": round(k["side"] * 1.1, 2)} for k in mine()["head"]["offer"]]
        api.put(f"/finals/{FID}/layers/{LID}/boxes", json={"head": "keys", "head_keys": hk}).raise_for_status()
        ws = Workspace(PROJECT)
        store = FinalStore(ws)
        f = store.get(FID)
        heads = heads_from(hk, n, f.size["w"], f.size["h"])
        base = sorted(store.frames_dir(FID, LID).glob("*.png"))
        t1 = time.time()
        r = api.post(f"/finals/{FID}/layers/{LID}/pass", json={"preset": "face"})
        r.raise_for_status()
        jid = r.json()["job_id"]
        while jid:
            while True:
                j = api.get(f"/jobs/{jid}").json()
                if j["status"] not in ("queued", "running"):
                    break
                time.sleep(4)
            print(f"  {j['status']} {jid} · {j.get('wall_s')} s", flush=True)
            if j["status"] != "done":
                break
            jid = (j.get("result") or {}).get("next_job_id")
        lay = layer()
        take = next((t for t in lay["takes"] if t.get("preset") == "face" and not t.get("stale") and t["id"] == lay.get("source")), None)
        fs = FaceSim(MODELS)
        p = StoryStore(ws).profile(lay["profile_id"]).version(lay["version"])
        ra = np.asarray(Image.open(Catalogue(ws).abs_path(Catalogue(ws).get(p.anim_ref_asset_id))).convert("RGB"))
        hero = fs.embed(ra, fs.detect(ra)[0].kps)

        def score(frames: list[Path]) -> float | None:
            sims = []
            for i in np.linspace(0, n - 1, 12).round().astype(int):
                im = np.asarray(box_crop(Image.open(frames[i]).convert("RGB"), heads[i]))
                faces = fs.detect(im)
                if faces:
                    sims.append(max(fs.similarity(hero, fs.embed(im, x.kps)) for x in faces[:3]))
            return round(float(np.mean(sims)), 3) if sims else None
        before = score(base)
        after = score(sorted(store.pass_dir(FID, LID, f"passes/{take['id']}").glob("*.png"))) if take else None
        results["H"] = {"keys": hk, "take": take, "seconds": round(time.time() - t1), "facesim_before": before, "facesim_after": after}
        save()
        check(bool(take) and take.get("head_sig") == sig(heads), f"H: the face take was made with the keys' head boxes ({round(time.time() - t1)} s)")
        check(before is not None and after is not None and after >= before - 0.05, f"H: FaceSim {before} → {after}")
        # a key changed after the performance shows as changed
        api.put(f"/finals/{FID}/layers/{LID}/boxes", json={"window": "keys", "window_keys": [{**keys[0], "cx": keys[0]["cx"] + 30}, *keys[1:]]}).raise_for_status()
        check(mine()["window"]["changed"], "W: a key changed after the performance shows as changed")
        rows = []
        for i in (0, n // 2, n - 1):
            x0, y0, s = heads[i]
            rows += [Image.open(base[i]).convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((200, 200)),
                     Image.open(store.pass_dir(FID, LID, f"passes/{take['id']}") / f"{i:04d}.png").convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((200, 200)) if take else Image.new("RGB", (200, 200))]
        sheet = Image.new("RGB", (200 * len(rows), 200))
        for k, im in enumerate(rows):
            sheet.paste(im, (200 * k, 0))
        sheet.save(OUT / "sheet.jpg", quality=88)
        results["window_size"] = list(WINDOW)
    finally:
        try:
            api.put(f"/finals/{FID}/layers/{LID}/boxes", json={"window": "auto", "head": "auto"})
        except Exception:  # noqa: BLE001
            pass
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
        save()
    return 0 if not results["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
