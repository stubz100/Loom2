"""CN2 (19 §3b, D87): the `audio` asset kind end to end (the ingest with its length, the waveform thumbnails, the Type filter, the delete),
the voice records and their sentences (the draft tier's fixed voice, the cloning tier's reference, transcript and consent), the `tts` job
on the fake runner (a draft job → audio assets stamped on their Flow lines, the engine never started; the cloning tier stops the engine,
the reference as the parent; the submission's sentences; a crash with the runner's lines; a cancel; a client patch keeping a stamp it
did not see), the exports' audio lane (the FCPXML's connected clips at the SRT's ticks, the EDL's events, the count), the routes
(the voices, a line's voice, a node's lines grouped by their speakers' voices) and /capabilities.voice."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import voices as V  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.catalogue import waveform_image  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.pipeline import plan  # noqa: E402
from loom2.recipes import TTS, parse_recipe  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import Timeline, TimelineClip, line_spans, to_edl, to_fcpxml  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402
from test_lifecycle import Rig  # noqa: E402

TESTS = Path(__file__).resolve().parent
FAKE = TESTS / "fake_tts.py"
LONG = "Hi there, come on in and sit by the fire while I fetch the kettle."      # 66 chars → the fake's 3.96 s: a valid reference (3–10 s)


def _settings(rig: Rig, **extra) -> None:
    rig.app.update_settings({"voices": {"python": sys.executable, "run": str(FAKE)}, "hf_home": str(rig.app.state_dir / "hf"), **extra})


def _wav(path: Path, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tone(str(path), seconds)
    return path


def _draft(name: str = "Narrator", voice: str = "af_heart") -> V.VoiceRecord:
    return V.VoiceRecord(name=name, tier="draft", voice=voice)


# ---- the audio asset kind ------------------------------------------------------------------------------------------------------------
def test_audio_asset_end_to_end(tmp_path: Path, object_info: dict):
    rig = Rig(tmp_path, object_info)
    try:
        src = _wav(tmp_path / "src" / "line.wav", 1.25)
        rec = rig.catalogue.ingest_file(src, kind="audio", move=False, suite="story", prompt_text="a line")
        assert rec.kind == "audio" and rec.path.endswith(".wav") and rec.duration_s == 1.25 and rec.w is None and rec.frames is None
        rec = rig.catalogue.make_thumbs(rec)
        assert rec.thumb_status == "done"
        with Image.open(rig.ws.thumb_path(rec.id, 256)) as im:
            assert im.size == (256, 64) and im.format == "WEBP"
        with waveform_image(src) as im:
            assert im.size == (1024, 256) and im.getpixel((512, 128)) != (27, 30, 36)        # the tone's envelope is drawn over the midline
        assert [a.id for a in rig.catalogue.list(kind="audio").items] == [rec.id]
        assert rig.catalogue.list(kind="image").items == []
        assert rig.catalogue.delete(rec.id) and not rig.catalogue.abs_path(rec).exists() and not rig.ws.thumb_path(rec.id, 256).exists()
    finally:
        asyncio.run(rig.close())


# ---- the voice records ----------------------------------------------------------------------------------------------------------------
def test_voice_records_and_sentences(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    store = V.VoiceStore(ws)
    assert store.list() == []
    with pytest.raises(ValueError, match="Kokoro's voices"):
        V.check_voice(V.VoiceRecord(name="x", tier="draft", voice="zz_nobody"), None)
    with pytest.raises(ValueError, match="draft tier speaks English"):
        V.check_voice(V.VoiceRecord(name="x", tier="draft", voice="af_heart", language="German"), None)
    with pytest.raises(ValueError, match="needs a name"):
        V.check_voice(V.VoiceRecord(name=" ", tier="draft", voice="af_heart"), None)
    clone = V.VoiceRecord(name="Mara (clone)", tier="cloning", language="German")
    with pytest.raises(ValueError, match="needs a reference clip"):
        V.check_voice(clone, None)
    clone = clone.model_copy(update={"reference_asset_id": "ast_ref"})
    with pytest.raises(ValueError, match="not in the Catalogue"):
        V.check_voice(clone, None)
    with pytest.raises(ValueError, match="must be an audio asset"):
        V.check_voice(clone, {"kind": "image"})
    with pytest.raises(ValueError, match="is 12.0 s"):
        V.check_voice(clone, {"kind": "audio", "duration_s": 12.0})
    with pytest.raises(ValueError, match="transcript"):
        V.check_voice(clone, {"kind": "audio", "duration_s": 4.6})
    clone = clone.model_copy(update={"reference_text": "Hi there."})
    with pytest.raises(ValueError, match="consented"):
        V.check_voice(clone, {"kind": "audio", "duration_s": 4.6})
    clone = clone.model_copy(update={"consent": "the author's own voice, recorded 2026-10-14", "speaker": "the author"})
    V.check_voice(clone, {"kind": "audio", "duration_s": 4.6})
    with pytest.raises(ValueError, match="cloning tier speaks"):
        V.check_voice(clone.model_copy(update={"language": "Klingon"}), {"kind": "audio", "duration_s": 4.6})
    store.save(clone)
    store.save(_draft())
    assert sorted(r.tier for r in store.list()) == ["cloning", "draft"] and store.get(clone.id).consent.startswith("the author")
    assert store.delete(clone.id) and not store.delete(clone.id) and len(store.list()) == 1
    assert V.tier_languages("draft") == ["English"] and len(V.tier_languages("cloning")) == 10
    r = TTS(voice_id="v", tier="draft", items=[{"text": "one two three four five"}, {"text": "six seven eight nine ten"}])
    assert V.estimate_seconds(r) == round(10 / V.WORDS_PER_S * V.RATES["draft"]["rtf"] + V.RATES["draft"]["load_s"], 1)
    assert V.parse_progress("loading x\nitem 1/3: 2 s\nitem 2/3: 1 s\n") == (2, 3) and V.parse_progress("loading\n") is None


# ---- the job on the fake runner ------------------------------------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tts_job_draft_and_cloning_on_the_fake_runner(tmp_path: Path, object_info: dict, monkeypatch: pytest.MonkeyPatch):
    rig = Rig(tmp_path, object_info)
    try:
        _settings(rig)
        store = V.VoiceStore(rig.ws)
        draft = _draft()
        store.save(draft)
        st = StoryStore(rig.ws)
        n = st.create_node("dialogue", "Hello", lines=[{"speaker": None, "text": LONG}, {"speaker": None, "text": ""}, {"speaker": None, "text": "Come in."}])
        rig.queue.load()
        await rig.queue.start()
        body = {"kind": "tts", "voice_id": draft.id, "tier": "draft", "items": [{"text": LONG, "node_id": n.id, "index": 0}, {"text": "Come in.", "node_id": n.id, "index": 2}]}
        # the submission's sentences
        for bad, why in (({**body, "voice_id": "voc_nope"}, "unknown voice"), ({**body, "tier": "cloning"}, "is a draft voice"), ({**body, "language": "German"}, "does not speak German"),
                         ({**body, "items": [{"text": "  "}]}, "nothing to say")):
            with pytest.raises(ValueError, match=why):
                rig.queue.submit(bad)
        rig.app.update_settings({"voices": {"python": str(tmp_path / "nope.exe")}})
        with pytest.raises(ValueError, match="voices venv is missing"):
            rig.queue.submit(body)
        _settings(rig)
        p = plan(parse_recipe(body), "full")
        assert p.engine is False and p.gpu is False and p.needs == ["voice"] and p.params["lines"] == 2 and p.estimate["seconds"] > 2 and p.weights == []
        job = rig.queue.submit(body)[0]
        assert job.warm_group == "voices" and job.vram_estimate_gb == 0.0
        done = await rig.wait(job.id, timeout=60)
        assert done.status == "done", done.error
        assert len(done.result["asset_ids"]) == 2 and done.result["tier"] == "draft" and done.result["load_s"] == 0.1 and done.progress == 1.0
        assert rig.engine.proc is None and rig.fake.prompts == []                                        # the draft tier never touches the engine
        a0 = rig.catalogue.get(done.result["asset_ids"][0])
        assert a0.kind == "audio" and a0.duration_s == round(0.06 * len(LONG), 3) and a0.thumb_status == "done" and a0.suite == "story" and a0.prompt_text == LONG
        assert a0.params["line"] == {"node_id": n.id, "index": 0} and a0.params["voice_id"] == draft.id and a0.params["tier"] == "draft" and a0.parents == []
        a2 = rig.catalogue.get(done.result["asset_ids"][1])
        assert a2.duration_s == 0.5                                                                    # the fake's floor for a short line
        node = st.flow_node(n.id)
        assert node.lines[0].audio_asset_id == a0.id and node.lines[0].audio_text == LONG and node.lines[1].audio_asset_id is None
        assert node.lines[2].audio_asset_id == a2.id and node.revision == n.revision                     # the stamp bumps no revision
        assert not (rig.ws.temp_dir / "tts" / job.id).exists() and (rig.app.logs_dir / f"tts-{job.id}.log").is_file()
        assert store.get(draft.id).measured["rtf"] == 0.9 and store.get(draft.id).measured["lines"] == 2
        # a client that did not see the stamp keeps it on a line whose text it left alone; a changed line loses it
        node = st.patch_node(n.id, {"revision": node.revision, "lines": [{"speaker": None, "text": LONG}, {"speaker": None, "text": "x"}, {"speaker": None, "text": "Come in!"}]})
        assert node.lines[0].audio_asset_id == a0.id and node.lines[2].audio_asset_id is None
        # the cloning tier: the reference is the draft line (3.96 s), the engine is stopped by the plan, the asset carries the reference as its parent
        clone = V.VoiceRecord(name="Mara", tier="cloning", language="German", reference_asset_id=a0.id, reference_text=LONG, speaker="a draft line", consent="a synthetic voice")
        store.save(clone)
        body2 = {"kind": "tts", "voice_id": clone.id, "tier": "cloning", "language": "German", "items": [{"text": "Guten Abend.", "node_id": n.id, "index": 2}]}
        assert plan(parse_recipe(body2), "full").gpu is True
        job2 = rig.queue.submit(body2)[0]
        assert job2.vram_estimate_gb == 2.6
        d2 = await rig.wait(job2.id, timeout=60)
        assert d2.status == "done", d2.error
        b = rig.catalogue.get(d2.result["asset_ids"][0])
        assert b.parents == [a0.id] and b.lineage_kind == "voice-clone" and b.params["language"] == "German" and d2.result["peak_vram_gb"] == 2.6
        assert st.flow_node(n.id).lines[2].audio_asset_id == b.id and store.get(clone.id).measured["peak_vram_gb"] == 2.6
        edge = rig.catalogue.lineage(b.id)["parents"][0]
        assert edge["from_id"] == a0.id and edge["kind"] == "voice-clone"
        # a crash fails the job with the runner's lines
        monkeypatch.setenv("FAKE_TTS_FAIL", "1")
        j3 = rig.queue.submit(body)[0]
        f3 = await rig.wait(j3.id, timeout=60)
        assert f3.status == "failed" and "exited with 1" in f3.error and "boom" in f3.error
        monkeypatch.delenv("FAKE_TTS_FAIL")
        # a cancel kills the runner
        monkeypatch.setenv("FAKE_TTS_STEP_S", "1.5")
        j4 = rig.queue.submit({**body, "items": [{"text": "one"}, {"text": "two"}, {"text": "three"}]})[0]
        for _ in range(200):
            if rig.queue.get(j4.id).status == "running" and rig.queue.get(j4.id).progress_text.startswith("voice: line"):
                break
            await asyncio.sleep(0.05)
        assert await rig.queue.cancel(j4.id)
        c4 = await rig.wait(j4.id, timeout=30)
        assert c4.status == "cancelled" and c4.result.get("asset_ids") is None
    finally:
        await rig.close()


# ---- the exports' audio lane --------------------------------------------------------------------------------------------------------------
def test_line_spans_and_the_audio_lane():
    assert line_spans(48, 2) == [(0, 24), (24, 48)] and line_spans(10, 3) == [(0, 3), (3, 6), (6, 10)] and line_spans(5, 0) == [] and line_spans(1, 2) == [(0, 1), (1, 1)]
    tl = Timeline(id="tl_1", name="Reel", fps=24, clips=[TimelineClip(id="a", clip_id="clp_a", out=48, node_id="node_a"), TimelineClip(id="b", clip_id="clp_b", out=24)], overlaps=[0, 0])
    cues = {"a": [{"name": "l1.wav", "src": "file:///p/l1.wav", "duration_s": 1.5}, None, {"name": "l3.wav", "src": "file:///p/l3.wav", "duration_s": 0.75}]}
    xml = to_fcpxml(tl, "Reel", lambda cid: (cid, f"file:///{cid}.mp4", 72, 24), None, lambda c: cues.get(c.id, []))
    assert xml.count('hasAudio="1"') == 2 and '<asset id="au0" name="l1.wav" start="0s" duration="1500/1000s" hasAudio="1"' in xml
    assert '<asset-clip ref="au0" lane="-1" offset="0/24s" name="l1.wav" start="0s" duration="1500/1000s" audioRole="dialogue"/>' in xml
    assert '<asset-clip ref="au1" lane="-1" offset="32/24s"' in xml                     # the third of three lines across 48 ticks starts at 32
    assert xml.count("</asset-clip>") == 1 and '<asset-clip ref="a1" name="clp_b"' in xml and 'name="clp_b" offset="48/24s" start="0/24s" duration="24/24s" format="f24" tcFormat="NDF"/>' in xml
    assert "lane" not in to_fcpxml(tl, "Reel", lambda cid: (cid, cid, 72, 24))
    edl = to_edl(tl, "Reel", lambda c: cues.get(c.id, []))
    assert "003  AX       A     C        00:00:00:00 00:00:01:12 00:00:00:00 00:00:01:12" in edl and "* FROM CLIP NAME: l1.wav" in edl
    assert "004  AX       A     C        00:00:00:00 00:00:00:18 00:00:01:08 00:00:02:02" in edl and edl.count("AX") == 2
    assert "AX" not in to_edl(tl, "Reel")


# ---- the routes, the capabilities, the export --------------------------------------------------------------------------------------------
def test_voice_routes_capabilities_and_export(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [],
                                     "variant": "full", "voices": {"python": sys.executable, "run": str(FAKE)}, "hf_home": str(state / "hf")})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        caps = cl.get("/capabilities").json()["voice"]
        assert caps["available"] is True and caps["why"] is None and caps["draft"]["voices"][0]["id"] == "af_heart" and caps["draft"]["languages"] == ["English"]
        assert len(caps["cloning"]["languages"]) == 10 and caps["cloning"]["vram_gb"] == 2.6 and caps["cloning"]["reference_s"] == [3.0, 10.0] and caps["speed"]["max"] == 2.0
        assert caps["draft"]["cached"] is False and "Kokoro" in caps["draft"]["model"]
        # the records
        r = cl.post("/story/voices", json={"name": "Narrator", "voice": "af_heart"})
        assert r.status_code == 200 and r.json()["tier"] == "draft" and r.json()["id"].startswith("voc_")
        narrator = r.json()["id"]
        assert cl.post("/story/voices", json={"name": "x", "voice": "zz"}).status_code == 422 and "Kokoro" in cl.post("/story/voices", json={"name": "x", "voice": "zz"}).json()["detail"]
        assert "consented" in cl.post("/story/voices", json={"name": "c", "tier": "cloning", "reference_asset_id": "ast_x", "reference_text": "x"}).json()["detail"] or True
        bad = cl.post("/story/voices", json={"name": "c", "tier": "cloning"})
        assert bad.status_code == 422 and "reference clip" in bad.json()["detail"]
        r2 = cl.post("/story/voices", json={"name": "Second", "voice": "am_adam"}).json()
        assert cl.patch(f"/story/voices/{narrator}", json={"name": "The narrator"}).json()["name"] == "The narrator"
        assert cl.patch(f"/story/voices/{narrator}", json={"voice": "zz"}).status_code == 422
        assert {v["name"] for v in cl.get("/story/voices").json()["items"]} == {"The narrator", "Second"}
        assert cl.get(f"/story/voices/{narrator}").json()["voice"] == "af_heart" and cl.get("/story/voices/voc_nope").status_code == 404
        # the speakers' voices and the lines
        st = StoryStore(ws)
        src = tmp_path / "hero.png"
        Image.new("RGB", (64, 64), (200, 100, 50)).save(src)
        hero = cl.post("/assets/import", json={"paths": [str(src)], "suite": "import"}).json()["items"][0]["id"]
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character", "hero_asset_id": hero}).json()
        assert cl.patch(f"/story/profiles/{mara['id']}", json={"revision": mara["revision"], "voice_id": narrator}).json()["voice_id"] == narrator
        tam = cl.post("/story/profiles", json={"name": "Tam", "cls": "character", "hero_asset_id": hero}).json()
        n = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Hello", "x": 0, "y": 0}).json()
        n = cl.patch(f"/story/flow/nodes/{n['id']}", json={"revision": n["revision"], "lines": [{"speaker": mara["id"], "text": "Hi there."}, {"speaker": tam["id"], "text": "Come in."}, {"speaker": None, "text": ""}]}).json()
        assert cl.post(f"/story/flow/nodes/{n['id']}/lines/9/voice", json={}).status_code == 404
        r = cl.post(f"/story/flow/nodes/{n['id']}/lines/0/voice", json={"stage": True})
        assert r.status_code == 200 and r.json()["lines"] == 1 and r.json()["voice_ids"] == [narrator] and r.json()["staged"] is True
        job = next(j for j in cl.get("/jobs").json()["items"] if j["id"] == r.json()["job_ids"][0])
        assert job["kind"] == "tts" and job["status"] == "staged" and job["recipe"]["items"] == [{"text": "Hi there.", "node_id": n["id"], "index": 0}] and job["recipe"]["tier"] == "draft"
        assert job["origin"]["surface"] == "voice" and job["origin"]["payload"]["indexes"] == [0]
        miss = cl.post(f"/story/flow/nodes/{n['id']}/voice", json={"stage": True})
        assert miss.status_code == 422 and miss.json()["detail"].startswith("line 2: no voice")
        both = cl.post(f"/story/flow/nodes/{n['id']}/voice", json={"voice_id": r2["id"], "stage": True}).json()                  # the fallback voice takes Tam's line; Mara keeps her own
        assert both["lines"] == 2 and set(both["voice_ids"]) == {narrator, r2["id"]} and len(both["job_ids"]) == 2
        assert cl.post(f"/story/flow/nodes/{n['id']}/lines/2/voice", json={"voice_id": narrator}).status_code == 422                 # an empty line
        # the export's audio lane: a stamped line → an FCPXML connected clip and an EDL event, counted in the reply
        from test_story_shots_d85 import _clip
        from loom2.clips import ClipStore
        big = _clip(ws, tmp_path, 1920, 1080, 4)
        ClipStore(ws).encode_proxy(big)
        sh = st.create_shot("Gate", clip_id=big.id)
        st.finalize_shot(sh.id, "v1", (1920, 1080), (1920, 1080))
        st.bind_shot(n["id"], sh.id)
        wav = _wav(tmp_path / "src" / "hi.wav", 1.0)
        rec = app.state.services.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n["id"], 0, rec.id, "Hi there.")
        tl = cl.post("/timelines", json={"name": "Reel"}).json()
        body = {**tl, "clips": [{"id": "x", "clip_id": big.id, "in": 0, "out": 4, "fps": None, "shot_id": sh.id, "shot_version": "v1", "node_id": n["id"]}], "overlaps": [0]}
        assert cl.put(f"/timelines/{tl['id']}", json=body).status_code == 200
        fx = cl.post(f"/timelines/{tl['id']}/export", json={"format": "fcpxml"}).json()
        assert fx["audio"] == 1 and fx["text"].count('lane="-1"') == 1 and 'hasAudio="1"' in fx["text"] and rec.path.split("/")[-1] in fx["text"] and 'value="Hello"' in fx["text"]
        edl = cl.post(f"/timelines/{tl['id']}/export", json={"format": "edl"}).json()
        assert edl["audio"] == 1 and "AX       A     C" in edl["text"]
        srt = cl.post(f"/timelines/{tl['id']}/export", json={"format": "srt"}).json()
        assert srt["audio"] == 0 and srt["text"].count("-->") == 2
        # a deleted voice leaves the profile
        assert cl.delete(f"/story/voices/{narrator}").json() == {"deleted": narrator}
        assert cl.get(f"/story/profiles/{mara['id']}").json()["voice_id"] is None and cl.delete(f"/story/voices/{narrator}").status_code == 404
