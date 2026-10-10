"""PE3 rig check (D47 / D48): the same Fill inpaint, same seed, pasted back three ways — feather (as before), feather + match colour,
seamless, seamless + match colour — on bench task 01 (remove the crates; cobblestone texture must continue). Runs on a temporary state and project (only the engine /
model settings are copied), like scripts/refine_edge_rig.py.

Per run: the result layer must come back with a linked layer mask over opaque pixels; the composite (original × (1 − mask) + result ×
mask) is scored by **seam energy** (mean |∇(composite − original)| in a band of ± feather px around the mask edge — a visible seam is a
step in that difference) and **ring drift** (mean |result − original| on the context just outside the mask: the model's colour drift that
match colour removes). A contact sheet of the seam region lands in engine/spikes/out/pe3/.

    orchestrator/.venv/Scripts/python.exe scripts/pe3_blend_rig.py [--mode fill|fill_match|remove] [--quick: the first two runs only] [--refine: D48 on Refine]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "bench" / "inpaint"
OUT = REPO / "engine" / "spikes" / "out" / "pe3"
PORT, TOKEN = 8772, "rigtoken"
BASE = f"http://127.0.0.1:{PORT}"
FEATHER = 8


def call(method: str, path: str, body=None, raw: bool = False):
    headers = {"X-Loom-Token": TOKEN}
    data = None
    if isinstance(body, dict):
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body); headers["Content-Type"] = "application/octet-stream"
    with urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, method=method, headers=headers), timeout=1800) as r:
        payload = r.read()
        return (payload, {k.lower(): v for k, v in r.headers.items()}) if raw else json.loads(payload or b"null")


def wait_job(jid: str, timeout: float = 1500) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = call("GET", f"/jobs/{jid}")
        if j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(1)
    raise TimeoutError(jid)


def layer(did: str, lid: str, kind: str) -> np.ndarray:
    data, h = call("GET", f"/documents/{did}/layers/{lid}/pixels?kind={kind}&raw=1", raw=True)
    w, hh, ch = int(h["x-loom-width"]), int(h["x-loom-height"]), int(h.get("x-loom-channels", "4" if kind == "image" else "1"))
    return np.frombuffer(data, np.uint8).reshape(hh, w, ch) if ch > 1 else np.frombuffer(data, np.uint8).reshape(hh, w)


def main() -> int:
    real = json.loads((REPO / ".loom2_state" / "app.json").read_text(encoding="utf-8"))["settings"]
    tmp = Path(tempfile.mkdtemp(prefix="loom2-pe3-"))
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
        call("POST", "/project", {"path": str(tmp / "proj"), "name": "PE3 rig", "size_cap_gb": 10})
        spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
        task = next(t for t in spec["tasks"] if t["id"].startswith("01"))
        src = BENCH / spec["source"]
        original = np.asarray(Image.open(src).convert("RGB"))
        H, W = original.shape[:2]
        mask = np.asarray(Image.open(BENCH / "masks" / f"{task['id']}.png").convert("L").resize((W, H)))
        asset = call("POST", "/assets/import", {"paths": [str(src)]})["items"][0]
        did = call("POST", "/documents", {"from_asset": asset["id"], "name": "pe3-blend"})["id"]
        call("POST", "/queue/unpause")
        sys.path.insert(0, str(REPO / "orchestrator"))
        from loom2 import maskops                                           # noqa: E402 (the repo's own helpers, for the band)
        inside = mask >= 128
        band = (maskops.expand(mask, FEATHER) >= 128) & ~(maskops.contract(mask, FEATHER) >= 128)
        ring = (maskops.expand(mask, FEATHER + 24) >= 128) & ~(maskops.expand(mask, FEATHER + 4) >= 128)
        rows, sheet = [], []
        if "--refine" in sys.argv:
            # D48 on Refine: the visible composite re-sampled at strength 0.35, same seed, without and with match colour; drift = mean
            # |result − original| and the Lab mean shift over the whole image
            from loom2 import tone                                            # noqa: E402
            lab0 = tone.srgb_to_lab(original).reshape(-1, 3).mean(axis=0)
            for name, extra in (("refine", {}), ("refine + match colour", {"match_colour": True})):
                recipe = {"kind": "i2i", "model_id": "klein-base-9b", "source": "visible", "strength": 0.35, "seeds": [7], **extra}
                j = wait_job(call("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]["id"])
                if j["status"] != "done":
                    print(f"{name}: FAILED {j.get('error')}", flush=True); return 1
                lid = j["result"]["layers"][0]
                px = layer(did, lid, "image")[..., :3]
                lab = tone.srgb_to_lab(px).reshape(-1, 3).mean(axis=0)
                print(f"{name}: {j['wall_s']} s · mean |Δrgb| {np.abs(px.astype(int) - original.astype(int)).mean():.2f} · Lab mean shift {np.round(lab - lab0, 2).tolist()}", flush=True)
                d = call("GET", f"/documents/{did}")
                call("PUT", f"/documents/{did}", {**d, "layers": [l for l in d["layers"] if not l["id"].startswith("grp_")]})
            return 0
        mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "fill"
        runs = (("feather", {}), ("feather + match colour", {"match_colour": True}), ("seamless", {"blend": "seamless"}), ("seamless + match colour", {"blend": "seamless", "match_colour": True}))
        if "--quick" in sys.argv:
            runs = runs[:2]
        for name, extra in runs:
            call("PUT", f"/documents/{did}/selection?w={W}&h={H}", mask.tobytes())
            recipe = {"kind": "inpaint", "mode": mode, "model_id": "klein-9b", "prompt_text": task["prompt"], "seeds": [7], "feather": FEATHER, **extra}
            job = call("POST", f"/documents/{did}/ai", {"recipe": recipe})["jobs"][0]
            j = wait_job(job["id"])
            if j["status"] != "done":
                print(f"{name}: FAILED {j.get('error')}", flush=True); return 1
            lid = j["result"]["layers"][0]
            d = call("GET", f"/documents/{did}")
            node = next(n for g in d["layers"] if g["kind"] == "group" for n in g["children"] if n["id"] == lid)
            px, m = layer(did, lid, "image"), layer(did, lid, "mask")
            ok_mask = node.get("mask") is not None and node["mask"]["linked"] and int(px[..., 3].min()) == 255
            x, y = node["x"], node["y"]
            a = np.zeros((H, W)); a[y:y + m.shape[0], x:x + m.shape[1]] = m / 255.0
            rgb = original.astype(np.float64).copy(); rgb[y:y + px.shape[0], x:x + px.shape[1]] = px[..., :3]
            comp = original * (1 - a[..., None]) + rgb * a[..., None]
            diff = comp - original
            gy, gx = np.gradient(diff, axis=(0, 1))
            seam = float(np.sqrt(gx ** 2 + gy ** 2).mean(axis=-1)[band].mean())
            drift = float(np.abs(rgb - original).mean(axis=-1)[ring & (a > 0)].mean()) if (ring & (a > 0)).any() else float("nan")
            rows.append((name, j["wall_s"], ok_mask, seam, drift))
            print(f"{name}: {j['wall_s']} s · layer mask {'ok' if ok_mask else 'MISSING'} · seam energy {seam:.2f} · ring drift {drift:.2f}", flush=True)
            sheet.append(np.clip(comp, 0, 255).astype(np.uint8))
            call("PUT", f"/documents/{did}", {**d, "layers": [l for l in d["layers"] if not l["id"].startswith("grp_")]})   # next run on the plain plate
        ys, xs = np.nonzero(inside)
        y0, y1, x0, x1 = max(0, ys.min() - 40), min(H, ys.max() + 40), max(0, xs.min() - 40), min(W, xs.max() + 40)
        Image.fromarray(np.concatenate([original[y0:y1, x0:x1]] + [s[y0:y1, x0:x1] for s in sheet], axis=1)).save(OUT / f"blend-task01-{mode}.png")
        print(f"sheet: {OUT / f'blend-task01-{mode}.png'} (original · feather · feather + match colour · seamless · seamless + match colour)", flush=True)
        return 0 if all(r[2] for r in rows) else 1
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
