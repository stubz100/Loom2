"""D193 (E64): the H3 (hero) card — the spec, the graph (E64's: the core's H3 nodes, the turbo LoRA, no negative, the sound decoded and saved
beside the frames), the 17n + 5 grid at a fixed 24 fps, the pixel cap, the estimate's exponent, the licence gate (`/capabilities` and the
queue), and the clip that keeps its sound (`sound.flac`, a stereo proxy) on the fake engine."""
from __future__ import annotations

from pathlib import Path

import av
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2.engine import graphs
from loom2.engine.follow import EngineFollower
from loom2.engine.graphs import CompileError, FieldError, compile_recipe
from loom2.models import registry
from loom2.recipes import I2V, Beat, Camera
from test_graph_parity_d64 import _pin_review
from test_lifecycle import Rig

H3 = next(s.id for s in registry.video_specs() if s.graph == "minimax_h3")
INS = {"start": "alley-rain_s20261004.png", "end": "captain-cabin_s20261004.png"}


@pytest.fixture(scope="module")
def roster(tmp_path_factory):
    return _pin_review().full_roster(tmp_path_factory.mktemp("roster"))


def _nodes(c, cls: str) -> list[dict]:
    return [n for n in c.graph.values() if n["class_type"] == cls]


def test_the_spec_is_full_only_waits_for_the_confirmation_and_makes_sound():
    spec = registry.get(H3)
    assert spec.recipes.i2v and spec.recipes.flf and not spec.recipes.beats and not spec.recipes.camera and spec.recipes.extend_lead is None
    assert registry.offered(spec, "full") and not registry.offered(spec, "open")                        # D26: community-licensed
    assert spec.video.sound and not spec.video.takes_negative and list(spec.video.presets) == ["draft"]  # one preset (E64)
    assert spec.geometry.fps == 24 and spec.geometry.fps_fixed and (spec.geometry.frame_step, spec.geometry.frame_base) == (17, 5)
    assert spec.geometry.tiers["draft"] == [864, 480] and spec.geometry.tiers["hd"] == [1024, 576] and spec.geometry.max_px == 1024 * 576
    assert set(spec.weights()) == {H3, spec.roles.te.default, spec.roles.vae, spec.roles.extra["audio_vae"], spec.roles.extra["turbo_lora"]}

    class S:
        h3_licence_confirmed = False
    assert registry.unconfirmed(spec, S()) == ["h3_licence_confirmed"]
    S.h3_licence_confirmed = True
    assert registry.unconfirmed(spec, S()) == []
    assert all(registry.unconfirmed(s, object()) == [] for s in registry.SPECS.values() if s.id != H3)   # nothing else waits for a flag
    assert registry.default_model("i2v") != H3


def test_the_graph_is_e64s(roster, object_info):
    r = I2V(model_id=H3, start_asset="a", end_asset="b", prompt_text="she rises", negative="ignored", frames=124, fps=24, width=864, height=480)
    c = compile_recipe(r, roster, object_info, 7, "loom2/h3", inputs=INS)
    assert c.problems == [], c.problems
    spec = registry.get(H3)
    (node,) = _nodes(c, "MiniMaxH3ImageToVideo")
    assert node["inputs"]["prompt"] == "she rises" and (node["inputs"]["width"], node["inputs"]["height"], node["inputs"]["length"]) == (864, 480, 124)
    for k in ("first_frame", "last_frame"):                                     # scaled and centre-cropped to the canvas before the node
        scale = c.graph[node["inputs"][k][0]]
        assert scale["class_type"] == "ImageScale" and scale["inputs"]["crop"] == "center" and (scale["inputs"]["width"], scale["inputs"]["height"]) == (864, 480)
    (lora,) = _nodes(c, "LoraLoaderModelOnly")
    assert lora["inputs"]["lora_name"].endswith("turbo_8step_v1.0_comfyui_bf16.safetensors")
    assert _nodes(c, "BasicGuider")[0]["inputs"]["model"] == _nodes(c, "BasicScheduler")[0]["inputs"]["model"] == [next(k for k, n in c.graph.items() if n is lora), 0]
    assert _nodes(c, "KSamplerSelect")[0]["inputs"]["sampler_name"] == spec.sampling.sampler == "res_multistep"
    assert _nodes(c, "BasicScheduler")[0]["inputs"] == {**_nodes(c, "BasicScheduler")[0]["inputs"], "scheduler": "simple", "steps": 8, "denoise": 1.0}
    assert _nodes(c, "CLIPLoader")[0]["inputs"]["type"] == "minimax"
    assert not _nodes(c, "CLIPTextEncode") and not _nodes(c, "CFGGuider")      # no negative, no CFG
    (dec_a,) = _nodes(c, "VAEDecodeAudio")
    (save_a,) = _nodes(c, "SaveAudio")
    assert save_a["inputs"]["filename_prefix"] == "loom2/h3" and _nodes(c, "SaveImage")[0]["inputs"]["filename_prefix"] == "loom2/h3"
    assert c.graph[dec_a["inputs"]["vae"][0]]["inputs"]["vae_name"].startswith("minimax_h3_audio_vae")
    assert c.summary["turbo"] is True and c.summary["sound"] is True and c.summary["fps"] == 24
    start_only = compile_recipe(I2V(model_id=H3, start_asset="a", frames=124, fps=24, width=864, height=480), roster, object_info, 7, "x", inputs={"start": INS["start"]})
    assert start_only.problems == [] and "last_frame" not in _nodes(start_only, "MiniMaxH3ImageToVideo")[0]["inputs"]


def test_beats_and_a_camera_move_are_refused(roster, object_info):
    with pytest.raises(CompileError, match="no beats"):
        compile_recipe(I2V(model_id=H3, start_asset="a", end_asset="b", beats=[Beat(frame=20, asset_id="k")]), roster, object_info, 1, "x",
                       inputs={**INS, "beats": {"k": INS["start"]}})
    with pytest.raises(CompileError, match="camera"):
        compile_recipe(I2V(model_id=H3, start_asset="a", camera=Camera(move="pan_left")), roster, object_info, 1, "x", inputs={"start": INS["start"]})


def test_the_grid_the_rate_and_the_cap():
    p = graphs.i2v_params(I2V(model_id=H3, start_asset="a", frames=130, fps=16, width=864, height=480))
    assert p["frames"] == 124 and p["fps"] == 24                                # 17n + 5, snapped down; the sound's rate whatever was asked
    assert graphs.i2v_params(I2V(model_id=H3, start_asset="a", frames=130, size_policy="snap_up"))["frames"] == 141
    with pytest.raises(FieldError) as e:
        graphs.i2v_params(I2V(model_id=H3, start_asset="a", frames=130, size_policy="error"))
    assert e.value.allowed == [124, 141] and "17n+5" in str(e.value)
    for w, h in ((1344, 768), (1280, 720)):
        with pytest.raises(FieldError, match="pixels on this card"):
            graphs.i2v_params(I2V(model_id=H3, start_asset="a", width=w, height=h))
    assert graphs.i2v_params(I2V(model_id=H3, start_asset="a", width=1024, height=576))["width"] == 1024
    wan = graphs.i2v_params(I2V(start_asset="a", frames=83, fps=20))
    assert wan["frames"] == 81 and wan["fps"] == 20                             # the others keep 4n + 1 and the panel's rate


def test_the_estimate_follows_e64():
    draft = graphs.estimate_i2v_seconds(I2V(model_id=H3, start_asset="a", frames=124, width=864, height=480))
    hd = graphs.estimate_i2v_seconds(I2V(model_id=H3, start_asset="a", frames=124, width=1024, height=576))
    assert draft["seconds"] == 138.0 and abs(hd["seconds"] - 240.7) < 3 and "E64" in hd["source"]   # E64: 137.9 s and 240.7 s
    longer = graphs.estimate_i2v_seconds(I2V(model_id=H3, start_asset="a", frames=243, width=864, height=480))
    assert longer["seconds"] > 2 * draft["seconds"]                              # superlinear in the work
    wan = registry.get(registry.default_model("i2v"))
    assert wan.estimates.work_exponent == 1.0                                    # the others as before


def test_outputs_collect_the_saved_sound():
    hist = {"outputs": {"22": {"images": [{"filename": "a_00001_.png", "subfolder": "loom2", "type": "output"}]},
                        "24": {"audio": [{"filename": "a_00001_.flac", "subfolder": "loom2", "type": "output"}]}}}
    assert {f["filename"] for f in EngineFollower.outputs(hist)} == {"a_00001_.png", "a_00001_.flac"}


def test_capabilities_list_h3_only_once_confirmed(tmp_path: Path):
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert H3 not in cl.get("/capabilities").json()["i2v"]["models"]
        assert cl.put("/settings", json={"h3_licence_confirmed": True}).status_code == 200
        m = cl.get("/capabilities").json()["i2v"]["models"][H3]
        assert m["sound"] is True and m["takes_negative"] is False and list(m["presets"]) == ["draft"] and m["preset_params"]["draft"]["turbo"] is True
        assert m["geometry"]["frame_base"] == 5 and m["geometry"]["fps_fixed"] is True and m["geometry"]["max_px"] == 589824 and m["short"] == "H3"
        wan = cl.get("/capabilities").json()["i2v"]["models"][registry.default_model("i2v")]
        assert wan["sound"] is False and wan["takes_negative"] is True


@pytest.mark.asyncio
async def test_a_clip_keeps_its_sound_on_the_fake_engine(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        rig.queue.load()
        await rig.queue.start()
        img = tmp_path / "s.png"
        Image.new("RGB", (96, 54), (40, 60, 90)).save(img)
        start = rig.catalogue.ingest_file(img, move=False, suite="animate")
        body = {"kind": "i2v", "model_id": H3, "start_asset": start.id, "end_asset": start.id, "prompt_text": "she rises", "frames": 22, "fps": 24,
                "width": 864, "height": 480}
        with pytest.raises(ValueError, match="Settings › Licences"):
            rig.queue.submit(body)                                               # D193: refused until the confirmation
        rig.app.update_settings({"h3_licence_confirmed": True})
        job = rig.queue.submit(body)[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        from loom2.clips import ClipStore
        rec = ClipStore(rig.ws).get(done.result["clip_id"])
        assert rec.frames == 22 and rec.fps == 24 and rec.sound_path and rec.sound_path.endswith("sound.flac")
        assert (rig.ws.path / rec.sound_path).is_file() and not list((rig.ws.path / rec.master_dir).glob("*.flac"))
        with av.open(str(rig.ws.path / rec.proxy_path)) as c:
            assert len(c.streams.video) == 1 and len(c.streams.audio) == 1
            a = c.streams.audio[0]
            assert a.codec_context.sample_rate == 32000 and a.codec_context.layout.nb_channels == 2   # stereo kept
        assert any("its sound" in x for x in done.log_tail)
    finally:
        await rig.close()
