"""CN4 (19 §3d, D87, E19 GO): the `animate` clip method — Wan2.2 Animate Move through the `I2V` recipe with the Stage's pose pass as the
guide and the start image as the character's reference: the spec stays out of the Animate suite's I2V list, the graph is E19's (the
LightX2V LoRA, CLIP vision on the reference, WanAnimateToVideo, the trim), one window of ≤ 77 frames, the weights and the estimate, the
submission's sentences (the pose pass required, one figure per pass, no end frame or beats), the reference padded into the clip before
upload (never cropped), a clip through the fake engine with lineage to the reference and the pass, and /capabilities.stage.animate."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.engine import graphs  # noqa: E402
from loom2.engine.pipeline import pad_reference, plan  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V, Guide  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_lifecycle import Rig  # noqa: E402
from test_stage_clip_d81 import _video_name  # noqa: E402

ANIM = registry.animate_specs()[0].id
LTX = next(s.id for s in registry.video_specs() if s.graph == "ltx23")


def _r(**kw) -> I2V:
    base = {"model_id": ANIM, "start_asset": "ast_ref", "prompt_text": "she waves at the camera", "frames": 77, "fps": 24, "width": 832, "height": 480,
            "guide": Guide(asset_id="ast_pose", kind="pose")}
    return I2V(**{**base, **kw})


def test_the_spec_and_the_graph(tmp_path: Path, object_info: dict):
    spec = registry.get(ANIM)
    assert spec and spec.recipes.animate and not spec.recipes.i2v and spec.graph == "wan_animate" and spec.recipes.guide_figures == 1
    assert ANIM not in [s.id for s in registry.video_specs()]                                   # not an Animate-suite model
    roster = _pin_review().full_roster(tmp_path)
    guide = _video_name(object_info)
    c = graphs.compile_recipe(_r(), roster, object_info, 7, "loom2/clip", inputs={"start": "alley-rain_s20261004.png", "end": None, "beats": {}, "guide": guide})
    kinds = {n["class_type"] for n in c.graph.values()}
    assert {"WanAnimateToVideo", "CLIPVisionLoader", "CLIPVisionEncode", "TrimVideoLatent", "LoadVideo", "GetVideoComponents", "LoraLoaderModelOnly"} <= kinds
    assert c.problems == [], c.problems
    g = c.graph
    assert g["11"]["inputs"]["pose_video"] == ["54", 0] and g["11"]["inputs"]["reference_image"] == ["100s", 0] and g["11"]["inputs"]["length"] == 77
    assert g["11"]["inputs"]["width"] == 832 and g["11"]["inputs"]["height"] == 480 and g["52"]["inputs"]["file"] == guide
    assert g["12"]["inputs"]["steps"] == 4 and g["12"]["inputs"]["cfg"] == 1.0 and g["1s"]["inputs"]["shift"] == 8.0
    assert g["13"]["inputs"]["trim_amount"] == ["11", 3] and g["1l"]["inputs"]["lora_name"].startswith("lightx2v_I2V_14B")
    assert g["4"]["inputs"]["clip_name"] == "clip_vision_h.safetensors" and g["100s"]["inputs"]["crop"] == "center"
    assert c.summary["frames"] == 77 and c.summary["guide"] == "pose" and c.summary["steps"] == 4
    ins = {"start": "alley-rain_s20261004.png", "end": None, "beats": {}, "guide": guide}
    for bad in (_r(guide=None), _r(guide=Guide(asset_id="g", kind="depth")), _r(end_asset="ast_end")):
        with pytest.raises(graphs.CompileError):
            graphs.compile_recipe(bad, roster, object_info, 7, "x", inputs=ins)
    with pytest.raises(graphs.FieldError):
        graphs.i2v_params(_r(frames=81))                                                          # one window: ≤ 77 frames (E19)
    assert graphs.i2v_params(_r(frames=40))["frames"] == 37                                       # 4n+1, snapped down
    assert graphs.animate_pad_size(_r(width=848)) == (848, 480)


def test_weights_estimate_and_padding(tmp_path: Path):
    w = graphs.recipe_weights(_r())
    assert {ANIM, "clip-vision-h", "lightx2v-i2v-4step", "umt5-xxl-fp8", "wan21-vae"} <= set(w) and "ltx23-ic-lora-union" not in w
    p = plan(_r())
    assert p.estimate["seconds"] == 128.0 and "E19" in p.estimate["source"] and p.vram_gb == 14.5 and p.params["guide"] if "guide" in p.params else True
    src = tmp_path / "hero.png"
    Image.new("RGB", (400, 600), (180, 60, 40)).save(src)                                         # a portrait hero

    class Q:
        class ws:
            temp_dir = tmp_path / "_temp"
    out = pad_reference(Q, src, 832, 480, "hero")                                                 # type: ignore[arg-type]
    with Image.open(out) as im:
        assert im.size == (832, 480)
        assert im.getpixel((416, 240)) == (180, 60, 40)                                           # the hero in the middle, whole
        assert im.getpixel((5, 240)) == (180, 60, 40)                                             # the pad: the image's own edge colour (flat here)
        box = im.convert("L").point(lambda v: 255 if v else 0).getbbox()
        assert box == (0, 0, 832, 480)


@pytest.mark.asyncio
async def test_submission_padding_and_a_clip_on_the_fake_engine(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        src = tmp_path / "src"
        src.mkdir()
        Image.new("RGB", (400, 600), (120, 160, 90)).save(src / "hero.png")
        hero = rig.catalogue.ingest_file(src / "hero.png", move=False, suite="story")
        import av, numpy as np
        mp4 = src / "pose.mp4"
        with av.open(str(mp4), "w") as c:
            s = c.add_stream("libx264", rate=24)
            s.width, s.height, s.pix_fmt = 64, 36, "yuv420p"
            for i in range(9):
                for pkt in s.encode(av.VideoFrame.from_ndarray(np.full((36, 64, 3), i * 20, np.uint8), format="rgb24")):
                    c.mux(pkt)
            for pkt in s.encode():
                c.mux(pkt)
        one = [[[[10, 10, 1]] * 18]] * 9
        two = [[[[10, 10, 1]] * 18, [[30, 10, 1]] * 18]] * 9
        pose1 = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", lineage_kind="stage-pass", params={"pass": "pose-sequence", "keypoints": one})
        pose2 = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", lineage_kind="stage-pass", params={"pass": "pose-sequence", "keypoints": two})
        depth = rig.catalogue.ingest_file(mp4, kind="video", move=False, suite="stage", params={"pass": "depth-sequence"})
        rig.queue.load()
        await rig.queue.start()
        body = {"kind": "i2v", "model_id": ANIM, "start_asset": hero.id, "prompt_text": "she waves", "frames": 9, "fps": 24, "width": 832, "height": 480,
                "guide": {"asset_id": pose1.id, "kind": "pose"}}
        for bad, why in (({**body, "guide": None}, "pose sequence"), ({**body, "guide": {"asset_id": depth.id, "kind": "depth"}}, "pose sequence"),
                         ({**body, "guide": {"asset_id": pose2.id, "kind": "pose"}}, "holds 2 figures"), ({**body, "end_asset": hero.id}, "no end frame"),
                         ({**body, "guide": {"asset_id": "ast_gone", "kind": "pose"}}, "missing from the Catalogue")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit(bad)
        job = rig.queue.submit(body)[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert any("reference padded into 832×480" in x for x in done.log_tail)
        sent = rig.fake.prompts[-1]["graph"]
        assert any(n["class_type"] == "WanAnimateToVideo" for n in sent.values())
        up = next(p for p in (rig.ws.temp_dir / "refs").glob("loom2ref-anim-*.png"))
        with Image.open(up) as im:
            assert im.size == (832, 480)
        a = rig.catalogue.get(done.result["asset_ids"][0])
        assert a.kind == "video" and set(a.parents) == {hero.id, pose1.id} and a.model_id == ANIM and a.frames == 9
    finally:
        await rig.close()


def test_capabilities_name_the_animate_method(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    with TestClient(create_app(state)) as cl:
        caps = cl.get("/capabilities").json()
        an = caps["stage"]["animate"]
        assert an and an["model_id"] == ANIM and an["kinds"] == ["pose"] and an["seconds"] == 200.0 and an["frames_max"] == 77 and an["figures_max"] == 1
        assert an["size"] == [832, 480] and an["frame_step"] == 4 and an["health"] != "missing"
        assert caps["stage"]["clip"]["model_id"] == LTX                                         # the IC-LoRA method stays
        assert ANIM not in [m["model_id"] for m in caps["i2v"]["models"]] if isinstance(caps["i2v"].get("models"), list) else ANIM not in caps["i2v"].get("models", {})
