"""P14 (D82): the angles verb — the `Reangle` recipe resolves `auto` to E12's pair (D77), both graphs compile against the engine's contract,
the weights and lineage are right, and `/capabilities` describes the moves and methods."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.finishers import _parents  # noqa: E402
from loom2.engine.pipeline import placeholder_inputs, plan, preview_problems  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import MOVES, Reangle, parse_recipe, reangle_method, reangle_model_id, warm_group  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402

IMG = {"image": "alley-rain_s20261004.png", "w": 1024, "h": 576}


def test_auto_picks_the_e12_pair():
    assert reangle_method(Reangle(asset_id="a", move="left45")) == "angles_lora"
    assert reangle_method(Reangle(asset_id="a", move="right45")) == "angles_lora"
    for move in ("topdown", "closeup", "wide"):
        assert reangle_method(Reangle(asset_id="a", move=move)) == "klein_prompt", move
    assert reangle_method(Reangle(asset_id="a", move="wide", method="angles_lora")) == "angles_lora"   # an explicit method runs any move
    r = Reangle(asset_id="a", move="left45")
    assert r.model_id == reangle_model_id(r) == registry.reangle_specs()[-1].id            # the Qwen spec (order 50) after Klein (order 1)
    assert warm_group(r) == r.model_id
    assert parse_recipe({"kind": "reangle", "asset_id": "a", "move": "closeup"}).model_id == "klein-9b"
    # D26: under `open` Klein 9B (flux-nc) is not offered, so the framing moves run Klein 4B; the Qwen set is Apache and stays
    k = Reangle(asset_id="a", move="closeup")
    assert reangle_model_id(k, "open") == "klein-4b" and reangle_model_id(k, "full") == "klein-9b" and warm_group(k, "open") == "klein-4b"
    assert reangle_model_id(Reangle(asset_id="a", move="left45"), "open") == "qwen-edit-2509-fp8"
    with pytest.raises(ValueError):
        parse_recipe({"kind": "reangle", "asset_id": "a", "move": "left90"})


@pytest.mark.parametrize("move", MOVES)
def test_both_graphs_compile_against_the_engine(tmp_path: Path, object_info: dict, move: str):
    roster = _pin_review().full_roster(tmp_path)
    for method in ("angles_lora", "klein_prompt"):
        r = Reangle(asset_id="ast_src", move=move, method=method, prompt_text="a harbour at dawn")
        c = graphs.compile_recipe(r, roster, object_info, 7, "loom2/angle", inputs=IMG)
        assert c.problems == [], (method, move, c.problems)
        kinds = [n["class_type"] for n in c.graph.values()]
        if method == "angles_lora":
            assert "TextEncodeQwenImageEditPlus" in kinds and "ModelSamplingAuraFlow" in kinds and kinds.count("LoraLoaderModelOnly") == 2
            assert c.serialized_prompt.startswith(graphs.ANGLE_INSTRUCTIONS[move]) and "harbour" in c.serialized_prompt
            assert c.graph["2"]["inputs"]["type"] == "qwen_image"
        else:
            assert "ReferenceLatent" in kinds and "EmptyFlux2LatentImage" in kinds
            assert (c.graph["9"]["inputs"]["width"], c.graph["9"]["inputs"]["height"]) == (1024, 576)   # the source's size, snapped to 16
            assert c.graph["2"]["class_type"] == "CLIPLoaderGGUF"                                   # D31: Klein's GGUF encoder by default
            assert "strict visual reference" in c.serialized_prompt and c.serialized_prompt.endswith("a harbour at dawn")
        assert c.summary["method"] == method and c.summary["move"] == move and c.output_node == "99"


def test_weights_lineage_plan_and_preview(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    a = Reangle(asset_id="ast_src", move="left45")
    ids = graphs.recipe_weights(a)
    assert {"qwen-edit-2509-fp8", "qwen25vl-7b-fp8", "qwen-image-vae", "qwen-edit-2509-lightning-4", "qwen-edit-2509-angles"} <= set(ids)
    k = Reangle(asset_id="ast_src", move="wide", te_id="qwen3-8b-fp8mixed")
    assert {"klein-9b", "qwen3-8b-fp8mixed", "flux2-vae"} <= set(graphs.recipe_weights(k))
    assert _parents(a) == ["ast_src"]
    p = plan(a)
    assert p.kind == "reangle" and p.model_id == a.model_id and p.needs == ["source"] and p.params["method"] == "angles_lora"
    assert p.estimate["seconds"] == 32.0 and p.count == 1 and p.vram_gb >= 14
    assert placeholder_inputs(a, object_info)["image"]
    assert preview_problems(a, roster, object_info) == []
    assert preview_problems(k, roster, object_info) == []
    assert graphs.recipe_weights(Reangle(asset_id="x", move="wide")) == graphs.recipe_weights(Reangle(asset_id="y", move="wide"))


def test_capabilities_describe_the_verb(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "open"})
    _pin_review().full_roster(tmp_path / "models")
    with TestClient(create_app(state)) as cl:
        caps = cl.get("/capabilities").json()
        rc = caps["reangle"]
        assert rc["moves"] == list(MOVES)
        assert set(rc["methods"]) == {"angles_lora", "klein_prompt"}                     # both Apache: offered under `open` too
        assert rc["methods"]["angles_lora"]["model_id"] == "qwen-edit-2509-fp8" and rc["methods"]["angles_lora"]["seconds"] == 32.0
        assert rc["methods"]["klein_prompt"]["moves"] == ["topdown", "closeup", "wide"] and rc["methods"]["klein_prompt"]["model_id"] == "klein-4b"
        assert rc["auto"] == {"left45": "angles_lora", "right45": "angles_lora", "topdown": "klein_prompt", "closeup": "klein_prompt", "wide": "klein_prompt"}
        pv = cl.post("/recipes/preview", json={"recipe": {"kind": "reangle", "asset_id": "ast_x", "move": "right45"}}).json()
        assert pv["kind"] == "reangle" and pv["params"]["method"] == "angles_lora" and pv["needs"] == ["source"]
        assert pv["estimate"]["seconds"] == 32.0 and "qwen-edit-2509-angles" in pv["weights"]
