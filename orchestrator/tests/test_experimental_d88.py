"""D88 (19 §7): extension (XE) and lip-sync (XL) back as experimental features — the LTX lead-in guide and the Wan last-frame start, the
chain record and its lineage, the S2V graph, the submission's sentences, the audio in the proxy, the lip-sync take on the shot version,
the routes (`/clips/{id}/extend`, the shot version's `lipsync`) and `/capabilities.experimental`."""
from __future__ import annotations

import sys
from pathlib import Path

import av
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.clips import ClipStore  # noqa: E402
from loom2.engine import graphs  # noqa: E402
from loom2.engine.pipeline import plan  # noqa: E402
from loom2.models import registry  # noqa: E402
from loom2.recipes import I2V, AudioRef, ExtendFrom  # noqa: E402
from loom2.story import StoryStore  # noqa: E402

from fake_tts import tone  # noqa: E402
from test_graph_parity_d64 import _pin_review  # noqa: E402
from test_lifecycle import Rig  # noqa: E402
from test_stage_clip_d81 import _video_name  # noqa: E402

LTX = next(s.id for s in registry.video_specs() if s.graph == "ltx23")
WAN = next(s.id for s in registry.video_specs() if s.graph == "wan22")
S2V = registry.lipsync_specs()[0].id
INS = {"start": "alley-rain_s20261004.png", "end": None, "beats": {}}


def _audio_name(object_info: dict) -> str:
    spec = object_info["LoadAudio"]["input"]["required"]["audio"]
    names = spec[1]["options"] if isinstance(spec[0], str) else spec[0]
    return names[0] if names else "line.wav"


def test_graphs(tmp_path: Path, object_info: dict):
    roster = _pin_review().full_roster(tmp_path)
    lead = _video_name(object_info)
    r = I2V(model_id=LTX, start_asset="a", prompt_text="she keeps walking", frames=81, fps=24, width=1024, height=576, extend_from=ExtendFrom(clip_id="clp_x", lead=9))
    c = graphs.compile_recipe(r, roster, object_info, 7, "x", inputs={**INS, "lead": lead})
    assert c.problems == [], c.problems
    g = c.graph
    assert g["56"]["inputs"]["file"] == lead and g["59"]["class_type"] == "LTXVAddGuide" and g["59"]["inputs"]["frame_idx"] == 0
    assert g["13"]["inputs"]["video_latent"] == ["59", 2] and g["14"]["inputs"]["conditioning"] == ["59", 0] and g["20"]["inputs"]["positive"] == ["59", 0]
    assert c.summary["extend_from"] == "clp_x" and c.summary["lead"] == 9 and c.summary["experimental"] is True
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(r, roster, object_info, 7, "x", inputs=INS)                                  # the lead-in not uploaded
    w = graphs.compile_recipe(I2V(model_id=WAN, start_asset="a", extend_from=ExtendFrom(clip_id="clp_x", lead=1)), roster, object_info, 7, "x", inputs=INS)
    assert "LoadVideo" not in {n["class_type"] for n in w.graph.values()} and w.summary["lead"] == 1      # Wan: the start is the last frame
    audio = _audio_name(object_info)
    s = I2V(model_id=S2V, start_asset="a", prompt_text="she says it", frames=49, fps=16, width=832, height=480, audio=AudioRef(asset_id="ast_line"))
    c2 = graphs.compile_recipe(s, roster, object_info, 7, "x", inputs={**INS, "audio": audio})
    assert c2.problems == [], c2.problems
    k = {n["class_type"] for n in c2.graph.values()}
    assert {"AudioEncoderLoader", "AudioEncoderEncode", "WanSoundImageToVideo", "LoadAudio"} <= k
    assert c2.graph["12"]["inputs"]["steps"] == 20 and c2.graph["12"]["inputs"]["cfg"] == 6.0 and c2.graph["12"]["inputs"]["sampler_name"] == "uni_pc"
    assert c2.graph["10"]["inputs"]["length"] == 49 and c2.graph["8"]["inputs"]["audio"] == audio and c2.summary["audio"] == "ast_line"
    fast = graphs.compile_recipe(s.model_copy(update={"preset": "fast"}), roster, object_info, 7, "x", inputs={**INS, "audio": audio})
    assert fast.graph["12"]["inputs"]["steps"] == 10
    for bad in (s.model_copy(update={"audio": None}), I2V(model_id=LTX, start_asset="a", audio=AudioRef(asset_id="z"))):
        with pytest.raises(graphs.CompileError):
            graphs.compile_recipe(bad, roster, object_info, 7, "x", inputs={**INS, "audio": audio})
    with pytest.raises(graphs.FieldError):
        graphs.i2v_params(s.model_copy(update={"frames": 81}))
    p = plan(s)
    assert p.estimate["seconds"] and "experimental" in p.estimate["source"] and {S2V, "wav2vec2-large-english"} <= set(p.weights)


def _clip(ws, tmp: Path, model: str, n: int = 12, w: int = 64, h: int = 36):
    src = tmp / "frames"
    src.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(n):
        p = src / f"{model[:3]}{i:03d}.png"
        Image.new("RGB", (w, h), (i * 20 % 256, 90, 140)).save(p)
        paths.append(p)
    store = ClipStore(ws)
    rec = store.create(paths, model_id=model, fps=24, start_asset_id="ast_s", prompt="walk", params={"recipe": {"frames": n, "width": 1024, "height": 576}})
    return store, store.encode_proxy(rec)


@pytest.mark.asyncio
async def test_extend_and_lipsync_jobs_on_the_fake_engine(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        _pin_review().full_roster(tmp_path / "models")
        rig.roster.scan()
        rig.queue.load()
        await rig.queue.start()
        store, prev = _clip(rig.ws, tmp_path, LTX)
        a = rig.catalogue.ingest_file(store.dir(prev.id) / "proxy.mp4", kind="video", in_place=True, suite="animate", params={"clip_id": prev.id})
        prev.asset_id = a.id
        store.save(prev)
        last = tmp_path / "last.png"
        Image.new("RGB", (64, 36), (200, 90, 140)).save(last)
        start = rig.catalogue.ingest_file(last, move=False, suite="animate")
        body = {"kind": "i2v", "model_id": LTX, "start_asset": start.id, "prompt_text": "on", "frames": 9, "fps": 24, "width": 1024, "height": 576,
                "extend_from": {"clip_id": prev.id, "lead": 9}}
        for bad, why in (({**body, "extend_from": {"clip_id": "clp_gone", "lead": 9}}, "not in the project"), ({**body, "extend_from": {"clip_id": prev.id, "lead": 1}}, "last 9"),
                         ({**body, "model_id": WAN}, "own model")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit(bad)
        job = rig.queue.submit(body)[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert any("lead-in: the last 9 frames" in x for x in done.log_tail)
        sent = rig.fake.prompts[-1]["graph"]
        assert any(n["class_type"] == "LTXVAddGuide" and n["inputs"].get("frame_idx") == 0 and isinstance(n["inputs"]["image"], list) and sent[n["inputs"]["image"][0]]["class_type"] == "ImageScale"
                   for n in sent.values())
        nxt = store.get(done.result["clip_id"])
        assert nxt.chained_from == prev.id and nxt.overlap == 9 and nxt.audio_asset_id is None
        assert prev.asset_id in rig.catalogue.get(done.result["asset_ids"][0]).parents
        # lip-sync: an English line of 3 s, a shot version with a frame; the clip carries the line and lands as a take
        wav = tmp_path / "line.wav"
        tone(str(wav), 3.0)
        line = rig.catalogue.ingest_file(wav, kind="audio", move=False, suite="story", params={"language": "English"})
        de_wav = tmp_path / "de.wav"
        tone(str(de_wav), 2.0)
        de = rig.catalogue.ingest_file(de_wav, kind="audio", move=False, suite="story", params={"language": "German"})
        long_wav = tmp_path / "long.wav"
        tone(str(long_wav), 6.0)
        long = rig.catalogue.ingest_file(long_wav, kind="audio", move=False, suite="story")
        face = rig.catalogue.ingest_file(last, move=False, suite="story")
        st = StoryStore(rig.ws)
        sh = st.create_shot("Talk", frame_asset_id=face.id)
        lip = {"kind": "i2v", "model_id": S2V, "start_asset": face.id, "prompt_text": "she speaks", "frames": 49, "fps": 16, "width": 832, "height": 480,
               "preset": "fast", "audio": {"asset_id": line.id}}
        for bad, why in (({**lip, "audio": None}, "voice the line"), ({**lip, "audio": {"asset_id": de.id}}, "English only"), ({**lip, "audio": {"asset_id": long.id}}, "6.0 s"),
                         ({**lip, "audio": {"asset_id": face.id}}, "not an audio asset"), ({**lip, "end_asset": face.id}, "one image and one line")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit(bad)
        from loom2.origin import JobOrigin
        job = rig.queue.submit(lip, origin=JobOrigin(suite="story", surface="lipsync", ref=sh.id, payload={"version": "v1"}))[0]
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert any(n["class_type"] == "WanSoundImageToVideo" for n in rig.fake.prompts[-1]["graph"].values())
        rec = store.get(done.result["clip_id"])
        assert rec.audio_asset_id == line.id and rec.frames == 49
        with av.open(str(rig.ws.path / rec.proxy_path)) as c:
            assert len(c.streams.audio) == 1 and len(c.streams.video) == 1
        assert set(rig.catalogue.get(done.result["asset_ids"][0]).parents) == {face.id, line.id}
        v = st.shot(sh.id).version("v1")
        assert any(t.kind == "clip" and t.id == rec.id for t in v.takes) and v.clip_id is None            # a take, not the version's clip
    finally:
        await rig.close()


def test_routes_and_capabilities(tmp_path: Path):
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ex = cl.get("/capabilities").json()["experimental"]
        assert ex["extend"]["models"] == {LTX: 9, WAN: 1} and "experimental" in ex["extend"]["caveat"]
        lp = ex["lipsync"]
        assert lp["available"] and lp["model_id"] == S2V and lp["languages"] == ["English"] and lp["frames_max"] == 77 and lp["seconds_max"] == 4.81
        assert set(lp["presets"]) == {"draft", "fast"} and lp["presets"]["fast"]["steps"] == 10 and "English" in lp["caveat"]
        svc = app.state.services
        ws = svc.ws
        store, prev = _clip(ws, tmp_path, LTX)
        r = cl.post(f"/clips/{prev.id}/extend", json={"stage": True, "prompt_text": "she keeps walking"})
        assert r.status_code == 200, r.text
        x = r.json()
        assert x["lead"] == 9 and x["model_id"] == LTX and x["staged"] is True
        job = next(j for j in cl.get("/jobs").json()["items"] if j["id"] == x["job_id"])
        assert job["recipe"]["extend_from"] == {"clip_id": prev.id, "lead": 9} and job["recipe"]["start_asset"] == x["start_asset_id"] and job["origin"]["surface"] == "extend"
        a = cl.get(f"/assets/{x['start_asset_id']}").json()
        assert a["lineage_kind"] == "frame-extract" and a["params"]["frame_index"] == prev.frames - 1
        assert cl.post("/clips/clp_gone/extend", json={}).status_code == 404
        # lip-sync on a shot version: the line's voice, the version's frame; frames from the line's length
        wav = tmp_path / "line.wav"
        tone(str(wav), 3.0)
        line = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        img = tmp_path / "f.png"
        Image.new("RGB", (64, 36), (10, 20, 30)).save(img)
        face = svc.catalogue.ingest_file(img, move=False, suite="story")
        st = StoryStore(ws)
        sh = st.create_shot("Talk", frame_asset_id=face.id)
        bare = st.create_shot("Bare")
        n = st.create_node("dialogue", "Hello", lines=[{"speaker": None, "text": "Hi."}, {"speaker": None, "text": "Unvoiced."}])
        st.set_line_audio(n.id, 0, line.id, "Hi.")
        r = cl.post(f"/story/shots/{sh.id}/versions/v1/lipsync", json={"node_id": n.id, "index": 0, "preset": "fast"})
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["frames"] == 49 and q["audio_asset_id"] == line.id and q["image_asset_id"] == face.id and q["staged"] is True and q["seconds"] == 545.0
        assert cl.post(f"/story/shots/{sh.id}/versions/v1/lipsync", json={"node_id": n.id, "index": 1}).json()["detail"].startswith("the line has no voice")
        assert "no frame" in cl.post(f"/story/shots/{bare.id}/versions/v1/lipsync", json={"audio_asset_id": line.id}).json()["detail"]
        assert cl.post(f"/story/shots/{sh.id}/versions/v9/lipsync", json={"audio_asset_id": line.id}).status_code == 404
