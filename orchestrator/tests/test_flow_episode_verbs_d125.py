"""D125 (S4, S8; SP7): a node keeps the spine beat it was made from; Voice all lines voices every Dialogue line of the episode not voiced yet
or changed since — naming a line without a voice first, queuing nothing then."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_voice_cn2 import FAKE  # noqa: E402


def test_beat_and_episode_voice(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [],
                                     "variant": "full", "voices": {"python": sys.executable, "run": str(FAKE)}, "hf_home": str(state / "hf")})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        # the beat a node was made from rides along and survives an edit
        b = cl.post("/story/flow/nodes", json={"type": "shot", "title": "The gate", "beat_id": "beat_1"}).json()
        assert b["beat_id"] == "beat_1" and b["shot_id"]
        assert cl.patch(f"/story/flow/nodes/{b['id']}", json={"revision": b["revision"], "title": "The gate at dusk"}).json()["beat_id"] == "beat_1"
        # Voice all lines: the unvoiced and the changed lines of every Dialogue node
        narrator = cl.post("/story/voices", json={"name": "Narrator", "voice": "af_heart"}).json()["id"]
        mara = cl.post("/story/profiles", json={"name": "Mara", "cls": "character"}).json()
        cl.patch(f"/story/profiles/{mara['id']}", json={"revision": mara["revision"], "voice_id": narrator})
        tam = cl.post("/story/profiles", json={"name": "Tam", "cls": "character"}).json()
        one = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "One"}).json()
        cl.patch(f"/story/flow/nodes/{one['id']}", json={"revision": one["revision"], "lines": [{"speaker": mara["id"], "text": "Hi there."}, {"speaker": mara["id"], "text": "Done."}, {"speaker": mara["id"], "text": "Changed."}]})
        two = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Two"}).json()
        cl.patch(f"/story/flow/nodes/{two['id']}", json={"revision": two["revision"], "lines": [{"speaker": tam["id"], "text": "Come in."}]})
        st = StoryStore(ws)
        st.set_line_audio(one["id"], 1, "ast_done", "Done.")                                       # voiced: skipped
        st.set_line_audio(one["id"], 2, "ast_old", "Changed before.")                              # changed since: voiced again
        miss = cl.post("/story/flow/voice", json={"stage": True})
        assert miss.status_code == 422 and "Two line 1" in miss.json()["detail"]                   # Tam has no voice, none picked
        assert not [j for j in cl.get("/jobs").json()["items"] if j["kind"] == "tts"]               # nothing queued
        r = cl.post("/story/flow/voice", json={"voice_id": narrator, "stage": True})
        assert r.status_code == 200, r.text
        assert r.json()["lines"] == 3 and len(r.json()["job_ids"]) == 2                           # one job per voice and node
        items = sorted((it["node_id"], it["index"]) for j in cl.get("/jobs").json()["items"] if j["kind"] == "tts" for it in j["recipe"]["items"])
        assert items == sorted([(one["id"], 0), (one["id"], 2), (two["id"], 0)])
