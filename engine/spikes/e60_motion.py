"""E60 (D185, propo02 04 §7, 05 Q7): text-to-motion on the mannequin — the measurement.

A story motion written in words ("walks on, looks back over her shoulder") made into a clip the Library's animation bench plays on the
mannequin. The model is LY Corporation's CMDM (CVPR 2026; the code CC0, the weights Apache-2.0, trained on HumanML3D — AMASS-derived,
so under D185 this is a measurement only: the weights live in F:/loom2-models/_spikes/e60 and go after). It runs on the CPU in the
spike's own Python 3.10 venv (engine/spikes/out/e60/.venv): a 300 MB VAE and a 300 MB causal DiT with CLIP ViT-B/32 as the text encoder;
no GPU job, nothing on the queue.

The model's output is HumanML3D's 22 joints as positions at 20 fps (Y up, metres, the pelvis first). loom2's motion library reads glb
files and retargets a Mixamo-named rig (motion/retarget.ts RIGS.mixamo) — so each sample becomes a glb with a Mixamo-named skeleton whose
rest pose is a T-pose at the sample's own limb lengths and whose animation is the per-bone shortest-arc rotation from the rest direction to
the frame's, the hips carrying the root motion. The retargeter reads bone directions, so the twist left unset costs nothing it uses.
Outputs under engine/spikes/out/e60/: <name>.npy (the joints), <name>.glb, sheet-<name>.png (six stick-figure frames), result.json.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e60_motion.py            (generate every prompt, then convert)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e60_motion.py --convert  (the glbs and sheets from npys made already)
"""
from __future__ import annotations

import base64
import csv
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "engine" / "spikes" / "out" / "e60"
CMDM = OUT / "CMDM"
VENV_PY = OUT / ".venv" / "Scripts" / "python.exe"
WEIGHTS = Path("F:/loom2-models/_spikes/e60/checkpoints")
FPS = 20

# the story motions asked: the plan's line first (propo02 05 Q7), then two the storyboard would ask for
PROMPTS = [
    ("walks_on_looks_back", "a person walks forward, then looks back over their shoulder while walking on.", 120),
    ("stops_and_waves", "a person walks forward, stops, and waves with the right hand.", 120),
    ("sits_down", "a person walks to a chair and sits down.", 120),
]

# HumanML3D's 22 joints → Mixamo's names and the tree (parent index), the bone's rest direction in the T-pose
J = {"Hips": 0, "LeftUpLeg": 1, "RightUpLeg": 2, "Spine": 3, "LeftLeg": 4, "RightLeg": 5, "Spine1": 6, "LeftFoot": 7, "RightFoot": 8, "Spine2": 9,
     "LeftToeBase": 10, "RightToeBase": 11, "Neck": 12, "LeftShoulder": 13, "RightShoulder": 14, "Head": 15, "LeftArm": 16, "RightArm": 17,
     "LeftForeArm": 18, "RightForeArm": 19, "LeftHand": 20, "RightHand": 21}
PARENT = {"Hips": None, "Spine": "Hips", "Spine1": "Spine", "Spine2": "Spine1", "Neck": "Spine2", "Head": "Neck",
          "LeftShoulder": "Spine2", "LeftArm": "LeftShoulder", "LeftForeArm": "LeftArm", "LeftHand": "LeftForeArm",
          "RightShoulder": "Spine2", "RightArm": "RightShoulder", "RightForeArm": "RightArm", "RightHand": "RightForeArm",
          "LeftUpLeg": "Hips", "LeftLeg": "LeftUpLeg", "LeftFoot": "LeftLeg", "LeftToeBase": "LeftFoot",
          "RightUpLeg": "Hips", "RightLeg": "RightUpLeg", "RightFoot": "RightLeg", "RightToeBase": "RightFoot"}
CHILD = {p: c for c, p in PARENT.items() if p is not None and c not in ("LeftShoulder", "RightShoulder", "LeftUpLeg", "RightUpLeg")}
CHILD.update({"Spine2": "Neck", "Hips": "Spine"})
# the T-pose: where each bone points (unit), the limb lengths from the sample
REST_DIR = {"Hips": (0, 1, 0), "Spine": (0, 1, 0), "Spine1": (0, 1, 0), "Spine2": (0, 1, 0), "Neck": (0, 1, 0), "Head": (0, 1, 0),
            "LeftShoulder": (1, 0, 0), "LeftArm": (1, 0, 0), "LeftForeArm": (1, 0, 0), "LeftHand": (1, 0, 0),
            "RightShoulder": (-1, 0, 0), "RightArm": (-1, 0, 0), "RightForeArm": (-1, 0, 0), "RightHand": (-1, 0, 0),
            "LeftUpLeg": (0, -1, 0), "LeftLeg": (0, -1, 0), "LeftFoot": (0, 0, 1), "LeftToeBase": (0, 0, 1),
            "RightUpLeg": (0, -1, 0), "RightLeg": (0, -1, 0), "RightFoot": (0, 0, 1), "RightToeBase": (0, 0, 1)}
TIP = {"Head": 0.12, "LeftHand": 0.08, "RightHand": 0.08, "LeftToeBase": 0.06, "RightToeBase": 0.06}   # the end bones' lengths (no child)
ORDER = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "RightShoulder", "RightArm",
         "RightForeArm", "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"]
PREFIX = "mixamorig:"


# ---- quaternions (x, y, z, w), glTF's order ------------------------------------------------------------------------------------------------
def q_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz])


def q_inv(q: np.ndarray) -> np.ndarray:
    return np.array([-q[0], -q[1], -q[2], q[3]])


def q_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    u, w = q[:3], q[3]
    return 2 * np.dot(u, v) * u + (w * w - np.dot(u, u)) * v + 2 * w * np.cross(u, v)


def q_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The shortest rotation taking unit a onto unit b."""
    d = float(np.dot(a, b))
    if d < -0.999999:
        axis = np.cross(np.array([1.0, 0, 0]), a)
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(np.array([0, 1.0, 0]), a)
        axis /= np.linalg.norm(axis)
        return np.array([axis[0], axis[1], axis[2], 0.0])
    c = np.cross(a, b)
    q = np.array([c[0], c[1], c[2], 1.0 + d])
    return q / np.linalg.norm(q)


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])


# ---- the glb -----------------------------------------------------------------------------------------------------------------------------
def bone_lengths(joints: np.ndarray) -> dict[str, float]:
    """Each bone's length as the mean distance to its child joint over the clip; the end bones' as set."""
    out = {}
    for name in ORDER:
        if name in CHILD:
            out[name] = float(np.linalg.norm(joints[:, J[CHILD[name]]] - joints[:, J[name]], axis=1).mean())
        else:
            out[name] = TIP[name]
    return out


def frame_directions(frame: np.ndarray, name: str) -> np.ndarray:
    """The bone's direction in the frame: towards its child joint; an end bone follows its parent's direction."""
    if name in CHILD:
        return unit(frame[J[CHILD[name]]] - frame[J[name]])
    return unit(frame[J[name]] - frame[J[PARENT[name]]])


def write_glb(joints: np.ndarray, path: Path, clip_name: str) -> None:
    """A Mixamo-named skeleton in a T-pose at the sample's limb lengths, animated by shortest-arc rotations per bone; Hips carry the travel."""
    n = joints.shape[0]
    lengths = bone_lengths(joints)
    # the rest pose: node translations are the parent bone's rest vector (child sits at the end of the parent's bone)
    rest_t = {}
    for name in ORDER:
        p = PARENT[name]
        if p is None:
            rest_t[name] = np.array([0.0, float(joints[0, 0, 1]), 0.0])
        elif name in ("LeftShoulder", "RightShoulder"):
            rest_t[name] = np.array([0.0, lengths[p], 0.0]) * 0 + np.array(REST_DIR[name]) * 0.05 + np.array([0.0, lengths["Spine2"], 0.0])
        elif name in ("LeftUpLeg", "RightUpLeg"):
            side = 1.0 if name.startswith("Left") else -1.0
            hip_w = float(np.linalg.norm(joints[0, 1] - joints[0, 2])) / 2
            rest_t[name] = np.array([side * hip_w, 0.0, 0.0])
        else:
            rest_t[name] = np.array(REST_DIR[p], dtype=float) * lengths[p]
    # per frame: world rotations from the rest direction to the frame's, local = parent_world^-1 * world
    rot_tracks = {name: np.zeros((n, 4)) for name in ORDER}
    hips_pos = joints[:, 0, :].astype(np.float32)
    for f in range(n):
        world = {}
        for name in ORDER:
            d = frame_directions(joints[f], name)
            world[name] = q_between(np.array(REST_DIR[name], dtype=float), d)
            p = PARENT[name]
            local = world[name] if p is None else q_mul(q_inv(world[p]), world[name])
            rot_tracks[name][f] = local / np.linalg.norm(local)
    # buffers: times, hips translation, each bone's rotations
    times = (np.arange(n, dtype=np.float32) / FPS)
    blobs: list[bytes] = []
    views: list[dict] = []
    accessors: list[dict] = []

    def add(arr: np.ndarray, kind: str, comp: int = 5126) -> int:
        b = arr.astype(np.float32).tobytes()
        off = sum(len(x) for x in blobs)
        pad = (-len(b)) % 4
        blobs.append(b + b"\0" * pad)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(b)})
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(arr.shape[0]), "type": kind}
        if kind == "SCALAR":
            acc["min"], acc["max"] = [float(arr.min())], [float(arr.max())]
        accessors.append(acc)
        return len(accessors) - 1
    t_acc = add(times, "SCALAR")
    nodes = []
    index = {name: i for i, name in enumerate(ORDER)}
    for name in ORDER:
        node = {"name": PREFIX + name, "translation": [float(x) for x in rest_t[name]], "rotation": [0.0, 0.0, 0.0, 1.0]}
        kids = [index[c] for c in ORDER if PARENT[c] == name]
        if kids:
            node["children"] = kids
        nodes.append(node)
    samplers, channels = [], []
    hp = add(hips_pos, "VEC3")
    samplers.append({"input": t_acc, "output": hp, "interpolation": "LINEAR"})
    channels.append({"sampler": 0, "target": {"node": index["Hips"], "path": "translation"}})
    for name in ORDER:
        acc = add(rot_tracks[name], "VEC4")
        samplers.append({"input": t_acc, "output": acc, "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1, "target": {"node": index[name], "path": "rotation"}})
    bin_blob = b"".join(blobs)
    gltf = {"asset": {"version": "2.0", "generator": "loom2 E60 spike"}, "scene": 0, "scenes": [{"nodes": [index["Hips"]], "name": clip_name}],
            "nodes": nodes, "animations": [{"name": clip_name, "samplers": samplers, "channels": channels}],
            "buffers": [{"byteLength": len(bin_blob)}], "bufferViews": views, "accessors": accessors}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((-len(js)) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_blob)
    with path.open("wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A)); fh.write(js)
        fh.write(struct.pack("<II", len(bin_blob), 0x004E4942)); fh.write(bin_blob)


def sheet(joints: np.ndarray, path: Path, title: str, n: int = 6) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    chains = [[0, 2, 5, 8, 11], [0, 1, 4, 7, 10], [0, 3, 6, 9, 12, 15], [9, 14, 17, 19, 21], [9, 13, 16, 18, 20]]
    picks = [round(i * (len(joints) - 1) / (n - 1)) for i in range(n)]
    fig, axes = plt.subplots(1, n, figsize=(2.6 * n, 3.2), subplot_kw={"projection": "3d"})
    lo, hi = joints.min(axis=(0, 1)), joints.max(axis=(0, 1))
    for ax, f in zip(axes, picks):
        fr = joints[f]
        for ch in chains:
            ax.plot(fr[ch, 0], fr[ch, 2], fr[ch, 1], "o-", ms=2, lw=1.5)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[2], hi[2]); ax.set_zlim(0, hi[1])
        ax.set_box_aspect((max(1e-3, hi[0] - lo[0]), max(1e-3, hi[2] - lo[2]), hi[1]))
        ax.view_init(elev=15, azim=-60); ax.set_axis_off(); ax.set_title(f"{f / FPS:.1f} s", fontsize=8)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def generate() -> float:
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "prompts.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["prompt", "length"])
        for _, text, length in PROMPTS:
            w.writerow([text, length])
    t0 = time.time()
    # the demo as it is, with its matplotlib mp4s turned off (no ffmpeg on this PATH; the npys are what the spike reads)
    wrapper = ("import sys, sample.demo as d; d.plot_3d_motion = lambda *a, **k: None; d.plot_3d_motion_long = lambda *a, **k: None; d.main()")
    cmd = [str(VENV_PY), "-c", wrapper, f"prompt_csv={csv_path.as_posix()}", "exp=e60", "autoregressive=false", "num_samples=2",
           f"checkpoints_dir={WEIGHTS.as_posix()}", "dataset_dir=./datasets", f"out_dir_root={(OUT / 'generations').as_posix()}", "num_workers=0"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=CMDM, text=True, capture_output=True)
    (OUT / "demo.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-3000:])
        sys.exit(1)
    return time.time() - t0


def convert() -> dict:
    gen = OUT / "generations" / "e60"
    report = {}
    for i, (name, text, length) in enumerate(PROMPTS):
        for rep in range(2):
            src = gen / f"sample_{i:02d}_rep{rep:02d}.npy"
            if not src.is_file():
                continue
            joints = np.load(src).astype(np.float64)              # (frames, 22, 3), Y up, metres
            key = f"{name}-{rep}"
            np.save(OUT / f"{key}.npy", joints)
            write_glb(joints, OUT / f"{key}.glb", key)
            sheet(joints, OUT / f"sheet-{key}.png", f"{text}  ({len(joints)} f @ {FPS} fps)")
            travel = float(np.linalg.norm(joints[-1, 0, [0, 2]] - joints[0, 0, [0, 2]]))
            report[key] = {"text": text, "frames": int(len(joints)), "fps": FPS, "travel_m": round(travel, 2), "glb": str(OUT / f"{key}.glb"),
                           "sheet": str(OUT / f"sheet-{key}.png"), "hip_height_m": round(float(joints[:, 0, 1].mean()), 2)}
            print(key, json.dumps(report[key]))
    return report


def main() -> None:
    secs = None
    if "--convert" not in sys.argv:
        secs = generate()
        print(f"generated in {secs:.0f} s on the CPU")
    report = convert()
    (OUT / "result.json").write_text(json.dumps({"seconds": secs, "samples": report}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
