"""D89 (wave CR, `.docs/creative_image/04`): the creative t2i / i2i families — Krea 2 Turbo + Raw, Z-Image, Chroma1-HD for Generate and
Refine, SD 3.5 Large for Refine only — compile to their Comfy templates' node shapes, stay out of the FLUX.2-only graphs (inpaint, tiled
refine, Angle, Stage), show only the controls their graphs use (T8) and keep their licences' variants (D26)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState
from loom2.engine.graphs import CompileError, compile_recipe, effective_params
from loom2.loras import check_loras, lora_options
from loom2.models import registry
from loom2.models.spec import ModelSpec
from loom2.recipes import I2I, Inpaint, LoraRef, T2I, Upscale
from test_graph_parity_d64 import _pin_review

IMG = {"image": "alley-rain_s20261004.png", "mask": "alley-rain_s20261004.png", "w": 960, "h": 544}
CREATIVE_T2I = [s.id for s in registry.image_specs() if s.graph not in registry.FLUX_GRAPHS and s.recipes.t2i]
CREATIVE_I2I = [s.id for s in registry.image_specs() if s.graph not in registry.FLUX_GRAPHS and s.recipes.i2i]


@pytest.fixture(scope="module")
def roster(tmp_path_factory):
    return _pin_review().full_roster(tmp_path_factory.mktemp("roster"))


def _by_class(g: dict, cls: str) -> list[dict]:
    return [n for n in g.values() if n["class_type"] == cls]


def test_the_wave_is_registered():
    graphs = {registry.get(m).graph for m in CREATIVE_T2I + CREATIVE_I2I}
    assert graphs == {"krea2", "zimage", "chroma", "sd3"}
    assert len(CREATIVE_T2I) == 4 and len(CREATIVE_I2I) == 5                       # SD 3.5 i2i only; Turbo refines since CR6 (partial denoise held)
    assert all(registry.get(m).graph != "sd3" for m in CREATIVE_T2I)
    for kind in ("t2i", "i2i", "inpaint"):                                       # the defaults did not move
        assert registry.get(registry.default_model(kind)).graph in registry.FLUX_GRAPHS


@pytest.mark.parametrize("model_id", CREATIVE_T2I)
def test_t2i_follows_the_template(model_id, roster, object_info):
    spec = registry.get(model_id)
    c = compile_recipe(T2I(model_id=model_id, prompt_text="a lighthouse in a storm", negative="blurry"), roster, object_info, 7, "loom2/t")
    g = c.graph
    clip = _by_class(g, "CLIPLoader")[0]["inputs"]
    assert clip["type"] == {"krea2": "krea2", "zimage": "lumina2", "chroma": "chroma"}[spec.graph]
    assert _by_class(g, {"krea2": "EmptyLatentImage"}.get(spec.graph, "EmptySD3LatentImage"))
    assert not _by_class(g, "FluxGuidance") and not _by_class(g, "EmptyFlux2LatentImage") and not _by_class(g, "ReferenceLatent")
    ks = _by_class(g, "KSampler")[0]["inputs"]
    sm = spec.sampling
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"], ks["denoise"]) == (sm.steps, sm.cfg, sm.sampler, sm.scheduler, 1.0)
    neg = g[ks["negative"][0]]
    if sm.distilled:                                                             # Turbo: the template's ConditioningZeroOut, the negative ignored
        assert neg["class_type"] == "ConditioningZeroOut" and c.summary["negative_used"] is False
    else:
        assert neg["class_type"] == "CLIPTextEncode" and neg["inputs"]["text"] == "blurry"
    assert g[ks["positive"][0]]["class_type"] == "CLIPTextEncode"
    shift = _by_class(g, "ModelSamplingAuraFlow")
    assert [n["inputs"]["shift"] for n in shift] == ({"zimage": [3.0], "chroma": [1.0]}.get(spec.graph, []))
    assert bool(_by_class(g, "T5TokenizerOptions")) == (spec.graph == "chroma")
    assert c.summary["guidance"] is None                                         # T8: nothing to show
    # a real-CFG family encodes its negative even when the recipe leaves it empty (the templates' CLIPTextEncode(""))
    g2 = compile_recipe(T2I(model_id=model_id, prompt_text="x"), roster, object_info, 7, "loom2/t").graph
    ks2 = _by_class(g2, "KSampler")[0]["inputs"]
    assert g2[ks2["negative"][0]]["class_type"] == ("ConditioningZeroOut" if sm.distilled else "CLIPTextEncode")


@pytest.mark.parametrize("model_id", CREATIVE_I2I)
def test_refine_runs_at_the_spec_sampler(model_id, roster, object_info):
    spec = registry.get(model_id)
    c = compile_recipe(I2I(document_id="d", model_id=model_id, strength=0.55), roster, object_info, 3, "loom2/t", inputs=IMG)
    g = c.graph
    ks = _by_class(g, "KSampler")[0]["inputs"]
    assert ks["denoise"] == 0.55 and ks["sampler_name"] == spec.sampling.sampler and ks["scheduler"] == spec.sampling.scheduler
    assert g[ks["latent_image"][0]]["class_type"] == "VAEEncode" and not _by_class(g, "FluxGuidance")
    assert c.summary["sampler"] == spec.sampling.sampler and c.summary["guidance"] is None
    if spec.graph == "sd3":                                                      # one checkpoint: model, clip, vae from node 1
        assert [n["class_type"] for n in g.values()].count("CheckpointLoaderSimple") == 1 and not _by_class(g, "CLIPLoader")
        assert g[ks["positive"][0]]["inputs"]["clip"] == ["1", 1] and _by_class(g, "VAEDecode")[0]["inputs"]["vae"] == ["1", 2]


def test_sd35_is_refine_only(roster, object_info):
    sd = next(m for m in CREATIVE_I2I if registry.get(m).graph == "sd3")
    with pytest.raises(CompileError, match="no T2I preset"):
        compile_recipe(T2I(model_id=sd, prompt_text="x"), roster, object_info, 1, "loom2/t")
    with pytest.raises(CompileError, match="one checkpoint"):                    # no separate encoder to move or swap
        compile_recipe(I2I(document_id="d", model_id=sd, te_device="cpu"), roster, object_info, 1, "loom2/t", inputs=IMG)


def test_the_flux_only_graphs_refuse_them(roster, object_info):
    z = next(m for m in CREATIVE_I2I if registry.get(m).graph == "zimage")
    with pytest.raises(CompileError, match="tiled refine"):
        compile_recipe(Upscale(document_id="d", model_id=registry.default_model("upscale"), refine=True, refine_model_id=z), roster, object_info, 1, "loom2/t", inputs=IMG)
    with pytest.raises(CompileError, match="Generate and Refine only"):
        compile_recipe(Inpaint(document_id="d", model_id=z, mode="fill", prompt_text="x"), roster, object_info, 1, "loom2/t", inputs=IMG)


def test_controls_that_do_not_apply_are_refused():
    chroma = next(m for m in CREATIVE_T2I if registry.get(m).graph == "chroma")
    krea = next(m for m in CREATIVE_T2I if registry.get(m).graph == "krea2")
    with pytest.raises(CompileError, match="ModelSamplingFlux"):
        effective_params(T2I(model_id=chroma, prompt_text="x", base_shift=0.5))
    with pytest.raises(CompileError, match="FLUX.2's"):
        effective_params(T2I(model_id=chroma, prompt_text="x", scheduler="flux2"))
    assert effective_params(T2I(model_id=krea, prompt_text="x", base_shift=0.5))["base_shift"] == 0.5   # Krea 2 takes ModelSamplingFlux (its style template)
    assert effective_params(T2I(model_id=krea, prompt_text="x", guidance=3.0))["guidance"] is None


def test_registry_keeps_them_out_of_the_edit_graphs():
    base = {"id": "zimage-bf16", "family": "zimage", "label": "x", "graph": "zimage", "roles": {"te": {"default": "qwen3-4b"}, "vae": "flux1-ae"}}
    for extra in ({"recipes": {"t2i": True, "inpaint": ["fill"]}}, {"inputs": {"refs_max": 2}}, {"recipes": {"stage": "clay"}}):
        with pytest.raises(registry.RegistryError, match="t2i and i2i only"):
            registry._check(ModelSpec.model_validate({**base, **extra}))
    with pytest.raises(registry.RegistryError, match="needs roles.te and roles.vae"):
        registry._check(ModelSpec.model_validate({**base, "roles": {}}))
    sd = {"id": "sd35-large-fp8", "family": "sd3", "label": "x", "graph": "sd3", "recipes": {"i2i": True}}
    registry._check(ModelSpec.model_validate(sd))
    with pytest.raises(registry.RegistryError, match="carries its encoders"):
        registry._check(ModelSpec.model_validate({**sd, "roles": {"vae": "flux1-ae"}}))


def test_krea_takes_its_style_loras_not_kleins(roster):
    krea = next(m for m in CREATIVE_T2I if registry.get(m).graph == "krea2")
    opts = {o["id"]: o for o in lora_options(roster, krea)}
    styles = [i for i, o in opts.items() if o["fits"] and i.startswith("krea2-lora-")]
    assert len(styles) == 9 and "krea2-style-reference" not in opts               # the style reference is a preset (CR+), never a slot
    check_loras(roster, [LoraRef(model_id=styles[0], strength=0.8)], krea)
    with pytest.raises(ValueError):                                              # the base check: a Krea style on Klein is refused
        check_loras(roster, [LoraRef(model_id=styles[0])], registry.default_model("t2i", "open"))
    with pytest.raises(ValueError, match="style reference"):
        check_loras(roster, [LoraRef(model_id="krea2-style-reference")], krea)


@pytest.mark.parametrize("variant", ["full", "open"])
def test_capabilities_list_them_by_licence(variant, tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": variant})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        caps = cl.get("/capabilities").json()
    assert caps["variant"] == variant
    models = caps["models"]
    offered = {m for m in CREATIVE_T2I + CREATIVE_I2I if variant == "full" or registry.get(m).graph in ("zimage", "chroma")}
    assert offered <= set(models) and not (set(CREATIVE_T2I + CREATIVE_I2I) - offered) & set(models)
    for m in offered:
        c = models[m]
        assert c["guidance_node"] is False and c["tiled_refine"] is False
        assert c["recipes"]["inpaint"] == [] and c["max_refs"] == 0
    flux_i2i = [m for m, c in models.items() if registry.get(m).graph in registry.FLUX_GRAPHS and c["recipes"]["i2i"]]
    assert flux_i2i and all(models[m]["tiled_refine"] and models[m]["guidance_node"] for m in flux_i2i)
