"""2026-10-23: the Generate panel's preview for every text-to-image model, and an unexpected error the WebView can read.

Lumina 2 and SD 3.5 carry their encoder in the checkpoint, so their preview's `te_id` is None; the reply model typed it `str`, the reply
failed validation, and the bare 500 (no CORS headers) reached the panel as `TypeError: Failed to fetch` with Generate disabled.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loom2.api import DEV_ORIGINS, create_app
from loom2.config import AppState


def _app(tmp_path: Path, variant: str):
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": variant})
    return create_app(state)


def _panel_recipe(model_id: str, mode: str) -> dict:
    """What the panel sends for a model picked with its defaults (generateStore.recipeFromPanel: nulls take the model's own)."""
    return {"kind": "t2i", "model_id": model_id, "prompt_mode": mode, "prompt_json": {"subjects": [{"description": "a red fox"}]} if mode == "tree" else None,
            "prompt_text": "a red fox", "negative": "", "width": 960, "height": 544, "steps": None, "guidance": None, "cfg": None, "sampler": None,
            "scheduler": None, "turbo": True, "turbo_strength": 1, "weight_dtype": None, "te_device": None, "te_id": None, "base_shift": None,
            "max_shift": None, "tiled_vae": False, "tile_size": 512, "seeds": [0, 0, 0, 0], "refs": [], "ref_max_px": 1024, "loras": [],
            "auto_lora": True, "mentions": [], "style_id": None}


@pytest.mark.parametrize("variant", ["full", "open"])
def test_every_t2i_model_previews(variant, tmp_path: Path):
    with TestClient(_app(tmp_path, variant)) as cl:
        models = {m: c for m, c in cl.get("/capabilities").json()["models"].items() if c["recipes"].get("t2i")}
        assert {"lumina-image-2"} <= set(models) and (variant == "open" or "sd35-medium-fp8" in models)
        for m in models:
            for mode in ("tree", "text"):
                r = cl.post("/recipes/preview", json={"recipe": _panel_recipe(m, mode)})
                assert r.status_code == 200, (m, mode, r.text[:300])
                assert r.json()["model_id"] == m
        own = cl.post("/recipes/preview", json={"recipe": _panel_recipe("lumina-image-2", "text")}).json()
        assert own["te_id"] is None and own["weights"] == ["lumina-image-2"]                     # the all-in-one checkpoint: no encoder of its own


def test_an_unexpected_error_answers_json_the_webview_can_read(tmp_path: Path):
    app = _app(tmp_path, "full")

    async def boom():
        raise RuntimeError("the route broke")
    app.add_api_route("/__boom", boom)
    origin = DEV_ORIGINS[1]
    with TestClient(app, raise_server_exceptions=False) as cl:
        r = cl.get("/__boom", headers={"Origin": origin, "X-Loom-Token": app.state.services.app.token})
        assert r.status_code == 500
        assert r.json()["detail"] == "Internal error (RuntimeError): see the orchestrator's log"
        assert r.headers["access-control-allow-origin"] == origin                                 # CORS saw the reply: the client reads it
        assert cl.get("/health", headers={"Origin": origin}).status_code == 200                  # and the next request is served
    with TestClient(app) as cl, pytest.raises(RuntimeError, match="the route broke"):            # still raised after the reply: logged, and tests see it
        cl.get("/__boom")
