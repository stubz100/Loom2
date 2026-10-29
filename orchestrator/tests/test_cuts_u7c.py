"""U7c (D157, proto01_UI2 05 §1, 06 §3; G14), on tests/fake_filmcraft.py: a 16 fps take on a 24 fps cut conformed by RIFE as it lands — the
Assemble queues a conform job, which swaps the RIFE frames in for the proxy as one undo step and moves the cut's revision on; an export that
brings a voiced line onto A1 moves it on too; a change holds the FilmCraft session whole; the cut editor's facts and ranges in /capabilities."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2 import final_assembly  # noqa: E402
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import STRIP_GAIN_DB, STRIP_PAN, STRIP_VOLUME_DB, STRIP_WIDTH, AppState  # noqa: E402
from loom2.cuts import CUT_LOCK, GRADE_PARAMS  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from fake_tts import tone  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}})
    return create_app(state)


def _clip(ws: Workspace, tmp_path: Path, tag: str, n: int, fps: int):
    cs = ClipStore(ws)
    frames = []
    for i in range(n):
        p = tmp_path / f"{tag}{i}.png"
        Image.new("RGB", (32, 24), (200, 0, 0)).save(p)
        frames.append(p)
    return cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt=tag, seed=1, fps=fps, start_asset_id="ast_x"))


def _one_pass(st: StoryStore, title: str, clip_id: str):
    n = st.create_node("shot", title=title)
    st.add_take(n.shot_id, "v1", "clip", clip_id, use=True)
    st.patch_shot(n.shot_id, {"revision": st.shot(n.shot_id).revision, "versions": [{"id": "v1", "method": "start_still"}]})
    return n


def test_a_16fps_take_is_conformed_as_it_lands_in_one_undo_step(tmp_path: Path, monkeypatch):
    conformed: list[tuple[str, int]] = []

    def fake_conform(src: Path, dst: Path, n16: int, cancelled=None) -> list[Path]:          # RIFE's shape: (n16 − 1) × 1.5 + 1 frames
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
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "C", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        wan, own = _clip(ws, tmp_path, "w", 17, 16), _clip(ws, tmp_path, "o", 24, 24)   # 1 s at 16 fps (25 frames at 24), 1 s at 24
        st = StoryStore(ws)
        route = [{"shot_id": n.shot_id, "node_id": n.id} for n in (_one_pass(st, "Gate", own.id), _one_pass(st, "Road", wan.id))]
        tl = cl.post("/timelines", json={"name": "Conform", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"revision": tl["revision"], "route": None, "shots": route}).json()
        assert r["report"]["placed"] == ["Gate", "Road"] and len(r["conforming"]) == 1                      # the 16 fps take only
        rev, undo = r["timeline"]["revision"], r["tracks"]["undo"]
        job = cl.get(f"/jobs/{r['conforming'][0]}").json()
        assert job["recipe"]["kind"] == "render" and job["recipe"]["conform"] is True and job["warm_group"] == "cpu"
        cl.post("/queue/unpause")
        t0 = time.time()
        while time.time() - t0 < 60:
            job = cl.get(f"/jobs/{job['id']}").json()
            if job["status"] in ("done", "failed", "cancelled"):
                break
            time.sleep(0.2)
        assert job["status"] == "done", job.get("error") or job.get("log_tail")
        assert job["result"]["conformed"] == [wan.id] and conformed == [(wan.id, 17)]
        tr = cl.get(f"{base}/tracks").json()
        v1 = tr["video"][0]["items"]
        assert [(i["name"], i["start"], i["duration"]) for i in v1] == [("Gate", 0, 24), ("Road", 24, 25)]   # in place, its length kept
        assert "conform24" in (v1[1]["media_path"] or "") and "conform24" not in (v1[0]["media_path"] or "")
        assert tr["undo"] == undo + 1 and cl.get(base).json()["revision"] == rev + 1                         # one undo step; the revision moved on
        # Assemble again: the conformed take is the take (its links kept) — nothing to place, nothing to conform
        r = cl.post(f"{base}/assemble", json={"revision": rev + 1, "route": None, "shots": route}).json()
        assert (r["report"]["kept"], r["report"]["placed"], r["report"]["renamed"], r["conforming"]) == (["Gate", "Road"], [], 0, [])
        # the cut's undo takes that Assemble back, then the conform: the proxy plays again
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert "conform24" in (r["tracks"]["video"][0]["items"][1]["media_path"] or "")
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert "conform24" not in (r["tracks"]["video"][0]["items"][1]["media_path"] or "")


def test_an_export_that_brings_a_line_moves_the_revision_and_a_change_holds_the_session(tmp_path: Path):
    app = _client(tmp_path)
    svc = app.state.services
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "E", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        st = StoryStore(ws)
        n = _one_pass(st, "Gate", _clip(ws, tmp_path, "g", 48, 24).id)
        st.patch_node(n.id, {"revision": st.flow_nodes()[n.id].revision, "lines": [{"speaker": None, "text": "Come in."}]})
        tl = cl.post("/timelines", json={"name": "Lines", "fps": 24, "w": 64, "h": 36}).json()
        base = f"/timelines/{tl['id']}"
        r = cl.post(f"{base}/assemble", json={"route": None, "shots": [{"shot_id": n.shot_id, "node_id": n.id}]}).json()
        rev = r["timeline"]["revision"]
        wav = tmp_path / "l.wav"
        tone(str(wav), 0.5)
        st.set_line_audio(n.id, 0, svc.catalogue.ingest_file(wav, kind="audio", move=False, suite="story").id, "x")
        cl.post(f"{base}/export", json={"format": "srt"})
        assert cl.get(base).json()["revision"] == rev + 1                                                   # the line came onto A1
        cl.post(f"{base}/export", json={"format": "srt"})
        assert cl.get(base).json()["revision"] == rev + 1                                                   # nothing to bring: no change
        # a change holds the FilmCraft session whole: another thread cannot start one meanwhile
        from loom2.routes.timelines import _store
        store = _store(svc, ws, svc.catalogue)
        seen: list[bool] = []

        def fn(p: Path) -> None:
            t = threading.Thread(target=lambda: seen.append(CUT_LOCK.acquire(timeout=0.1)))
            t.start()
            t.join()
        store.cuts.changing(store.get(tl["id"]), fn)
        assert seen == [False]


def test_the_cut_editors_facts_and_ranges_are_in_capabilities(tmp_path: Path):
    app = _client(tmp_path)
    with TestClient(app) as cl:
        cut = cl.get("/capabilities").json()["cut"]
        assert cut["available"] is True and cut["conform"] == (final_assembly.rife_binary() is not None)
        assert cut["strip"] == {"gain_db": list(STRIP_GAIN_DB), "volume_db": list(STRIP_VOLUME_DB), "pan": list(STRIP_PAN), "width": list(STRIP_WIDTH)}
        assert cut["grade"] == {k: list(v) for k, v in GRADE_PARAMS.items()}
