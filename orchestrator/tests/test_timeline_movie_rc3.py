"""RC3 (D96, proto01_animate 29): the cut rendered as a movie — a CPU job with `movie: true` on a lane with a 24 fps clip, a 16 fps clip
(conformed: the RIFE step faked so the test never takes the card) and a dissolve, a voiced Dialogue line on the first clip → one MP4 in the
cut's folder at the cut's size (each clip letterboxed), the lane's length, the line's audio where the exports place it and silence after
it; the Catalogue video with lineage to both clips; the engine never started."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import final_assembly  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.pipeline import plan  # noqa: E402
from loom2.recipes import Render  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402


def test_the_estimate_names_the_movie():
    assert "MP4" in plan(Render(timeline_id="tl_x", movie=True)).estimate["source"]
    assert "MP4" not in plan(Render(timeline_id="tl_x")).estimate["source"]


def test_movie_render_makes_an_mp4_with_the_voice_lane(tmp_path: Path, monkeypatch):
    import av
    conformed: list[tuple[str, int]] = []

    def fake_conform(src: Path, dst: Path, n16: int) -> list[Path]:          # RIFE's output shape: (n16 − 1) × 1.5 + 1 frames, here painted green
        conformed.append((src.parent.name, n16))
        dst.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(round((n16 - 1) * 24 / 16) + 1):
            p = dst / f"{i:06d}.png"
            Image.new("RGB", (32, 24), (0, 200, 0)).save(p)
            out.append(p)
        return out
    monkeypatch.setattr(final_assembly, "rife_binary", lambda: Path("rife-ncnn-vulkan.exe"))
    monkeypatch.setattr(final_assembly, "conform_24", fake_conform)
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "M", "size_cap_gb": 10}, headers=H)
        ws = Workspace(tmp_path / "proj")
        cs, svc = ClipStore(ws), app.state.services

        def clip(tag: str, colour: tuple[int, int, int], n: int, fps: int, size: tuple[int, int]):
            frames = []
            for i in range(n):
                p = tmp_path / f"{tag}{i}.png"
                Image.new("RGB", size, colour).save(p)
                frames.append(p)
            rec = cs.create(frames, model_id="wan22-i2v-high-fp8", prompt=tag, seed=1, fps=fps, start_asset_id="ast_x")
            rec = cs.encode_proxy(rec)
            asset = svc.catalogue.ingest_file(ws.path / rec.proxy_path, kind="video", in_place=True, suite="animate", frames=rec.frames, w=rec.w, h=rec.h)
            rec.asset_id = asset.id
            cs.save(rec)
            return rec
        a = clip("a", (200, 0, 0), 24, 24, (64, 48))                      # 1 s at 24 fps, 4:3
        b = clip("b", (0, 0, 200), 17, 16, (32, 24))                      # 1 s at 16 fps → 25 conformed frames
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Hello", with_shot=False)
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Hi there."}]})
        wav = tmp_path / "src" / "hi.wav"
        wav.parent.mkdir(parents=True)
        tone(str(wav), 0.5)                                                  # 24 kHz: the movie resamples it to 48 kHz
        line = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n.id, 0, line.id, "Hi there.")
        tl = cl.post("/timelines", json={"name": "Movie Cut", "fps": 24, "w": 96, "h": 54}, headers=H).json()
        body = {**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24, "node_id": n.id}, {"id": "y", "clip_id": b.id, "in": 0, "out": 16, "fps": 16}],
                "overlaps": [0, 4]}
        r = cl.put(f"/timelines/{tl['id']}", json=body, headers=H)
        assert r.status_code == 200, r.text
        r = cl.post(f"/timelines/{tl['id']}/render", json={"movie": True}, headers=H)
        assert r.status_code == 200, r.text
        job = r.json()["jobs"][0]
        assert job["recipe"]["kind"] == "render" and job["recipe"]["movie"] is True and job["warm_group"] == "cpu"
        cl.post("/queue/unpause", headers=H)
        t0 = time.time()
        while time.time() - t0 < 60:
            j = cl.get(f"/jobs/{job['id']}", headers=H).json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j.get("error") or j.get("log_tail")
        assert cl.get("/engine", headers=H).json().get("running") in (False, None)
        assert conformed == [(b.id, 17)]                                    # the 16 fps clip only, once
        assert j["result"]["path"] == f"timelines/{tl['id']}/movie-cut/movie-cut.mp4" and j["result"]["lines"] == 1 and j["result"]["revision"] == 1
        assert not any(c.model_id == "sequence" for c in cs.list())          # a movie is not a clip
        out = ws.path / j["result"]["path"]
        with av.open(str(out)) as c:
            vs = c.streams.video[0]
            assert (vs.codec_context.width, vs.codec_context.height) == (96, 54) and vs.codec_context.name == "h264"
            frames = [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]
        assert len(frames) == 44                                             # 24 + 24 ticks − the 4-tick dissolve
        f0 = frames[0]
        assert f0[27, 2].max() < 30 and f0[27, 93].max() < 30                # letterboxed: 4:3 into 16:9 leaves bars at the sides
        assert f0[27, 48, 0] > 170 and f0[27, 48, 1] < 40                    # the red clip
        g = frames[34][27, 48]
        assert g[1] > 170 and g[0] < 40 and g[2] < 40, g                     # the 16 fps clip's conformed (green) frames, not its blue masters
        with av.open(str(out)) as c:
            st_a = c.streams.audio[0]
            assert st_a.codec_context.name == "aac" and st_a.rate == 48000
            pcm = np.concatenate([f.to_ndarray().reshape(-1) for f in c.decode(audio=0)])
        rms = lambda s0, s1: float(np.sqrt(np.mean(pcm[int(s0 * 48000):int(s1 * 48000)] ** 2)))   # noqa: E731
        assert rms(0.1, 0.4) > 0.05 and rms(0.8, 1.6) < 0.005                # the line at the clip's start, silence after it
        asset = cl.get(f"/assets/{j['result']['asset_ids'][0]}", headers=H).json()
        assert asset["kind"] == "video" and sorted(asset["parents"]) == sorted([a.asset_id, b.asset_id]) and asset["lineage_kind"] == "render"
        assert asset["params"]["movie"] is True and asset["params"]["lines"] == 1 and (asset["w"], asset["h"], asset["frames"]) == (96, 54, 44)
        assert (ws.path / asset["path"]).is_file() and asset["path"] != j["result"]["path"]   # the Catalogue's copy: deleting the cut's folder keeps it
        # the draft is unchanged: the same route with no body makes a clip
        assert cl.post(f"/timelines/{tl['id']}/render", headers=H).json()["jobs"][0]["recipe"]["movie"] is False
