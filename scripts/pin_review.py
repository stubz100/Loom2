"""M7 pin review (12 §8 slice 3, D15): is a newer ComfyUI safe for loom2's graphs?

Captures `/object_info` from a ComfyUI started on the CPU from a scratch checkout of the candidate tag (no GPU, no
weights needed), diffs it against the pinned fixture (tests/fixtures/object_info.json) for the node classes loom2 uses,
and compiles every recipe kind (t2i incl. Klein and Turbo, i2i, inpaint modes, upscale + tiled refine, segment, i2v Wan /
FLF / LTX with beats) against the candidate — the same contract check the queue runs before every job.

    # scratch checkout + CPU engine (custom nodes copied from the pinned checkout so their classes are present):
    git -C engine/comfyui worktree add .loom2_state/comfy-v0.39.0 v0.39.0
    engine/.venv/Scripts/python.exe .loom2_state/comfy-v0.39.0/main.py --listen 127.0.0.1 --port 8189 --cpu --disable-auto-launch
    orchestrator/.venv/Scripts/python.exe scripts/pin_review.py --url http://127.0.0.1:8189 --tag v0.39.0
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))
sys.path.insert(0, str(REPO / "orchestrator" / "tests"))

from loom2.engine import graphs  # noqa: E402
from loom2.engine.contract import check_graph  # noqa: E402
from loom2.recipes import (AnimateChain, AudioRef, Beat, ExtendFrom, Guide, I2I, I2V, ImageToMesh, ImageToSet, Inpaint, Keypoints, MatteSequence,  # noqa: E402
                           Reangle, RefImage, Segment, StageShot, T2I, Upscale)
from loom2.roster import ROSTER_BY_ID, Roster  # noqa: E402

FIXTURE = REPO / "orchestrator" / "tests" / "fixtures" / "object_info.json"
OUT = REPO / "engine" / "spikes" / "out" / "pin_review"


def spec_sig(info: dict) -> dict:
    """{input name: (kind, required)} with enum members dropped (uploaded files vary) but enum-ness kept."""
    out = {}
    for req, group in (("required", True), ("optional", False)):
        for k, v in (info.get("input", {}).get(group and "required" or "optional") or {}).items():
            t = v[0] if isinstance(v, list) and v else v
            out[k] = ("enum" if isinstance(t, list) else str(t), req)
    return out


def full_roster(tmp: Path) -> Roster:
    for e in ROSTER_BY_ID.values():
        if e.retired:
            continue
        p = tmp / e.folder / e.name
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_bytes(b"x" * 16)
    (tmp / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(tmp).scan()


def recipes() -> list[tuple[str, object, dict]]:
    png = "alley-rain_s20261004.png"
    img = {"image": png, "mask": png, "w": 960, "h": 544}
    return [
        ("t2i dev json", T2I(prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("t2i dev turbo", T2I(prompt_mode="text", prompt_text="a cat", turbo=True, seeds=[1]), {}),
        ("t2i klein 9b", T2I(model_id="klein-9b", prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("t2i klein base 9b + refs", T2I(model_id="klein-base-9b", prompt_mode="text", prompt_text="a cat", seeds=[1], refs=[RefImage(asset_id="a")]), {"refs": {"a": "alley-rain_s20261004.png"}}),
        ("i2i refine", I2I(document_id="d", model_id="klein-base-9b", source="visible", strength=0.25, seeds=[1]), img),
        ("inpaint fill", Inpaint(document_id="d", mode="fill", prompt_text="x", seeds=[1]), img),
        ("inpaint fill_match", Inpaint(document_id="d", mode="fill_match", prompt_text="x", seeds=[1]), img),
        ("inpaint remove", Inpaint(document_id="d", mode="remove", prompt_text="x", seeds=[1]), img),
        ("inpaint fill_hero", Inpaint(document_id="d", mode="fill_hero", prompt_text="x", seeds=[1]), img),
        ("inpaint outpaint", Inpaint(document_id="d", mode="outpaint", outpaint={"right": 240}, prompt_text="x", seeds=[1]), img),
        ("upscale x2", Upscale(document_id="d", model_id="realesrgan-x2", source="visible", seeds=[0]), img),
        ("upscale + tiled refine", Upscale(document_id="d", model_id="realesrgan-x2", source="visible", refine=True, refine_model_id="klein-base-9b", seeds=[0]), img),
        # D89 (wave CR): the creative families — T2I on Krea 2 Turbo / Raw, Z-Image, Chroma; Refine on Krea 2 Raw, Z-Image, Chroma, SD 3.5 Large
        ("t2i krea2 turbo", T2I(model_id="krea2-turbo-fp8", prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("t2i krea2 raw", T2I(model_id="krea2-raw-fp8", prompt_mode="text", prompt_text="a cat", negative="blurry", seeds=[1]), {}),
        ("t2i z-image", T2I(model_id="zimage-bf16", prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("t2i chroma", T2I(model_id="chroma1-hd-fp8mixed", prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("i2i krea2 raw", I2I(document_id="d", model_id="krea2-raw-fp8", source="visible", strength=0.55, seeds=[1]), img),
        ("i2i z-image", I2I(document_id="d", model_id="zimage-bf16", source="visible", strength=0.55, seeds=[1]), img),
        ("i2i chroma", I2I(document_id="d", model_id="chroma1-hd-fp8mixed", source="visible", strength=0.55, seeds=[1]), img),
        ("i2i sd3.5 large", I2I(document_id="d", model_id="sd35-large-fp8", source="visible", strength=0.55, seeds=[1]), img),
        # D91: the sample models — Lumina 2 (T2I) and SD 3.5 Medium (T2I and Refine)
        ("t2i lumina 2", T2I(model_id="lumina-image-2", prompt_mode="text", prompt_text="a cat", negative="blurry ugly bad", seeds=[1]), {}),
        ("t2i sd3.5 medium", T2I(model_id="sd35-medium-fp8", prompt_mode="text", prompt_text="a cat", seeds=[1]), {}),
        ("i2i sd3.5 medium", I2I(document_id="d", model_id="sd35-medium-fp8", source="visible", strength=0.55, seeds=[1]), img),
        ("segment birefnet", Segment(document_id="d", mode="subject"), img),
        ("segment sam3 text", Segment(document_id="d", model_id="sam3", mode="text", text="a woman"), img),
        ("i2v wan draft", I2V(start_asset="a"), {"start": "alley-rain_s20261004.png"}),
        ("i2v wan motion FLF", I2V(start_asset="a", end_asset="b", preset="motion"), {"start": "alley-rain_s20261004.png", "end": "captain-cabin_s20261004.png"}),
        ("i2v ltx beats", I2V(start_asset="a", end_asset="b", model_id="ltx23-distilled-fp8", frames=121, fps=24, width=1024, height=576, beats=[Beat(frame=40, asset_id="k")]),
         {"start": "alley-rain_s20261004.png", "end": "captain-cabin_s20261004.png", "beats": {"k": "01-remove-crates.png"}}),
        # 2026-10-28 (the review against v0.43.1): the graphs built since this list was written — the Stage's pose-driven clip and its second
        # batch (CN4, D111), the lip-sync clip (D88), LTX's guided clip (ST4) and extension (D88), the reangle pair (D82), the stage shot's two
        # methods (ST3), a prop's mesh (P18), a picture set (SC3), the keypoints (CA1b) and the two mattes (PS5d)
        ("i2v wan animate (pose guide)", I2V(model_id="wan22-animate-fp8", start_asset="a", frames=77, guide=Guide(asset_id="g", kind="pose")), {"start": png, "guide": "pose.mp4"}),
        ("i2v wan animate, batch 2 (carry)", I2V(model_id="wan22-animate-fp8", start_asset="a", frames=77, guide=Guide(asset_id="g", kind="pose"), chain=AnimateChain(clip_id="c", carry=5, offset=72)),
         {"start": png, "guide": "pose.mp4", "carry": [png] * 5}),
        ("i2v wan s2v (a line)", I2V(model_id="wan22-s2v-fp8", start_asset="a", frames=77, audio=AudioRef(asset_id="x")), {"start": png, "audio": "line.wav"}),
        ("i2v ltx guided (depth)", I2V(model_id="ltx23-distilled-fp8", start_asset="a", frames=121, fps=24, width=1024, height=576, guide=Guide(asset_id="g", kind="depth")), {"start": png, "guide": "depth.mp4"}),
        ("i2v ltx extend (9 lead frames)", I2V(model_id="ltx23-distilled-fp8", start_asset="a", frames=121, fps=24, width=1024, height=576, extend_from=ExtendFrom(clip_id="c", lead=9)), {"start": png, "lead": "lead.mp4"}),
        ("i2v wan extend (the last frame)", I2V(start_asset="a", extend_from=ExtendFrom(clip_id="c", lead=1)), {"start": png}),
        ("reangle angles lora (left45)", Reangle(asset_id="a", move="left45"), img),
        ("reangle klein (wide)", Reangle(asset_id="a", move="wide"), img),
        ("stage shot clay", StageShot(stage_id="s", camera_id="c", passes={"clay": "p"}, refs=[RefImage(asset_id="a")]), {"clay": png, "w": 1280, "h": 720, "refs": {"a": png}}),
        ("stage shot refcontrol", StageShot(stage_id="s", camera_id="c", passes={"pose": "p"}, method="refcontrol", refs=[RefImage(asset_id="a")]), {"pose": png, "w": 1280, "h": 720, "refs": {"a": png}}),
        ("image to mesh (pixal3d)", ImageToMesh(asset_id="a"), {"image": png}),
        ("image to set (moge)", ImageToSet(asset_id="a"), {"image": png}),
        ("keypoints (sdpose)", Keypoints(asset_id="a"), {"image": png}),
        ("matte sequence sam3 (text)", MatteSequence(final_id="f", layer_id="l"), {"video": "frames.mp4"}),
        ("matte sequence birefnet (subject)", MatteSequence(final_id="f", layer_id="l", mode="subject"), {"video": "frames.mp4"}),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8189")
    ap.add_argument("--tag", default="candidate")
    ap.add_argument("--capture", default=None, help="use this saved object_info JSON instead of --url")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.capture:
        cand = json.loads(Path(a.capture).read_text(encoding="utf-8"))
        cand = cand.get("object_info", cand)
    else:
        with urllib.request.urlopen(a.url + "/object_info", timeout=300) as r:
            cand = json.loads(r.read())
        with urllib.request.urlopen(a.url + "/system_stats", timeout=30) as r:
            stats = json.loads(r.read())
        print(f"candidate {a.tag}: comfyui {stats['system'].get('comfyui_version')} · {len(cand)} node classes")
        (OUT / f"object_info-{a.tag}.json").write_text(json.dumps({"object_info": cand, "system": stats.get("system")}, indent=0), encoding="utf-8")
    pinned = json.loads(FIXTURE.read_text(encoding="utf-8"))["object_info"]
    used = sorted(pinned)
    missing = [c for c in used if c not in cand]
    changed = []
    for c in used:
        if c in cand:
            before, after = spec_sig(pinned[c]), spec_sig(cand[c])
            if before != after:
                added = {k: v for k, v in after.items() if k not in before}
                removed = {k: v for k, v in before.items() if k not in after}
                altered = {k: (before[k], after[k]) for k in before if k in after and before[k] != after[k]}
                changed.append((c, added, removed, altered))
    print(f"\nnode classes loom2 uses: {len(used)} · missing in the candidate: {len(missing)} · with changed inputs: {len(changed)}")
    for c in missing:
        print(f"  MISSING {c}")
    for c, added, removed, altered in changed:
        print(f"  CHANGED {c}: +{sorted(added)} −{sorted(removed)} ~{ {k: f'{v[0][0]}→{v[1][0]}' for k, v in altered.items()} }")
    import tempfile

    roster = full_roster(Path(tempfile.mkdtemp(prefix="pin-roster-")))
    problems_total = 0
    print("\nrecipes compiled against the candidate:")
    for label, recipe, inputs in recipes():
        try:
            c = graphs.compile_recipe(recipe, roster, cand, 1, "loom2/pin", ref_files=inputs.get("refs") or None, inputs=inputs)
            problems = [p for p in c.problems if "not in enum" not in p]            # uploaded-file enums differ per engine: not a pin problem
            # also check against the pinned fixture to see whether a problem is new
            old = graphs.compile_recipe(recipe, roster, pinned, 1, "loom2/pin", ref_files=inputs.get("refs") or None, inputs=inputs)
            old_problems = [p for p in old.problems if "not in enum" not in p]
            new_problems = [p for p in problems if p not in old_problems]
            problems_total += len(new_problems)
            print(f"  [{'ok' if not new_problems else 'FAIL'}] {label}: {len(c.graph)} nodes" + (f" · NEW problems: {new_problems}" if new_problems else "") + (f" · (also on the pin: {old_problems})" if old_problems else ""))
        except Exception as e:  # noqa: BLE001
            problems_total += 1
            print(f"  [FAIL] {label}: {type(e).__name__}: {e}")
    verdict = "SAFE to bump (no missing classes, no changed inputs on the nodes loom2 uses, every recipe compiles)" if not missing and not changed and not problems_total else "NOT a drop-in: review the lines above"
    print(f"\n{a.tag}: {verdict}")
    (OUT / f"review-{a.tag}.json").write_text(json.dumps({"tag": a.tag, "missing": missing, "changed": [(c, sorted(a_), sorted(r_), {k: [list(v[0]), list(v[1])] for k, v in al.items()}) for c, a_, r_, al in changed],
                                                           "new_problems": problems_total, "verdict": verdict}, indent=1), encoding="utf-8")
    return 0 if not missing and not problems_total else 1


if __name__ == "__main__":
    sys.exit(main())
