"""C3 (D181, propo02 04 §4.3, §4.6; 05 Q4, Q6): Record and the scene's length.

- a scene has a length (frames): a new one starts at the project's default (5 s, PUT /project/defaults sets it, 20 s the cap); the stage's
  range and a shot's range lie inside it; the length never grows by itself (F37) — a range past it is refused, the scene is lengthened first;
  a scene from before C3 (length 0) reads as what it already spans;
- Record ▶ posts the frames it rendered (blobs) as the version's animatic: a clip of the project with its proxy, the proxy a video asset
  in the shot's home (the Bin under the shot), the version stamped with the scene's revision; a second recording replaces the row's clip
  and keeps the first in the Bin; the cards read the animatic's length and picture; Episode's final_of lays the animatic when the version
  has nothing else (Q6).
"""
from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.stages import StageRange, StageStore, scene_length  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.timelines import final_of  # noqa: E402
from loom2.workspace import SCENE_SECONDS_DEFAULT, SCENE_SECONDS_MAX, Workspace  # noqa: E402


def _client(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    app = create_app(state)
    return app, TestClient(app, headers={"X-Loom-Token": app.state.services.app.token})


def _png_bytes(i: int) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (64, 36), (i * 20, 40, 90)).save(b, format="PNG")
    return b.getvalue()


def test_the_scenes_length(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    stages = StageStore(ws)
    st = stages.create("Quay", {"w": 1920, "h": 1080, "fps": 24}, seconds=SCENE_SECONDS_DEFAULT)
    assert st.length == 120 and st.range.model_dump() == {"start": 0, "end": 119} and scene_length(st) == 120
    old = stages.create("Before C3")                                            # the default when no seconds are given (the project's)
    assert old.length == 120
    old = stages.put(old.id, {"revision": old.revision, "length": 0, "range": {"start": 0, "end": 120}})   # a stage from before C3: no length, the range as it was
    assert old.length == 0 and scene_length(old) == 121
    with pytest.raises(ValueError, match="lengthen the scene first"):            # F37: the range never lengthens the scene
        stages.put(st.id, {"revision": st.revision, "range": {"start": 0, "end": 130}})
    with pytest.raises(ValueError, match=f"at most {SCENE_SECONDS_MAX} s"):
        stages.put(st.id, {"revision": st.revision, "length": SCENE_SECONDS_MAX * 24 + 1})
    longer = stages.put(st.id, {"revision": st.revision, "length": 240})          # lengthened first, then the range
    assert longer.length == 240
    ranged = stages.put(st.id, {"revision": longer.revision, "range": {"start": 0, "end": 130}})
    assert ranged.range.end == 130 and scene_length(ranged) == 240
    grown = stages.put(old.id, {"revision": old.revision, "range": {"start": 0, "end": 300}})   # before C3: nothing to run past
    assert grown.range.end == 300 and scene_length(grown) == 301


def test_the_project_default_and_the_shots_range(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        assert cl.get("/project").json()["scene_seconds"] == SCENE_SECONDS_DEFAULT
        a = cl.post("/story/flow/shots", json={"title": "Wide", "scene": "new"}).json()
        sid = a["shot_id"]
        v = cl.get(f"/story/shots/{sid}").json()["versions"][0]
        st = cl.get(f"/stages/{v['stage_id']}").json()
        assert st["length"] == SCENE_SECONDS_DEFAULT * 24 and st["range"] == {"start": 0, "end": SCENE_SECONDS_DEFAULT * 24 - 1}
        rev = cl.get(f"/story/shots/{sid}").json()["revision"]
        r = cl.patch(f"/story/shots/{sid}", json={"revision": rev, "versions": [{"id": "v1", "range": {"start": 0, "end": 150}}]})
        assert r.status_code == 422 and "lengthen the scene" in r.json()["detail"]
        r = cl.patch(f"/story/shots/{sid}", json={"revision": rev, "versions": [{"id": "v1", "range": {"start": 10, "end": 100}}]})
        assert r.status_code == 200 and r.json()["versions"][0]["range"] == {"start": 10, "end": 100}
        assert cl.put("/project/defaults", json={"scene_seconds": 8}).json()["scene_seconds"] == 8
        assert cl.put("/project/defaults", json={"scene_seconds": 25}).status_code == 422
        b = cl.post("/story/flow/shots", json={"title": "Close", "scene": "new"}).json()
        v2 = cl.get(f"/story/shots/{b['shot_id']}").json()["versions"][0]
        assert cl.get(f"/stages/{v2['stage_id']}").json()["length"] == 8 * 24
        made = cl.post("/stages", json={"name": "By hand"}).json()
        assert made["length"] == 8 * 24 and made["range"]["end"] == 8 * 24 - 1


def test_record_writes_the_animatic(tmp_path: Path):
    app, cl = _client(tmp_path)
    with cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        a = cl.post("/story/flow/shots", json={"title": "Wide", "scene": "new"}).json()
        sid = a["shot_id"]
        v = cl.get(f"/story/shots/{sid}").json()["versions"][0]
        st = cl.get(f"/stages/{v['stage_id']}").json()
        shas = []
        for i in range(9):
            data = _png_bytes(i)
            sha = hashlib.sha256(data).hexdigest()
            assert cl.put(f"/blobs/{sha}", content=data).status_code == 200
            shas.append(sha)
        r = cl.post(f"/story/shots/{sid}/versions/v1/animatic", json={"frames": shas, "fps": 24})
        assert r.status_code == 200, r.text
        an = r.json()["versions"][0]["animatic"]
        assert an and an["frames"] == 9 and an["fps"] == 24 and an["size"] == {"w": 64, "h": 36} and an["stage_id"] == st["id"] and an["stage_revision"] == st["revision"]
        ws = app.state.services.ws
        clip = ClipStore(ws).get(an["clip_id"])
        assert clip is not None and clip.model_id == "animatic" and clip.frames == 9 and clip.proxy_path and clip.asset_id == an["asset_id"]
        asset = cl.get(f"/assets/{an['asset_id']}").json()
        assert asset["kind"] == "video" and asset["lineage_kind"] == "animatic" and asset["origin"]["payload"]["shot_id"] == sid
        groups = app.state.services.groups
        home = groups._get(groups.parent[("asset", an["asset_id"])])
        assert home.path == f"shots/{sid}/v1"                                        # the Bin under the shot (U2e's home)
        card = next(x for x in cl.get("/story/shots/cards").json()["items"] if x["shot_id"] == sid)
        assert card["length_from"] == "animatic" and card["length_s"] == 0.38 and card["take_asset_id"] == an["asset_id"]
        shot = StoryStore(ws).shot(sid)
        assert final_of(shot, []) == ("v1", an["clip_id"])                          # Q6: Episode cuts the animatic before any model runs
        # recorded again: the newest on the row, the first still a clip of the project
        r2 = cl.post(f"/story/shots/{sid}/versions/v1/animatic", json={"frames": shas[:4], "fps": 24})
        an2 = r2.json()["versions"][0]["animatic"]
        assert an2["clip_id"] != an["clip_id"] and an2["frames"] == 4 and ClipStore(ws).get(an["clip_id"]) is not None
        # no scene, no animatic; a blob never uploaded is refused
        free = cl.post("/story/shots", json={"name": "Free"}).json()
        assert cl.post(f"/story/shots/{free['id']}/versions/{free['current']}/animatic", json={"frames": shas[:1], "fps": 24}).status_code == 422
        assert cl.post(f"/story/shots/{sid}/versions/v1/animatic", json={"frames": ["0" * 64], "fps": 24}).status_code == 422
        assert cl.post(f"/story/shots/{sid}/versions/v9/animatic", json={"frames": shas[:1], "fps": 24}).status_code == 404
