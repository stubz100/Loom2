"""D153 (E40): SeedVR2 3B as the Upscale tool's default "add real detail" model — the default in both variants, the graph as the engine's own
template wires it (the core nodes, a one-step KSampler, the Lab colour match), the weights it loads (the VAE too), the tiled refine cut from its
output, ESRGAN still the cheap choice."""
from __future__ import annotations

import pytest

from loom2.engine.graphs import compile_recipe, doc_estimate_seconds, recipe_weights
from loom2.models import registry
from loom2.recipes import Upscale, parse_recipe
from test_graph_parity_d64 import _pin_review

IMG = {"image": "alley-rain_s20261004.png", "w": 960, "h": 544}
ORDER = ["LoadImage", "ImageScaleBy", "SeedVR2Preprocess", "VAELoader", "VAEEncodeTiled", "UNETLoader", "SeedVR2Conditioning", "KSampler",
         "VAEDecodeTiled", "SeedVR2PostProcessing", "SaveImage"]


@pytest.fixture(scope="module")
def roster(tmp_path_factory):
    return _pin_review().full_roster(tmp_path_factory.mktemp("roster"))


def _by_class(g: dict, cls: str) -> list[dict]:
    return [n for n in g.values() if n["class_type"] == cls]


def test_seedvr2_is_the_default_upscaler_in_both_variants():
    sid = registry.default_model("upscale")
    spec = registry.get(sid)
    assert spec.graph == "seedvr2" and spec.recipes.upscale_factor == 2 and spec.roles.vae
    assert registry.default_model("upscale", "open") == sid                       # Apache-2.0 weights: the open variant has it too
    assert registry.offered(spec, "open")
    esrgan = [s for s in registry.SPECS.values() if s.graph == "esrgan"]
    assert esrgan and all("upscale" not in s.recipes.default_for for s in esrgan)  # ESRGAN stays the cheap choice, not the default
    assert parse_recipe({"kind": "upscale", "document_id": "d"}).model_id == sid


def test_the_graph_is_the_engine_templates_one(roster, object_info):
    sid = registry.default_model("upscale")
    c = compile_recipe(Upscale(document_id="d", model_id=sid, source="visible", seeds=[3]), roster, object_info, 3, "loom2/t", inputs=IMG)
    assert c.problems == []
    g = c.graph
    assert [g[str(k)]["class_type"] for k in (100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 99)] == ORDER
    assert g["101"]["inputs"] == {"image": ["100", 0], "upscale_method": "lanczos", "scale_by": 2.0}
    assert g["104"]["inputs"]["pixels"] == ["102", 0] and g["104"]["inputs"]["tile_size"] == 512 and g["104"]["inputs"]["overlap"] == 128
    ks = g["107"]["inputs"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"], ks["denoise"], ks["seed"]) == (1, 1.0, "euler", "simple", 1.0, 3)
    assert ks["positive"] == ["106", 0] and ks["negative"] == ["106", 1] and ks["latent_image"] == ["104", 0] and ks["model"] == ["105", 0]
    assert g["106"]["inputs"] == {"model": ["105", 0], "vae_conditioning": ["104", 0]}
    assert g["109"]["inputs"] == {"images": ["108", 0], "original_resized_images": ["101", 0], "color_correction_method": "lab"}
    assert g["99"]["inputs"]["images"] == ["109", 0]
    assert c.summary["factor"] == 2 and c.summary["colour_match"] == "lab" and c.summary["model_id"] == sid
    assert g["105"]["inputs"]["unet_name"].endswith(".safetensors") and g["103"]["inputs"]["vae_name"].endswith(".safetensors")


def test_the_weights_and_the_estimate_name_the_vae_too():
    sid = registry.default_model("upscale")
    r = Upscale(document_id="d", model_id=sid)
    assert set(recipe_weights(r)) == {sid, registry.get(sid).roles.vae}
    assert doc_estimate_seconds(r)["seconds"] == registry.get(sid).estimates.doc_seconds == 8.0


def test_the_tiled_refine_is_cut_from_seedvr2s_output(roster, object_info):
    sid, ref = registry.default_model("upscale"), registry.default_model("i2i")
    c = compile_recipe(Upscale(document_id="d", model_id=sid, source="visible", refine=True, refine_model_id=ref, seeds=[0]), roster, object_info, 0, "loom2/t", inputs=IMG)
    assert c.problems == []
    crops = _by_class(c.graph, "ImageCrop")
    assert crops and all(n["inputs"]["image"] == ["109", 0] for n in crops)      # the tiles come from the restoration, not from an ESRGAN node
    assert c.summary["tiles"] == len(crops) and c.summary["upscaled"] == [1920, 1088] and c.summary["colour_match"] == "lab"
    assert ref in recipe_weights(Upscale(document_id="d", model_id=sid, refine=True, refine_model_id=ref))


def test_esrgan_still_compiles_as_the_cheap_one(roster, object_info):
    esr = next(s.id for s in registry.SPECS.values() if s.graph == "esrgan" and s.recipes.upscale_factor == 2)
    c = compile_recipe(Upscale(document_id="d", model_id=esr, source="visible", seeds=[0]), roster, object_info, 0, "loom2/t", inputs=IMG)
    assert c.problems == [] and _by_class(c.graph, "ImageUpscaleWithModel") and not _by_class(c.graph, "SeedVR2Conditioning")
    assert c.summary["factor"] == 2 and "colour_match" not in c.summary and recipe_weights(Upscale(document_id="d", model_id=esr)) == [esr]
