"""P13 ST4 (D76 / D81, 16 §8): Stage → clip — the `I2V` recipe's `guide` puts LTX-2.3's IC-LoRA and the uploaded pass sequence into the E11
graph, the weights carry the LoRA only then, the clip's lineage reaches the guide, the guide route turns per-frame blobs into one video
asset on the stage's album page and records it on the document, and `/capabilities.stage.clip` names the model."""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.pipeline import placeholder_inputs, plan, preview_problems  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V, Guide, parse_recipe  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402

LTX = next(s.id for s in registry.video_specs() if s.graph == "ltx23")
WAN = next(s.id for s in registry.video_specs() if s.graph == "wan22")


def _video_name(object_info: dict) -> str:
    spec = object_info["LoadVideo"]["input"]["required"]["file"]
    return (spec[1]["options"] if isinstance(spec[0], str) else spec[0])[0]                 # V3 dynamic combo: ["COMBO", {options}]


def test_guide_graph_compiles_against_the_engine(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    guide = _video_name(object_info)
    r = I2V(model_id=LTX, start_asset="ast_start", prompt_text="a dolly in on the two figures", frames=81, fps=24, width=1024, height=576,
            guide=Guide(asset_id="ast_guide", kind="depth", strength=0.9))
    c = graphs.compile_recipe(r, roster, object_info, 7, "loom2/clip", inputs={"start": "alley-rain_s20261004.png", "end": None, "beats": {}, "guide": guide})
    assert c.problems == [], c.problems
    kinds = [n["class_type"] for n in c.graph.values()]
    assert "GetICLoRAParameters" in kinds and "LoadVideo" in kinds and "GetVideoComponents" in kinds and kinds.count("LTXVAddGuide") == 1
    assert c.graph["50"]["inputs"]["lora_name"].endswith("ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors")
    assert c.graph["52"]["inputs"]["file"] == guide and c.graph["54"]["inputs"]["frame_idx"] == 0 and c.graph["54"]["inputs"]["strength"] == 0.9
    assert c.graph["54"]["inputs"]["iclora_parameters"] == ["51", 0] and c.graph["14"]["inputs"]["model"] == ["50", 0]
    assert c.graph["13"]["inputs"]["video_latent"] == ["54", 2] and c.graph["20"]["inputs"]["positive"] == ["54", 0]   # the guide is last in the chain
    assert c.summary["guide"] == "depth" and c.summary["frames"] == 81
    plain = graphs.compile_recipe(I2V(model_id=LTX, start_asset="ast_start", frames=81, fps=24, width=1024, height=576), roster, object_info, 7, "x",
                                  inputs={"start": "alley-rain_s20261004.png", "end": None, "beats": {}})
    assert "GetICLoRAParameters" not in [n["class_type"] for n in plain.graph.values()] and plain.graph["14"]["inputs"]["model"] == ["1", 0]
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(r, roster, object_info, 7, "x", inputs={"start": "alley-rain_s20261004.png", "end": None, "beats": {}})       # no upload
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(I2V(model_id=WAN, start_asset="a", guide=Guide(asset_id="g")), roster, object_info, 7, "x",
                              inputs={"start": "alley-rain_s20261004.png", "end": None, "beats": {}, "guide": guide})                         # Wan has no IC-LoRA


def test_weights_plan_preview_and_parsing(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    guided = I2V(model_id=LTX, start_asset="ast_start", frames=81, fps=24, width=1024, height=576, guide=Guide(asset_id="ast_guide"))
    plain = I2V(model_id=LTX, start_asset="ast_start", frames=81, fps=24, width=1024, height=576)
    assert "ltx23-ic-lora-union" in graphs.recipe_weights(guided) and "ltx23-ic-lora-union" not in graphs.recipe_weights(plain)
    p, q = plan(guided), plan(plain)
    assert p.estimate["seconds"] > q.estimate["seconds"] and "IC-LoRA" in p.estimate["source"]
    assert placeholder_inputs(guided, object_info)["guide"] == _video_name(object_info)
    assert preview_problems(guided, roster, object_info) == []
    assert parse_recipe({"kind": "i2v", "model_id": LTX, "start_asset": "a", "guide": {"asset_id": "g", "kind": "pose"}}).guide.kind == "pose"   # type: ignore[union-attr]
    with pytest.raises(ValueError):
        parse_recipe({"kind": "i2v", "model_id": LTX, "start_asset": "a", "guide": {"asset_id": "g", "kind": "normal"}})


def _png(i: int) -> bytes:
    im = Image.new("RGB", (64, 36), (i * 20 % 256, 40, 200 - i * 10 % 200))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_guide_route_encodes_a_video_asset_and_records_it(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        s = cl.post("/stages", json={"name": "Alley"}, headers=H).json()
        cam = s["cameras"][0]["id"]
        shas = []
        for i in range(9):
            data = _png(i)
            sha = hashlib.sha256(data).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=data, headers=H).status_code == 200
            shas.append(sha)
        body = {"camera_id": cam, "revision": 0, "kind": "depth", "fps": 24, "size": {"w": 64, "h": 36}, "range": {"start": 0, "end": 8}, "frames": shas,
                "keypoints": [[[[1, 2, 1]] * 18]] * 9}
        r = cl.post(f"/stages/{s['id']}/guide", json=body, headers=H)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["revision"] == 1 and doc["group_id"] and len(doc["passes"]) == 1
        entry = doc["passes"][0]
        g = entry["guides"]["depth"]
        assert entry["camera_id"] == cam and g["frames"] == 9 and g["fps"] == 24 and g["range"] == {"start": 0, "end": 8}
        a = cl.get(f"/assets/{g['asset_id']}", headers=H).json()
        assert a["kind"] == "video" and a["lineage_kind"] == "stage-pass" and a["suite"] == "stage" and a["frames"] == 9 and a["fps"] == 24.0 and a["w"] == 64
        assert a["params"]["pass"] == "depth-sequence" and len(a["params"]["keypoints"]) == 9 and a["origin"]["surface"] == "guide"
        assert a["path"].endswith(".mp4") and (tmp_path / "proj" / a["path"]).stat().st_size > 500
        page = cl.get(f"/groups/{doc['group_id']}", headers=H).json()
        assert [it["id"] for it in page["group"]["items"]] == [g["asset_id"]]
        # a pose guide joins the same entry; the stills (passes) can come after and keep the guides
        body2 = {**body, "kind": "pose", "revision": 1}
        doc2 = cl.post(f"/stages/{s['id']}/guide", json=body2, headers=H).json()
        assert set(doc2["passes"][0]["guides"]) == {"depth", "pose"} and doc2["revision"] == 2
        assert cl.post(f"/stages/{s['id']}/guide", json={**body, "kind": "normal"}, headers=H).status_code == 422
        assert cl.post(f"/stages/{s['id']}/guide", json={**body, "frames": shas[:1]}, headers=H).status_code == 422
        assert cl.post(f"/stages/{s['id']}/guide", json={**body, "frames": ["0" * 64, "1" * 64]}, headers=H).status_code == 422


def test_capabilities_name_the_clip_model(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    with TestClient(create_app(state)) as cl:
        clip = cl.get("/capabilities").json()["stage"]["clip"]
        assert clip and clip["model_id"] == LTX and clip["seconds"] == 147.0 and clip["kinds"] == ["depth", "pose"] and clip["fps"] == 24 and clip["frame_step"] == 8
        assert clip["health"] != "missing"
