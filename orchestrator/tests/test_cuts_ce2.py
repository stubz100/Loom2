"""CE2a (proto01_animate 30 §12, D126): the editor on a FilmCraft cut, on tests/fake_filmcraft.py (the real binary on the rig) — the cut's
every track read from its project, the editor's edits as whitelisted FilmCraft commands under the cut's revision (a refused command, a
stale base), a dissolve removed with the clip kept in place, *Update* in place, a Catalogue picture and sound placed, the lane staying the
takes in order when V1 holds more, the viewer's frame, the exports from the project and the draft through FilmCraft."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}})
    return create_app(state)


def _clip(ws: Workspace, tmp_path: Path, tag: str, colour: tuple[int, int, int], n: int = 24, fps: int = 24):
    cs = ClipStore(ws)
    frames = []
    for i in range(n):
        p = tmp_path / f"{tag}{i}.png"
        Image.new("RGB", (32, 24), colour).save(p)
        frames.append(p)
    return cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt=tag, seed=1, fps=fps, start_asset_id="ast_x"))


def test_the_editor_on_a_filmcraft_cut(tmp_path: Path):
    app = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "E", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b, c = _clip(ws, tmp_path, "a", (200, 0, 0)), _clip(ws, tmp_path, "b", (0, 0, 200)), _clip(ws, tmp_path, "c", (0, 200, 0))
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Gate", with_shot=False)
        st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in."}]})
        tl = cl.post("/timelines", json={"name": "Edit me", "fps": 24, "w": 64, "h": 36}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 24, "node_id": n.id},
                                                                   {"id": "y", "clip_id": b.id, "in": 0, "out": 24}], "overlaps": [0, 6]}).json()
        base = f"/timelines/{tl['id']}"
        tr = cl.get(f"{base}/tracks").json()
        assert [t["name"] for t in tr["video"]] == ["Video 1", "Video 2"] and len(tr["audio"]) == 3 and tr["fps"] == 24
        v1 = tr["video"][0]
        assert [(i["kind"], i["clip_id"], i["start"], i["duration"]) for i in v1["items"]] == [("take", a.id, 0, 21), ("take", b.id, 21, 21)]
        assert [(x["effect"], x["start"], x["duration"], x["from"], x["to"]) for x in v1["transitions"]] == [("cross_dissolve", 18, 6, v1["items"][0]["id"], v1["items"][1]["id"])]
        # an edit: the track's name, under the cut's revision; a stale base and a command the editor may not run are refused
        r = cl.post(f"{base}/edit", json={"revision": tl["revision"], "steps": [{"id": "timeline.setTrack", "params": {"track": "V1", "name": "Shots"}}]})
        assert r.status_code == 200, r.text
        rev = r.json()["timeline"]["revision"]
        assert rev == tl["revision"] + 1 and r.json()["tracks"]["video"][0]["name"] == "Shots"
        assert cl.post(f"{base}/edit", json={"revision": tl["revision"], "steps": [{"id": "timeline.setTrack", "params": {"track": "V1", "name": "x"}}]}).status_code == 409
        bad = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "file.saveAs", "params": {"path": str(tmp_path / "x.fcproj")}}]})
        assert bad.status_code == 422 and "not an editor command" in bad.json()["detail"]
        # the dissolve removed: the clip it led into stays where it was
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "loom2.removeTransition", "params": {"transition": v1["transitions"][0]["id"]}}]}).json()
        rev, v1 = r["timeline"]["revision"], r["tracks"]["video"][0]
        assert v1["transitions"] == [] and [(i["clip_id"], i["start"], i["duration"]) for i in v1["items"]] == [(a.id, 0, 21), (b.id, 21, 21)]
        # razor, a piece to V2, speed — and undo
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.razor", "params": {"time": 10 * 254016000000 // 24, "track": "V1"}}]}).json()
        rev, v1 = r["timeline"]["revision"], r["tracks"]["video"][0]
        assert [(i["start"], i["duration"]) for i in v1["items"]] == [(0, 10), (10, 11), (21, 21)]
        piece = v1["items"][1]["id"]
        r = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.move", "params": {"moves": [{"clip": piece, "track": "V2", "time": 30 * 254016000000 // 24}], "insert": False}},
                                                                    {"id": "clip.speedDuration", "params": {"clips": [v1["items"][0]["id"]], "speed": 50}}]}).json()
        rev, trk = r["timeline"]["revision"], r["tracks"]
        assert [i["id"] for i in trk["video"][1]["items"]] == [piece] and trk["video"][1]["items"][0]["start"] == 30 and trk["video"][0]["items"][0]["speed"] == 0.5
        lane = cl.get(base).json()
        assert [c["clip_id"] for c in lane["clips"]] == [a.id, b.id] and lane["clips"][0]["node_id"] == n.id   # the lane: V1's takes in order, a gap closed up
        assert trk["undo"] >= 4 and trk["redo"] == 0
        r = cl.post(f"{base}/undo", json={"revision": rev}).json()                                 # the cut's undo: the whole last change (move and speed)
        rev = r["timeline"]["revision"]
        assert r["tracks"]["video"][0]["items"][0]["speed"] == 1.0 and r["tracks"]["video"][1]["items"] == [] and r["tracks"]["redo"] == 1
        r = cl.post(f"{base}/redo", json={"revision": rev}).json()
        assert r["tracks"]["video"][0]["items"][0]["speed"] == 0.5 and r["tracks"]["redo"] == 0
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        rev = r["timeline"]["revision"]
        refused = cl.post(f"{base}/edit", json={"revision": rev, "steps": [{"id": "timeline.setTrack", "params": {"track": "V1", "name": "y"}},
                                                                          {"id": "timeline.slip", "params": {"clip": 999999, "deltaFrames": 2}}]})
        assert refused.status_code == 422
        after = cl.get(f"{base}/tracks").json()
        assert after["video"][0]["name"] == "Shots" and after["undo"] == r["tracks"]["undo"]   # refused part-way: rolled back, no step left behind
        # Update in place: the first take swapped for another, its start and length kept
        first = r["tracks"]["video"][0]["items"][0]
        r = cl.post(f"{base}/replace", json={"revision": rev, "clip": first["id"], "clip_id": c.id, "shot_id": "sht_c", "shot_version": "v2", "node_id": n.id}).json()
        rev = r["timeline"]["revision"]
        now = r["tracks"]["video"][0]["items"][0]
        assert (now["clip_id"], now["shot_id"], now["start"], now["duration"]) == (c.id, "sht_c", first["start"], first["duration"])
        # a Catalogue picture on V2 and a sound on A2
        pic = tmp_path / "title.png"
        Image.new("RGB", (64, 36), (255, 255, 255)).save(pic)
        pa = svc.catalogue.ingest_file(pic, kind="image", move=False, suite="import")
        wav = tmp_path / "music.wav"
        tone(str(wav), 1.0, hz=220)
        sa = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="import")
        r = cl.post(f"{base}/place", json={"revision": rev, "asset_id": pa.id, "track": "V2", "frame": 0})
        assert r.status_code == 200, r.text
        r = cl.post(f"{base}/place", json={"revision": r.json()["timeline"]["revision"], "asset_id": sa.id, "track": "A2", "frame": 4}).json()
        rev = r["timeline"]["revision"]
        v2, a2 = r["tracks"]["video"][1]["items"], r["tracks"]["audio"][1]["items"]
        assert v2[0]["asset_id"] == pa.id and [i["asset_id"] for i in a2] == [sa.id] and a2[0]["start"] == 4
        assert cl.post(f"{base}/place", json={"revision": rev, "clip_id": "clp_nope", "track": "V2", "frame": 0}).status_code == 422
        # the viewer's frame, the exports from the project, the draft through FilmCraft
        fr = cl.get(f"{base}/frame", params={"t": 0.5, "side": 32})
        assert fr.status_code == 200 and fr.content[:4] == b"\x89PNG" and fr.headers["content-type"] == "image/png"
        edl = cl.post(f"{base}/export", json={"format": "edl"}).json()
        assert edl["text"].startswith("TITLE: Edit me") and edl["path"].endswith(".edl")
        srt = cl.post(f"{base}/export", json={"format": "srt"}).json()
        assert srt["text"].count("-->") == 1 and "Come in." in srt["text"] and "00:00:00,000 -->" in srt["text"]
        res = cl.post(f"{base}/export", json={"format": "resolve"}).json()
        assert sorted(res["text"].split("\n")) == sorted(["edit-me.fcpxml", "edit-me.edl", "edit-me.srt", "markers.txt"])
        assert (ws.timelines_dir / tl["id"] / "edit-me" / "markers.txt").read_text(encoding="utf-8").startswith("00:00:00:00\tGate")
        job = cl.post(f"{base}/render").json()["jobs"][0]
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 60:
            j = cl.get(f"/jobs/{job['id']}").json()
            if j["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert j["status"] == "done", j.get("error") or j.get("log_tail")
        assert any("render (FilmCraft)" in x for x in j["log_tail"])
        rec = ClipStore(ws).get(j["result"]["clip_id"])
        tracks_now = cl.get(f"{base}/tracks").json()
        v1_end = max(i["start"] + i["duration"] for i in tracks_now["video"][0]["items"])
        assert rec is not None and rec.frames == round(v1_end) and (rec.w, rec.h) == (64, 36) and rec.model_id == "sequence"
        # a cut still a record has no tracks yet
        old = cl.post("/timelines", json={"name": "Plain"}).json()
        from loom2.timelines import TimelineStore
        TimelineStore(ws).save(TimelineStore(ws).get(old["id"]).model_copy(update={"file": None}))
        assert cl.get(f"/timelines/{old['id']}/tracks").status_code == 422


def test_a_line_voiced_after_the_cut_reaches_a1_at_the_export(tmp_path: Path):
    """CE2: lines reach A1 when the cut is made; one voiced later is brought there by the next export (one undo step), a second export
    changes nothing, a line voiced anew plays its new audio where its clip sits."""
    app = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "L", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a = _clip(ws, tmp_path, "a", (200, 0, 0), 48)
        st = StoryStore(ws)
        n = st.create_node("dialogue", title="Gate", with_shot=False)
        n = st.patch_node(n.id, {"revision": n.revision, "lines": [{"speaker": None, "text": "Come in."}, {"speaker": None, "text": "Sit down."}]})
        tl = cl.post("/timelines", json={"name": "Lines", "fps": 24, "w": 64, "h": 36}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": "x", "clip_id": a.id, "in": 0, "out": 48, "node_id": n.id}], "overlaps": [0]}).json()
        base = f"/timelines/{tl['id']}"
        assert cl.get(f"{base}/tracks").json()["audio"][0]["items"] == []                       # nothing voiced yet
        for k, secs in enumerate((0.5, 0.25)):
            wav = tmp_path / f"l{k}.wav"
            tone(str(wav), secs)
            st.set_line_audio(n.id, k, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        before = cl.get(f"{base}/tracks").json()["undo"]
        fx = cl.post(f"{base}/export", json={"format": "fcpxml"}).json()
        a1 = cl.get(f"{base}/tracks").json()
        assert fx["audio"] == 2 and fx["text"].count('lane="-1"') == 2 and 'hasAudio="1"' in fx["text"]
        assert [(i["line"], i["start"]) for i in a1["audio"][0]["items"]] == [(0, 0), (1, 24)] and a1["undo"] == before + 1
        cl.post(f"{base}/export", json={"format": "edl"})
        assert cl.get(f"{base}/tracks").json()["undo"] == before + 1                               # nothing to bring: no change
        wav = tmp_path / "again.wav"
        tone(str(wav), 0.5, hz=660)
        again = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        st.set_line_audio(n.id, 1, again.id, "x")
        cl.post(f"{base}/export", json={"format": "srt"})
        a1 = cl.get(f"{base}/tracks").json()["audio"][0]["items"]
        assert [(i["line"], i["start"], i["asset_id"]) for i in a1][1] == (1, 24, again.id)
