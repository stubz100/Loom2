"""P17 (D83): the sequence document — lane maths at one and at mixed frame rates, the invariants a PUT keeps (409 on a stale
revision), EDL / FCPXML exports (the EDL text is the parity fixture of frontend/src/suites/animate/lane.test.ts), and the routes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.clips import ClipStore  # noqa: E402
from loom2.timelines import StaleTimeline, Timeline, TimelineClip, TimelineStore, check, duration, starts, tc, ticks, to_edl, to_fcpxml  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

# the parity lane: three clips at 24 fps, a 12-tick dissolve into the second (the same lane lane.test.ts builds)
PARITY = Timeline(id="tl_parity", name="Parity", fps=24, w=1920, h=1080,
                  clips=[TimelineClip(id="a", clip_id="clp_aaaa0001", **{"in": 0, "out": 120}), TimelineClip(id="b", clip_id="clp_bbbb0002", **{"in": 10, "out": 110}),
                         TimelineClip(id="c", clip_id="clp_cccc0003", **{"in": 0, "out": 48})],
                  overlaps=[0, 12, 0])
PARITY_EDL = """TITLE: Parity
FCM: NON-DROP FRAME

001  aaaa0001 V     C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00
* FROM CLIP NAME: clp_aaaa0001

002  aaaa0001 V     C        00:00:04:12 00:00:04:12 00:00:04:12 00:00:04:12
002  bbbb0002 V     D    012 00:00:00:10 00:00:04:14 00:00:04:12 00:00:08:16
* FROM CLIP NAME: clp_bbbb0002

003  cccc0003 V     C        00:00:00:00 00:00:02:00 00:00:08:16 00:00:10:16
* FROM CLIP NAME: clp_cccc0003
"""


def test_lane_maths_and_timecode():
    assert starts(PARITY) == [0, 108, 208] and duration(PARITY) == 256
    assert tc(256, 24) == "00:00:10:16" and tc(0, 24) == "00:00:00:00" and tc(3600 * 24 + 25, 24) == "01:00:01:01"
    check(PARITY)
    # a 16 fps clip on the 24 fps lane takes round(81 × 24 / 16) = 122 ticks; the maths never makes frames
    mixed = Timeline(id="tl_m", fps=24, clips=[TimelineClip(id="w", clip_id="clp_w", fps=16, **{"in": 0, "out": 81}), TimelineClip(id="l", clip_id="clp_l", **{"in": 0, "out": 121})],
                     overlaps=[0, 24])
    assert ticks(mixed, mixed.clips[0]) == 122 and starts(mixed) == [0, 98] and duration(mixed) == 219


def test_invariants():
    with pytest.raises(ValueError, match="overlaps"):
        check(Timeline(id="x", clips=[TimelineClip(id="a", clip_id="c", **{"in": 0, "out": 10})], overlaps=[]))
    with pytest.raises(ValueError, match="first clip"):
        check(Timeline(id="x", clips=[TimelineClip(id="a", clip_id="c", **{"in": 0, "out": 10})], overlaps=[3]))
    with pytest.raises(ValueError, match="shorter than both"):
        check(Timeline(id="x", clips=[TimelineClip(id="a", clip_id="c", **{"in": 0, "out": 10}), TimelineClip(id="b", clip_id="c", **{"in": 0, "out": 10})], overlaps=[0, 10]))
    with pytest.raises(ValueError, match="past the clip"):
        check(Timeline(id="x", clips=[TimelineClip(id="a", clip_id="c", **{"in": 0, "out": 10})], overlaps=[0]), {"c": 8})
    with pytest.raises(ValueError, match="not in the project"):
        check(Timeline(id="x", clips=[TimelineClip(id="a", clip_id="zz", **{"in": 0, "out": 10})], overlaps=[0]), {"c": 8})


def test_exports_match_the_parity_fixture():
    assert to_edl(PARITY, "Parity") == PARITY_EDL
    xml = to_fcpxml(PARITY, "Parity", lambda cid: (cid, f"file:///x/{cid}.mp4", 120, 24))
    assert '<fcpxml version="1.10">' in xml and xml.count("<asset-clip") == 3 and xml.count('<transition name="Cross Dissolve"') == 1
    assert 'offset="108/24s" duration="12/24s"' in xml and 'duration="256/24s"' in xml and '<format id="f24"' in xml
    mixed = Timeline(id="tl_m", name="Mixed", fps=24, clips=[TimelineClip(id="w", clip_id="clp_w", fps=16, **{"in": 0, "out": 81})], overlaps=[0])
    xml2 = to_fcpxml(mixed, "Mixed", lambda cid: (cid, "file:///w.mp4", 81, 16))
    assert '<format id="f16"' in xml2 and '<format id="f24"' in xml2 and 'duration="81/16s" format="f16"' in xml2   # the clip keeps its rate


def test_store_put_revision_and_delete(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = TimelineStore(ws)
    tl = st.create("Opening", fps=24, w=1920, h=1080)
    assert tl.revision == 0 and st.get(tl.id) == tl and [t.id for t in st.list()] == [tl.id]
    body = {**tl.model_dump(by_alias=True), "clips": [{"id": "a", "clip_id": "clp_x", "in": 0, "out": 10}], "overlaps": [0]}
    t1 = st.put(tl.id, body, {"clp_x": 10})
    assert t1.revision == 1 and t1.clips[0].length == 10 and t1.schema_version == 1
    with pytest.raises(StaleTimeline):
        st.put(tl.id, body, {"clp_x": 10})                                   # based on revision 0 again
    with pytest.raises(ValueError):
        st.put(tl.id, {**body, "revision": 1, "clips": [{"id": "a", "clip_id": "clp_x", "in": 0, "out": 11}]}, {"clp_x": 10})
    assert st.get(tl.id).revision == 1                                       # a refused PUT changes nothing
    assert st.delete(tl.id) and st.get(tl.id) is None and not st.delete(tl.id)


def test_routes(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        assert cl.get("/timelines", headers=H).status_code == 409                # no project
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "T", "size_cap_gb": 10}, headers=H)
        ws = Workspace(tmp_path / "proj")
        frames = []
        for i in range(4):
            p = tmp_path / f"f{i}.png"
            Image.new("RGB", (64, 48), (i * 60, 20, 200)).save(p)
            frames.append(p)
        rec = ClipStore(ws).create(frames, model_id="wan22-i2v-high-fp8", prompt="t", seed=1, fps=16, start_asset_id="ast_x")
        tl = cl.post("/timelines", json={"name": "Reel"}, headers=H).json()
        assert tl["fps"] == 24 and tl["w"] == 1920 and tl["revision"] == 0 and tl["schema_version"] == 1
        assert [t["id"] for t in cl.get("/timelines", headers=H).json()["items"]] == [tl["id"]]
        body = {**tl, "clips": [{"id": "a", "clip_id": rec.id, "in": 0, "out": 4, "fps": 16}], "overlaps": [0]}
        r = cl.put(f"/timelines/{tl['id']}", json=body, headers=H)
        assert r.status_code == 200 and r.json()["revision"] == 1
        assert cl.put(f"/timelines/{tl['id']}", json=body, headers=H).status_code == 409           # stale base
        bad = {**body, "revision": 1, "clips": [{"id": "a", "clip_id": rec.id, "in": 0, "out": 9}]}
        assert cl.put(f"/timelines/{tl['id']}", json=bad, headers=H).status_code == 422            # past the clip's frames
        ghost = {**body, "revision": 1, "clips": [{"id": "a", "clip_id": "clp_ghost", "in": 0, "out": 2}]}
        assert cl.put(f"/timelines/{tl['id']}", json=ghost, headers=H).status_code == 422
        e = cl.post(f"/timelines/{tl['id']}/export", json={"format": "edl"}, headers=H).json()
        assert e["format"] == "edl" and e["text"].startswith("TITLE: Reel") and (ws.path / e["path"]).is_file()
        x = cl.post(f"/timelines/{tl['id']}/export", json={"format": "fcpxml"}, headers=H).json()
        assert "<fcpxml" in x["text"] and 'format="f16"' in x["text"] and x["path"].endswith(".fcpxml")
        assert cl.post(f"/timelines/{tl['id']}/export", json={"format": "aaf"}, headers=H).status_code == 422
        assert cl.delete(f"/timelines/{tl['id']}", headers=H).json()["deleted"] == tl["id"]
        assert cl.get(f"/timelines/{tl['id']}", headers=H).status_code == 404
