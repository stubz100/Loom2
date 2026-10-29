"""U4d (D157, G13; proto01_UI2 04 §6, 06 §2.8): the words of a shot's pictures, from the shot's own records, part by part with their sources.

- the Look (the default style), the place (its sheet), the cast the shot's camera sees (left to right; a thing behind the camera is not
  in it), the lights as words for that camera, the scene's words, the action (the description) and this shot's own words, in that order;
- a plate has no cast and no action; the route gives them for a purpose; the words of the scene and the shot are patched with their records;
- the plate route sends a shot's plate words after the place-neutral lead (F38: not "the room … bare walls and floor" on a street).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from loom2.shot_prompt import light_words, screen_x, shot_prompt  # noqa: E402
from loom2.stages import StageCamera, StageObject, StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from test_groups_d34 import _setup  # noqa: E402


def _final_on_disk(ws, stage_id: str, camera_id: str, shot: tuple[str, str]):
    """test_finals_d111's final with its passes, made for a shot."""
    from loom2.finals import FinalStore
    from PIL import Image
    src = ws.temp_dir / "blobs"
    src.mkdir(parents=True, exist_ok=True)
    png = src / "grey.png"
    Image.new("RGB", (64, 48), (128, 128, 128)).save(png)
    data = {"name": "Shot", "stage_id": stage_id, "camera_id": camera_id, "stage_revision": 0, "range": {"start": 0, "end": 3}, "rate": 16,
            "size": {"w": 128, "h": 128}, "frames": 3, "shot_id": shot[0], "shot_version": shot[1],
            "layers": [{"id": "plate", "kind": "plate", "name": "Street", "method": "projected"}, {"id": "shadows", "kind": "shadows", "name": "Shadows", "method": "stage"}]}
    return FinalStore(ws).create(data, {"plate": {"depth": [png] * 3, "clay": [png] * 3}, "shadows": {"clay": [png] * 3}}, {})


def _groups(ws):
    from loom2.catalogue import Catalogue
    from loom2.groups import GroupStore
    return GroupStore(ws, Catalogue(ws, [32], session_id="ses_now"))


def _story(tmp_path: Path):
    ws, cat, groups, ids = _setup(tmp_path)
    st = StoryStore(ws)
    st.put_world({"styles": [{"id": "sty_noir", "name": "Harbour noir", "fragment": "moody teal and amber, film grain"}], "default_style": "sty_noir"})
    pier = st.create_profile("Harbour pier", "place", groups, hero_asset_id=ids[0], appearance="a weathered wooden pier, iron lamps")
    ines = st.create_profile("Ines", "character", groups, hero_asset_id=ids[1], appearance="a woman in her thirties", outfit="a red wool coat")
    tomas = st.create_profile("Tomas", "character", groups, appearance="an old ferryman with a grey beard")
    crate = st.create_profile("Crate", "prop", groups, appearance="a fish crate")
    n = st.make_shot("The seal", place_id=pier.id)
    v = st.shot(n.shot_id).version()
    stages = StageStore(ws)
    stg = stages.get(v.stage_id)
    objs = [StageObject(id="o_ines", kind="mannequin", name="Figure 1", profile_id=ines.id, transform={"pos": [-1.0, 0.0, 0.0]}),
            StageObject(id="o_tomas", kind="mannequin", name="Figure 2", profile_id=tomas.id, transform={"pos": [1.0, 0.0, 0.0]}),
            StageObject(id="o_crate", kind="mesh", name="Crate", profile_id=crate.id, transform={"pos": [0.0, 0.0, 8.0]}),     # behind the camera
            StageObject(id="o_lamp", kind="light", name="Lamp", transform={"pos": [-4.0, 2.5, 0.0]}, light={"colour": "#ffb070", "softness": 0.7, "target": [0, 1, 0]}),
            StageObject(id="o_moon", kind="light", name="Moonlight", transform={"pos": [0.0, 3.0, -6.0]}, light={"colour": "#9fb4ff", "intensity": 0.6})]
    stages.put(stg.id, {"revision": stg.revision, "objects": [o.model_dump() for o in objs]})
    scn = st.flow_node(n.id).scene_id
    st.patch_scene(scn, {"words": "night, drifting fog"})
    st.patch_node(n.id, {"text": "Ines shows the letter; Tomas recognises the wax seal"})
    st.patch_shot(n.shot_id, {"revision": st.shot(n.shot_id).revision, "versions": [{"id": "v1", "words": "rain on the planks"}]})
    return ws, st, n, ids


def test_the_words_of_a_still_part_by_part(tmp_path: Path):
    ws, st, n, ids = _story(tmp_path)
    p = shot_prompt(ws, n.shot_id, None, "still")
    assert [x.id for x in p.parts] == ["look", "place", "cast", "lights", "scene", "action", "shot"]
    by = {x.id: x for x in p.parts}
    assert by["look"].source == "World › Look › Harbour noir ★" and by["look"].text == "moody teal and amber, film grain"
    assert by["place"].text == "Harbour pier: a weathered wooden pier, iron lamps" and by["place"].refs and by["place"].source.startswith("World › Places › Harbour pier")
    assert by["cast"].text == "Ines, a woman in her thirties, wearing a red wool coat; Tomas, an old ferryman with a grey beard"   # left to right, the crate behind the camera left out
    assert by["cast"].source == "Clay › Ines, Tomas (left to right)" and len(by["cast"].refs) == 1                   # Ines has a hero, Tomas none
    assert by["lights"].text == "warm soft lamp light from the left, cool dim moonlight from behind"
    assert (by["scene"].text, by["action"].source, by["shot"].text) == ("night, drifting fog", "the shot's description", "rain on the planks")
    assert p.text.startswith("moody teal and amber, film grain. Harbour pier: a weathered wooden pier, iron lamps. Ines,") and p.text.endswith("rain on the planks.")


def test_a_plate_has_no_cast_and_no_action(tmp_path: Path):
    ws, st, n, _ = _story(tmp_path)
    p = shot_prompt(ws, n.shot_id, "v1", "plate")
    assert [x.id for x in p.parts] == ["look", "place", "lights", "scene", "shot"] and "Ines" not in p.text and "letter" not in p.text
    # the place bound to the set wins over the node's (Stay: the street set, the node still at the pier)
    street = st.create_profile("Town street", "place", _groups(ws), appearance="a narrow cobbled street")
    stages = StageStore(ws)
    stg = stages.get(st.shot(n.shot_id).version().stage_id)
    stages.put(stg.id, {"revision": stg.revision, "objects": [*[o.model_dump() for o in stg.objects],
                                                             StageObject(id="o_set", kind="set", name="Street", preset="built", profile_id=street.id, place_set={"kind": "street"}).model_dump()]})
    assert shot_prompt(ws, n.shot_id, "v1", "plate").parts[1].text == "Town street: a narrow cobbled street"
    with pytest.raises(ValueError):
        shot_prompt(ws, n.shot_id, "v1", "poster")
    with pytest.raises(KeyError):
        shot_prompt(ws, "sht_nope", None, "still")
    with pytest.raises(ValueError, match="final"):                           # a final version's words are fixed with it
        sid = n.shot_id
        rec = st._holder(sid)
        part = rec.shot.model_copy(update={"versions": [rec.shot.versions[0].model_copy(update={"state": "final"})]})
        st._save_record(rec.model_copy(update={"shot": part}))
        st.patch_shot(sid, {"revision": st.shot(sid).revision, "versions": [{"id": "v1", "words": "more"}]})


def test_the_camera_and_the_lights(tmp_path: Path):
    cam = StageCamera(id="c", pos=[0, 1.5, 4], target=[0, 1, 0])
    assert screen_x([-1, 1, 0], cam) < 0 < screen_x([1, 1, 0], cam) and screen_x([0, 1, 8], cam) is None and screen_x([30, 1, 0], cam) is None
    lamp = StageObject(id="l", kind="light", name="Light 1", transform={"pos": [0, 6, 0.5]})
    assert light_words(lamp, cam) == "light from above"                       # E23c's white key, unnamed, overhead
    rim = StageObject(id="r", kind="light", name="Window", transform={"pos": [0.2, 1.5, 6]}, light={"colour": "#ffffff", "intensity": 8, "softness": 0.05})
    assert light_words(rim, cam) == "strong hard window light from the front"


def test_the_route_and_the_plate_route(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from loom2.finals import PLATE_LEAD
    from loom2.workspace import Workspace
    from test_graph_parity_d64 import _pin_review
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"), "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    H = {"X-Loom-Token": app.state.services.app.token}
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10}, headers=H)
        n = cl.post("/story/flow/shots", json={"title": "Street", "scene": "new"}, headers=H).json()
        sid = n["shot_id"]
        scn = next(s for s in cl.get("/story/scenes", headers=H).json()["items"] if n["id"] in s["node_ids"])
        assert cl.patch(f"/story/scenes/{scn['id']}", json={"words": "dusk, wet cobbles"}, headers=H).status_code == 200
        r = cl.get(f"/story/shots/{sid}/versions/v1/prompt?purpose=plate", headers=H)
        assert r.status_code == 200 and r.json()["text"] == "dusk, wet cobbles." and r.json()["parts"][0]["source"] == "Scene › Street"
        assert cl.get(f"/story/shots/{sid}/versions/v1/prompt?purpose=poster", headers=H).status_code == 422
        v = cl.get("/story/shots", headers=H).json()["items"]
        v = next(s for s in v if s["id"] == sid)["versions"][0]
        f = _final_on_disk(Workspace(tmp_path / "proj"), v["stage_id"], v["camera_id"], shot=(sid, "v1"))           # a final made for the shot
        q = cl.post(f"/finals/{f.id}/plate", json={"prompt_text": ""}, headers=H)
        assert q.status_code == 200, q.text
        job = next(j for j in cl.get("/jobs", headers=H).json()["items"] if j["id"] == q.json()["job_id"])
        assert job["recipe"]["prompt_text"] == f"{PLATE_LEAD} dusk, wet cobbles." and "room" not in job["recipe"]["prompt_text"]
