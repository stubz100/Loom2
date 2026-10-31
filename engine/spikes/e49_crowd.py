"""Spike E49 (M6, the author's idea; journal 2026-10-31 11:12): a crowd clip of the market's stall front, the camera held still, to be
played on the facade face — through the app's own routes on E47's copy (an edit document from the crop, then POST /jobs):
- SP / SE  the stretch the shot's v2 sees (facade_right x 80–360 of 750, full height) scaled to 1088×480 and refined by Klein (I2I) —
           with stallholders and shoppers (strength 0.6) / nobody (0.35);
- CP / CE  Wan 2.2 Fun-Camera, Static, Draft, from SP / SE;
- CN       the plain Wan 2.2 I2V from SP, the stillness asked in words only;
- CP2      Fun-Camera, Static, from CP's last frame (a Wan continuation, lead 1 — the extend route keeps no camera, so by hand).
Measured: the upper band's drift (phase correlation of the top 40 % against frame 0, every fourth frame) and the zoom first → last; the
join CP → CP2; sheets; a preview of Final 3's plate with the clip mapped onto its facade band (E49's match: x 171 → 90, rows 42–117,
0.21 texels a plate pixel). Outputs under engine/spikes/out/e49/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e49_crowd.py
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

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PID, PROJECT, STATE, VID  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e49"
PORT, TOKEN = 8766, "devtoken"
FACE = "facade_right"
X0, X1 = 80, 360                                  # the stretch of the texture the clip covers
W, H, FRAMES, FPS = 1088, 480, 81, 16
PLATE = PROJECT / "finals" / "fin_d5ce3248" / "plate" / "frames"   # Final 5 (D + E48's ground): the shot's v2, 65 frames; the match was made on Final 3, the same facade
MATCH = {"x0": 171.0, "x64": 90.0, "y": 42.0, "s": 0.21, "band": 0.75}
STALLS = "a flat elevation of fish market stalls seen square on: counters of fish on ice, crates below, lamps above, iron columns, white tiles"
PROMPTS = {
    "SP": f"{STALLS}; stallholders in aprons behind the counters and shoppers with bags and baskets standing and walking in front of them, "
          "seen from the side at eye level, even light, no perspective",
    "SE": f"{STALLS}; nobody in it, even light, no perspective",
    "CP": "stallholders serve at the counters, shoppers walk slowly left and right past the fish stalls, some stop to look; the camera does not move",
    "CE": "shoppers walk into view from the left and the right and pass the fish stalls, stallholders work at the counters; the camera does not move",
    "CN": "a static locked-off camera: stallholders serve at the counters, shoppers walk slowly left and right past the fish stalls; the camera does not move",
}


def gray(im: Image.Image) -> np.ndarray:
    g = np.asarray(im.convert("L"), dtype=np.float64)
    g = g[: int(g.shape[0] * 0.4)]                                           # the upper band: lamps, columns, wall
    g -= g.mean()
    return g * np.hanning(g.shape[0])[:, None] * np.hanning(g.shape[1])[None, :]


def shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    F, G = np.fft.fft2(a), np.fft.fft2(b)
    R = G * np.conj(F)
    R /= np.abs(R) + 1e-9
    r = np.fft.ifft2(R).real
    iy, ix = np.unravel_index(int(np.argmax(r)), r.shape)
    h, w = r.shape
    return float(ix if ix <= w // 2 else ix - w), float(iy if iy <= h // 2 else iy - h)


def zoom(first: Image.Image, last: Image.Image) -> float:
    """The scale (0.95–1.05) that best maps the first frame's upper band, zoomed about the frame's centre, onto the last's."""
    a = first.convert("L"); t = np.asarray(last.convert("L"), dtype=np.float64)
    w, h = a.size
    cx, cy, rw, rh = w // 2, h // 2, int(w * 0.4), int(h * 0.3)
    tt = t[cy - rh:cy - rh // 3, cx - rw:cx + rw]; tt = (tt - tt.mean()) / (tt.std() + 1e-6)
    best, best_s = -2.0, 1.0
    for s in np.linspace(0.95, 1.05, 41):
        zw, zh = int(round(w * s)), int(round(h * s))
        z = np.asarray(a.resize((zw, zh), Image.Resampling.BILINEAR), dtype=np.float64)
        zcx, zcy = zw // 2, zh // 2
        c = z[zcy - rh:zcy - rh // 3, zcx - rw:zcx + rw]; c = (c - c.mean()) / (c.std() + 1e-6)
        v = float((c * tt).mean())
        if v > best:
            best, best_s = v, float(s)
    return round(best_s, 4)


def measure(frames: list[Image.Image]) -> dict:
    g0 = gray(frames[0])
    d = [shift(g0, gray(frames[k])) for k in range(0, len(frames), 4)]
    return {"drift_max_px": round(max(max(abs(x), abs(y)) for x, y in d), 1), "drift_last": [round(v, 1) for v in d[-1]],
            "zoom_last": zoom(frames[0], frames[-1])}


def preview(frames: list[Image.Image], path: Path) -> list[Image.Image]:
    """Final 3's plate with the clip on its facade band: plate (u, v) in the upper 75 % → texture (x0(k) + 0.21 u, 42 + 0.21 v) → clip."""
    out = []
    n = len(sorted(PLATE.glob("*.png")))
    bh = int(480 * MATCH["band"])
    v, u = np.mgrid[0:bh, 0:848].astype(np.float64)
    for k in range(n):
        plate = np.asarray(Image.open(PLATE / f"{k:04d}.png").convert("RGB")).copy()
        x0 = MATCH["x0"] + (MATCH["x64"] - MATCH["x0"]) * k / max(1, n - 1)
        tx, ty = x0 + MATCH["s"] * u, MATCH["y"] + MATCH["s"] * v
        cx = np.clip(((tx - X0) * W / (X1 - X0)).round().astype(int), 0, W - 1)
        cy = np.clip((ty * H / 124.0).round().astype(int), 0, H - 1)
        clip = np.asarray(frames[min(k, len(frames) - 1)])
        plate[:bh] = clip[cy, cx]
        out.append(Image.fromarray(plate))
    try:
        import av
        with av.open(str(path), "w", format="mp4") as c:
            s = c.add_stream("libx264", rate=FPS)
            s.width, s.height, s.pix_fmt = 848, 480, "yuv420p"
            s.options = {"crf": "18"}
            for im in out:
                for pkt in s.encode(av.VideoFrame.from_image(im)):
                    c.mux(pkt)
            for pkt in s.encode():
                c.mux(pkt)
    except Exception as e:  # noqa: BLE001
        print("no mp4:", e, flush=True)
    return out


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8188) or port_busy(PORT):
        raise SystemExit("the engine's or the orchestrator's port is busy — one GPU job at a time (rule 10)")
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat = Catalogue(ws)
    f = next(x for x in StoryStore(ws).profile(PID).version(VID).place_set.faces if x.id == FACE)
    tex = Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB")
    crop = tex.crop((X0, 0, X1, tex.height)).resize((W, H), Image.Resampling.LANCZOS)
    crop_p = OUT / "crop.png"
    crop.save(crop_p)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "texture": f.texture_asset_id, "arms": {}}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers={"X-Loom-Token": TOKEN}, timeout=120)
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state",
                             str(STATE), "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env={**os.environ, "LOOM2_TOKEN": TOKEN}, stdout=log, stderr=subprocess.STDOUT)

    def run(recipe: dict, arm: str) -> dict:
        t0 = time.time()
        r = api.post("/jobs", json={"recipe": recipe})
        r.raise_for_status()
        jid = r.json()["jobs"][0]["id"]
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

    def clip_frames(clip_id: str) -> list[Image.Image]:
        rec = json.loads((PROJECT / "clips" / clip_id / "clip.json").read_text(encoding="utf-8"))
        return [Image.open(p).convert("RGB") for p in sorted((PROJECT / rec["master_dir"]).glob("*.png"))]

    def imported(p: Path) -> str:
        return api.post("/assets/import", json={"paths": [str(p)]}).json()["items"][0]["id"]

    clips: dict[str, list[Image.Image]] = {}
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        crop_id = imported(crop_p)
        starts = {}
        for arm, strength in (("SP", 0.6), ("SE", 0.35)):
            doc = api.post("/documents", json={"from_asset": crop_id, "name": f"E49 {arm}"}).json()["id"]
            run({"kind": "i2i", "document_id": doc, "source": "visible", "prompt_text": PROMPTS[arm], "strength": strength, "seeds": [11]}, arm)
            r = api.post(f"/documents/{doc}/flatten", json={"to_catalogue": True, "name": f"E49 {arm}"})   # the refine lands as a layer
            r.raise_for_status()
            starts[arm] = r.json()["asset"]["id"]
            Image.open(cat.abs_path(cat.get(starts[arm]))).convert("RGB").save(OUT / f"start_{arm}.png")
        base = {"kind": "i2v", "frames": FRAMES, "fps": FPS, "width": W, "height": H, "preset": "draft", "seeds": [11]}
        for arm, start, model, cam in (("CP", "SP", "wan22-fun-camera-high-fp8", True), ("CE", "SE", "wan22-fun-camera-high-fp8", True),
                                       ("CN", "SP", "wan22-i2v-high-fp8", False)):
            res = run({**base, "model_id": model, "start_asset": starts[start], "prompt_text": PROMPTS[arm], **({"camera": {"move": "static"}} if cam else {})}, arm)
            clips[arm] = clip_frames(res["clip_id"])
        last = OUT / "cp_last.png"
        clips["CP"][-1].save(last)
        res = run({**base, "model_id": "wan22-fun-camera-high-fp8", "start_asset": imported(last), "prompt_text": PROMPTS["CP"], "camera": {"move": "static"}}, "CP2")
        clips["CP2"] = clip_frames(res["clip_id"])
        api.post("/engine/stop")
    finally:
        try:
            orch.terminate()
            orch.wait(timeout=30)
        except Exception:  # noqa: BLE001
            orch.kill()
        log.close()
    for arm, fr in clips.items():
        results["arms"][arm].update(measure(fr))
        results["arms"][arm]["size"] = list(fr[0].size)
    if "CP" in clips and "CP2" in clips:
        dx, dy = shift(gray(clips["CP"][-1]), gray(clips["CP2"][0]))
        results["join_px"] = [round(dx, 1), round(dy, 1)]
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    rows = [(a, clips[a]) for a in ("CP", "CE", "CN", "CP2") if a in clips]
    tw, th = 544, 240
    sheet = Image.new("RGB", (tw * 3, (th + 18) * len(rows)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for i, (arm, fr) in enumerate(rows):
        for j, k in enumerate((0, len(fr) // 2, len(fr) - 1)):
            sheet.paste(fr[k].resize((tw, th)), (j * tw, i * (th + 18) + 18))
            dr.text((j * tw + 4, i * (th + 18) + 3), f"{arm} frame {k} · drift max {results['arms'][arm]['drift_max_px']} px · zoom {results['arms'][arm]['zoom_last']}", fill=(230, 230, 230))
    sheet.save(OUT / "sheet.jpg", quality=86)
    for arm in ("CP", "CE", "CN"):
        if arm in clips:
            pv = preview(clips[arm], OUT / f"preview_{arm}.mp4")
            for k in (0, 32, 64):
                pv[k].save(OUT / f"preview_{arm}_{k}.png")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("seconds", "drift_max_px", "zoom_last", "status")} for k, v in results["arms"].items()}), flush=True)
    print("join", results.get("join_px"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
