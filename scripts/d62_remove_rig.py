"""D62 rig check: Remove as it is, Remove with the content-aware pre-fill, and Quick Remove (no GPU) — same seed, bench task 01 (remove
the crates; the cobblestones and the wall must continue). Runs on a temporary state and project (only the engine / model settings are
copied), like scripts/pe3_blend_rig.py. Prints the wall time of each and writes a contact sheet of the region to engine/spikes/out/d62/
(original · Remove · Remove + pre-fill · Quick Remove) for the eye: whether the pre-fill helps decides its default (D62).

    orchestrator/.venv/Scripts/python.exe scripts/d62_remove_rig.py [--seed 7]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pe3_blend_rig import BENCH, PORT, REPO, TOKEN, call, layer, wait_job  # noqa: E402

OUT = REPO / "engine" / "spikes" / "out" / "d62"


def main() -> int:
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    real = json.loads((REPO / ".loom2_state" / "app.json").read_text(encoding="utf-8"))["settings"]
    tmp = Path(tempfile.mkdtemp(prefix="loom2-d62-"))
    state = tmp / "state"
    state.mkdir()
    (state / "app.json").write_text(json.dumps({"schema_version": 1, "settings": {k: real[k] for k in ("engine", "models_root", "mounted_model_trees", "variant") if k in real}}), encoding="utf-8")
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(state)], cwd=str(REPO / "orchestrator"), env=env,
                            stdout=open(tmp / "orchestrator.log", "w", encoding="utf-8"), stderr=subprocess.STDOUT)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        for _ in range(120):
            try:
                call("GET", "/health"); break
            except Exception:
                time.sleep(0.5)
        print("content_aware:", call("GET", "/capabilities").get("content_aware"), flush=True)
        call("POST", "/project", {"path": str(tmp / "proj"), "name": "D62 rig", "size_cap_gb": 10})
        spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in spec["tasks"] if t["id"].startswith("01"))
        src = BENCH / spec["source"]
        original = np.asarray(Image.open(src).convert("RGB"))
        H, W = original.shape[:2]
        mask = np.asarray(Image.open(BENCH / "masks" / f"{task['id']}.png").convert("L").resize((W, H)))
        asset = call("POST", "/assets/import", {"paths": [str(src)]})["items"][0]
        did = call("POST", "/documents", {"from_asset": asset["id"], "name": "d62"})["id"]
        call("POST", "/queue/unpause")
        sheet = []
        runs = (("Remove", {"mode": "remove", "model_id": "klein-9b", "prompt_text": task["prompt"]}),
                ("Remove + pre-fill", {"mode": "remove", "model_id": "klein-9b", "prompt_text": task["prompt"], "prefill": True}),
                ("Quick Remove (CPU)", {"mode": "quick_remove"}))
        for name, extra in runs:
            call("PUT", f"/documents/{did}/selection?w={W}&h={H}", mask.tobytes())
            recipe = {"kind": "inpaint", "seeds": [seed], "feather": 8, **extra}
            j = wait_job(call("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]["id"])
            if j["status"] != "done":
                print(f"{name}: FAILED {j.get('error')}", flush=True); return 1
            lid = j["result"]["layers"][0]
            d = call("GET", f"/documents/{did}")
            node = next(n for g in d["layers"] if g["kind"] == "group" for n in g["children"] if n["id"] == lid)
            px, m = layer(did, lid, "image"), layer(did, lid, "mask")
            x, y = node["x"], node["y"]
            a = np.zeros((H, W)); a[y:y + m.shape[0], x:x + m.shape[1]] = m / 255.0
            rgb = original.astype(np.float64).copy(); rgb[y:y + px.shape[0], x:x + px.shape[1]] = px[..., :3]
            comp = original * (1 - a[..., None]) + rgb * a[..., None]
            sheet.append(np.clip(comp, 0, 255).astype(np.uint8))
            print(f"{name}: {j['wall_s']} s", flush=True)
            call("PUT", f"/documents/{did}", {**d, "layers": [l for l in d["layers"] if not l["id"].startswith("grp_")]})
        ys, xs = np.nonzero(mask >= 128)
        y0, y1, x0, x1 = max(0, ys.min() - 40), min(H, ys.max() + 40), max(0, xs.min() - 40), min(W, xs.max() + 40)
        out = OUT / f"remove-task01-seed{seed}.png"
        Image.fromarray(np.concatenate([original[y0:y1, x0:x1]] + [s[y0:y1, x0:x1] for s in sheet], axis=1)).save(out)
        print(f"sheet: {out} (original · Remove · Remove + pre-fill · Quick Remove)", flush=True)
        return 0
    finally:
        try:
            call("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=60)
        except Exception:
            orch.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
