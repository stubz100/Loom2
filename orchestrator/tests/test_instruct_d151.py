"""D151 (post-MVP item 8): an edit by instruction in the Edit AI tab — the Instruct recipe, its graph on Qwen-Image-Edit 2509 fp8 +
Lightning (the angles verb's weights without the angles LoRA), the estimate, the document route and the capabilities."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs, pipeline  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import Instruct, parse_recipe  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def _pin_review():
    spec = importlib.util.spec_from_file_location("pin_review", REPO / "scripts" / "pin_review.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_the_recipe_runs_the_registrys_instruct_model():
    r = parse_recipe({"kind": "instruct", "prompt_text": "make it dusk"})
    assert isinstance(r, Instruct) and r.model_id == registry.default_model("instruct") and r.source == "visible" and r.max_pixels == 1_048_576
    spec = registry.get(r.model_id)
    assert spec is not None and spec.recipes.instruct and spec.recipes.reangle          # the same weights serve the Angle tab (D82)
    for bad in ({"kind": "instruct", "max_pixels": 1000}, {"kind": "instruct", "source": "selection"}):
        with pytest.raises(ValueError):
            parse_recipe(bad)


def test_the_graph_is_the_angles_graph_without_its_lora(object_info: dict):
    pr = _pin_review()
    roster = pr.full_roster(Path(tempfile.mkdtemp(prefix="instruct-")))
    img = {"image": "alley-rain_s20261004.png", "w": 960, "h": 544}
    c = graphs.compile_recipe(Instruct(document_id="d", prompt_text="make it dusk, the lamps lit"), roster, object_info, 7, "loom2/t", inputs=img)
    kinds = [n["class_type"] for n in c.graph.values()]
    assert kinds.count("LoraLoaderModelOnly") == 1                                      # Lightning stays, the angles LoRA goes
    assert "TextEncodeQwenImageEditPlus" in kinds and "ImageScaleToTotalPixels" in kinds and "SaveImage" in kinds
    assert c.graph["7"]["inputs"]["prompt"] == "make it dusk, the lamps lit" and c.graph["8"]["inputs"]["prompt"] == ""
    assert c.graph["20"]["inputs"]["megapixels"] == 1.0 and c.graph["10"]["inputs"]["seed"] == 7
    assert c.summary["instruction"] == "make it dusk, the lamps lit" and c.summary["source"] == "visible"
    assert not [p for p in c.problems if "not in enum" not in p]
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(Instruct(document_id="d", prompt_text="   "), roster, object_info, 1, "loom2/t", inputs=img)
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(Instruct(document_id="d", prompt_text="x"), roster, object_info, 1, "loom2/t")   # no upload


def test_the_estimate_is_the_models_measured_seconds():
    p = pipeline.plan(Instruct(document_id="d", prompt_text="snow on the street"))
    spec = registry.get(registry.default_model("instruct"))
    assert spec is not None and p.estimate["seconds"] == spec.estimates.base_seconds and "document" in p.needs
    assert p.params["instruction"] == "snow on the street"


def test_the_document_route_and_the_capabilities(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    client = TestClient(app)
    H = {"X-Loom-Token": app.state.services.app.token}
    with client:
        assert client.post("/project", json={"path": str(tmp_path / "proj"), "name": "AI", "size_cap_gb": 10}, headers=H).status_code == 200
        client.post("/queue/pause", headers=H)
        caps = client.get("/capabilities", headers=H).json()
        assert caps["instruct"]["default"] == registry.default_model("instruct") and caps["instruct"]["models"][caps["instruct"]["default"]]["health"] in ("missing", "present", "verified")
        did = client.post("/documents", json={"w": 64, "h": 48, "name": "ai"}, headers=H).json()["id"]
        r = client.post(f"/documents/{did}/ai", json={"recipe": {"kind": "instruct", "prompt_text": "make it dusk", "seeds": [1, 2]}, "stage": True}, headers=H)
        assert r.status_code == 200, r.text
        jobs = r.json()["jobs"]
        assert len(jobs) == 2 and all(j["kind"] == "instruct" and j["recipe"]["document_id"] == did and j["status"] == "staged" for j in jobs)
        pv = client.post("/recipes/preview", json={"recipe": {"kind": "instruct", "document_id": did, "prompt_text": "make it dusk"}}, headers=H)
        assert pv.status_code == 200, pv.text
        assert json.dumps(pv.json()).count("instruct") >= 1
