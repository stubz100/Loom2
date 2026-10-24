"""CE1 (proto01_animate 30 §10, D126): the cut's file is a FilmCraft project — the session (mcp_session.py shared with EffectCraft), the
cut's lane written by commands and read back from the project's JSON (the dissolve on the cut, a 16 fps take as its proxy, the shot's stamps,
the route, the spoken lines on A1 — a line that would overlap the one before it starting where that one ends), and the routes: a new cut is
a project, a change writes it, a stale revision is refused, today's cut is converted on its first change, a converted cut without FilmCraft
is read and not changed, the exports read it, a delete takes the project along. On tests/fake_filmcraft.py (the real binary on the rig)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.cuts import CUT_FILE, Cuts, lane, lines, read  # noqa: E402
from loom2.filmcraft import TICK, FilmCraft, FilmCraftError, export_script  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import Timeline, TimelineClip, starts  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def _app(tmp_path: Path, cli: Path | str = FAKE) -> AppState:
    app = AppState(tmp_path / "state")
    app.update_settings({"filmcraft": {"cli": str(cli), "timeout_s": 20.0}})
    return app


def test_the_session_on_the_fake(tmp_path: Path):
    fc = FilmCraft(_app(tmp_path))
    assert fc.argv()[-1] == "mcp" and "--data-dir" in fc.argv() and fc.available()
    seq = fc.new(tmp_path / "c.fcproj", "Cut", 64, 36, 24)
    assert (tmp_path / "c.fcproj").is_file() and fc.state()["project"] == str(tmp_path / "c.fcproj")
    doc = read(tmp_path / "c.fcproj")
    assert doc["project"]["items"][str(seq)]["kind"]["Sequence"]["settings"]["width"] == 64
    s = fc.sequence()
    assert [len(s["video"]), len(s["audio"])] == [2, 3]                                       # D126 #3: V1 V2, A1 A2 A3
    assert fc.frame(0.5, 32)[:4] == b"\x89PNG"
    with pytest.raises(FilmCraftError, match="unknown command"):
        fc.command("no.such", {})
    with pytest.raises(FilmCraftError, match="command_batch"):
        fc.batch([{"id": "file.save", "params": {}}, {"id": "no.such"}])
    fc.proc.kill()                                                                           # it dies: the next use starts it again, the project reopened
    fc.proc.wait()
    assert fc.sequence()["name"] == "Cut" and fc.restarts == 1
    fc.close(tmp_path / "c.fcproj")
    assert fc.state()["project"] is None
    fc.stop()
    assert not FilmCraft(_app(tmp_path / "x", tmp_path / "missing.exe")).available()
    script = export_script(tmp_path / "m.mp4", "h264", 24)
    assert [json.loads(x)["id"] for x in script.splitlines()] == ["prefs.set", "file.exportMedia"] and '"playback.hardwareDecoding": "off"' in script


def _clips(ws: Workspace, tmp_path: Path) -> tuple:
    cs = ClipStore(ws)

    def clip(tag: str, colour: tuple[int, int, int], n: int, fps: int):
        frames = []
        for i in range(n):
            p = tmp_path / f"{tag}{i}.png"
            Image.new("RGB", (32, 24), colour).save(p)
            frames.append(p)
        rec = cs.create(frames, model_id="wan22-i2v-high-fp8", prompt=tag, seed=1, fps=fps, start_asset_id="ast_x")
        return cs.encode_proxy(rec)
    return clip("a", (200, 0, 0), 24, 24), clip("b", (0, 0, 200), 17, 16)


def test_a_cut_written_and_read_back(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    a, b = _clips(ws, tmp_path)
    wav1, wav2 = tmp_path / "l1.wav", tmp_path / "l2.wav"
    tone(str(wav1), 0.75)
    tone(str(wav2), 0.5)
    cues = {a.id: [{"path": str(wav1), "duration_s": 0.75, "asset": "ast_l1", "node": "node_1", "line": 0},
                  {"path": str(wav2), "duration_s": 0.5, "asset": "ast_l2", "node": "node_1", "line": 1}]}
    fc = FilmCraft(_app(tmp_path))
    cuts = Cuts(ws, fc, lambda c: cues.get(c.clip_id, []))             # as story_lookup: by what the clip is, not its lane id
    tl = Timeline(id="tl_ce1", name="Cut", fps=24, w=64, h=36, route={"node_choice": "opt_b"},
                  clips=[TimelineClip(id="x", clip_id=a.id, **{"in": 2}, out=24, shot_id="sht_1", shot_version="v2", node_id="node_1"),
                         TimelineClip(id="y", clip_id=b.id, **{"in": 0}, out=17, fps=16)], overlaps=[0, 6])
    cuts.write(tl, {a.id: a, b.id: b})
    doc = read(cuts.path(tl.id))
    clips, overlaps, route = lane(doc, 24)
    assert [(c.clip_id, c.in_, c.out, c.fps) for c in clips] == [(a.id, 2, 24, None), (b.id, 0, 17, 16)]
    assert overlaps == [0, 6] and route == {"node_choice": "opt_b"} and starts(tl) == [0, 16]
    assert (clips[0].shot_id, clips[0].shot_version, clips[0].node_id) == ("sht_1", "v2", "node_1") and clips[1].shot_id is None
    v1 = doc["project"]["items"]
    media = {it["metadata"]["loom2.clip"]: it for it in v1.values() if "loom2.clip" in it["metadata"]}
    assert media[a.id]["metadata"]["loom2.media"] == "master" and media[a.id]["kind"]["Media"]["info"]["kind"] == "Image Sequence"   # the PNG master at 24
    assert media[b.id]["metadata"]["loom2.media"] == "proxy" and media[b.id]["metadata"]["loom2.fps"] == "16"                        # 16 fps: its proxy until the movie conforms it
    seq = next(it for it in v1.values() if "Sequence" in it["kind"])["kind"]["Sequence"]
    cut_tick = 16 + 3                                                                          # the dissolve 16–22, the cut in its middle
    assert [ti["start"] for ti in seq["video_tracks"][0]["items"]] == [0, cut_tick * TICK // 24]
    tr = seq["video_tracks"][0]["transitions"][0]
    assert tr["start"] == 16 * TICK // 24 and tr["duration"] == 6 * TICK // 24
    ls = lines(doc)                                                                             # 22 ticks laid in two: 0 and 11 — the first (18 ticks) pushes the second to 18
    assert [(round(x["start"] * 24 / TICK), x["line"], x["asset"]) for x in ls] == [(0, 0, "ast_l1"), (18, 1, "ast_l2")]
    # written again from what was read: the same project (stable), the media and lines imported once
    cuts.write(tl.model_copy(update={"clips": clips, "overlaps": overlaps}), {a.id: a, b.id: b})
    doc2 = read(cuts.path(tl.id))
    assert [(c.in_, c.out) for c in lane(doc2, 24)[0]] == [(2, 24), (0, 17)] and lane(doc2, 24)[1] == overlaps
    assert sum(1 for it in doc2["project"]["items"].values() if "Media" in it["kind"]) == 4 and len(lines(doc2)) == 2
    fc.stop()


def _client(tmp_path: Path, cli: Path | str = FAKE):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(cli), "timeout_s": 20.0}})
    return create_app(state)


def test_the_routes_on_a_filmcraft_cut(tmp_path: Path):
    app = _client(tmp_path, tmp_path / "unbuilt.exe")                                           # first without FilmCraft: today's cut
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b = _clips(ws, tmp_path)
        legacy = cl.post("/timelines", json={"name": "Old cut", "fps": 24, "w": 64, "h": 36}).json()
        assert legacy["file"] is None
        body = {**legacy, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24}], "overlaps": [0]}
        legacy = cl.put(f"/timelines/{legacy['id']}", json=body).json()
        assert legacy["file"] is None and legacy["revision"] == 1
    app = _client(tmp_path)                                                                    # FilmCraft built (the fake)
    with TestClient(app) as cl:
        cl.post("/project/open", json={"path": str(tmp_path / "proj")})
        tl = cl.post("/timelines", json={"name": "New cut", "fps": 24, "w": 64, "h": 36}).json()
        assert tl["file"] == CUT_FILE and (ws.timelines_dir / tl["id"] / CUT_FILE).is_file() and tl["clips"] == []
        body = {**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24}, {"id": "y", "clip_id": b.id, "in": 0, "out": 17, "fps": 16}], "overlaps": [0, 4]}
        r = cl.put(f"/timelines/{tl['id']}", json=body)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["revision"] == 1 and [(c["clip_id"], c["in"], c["out"]) for c in got["clips"]] == [(a.id, 0, 24), (b.id, 0, 17)] and got["overlaps"] == [0, 4]
        rec = json.loads((ws.timelines_dir / f"{tl['id']}.json").read_text(encoding="utf-8"))
        assert rec["clips"] == [] and rec["file"] == CUT_FILE                                  # the record keeps no clips: the project is the cut
        assert cl.get(f"/timelines/{tl['id']}").json()["clips"] == got["clips"]
        assert cl.put(f"/timelines/{tl['id']}", json={**body, "revision": 0}).status_code == 409
        # today's cut is converted on its first change
        conv = cl.put(f"/timelines/{legacy['id']}", json={**legacy, "overlaps": [0], "clips": [{"id": "x", "clip_id": a.id, "in": 4, "out": 24}]}).json()
        assert conv["file"] == CUT_FILE and conv["clips"][0]["in"] == 4 and conv["revision"] == 2
        # the same take on the lane as a shot and as a plain clip: two items of one file, each with its own links (an e2e found the last write winning)
        twice = cl.put(f"/timelines/{tl['id']}", json={**got, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24, "shot_id": "sht_9", "shot_version": "v1", "node_id": "node_9"},
                                                                       {"id": "y", "clip_id": a.id, "in": 0, "out": 12}], "overlaps": [0, 0]}).json()
        assert [(c["shot_id"], c["node_id"]) for c in twice["clips"]] == [("sht_9", "node_9"), (None, None)]
        doc = read(ws.timelines_dir / tl["id"] / CUT_FILE)
        takes = [it["metadata"] for it in doc["project"]["items"].values() if "loom2.clip" in it["metadata"]]
        assert sorted((m["loom2.clip"], m["loom2.shot"]) for m in takes) == sorted([(a.id, "sht_9"), (a.id, "")])   # b's item went with its use
        got = twice
        # the exports read the project
        edl = cl.post(f"/timelines/{tl['id']}/export", json={"format": "edl"}).json()
        assert edl["text"].count("* FROM CLIP NAME") == 2 and " D    " not in edl["text"]
        assert cl.delete(f"/timelines/{conv['id']}").json() == {"deleted": conv["id"]} and not (ws.timelines_dir / conv["id"]).exists()
    app = _client(tmp_path, tmp_path / "unbuilt.exe")                                           # FilmCraft gone: the cut is read, not changed
    with TestClient(app) as cl:
        cl.post("/project/open", json={"path": str(tmp_path / "proj")})
        assert cl.get(f"/timelines/{tl['id']}").json()["clips"] == got["clips"]
        r = cl.put(f"/timelines/{tl['id']}", json={**got, "overlaps": [0, 2]})
        assert r.status_code == 422 and "FilmCraft is not built" in r.json()["detail"]


def test_a_new_cut_carries_its_voiced_lines_on_a1(tmp_path: Path):
    """The route's story lookup gives the lines: a Dialogue node's voiced line lands on A1 with its links."""
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, _ = _clips(ws, tmp_path)
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Hello", with_shot=False)
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Hi there."}]})
        wav = tmp_path / "hi.wav"
        tone(str(wav), 0.5)
        line = app.state.services.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n.id, 0, line.id, "Hi there.")
        tl = cl.post("/timelines", json={"name": "Lines", "fps": 24, "w": 64, "h": 36}).json()
        t0 = time.time()
        r = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24, "node_id": n.id}], "overlaps": [0]})
        assert r.status_code == 200, r.text
        assert time.time() - t0 < 20
        ls = lines(read(ws.timelines_dir / tl["id"] / CUT_FILE))
        assert [(x["start"], x["node"], x["line"], x["asset"]) for x in ls] == [(0, n.id, 0, line.id)]


def test_the_movie_is_filmcrafts_export(tmp_path: Path, monkeypatch):
    """D126 #5: a FilmCraft cut's movie — the 16 fps take conformed (RIFE faked: the test never takes the card) and swapped in for its
    proxy with the lane unchanged, the export run as a process of its own, the line's audio where A1 holds it, the Catalogue copy."""
    import av
    import numpy as np
    from loom2 import final_assembly

    def fake_conform(src: Path, dst: Path, n16: int) -> list[Path]:                       # as rife-ncnn-vulkan writes them: numbered from 1
        dst.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(1, round((n16 - 1) * 24 / 16) + 2):
            p = dst / f"{i:06d}.png"
            Image.new("RGB", (32, 24), (0, 200, 0)).save(p)
            out.append(p)
        return out
    monkeypatch.setattr(final_assembly, "rife_binary", lambda: Path("rife-ncnn-vulkan.exe"))
    monkeypatch.setattr(final_assembly, "conform_24", fake_conform)
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b = _clips(ws, tmp_path)
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Hello", with_shot=False)
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Hi there."}]})
        wav = tmp_path / "hi.wav"
        tone(str(wav), 0.5)
        line = app.state.services.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n.id, 0, line.id, "Hi there.")
        tl = cl.post("/timelines", json={"name": "Movie Cut", "fps": 24, "w": 64, "h": 36}).json()
        body = {**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24, "node_id": n.id}, {"id": "y", "clip_id": b.id, "in": 0, "out": 17, "fps": 16}],
                "overlaps": [0, 4]}
        lane_before = cl.put(f"/timelines/{tl['id']}", json=body).json()["clips"]
        r = cl.post(f"/timelines/{tl['id']}/render", json={"movie": True})
        assert r.status_code == 200, r.text
        job = r.json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 60:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j.get("error") or j.get("log_tail")
        assert j["result"]["engine"] == "filmcraft" and j["result"]["path"] == f"timelines/{tl['id']}/movie-cut/movie-cut.mp4" and j["result"]["lines"] == 1
        assert any("1 take(s) conformed" in x for x in j["log_tail"])
        doc = read(ws.timelines_dir / tl["id"] / CUT_FILE)
        kinds = {it["metadata"].get("loom2.clip"): it["metadata"].get("loom2.media") for it in doc["project"]["items"].values() if "loom2.clip" in it["metadata"]}
        assert kinds == {a.id: "master", b.id: "conform24"}                                       # the proxy item is gone, the conformed one in its place
        assert [(c["clip_id"], c["in"], c["out"]) for c in cl.get(f"/timelines/{tl['id']}").json()["clips"]] == [(c["clip_id"], c["in"], c["out"]) for c in lane_before]
        out = ws.path / j["result"]["path"]
        with av.open(str(out)) as c:
            assert (c.streams.video[0].codec_context.width, c.streams.video[0].codec_context.height) == (64, 36)
            frames = sum(1 for _ in c.decode(video=0))
        with av.open(str(out)) as c:
            pcm = np.concatenate([f.to_ndarray().reshape(-1) for f in c.decode(audio=0)])
        from loom2.timelines import duration
        assert frames == duration(Timeline.model_validate(cl.get(f"/timelines/{tl['id']}").json())) == 24 + 26 - 4   # the lane's length (17 frames at 16 fps: 26 ticks)
        rms = lambda s0, s1: float(np.sqrt(np.mean(pcm[int(s0 * 48000):int(s1 * 48000)] ** 2)))   # noqa: E731
        assert rms(0.1, 0.4) > 0.05 and rms(0.8, 1.6) < 0.005
        asset = cl.get(f"/assets/{j['result']['asset_ids'][0]}").json()
        assert asset["params"]["engine"] == "filmcraft" and sorted(asset["parents"]) == sorted(x for x in (a.asset_id, b.asset_id) if x) and asset["lineage_kind"] == "render"
