"""RC2b (D96, proto01_animate 31 §3a): the Shot cards' facts in one call — each shot's take, its length (the used clip's, else the voiced
lines'), the 30 s guide, and its recipe graph's stale count (a stage edited after the frame was made)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.stages import StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402
from test_story_shots_d85 import _clip  # noqa: E402
from test_layer_pass_ae4 import _wav  # noqa: E402


def test_cards(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        svc = app.state.services
        ws = Workspace(tmp_path / "p")
        st = StoryStore(ws)
        # a shot with a 40-frame clip at 24 fps: 1.67 s, from its clip
        a = st.create_node("shot", "Arrival")
        clip = _clip(ws, tmp_path, n=40)
        st.add_take(a.shot_id, "v1", "clip", clip.id)
        # a Dialogue whose two lines are voiced (0.5 s each): 1.0 s from its lines
        wav = _wav(tmp_path / "l.wav", seconds=0.5)
        audio = svc.catalogue.ingest_file(wav, kind="audio", suite="story", params={})
        d = st.create_node("dialogue", "Talk", lines=[{"speaker": None, "text": "Hi.", "audio_asset_id": audio.id, "audio_text": "Hi."},
                                                    {"speaker": None, "text": "Ho.", "audio_asset_id": audio.id, "audio_text": "Ho."}])
        # a stage shot whose frame was made at the stage's revision, then the stage moved on: its frame is stale
        stages = StageStore(ws)
        stg = stages.create("Alley", {"w": 64, "h": 64, "fps": 24})
        s = st.create_node("shot", "Gate")
        st.set_source(s.shot_id, "v1", stg.id, stg.cameras[0].id, stg.revision)
        img = svc.catalogue.ingest_file(_png(tmp_path / "f.png"), kind="image").id
        st.add_take(s.shot_id, "v1", "image", img, stage_revision=stg.revision)
        st.record_run(s.shot_id, "v1", {"kind": "stage_shot", "stage_id": stg.id, "camera_id": stg.cameras[0].id}, outputs=[img], job_id=None, seconds=12.0,
                      stage_id=stg.id, stage_revision=stg.revision)
        cards = {c["shot_id"]: c for c in cl.get("/story/shots/cards").json()["items"]}
        assert cards[s.shot_id]["stale"] == 0 and cards[s.shot_id]["stale_steps"] == []
        cur = stages.get(stg.id)
        stages.put(stg.id, {**cur.model_dump(), "revision": cur.revision, "name": "Alley at night"})
        r = cl.get("/story/shots/cards").json()
        assert r["guide_s"] == 30.0
        cards = {c["shot_id"]: c for c in r["items"]}
        assert cards[a.shot_id]["length_from"] == "clip" and abs(cards[a.shot_id]["length_s"] - 40 / 24) < 0.01 and cards[a.shot_id]["take_asset_id"] == clip.asset_id
        assert cards[a.shot_id]["node_id"] == a.id and cards[a.shot_id]["version"] == "v1"
        assert cards[d.shot_id]["length_from"] == "lines" and abs(cards[d.shot_id]["length_s"] - 1.0) < 0.05 and cards[d.shot_id]["take_asset_id"] is None
        assert cards[s.shot_id]["stale"] >= 1 and cards[s.shot_id]["take_asset_id"] == img and cards[s.shot_id]["route"] == "stage"
        assert cards[s.shot_id]["stale_steps"] == ["frame", "stage"] and cards[a.shot_id]["stale_steps"] == []   # U0 (FE#3): the board's cells


def _png(p: Path) -> Path:
    from PIL import Image
    Image.new("RGB", (64, 64), (40, 80, 120)).save(p)
    return p
