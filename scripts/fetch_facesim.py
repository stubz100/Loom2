"""Fetch the FaceSim weights (11 §11 item 6): InsightFace's `buffalo_l` pack — SCRFD `det_10g.onnx` (face detector with 5
landmarks) and ArcFace `w600k_r50.onnx` (512-d embedding) — into <models_root>/insightface/buffalo_l/. ≈ 275 MB zip from
the InsightFace GitHub release; only the two files loom2 uses are kept. Licence: the models are for non-commercial
research per InsightFace's model-zoo terms — an advisory number in a personal tool.

    orchestrator/.venv/Scripts/python.exe scripts/fetch_facesim.py [--models-root F:/loom2-models]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
KEEP = {"det_10g.onnx", "w600k_r50.onnx"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-root", default=None)
    a = ap.parse_args()
    root = Path(a.models_root) if a.models_root else None
    if root is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "orchestrator"))
        from loom2.config import AppState, default_state_dir
        root = Path(AppState(default_state_dir()).settings.models_root)
    dest = root / "insightface" / "buffalo_l"
    dest.mkdir(parents=True, exist_ok=True)
    if all((dest / k).is_file() for k in KEEP):
        print(f"already present: {dest}"); return 0
    print(f"downloading {URL} …", flush=True)
    t0 = time.time()
    with urllib.request.urlopen(URL, timeout=120) as r:
        data = r.read()
    print(f"  {len(data) / 2**20:.1f} MiB in {time.time() - t0:.0f} s", flush=True)
    ledger = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            base = Path(name).name
            if base in KEEP:
                payload = z.read(name)
                (dest / base).write_bytes(payload)
                ledger[base] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "source": URL}
                print(f"  {base}: {len(payload) / 2**20:.1f} MiB sha256 {ledger[base]['sha256'][:16]}…")
    (dest / "loom2.json").write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    missing = KEEP - set(ledger)
    if missing:
        print(f"missing in the zip: {missing}"); return 1
    print(f"ready: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
