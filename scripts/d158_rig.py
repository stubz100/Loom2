"""D158 rig (E42's follow-up, proto01_UI2 04 §4): a turned figure performed from behind through the app's own route, on the GPU, alone.

A — Stay, as the app makes it now: a new final for the walkthrough's *Stay* (on a copy of The Last Ferry), its passes drawn by today's Stage
    in headless Edge (scripts/d158_make_final.cjs), then Ines's layer performed by `POST /finals/{fid}/layers/{lid}/run` — the reply says
    from behind and the back view; the guide's first frame has no nose; the take's away frames carry no frontal face (SCRFD).
B — a turning figure: a copy of Stay's stage where Ines stands and turns from the camera to away over frames 0–36 and holds, as a shot of its
    own; the same route. Its frames are split by the final's own keypoints into the ones facing the camera and the ones facing away: a
    face on the first (the guide keeps it there), none on the second — with the back view as the batch's reference (mostly away).

Bars (journal, set before the run): both takes done; A: from_behind and back_view, no nose on the guide's first frame, a face on ≤ 20 % of
the away frames; B: from_behind, a face on ≤ 20 % of its away frames and on ≥ 50 % of the frames facing the camera.

    orchestrator/.venv/Scripts/python.exe scripts/d158_rig.py [--parts A,B] [--state <scratch state dir>]

The orchestrator (on 8766, the copy as its project) and the preview server (1420, `npm run build` first) are started here and stopped at
the end; the engine starts with the first job and is stopped too. One GPU job at a time (rule 10): the queue runs them in turn.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator")]
PROJECT = Path("F:/loom2-projects/_u3-check/last-ferry-copy")
STAY = "sht_6d6815a0"
PORT, TOKEN = 8766, "devtoken"
OUT = ROOT / "engine" / "spikes" / "out" / "d158"
BAR_AWAY, BAR_TOWARD = 0.2, 0.5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="A,B")
    ap.add_argument("--state", default=str(Path(os.environ.get("TEMP", ".")) / "loom2-d158-state"))
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")                              # the bars print ≤ / ≥ (a Windows console is cp1252)
    from loom2.finals import faces_away
    from loom2.config import AppState
    from loom2.tools.facesim import FaceSim
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "project": str(PROJECT), "parts": {}, "failures": []}
    H = {"X-Loom-Token": TOKEN}
    api = httpx.Client(base_url=f"http://127.0.0.1:{PORT}", headers=H, timeout=120)

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            results["failures"].append(text)

    def save() -> None:
        (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    env = {**os.environ, "LOOM2_TOKEN": TOKEN}
    log = (OUT / "orchestrator.log").open("a", encoding="utf-8")
    orch = subprocess.Popen([str(ROOT / "orchestrator" / ".venv" / "Scripts" / "python.exe"), "-m", "loom2.main", "--port", str(PORT), "--state", a.state, "--project", str(PROJECT)],
                            cwd=str(ROOT / "orchestrator"), env=env, stdout=log, stderr=subprocess.STDOUT)
    preview = subprocess.Popen("npx vite preview --host 127.0.0.1 --port 1420 --strictPort", cwd=str(ROOT / "frontend"), shell=True, stdout=log, stderr=subprocess.STDOUT)
    fs = FaceSim(AppState().models_root)
    try:
        for _ in range(120):
            try:
                api.get("/project").raise_for_status()
                break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        time.sleep(3)

        def faces(frames: list[Path], keep: list[bool]) -> dict:
            sc = [max((x.score for x in fs.detect(np.asarray(Image.open(f).convert("RGB")), thresh=0.5)), default=0.0) for f, k in zip(frames, keep) if k]
            n = len(sc)
            return {"frames": n, "with_face": sum(1 for s in sc if s >= 0.5), "share": round(sum(1 for s in sc if s >= 0.5) / n, 3) if n else None}

        def make_final(shot: str, stage: str) -> dict:
            url = f"http://127.0.0.1:1420/?token={TOKEN}&port={PORT}&ui=2#shots/{shot}/performance"
            r = subprocess.run(["node", str(ROOT / "scripts" / "d158_make_final.cjs"), url, str(PORT), TOKEN, stage], capture_output=True, text=True, timeout=600)
            print(r.stdout.strip()[-400:], r.stderr.strip()[-400:], flush=True)
            if r.returncode:
                raise RuntimeError("the final was not made")
            items = api.get("/finals", params={"stage_id": stage}).json()["items"]
            return sorted(items, key=lambda f: f["created_at"])[-1]

        def perform(fin: dict) -> tuple[dict, dict, float]:
            lid = next(x["id"] for x in fin["layers"] if x["kind"] == "figure")
            t0 = time.time()
            r = api.post(f"/finals/{fin['id']}/layers/{lid}/run", json={})
            r.raise_for_status()
            reply = r.json()
            while time.time() - t0 < 3600:
                lay = next(x for x in api.get(f"/finals/{fin['id']}").json()["layers"] if x["id"] == lid)
                if lay["status"] in ("done", "failed"):
                    break
                time.sleep(5)
            return reply, lay, time.time() - t0

        def frames_of(fid: str, lid: str) -> list[Path]:
            return sorted((PROJECT / "finals" / fid / lid / "frames").glob("*.png"))

        def keypoints(fid: str, lid: str) -> list:
            p = PROJECT / "finals" / fid / lid / "keypoints.json"
            return json.loads(p.read_text(encoding="utf-8"))["frames"] if p.is_file() else []

        rows: list[tuple[str, list[Image.Image]]] = []
        parts = [x.strip() for x in a.parts.split(",") if x.strip()]
        stay = next(s for s in api.get("/story/shots").json()["items"] if s["id"] == STAY)
        sv = next(v for v in stay["versions"] if v["id"] == stay["current"])
        if "A" in parts:
            fin = make_final(STAY, sv["stage_id"])
            lid = next(x["id"] for x in fin["layers"] if x["kind"] == "figure")
            kps = keypoints(fin["id"], lid)
            pose0 = PROJECT / "finals" / fin["id"] / lid / "pose" / "0000.png"
            nose = kps[0][0] if kps else None
            px = np.asarray(Image.open(pose0).convert("RGB"))[int(nose[1]), int(nose[0])].tolist() if nose and pose0.is_file() else None
            reply, lay, secs = perform(fin)
            fr = frames_of(fin["id"], lid)
            away = [faces_away(k) for k in kps][:len(fr)]
            m = faces(fr, away)
            results["parts"]["A"] = {"final": fin["id"], "reply": reply, "status": lay["status"], "error": lay.get("error"), "seconds": round(secs), "nose_pixel": px,
                                     "away_frames": sum(away), "faces_away": m}
            check(lay["status"] == "done", f"A: Stay's take done ({len(fr)} frames, {round(secs)} s)")
            check(bool(reply.get("from_behind")) and bool(reply.get("back_view")), f"A: from behind {reply.get('from_behind')}, the back view {reply.get('back_view')}")
            check(px is not None and sum(px) == 0, f"A: no nose on the guide's first frame (the pixel at the nose {px})")
            check(m["share"] is not None and m["share"] <= BAR_AWAY, f"A: a face on {m['with_face']} of {m['frames']} away frames (≤ {BAR_AWAY})")
            if fr:
                rows.append((f"A Stay · a face on {m['with_face']}/{m['frames']} away frames", [Image.open(fr[i]) for i in (0, len(fr) // 3, 2 * len(fr) // 3, len(fr) - 1)]))
            save()
        if "B" in parts:
            src = api.get(f"/stages/{sv['stage_id']}").json()
            ines = next(o for o in src["objects"] if o["kind"] == "mannequin" and o.get("profile_id"))
            cam = next(c for c in src["cameras"] if c["id"] == sv["camera_id"])
            keys0 = (src.get("keyframes", {}).get("objects", {}).get(ines["id"]) or [])
            pos = (sorted(keys0, key=lambda k: k["frame"])[0]["transform"]["pos"] if keys0 else ines["transform"]["pos"])
            toward = math.degrees(math.atan2(cam["pos"][0] - pos[0], cam["pos"][2] - pos[2]))
            key = lambda f, yaw: {"frame": f, "ease": "ease", "transform": {"pos": list(pos), "rot": [0.0, yaw, 0.0], "scale": ines["transform"]["scale"]}, "pose": {"preset": "stand", "joints": {}}}  # noqa: E731
            st = api.post("/stages", json={"name": "D158 turn"}).json()
            body = {"revision": st["revision"], "objects": src["objects"], "cameras": src["cameras"], "active_camera": cam["id"], "range": src["range"], "size": src["size"],
                    "keyframes": {"camera": src.get("keyframes", {}).get("camera", {}), "objects": {ines["id"]: [key(0, toward), key(36, toward + 180.0), key(src["range"]["end"], toward + 180.0)]}},
                    "tracks": {}}
            st = api.put(f"/stages/{st['id']}", json=body).json()
            node = api.post("/story/flow/shots", json={"title": "D158 turn", "scene": "new"}).json()
            api.put(f"/story/shots/{node['shot_id']}/versions/v1/source", json={"stage_id": st["id"], "camera_id": cam["id"]}).raise_for_status()
            fin = make_final(node["shot_id"], st["id"])
            lid = next(x["id"] for x in fin["layers"] if x["kind"] == "figure")
            kps = keypoints(fin["id"], lid)
            reply, lay, secs = perform(fin)
            fr = frames_of(fin["id"], lid)
            away = [faces_away(k) for k in kps][:len(fr)]
            ma, mt = faces(fr, away), faces(fr, [not x for x in away])
            results["parts"]["B"] = {"final": fin["id"], "shot": node["shot_id"], "reply": reply, "status": lay["status"], "error": lay.get("error"), "seconds": round(secs),
                                     "away_frames": sum(away), "toward_frames": len(away) - sum(away), "faces_away": ma, "faces_toward": mt}
            check(lay["status"] == "done", f"B: the turn's take done ({len(fr)} frames, {round(secs)} s)")
            check(bool(reply.get("from_behind")), f"B: performed from behind (mostly away: {sum(away)} of {len(away)})")
            check(ma["share"] is not None and ma["share"] <= BAR_AWAY, f"B: a face on {ma['with_face']} of {ma['frames']} away frames (≤ {BAR_AWAY})")
            check(mt["share"] is not None and mt["share"] >= BAR_TOWARD, f"B: a face on {mt['with_face']} of {mt['frames']} frames facing the camera (≥ {BAR_TOWARD})")
            if fr:
                rows.append((f"B turn · facing: a face on {mt['with_face']}/{mt['frames']} · away: {ma['with_face']}/{ma['frames']}", [Image.open(fr[i]) for i in (0, len(fr) // 5, 2 * len(fr) // 5, len(fr) - 1)]))
            save()
        if rows:
            w, h = 424, 240
            im = Image.new("RGB", (w * 4, (h + 22) * len(rows)), (24, 24, 24))
            d = ImageDraw.Draw(im)
            for i, (label, ims) in enumerate(rows):
                d.text((6, i * (h + 22) + 4), label, fill=(230, 230, 230))
                for j, x in enumerate(ims):
                    im.paste(x.convert("RGB").resize((w, h)), (j * w, i * (h + 22) + 22))
            im.save(OUT / "sheet.jpg", quality=88)
    finally:
        try:
            api.post("/engine/stop")
        except Exception:  # noqa: BLE001
            pass
        for p in (orch, preview):
            try:
                if p is preview:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                else:
                    p.terminate()
                    p.wait(timeout=30)
            except Exception:  # noqa: BLE001
                p.kill()
        log.close()
        save()
    return 0 if not results["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
