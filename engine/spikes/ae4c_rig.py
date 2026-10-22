"""AE4c rig (D118): the face pass on the PS5 rig's final through the app — E29b's English line attached to Mara's layer at 1.0 s (AE4b), the
Lip-sync pass run as its chain of jobs (the S2V talking head for the line's window, then Wan Animate on the head crop in two batches, the
paste), the take measured as E29b measured its arms (FaceSim of the head crop against the reference's head, the sync r of the mouth against
the line, the articulation, the paste seam against the frames it was pasted on), the composition synced and the finished shot rendered
for the author's look; then, when asked, the Face pass without a line for comparison. Outputs under engine/spikes/out/ae4c/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/ae4c_rig.py [--arms lipsync,face]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
import e18_lipsync as E18  # noqa: E402
from e29b_headlayer import seam  # noqa: E402
from m1_acceptance import Orch  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "ae4c"
PROJECT = ROOT / "engine" / "spikes" / "out" / "ps5" / "project"
FID, LID = "fin_0f41f551", "fig_m"
WAV = ROOT / "engine" / "spikes" / "out" / "e20" / "en1_draft.wav"          # E20's line en1 (ae4b's ingest moved the e29b copy into the catalogue)
REF_HEAD = ROOT / "engine" / "spikes" / "out" / "e29b" / "ref_head.png"
PORT = 8796
LINE_AT = 1.0


def log(m: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {m}"
    print(line, flush=True)
    with (OUT / "log.txt").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def follow_chain(o: Orch, job_id: str) -> list[dict]:
    """Every job of the pass's chain waited for in turn; the records."""
    out = []
    while job_id:
        t0 = time.time()
        j = o.wait_job(job_id, {"done", "failed", "cancelled"}, timeout=3600)
        c = (j.get("result") or {}).get("compiled") or {}
        stage = c.get("stage") or ((j.get("recipe") or {}).get("step") or {}).get("stage")
        log(f"  {j['status']} {job_id}: {stage} {c.get('k')}+1/{c.get('of')} · {c.get('frames')} frames · {time.time() - t0:.0f} s · {(j.get('log_tail') or [])[-1:]}")
        out.append({"job_id": job_id, "status": j["status"], "stage": stage, "k": c.get("k"), "frames": c.get("frames"), "wall_s": round(time.time() - t0),
                    "error": j.get("error")})
        if j["status"] != "done":
            break
        job_id = (j.get("result") or {}).get("next_job_id")
    return out


def measure(arm: str, take_dir: Path, base_dir: Path, boxes: list[tuple[int, int, int]], fs, hero, audio: np.ndarray, sr: int, f: dict, with_speech: bool) -> dict:
    n, fps = f["frames"], f["rate"]
    heads = sorted((take_dir / "head").glob("*.png"))[:n]
    pasted = sorted(take_dir.glob("*.png"))[:n]
    base = sorted(base_dir.glob("*.png"))[:n]
    rgb_dir = OUT / f"{arm}_head_rgb"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    rgb = []
    for i, p in enumerate(heads):                                        # the measures read RGB; the take keeps RGBA
        q = rgb_dir / f"{i:04d}.png"
        Image.open(p).convert("RGB").save(q)
        rgb.append(q)
    motion, ok = E18.mouth_energy(fs, rgb)
    env = E18.rms_envelope(audio, sr, fps, len(rgb))
    r, lag = E18.sync_score(motion[1:], env[1:]) if ok and with_speech else (None, 0)
    sims = []
    for idx in (0, n // 2, n - 1):
        emb = E18.largest_face(fs, rgb[idx])
        sims.append(round(float(fs.similarity(hero, emb)), 3) if hero is not None and emb is not None else None)
    alphas = [float(np.asarray(Image.open(p).convert("RGBA"))[..., 3].mean() / 255.0) for p in heads[::8]]
    wav = OUT / f"{arm}_shot.wav"
    import soundfile as sf
    sf.write(str(wav), audio, sr)
    E18.mux(rgb, wav, OUT / f"{arm}_head.mp4", fps, 512, 512)
    E18.mux(pasted, wav, OUT / f"{arm}_take.mp4", fps, f["size"]["w"], f["size"]["h"])
    cells = []
    for idx in (0, n // 4, n // 2, 3 * n // 4, n - 1):
        x0, y0, s = boxes[idx]
        q = OUT / f"{arm}_base_{idx}.png"
        Image.open(base[idx]).convert("RGB").crop((x0, y0, x0 + s, y0 + s)).resize((512, 512), Image.LANCZOS).save(q)
        cells.append((q, f"before f{idx}"))
        cells.append((rgb[idx], f"{arm} f{idx}"))
    E18.sheet(cells, OUT / f"{arm}_sheet.jpg", cols=2, cell=256)
    return {"sync_r": r, "sync_lag": lag, "mouth_found": bool(ok), "articulation": round(float(np.mean(motion[1:])), 3) if ok else None, "facesim": sims,
            "seam": seam(pasted, base, boxes), "alpha_mean": round(float(np.mean(alphas)), 3)}


def repaste(arms: list[str]) -> int:
    """The takes' frames made again from their kept heads with the current paste (a CPU re-run of the finisher's last step), measured, the
    composition synced to each and the finished shot rendered — for a change to heads.paste_head without the GPU's half hour."""
    OUT.mkdir(parents=True, exist_ok=True)
    from loom2.compositions import CompositionStore
    from loom2.finals import FinalStore
    from loom2.heads import head_boxes, paste_take
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    ws = Workspace(PROJECT)
    store, cs = FinalStore(ws), CompositionStore(ws)
    f0 = store.get(FID)
    lay = next(x for x in f0.layers if x.id == LID)
    boxes = head_boxes(store.keypoints(FID, LID), f0.frames, f0.size["w"], f0.size["h"])
    n = f0.frames
    base_dir = store.pass_dir(FID, LID, "frames")
    cleanup = next((t for t in lay.takes if t["preset"] == "cleanup"), None)
    if cleanup:
        base_dir = store.pass_dir(FID, LID, f"passes/{cleanup['id']}")            # the base the passes were run on
    base = sorted(base_dir.glob("*.png"))[:n]
    mattes = sorted(store.pass_dir(FID, LID, "matte").glob("*.png"))[:n]
    comp_mattes = sorted((cs.footage(FID) / f"{LID}_matte").glob("*.png"))[:n]
    fs = FaceSim(E18.MODELS)
    hero = E18.largest_face(fs, REF_HEAD) if REF_HEAD.is_file() else None
    seconds = n / f0.rate
    line, sr = E18.fit_audio(WAV, seconds - LINE_AT, OUT / "line_fit.wav")
    audio = np.concatenate([np.zeros(int(round(LINE_AT * sr)), dtype=np.float32), line])[: int(round(seconds * sr))]
    results = {"repaste": {}}
    state = OUT / "_state"
    o = Orch(state, PORT, PROJECT).start(timeout=180)
    try:
        h = o.http
        for arm in arms:
            preset = "lipsync" if arm == "lipsync" else "face"
            take = next((t for t in lay.takes if t["preset"] == preset), None)
            if not take:
                log(f"repaste {arm}: no take")
                continue
            take_dir = store.pass_dir(FID, LID, f"passes/{take['id']}")
            heads = sorted((take_dir / "head").glob("*.png"))[:n]
            t0 = time.time()
            paste_take(take_dir, heads, base, mattes, comp_mattes, boxes, n)
            m = measure(f"{arm}_repaste", take_dir, base_dir, boxes, fs, hero, audio, sr, f0.model_dump(), preset == "lipsync")
            log(f"repaste {arm}: {take['id']} in {time.time() - t0:.0f} s · {json.dumps(m)}")
            r = h.post(f"/finals/{FID}/layers/{LID}/source", json={"take": take["id"]}, timeout=300).json()
            cs_rev = (r.get("composition") or {}).get("revision")
            jid = h.post(f"/finals/{FID}/composition/render", timeout=60).json()["job_id"]
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=1800)
            if j["status"] == "done":
                clip = h.get(f"/clips/{j['result']['clip_id']}").json()
                shutil.copyfile(PROJECT / clip["proxy_path"], OUT / f"final_{arm}.mp4")
            log(f"  source set (composition rev {cs_rev}), rendered {j['status']}")
            results["repaste"][arm] = {"take": take["id"], **m, "comp_revision": cs_rev, "render": j["status"]}
        prev = json.loads((OUT / "results.json").read_text(encoding="utf-8")) if (OUT / "results.json").is_file() else {}
        (OUT / "results.json").write_text(json.dumps({**prev, **results}, indent=1), encoding="utf-8")
        log(f"repaste done: {json.dumps(results)}")
    finally:
        o.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="lipsync,face", help="lipsync (the talking head drives the mouth), face, mouth (Lip-sync with the mouth by the model, AE4d)")
    ap.add_argument("--repaste", action="store_true", help="no GPU: paste the kept heads of the existing face / lipsync takes again (heads.paste_take), measure, render")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    if a.repaste:
        return repaste(arms)
    if E18.engine_listening():
        print("an engine is already listening on 8188 — stop it first (D97)")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    from loom2.catalogue import Catalogue
    from loom2.finals import FinalStore
    from loom2.heads import head_boxes
    from loom2.tools.facesim import FaceSim
    from loom2.workspace import Workspace
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    store = FinalStore(ws)
    f0 = store.get(FID)
    boxes = head_boxes(store.keypoints(FID, LID), f0.frames, f0.size["w"], f0.size["h"])
    base_dir = store.frames_dir(FID, LID)                                  # the shown source the pass reads (the clean-up take, AE4a)
    log(f"AE4c start · arms {arms} · base {base_dir.relative_to(store.folder(FID)).as_posix()} · boxes {boxes[0]} … {boxes[-1]}")
    fs = FaceSim(E18.MODELS)
    hero = E18.largest_face(fs, REF_HEAD) if REF_HEAD.is_file() else None
    seconds = f0.frames / f0.rate
    line, sr = E18.fit_audio(WAV, seconds - LINE_AT, OUT / "line_fit.wav")
    audio = np.concatenate([np.zeros(int(round(LINE_AT * sr)), dtype=np.float32), line])[: int(round(seconds * sr))]   # the line where it plays in the shot
    asset = cat.ingest_file(WAV, kind="audio", move=False, suite="story", prompt_text="Hello, this is Mara.", params={"rig": "ae4c", "source": "E20 en1 draft"})
    asset = cat.make_thumbs(asset, WAV)
    state = OUT / "_state"
    shutil.rmtree(state, ignore_errors=True)
    o = Orch(state, PORT, PROJECT).start(timeout=180)
    results: dict = {"arms": {}}
    try:
        h = o.http
        c = h.get(f"/finals/{FID}/composition").json()
        mine = [x for x in c.get("audio") or [] if x.get("final_layer") == LID]
        if not mine:
            c = h.post(f"/finals/{FID}/composition/audio", json={"asset_id": asset.id, "layer_id": LID, "t": LINE_AT}, timeout=300).json()
            mine = [x for x in c["audio"] if x.get("final_layer") == LID]
        log(f"the line on the lanes: layer {mine[0]['layer']} · composition rev {c['revision']}")
        for arm in arms:
            preset = "lipsync" if arm in ("lipsync", "mouth") else "face"
            body = {"preset": preset, **({"mouth": "model"} if arm == "mouth" else {})}        # AE4d: the mouth by the model (LatentSync in its venv)
            t0 = time.time()
            r = h.post(f"/finals/{FID}/layers/{LID}/pass", json=body, timeout=120)
            if r.status_code != 200:
                log(f"{arm}: refused {r.status_code} {r.text[:300]}")
                results["arms"][arm] = {"error": r.text[:300]}
                continue
            log(f"{arm}: queued {r.json()['job_id']}")
            steps = follow_chain(o, r.json()["job_id"])
            total = round(time.time() - t0)
            fin = h.get(f"/finals/{FID}").json()
            lay = next(x for x in fin["layers"] if x["id"] == LID)
            take = lay["takes"][-1] if lay["takes"] and lay["takes"][-1]["preset"] == preset else None
            if not take or lay["source"] != take["id"] or any(s["status"] != "done" for s in steps):
                log(f"{arm}: no take ({[s['status'] for s in steps]})")
                results["arms"][arm] = {"steps": steps, "wall_s": total, "error": "no take"}
                continue
            take_dir = store.pass_dir(FID, LID, f"passes/{take['id']}")
            m = measure(arm, take_dir, base_dir, boxes, fs, hero, audio, sr, fin, preset == "lipsync")
            log(f"{arm}: take {take['id']} in {total} s · {json.dumps(m)} · lines {take.get('lines')}")
            cs = h.post(f"/finals/{FID}/composition/sync", timeout=300).json()
            log(f"  composition synced: rev {cs['revision']} sources {cs['sources']}")
            t1 = time.time()
            jid = h.post(f"/finals/{FID}/composition/render", timeout=60).json()["job_id"]
            j = o.wait_job(jid, {"done", "failed", "cancelled"}, timeout=1800)
            render = {"status": j["status"], "wall_s": round(time.time() - t1)}
            if j["status"] == "done":
                clip = h.get(f"/clips/{j['result']['clip_id']}").json()
                shutil.copyfile(PROJECT / clip["proxy_path"], OUT / f"final_{arm}.mp4")
                render["clip_id"] = clip["id"]
            log(f"  rendered: {render}")
            results["arms"][arm] = {"take": take["id"], "steps": steps, "wall_s": total, **m, "lines": take.get("lines"), "render": render, "comp_revision": cs["revision"]}
            (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        log(f"done: {json.dumps(results)}")
    finally:
        o.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
