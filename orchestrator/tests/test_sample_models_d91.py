"""D91: the sample-model choice — Lumina Image 2.0 (Apache-2.0: `full` and `open`) and SD 3.5 Medium (Stability Community: `full` only)
join Klein 4B as sample models; `/capabilities.sample_models` lists the variant's (the default first), `Settings.samples.model_id` picks one
for the preset swatches (an unknown or not-offered id falls back to the default swatch model), and both compile to their Comfy shapes."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import create_app
from loom2.config import AppState, SampleSettings
from loom2.engine.graphs import compile_recipe
from loom2.models import registry
from loom2.models.spec import ModelSpec
from loom2.preset_icons import swatch_recipe
from loom2.recipes import I2I, T2I
from loom2.roster import ROSTER_BY_ID
from test_graph_parity_d64 import _pin_review

LUMINA, MEDIUM = "lumina-image-2", "sd35-medium-fp8"
IMG = {"image": "alley-rain_s20261004.png", "mask": "alley-rain_s20261004.png", "w": 960, "h": 544}


@pytest.fixture(scope="module")
def roster(tmp_path_factory):
    return _pin_review().full_roster(tmp_path_factory.mktemp("roster"))


def _by_class(g: dict, cls: str) -> list[dict]:
    return [n for n in g.values() if n["class_type"] == cls]


def test_the_two_models_and_their_licences():
    lum, med = registry.get(LUMINA), registry.get(MEDIUM)
    assert lum and med and lum.graph == "lumina2" and med.graph == "sd3"
    assert ROSTER_BY_ID[LUMINA].variants == ["full", "open"] and ROSTER_BY_ID[LUMINA].license == "apache-2.0"
    assert ROSTER_BY_ID[MEDIUM].variants == ["full"] and ROSTER_BY_ID[MEDIUM].license.startswith("stabilityai-ai-community")
    assert ROSTER_BY_ID[LUMINA].folder == ROSTER_BY_ID[MEDIUM].folder == "checkpoints"
    assert lum.recipes.t2i and lum.recipes.sample and not lum.recipes.i2i
    assert med.recipes.t2i and med.recipes.i2i and med.recipes.sample
    assert lum.weights() == [LUMINA] and med.weights() == [MEDIUM]                 # all-in-one checkpoints
    assert registry.offered(lum, "open") and not registry.offered(med, "open")


def test_the_sample_list_and_the_fallback():
    for variant in ("full", "open"):
        ids = [s.id for s in registry.sample_specs(variant)]
        assert ids[0] == registry.default_model("swatch", variant) and len(ids) == len(set(ids))
        assert all(registry.get(i).recipes.sample and registry.offered(registry.get(i), variant) for i in ids)
        assert LUMINA in ids and (MEDIUM in ids) == (variant == "full")
    default = registry.default_model("swatch", "open")
    assert registry.default_model("swatch", "full") == default                    # Klein 4B stays the default in both
    assert registry.sample_model(MEDIUM, "full").id == MEDIUM
    assert registry.sample_model(MEDIUM, "open").id == default                    # not offered under open → the default
    assert registry.sample_model("no-such-model", "full").id == default
    assert registry.sample_model(None, "full").id == default
    t2i_only = next(s.id for s in registry.image_specs() if s.recipes.t2i and not s.recipes.sample)
    assert registry.sample_model(t2i_only, "full").id == default                  # a Generate model that is not a sample model


def test_the_registry_checks_the_sample_flag():
    base = {"id": LUMINA, "family": "lumina2", "label": "x", "graph": "lumina2"}
    registry._check(ModelSpec.model_validate({**base, "recipes": {"t2i": True, "sample": True}}))
    with pytest.raises(registry.RegistryError, match="needs recipes.t2i"):
        registry._check(ModelSpec.model_validate({**base, "recipes": {"sample": True}}))
    with pytest.raises(registry.RegistryError, match="must be a sample model"):
        registry._check(ModelSpec.model_validate({**base, "recipes": {"t2i": True, "default_for": ["swatch"]}}))
    with pytest.raises(registry.RegistryError, match="carries its encoders"):
        registry._check(ModelSpec.model_validate({**base, "recipes": {"t2i": True}, "roles": {"vae": "flux1-ae"}}))


def test_lumina_follows_its_example_workflow(roster, object_info):
    spec = registry.get(LUMINA)
    c = compile_recipe(T2I(model_id=LUMINA, prompt_text="a lighthouse in a storm", negative="blurry ugly bad", width=1024, height=1024), roster, object_info, 7, "loom2/t")
    assert c.problems == []
    g = c.graph
    assert [n["inputs"]["ckpt_name"] for n in _by_class(g, "CheckpointLoaderSimple")] == ["lumina_2.safetensors"]
    assert [n["inputs"]["shift"] for n in _by_class(g, "ModelSamplingAuraFlow")] == [6.0]
    assert _by_class(g, "EmptySD3LatentImage")[0]["inputs"] == {"width": 1024, "height": 1024, "batch_size": 1}
    ks = _by_class(g, "KSampler")[0]["inputs"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"]) == (25, 4.0, "res_multistep", "simple")
    assert g[ks["model"][0]]["class_type"] == "ModelSamplingAuraFlow"
    pos, neg = g[ks["positive"][0]]["inputs"], g[ks["negative"][0]]["inputs"]
    assert pos["text"].startswith("You are an assistant designed to generate superior images") and pos["text"].endswith("<Prompt Start> a lighthouse in a storm")
    assert neg["text"] == "blurry ugly bad"                                        # the example's negative carries no system prompt
    assert pos["clip"] == neg["clip"] == ["1", 1] and _by_class(g, "VAEDecode")[0]["inputs"]["vae"] == ["1", 2]
    assert c.serialized_prompt == "a lighthouse in a storm" and c.summary["prompt_prefix"] == spec.sampling.prompt_prefix


def test_sd35_medium_runs_t2i_and_refine_on_the_sd3_graph(roster, object_info):
    c = compile_recipe(T2I(model_id=MEDIUM, prompt_text="a lighthouse", width=512, height=512), roster, object_info, 7, "loom2/t")
    assert c.problems == []
    g = c.graph
    assert [n["inputs"]["ckpt_name"] for n in _by_class(g, "CheckpointLoaderSimple")] == ["sd3.5_medium_incl_clips_t5xxlfp8scaled.safetensors"]
    ks = _by_class(g, "KSampler")[0]["inputs"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"]) == (40, 4.5, "euler", "sgm_uniform")
    assert not _by_class(g, "ModelSamplingAuraFlow") and "prompt_prefix" not in c.summary
    r = compile_recipe(I2I(document_id="d", model_id=MEDIUM, strength=0.3), roster, object_info, 3, "loom2/t", inputs=IMG)
    assert r.problems == [] and _by_class(r.graph, "KSampler")[0]["inputs"]["denoise"] == 0.3


def test_the_swatch_recipe_follows_the_setting():
    default = registry.default_model("swatch", "full")
    assert swatch_recipe("mood", "eerie", "full")["model_id"] == default
    r = swatch_recipe("mood", "eerie", "full", model_id=LUMINA)
    assert r["model_id"] == LUMINA and r["width"] == r["height"] == registry.get(LUMINA).geometry.sample_px.swatch
    assert swatch_recipe("mood", "eerie", "open", model_id=MEDIUM)["model_id"] == default
    assert swatch_recipe("mood", "eerie", "full", model_id="gone")["model_id"] == default
    assert SampleSettings(model_id="  ").model_id is None and SampleSettings().model_id is None


@pytest.mark.parametrize("variant", ["full", "open"])
def test_capabilities_and_the_make_route(tmp_path: Path, variant: str):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1},
                                     "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": variant})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as c:
        caps = c.get("/capabilities").json()
        sm = caps["sample_models"]
        assert [m["id"] for m in sm] == [s.id for s in registry.sample_specs(variant)]
        assert sm[0]["default"] and sm[0]["id"] == caps["defaults"]["swatch"] and not any(m["default"] for m in sm[1:])
        assert all(m["health"] == "missing" and m["missing"] for m in sm)          # an empty models root: "(not fetched)" in the picker
        assert all(m["id"] in caps["models"] for m in sm)                          # every sample model is a Generate model too
        lum = next(m for m in sm if m["id"] == LUMINA)
        assert (lum["style_px"], lum["swatch_px"]) == (registry.get(LUMINA).geometry.sample_px.style, registry.get(LUMINA).geometry.sample_px.swatch)
        assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "P"}).status_code == 200
        c.post("/queue/pause")
        assert c.put("/settings", json={"samples": {"model_id": MEDIUM}}).json()["samples"]["model_id"] == MEDIUM
        job = c.post("/preset-icons/make", json={"items": [{"field": "mood", "value": "eerie"}]}).json()["jobs"][0]
        assert job["recipe"]["model_id"] == (MEDIUM if variant == "full" else caps["defaults"]["swatch"])
        c.put("/settings", json={"samples": {"model_id": LUMINA}})
        job = c.post("/preset-icons/make", json={"items": [{"field": "mood", "value": "eerie"}]}).json()["jobs"][0]
        assert job["recipe"]["model_id"] == LUMINA
        assert c.put("/settings", json={"samples": {"model_id": ""}}).json()["samples"]["model_id"] is None
