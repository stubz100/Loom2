"""17 (D85) · SY4 Episode: the lane clip's shot stamps, the SRT from the nodes' Dialogue lines timed by the lane, the chapter markers in the
FCPXML and the sidecar, and the export route reading the Story records."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import Timeline, TimelineClip, srt_tc, to_fcpxml, to_markers, to_srt  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_story_shots_d85 import _clip  # noqa: E402


def _tl() -> Timeline:
    return Timeline(id="tl_1", name="Reel", fps=24, clips=[TimelineClip(id="a", clip_id="clp_a", out=48, shot_id="sht_a", shot_version="v1", node_id="node_a"),
                                                          TimelineClip(id="b", clip_id="clp_b", out=24), TimelineClip(id="c", clip_id="clp_c", out=72, shot_id="sht_c", shot_version="v2", node_id=None)],
                    overlaps=[0, 12, 0])


def test_srt_and_markers():
    assert srt_tc(0, 24) == "00:00:00,000" and srt_tc(36, 24) == "00:00:01,500" and srt_tc(24 * 3661, 24) == "01:01:01,000"
    tl = _tl()
    lines = {"a": ["Hi there.", "  ", "Come in."], "c": ["Last words"]}
    srt = to_srt(tl, lambda c: lines.get(c.id, []))
    blocks = srt.strip().split("\n\n")
    assert len(blocks) == 3
    assert blocks[0].split("\n") == ["1", "00:00:00,000 --> 00:00:01,000", "Hi there."]        # 48 ticks, two lines: 24 each
    assert blocks[1].split("\n") == ["2", "00:00:01,000 --> 00:00:02,000", "Come in."]
    assert blocks[2].split("\n")[1] == "00:00:02,500 --> 00:00:05,500"                           # clip c starts at 48 + 24 − 12 = 60 ticks
    assert to_srt(tl, lambda c: []) == ""
    names = {"a": "Hello", "c": "The gate"}
    assert to_markers(tl, lambda c: names.get(c.id)) == "00:00:00:00\tHello\n00:00:02:12\tThe gate\n"
    xml = to_fcpxml(tl, "Reel", lambda cid: (cid, f"file:///{cid}.mp4", 72, 24), lambda c: names.get(c.id))
    assert xml.count("<marker ") == 2 and '<marker start="0/24s" duration="1/24s" value="Hello"/>' in xml and 'value="The gate"' in xml
    assert '<asset-clip ref="a1" name="clp_b"' in xml and xml.count("</asset-clip>") == 2                 # the unnamed clip stays self-closing
    assert "<marker" not in to_fcpxml(tl, "Reel", lambda cid: (cid, cid, 72, 24))


def test_export_route_reads_the_story(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        big = _clip(ws, tmp_path, 1920, 1080, 4)
        ClipStore(ws).encode_proxy(big)
        st = StoryStore(ws)
        sh = st.create_shot("Gate", clip_id=big.id)
        st.finalize_shot(sh.id, "v1", (1920, 1080), (1920, 1080))
        n = st.create_node("dialogue", "Hello", lines=[{"speaker": None, "text": "Hi there."}, {"speaker": None, "text": "Come in."}])
        st.bind_shot(n.id, sh.id)
        tl = cl.post("/timelines", json={"name": "Reel"}).json()
        body = {**tl, "clips": [{"id": "x", "clip_id": big.id, "in": 0, "out": 4, "fps": None, "shot_id": sh.id, "shot_version": "v1", "node_id": n.id}, {"id": "y", "clip_id": big.id, "in": 0, "out": 4, "fps": None}], "overlaps": [0, 0]}
        r = cl.put(f"/timelines/{tl['id']}", json=body)
        assert r.status_code == 200 and r.json()["clips"][0]["shot_id"] == sh.id and r.json()["clips"][1]["shot_id"] is None     # the stamps round-trip, optional
        srt = cl.post(f"/timelines/{tl['id']}/export", json={"format": "srt"}).json()
        assert srt["format"] == "srt" and srt["path"].endswith(".srt") and "Hi there." in srt["text"] and "Come in." in srt["text"] and srt["text"].count("-->") == 2
        fx = cl.post(f"/timelines/{tl['id']}/export", json={"format": "fcpxml"}).json()
        assert 'value="Hello"' in fx["text"] and fx["text"].count("<marker ") == 1                         # the stamped clip, named by its node
        assert (ws.path / "timelines" / tl["id"] / "markers.txt").read_text(encoding="utf-8") == "00:00:00:00\tHello\n"
        assert cl.post(f"/timelines/{tl['id']}/export", json={"format": "edl"}).json()["text"].startswith("TITLE: Reel")
        assert cl.post(f"/timelines/{tl['id']}/export", json={"format": "txt"}).status_code == 422
