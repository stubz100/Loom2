"""D125 (S13, S14; SP6): a cut keeps the Flow route it was assembled from; Export for Resolve writes the FCPXML (markers.txt beside it), the EDL
and the SRT into one folder named after the cut; deleting the cut takes the folder with it."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_story_shots_d85 import _clip  # noqa: E402


def test_route_and_resolve_folder(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        ws = Workspace(tmp_path / "p")
        c = _clip(ws, tmp_path, 832, 480, 4)
        ClipStore(ws).encode_proxy(c)
        st = StoryStore(ws)
        n = st.create_node("dialogue", "Hello", lines=[{"speaker": None, "text": "Hi there."}])
        sid = n.shot_id
        tl = cl.post("/timelines", json={"name": "Episode 1 · Stay"}).json()
        assert tl["route"] is None                                                                       # a cut built by hand
        body = {**tl, "route": {"nod_choice": "stay"}, "clips": [{"id": "x", "clip_id": c.id, "in": 0, "out": 4, "fps": None, "shot_id": sid, "shot_version": "v1", "node_id": n.id}], "overlaps": [0]}
        r = cl.put(f"/timelines/{tl['id']}", json=body)
        assert r.status_code == 200 and r.json()["route"] == {"nod_choice": "stay"}
        out = cl.post(f"/timelines/{tl['id']}/export", json={"format": "resolve"}).json()
        folder = ws.path / out["path"]
        assert folder.is_dir() and folder.parent.name == tl["id"] and folder.name.startswith("episode-1")
        assert sorted(p.name for p in folder.iterdir()) == sorted(out["text"].split("\n"))
        assert {p.suffix for p in folder.iterdir()} == {".fcpxml", ".edl", ".srt", ".txt"}
        assert (folder / "markers.txt").read_text(encoding="utf-8") == "00:00:00:00\tHello\n"
        assert "Hi there." in next(folder.glob("*.srt")).read_text(encoding="utf-8")
        assert not list((ws.path / "timelines" / tl["id"]).glob("*.fcpxml"))                             # nothing left beside the folder
        assert cl.delete(f"/timelines/{tl['id']}").status_code == 200
        assert not (ws.path / "timelines" / tl["id"]).exists()
