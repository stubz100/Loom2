"""D156 (E41): camera control — the Fun-Camera spec offered in both variants, the Wan graph's two camera nodes when a move is set and its
refusals (a model without the flag, an end frame), the plan's parameters, the weights, and the clip's tone matched to its start image."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from loom2.engine import graphs, tone
from loom2.engine.graphs import CompileError, compile_recipe
from loom2.models import registry
from loom2.recipes import Camera, I2V
from test_graph_parity_d64 import _pin_review

START = "alley-rain_s20261004.png"


@pytest.fixture(scope="module")
def roster(tmp_path_factory):
    return _pin_review().full_roster(tmp_path_factory.mktemp("roster"))


def _nodes(c, cls: str) -> list[dict]:
    return [n for n in c.graph.values() if n["class_type"] == cls]


def camera_model() -> str:
    return next(s.id for s in registry.video_specs() if s.recipes.camera)


def test_the_camera_model_is_a_wan22_i2v_spec_offered_in_both_variants():
    sid = camera_model()
    spec = registry.get(sid)
    assert spec.graph == "wan22" and spec.recipes.i2v and spec.recipes.camera and not spec.recipes.flf
    assert registry.offered(spec, "open") and registry.offered(spec, "full")
    assert sid != registry.default_model("i2v")                                      # the plain model stays the default
    assert set(spec.weights()) >= {sid, spec.roles.extra["low_expert"], spec.roles.extra["lightning_high"], spec.roles.extra["lightning_low"]}


def test_the_graph_swaps_in_the_camera_nodes(roster, object_info):
    sid = camera_model()
    r = I2V(model_id=sid, start_asset="a", prompt_text="she stands still", camera=Camera(move="pan_left", speed=1.5))
    c = compile_recipe(r, roster, object_info, 7, "loom2/c1", inputs={"start": START})
    assert c.problems == [], c.problems
    emb = _nodes(c, "WanCameraEmbedding")
    cond = _nodes(c, "WanCameraImageToVideo")
    assert len(emb) == 1 and len(cond) == 1 and not _nodes(c, "WanImageToVideo")
    assert emb[0]["inputs"] == {"camera_pose": "Pan Left", "width": 832, "height": 480, "length": 81, "speed": 1.5}
    assert cond[0]["inputs"]["camera_conditions"] == [next(k for k, n in c.graph.items() if n["class_type"] == "WanCameraEmbedding"), 0]
    assert cond[0]["inputs"]["start_image"] and cond[0]["inputs"]["length"] == 81
    ks = _nodes(c, "KSamplerAdvanced")
    assert len(ks) == 2 and len(_nodes(c, "LoraLoaderModelOnly")) == 2                 # the Draft recipe, both Lightning LoRAs
    assert c.summary["camera"] == {"move": "pan_left", "speed": 1.5}
    for move, pose in (("zoom_in", "Zoom In"), ("roll_ccw", "Anti Clockwise (ACW)"), ("static", "Static")):
        c2 = compile_recipe(I2V(model_id=sid, start_asset="a", camera=Camera(move=move)), roster, object_info, 1, "loom2/c", inputs={"start": START})
        assert c2.problems == [] and _nodes(c2, "WanCameraEmbedding")[0]["inputs"]["camera_pose"] == pose


def test_without_a_move_the_camera_model_runs_the_plain_graph(roster, object_info):
    c = compile_recipe(I2V(model_id=camera_model(), start_asset="a"), roster, object_info, 1, "loom2/c", inputs={"start": START})
    assert c.problems == [] and _nodes(c, "WanImageToVideo") and not _nodes(c, "WanCameraEmbedding") and "camera" not in c.summary


def test_a_move_is_refused_on_the_plain_model_and_with_an_end_frame(roster, object_info):
    with pytest.raises(CompileError, match="camera"):
        compile_recipe(I2V(start_asset="a", camera=Camera(move="pan_left")), roster, object_info, 1, "loom2/c", inputs={"start": START})
    with pytest.raises(CompileError, match="end frame"):
        compile_recipe(I2V(model_id=camera_model(), start_asset="a", end_asset="b", camera=Camera(move="pan_left")), roster, object_info, 1, "loom2/c", inputs={"start": START, "end": START})
    with pytest.raises(ValueError):
        Camera(move="dolly")                                                           # not a move the node knows
    with pytest.raises(ValueError):
        Camera(move="pan_left", speed=9)


def test_i2v_params_carry_the_move():
    p = graphs.i2v_params(I2V(model_id=camera_model(), start_asset="a", camera=Camera(move="zoom_out", speed=0.5)))
    assert p["camera"] == {"move": "zoom_out", "speed": 0.5}
    assert "camera" not in graphs.i2v_params(I2V(start_asset="a"))


def test_tone_match_takes_a_lifted_clip_back_to_its_start_image(tmp_path: Path):
    rng = np.random.default_rng(3)
    start = rng.integers(20, 200, (48, 64, 3), dtype=np.uint8)
    start_path = tmp_path / "start.png"
    Image.fromarray(start, "RGB").resize((96, 54)).save(start_path)                   # another size and aspect: the fit scales and crops it as the graph did
    base = np.asarray(tone.scaled_like_graph(Image.open(start_path), 64, 48))
    lifted = np.clip(base.astype(np.float64) * 0.95 + np.array([12.0, 14.0, 16.0]), 0, 255).astype(np.uint8)
    paths = []
    for i in range(3):
        p = tmp_path / f"f{i}.png"
        Image.fromarray(lifted, "RGB").save(p)
        paths.append(p)
    r = tone.match_frames_to(paths, start_path)
    assert r["applied"] and r["frames"] == 3 and r["mae_before"] > 5 and r["mae_after"] < 2.5        # the lift reads ~8 levels on this range
    assert abs(r["gains"][0] - 1 / 0.95) < 0.05 and abs(r["offsets"][2] + 16 / 0.95) < 2
    fixed = np.asarray(Image.open(paths[2]).convert("RGB"))
    assert tone.mae(fixed, base) < 2.5
    same = tone.match_frames_to([paths[2]], start_path)                              # already matched: the fit helps nothing and is not applied
    assert same["mae_after"] <= same["mae_before"] + 0.01
