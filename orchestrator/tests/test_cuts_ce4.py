"""CE4 (proto01_animate 30 §5, D126, O6): colour on a FilmCraft cut, on tests/fake_filmcraft.py (the real binary on the rig) — FilmCraft's
presets and looks listed from the engine, *Grade the scene* (an adjustment layer on the top Grade track over the run of V1's shots at the
chosen shot's place, named after it; asked again it is the same grade), a grade's preset, values (brought inside their ranges), look and a
LUT file, a shot matched to another, reset, and the cut's undo."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.clips import ClipStore  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_filmcraft.py"


def test_grades_matches_and_the_scene(tmp_path: Path):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full", "filmcraft": {"cli": str(FAKE), "timeout_s": 20.0}})
    app = create_app(state)
    with TestClient(app) as cl:
        cl.post("/project", json={"path": str(tmp_path / "proj"), "name": "S", "size_cap_gb": 10})
        ws = Workspace(tmp_path / "proj")
        cs, st = ClipStore(ws), StoryStore(ws)
        frames = []
        for i in range(24):
            f = tmp_path / f"f{i}.png"
            Image.new("RGB", (32, 24), (180, 90, 40)).save(f)
            frames.append(f)
        clip = cs.encode_proxy(cs.create(frames, model_id="wan22-i2v-high-fp8", prompt="s", seed=1, fps=24, start_asset_id="ast_x"))
        groups = GroupStore(ws, app.state.services.catalogue)
        gate = st.create_profile("Gate", "place", groups)
        yard = st.create_profile("Yard", "place", groups)
        nodes = []
        for title, place in (("In", gate), ("Through", gate), ("Out", yard)):
            n = st.create_node("dialogue", title=title, with_shot=False)
            nodes.append(st.patch_node(n.id, {"revision": n.revision, "place_id": place.id}))
        tl = cl.post("/timelines", json={"name": "Colour", "fps": 24, "w": 64, "h": 36}).json()
        tl = cl.put(f"/timelines/{tl['id']}", json={**tl, "clips": [{"id": str(k), "clip_id": clip.id, "in": 0, "out": 24, "node_id": n.id} for k, n in enumerate(nodes)],
                                                    "overlaps": [0, 0, 0]}).json()
        base = f"/timelines/{tl['id']}"
        looks = cl.get("/colour/looks").json()
        assert [p["name"] for p in looks["presets"]][:1] == ["Golden Dusk"] and [x["ref"] for x in looks["looks"]] == ["builtin:look-teal-orange", "builtin:look-night"]
        v1 = cl.get(f"{base}/tracks").json()["video"][0]["items"]
        assert [i["grade"] for i in v1] == [None, None, None]
        # the scene: the run of shots at the Gate — the first two — under one adjustment layer on the top Grade track
        r = cl.post(f"{base}/grade/scene", json={"revision": cl.get(base).json()["revision"], "clip": v1[1]["id"]})
        assert r.status_code == 200, r.text
        res, tracks = r.json()["results"][0], r.json()["tracks"]
        assert res["made"] and res["shots"] == 2
        grade_track = tracks["video"][-1]
        adj = grade_track["items"][0]
        assert grade_track["name"] == "Grade" and adj["kind"] == "adjustment" and adj["name"] == "Grade · Gate"
        assert (adj["start"], adj["duration"]) == (v1[0]["start"], v1[0]["duration"] + v1[1]["duration"]) and adj["grade"] is None   # as shot until graded
        again = cl.post(f"{base}/grade/scene", json={"clip": v1[0]["id"]}).json()["results"][0]
        assert again == {"clip": adj["id"], "made": False, "shots": 2}
        assert cl.post(f"{base}/grade/scene", json={"clip": adj["id"]}).status_code == 422                 # a scene comes from a V1 shot
        # its grade: a preset, values inside their ranges, a look, a LUT file
        g = lambda r: next(i for t in r.json()["tracks"]["video"] for i in t["items"] if i["id"] == adj["id"])["grade"]   # noqa: E731
        r = cl.post(f"{base}/grade", json={"clip": adj["id"], "preset": "Golden Dusk"})
        assert g(r)["values"]["temperature"] == 35.0
        r = cl.post(f"{base}/grade", json={"clip": adj["id"], "values": {"exposure": 9, "contrast": -20}, "look": "builtin:look-teal-orange"})
        assert (g(r)["values"]["exposure"], g(r)["values"]["contrast"], g(r)["look"], g(r)["values"]["temperature"]) == (5.0, -20.0, "builtin:look-teal-orange", 35.0)
        r = cl.post(f"{base}/grade", json={"clip": adj["id"], "preset": "Steel Blue"})                   # a preset replaces the grade: one Lumetri, not two
        lum = [e for t in __import__("json").loads((tmp_path / "proj" / "timelines" / tl["id"] / "cut.fcproj").read_text(encoding="utf-8"))["project"]["items"].values()
               if "Sequence" in t["kind"] for tr in t["kind"]["Sequence"]["video_tracks"] for i in tr["items"] if i["id"] == adj["id"] for e in i["effects"] if e["effect"] == "lumetri"]
        assert len(lum) == 1 and (g(r)["values"]["temperature"], g(r)["values"]["exposure"], g(r)["look"]) == (-40.0, 0.0, "")
        cube = tmp_path / "Warm.cube"
        cube.write_text("LUT_3D_SIZE 2\n0 0 0\n1 0 0\n0 1 0\n1 1 0\n0 0 1\n1 0 1\n0 1 1\n1 1 1\n", encoding="utf-8")
        r = cl.post(f"{base}/grade", json={"clip": adj["id"], "look_file": str(cube)})
        assert g(r)["look"].startswith("lib:")
        assert cl.post(f"{base}/grade", json={"clip": adj["id"], "values": {"hue": 3}}).status_code == 422
        # a shot matched to another: its own Lumetri, the wheels moved
        r = cl.post(f"{base}/grade", json={"clip": v1[2]["id"], "match": v1[0]["id"]})
        assert r.json()["results"][0]["match"] == {"before": 0.6, "after": 0.2}
        m = next(i for i in r.json()["tracks"]["video"][0]["items"] if i["id"] == v1[2]["id"])["grade"]
        assert m["matched"] is True
        # reset, and the cut's undo brings it back
        r = cl.post(f"{base}/grade", json={"clip": v1[2]["id"], "reset": True}).json()
        assert next(i for i in r["tracks"]["video"][0]["items"] if i["id"] == v1[2]["id"])["grade"] is None
        r = cl.post(f"{base}/undo", json={"revision": r["timeline"]["revision"]}).json()
        assert next(i for i in r["tracks"]["video"][0]["items"] if i["id"] == v1[2]["id"])["grade"]["matched"] is True
