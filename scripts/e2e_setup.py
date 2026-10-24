"""Prepares the state for the frontend end-to-end run (D68, ArtCraft P6): called by `frontend/e2e/global-setup.ts`, which then starts
the fake engine (`orchestrator/tests/fake_comfy.py`), the orchestrator and `vite preview` itself.

    orchestrator/.venv/Scripts/python.exe scripts/e2e_setup.py --state DIR --project DIR --engine-port N [--count 200]

Writes
- `<state>/models/`: zero-byte-ish weight files for the Klein 4B text-to-image path (transformer, encoder, VAE — the names come from the
  model registry and the roster, so a spec change follows), offered under both variants;
- `<state>/app.json`: settings pointing the engine at the fake engine's port and the models root at that tree, no mounted trees;
- the project: `scripts/make_synthetic_assets.py --count N` (reused when it already holds a project made by the same inputs — the perf
  run keeps a 10k project between runs, keyed by a hash of the scripts and modules that shape it).
Prints one JSON line `{"project": …, "assets": N, "reused": bool}`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))

from loom2.config import AppRecord, Settings  # noqa: E402
from loom2.fsio import atomic_write_json  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.roster import ROSTER_BY_ID  # noqa: E402

SMOKE_MODEL_LABEL = "Klein 4B"          # the T2I model the smoke run generates with: offered in `full` and `open`
SHAPERS = ["scripts/make_synthetic_assets.py", "orchestrator/loom2/catalogue.py", "orchestrator/loom2/workspace.py"]


def fake_models(root: Path) -> list[str]:
    spec = next((s for s in registry.load().values() if s.label == SMOKE_MODEL_LABEL), None)
    if spec is None:
        raise SystemExit(f"no model labelled {SMOKE_MODEL_LABEL!r} in the registry")
    written = []
    specs = [spec, *registry.reangle_specs(), *registry.stage_specs()]   # P14 / ST3: the Angle and Shot tabs' methods are "present" too (the fake engine answers any graph)
    i2v = registry.get(registry.default_model("i2v"))                 # P17: the smoke run animates one clip for the sequence lane
    if i2v is not None:
        specs.append(i2v)
    specs += [s for s in registry.video_specs() if s.recipes.guide_lora]  # ST4: the clip model with its IC-LoRA (LTX-2.3)
    specs += registry.mesh_specs()                                     # P18: Pixal3D and its encoders (the fake engine writes a GLB)
    specs += registry.animate_specs()                                  # CN4: Wan2.2 Animate, CLIP vision, the LightX2V LoRA (the Stage's animate method)
    specs += registry.lipsync_specs()                                  # D88 XL: Wan2.2 S2V and wav2vec2 (experimental lip-sync)
    specs += [s for s in registry.video_specs() if s.graph == "wan22"]   # D118 (AE4a): the clean-up pass runs on Wan 2.2's low-noise expert
    specs += [s for s in registry.image_specs() if s.recipes.train]     # LT2: the LoRA bases (the fake trainer never loads them)
    specs += [s for s in registry.load().values() if s.recipes.keypoints]   # CA1b: SDPose + RT-DETR (the fake engine answers with an A-pose person)
    specs += [registry.get(registry.segment_model("text"))]                   # D111 (PS5d): SAM 3 mattes a character layer (the fake answers a mask a frame)
    for rid in dict.fromkeys(r for s in specs for r in [*s.weights(), *([s.recipes.stage_lora] if s.recipes.stage_lora else []), *([s.recipes.guide_lora] if s.recipes.guide_lora else [])]):
        e = ROSTER_BY_ID[rid]
        p = root / e.folder / e.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 16)
        written.append(f"{e.folder}/{e.name}")
    lora = root / "loras" / "smoke" / "mara_smoke.safetensors"                 # LT1: a file LoRA for the slots scenario (18 §3e)
    lora.parent.mkdir(parents=True, exist_ok=True)
    lora.write_bytes(b"x" * 16)
    written.append("loras/smoke/mara_smoke.safetensors")
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return written


def project_key(count: int) -> str:
    h = hashlib.sha256(str(count).encode())
    for rel in SHAPERS:
        h.update((REPO / rel).read_bytes())
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--engine-port", type=int, required=True)
    ap.add_argument("--count", type=int, default=200)
    a = ap.parse_args()
    state, project = Path(a.state), Path(a.project)
    state.mkdir(parents=True, exist_ok=True)
    models = state / "models"
    weights = fake_models(models)
    settings = Settings().model_dump()
    settings.update(models_root=str(models), mounted_model_trees=[], reopen_last_project=False)
    # the orchestrator adopts the fake engine listening on that port; should it be down, the "engine" it launches is `python -c …`, which
    # exits at once (never the real ComfyUI on the GPU)
    settings["engine"].update(port=a.engine_port, health_timeout_s=10.0, python=sys.executable, main="-c")
    tests = Path(__file__).resolve().parents[1] / "orchestrator" / "tests"                      # LT2: the fake trainer stands in for ai-toolkit
    settings["trainer"] = {**settings["trainer"], "python": sys.executable, "run": str(tests / "fake_trainer.py"), "cwd": str(tests),
                           "vae": str(next(models.glob("vae/*.safetensors"), models / "vae" / "none.safetensors"))}   # a local stand-in: no hub access
    settings["voices"] = {**settings["voices"], "python": sys.executable, "run": str(tests / "fake_tts.py")}   # CN2: the fake runner stands in for voices/tts.py
    lipsync = state / "lipsync" / "checkpoints"                                                # AE4d: the fake runner stands in for tools/lipsync/sync.py
    lipsync.mkdir(parents=True, exist_ok=True)
    (lipsync / "latentsync_unet.pt").write_bytes(b"x" * 16)
    settings["lipsync"] = {**settings["lipsync"], "python": sys.executable, "run": str(tests / "fake_lipsync.py"), "checkout": str(lipsync.parent)}
    settings["effectcraft"] = {**settings["effectcraft"], "cli": str(tests / "fake_effectcraft.py")}         # AE1: the fake session stands in for effectcraft-cli
    settings["filmcraft"] = {**settings["filmcraft"], "cli": str(tests / "fake_filmcraft.py")}             # CE1 (D126): the fake stands in for filmcraft-cli: cuts are FilmCraft projects
    settings["hf_home"] = str(state / "hf")
    motion = models / "motion" / "test"                                                      # CA1: the library's test rig stands in for the starter set
    motion.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tests / "fixtures" / "motion" / "test_rig.glb", motion / "test_rig.glb")
    atomic_write_json(state / "app.json", AppRecord(settings=Settings.model_validate(settings)).model_dump())

    key = project_key(a.count)
    marker = project / ".e2e-key"
    reused = (project / "project.json").exists() and marker.exists() and marker.read_text(encoding="utf-8").strip() == key
    if not reused:
        if project.exists() and any(project.iterdir()):
            raise SystemExit(f"{project} exists and was not made by this script with these inputs: delete it first")
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run([sys.executable, str(REPO / "scripts" / "make_synthetic_assets.py"), "--project", str(project), "--count", str(a.count)],
                       check=True, env=env, stdout=subprocess.DEVNULL)
        marker.write_text(key, encoding="utf-8")
    print(json.dumps({"project": str(project), "assets": a.count, "reused": reused, "weights": weights}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
