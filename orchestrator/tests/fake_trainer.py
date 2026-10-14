"""A stand-in for trainers/ai-toolkit/run.py (LT2's tests and the e2e smoke): reads the yaml, counts the dataset, prints tqdm-shaped
progress lines as ai-toolkit does, writes the step saves and the final adapter under <training_folder>/<name>/, resumes from the newest
save ("#### IMPORTANT RESUMING FROM … ####" · "Found step N in metadata, starting from there"), and exits 1 at FAKE_TRAINER_CRASH_AT
to stand for a kill. Never touches a GPU.

    python fake_trainer.py <config.yaml>
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import yaml


def main(argv: list[str]) -> int:
    cfg = yaml.safe_load(Path(argv[1]).read_text(encoding="utf-8"))
    name = cfg["config"]["name"]
    p = cfg["config"]["process"][0]
    steps = int(p["train"]["steps"])
    save_every = int(p["save"]["save_every"])
    folder = Path(p["training_folder"]) / name
    folder.mkdir(parents=True, exist_ok=True)
    images = sorted(Path(p["datasets"][0]["folder_path"]).glob("*.png"))
    print(f"Loading Flux2 model ({p['model']['arch']})", flush=True)
    print(f"  -  Found {len(images)} images", flush=True)
    for img in images:
        cap = img.with_suffix(".txt")
        if not cap.is_file():
            print(f"missing caption for {img.name}", flush=True)
            return 2
    saves = sorted(folder.glob(f"{name}_*.safetensors"), key=lambda x: x.name)
    start = 0
    if saves:
        m = re.search(r"_(\d+)\.safetensors$", saves[-1].name)
        start = int(m.group(1)) if m else 0
        print(f"#### IMPORTANT RESUMING FROM {saves[-1]} ####", flush=True)
        print(f"Found step {start} in metadata, starting from there", flush=True)
    crash_at = int(os.environ.get("FAKE_TRAINER_CRASH_AT") or 0)
    delay = float(os.environ.get("FAKE_TRAINER_STEP_S") or 0.01)
    print("Skipping first sample due to config setting", flush=True)
    for step in range(start, steps + 1):
        pct = int(100 * step / steps)
        print(f"{name}: {pct:3d}%|{'█' * (pct // 10):<10}| {step}/{steps} [00:{step % 60:02d}<00:10,  1.00s/it, lr: 1.0e-04 loss: {0.5 - step / (4 * steps):.3e}]\r", end="", flush=True)
        if step and step % save_every == 0 and step < steps:
            (folder / f"{name}_{step:09d}.safetensors").write_bytes(b"fake-save" + os.urandom(64))
            (folder / "optimizer.pt").write_bytes(b"fake-optimizer")
        if crash_at and step >= crash_at:
            print(f"\nkilled at step {step} (FAKE_TRAINER_CRASH_AT)", flush=True)
            return 1
        time.sleep(delay)
    print(flush=True)
    (folder / f"{name}.safetensors").write_bytes(b"fake-adapter" + os.urandom(1024))
    (folder / "optimizer.pt").write_bytes(b"fake-optimizer")
    print(f"Saved checkpoint to {folder / (name + '.safetensors')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
