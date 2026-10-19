"""Spike E25 (proto01_animate 01 §9a, 02 §3; before CA1 builds the Detailed dummy): does Wan Animate follow hands and feet drawn in the
pose guide? One character (CA0's Mara reference, full body, A-pose), two clips from the CC0 starter set with clear hand action
(Idle_Talking_Loop looped; Interact at half speed, then held), each guide drawn twice by ComfyUI's own DWPose drawer
(comfy_extras/pose/keypoint_draw.py): **A** the body only (COCO-18, as the Stage's pose pass today) and **B** the body + both hands
(21 points each) + feet (6). The guide's figure comes straight from the source rig (Rigify DEF- bones, fingers included): a small glTF
evaluator here, no Stage — the question is the model's, not the dummy's. Every guide runs twice (Wan Animate is not deterministic at a
fixed seed, E30a), through the app (its guide route, the Stage's animate method), one GPU job at a time, A and B alternating.

Measured with SDPose (wholebody) on every 6th frame: body PCK@0.1 against the guide's 18 points; **hand PCK** — each guide hand's 21
points against the detected hand of the same side, a hit within 0.2 × the guide hand's box diagonal (≥ 12 px), a missing detection a
miss; the hand detection rate. A contact sheet (guide | result at four times) for the finger counts by eye. Outputs under
engine/spikes/out/e25/ (git-ignored).

    orchestrator/.venv/Scripts/python.exe engine/spikes/e25_hands.py [--runs 2]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
sys.path.insert(0, str(ROOT / "engine" / "spikes"))
OUT = ROOT / "engine" / "spikes" / "out" / "e25"
GLB = Path(os.environ.get("LOOM2_MODELS", "F:/loom2-models")) / "motion" / "quaternius-ual1" / "Animation Library[Standard]" / "Godot" / "AnimationLibrary_Godot_Standard.glb"
REF = ROOT / "engine" / "spikes" / "out" / "ca0" / "refs" / "mara_v2.png"     # CA0's reference: Mara at the market, full body, hands visible
PORT, TOKEN = 8781, "e25"
W, H, FPS, N = 832, 480, 16, 77                                                   # Wan Animate's Draft geometry (/capabilities.stage.animate)
CLIPS = {"talk": ("Idle_Talking_Loop", 1.0, "the woman talks and gestures with her hands"),
         "interact": ("Interact", 0.5, "the woman reaches out and works something with her hands")}
FINGERS = ["thumb", "f_index", "f_middle", "f_ring", "f_pinky"]

_spec = importlib.util.spec_from_file_location("keypoint_draw", ROOT / "engine" / "comfyui" / "comfy_extras" / "pose" / "keypoint_draw.py")
_kd = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_kd)                          # type: ignore[union-attr]
KD = _kd.KeypointDraw()


# ---- a small glTF evaluator: node TRS, LINEAR samplers (slerp for rotations), world positions per frame ---------------------------------
def load_glb(path: Path):
    b = path.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    j = json.loads(b[20:20 + n])
    off = 20 + n
    bin_len = struct.unpack_from("<I", b, off)[0]
    data = b[off + 8: off + 8 + bin_len]
    return j, data


def accessor(j, data, i):
    a = j["accessors"][i]
    v = j["bufferViews"][a["bufferView"]]
    comps = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[a["type"]]
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.frombuffer(data, dtype=np.float32, count=a["count"] * comps, offset=start)
    return arr.reshape(a["count"], comps) if comps > 1 else arr


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2, w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2, w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2])


def qrot(q, v):
    x, y, z, w = q
    u = np.array([x, y, z])
    return 2 * np.dot(u, v) * u + (w * w - np.dot(u, u)) * v + 2 * w * np.cross(u, v)


def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + t * (b - a)
        return r / np.linalg.norm(r)
    th = np.arccos(d)
    return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


class Rig:
    def __init__(self, path: Path):
        self.j, self.data = load_glb(path)
        self.nodes = self.j["nodes"]
        self.parent = {c: i for i, nd in enumerate(self.nodes) for c in nd.get("children", [])}
        self.by_name = {nd.get("name"): i for i, nd in enumerate(self.nodes)}

    def pose(self, anim_name: str, t: float):
        """World positions and rotations of every node at time t (the clip's own channels over the rest TRS)."""
        trs = {i: [np.array(nd.get("translation", [0, 0, 0]), float), np.array(nd.get("rotation", [0, 0, 0, 1]), float), np.array(nd.get("scale", [1, 1, 1]), float)]
               for i, nd in enumerate(self.nodes)}
        anim = next(a for a in self.j["animations"] if a["name"] == anim_name)
        for ch in anim["channels"]:
            s = anim["samplers"][ch["sampler"]]
            times = accessor(self.j, self.data, s["input"])
            vals = accessor(self.j, self.data, s["output"])
            k = int(np.searchsorted(times, t, side="right")) - 1
            k = max(0, min(k, len(times) - 1))
            if k >= len(times) - 1:
                v = vals[-1]
            else:
                w = (t - times[k]) / max(1e-9, times[k + 1] - times[k])
                v = slerp(vals[k], vals[k + 1], w) if ch["target"]["path"] == "rotation" else vals[k] * (1 - w) + vals[k + 1] * w
            slot = {"translation": 0, "rotation": 1, "scale": 2}[ch["target"]["path"]]
            trs[ch["target"]["node"]][slot] = np.array(v, float)
        pos, rot = {}, {}

        def world(i):
            if i in pos:
                return pos[i], rot[i]
            t_, r_, s_ = trs[i]
            if i in self.parent:
                pp, pr = world(self.parent[i])
                pos[i] = pp + qrot(pr, t_)
                rot[i] = qmul(pr, r_)
            else:
                pos[i], rot[i] = t_.copy(), r_.copy()
            return pos[i], rot[i]
        for i in range(len(self.nodes)):
            world(i)
        return pos, rot

    def p(self, pos, name):
        return pos[self.by_name[name]]


def wholebody(rig: Rig, anim: str, t: float, rest_rot):
    """The 134 DWPose points (body 18, feet 6, face 68 unused, right hand 21, left hand 21) in character space (+Z faces the camera)."""
    pos, rot = rig.pose(anim, t)
    P = lambda n: rig.p(pos, n)                                                    # noqa: E731
    kp = np.zeros((134, 3)); sc = np.zeros(134)
    right = P("DEF-upper_arm.R") - P("DEF-upper_arm.L")
    head_i = rig.by_name["DEF-head"]
    hd = qmul(rot[head_i], np.array([-rest_rot[0], -rest_rot[1], -rest_rot[2], rest_rot[3]]))  # the head's turn from rest
    up, fwd = qrot(hd, np.array([0, 1.0, 0])), qrot(hd, np.array([0, 0, 1.0]))
    side = qrot(hd, np.array([-1.0, 0, 0]))
    hp = P("DEF-head")
    body = {0: hp + up * 0.10 + fwd * 0.10, 1: P("DEF-neck"), 2: P("DEF-upper_arm.R"), 3: P("DEF-forearm.R"), 4: P("DEF-hand.R"),
            5: P("DEF-upper_arm.L"), 6: P("DEF-forearm.L"), 7: P("DEF-hand.L"), 8: P("DEF-thigh.R"), 9: P("DEF-shin.R"), 10: P("DEF-foot.R"),
            11: P("DEF-thigh.L"), 12: P("DEF-shin.L"), 13: P("DEF-foot.L"),
            14: hp + up * 0.13 + fwd * 0.085 + side * 0.035, 15: hp + up * 0.13 + fwd * 0.085 - side * 0.035, 16: hp + up * 0.10 + side * 0.08, 17: hp + up * 0.10 - side * 0.08}
    for i, v in body.items():
        kp[i] = v; sc[i] = 1
    for base, s in ((18, "L"), (21, "R")):                                         # feet: big toe, small toe, heel (left first, as COCO-WholeBody)
        toe, foot = P(f"DEF-toe.{s}"), P(f"DEF-foot.{s}")
        f = toe - foot; f[1] = 0; f /= max(1e-6, np.linalg.norm(f))
        med = np.cross(np.array([0, 1.0, 0]), f) * (1 if s == "L" else -1)
        kp[base] = toe + f * 0.05 - med * 0.02; kp[base + 1] = toe + f * 0.03 + med * 0.03; kp[base + 2] = foot - f * 0.06 - np.array([0, 0.07, 0])
        sc[base:base + 3] = 1
    for base, s in ((92, "R"), (113, "L")):
        kp[base] = P(f"DEF-hand.{s}"); sc[base] = 1
        for fi, fn in enumerate(FINGERS):
            pts = [P(f"DEF-{fn}.0{k}.{s}") for k in (1, 2, 3)]
            tip = pts[2] + (pts[2] - pts[1]) * 0.8
            for k, v in enumerate(pts + [tip]):
                kp[base + 1 + fi * 4 + k] = v; sc[base + 1 + fi * 4 + k] = 1
    return kp, sc, right


def project(kp3, cam):
    cy, f, d = cam
    z = d - kp3[:, 2]
    return np.stack([W / 2 + f * kp3[:, 0] / z, H / 2 - f * (kp3[:, 1] - cy) / z], axis=1)


def render_guides(rig: Rig, anim: str, speed: float):
    """Both arms of one clip: frames (A body only, B body + hands + feet) and the body keypoints the app keeps."""
    head_rest = np.array(rig.nodes[rig.by_name["DEF-head"]].get("rotation", [0, 0, 0, 1]), float)
    _, rest_rot = rig.pose(anim, 0.0)
    head_rest = rest_rot[rig.by_name["DEF-head"]]
    dur = max(accessor(rig.j, rig.data, s["input"]).max() for a in rig.j["animations"] if a["name"] == anim for s in a["samplers"])
    frames3 = []
    for i in range(N):
        t = (i / FPS) * speed
        t = t % dur if anim.endswith("_Loop") else min(t, dur)                       # a loop loops; a one-shot holds its last frame
        frames3.append(wholebody(rig, anim, t, head_rest))
    right = frames3[0][2]
    turn_angle = np.arctan2(right[2], right[0])                                    # the figure's right onto −X: rotate about Y
    a = np.pi - turn_angle
    rotY = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    pts = [(kp @ rotY.T, sc) for kp, sc, _ in frames3]
    ys = np.concatenate([p[0][:24, 1] for p in pts])
    cy = (ys.max() + ys.min()) / 2
    d = 4.0
    f = 0.8 * H * d / max(0.5, ys.max() - ys.min())
    outA, outB, body_kp = [], [], []
    for kp, sc in pts:
        xy = project(kp, (cy, f, d))
        full = np.zeros((134, 2)); full[:] = xy
        for arm, out in (("A", outA), ("B", outB)):
            canvas = np.zeros((H, W, 3), np.uint8)
            canvas = KD.draw_wholebody_keypoints(canvas, full, sc, draw_face=False, draw_hands=arm == "B", draw_feet=arm == "B")
            out.append(Image.fromarray(np.asarray(canvas)))
        body_kp.append([[[float(x), float(y), 1] for x, y in xy[:18]]])
        body_kp[-1].append(None)                                                   # (placeholder removed below)
        body_kp[-1].pop()
    hands = [project(kp, (cy, f, d))[92:134].tolist() for kp, _ in pts]
    return outA, outB, body_kp, hands


# ---- the app ---------------------------------------------------------------------------------------------------------------------------
def api(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method, headers={"Content-Type": "application/json", "X-Loom-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def wait_job(job_id, timeout_s=3600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == job_id), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(2)
    raise TimeoutError(job_id)


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def hand_pck(gt_hand: list, pred: list | None, side_ok=True):
    g = np.array(gt_hand, float)
    diag = max(12.0, float(np.linalg.norm(g.max(0) - g.min(0))))
    if not pred:
        return 0, len(g)
    p = np.array(pred, float).reshape(-1, 3)
    hit = sum(1 for k in range(len(g)) if p[k, 2] > 0.3 and np.linalg.norm(p[k, :2] - g[k]) <= 0.2 * diag)
    return hit, len(g)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    a = ap.parse_args()
    for need in (GLB, REF):
        if not need.is_file():
            print(f"missing {need}"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    rig = Rig(GLB)
    guides = {}
    for key, (anim, speed, _) in CLIPS.items():
        A, B, body_kp, hands = render_guides(rig, anim, speed)
        for arm, frames in (("A", A), ("B", B)):
            d = OUT / "guides" / f"{key}_{arm}"
            d.mkdir(parents=True, exist_ok=True)
            for i, im in enumerate(frames):
                im.save(d / f"{i:03d}.png")
        guides[key] = {"body": body_kp, "hands": hands}
        log(f"guides drawn: {key} ({anim} ×{speed}), {N} frames each arm")
    tmp = Path(tempfile.mkdtemp(prefix="loom2-e25-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full", "engine": {"port": 8188}})
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"), env=env,
                            stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    rows = []
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "E25", "size_cap_gb": 20})
        caps = api("GET", "/capabilities")["stage"]["animate"]
        ref = api("POST", "/assets/import", {"paths": [str(REF)]})["items"][0]["id"]
        st = api("POST", "/stages", {"name": "E25"})
        cam = st["cameras"][0]["id"]
        rev = st["revision"]
        assets = {}
        for key in CLIPS:
            for arm in ("A", "B"):
                shas = []
                for p in sorted((OUT / "guides" / f"{key}_{arm}").glob("*.png")):
                    data = p.read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/blobs/{sha}", data=data, method="PUT", headers={"X-Loom-Token": TOKEN}), timeout=60).read()
                    shas.append(sha)
                doc = api("POST", f"/stages/{st['id']}/guide", {"camera_id": cam, "revision": rev, "kind": "pose", "fps": FPS, "size": {"w": W, "h": H},
                                                                 "range": {"start": 0, "end": N - 1}, "frames": shas, "keypoints": guides[key]["body"]})
                rev = doc["revision"]
                assets[(key, arm)] = next(x for x in doc["passes"] if x["camera_id"] == cam)["guides"]["pose"]["asset_id"]
        sys.path.insert(0, str(ROOT / "engine" / "spikes"))
        from e10_stage import pck, sdpose_graph
        from e12_angles import Engine
        eng = Engine("127.0.0.1:8188")
        for run in range(a.runs):
            for key, (anim, speed, prompt) in CLIPS.items():
                for arm in (("A", "B") if run % 2 == 0 else ("B", "A")):
                    recipe = {"kind": "i2v", "model_id": caps["model_id"], "start_asset": ref, "prompt_text": f"{prompt}, plain light grey studio background, steady camera",
                              "frames": N, "fps": FPS, "width": W, "height": H, "preset": "draft", "guide": {"asset_id": assets[(key, arm)], "kind": "pose"}}
                    job = api("POST", "/jobs", {"recipe": recipe})["jobs"][0]
                    j = wait_job(job["id"])
                    row = {"clip": key, "arm": arm, "run": run, "status": j["status"], "wall_s": j.get("wall_s")}
                    if j["status"] != "done":
                        row["error"] = j.get("error"); rows.append(row); log(f"{key} {arm} run {run}: {j['status']} {j.get('error')}"); continue
                    clip_id = j["result"]["clip_id"]
                    frames = sorted((tmp / "proj" / "clips" / clip_id / "master").glob("*.png"))
                    dest = OUT / "results" / f"{key}_{arm}_{run}"
                    dest.mkdir(parents=True, exist_ok=True)
                    bh = bt = hh = ht = det = dtot = 0
                    for idx in range(0, len(frames), 6):
                        im = Image.open(frames[idx])
                        sx, sy = im.size[0] / W, im.size[1] / H
                        hp, _, _ = eng.run(sdpose_graph(eng.upload(frames[idx])))
                        people = json.loads(hp["outputs"]["6"]["text"][0])[0]["people"]
                        figs = [[[x * sx, y * sy, v] for x, y, v in fig] for fig in guides[key]["body"][idx]]
                        h_, t_ = pck(figs, people); bh += h_; bt += t_
                        person = max(people, key=lambda q: sum(q["pose_keypoints_2d"][2::3])) if people else None
                        gh = guides[key]["hands"][idx]
                        for side, sl, field in (("R", slice(0, 21), "hand_right_keypoints_2d"), ("L", slice(21, 42), "hand_left_keypoints_2d")):
                            g = [[x * sx, y * sy] for x, y in gh[sl]]
                            pred = person.get(field) if person else None
                            dtot += 1
                            if pred and sum(1 for c in pred[2::3] if c > 0.3) >= 8:
                                det += 1
                            a_, b_ = hand_pck(g, pred)
                            hh += a_; ht += b_
                    for i in (0, N // 3, 2 * N // 3, N - 1):
                        shutil.copy2(frames[min(i, len(frames) - 1)], dest / f"{i:03d}.png")
                    row.update(clip_id=clip_id, body_pck=round(bh / bt, 3) if bt else None, hand_pck=round(hh / ht, 3) if ht else None,
                               hands_detected=round(det / dtot, 3) if dtot else None)
                    rows.append(row)
                    log(f"{key} {arm} run {run}: body PCK {row['body_pck']}, hand PCK {row['hand_pck']}, hands found {row['hands_detected']}, {j.get('wall_s')} s")
    finally:
        try:
            api("POST", "/shutdown"); time.sleep(1.0)
        except Exception:
            pass
        if orch.poll() is None:
            orch.kill()
        orch_log.close()
    # the contact sheet: per run, guide B | result at four times
    tw, th = 208, 120
    sheet = Image.new("RGB", (8 + (tw + 4) * 8, 8 + (th + 18) * max(1, len(rows))), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for r_i, row in enumerate(rows):
        y = 8 + r_i * (th + 18)
        dr.text((8, y), f"{row['clip']} {row['arm']} run {row['run']} · body {row.get('body_pck')} · hands {row.get('hand_pck')} · found {row.get('hands_detected')}", fill=(230, 230, 230))
        for c_i, i in enumerate((0, N // 3, 2 * N // 3, N - 1)):
            g = Image.open(OUT / "guides" / f"{row['clip']}_{row['arm']}" / f"{i:03d}.png").convert("RGB"); g.thumbnail((tw, th))
            sheet.paste(g, (8 + c_i * 2 * (tw + 4), y + 14))
            rp = OUT / "results" / f"{row['clip']}_{row['arm']}_{row['run']}" / f"{i:03d}.png"
            if rp.is_file():
                r_ = Image.open(rp).convert("RGB"); r_.thumbnail((tw, th)); sheet.paste(r_, (8 + (c_i * 2 + 1) * (tw + 4), y + 14))
    sheet.save(OUT / "sheet.jpg", quality=88)
    with (OUT / "results.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%d %H:%M"), "rows": rows}) + "\n")
    for arm in ("A", "B"):
        rs = [r for r in rows if r["arm"] == arm and r.get("body_pck") is not None]
        if rs:
            log(f"arm {arm}: body PCK mean {np.mean([r['body_pck'] for r in rs]):.3f}, hand PCK mean {np.mean([r['hand_pck'] for r in rs]):.3f}, hands found {np.mean([r['hands_detected'] for r in rs]):.3f} over {len(rs)} runs")
    log(f"sheet: {OUT / 'sheet.jpg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
