"""RS2 (D197 G2, proto02 01 §9.1): every generation shows its parameters — the audit.

D60's settings audit checks that a recipe field reaches the code that runs; this one checks the other end: that the author can set it.
A static scan (no engine, no network). Every field of every recipe (`recipes.AnyRecipe`) must be one of:

- **shown** — the frontend module that builds the recipe from a form names the field (SURFACE: the recipe → that module; a field is
  counted when the module contains its name as a word). A coarse test on purpose: it finds a field no form sends, not a field sent fixed;
- **structural** — what the job acts on or a seam between jobs, not a setting (STRUCTURAL, by name);
- **allowed** — not the author's to set, with the reason (ALLOW);
- **owed** — hidden today, with the wave of proto02 03 that shows it (OWED). Owed fields are listed and counted, and do not fail the
  audit: the list is the ratchet — it may only shrink, and RS9 closes at zero.

A field in none of them fails (exit 1): a new recipe field must be given a form, a reason or a wave. Jobs the server builds with fixed
values (a character layer's performance, the plate's paths, the crowd's loop, the turn test — proto02 05 §A) set recipe fields that *are*
shown elsewhere, so the scan cannot see them; they are listed in ROUTES_OWED and printed, to be struck as their run forms land.

    orchestrator/.venv/Scripts/python.exe scripts/exposure_audit.py [-v]
"""
from __future__ import annotations

import re
import sys
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend" / "src"
sys.path.insert(0, str(ROOT / "orchestrator"))

from loom2 import recipes  # noqa: E402

# the module that builds each recipe from what the author set
SURFACE: dict[str, list[str]] = {
    "T2I": ["suites/generate/generateStore.ts"],
    "I2I": ["suites/edit/aiRecipes.ts", "suites/edit/aiPanelStore.ts"],
    "Inpaint": ["suites/edit/aiRecipes.ts", "suites/edit/aiPanelStore.ts"],
    "Upscale": ["suites/edit/aiRecipes.ts", "suites/edit/aiPanelStore.ts"],
    "Segment": ["suites/edit/aiRecipes.ts", "suites/edit/aiPanelStore.ts", "suites/edit/EditSuite.tsx"],
    "Instruct": ["suites/edit/aiRecipes.ts", "suites/edit/aiPanelStore.ts"],
    "I2V": ["suites/animate/animateStore.ts", "suites/stage/stageStore.ts"],          # the panel; the stage clip (its guide)
    "Reangle": ["suites/generate/generateStore.ts"],
    "StageShot": ["suites/stage/stageStore.ts"],
    "ImageToMesh": ["suites/story/MeshRunForm.tsx", "suites/story/storyStore.ts"],
    "ImageToSet": ["suites/stage/stageStore.ts", "suites/story/setBuilder.ts"],
    "Render": ["suites/story/episode/sequenceStore.ts", "suites/story/episode/SequencePanel.tsx"],
    "TTS": ["suites/story/storyStore.ts", "suites/story/VoicesBlock.tsx"],
    "CompRender": ["suites/animate/RenderSettingsBlock.tsx", "suites/animate/FinalSuite.tsx"],
    "LayerPass": ["suites/animate/compositionStore.ts", "suites/animate/FinalEditor.tsx"],
    "MatteSequence": ["suites/stage/finalShot.ts"],
    "Keypoints": [],
    "AssembleFinal": [],
    "TrainLora": [],
}

# what a job acts on, or a seam between jobs — not a setting
STRUCTURAL = {
    "kind", "document_id", "layer_id", "asset_id", "stage_id", "camera_id", "final_id", "clip_id", "timeline_id", "group_id", "profile_id", "version",
    "replace_set_id", "start_asset", "end_asset", "image_blob", "mask_blob", "passes", "items", "mentions", "points", "box", "source", "as_layer", "op",
    "prompt_json", "chain", "frame", "empty", "extend_from", "audio", "bind_refs", "auto_lora", "outpaint", "settings", "voice_id", "step", "scope", "conform",
}

ALLOW: dict[str, str] = {
    "T2I.style_text": "the Look's words, stamped by the server from style_id at submit (D85) — the author picks the style",
    "T2I.size_policy": "how a size off the model's grid is snapped — the panel shows the snapped size (T8), the policy is the server's",
    "I2V.size_policy": "as T2I's",
    "Segment.seeds": "segmentation is deterministic — the field exists for the queue's batch seam",
    "Segment.loras": "no LoRA applies to a segmenter — the queue's shared seam",
    "Upscale.seeds": "one result per upscale — the queue's batch seam (the refine pass's seed is the document's)",
    "Upscale.loras": "the queue's shared seam; the refine pass takes the panel's LoRAs through I2I",
    "Render.seeds": "a render has no seed — the queue's batch seam",
    "AssembleFinal.seeds": "an assembly has no seed — the queue's batch seam",
    "CompRender.seeds": "a render has no seed — the queue's batch seam",
    "MatteSequence.seeds": "a matte has no seed — the queue's batch seam",
    "TTS.seeds": "a voiced line has no seed today — the queue's batch seam",
    "TTS.tier": "the voice's own tier (draft / cloning), set when the voice is made (VoicesBlock)",
    "TTS.language": "the voice's own language, set when the voice is made",
    **{f"TrainLora.{f}": "LoRA training was taken out (D157); its recipe is removed with its leftovers in RS8 (proto02 Q21)"
       for f in ("model_id", "steps", "rank", "resolution", "lr", "seed", "trigger", "name", "setting", "seeds")},
}

OWED: dict[str, str] = {
    "ImageToSet.model_id": "RS2b — the set's run form (one model, MoGe-2: its tile)",
    "ImageToSet.lens_deg": "RS2b — the set's run form (the place's route sends none; the stage's asks it)",
    "ImageToSet.relief": "RS2b — the set's run form (cut is sent; sheet cannot be reached)",
    "ImageToSet.decimation": "RS2b — the set's run form",
    "Keypoints.model_id": "RS9 — the body fit's form, or allowed as a measurement",
    "Keypoints.boxes": "RS9 — as above",
    "Keypoints.inset": "RS9 — as above",
    "Keypoints.matte": "RS9 — as above",
    "MatteSequence.mode": "RS6 — a character layer's matte step",
    "MatteSequence.text": "RS6 — as above (the UI sends 'person')",
    "MatteSequence.threshold": "RS6 — as above",
    "LayerPass.model_id": "RS6 — the passes' model tiles",
    "TTS.speed": "RS4 — the Lines track's editor (the store sends 1)",
    "I2I.steps": "RS9 — Edit's AI tab",
    "I2I.loras": "RS9 — Edit's AI tab (Make has the slots)",
    "I2I.te_device": "RS9 — Edit's AI tab (Make has it)",
    "Inpaint.loras": "RS9 — Edit's AI tab",
    "Inpaint.te_device": "RS9 — Edit's AI tab",
    "Upscale.steps": "RS9 — Edit's Upscale (the refine pass)",
    "Upscale.te_device": "RS9 — Edit's Upscale",
    "Segment.max_size": "RS9 — Edit's Select",
    "I2V.loras": "RS6 — Process's Generate steps",
    "StageShot.te_id": "RS6 — Process's Still (the encoder picker Make has)",
    "LayerPass.seeds": "RS6 — the passes' run forms",
    "Inpaint.max_pixels": "RS9 — Edit's AI tab",
    "Instruct.max_pixels": "RS9 — Edit's AI tab",
    "Segment.threshold": "RS9 — Edit's Select",
    "Segment.refine_iterations": "RS9 — Edit's Select",
}

# jobs the server builds with fixed values (proto02 05 §A) — printed, struck as their run forms land
ROUTES_OWED: list[str] = [
    "A31 a character layer's performance (Wan Animate: preset, prompt tail, window, batches, pose strength, seed) — RS6",
    "A28 / A29 the plate along the path and its keyframe Fills — RS6",
    "A34 / A35 the face pass and lip-sync — RS6",
    "A38 the stage clip (model, guide strength, seed) — RS6",
    "A21 / A22 the crowd's and the walkers' loops (model, strength, frames, seed) — RS2b",
    "A20 / A24 the Fills' and the clean's prompt leads, expand, feather — RS2b",
    "A39 the turn test (preset, seed, frames) — RS2b",
    "A14 a set's moving things (Pixal3D at the recipe's defaults) — RS2b",
    "A13 the Bin's Make a 3D prop… (Pixal3D at the recipe's defaults) — RS2b",
]


def main() -> int:
    verbose = "-v" in sys.argv
    texts: dict[str, str] = {}

    def has(model: str, field: str) -> bool:
        for rel in SURFACE.get(model, []):
            if rel not in texts:
                p = FE / rel
                if not p.is_file():
                    print(f"exposure_audit: SURFACE names a missing file: {rel}")
                    texts[rel] = ""
                else:
                    texts[rel] = p.read_text(encoding="utf-8")
            if re.search(rf"\b{re.escape(field)}\b", texts[rel]):
                return True
        return False

    shown = structural = allowed = 0
    owed: list[str] = []
    problems: list[str] = []
    seen: set[str] = set()
    for m in typing.get_args(recipes.AnyRecipe):
        if m.__name__ not in SURFACE:
            problems.append(f"{m.__name__}: a recipe with no SURFACE entry — name the module that builds it from a form")
            continue
        for f in m.model_fields:
            key = f"{m.__name__}.{f}"
            seen.add(key)
            if key in OWED:
                owed.append(f"{key} — {OWED[key]}")
                if has(m.__name__, f) and verbose:
                    print(f"  note: {key} is owed but its surface names it — strike it if a form sets it now")
            elif key in ALLOW:
                allowed += 1
            elif f in STRUCTURAL:
                structural += 1
            elif has(m.__name__, f):
                shown += 1
            else:
                problems.append(f"{key}: no form sends it — give it a control, a reason (ALLOW) or a wave (OWED)")
    for key in (*OWED, *ALLOW):
        if key not in seen:
            problems.append(f"{key}: listed but no such recipe field — remove it from the list")
    if verbose or problems:
        for line in problems:
            print("  " + line)
    print(f"exposure_audit: {shown} shown, {structural} structural, {allowed} allowed with a reason, {len(owed)} owed, {len(problems)} problem(s); "
          f"{len(ROUTES_OWED)} server-built jobs owed a run form")
    if verbose:
        for line in owed:
            print("  owed: " + line)
        for line in ROUTES_OWED:
            print("  route: " + line)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
