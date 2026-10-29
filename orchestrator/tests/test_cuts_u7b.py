"""U7b (D157, proto01_UI2 05 §1, 06 §3; G14): Assemble from the Flow on the backend, on tests/fake_filmcraft.py — each shot of the route at
its final (the version marked final, else its latest final, a one-pass version's clip; none: listed), only what changed placed on V1 with the
author's edits to the rest kept (a trim, a newer final in place, a shot taken off the route, the route's order), one undo step; a shot held
for its lines or listed (F39), its clip named after it (F40); FilmCraft's refusal leaves the cut as it was."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.finals import Final, FinalStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import final_of  # noqa: E402
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


def _final(ws: Workspace, shot_id: str, clip_id: str, version: str | None = "v1") -> str:
    """A final shot made for the shot, its clip rendered (the record alone: the assemble reads only the record)."""
    fs = FinalStore(ws)
    f = Final(stage_id="stg_x", camera_id="cam_x", stage_revision=0, range={"start": 0, "end": 47}, size={"w": 832, "h": 480}, frames=48,
              shot_id=shot_id, shot_version=version)
    fs.path(f.id).parent.mkdir(parents=True, exist_ok=True)
    fs.save(f)
    f = fs.set_clip(f.id, clip_id)
    _final.n = getattr(_final, "n", 0) + 1                                      # the newest final is the one updated last (the stamps
    fs.save(f.model_copy(update={"updated_at": f"2026-01-01T00:00:{_final.n:02d}+00:00"}))   # are whole seconds)
    return f.id


def _v1(cl: TestClient, base: str) -> list[tuple]:
    return [(i["id"], i["name"], i["clip_id"], i["start"], i["duration"]) for i in cl.get(f"{base}/tracks").json()["video"][0]["items"]]


def test_a_shots_final_is_the_marked_one_then_the_latest_then_a_one_pass_clip():
    """05 §1: the marked-final version's final first; else the latest final of any version; a one-pass version's clip is its final; none."""
    def shot(versions, current="v1"):
        return NS(id="s", current=current, versions=[NS(id=v, state=st, method=m, clip_id=c) for v, st, m, c in versions])

    def fin(clip, version, at):
        return NS(shot_id="s", shot_version=version, clip_id=clip, updated_at=at)
    finals = [fin("c_old", "v1", "1"), fin("c_v2", "v2", "3"), fin("c_v1", "v1", "2"), fin(None, "v1", "9"), NS(shot_id="t", shot_version="v1", clip_id="x", updated_at="9")]
    assert final_of(shot([("v1", "final", None, "c_take"), ("v2", "open", None, None)], current="v2"), finals) == ("v1", "c_v1")   # marked final
    assert final_of(shot([("v1", "open", None, None), ("v2", "open", None, None)]), finals) == ("v2", "c_v2")                   # the latest
    assert final_of(shot([("v1", "open", None, "c_take")]), finals[:0]) == ("v1", None)                                       # a clip is no final …
    assert final_of(shot([("v1", "open", "start_still", "c_take")]), finals[:0]) == ("v1", "c_take")                          # … unless made in one pass
    assert final_of(shot([("v1", "final", "one_pass", "c_take")]), finals[:0]) == ("v1", "c_take")
    assert final_of(shot([("v1", "open", None, None)]), [NS(shot_id="s", shot_version=None, clip_id="c_pre", updated_at="1")]) == ("v1", "c_pre")   # before A1


def test_assemble_places_only_what_changed_and_keeps_the_authors_edits(tmp_path: Path):
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "A", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b, c, a2 = (_clip(ws, tmp_path, "a", (200, 0, 0), 48), _clip(ws, tmp_path, "b", (0, 0, 200)), _clip(ws, tmp_path, "c", (0, 200, 0)),
                       _clip(ws, tmp_path, "a2", (250, 50, 0), 48))
        st = StoryStore(ws)
        na, nb, nc = (st.create_node("shot", title=t) for t in ("Arrival", "The seal", "Departure"))
        _final(ws, na.shot_id, a.id)                                            # A: a final shot, rendered
        st.add_take(nb.shot_id, "v1", "clip", b.id, use=True)                   # B: made from its start still — its clip is its final
        st.patch_shot(nb.shot_id, {"revision": st.shot(nb.shot_id).revision, "versions": [{"id": "v1", "method": "start_still"}]})
        st.add_take(nc.shot_id, "v1", "clip", c.id, use=True)                   # C: a take, not a final yet
        route = [{"shot_id": n.shot_id, "node_id": n.id} for n in (na, nb, nc)]
        tl = cl.post("/timelines", json={"name": "Episode 1", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"revision": tl["revision"], "route": {}, "shots": route})
        assert r.status_code == 200, r.text
        rep = r.json()["report"]
        assert (rep["placed"], rep["missing"], rep["kept"], rep["removed"]) == (["Arrival", "The seal"], ["Departure"], [], [])
        v1 = _v1(cl, base)
        assert [(n, k, s, d) for _, n, k, s, d in v1] == [("Arrival", a.id, 0, 48), ("The seal", b.id, 48, 24)]          # F40: named after the shots
        assert [(x["shot_id"], x["node_id"]) for x in r.json()["timeline"]["clips"]] == [(na.shot_id, na.id), (nb.shot_id, nb.id)]
        # the author's ripple trim on Arrival; Departure's final lands; Assemble again keeps the trim and puts Departure after The seal
        e = cl.post(f"{base}/edit", json={"revision": r.json()["timeline"]["revision"], "steps": [{"id": "timeline.trim", "params": {"clip": v1[0][0], "edge": "out", "mode": "ripple", "deltaFrames": -8}}]})
        assert e.status_code == 200, e.text
        rev = e.json()["timeline"]["revision"]
        _final(ws, nc.shot_id, c.id)
        undo = cl.get(f"{base}/tracks").json()["undo"]
        r = cl.post(f"{base}/assemble", json={"revision": rev, "route": {}, "shots": route}).json()
        assert (r["report"]["kept"], r["report"]["placed"], r["report"]["missing"], r["report"]["renamed"]) == (["Arrival", "The seal"], ["Departure"], [], 1)
        v1b = _v1(cl, base)
        assert [(x[0], x[3], x[4]) for x in v1b[:2]] == [(v1[0][0], 0, 40), (v1[1][0], 40, 24)]                         # the same clips, the trim kept
        assert v1b[2][1:] == ("Departure", c.id, 64, 24) and r["tracks"]["undo"] == undo + 1                            # one undo step
        # a newer final of Arrival plays in place (its trim kept); the route without The seal takes it off and Departure closes up
        _final(ws, na.shot_id, a2.id)
        r = cl.post(f"{base}/assemble", json={"revision": r["timeline"]["revision"], "route": {"ch": "leave"}, "shots": [route[0], route[2]]}).json()
        assert (r["report"]["updated"], r["report"]["removed"], r["report"]["kept"]) == (["Arrival"], ["The seal"], ["Departure"])
        v1c = _v1(cl, base)
        assert [(x[0], x[2], x[3], x[4]) for x in v1c] == [(v1[0][0], a2.id, 0, 40), (v1b[2][0], c.id, 40, 24)]
        assert r["timeline"]["route"] == {"ch": "leave"}
        # the route's order changed: Departure before Arrival — Arrival (the longest run in order) stays, Departure goes in before it
        r = cl.post(f"{base}/assemble", json={"revision": r["timeline"]["revision"], "route": {}, "shots": [route[2], route[0]]}).json()
        assert (r["report"]["kept"], r["report"]["removed"], r["report"]["placed"]) == (["Arrival"], ["Departure"], ["Departure"])
        assert [(x[1], x[3], x[4]) for x in _v1(cl, base)] == [("Departure", 0, 24), ("Arrival", 24, 40)]
        # the cut's undo takes the whole Assemble back
        cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]})
        assert [(x[0], x[3]) for x in _v1(cl, base)] == [(v1[0][0], 0), (v1b[2][0], 40)]


def test_a_shot_is_held_for_its_lines_or_listed(tmp_path: Path):
    """F39: a shot's lines are laid inside it; a shot trimmed shorter than its lines is held for them from its final's frames; a final too
    short for its lines is listed (the lines run 1.5 s, the final 1.0 s). FilmCraft's refusal (a sound in the way) leaves the cut as it was."""
    app = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "H", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        a, b = _clip(ws, tmp_path, "a", (200, 0, 0), 48), _clip(ws, tmp_path, "b", (0, 0, 200))
        st = StoryStore(ws)
        na, nb = st.create_node("shot", title="Gate"), st.create_node("shot", title="Road")
        st.patch_node(na.id, {"revision": st.flow_nodes()[na.id].revision, "lines": [{"speaker": None, "text": "Come in."}, {"speaker": None, "text": "Sit."}]})
        st.patch_node(nb.id, {"revision": st.flow_nodes()[nb.id].revision, "lines": [{"speaker": None, "text": "It is a long way."}]})
        for n, k, secs in ((na, 0, 1.0), (na, 1, 0.5), (nb, 0, 1.5)):
            wav = tmp_path / f"{n.id}{k}.wav"
            tone(str(wav), secs)
            st.set_line_audio(n.id, k, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        _final(ws, na.shot_id, a.id)
        _final(ws, nb.shot_id, b.id)
        route = [{"shot_id": n.shot_id, "node_id": n.id} for n in (na, nb)]
        tl = cl.post("/timelines", json={"name": "Lines", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"revision": tl["revision"], "route": None, "shots": route}).json()
        assert r["report"]["short"] == [{"name": "Road", "lines_s": 1.5, "final_s": 1.0}] and r["report"]["held"] == []
        a1 = [(i["node_id"], i["line"], i["start"], i["duration"]) for i in r["tracks"]["audio"][0]["items"]]
        assert a1 == [(na.id, 0, 0, 24), (na.id, 1, 24, 12), (nb.id, 0, 48, 36)]                                        # Gate's inside its 48 frames
        # the author trims Gate to 24 frames (a ripple trim would cut its own line on A1: FilmCraft refuses it), its lines run 1.75 s with
        # the breath: Assemble again holds it from its final's frames, the later clips moving on (a ripple out)
        gate = _v1(cl, base)[0][0]
        e = cl.post(f"{base}/edit", json={"steps": [{"id": "timeline.trim", "params": {"clip": gate, "edge": "out", "mode": "regular", "deltaFrames": -24}}]})
        assert e.status_code == 200, e.text
        r = cl.post(f"{base}/assemble", json={"route": None, "shots": route}).json()
        assert r["report"]["held"] == ["Gate"]
        assert [(x[1], x[3], x[4]) for x in _v1(cl, base)] == [("Gate", 0, 42), ("Road", 66, 24)]
        # a sound across both shots on A2: taking Road off would break sync — FilmCraft refuses, the cut stays as it was
        wav = tmp_path / "bed.wav"
        tone(str(wav), 4.0)
        bed = svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story")
        cl.post(f"{base}/place", json={"asset_id": bed.id, "track": "A2", "frame": 0})
        before, undo = _v1(cl, base), cl.get(f"{base}/tracks").json()["undo"]
        bad = cl.post(f"{base}/assemble", json={"route": None, "shots": route[:1]})
        assert bad.status_code == 422 and "in the way" in bad.json()["detail"]
        assert _v1(cl, base) == before and cl.get(f"{base}/tracks").json()["undo"] == undo
