"""D89: the node shapes in which the image families' T2I and I2I graphs differ (`.docs/creative_image/04` §2), keyed by the spec's `graph`.

Read from the pinned engine's Comfy templates (`comfyui_workflow_templates_json`: image_krea2_turbo_t2i, image_z_image,
image_chroma_text_to_image, sd3.5_simple_example; D91: the Lumina 2 example workflow). Shapes only — steps, CFG, sampler, scheduler and shift stay in the spec (D65).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..models.spec import ModelSpec


@dataclass(frozen=True)
class Family:
    clip_type: str | None              # CLIPLoader.type; None = a checkpoint (CheckpointLoaderSimple) carries the encoders and the VAE
    latent: str                        # the empty latent T2I starts from
    flux_guidance: bool                # FluxGuidance on the positive (the FLUX.2 family); elsewhere guidance is not a control
    flux_shift: bool                   # ModelSamplingFlux (the recipe's base_shift / max_shift) applies
    shift_node: str | None = None      # the node that sets `sampling.model_shift` (None = the model's built-in shift)
    t5_options: bool = False           # Chroma: T5TokenizerOptions(min_padding 0, min_length 0) on the encoder (the template's)


FAMILIES: dict[str, Family] = {
    "flux2": Family("flux2", "EmptyFlux2LatentImage", flux_guidance=True, flux_shift=True),
    "klein": Family("flux2", "EmptyFlux2LatentImage", flux_guidance=True, flux_shift=True),
    "krea2": Family("krea2", "EmptyLatentImage", flux_guidance=False, flux_shift=True),       # built-in shift 1.15; the style-reference template sets ModelSamplingFlux
    "zimage": Family("lumina2", "EmptySD3LatentImage", flux_guidance=False, flux_shift=False, shift_node="ModelSamplingAuraFlow"),
    "chroma": Family("chroma", "EmptySD3LatentImage", flux_guidance=False, flux_shift=False, shift_node="ModelSamplingAuraFlow", t5_options=True),
    "sd3": Family(None, "EmptySD3LatentImage", flux_guidance=False, flux_shift=False),          # built-in shift 3.0
    # D91: Lumina Image 2.0 — the engine's own example (ComfyUI_examples/lumina2, lumina2_basic_example.png; the pinned templates carry only
    # its NetaYume fine-tune, the same shape): one all-in-one checkpoint, ModelSamplingAuraFlow, EmptySD3LatentImage; the system prompt is
    # the spec's `sampling.prompt_prefix`
    "lumina2": Family(None, "EmptySD3LatentImage", flux_guidance=False, flux_shift=False, shift_node="ModelSamplingAuraFlow"),
}


def family(spec: ModelSpec) -> Family:
    return FAMILIES[spec.graph]
