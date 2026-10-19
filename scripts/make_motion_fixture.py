"""CA1: the motion library's test rig — a tiny binary glTF (committed at orchestrator/tests/fixtures/motion/test_rig.glb) with the 17 bones
the retargeter maps, Unreal-named (as Quaternius' UAL2), in a T-pose facing +Z, and two clips: `Walk_RM` (the pelvis travels 1 m forward
while the right arm comes down) and `Wave_Loop` (the left arm swings, in place). The offline tests and the e2e smoke use it instead of the
starter set (which is not in CI) — and never a Mixamo file (Adobe's Additional Terms §1).

    orchestrator/.venv/Scripts/python.exe scripts/make_motion_fixture.py
"""
from __future__ import annotations

import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "orchestrator" / "tests" / "fixtures" / "motion" / "test_rig.glb"

# name, parent, translation (metres, relative to the parent)
BONES = [("Armature", None, (0, 0, 0)), ("pelvis", "Armature", (0, 1, 0)), ("spine_01", "pelvis", (0, 0.1, 0)), ("spine_03", "spine_01", (0, 0.3, 0)),
         ("neck_01", "spine_03", (0, 0.2, 0)), ("Head", "neck_01", (0, 0.1, 0))]
for side, sx in (("r", -1), ("l", 1)):
    BONES += [(f"upperarm_{side}", "spine_03", (sx * 0.2, 0.15, 0)), (f"lowerarm_{side}", f"upperarm_{side}", (sx * 0.3, 0, 0)),
              (f"hand_{side}", f"lowerarm_{side}", (sx * 0.25, 0, 0)), (f"thigh_{side}", "pelvis", (sx * 0.1, -0.05, 0)),
              (f"calf_{side}", f"thigh_{side}", (0, -0.45, 0)), (f"foot_{side}", f"calf_{side}", (0, -0.45, 0))]


def quat_z(deg: float) -> list[float]:
    h = math.radians(deg) / 2
    return [0.0, 0.0, math.sin(h), math.cos(h)]


def main() -> None:
    index = {name: i for i, (name, _, _) in enumerate(BONES)}
    nodes = [{"name": n, "translation": list(t), "children": [index[c] for c, p, _ in BONES if p == n]} for n, _, t in BONES]
    for nd in nodes:
        if not nd["children"]:
            del nd["children"]
    bin_ = bytearray()
    views, accessors = [], []

    def add(values: list[float], kind: str, count: int, with_minmax: bool = False) -> int:
        off = len(bin_)
        bin_.extend(struct.pack(f"<{len(values)}f", *values))
        while len(bin_) % 4:
            bin_.append(0)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": 4 * len(values)})
        acc = {"bufferView": len(views) - 1, "componentType": 5126, "count": count, "type": kind}
        if with_minmax:
            acc["min"], acc["max"] = [min(values)], [max(values)]
        accessors.append(acc)
        return len(accessors) - 1

    times = add([0.0, 0.5, 1.0], "SCALAR", 3, True)
    walk_pos = add([0, 1, 0, 0, 1, 0.5, 0, 1, 1], "VEC3", 3)
    walk_arm = add(quat_z(0) + quat_z(45) + quat_z(90), "VEC4", 3)
    wave_arm = add(quat_z(0) + quat_z(-60) + quat_z(0), "VEC4", 3)
    anims = [
        {"name": "Walk_RM", "samplers": [{"input": times, "output": walk_pos, "interpolation": "LINEAR"}, {"input": times, "output": walk_arm, "interpolation": "LINEAR"}],
         "channels": [{"sampler": 0, "target": {"node": index["pelvis"], "path": "translation"}}, {"sampler": 1, "target": {"node": index["upperarm_r"], "path": "rotation"}}]},
        {"name": "Wave_Loop", "samplers": [{"input": times, "output": wave_arm, "interpolation": "LINEAR"}],
         "channels": [{"sampler": 0, "target": {"node": index["upperarm_l"], "path": "rotation"}}]},
    ]
    gltf = {"asset": {"version": "2.0", "generator": "loom2 scripts/make_motion_fixture.py"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": nodes,
            "animations": anims, "buffers": [{"byteLength": len(bin_)}], "bufferViews": views, "accessors": accessors}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
    print(f"{OUT} · {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
