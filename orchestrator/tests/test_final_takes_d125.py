"""D125 (A1, WB1, WB2): a final shot's assembled and rendered clips become takes of the Story shot version it was made for — the For chip's,
recorded on the final as `shot_id` + `shot_version` — or, made without one, of the shots whose current open version points at its stage and
camera (as a stage clip does). The create route checks the shot; the lines a final can attach follow the same shots. D125 (#6): a version is
marked final at any size."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.engine.finishers import _final_take  # noqa: E402
from loom2.finals import Final  # noqa: E402
from loom2.story import ShotVersion, StoryStore, finalize_reason  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

from test_finals_d111 import _png  # noqa: E402


class _Hub:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def broadcast(self, kind: str, data: dict) -> None:
        self.events.append((kind, data))


def _final(**kw) -> Final:
    return Final(stage_id="stg_1", camera_id="cam_1", stage_revision=1, range={"start": 0, "end": 12}, size={"w": 832, "h": 480}, frames=9, **kw)


def test_the_take_lands_on_the_shot_version_it_was_made_for(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    s = st.create_shot("Reunion")
    q = SimpleNamespace(ws=ws, hub=_Hub())
    _final_take(q, _final(shot_id=s.id, shot_version="v1"), "clp_asm", False, None)      # the assembly: a take, never the clip by itself
    v = st.shot(s.id).version("v1")
    assert [t.id for t in v.takes] == ["clp_asm"] and v.clip_id is None
    _final_take(q, _final(shot_id=s.id, shot_version="v1"), "clp_render", None, None)     # the render fills the empty clip slot
    v = st.shot(s.id).version("v1")
    assert [t.id for t in v.takes] == ["clp_asm", "clp_render"] and v.clip_id == "clp_render"
    assert v.stage_revision == _final().stage_revision                                     # RC1: the clip stamps the stage it read
    assert not [e for e in q.hub.events if e[1].get("error")]


def test_a_final_made_before_d125_names_no_version_and_takes_the_current_one(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    s = st.create_shot("Reunion")
    q = SimpleNamespace(ws=ws, hub=_Hub())
    _final_take(q, _final(shot_id=s.id), "clp_old", None, None)                            # WB2: the version was missing, the take was lost
    assert st.shot(s.id).version("v1").clip_id == "clp_old"


def test_without_a_shot_the_take_follows_the_camera(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    linked = st.create_shot("Wide", stage_id="stg_1", camera_id="cam_1")
    other = st.create_shot("Close", stage_id="stg_1", camera_id="cam_2")
    q = SimpleNamespace(ws=ws, hub=_Hub())
    _final_take(q, _final(), "clp_asm", False, None)
    assert [t.id for t in st.shot(linked.id).version().takes] == ["clp_asm"] and st.shot(linked.id).version().clip_id is None
    assert st.shot(other.id).version().takes == []
    _final_take(q, _final(), "clp_render", None, None)
    assert st.shot(linked.id).version().clip_id == "clp_render"


def test_any_size_is_markable():
    v = ShotVersion(id="v1", clip_id="clp")
    assert finalize_reason(v, 832, 480, 1920, 1080) is None                                # D125 (#6): approval is the author's decision
    assert "no clip yet" in (finalize_reason(ShotVersion(id="v1"), None, None, 1920, 1080) or "")


def test_the_create_route_checks_the_shot_and_the_lines_follow_it(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        st = cl.post("/stages", json={"name": "Room"}, headers=H).json()
        cam = st["cameras"][0]["id"]
        png = _png(40)
        sha = hashlib.sha256(png).hexdigest()
        assert cl.put(f"/blobs/{sha}", content=png, headers=H).status_code == 200
        still = [sha] * 3
        body = {"name": "F", "stage_id": st["id"], "camera_id": cam, "stage_revision": st["revision"], "range": {"start": 0, "end": 3}, "rate": 16,
                "size": {"w": 832, "h": 480}, "frames": 3, "layers": [{"id": "plate", "kind": "plate", "name": "Room", "passes": {"depth": still, "clay": still}},
                                                                       {"id": "shadows", "kind": "shadows", "name": "Shadows", "passes": {"clay": still}}]}
        shot = cl.post("/story/shots", json={"name": "Reunion"}, headers=H).json()
        r = cl.post("/finals", json={**body, "shot_id": shot["id"]}, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["shot_id"] == shot["id"] and r.json()["shot_version"] == "v1"           # no version given: the shot's current one
        tpl = cl.get(f"/story/shots/{shot['id']}", headers=H).json()["versions"][0]["recipe"]["template"]
        assert tpl == "clay1"                                                                    # RC1: a version made by a final shot is on the clay route
        assert cl.post("/finals", json={**body, "shot_id": "sht_nope"}, headers=H).status_code == 422
        assert cl.post("/finals", json={**body, "shot_id": shot["id"], "shot_version": "v9"}, headers=H).status_code == 422
        # the lines: a Dialogue node bound to the shot, a voiced line (the audio asset stands in) — the final made for the shot lists it
        node = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Reunion"}, headers=H).json()
        assert cl.post(f"/story/flow/nodes/{node['id']}/bind", json={"shot_id": shot["id"]}, headers=H).status_code == 200
        cl.patch(f"/story/flow/nodes/{node['id']}", json={"lines": [{"speaker": None, "text": "You kept the place.", "audio_asset_id": "ast_line", "audio_text": "You kept the place."}]}, headers=H)
        fin = r.json()["id"]
        items = cl.get(f"/finals/{fin}/lines", headers=H).json()["items"]
        assert [x["text"] for x in items] == ["You kept the place."]
        # made without a shot, a final reads the lines of the shots on its camera
        loose = cl.post("/finals", json=body, headers=H).json()
        assert cl.get(f"/finals/{loose['id']}/lines", headers=H).json()["items"] == []
        linked = cl.post("/story/shots", json={"name": "Wide", "stage_id": st["id"], "camera_id": cam}, headers=H).json()
        node2 = cl.post("/story/flow/nodes", json={"type": "dialogue", "title": "Wide"}, headers=H).json()
        cl.post(f"/story/flow/nodes/{node2['id']}/bind", json={"shot_id": linked["id"]}, headers=H)
        cl.patch(f"/story/flow/nodes/{node2['id']}", json={"lines": [{"speaker": None, "text": "Someone had to.", "audio_asset_id": "ast_l2", "audio_text": "Someone had to."}]}, headers=H)
        assert [x["text"] for x in cl.get(f"/finals/{loose['id']}/lines", headers=H).json()["items"]] == ["Someone had to."]
