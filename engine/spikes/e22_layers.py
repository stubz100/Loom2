"""E22 — complex, different actions for both characters at once: one shared clip vs layers (journal 2026-10-17 20:55; D94, E21).

The shot is E21's (the passes in engine/spikes/out/e21/passes: the `room` set, camera (0, 1.05, 4.3) fov 30°, Mara `stand` at x −1 turned
+35°, Ines `arms_crossed` at x +1 turned −35°), in a scratch copy of E21's project. Each character gets a multi-beat action over ≈ 5 s:

  Mara (left)   M1 walks two steps forward towards the middle of the room · M2 stops and raises both arms high above her head ·
                M3 lowers them and puts her hands on her hips
  Ines (right)  I1 uncrosses her arms · I2 takes one step back · I3 points with an outstretched arm at the window on the far left ·
                I4 turns her head to look at the window

  (a)     Stage clay still (Klein 9B, both figures bound, D93 C / D94) → one Wan 2.2 I2V Draft clip, both actions in one prompt.
  (a_ltx) the same stills → one LTX-2.3 distilled Draft clip (1024×576, 121 f @ 24 fps), the same prompt.
  (b)     layers, no post-processing: E21's plate → each character into its own copy of the plate *facing as blocked* (Klein 9B Fill-Match +
          references, the facing in the prompt; a copy whose face does not turn the blocked way — FaceSim's 5 keypoints, nose offset from
          the eye midpoint ÷ eye distance, |yaw| ≥ 0.4 with the right sign — is redone with another seed) → each copy animated alone with
          only its own action → per-frame SAM 3 masks by text ("woman", per-frame detection: the character walks, a fixed box would not
          follow) → stacked over the plate with a plain feathered alpha (no colour lock, no shadow zone, no video pass).

  orchestrator/.venv/Scripts/python.exe engine/spikes/e22_layers.py run [--seeds 3] [--ltx]
  orchestrator/.venv/Scripts/python.exe engine/spikes/e22_layers.py score
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e21_layers as e21  # noqa: E402
from e21_layers import (H, W, FRAMES, FPS, Engine, Orch, Vram, arr, blur, copy_graph, copy_mask, dilate, download_all, encode_mp4,  # noqa: E402
                        fit_cover, frames_of, load_mask, port_busy, roster, save_mask, silhouettes)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "engine" / "spikes" / "out" / "e22"
E21 = REPO / "engine" / "spikes" / "out" / "e21"
STATE = OUT / "state.json"
MODELS = Path("F:/loom2-models")
SRC = Path("F:/loom2-projects/e21-layers-20261017-190731")
W0, H0 = 1280, 720
SEED0 = 20261017
ENGINE_PORT = 8188
LTX = {"w": 1024, "h": 576, "frames": 121, "fps": 24}

SCENE = e21.SCENE
MARA_D, INES_D = e21.MARA_D, e21.INES_D
MARA_ACT = ("walks two steps forward towards the middle of the room, stops, raises both arms high above her head, then lowers them and "
            "puts her hands on her hips")
INES_ACT = ("uncrosses her arms, takes one step back, then points with her outstretched arm at the window on the far left of the room and "
            "turns her head to look at it")
BEATS = {"Mara": ["M1 walks two steps towards the middle", "M2 raises both arms above her head", "M3 lowers them, hands on hips"],
         "Ines": ["I1 uncrosses her arms", "I2 one step back", "I3 points at the window (left) with an outstretched arm", "I4 turns her head to the window"]}
STILL_TEXT = (f"Mara stands with her arms relaxed at her sides, turned towards Ines; Ines stands with her arms crossed, turned towards Mara. {SCENE}")
P_A = (f"Static camera, a wide two-shot in a quiet room; two women face each other a few metres apart. The woman on the left, {MARA_D}, "
       f"{MARA_ACT}. At the same time the woman on the right, {INES_D}, {INES_ACT}. They do not touch; the camera does not move.")
P_L = (f"Static camera, a quiet room. {MARA_D[0].upper() + MARA_D[1:]}, turned towards someone off-screen to the right, {MARA_ACT}. "
       f"The camera does not move.")
P_R = (f"Static camera, a quiet room. {INES_D[0].upper() + INES_D[1:]}, turned towards someone off-screen to the left, {INES_ACT}. "
       f"The camera does not move.")
CHARS = {"L": {"name": "Mara", "desc": MARA_D, "prompt": P_L, "sign": 1,
               "pose": ("standing, her arms relaxed at her sides, her body turned three-quarters to the right towards someone off-screen on the right, "
                        "her face in three-quarter view looking to the right, not at the camera")},
         "R": {"name": "Ines", "desc": INES_D, "prompt": P_R, "sign": -1,
               "pose": ("standing with her arms crossed, her body turned three-quarters to the left towards someone off-screen on the left, "
                        "her face in three-quarter view looking to the left, not at the camera")}}
YAW_MIN = 0.4
SAM_ONE, SAM_TWO = "woman", "woman:2"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")


def record(s: dict, step: str, wall: float, vram: float, **extra) -> None:
    s.setdefault("steps", {})[step] = {"wall_s": round(wall, 1), "vram_peak_gb": vram, **extra}
    save_state(s)
    log(f"  {step}: {wall:.1f} s, peak {vram} GB {json.dumps(extra)[:200] if extra else ''}")


def face_yaw(fs, im: np.ndarray) -> tuple[float | None, int]:
    """The largest face's turn: (nose x − eye-midpoint x) ÷ eye distance; > 0 = turned to the viewer's right. E21: its (a) stills ±1.0,
    its copies 0.01–0.08 (frontal)."""
    fl = fs.detect(im.astype(np.uint8))
    if not fl:
        return None, 0
    f = max(fl, key=lambda x: x.area)
    k = np.asarray(f.kps)
    return float((k[2, 0] - (k[0, 0] + k[1, 0]) / 2) / max(1e-3, abs(k[1, 0] - k[0, 0]))), len(fl)


def sam_text_graph(ros, video_name: str, text: str, prefix: str) -> dict:
    """SAM3_Detect by text on every frame (per-frame detection: follows a walking character); `woman:2` = up to two, union."""
    _, ckpt = ros.require("sam3")
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "LoadVideo", "inputs": {"file": video_name}},
        "3": {"class_type": "GetVideoComponents", "inputs": {"video": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["1", 1]}},
        "5": {"class_type": "SAM3_Detect", "inputs": {"model": ["1", 0], "image": ["3", 0], "conditioning": ["4", 0], "threshold": 0.4,
                                                      "refine_iterations": 2, "individual_masks": False}},
        "7": {"class_type": "MaskToImage", "inputs": {"mask": ["5", 0]}},
        "99": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": prefix}},
    }


def plain_merge(layers: list[dict], plate: np.ndarray, dest: Path, n: int) -> dict:
    """layers far → near: [{frames, sam}]. alpha = the SAM mask feathered ≈ 2 px; a frame whose mask lost > 60 % of the clip's median area
    (a missed detection) reuses the previous frame's mask. Nothing else: no colour lock, no shadow zone, no video pass."""
    dest.mkdir(parents=True, exist_ok=True)
    alphas = np.zeros((len(layers), n, H, W), dtype=np.float16)
    held = [0] * len(layers)
    masks = [[load_mask(p) for p in L["sam"][:n]] for L in layers]
    med = [float(np.median([m.mean() for m in ms])) for ms in masks]
    prev: list[np.ndarray | None] = [None] * len(layers)
    for t in range(n):
        out = plate.copy()
        for k, L in enumerate(layers):
            m = masks[k][t]
            if m.mean() < 0.4 * med[k] and prev[k] is not None:
                m = prev[k]; held[k] += 1
            prev[k] = m
            a = np.clip(blur(m, 1), 0, 1)
            out = out * (1 - a[..., None]) + arr(L["frames"][t]) * a[..., None]
            alphas[k, t] = a
        Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save(dest / f"{t:04d}.png")
    np.savez_compressed(dest.parent / f"{dest.name}_alpha.npz", alpha=alphas)
    return {"held_frames": held}


def run(a: argparse.Namespace) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    s = load_state()
    if port_busy(ENGINE_PORT) and not a.adopt:
        print("engine port busy — stop the running engine first (or --adopt)"); return 2
    seeds = [SEED0 + i for i in range(a.seeds)]
    if "project" not in s:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        s["project"] = str(Path(a.projects) / f"e22-action-{stamp}")
        s["state_dir"] = str(Path(a.projects) / f"_state-e22-action-{stamp}")
        shutil.copytree(SRC, s["project"])                        # a scratch copy: E21's project stays as it was
        e21s = json.loads((E21 / "state.json").read_text(encoding="utf-8"))
        s["stage_id"], s["passes_both"] = e21s["stage_id"], e21s["passes_both"]
        s["prompts"] = {"still": STILL_TEXT, "a": P_A, "L": P_L, "R": P_R}
        save_state(s)
    for d in ("stills", "masks", "heroes"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(E21 / "stills" / "plate.png", OUT / "stills" / "plate.png")
    for k in CHARS:
        shutil.copyfile(E21 / "heroes" / f"{k}.png", OUT / "heroes" / f"{k}.png")
    project = Path(s["project"])
    sils = silhouettes()
    for k, m in sils.items():
        save_mask(copy_mask(m), OUT / "masks" / f"copymask_{k}.png")
    from loom2.tools.facesim import FaceSim
    fs = FaceSim(MODELS)
    o = Orch(Path(s["state_dir"]), a.port).start()
    vram = Vram(ENGINE_PORT)
    ros = roster()
    try:
        r = o.http.post("/project/open", json={"path": str(project)})
        assert r.status_code == 200, r.text[:200]
        profs = {p["name"]: p for p in o.http.get("/story/profiles").json()["items"]}
        mara, ines = profs["Mara"], profs["Ines"]
        prof = {"L": mara, "R": ines}
        assert o.http.get(f"/stages/{s['stage_id']}").status_code == 200
        base = {"kind": "stage_shot", "stage_id": s["stage_id"], "camera_id": "cam_1", "method": "clay", "width": W0, "height": H0}

        def job(recipe: dict, step: str, timeout: float = 3600) -> dict:
            vram.lap()
            j = o.http.post("/jobs", json={"recipe": recipe}).json()["jobs"][0]
            j = o.wait_job(j["id"], {"done", "failed", "cancelled"}, timeout)
            if j["status"] != "done":
                raise RuntimeError(f"{step}: {j['status']} {j.get('error')}")
            record(s, step, float(j.get("wall_s") or 0), vram.lap())
            return j

        def fetch_asset(aid: str, p: Path) -> Path:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(o.http.get(f"/assets/{aid}/file").content)
            return p

        def fetch_clip(cid: str, dest: Path) -> None:
            rec = o.http.get(f"/clips/{cid}").json()
            src = project / rec["master_dir"]
            dest.mkdir(parents=True, exist_ok=True)
            for i, f in enumerate(sorted(src.glob("*.png"))):
                shutil.copyfile(f, dest / f"{i:04d}.png")

        # ---- (a) stills: the clay method, both figures bound (D93 C), the start state in words
        mentions = [{"profile_id": mara["id"], "figure": "fig_left"}, {"profile_id": ines["id"], "figure": "fig_right"}]
        for sd in seeds:
            p = OUT / "stills" / f"a_s{sd}.png"
            if not p.is_file():
                rec = {**base, "passes": s["passes_both"], "prompt_text": STILL_TEXT, "mentions": mentions, "bind_refs": True, "seeds": [sd]}
                if "prompt_a_still" not in s:
                    s["prompt_a_still"] = o.http.post("/recipes/preview", json={"recipe": rec}).json()["params"]["prompt"]
                j = job(rec, f"a_still_s{sd}")
                s.setdefault("assets", {})[f"a_s{sd}"] = j["result"]["asset_ids"][0]
                fetch_asset(j["result"]["asset_ids"][0], p)
            im = arr(p)
            s.setdefault("yaw", {})[f"a_s{sd}"] = [round(face_yaw(fs, im[:, : W0 // 2])[0] or 0, 2), round(face_yaw(fs, im[:, W0 // 2:])[0] or 0, 2)]
        save_state(s)
        if not port_busy(ENGINE_PORT):
            o.http.post("/engine/start", timeout=300)
            t0 = time.time()
            while not port_busy(ENGINE_PORT) and time.time() - t0 < 300:
                time.sleep(2)
            time.sleep(5)
        e = Engine(f"127.0.0.1:{ENGINE_PORT}")
        # ---- (b) each character into its own copy of the plate, facing as blocked; redo a copy that faces the camera
        pa = arr(OUT / "stills" / "plate.png")
        s.setdefault("copies", {})
        for k, c in CHARS.items():
            names = [e.upload(p) for p in sorted((E21 / "refs").glob(f"{k}_*.png"))]
            clay = arr(e21.PASSES / f"{e21.CHARS[k]['pass']}_clay.png")
            src = pa.copy()
            src[sils[k]] = clay[sils[k]]
            sp = OUT / "copies" / f"src_{k}.png"
            sp.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(src.astype(np.uint8)).save(sp)
            img_name, mask_name = e.upload(sp), e.upload(OUT / "masks" / f"copymask_{k}.png")
            prompt = (f"Replace the grey clay mannequin in image 1 with the woman shown in image 2 and image 3: {c['desc']}, {c['pose']}, at exactly "
                      f"the mannequin's position, size and pose. She stands on the floor and casts a soft shadow on it. Keep everything else in image 1 "
                      f"exactly as it is: the room, the light, the camera.")
            s["prompts"][f"copy_{k}"] = prompt
            picked = s["copies"].setdefault(k, [])
            tries = s.setdefault("copy_tries", {}).setdefault(k, [])
            cs = SEED0 + 300
            while len(picked) < len(seeds) and cs < SEED0 + 300 + a.copy_tries:
                p = OUT / "copies" / f"{k}_c{cs}.png"
                if not p.is_file():
                    g = copy_graph(ros, cs, img_name, mask_name, names, prompt, f"e22/copy_{k}_c{cs}")
                    vram.lap()
                    h, wall, ex = e.run(g, timeout=1800)
                    e.image(h, "99").save(p)
                    record(s, f"copy_{k}_c{cs}", wall, vram.lap(), exec_s=round(ex, 1))
                if cs not in [t["seed"] for t in tries]:
                    y, nf = face_yaw(fs, arr(p))
                    ok = y is not None and nf == 1 and y * c["sign"] >= YAW_MIN
                    tries.append({"seed": cs, "yaw": None if y is None else round(y, 2), "faces": nf, "ok": ok})
                    if ok:
                        picked.append(cs)
                    log(f"  copy {k} c{cs}: yaw {y}, faces {nf} → {'ok' if ok else 'redo'}")
                    save_state(s)
                cs += 1
            if len(picked) < len(seeds):
                raise RuntimeError(f"copies {k}: only {len(picked)} of {a.copy_tries} face as blocked")
        # ---- clips: (a) and each copy, Wan 2.2 I2V Draft through the app; (a_ltx) LTX-2.3 Draft
        i2v = {"kind": "i2v", "model_id": "wan22-i2v-high-fp8", "frames": FRAMES, "fps": FPS, "width": W, "height": H, "preset": "draft"}
        ltx = {"kind": "i2v", "model_id": "ltx23-distilled-fp8", "frames": LTX["frames"], "fps": LTX["fps"], "width": LTX["w"], "height": LTX["h"], "preset": "draft"}
        todo = [(f"a_s{sd}", OUT / "stills" / f"a_s{sd}.png", P_A, sd, i2v) for sd in seeds]
        for i, sd in enumerate(seeds):
            for k in CHARS:
                todo.append((f"{k}_s{sd}", OUT / "copies" / f"{k}_c{s['copies'][k][i]}.png", CHARS[k]["prompt"], sd, i2v))
        if a.ltx:
            todo += [(f"altx_s{sd}", OUT / "stills" / f"a_s{sd}.png", P_A, sd, ltx) for sd in seeds[: a.ltx_seeds]]
        for name, still, prompt, sd, base_i2v in todo:
            dest = OUT / "clips" / name
            if len(frames_of(dest)) >= base_i2v["frames"]:
                continue
            key = f"a_s{sd}" if name.startswith("a") else f"copy_{name}"
            aid = s.get("assets", {}).get(key)
            if not aid:
                aid = o.http.post("/assets/import", json={"paths": [str(still)], "suite": "import"}).json()["items"][0]["id"]
                s.setdefault("assets", {})[key] = aid
                save_state(s)
            j = job({**base_i2v, "start_asset": aid, "prompt_text": prompt, "seeds": [sd]}, f"clip_{name}")
            s.setdefault("clips", {})[name] = j["result"]["clip_id"]
            fetch_clip(j["result"]["clip_id"], dest)
        # ---- SAM 3 by text on every layer clip (the alpha)
        plate832 = np.asarray(fit_cover(Image.fromarray(pa.astype(np.uint8)))).astype(np.float32)
        np.save(OUT / "plate832.npy", plate832)

        def sam(name: str, src_dir: Path, text: str) -> None:
            dest = OUT / "sam" / name
            fr = frames_of(src_dir)
            if len(frames_of(dest)) >= len(fr):
                return
            mp4 = OUT / "sam" / f"{name}_src.mp4"
            mp4.parent.mkdir(parents=True, exist_ok=True)
            encode_mp4(fr, mp4, fps=FPS, crf=10)
            g = sam_text_graph(ros, e.upload(mp4), text, f"e22/sam_{name}")
            vram.lap()
            h, wall, ex = e.run(g, timeout=1800)
            download_all(e, h, "99", dest)
            record(s, f"sam_{name}", wall, vram.lap(), exec_s=round(ex, 1))

        for sd in seeds:
            for k in CHARS:
                sam(f"{k}_s{sd}", OUT / "clips" / f"{k}_s{sd}", SAM_ONE)
        # ---- (b) the plain stack: Ines (far) then Mara (near — she walks towards the camera's side of the room)
        for sd in seeds:
            dest = OUT / "merged" / f"b_s{sd}"
            n = min(len(frames_of(OUT / "clips" / f"L_s{sd}")), len(frames_of(OUT / "clips" / f"R_s{sd}")))
            if len(frames_of(dest)) >= n:
                continue
            layers = [{"frames": frames_of(OUT / "clips" / f"{k}_s{sd}"), "sam": frames_of(OUT / "sam" / f"{k}_s{sd}")} for k in ("R", "L")]
            t0 = time.time()
            info = plain_merge(layers, plate832, dest, n)
            record(s, f"merge_b_s{sd}", time.time() - t0, 0.0, **info)
        # ---- SAM 3 (up to two women, union) on the two-character clips — the measurement masks, the same method for every arm
        for sd in seeds:
            sam(f"a_s{sd}", OUT / "clips" / f"a_s{sd}", SAM_TWO)
            sam(f"b_s{sd}", OUT / "merged" / f"b_s{sd}", SAM_TWO)
            if a.ltx and frames_of(OUT / "clips" / f"altx_s{sd}"):
                sam(f"altx_s{sd}", OUT / "clips" / f"altx_s{sd}", SAM_TWO)
    finally:
        vram.stop = True
        o.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "score"])
    ap.add_argument("--projects", default="F:/loom2-projects")
    ap.add_argument("--port", type=int, default=8775)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--copy-tries", type=int, default=10)
    ap.add_argument("--ltx", action="store_true")
    ap.add_argument("--ltx-seeds", type=int, default=3)
    ap.add_argument("--adopt", action="store_true")
    ap.add_argument("--best-a", type=int, default=0)
    ap.add_argument("--best-b", type=int, default=0)
    ap.add_argument("--best-ltx", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "run":
        return run(a)
    from e22_score import score
    return score(a)


if __name__ == "__main__":
    raise SystemExit(main())
