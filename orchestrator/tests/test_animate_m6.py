"""M6 Animate, backend slice (11 §10, 06 §7): the I2V compiler against the pinned engine's object_info (Wan 2.2 presets,
FLF, LTX-2.3 with end frame and beats), parameter snapping, and the queue end to end on the fake engine — frames
become a clip (PNG master + h264 proxy + clip.json), a Catalogue video asset with a poster thumbnail and lineage, and
`/clips/*` serves the proxy (Range), frames and harvests frames with `frame-extract` lineage."""
from __future__ import annotations

import json
from pathlib import Path

import av
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2.api import create_app
from loom2.clips import ClipStore
from loom2.config import AppState
from loom2.engine import graphs
from loom2.recipes import I2V, Beat
from loom2.roster import ROSTER_BY_ID, Roster
from loom2.workspace import Workspace

from test_lifecycle import Rig

START, END = "alley-rain_s20261004.png", "captain-cabin_s20261004.png"      # uploaded names the fixture's LoadImage enum lists


def _video_weights(root: Path) -> None:
    for e in ROSTER_BY_ID.values():
        if e.family in ("wan22", "ltx23") and not e.retired:
            p = root / e.folder / e.name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * 16)


def _roster(tmp: Path) -> Roster:
    root = tmp / "models"
    _video_weights(root)
    (root / "roster.index.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    return Roster(root).scan()


def _nodes(c: graphs.Compiled, cls: str) -> list[dict]:
    return [n for n in c.graph.values() if n["class_type"] == cls]


# ---- compiler ----------------------------------------------------------------------------------------------
def test_i2v_params_snap_to_each_models_rule():
    wan = graphs.i2v_params(I2V(start_asset="a", width=833, height=481, frames=80))
    assert (wan["width"], wan["height"], wan["frames"]) == (832, 480, 81) and wan["family"] == "wan22"
    ltx = graphs.i2v_params(I2V(start_asset="a", model_id="ltx23-distilled-fp8", width=1010, height=570, frames=120, fps=24))
    assert (ltx["width"], ltx["height"], ltx["frames"]) == (1024, 576, 121) and ltx["steps"] == 8
    motion = graphs.i2v_params(I2V(start_asset="a", preset="motion"))
    assert (motion["steps"], motion["split"], motion["cfg_high"], motion["cfg_low"], motion["lora_high"], motion["lora_low"]) == (8, 4, 3.5, 1.0, False, True)
    with pytest.raises(graphs.CompileError):
        graphs.i2v_params(I2V(start_asset="a", model_id="klein-4b"))


def test_wan_graphs_pass_the_contract_for_every_preset_and_flf(tmp_path: Path, object_info):
    roster = _roster(tmp_path)
    for preset in ("draft", "motion", "quality"):
        r = I2V(start_asset="a", preset=preset, prompt_text="she turns")
        c = graphs.compile_recipe(r, roster, object_info, 7, "loom2/j1", inputs={"start": START})
        assert not c.problems, c.problems
        assert _nodes(c, "WanImageToVideo") and not _nodes(c, "WanFirstLastFrameToVideo")
        ks = _nodes(c, "KSamplerAdvanced")
        assert len(ks) == 2 and ks[0]["inputs"]["noise_seed"] == 7 and ks[0]["inputs"]["steps"] == graphs.WAN_PRESETS[preset].steps
        assert len(_nodes(c, "LoraLoaderModelOnly")) == {"draft": 2, "motion": 1, "quality": 0}[preset]
        save = _nodes(c, "SaveImage")
        assert len(save) == 1 and save[0]["inputs"]["filename_prefix"] == "loom2/j1" and not _nodes(c, "SaveVideo")
        assert c.summary["frames"] == 81 and c.summary["fps"] == 16 and c.serialized_prompt == "she turns"
    flf = graphs.compile_recipe(I2V(start_asset="a", end_asset="b"), roster, object_info, 1, "loom2/j2", inputs={"start": START, "end": END})
    assert not flf.problems and _nodes(flf, "WanFirstLastFrameToVideo")[0]["inputs"]["end_image"] and flf.summary["flf"] is True
    assert len(_nodes(flf, "LoadImage")) == 2


def test_ltx_graph_with_end_frame_and_beats_passes_the_contract(tmp_path: Path, object_info):
    roster = _roster(tmp_path)
    r = I2V(start_asset="a", end_asset="b", model_id="ltx23-distilled-fp8", frames=121, fps=24, width=1024, height=576,
            beats=[Beat(frame=40, asset_id="k1", strength=0.6), Beat(frame=500, asset_id="k2")])
    c = graphs.compile_recipe(r, roster, object_info, 3, "loom2/j3", inputs={"start": START, "end": END, "beats": {"k1": "01-remove-crates.png", "k2": "02-change-cloak.png"}})
    assert not c.problems, c.problems
    guides = _nodes(c, "LTXVAddGuide")
    assert [(g["inputs"]["frame_idx"], g["inputs"]["strength"]) for g in guides] == [(-1, 1.0), (40, 0.6), (120, 1.0)]      # the late beat is clamped
    assert len(_nodes(c, "VAELoader")) == 2 and _nodes(c, "LTXVEmptyLatentAudio")[0]["inputs"]["audio_vae"]
    assert _nodes(c, "LTXVScheduler")[0]["inputs"]["steps"] == 8 and _nodes(c, "RandomNoise")[0]["inputs"]["noise_seed"] == 3
    assert _nodes(c, "SaveImage")[0]["inputs"]["filename_prefix"] == "loom2/j3"
    with pytest.raises(graphs.CompileError):
        graphs.compile_recipe(r, roster, object_info, 3, "loom2/j3", inputs={"start": START, "end": END, "beats": {}})
    est = graphs.estimate_i2v_seconds(r)
    assert 100 < est["seconds"] < 400 and "spikes" in est["source"]


# ---- queue end to end ----------------------------------------------------------------------------------------
async def test_i2v_job_makes_a_clip_with_master_proxy_asset_and_lineage(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info)
    _video_weights(tmp_path / "models"); rig.roster.scan()
    try:
        rig.queue.load()
        await rig.queue.start()
        png = tmp_path / "start.png"
        Image.new("RGB", (320, 200), (10, 200, 30)).save(png)
        start = rig.catalogue.ingest_file(png, kind="image", move=False, suite="import")
        job = rig.queue.submit({"kind": "i2v", "start_asset": start.id, "prompt_text": "she turns", "frames": 9, "width": 256, "height": 256, "fps": 16, "seeds": [5]})[0]
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        store = ClipStore(rig.ws)
        rec = store.get(j.result["clip_id"])
        assert rec and (rec.frames, rec.w, rec.h, rec.fps, rec.seed) == (9, 256, 256, 16, 5)
        assert len(list((rig.ws.clips_dir / rec.id / "master").glob("*.png"))) == 9
        proxy = rig.ws.path / rec.proxy_path
        with av.open(str(proxy)) as c:
            s = c.streams.video[0]
            assert s.codec_context.name == "h264" and s.average_rate == 16
            assert sum(1 for _ in c.decode(s)) == 9
        a = rig.catalogue.get(j.result["asset_ids"][0])
        assert a and a.kind == "video" and a.frames == 9 and a.thumb_status == "done" and a.params["clip_id"] == rec.id and a.parents == [start.id]
        assert rig.catalogue.abs_path(a) == proxy and rec.asset_id == a.id
        assert any(e["type"] == "clip.ready" and e["data"]["clip_id"] == rec.id for e in rig.hub.recent)
        assert not list((rig.state / "engine_out" / "loom2").glob("*")), "engine frames were not moved into the clip"
        # a Catalogue rebuild re-indexes the clip proxy from clips/<id>/proxy.json and can re-make its poster thumbnail
        n = rig.catalogue.rebuild()
        again = rig.catalogue.get(a.id)
        assert n >= 2 and again and again.kind == "video" and again.params["clip_id"] == rec.id
        for f in (rig.ws.thumbs_dir / a.id).glob("*.webp"):
            f.unlink()
        assert rig.catalogue.make_thumbs(again).thumb_status == "done"
        # LTX with an end frame and a beat: three uploads, the beat resolves to its uploaded name
        job2 = rig.queue.submit({"kind": "i2v", "model_id": "ltx23-distilled-fp8", "start_asset": start.id, "end_asset": start.id, "frames": 9, "fps": 24,
                                 "width": 256, "height": 256, "beats": [{"frame": 4, "asset_id": start.id, "strength": 0.5}], "seeds": [2]})[0]
        j2 = await rig.wait(job2.id)
        assert j2.status == "done", j2.error
        assert j2.result["compiled"]["beats"] == 1 and j2.result["compiled"]["flf"] is True
        rec2 = store.get(j2.result["clip_id"])
        assert rec2 and rec2.frames == 9 and rec2.fps == 24 and rec2.end_asset_id == start.id
    finally:
        await rig.close()


def test_i2v_submission_validates_model_and_beats(tmp_path: Path, object_info):
    rig = Rig(tmp_path, object_info)
    try:
        with pytest.raises(ValueError):
            rig.queue.submit({"kind": "i2v", "start_asset": "x", "model_id": "klein-4b"})
        with pytest.raises(ValueError):
            rig.queue.submit({"kind": "i2v", "start_asset": "x", "beats": [{"frame": 1, "asset_id": "y"}]})      # Wan has no keyframe guides
    finally:
        rig.fake.stop()


# ---- API: proxy, frames, harvest ----------------------------------------------------------------------------
def test_clip_api_serves_proxy_frames_and_extracts_with_lineage(tmp_path: Path):
    state = tmp_path / "state"
    app_state = AppState(state)
    app_state.update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    client = TestClient(app)
    token = app.state.services.app.token
    H = {"X-Loom-Token": token}
    with client:
        client.post("/project", json={"path": str(tmp_path / "proj"), "name": "Clips", "size_cap_gb": 10}, headers=H)
        caps = client.get("/capabilities").json()
        assert "i2v" in caps["recipes"] and caps["i2v"]["models"]["wan22-i2v-high-fp8"]["frame_step"] == 4 and caps["i2v"]["models"]["ltx23-distilled-fp8"]["beats"] is True
        ws = Workspace(tmp_path / "proj")
        store = ClipStore(ws)
        frames = []
        for i in range(3):
            p = tmp_path / f"f{i}.png"
            Image.new("RGB", (64, 48), (i * 80, 20, 200)).save(p)
            frames.append(p)
        rec = store.create(frames, model_id="wan22-i2v-high-fp8", prompt="test", seed=1, fps=16, start_asset_id="ast_missing")
        rec = store.encode_proxy(rec)
        assert client.get("/clips").json()["items"][0]["id"] == rec.id
        assert client.get(f"/clips/{rec.id}").json()["frames"] == 3
        r = client.get(f"/clips/{rec.id}/frames/1.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert client.get(f"/clips/{rec.id}/frames/3.png").status_code == 404
        full = client.get(f"/clips/{rec.id}/proxy.mp4")
        assert full.status_code == 200 and full.headers["content-type"] == "video/mp4" and full.headers.get("accept-ranges") == "bytes"
        part = client.get(f"/clips/{rec.id}/proxy.mp4", headers={"Range": "bytes=0-99"})
        assert part.status_code == 206 and len(part.content) == 100
        r = client.post(f"/clips/{rec.id}/extract", json={"frames": [0, 2, 99]}, headers=H)
        items = r.json()["items"]
        assert len(items) == 2 and all(a["suite"] == "animate" and a["thumb_status"] == "done" for a in items)
        assert [a["params"]["frame_index"] for a in items] == [0, 2]
        assert r.json()["clip"]["extracted_asset_ids"] == [a["id"] for a in items]
        assert client.get(f"/assets/{items[1]['id']}/file").status_code == 200
        assert client.post(f"/clips/{rec.id}/extract", json={"frames": [50]}, headers=H).status_code == 422
        assert client.get("/clips/clp_nope").status_code == 404
