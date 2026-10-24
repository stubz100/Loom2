"""E35b (D131, after E35's first run): do chained Klein stills follow their own frame's clay when the references are told to give the look
and not the layout? E35 as run (each reference noted "… keep its walls, window, floor, light and materials exactly") copied the first
frame's composition into every still — the room never turned (travel 0 px against the set's 124) and the dense chain decayed. Here the
keyframe chain of E35's arm B (every 8th frame from its clay) again on E35's project, with one thing changed at a time:

  V1 — the note asks for the look, not the layout, three references (the keyframes before it);
  V2 — the same note, one reference (the keyframe just before it).

Measured: the keyframes' sideways travel against the set's clay at the same frames (phase correlation from keyframe to keyframe, px of
256), each keyframe's distance from the first still (the look kept), the time. Sheet: the clay · E35's keyframes · V1 · V2.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e35b_notes.py      # after e35_chain.py; the engine free (D97)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from ca3_acceptance import _grad, _shift  # noqa: E402
from e35_chain import KEY_EVERY, OUT, still_paths  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

LOOK = ("the same room a little earlier along the camera's path: take its materials, colours and light from it, not its layout — the walls, "
        "the floor and their corners are where image 1 puts them")
VARIANTS = {"V1 look, three references": (LOOK, 3), "V2 look, one reference": (LOOK, 1)}


def keytravel(frames: list[Path]) -> list[int]:
    out, t = [], 0
    for a, b in zip(frames, frames[1:]):
        t += _shift(_grad(a), _grad(b))
        out.append(t)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import e35_chain
    run = json.loads((OUT / "run.json").read_text(encoding="utf-8"))
    fid = run["final_id"]
    P.OUT = OUT
    app = P.App(OUT / "proj")
    res: dict = {"variants": {}}
    try:
        f = P.api("GET", f"/finals/{fid}")
        plate = next(x for x in f["layers"] if x["id"] == "plate")
        jobs = {j["id"]: j for j in json.loads((OUT / "proj" / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]}
        still_job = jobs[plate["job_ids"][-2]]
        base = {**still_job["recipe"], "seeds": [still_job["seed"]]}
        clay_dir = OUT / "proj" / "finals" / fid / "plate" / "clay"
        clay = sorted(clay_dir.glob("*.png"))
        keys = list(range(0, f["frames"], KEY_EVERY))
        clay_ids = {k: P.api("POST", "/assets/import", {"paths": [str(clay[k])], "suite": "stage"})["items"][0]["id"] for k in keys}
        ids = [clay_ids.get(i, "") for i in range(f["frames"])]
        rows = {"the set (clay)": [clay[k] for k in keys], "E35 as run": [still_paths({k: run["B_keys"][str(k)]})[k] for k in keys]}
        for name, (note, nrefs) in VARIANTS.items():
            e35_chain.NOTE = note
            log: list = []
            made = chain_n(base, ids, keys, plate["still_asset_id"], log, nrefs)
            paths = still_paths(made)
            rows[name] = [paths[k] for k in keys]
            res["variants"][name] = {"stills": made, "per_still": [x["wall_s"] for x in log]}
    finally:
        app.close()
    t_set = keytravel(rows["the set (clay)"])
    first = np.asarray(Image.open(rows["E35 as run"][0]).convert("RGB").resize((256, 144)), dtype=np.float64)
    res["measured"] = {}
    for name, frames in rows.items():
        t = keytravel(frames)
        look = [round(float(np.abs(np.asarray(Image.open(p).convert("RGB").resize((256, 144)), dtype=np.float64) - first).mean()), 1) for p in frames]
        res["measured"][name] = {"travel": t, "end": t[-1], "apart": max(abs(a - c) for a, c in zip(t, t_set)), "from_first_still": look}
    tw, th = 240, 135
    cols = list(range(len(keys)))
    sheet = Image.new("RGB", (190 + tw * len(cols), 22 + th * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for ri, (name, frames) in enumerate(rows.items()):
        d.text((6, 22 + ri * th + th // 2), name, fill=(220, 220, 220))
        for c in cols:
            sheet.paste(Image.open(frames[c]).convert("RGB").resize((tw, th)), (190 + c * tw, 22 + ri * th))
            if ri == 0:
                d.text((190 + c * tw + 6, 5), f"frame {keys[c]}", fill=(220, 220, 220))
    sheet.save(OUT / "e35b_sheet.jpg", quality=86)
    (OUT / "e35b.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, m in res["measured"].items():
        print(f"{name:28s} travel {m['end']:4d} px · at most {m['apart']:3d} apart · from the first still {m['from_first_still'][-1]}")
    return 0


def chain_n(base: dict, clay_ids: list[str], frames: list[int], first: str, log: list, nrefs: int) -> dict[int, str]:
    """e35_chain.chain with `nrefs` references (the nearest)."""
    import e35_chain
    made = {frames[0]: first}
    for k in frames[1:]:
        prev = [made[x] for x in reversed(list(made))][:nrefs]
        recipe = {**base, "passes": {"clay": clay_ids[k]}, "refs": [{"asset_id": a, "note": e35_chain.NOTE} for a in prev], "seeds": [base["seeds"][0]]}
        jid = P.api("POST", "/jobs", {"recipe": recipe, "stage": False})["jobs"][0]["id"]
        j = P.wait_job(jid, timeout=1800)
        if j["status"] != "done":
            raise RuntimeError(f"frame {k}: {j.get('error')}")
        made[k] = j["result"]["asset_ids"][0]
        log.append({"frame": k, "wall_s": j.get("wall_s")})
        print(f"frame {k}: {j.get('wall_s')} s", flush=True)
    return made


if __name__ == "__main__":
    raise SystemExit(main())
