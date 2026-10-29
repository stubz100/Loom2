"""D158 (E42; F42, F43): a figure turned away from the camera is performed from behind.

- a frame faces away when the figure's right eye is on the image's right of its left one, or (an eye out of frame) its right shoulder;
  a layer is performed from behind when more than half of its frames face away;
- such a layer's run takes the version's back A-pose (the front one when it has none) and the words for it; a layer facing the camera
  keeps the front one and the app's words.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from loom2.finals import BACK_WORDS, faces_away, mostly_away  # noqa: E402


def _kp(away: bool, eyes: bool = True) -> list:
    """A whole figure (nose, hips, ankles where place_reference wants them), its shoulders and eyes mirrored when it faces away."""
    k = [[0.0, 0.0, 0.0] for _ in range(18)]
    k[0] = [64.0, 20.0, 1.0]
    for i in (8, 11):
        k[i] = [64.0, 60.0, 1.0]
    k[10], k[13] = [58.0, 110.0, 1.0], [70.0, 110.0, 1.0]
    right, left = (74.0, 54.0) if away else (54.0, 74.0)                # a figure facing the camera has its right on the image's left
    k[2], k[5] = [right, 30.0, 1.0], [left, 30.0, 1.0]
    if eyes:                                                            # the right eye (14) and the left (15), mirrored the same way
        k[14], k[15] = ([70.0, 18.0, 1.0], [58.0, 18.0, 1.0]) if away else ([58.0, 18.0, 1.0], [70.0, 18.0, 1.0])
    return k


def test_a_frame_faces_away_by_its_eyes_else_its_shoulders():
    assert faces_away(_kp(True)) and not faces_away(_kp(False))
    assert faces_away(_kp(True, eyes=False)) and not faces_away(_kp(False, eyes=False))
    head_turned = _kp(False)
    head_turned[14][0], head_turned[15][0] = 70.0, 58.0                 # the body to the camera, the head looking back over the shoulder
    assert faces_away(head_turned)
    assert not faces_away(None) and not faces_away([])
    assert mostly_away([_kp(True)] * 3 + [_kp(False)] * 2) and not mostly_away([_kp(True)] * 2 + [_kp(False)] * 2) and not mostly_away([])


def _run(tmp_path: Path, away: bool, back: bool) -> tuple[dict, dict]:
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.catalogue import Catalogue
    from loom2.config import AppState
    from loom2.finals import FinalStore
    from loom2.groups import GroupStore
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    from PIL import Image
    from test_finals_d111 import _figure_ref
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        ws = Workspace(tmp_path / "proj")
        cat = Catalogue(ws, [32], session_id="t")
        front = cat.ingest_file(_figure_ref(tmp_path / "front.png"), kind="image", move=False, suite="stage")
        back_ref = cat.ingest_file(_figure_ref(tmp_path / "back.png"), kind="image", move=False, suite="stage")
        st = StoryStore(ws)
        p = st.create_profile("Ines", "character", GroupStore(ws, cat), appearance="a young woman in a red raincoat")
        st.set_anim_ref(p.id, "v1", "front", front.id)
        if back:
            st.set_anim_ref(p.id, "v1", "back", back_ref.id)
        stage = cl.post("/stages", json={"name": "Street"}, headers=H).json()
        png = ws.temp_dir / "p.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (128, 128), (128, 128, 128)).save(png)
        n = 20
        data = {"name": "Shot", "stage_id": stage["id"], "camera_id": stage["cameras"][0]["id"], "stage_revision": 0, "range": {"start": 0, "end": 19}, "rate": 16,
                "size": {"w": 128, "h": 128}, "frames": n,
                "layers": [{"id": "plate", "kind": "plate", "name": "Street", "method": "projected"}, {"id": "fig", "kind": "figure", "name": "Ines", "object_id": "fig_1", "method": "move", "profile_id": p.id},
                           {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
        f = FinalStore(ws).create(data, {"plate": {"depth": [png] * n, "clay": [png] * n}, "fig": {"pose": [png] * n, "depth": [png] * n}, "shadows": {"clay": [png] * n}},
                                  {"fig": [_kp(away)] * n})
        r = cl.post(f"/finals/{f.id}/layers/fig/run", json={}, headers=H)
        assert r.status_code == 200, r.text
        job = next(j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] == r.json()["job_id"])
        return r.json(), job


def test_a_layer_facing_away_is_performed_from_behind(tmp_path: Path):
    out, job = _run(tmp_path / "a", away=True, back=True)
    assert out["from_behind"] and out["back_view"] and BACK_WORDS in job["recipe"]["prompt_text"]
    out, job = _run(tmp_path / "b", away=True, back=False)                   # no back view: the front one, the words still
    assert out["from_behind"] and not out["back_view"] and BACK_WORDS in job["recipe"]["prompt_text"]
    out, job = _run(tmp_path / "c", away=False, back=True)                   # facing the camera: as before
    assert not out["from_behind"] and not out["back_view"] and BACK_WORDS not in job["recipe"]["prompt_text"]
