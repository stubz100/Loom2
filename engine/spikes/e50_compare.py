"""Spike E50 (M6, the author chose to compare first; journal 2026-10-31 14:47): three ways to a busy market on the market walk's v2 on E47's
copy (Final 5: the plate under D170 and D172), each assembled with the same three performances (Mira, Hanne, Bram — performed once
through POST /finals/{fid}/owed):
- (a) the extras: Final 5 as it is;
- (b) the generated plate with a crowd: Klein paints a crowd into the plate's frame 0 (I2I 0.55), LTX-2.3 carries it along the path on
      the plate's own depth pass (D130's recipe, the crowd asked for) — the plate of a copy of Final 5;
- (c) the crowd clip: E49c's L1, its tone locked to frame 0, mapped onto Final 5's facade band (E49's match) — the plate of another copy.
Measured: the three assembled clips side by side (frames 5, 32, 60, and a video), (b)'s stall front against Final 5's plate (NCC of the
upper band), each arm's own GPU seconds. A phase already done (results.json) is not run again. Outputs under engine/spikes/out/e50/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e50_compare.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e49_crowd as e  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e50"
F5 = "fin_d5ce3248"
CROWD_STILL = ("a busy fish market: shoppers with bags and baskets walking along the aisle in front of the fish stalls and standing at the "
               "counters, stallholders in aprons serving behind the counters, seen from the side at eye level, the same light")
CROWD_PATH = ("A busy fish market hall: shoppers walk along the aisle and past the fish stalls, stallholders serve behind the counters, people "
              "carry bags and baskets. The camera moves slowly sideways along the aisle.")
SAMPLE = (5, 32, 60)


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    return round(float((a * b).mean()), 3)


def tone_locked(frames: list[Image.Image]) -> list[Image.Image]:
    """E49c: every frame's tone locked to frame 0 — a per-channel gain and offset fitted on the static upper band."""
    ref = np.asarray(frames[0], dtype=np.float64)[:190].reshape(-1, 3)
    out = []
    for im in frames:
        f = np.asarray(im, dtype=np.float64)
        band = f[:190].reshape(-1, 3)
        o = np.empty_like(f)
        for c in range(3):
            g, k = np.linalg.lstsq(np.stack([band[:, c], np.ones(len(band))], 1), ref[:, c], rcond=None)[0]
            o[..., c] = f[..., c] * g + k
        out.append(Image.fromarray(np.clip(o, 0, 255).astype(np.uint8)))
    return out


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore, plate_path_frames, plate_path_guide, plate_path_size
    from loom2.fsio import new_id
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(e.PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    rp = OUT / "results.json"
    results: dict = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else {"arms": {}}
    save = lambda: rp.write_text(json.dumps(results, indent=1), encoding="utf-8")  # noqa: E731
    ws = Workspace(e.PROJECT)
    cat, store = Catalogue(ws), FinalStore(ws)
    f5 = store.get(F5)
    w, h = plate_path_size(f5, 576, 64)
    n = plate_path_frames(f5.frames)
    if "guide" not in results:                                                  # (b)'s guide and its first frame, catalogued before the orchestrator starts
        depth = sorted(store.pass_dir(F5, "plate", "depth").glob("*.png"))
        plate_path_guide(depth, w, h, n, OUT / "depth.mp4", f5.rate)
        g = cat.make_thumbs(cat.ingest_file(OUT / "depth.mp4", kind="video", move=False, suite="stage", lineage_kind="stage-pass",
                                            params={"final_id": F5, "layer": "plate", "pass": "depth-sequence", "spike": "E50"},
                                            frames=n, fps=float(f5.rate), w=w, h=h), depth[0])
        shutil.copyfile(store.frames_dir(F5, "plate") / "0000.png", OUT / "plate0.png")
        p0 = cat.make_thumbs(cat.ingest_file(OUT / "plate0.png", kind="image", move=False, suite="stage", params={"final_id": F5, "spike": "E50"}))
        results.update(guide=g.id, plate0=p0.id, size=[w, h], frames=n)
        save()
    api = httpx.Client(base_url=f"http://127.0.0.1:{e.PORT}", headers={"X-Loom-Token": e.TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(e.PORT), "--state",
                             str(e.STATE), "--project", str(e.PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": e.TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def wait(jid: str) -> dict:
        while True:
            j = api.get(f"/jobs/{jid}").json()
            if j["status"] not in ("queued", "running", "staged"):
                return j
            time.sleep(5)

    def idle(limit_min: float = 120) -> list[dict]:
        t0 = time.time()
        while time.time() - t0 < limit_min * 60:
            items = api.get("/jobs").json().get("items", [])
            if not any(x["status"] in ("queued", "running", "staged") for x in items):
                return items
            time.sleep(10)
        raise RuntimeError("the queue is still busy")

    def run(recipe: dict, label: str) -> dict:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": recipe})
        r.raise_for_status()
        j = wait(r.json()["jobs"][0]["id"])
        print(f"{label}: {j['status']} in {round(time.time() - t0)} s {j.get('error') or ''}", flush=True)
        if j["status"] != "done":
            raise RuntimeError(f"{label}: {j['status']} {j.get('error')}")
        return {"job": j["id"], "seconds": round(time.time() - t0), "result": j.get("result") or {}}

    def assemble(fid: str, label: str) -> str:
        t0 = time.time()
        r = api.post(f"/finals/{fid}/assemble")
        if r.status_code != 200:
            raise RuntimeError(f"assemble {label}: {r.status_code} {r.text[:400]}")
        j = wait(r.json()["job_id"])
        print(f"assembled {label}: {j['status']} in {round(time.time() - t0)} s {j.get('error') or ''}", flush=True)
        if j["status"] != "done":
            raise RuntimeError(f"assemble {label}: {j.get('error')}")
        return j["result"]["clip_id"]

    def copy_final(name: str, plate: list[Image.Image]) -> str:
        fid = new_id("fin")
        shutil.copytree(store.folder(F5), store.folder(fid))
        rec = json.loads(store.path(fid).read_text(encoding="utf-8"))
        rec.update(id=fid, name=name, assembly=None, assembled_at=None, clip_id=None)
        store.path(fid).write_text(json.dumps(rec, indent=1), encoding="utf-8")
        d = store.frames_dir(fid, "plate")
        for i, im in enumerate(plate):
            im.convert("RGB").resize((f5.size["w"], f5.size["h"]), Image.Resampling.LANCZOS).save(d / f"{i:04d}.png")
        return fid

    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        if "performed" not in results:
            t0 = time.time()
            r = api.post(f"/finals/{F5}/owed")
            r.raise_for_status()
            print("owed:", json.dumps({k: r.json()[k] for k in ("queued", "refused")}), flush=True)
            items = idle()
            jids = [q["job_id"] for q in r.json()["queued"]]
            results["performed"] = {"seconds": round(time.time() - t0), "queued": r.json()["queued"], "refused": r.json()["refused"],
                                    "jobs": [{"id": x["id"], "kind": x.get("recipe", {}).get("kind"), "status": x["status"], "wall_s": x.get("wall_s")}
                                             for x in items if x["id"] in jids or x.get("origin", {}) and (x.get("origin") or {}).get("ref") == F5][-20:]}
            save()
            print("performed in", results["performed"]["seconds"], "s", flush=True)
        if "b_clip" not in results:
            doc = api.post("/documents", json={"from_asset": results["plate0"], "name": "E50 crowd still"}).json()["id"]
            s1 = run({"kind": "i2i", "document_id": doc, "source": "visible", "prompt_text": CROWD_STILL, "strength": 0.55, "seeds": [7]}, "(b) still")
            r = api.post(f"/documents/{doc}/flatten", json={"to_catalogue": True, "name": "E50 crowd still"})
            r.raise_for_status()
            still = r.json()["asset"]["id"]
            Image.open(cat.abs_path(cat.get(still))).convert("RGB").save(OUT / "b_still.png")
            s2 = run({"kind": "i2v", "model_id": "ltx23-distilled-fp8", "start_asset": still, "prompt_text": CROWD_PATH, "frames": n, "fps": f5.rate,
                      "width": w, "height": h, "preset": "draft", "seeds": [7], "guide": {"asset_id": results["guide"], "kind": "depth", "strength": 1.0}}, "(b) path")
            results.update(b_still=still, b_clip=s2["result"]["clip_id"], b_seconds=s1["seconds"] + s2["seconds"])
            save()
        api.post("/engine/stop")
        if "a_clip" not in results:
            results["a_clip"] = assemble(F5, "(a) extras")
            save()
        if "c_clip" not in results:
            l1 = json.loads((ROOT / "engine" / "spikes" / "out" / "e49c" / "results.json").read_text(encoding="utf-8"))["arms"]["L1"]["clip_id"]
            fr = tone_locked([Image.open(p).convert("RGB") for p in sorted((e.PROJECT / "clips" / l1 / "master").glob("*.png"))])
            fid = copy_final("E50 (c) crowd clip", e.preview(fr, OUT / "c_plate.mp4"))
            results.update(c_final=fid, c_clip=assemble(fid, "(c) crowd clip"))
            save()
        if "b_assembled" not in results:
            rec = json.loads((e.PROJECT / "clips" / results["b_clip"] / "clip.json").read_text(encoding="utf-8"))
            fr = [Image.open(p).convert("RGB") for p in sorted((e.PROJECT / rec["master_dir"]).glob("*.png"))][: f5.frames]
            fid = copy_final("E50 (b) generated plate", fr)
            results.update(b_final=fid, b_assembled=assemble(fid, "(b) generated plate"))
            save()
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()

    def clip(cid: str) -> list[Image.Image]:
        rec = json.loads((e.PROJECT / "clips" / cid / "clip.json").read_text(encoding="utf-8"))
        return [Image.open(p).convert("RGB") for p in sorted((e.PROJECT / rec["master_dir"]).glob("*.png"))]
    arms = {"(a) extras": clip(results["a_clip"]), "(b) generated plate": clip(results["b_assembled"]), "(c) crowd clip": clip(results["c_clip"])}
    base = [np.asarray(Image.open(store.frames_dir(F5, "plate") / f"{k:04d}.png").convert("L"), dtype=np.float64)[: int(480 * 0.6)] for k in SAMPLE]
    bplate = [np.asarray(Image.open(store.frames_dir(results["b_final"], "plate") / f"{k:04d}.png").convert("L"), dtype=np.float64)[: int(480 * 0.6)] for k in SAMPLE]
    results["b_set_ncc"] = [ncc(a, b) for a, b in zip(base, bplate)]
    save()
    W, H = 848, 480
    sheet = Image.new("RGB", (W // 2 * 3, (H // 2 + 18) * 3), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for c, (name, fr) in enumerate(arms.items()):
        for r_, k in enumerate(SAMPLE):
            sheet.paste(fr[min(k, len(fr) - 1)].resize((W // 2, H // 2)), (c * W // 2, r_ * (H // 2 + 18) + 18))
            dr.text((c * W // 2 + 4, r_ * (H // 2 + 18) + 3), f"{name} · frame {k}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=88)
    import av
    m = min(len(x) for x in arms.values())
    with av.open(str(OUT / "compare.mp4"), "w", format="mp4") as cont:
        st = cont.add_stream("libx264", rate=16)
        st.width, st.height, st.pix_fmt = W, H * 3, "yuv420p"
        st.options = {"crf": "20"}
        for k in range(m):
            canvas = Image.new("RGB", (W, H * 3))
            d2 = ImageDraw.Draw(canvas)
            for r_, (name, fr) in enumerate(arms.items()):
                canvas.paste(fr[k].resize((W, H)), (0, r_ * H))
                d2.text((8, r_ * H + 6), name, fill=(255, 255, 255))
            for pkt in st.encode(av.VideoFrame.from_image(canvas)):
                cont.mux(pkt)
        for pkt in st.encode():
            cont.mux(pkt)
    print(json.dumps({k: v for k, v in results.items() if k in ("b_set_ncc", "b_seconds", "a_clip", "b_assembled", "c_clip")}), flush=True)
    print("performed:", json.dumps(results.get("performed", {}).get("queued")), "refused:", json.dumps(results.get("performed", {}).get("refused")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
