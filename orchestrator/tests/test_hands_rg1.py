"""RG1 (D187, D188; proto01_rig 00 §4, §9, §10): a character's own hands and feet, read from a hand picture and a feet picture.

- the hand's shape from SDPose's 21 points, in palm lengths in the palm's frame (+x toward the thumb, so either hand gives the same shape),
  its fingers' widths from the subject matte (a merged pair read twice as wide is not taken), a read too unsure refused with a sentence;
- the foot's shape from a side view's foot points and the floor (the matte's lowest row);
- points read on a picture shrunk into its canvas come back in its own pixels;
- the pictures' words: the author's own, else the sheet's clauses about the hand or the feet (shared with the client, fixtures/ref_words.json);
- the make (no mention, no sheet, no Look; 1024²), the pick (read at once), the keypoints graph without boxes and with the matte, the
  finisher writing the shape on the body and the points on the version, a failed read said on the version, the Bin's roles.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.hands import (FINGERS, FootShape, HandShape, Hands, fit_foot, fit_hand, part_prompt, sheet_words,  # noqa: E402
                         unshrink)

TESTS = Path(__file__).resolve().parent


def hand_points(shape: HandShape, wrist=(416.0, 330.0), palm_px=100.0, up=(0.0, -1.0), thumb_right=True, conf=0.95) -> list[list[float]]:
    """A hand drawn from a shape: 21 × [x, y, c] in the picture's pixels."""
    ey = np.array(up) / np.linalg.norm(up)
    ex = np.array([-ey[1], ey[0]]) * (1.0 if thumb_right else -1.0)
    W = np.array(wrist)
    pts = [[*W, conf]] + [None] * 20
    chains = {"thumb": (1, 2, 3, 4), "index": (5, 6, 7, 8), "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}
    for name, ch in chains.items():
        f = shape.fingers[name]
        p = W + palm_px * (f.base[0] * ex + f.base[1] * ey)
        a = math.radians(f.angle)
        d = math.cos(a) * ey + math.sin(a) * ex
        pts[ch[0]] = [*p, conf]
        for k, seg in enumerate(f.lengths):
            p = p + palm_px * seg * d
            pts[ch[k + 1]] = [*p, conf]
    return pts


def person(hand: list[list[float]] | None = None, foot: list[list[float]] | None = None, legs: list[list[float]] | None = None) -> dict:
    flat = lambda rows: [float(v) for r in rows for v in r]  # noqa: E731
    body = [[0.0, 0.0, 0.0] for _ in range(18)]
    for i, p in zip((8, 9, 10), legs or []):
        body[i] = p
    return {"pose_keypoints_2d": flat(body), "hand_right_keypoints_2d": flat(hand) if hand else [], "hand_left_keypoints_2d": [],
            "foot_keypoints_2d": flat(foot) if foot else []}


def test_a_hand_read_gives_its_shape_back_whichever_hand_it_is():
    ghoul = HandShape()
    ghoul = ghoul.model_copy(update={"fingers": {n: f.model_copy(update={"lengths": [x * (1.4 if n != "thumb" else 1.1) for x in f.lengths]})
                                                 for n, f in ghoul.fingers.items()}})
    for thumb_right, up in ((True, (0.0, -1.0)), (False, (0.3, -1.0))):        # a right hand upright, a left one leaning
        shape, report, pts = fit_hand([person(hand_points(ghoul, up=up, thumb_right=thumb_right))])
        for n in FINGERS:
            assert shape.fingers[n].lengths == pytest.approx(ghoul.fingers[n].lengths, abs=0.005)
            assert shape.fingers[n].base == pytest.approx(ghoul.fingers[n].base, abs=0.005)
            assert shape.fingers[n].angle == pytest.approx(ghoul.fingers[n].angle, abs=0.2)
        assert shape.palm_width == pytest.approx(math.dist((0.27, 0.96), (-0.38, 0.86)), abs=0.005)
        assert report["middle_palm"] == pytest.approx(0.73 * 1.4, abs=0.005) and report["kept"] == [] and len(pts) == 21
        assert shape.count == 5 and shape.claw == 0.0


def test_the_count_and_the_claws_stay_the_authors():
    base = HandShape(count=4, claw=0.2)
    base.fingers["index"] = base.fingers["index"].model_copy(update={"claw": 0.4})
    shape, _, _ = fit_hand([person(hand_points(HandShape()))], base=base)
    assert shape.count == 4 and shape.claw == 0.2 and shape.fingers["index"].claw == 0.4 and shape.shown() == ["thumb", "index", "middle", "ring"]


def test_a_finger_read_unsurely_keeps_the_last_one_and_an_unsure_hand_is_refused():
    pts = hand_points(HandShape())
    pts[18][2] = 0.1                                                            # the pinky's middle joint not seen
    long = HandShape(fingers={**HandShape().fingers, "pinky": HandShape().fingers["pinky"].model_copy(update={"lengths": [0.5, 0.3, 0.2]})})
    shape, report, _ = fit_hand([person(pts)], base=long)
    assert report["kept"] == ["pinky"] and shape.fingers["pinky"].lengths == [0.5, 0.3, 0.2]
    with pytest.raises(ValueError, match="too unsurely"):
        fit_hand([person(hand_points(HandShape(), conf=0.4))])
    with pytest.raises(ValueError, match="no hand"):
        fit_hand([person()])


def _matte(pts: list[list[float]], widths: dict[str, float], palm_px: float, size=(832, 480), merge: tuple[str, str] | None = None) -> np.ndarray:
    im = Image.new("L", size, 0)
    d = ImageDraw.Draw(im)
    d.polygon([tuple(pts[i][:2]) for i in (0, 1, 5, 9, 13, 17)], fill=255)
    chains = {"thumb": (1, 2, 3, 4), "index": (5, 6, 7, 8), "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16), "pinky": (17, 18, 19, 20)}
    for n, ch in chains.items():
        for k in range(3):
            d.line([tuple(pts[ch[k]][:2]), tuple(pts[ch[k + 1]][:2])], fill=255, width=max(1, round(widths.get(n, 0.2) * palm_px)))
    if merge:                                                                   # two fingers touching: the gap between them filled
        a, b = chains[merge[0]], chains[merge[1]]
        d.polygon([tuple(pts[a[0]][:2]), tuple(pts[a[2]][:2]), tuple(pts[b[2]][:2]), tuple(pts[b[0]][:2])], fill=255)
    return np.asarray(im) > 127


def test_the_fingers_widths_come_from_the_matte():
    pts = hand_points(HandShape(), palm_px=120)
    thin = {"index": 0.13, "middle": 0.14, "ring": 0.13, "pinky": 0.12}            # a ghoul's, E62: 0.12–0.15 palms
    shape, report, _ = fit_hand([person(pts)], _matte(pts, thin, 120))
    for n, w in thin.items():
        assert shape.fingers[n].width == pytest.approx(w, abs=0.025)
    assert shape.fingers["thumb"].width == pytest.approx(1.2 * sorted(thin.values())[2], abs=0.03)
    shape, report, _ = fit_hand([person(pts)], _matte(pts, {"index": 0.2, "middle": 0.2, "ring": 0.2, "pinky": 0.18}, 120, merge=("middle", "ring")))
    assert shape.fingers["middle"].width < 0.3 and shape.fingers["ring"].width < 0.3   # read twice as wide where they touch: not taken


def test_a_side_view_gives_the_foot():
    heel, big, small = [300.0, 400.0, 0.9], [404.0, 412.0, 0.9], [396.0, 410.0, 0.8]   # the toe 12 px lower: the heel raised a little
    legs = [[310.0, 100.0, 0.9], [312.0, 250.0, 0.9], [318.0, 380.0, 0.9]]            # the right hip, knee, ankle
    shape, report, got = fit_foot([person(foot=[[0, 0, 0.1]] * 3 + [big, small, heel], legs=legs)])
    L = math.dist(big[:2], heel[:2])
    assert shape.pitch == pytest.approx(math.degrees(math.atan2(12, 104)), abs=0.1)
    assert shape.heel_up == pytest.approx(12 / L, abs=0.002) and shape.toe_up == 0.0
    assert shape.ankle_up == pytest.approx(32 / L, abs=0.002) and shape.ankle_at == pytest.approx(18 / L, abs=0.002)
    assert shape.length_leg == pytest.approx(L / (math.dist(legs[0][:2], legs[1][:2]) + math.dist(legs[1][:2], legs[2][:2])), abs=0.002)
    assert shape.ball_at == 0.72 and got["foot"][2][:2] == heel[:2]
    mask = np.zeros((480, 832), bool)
    mask[350:430, 290:410] = True                                               # the shoe's sole on the floor at row 429
    shape, _, got = fit_foot([person(foot=[big, small, heel])], mask)
    assert shape.heel_up == pytest.approx((429 - 400) / L, abs=0.002) and got["floor"] == 429 and shape.length_leg is None
    with pytest.raises(ValueError, match="no foot"):
        fit_foot([person()])
    far = [[560.0, 380.0, 0.95], [540.0, 378.0, 0.9], [470.0, 360.0, 0.95]]           # a three-quarter view: the far foot surer and higher
    near = [[404.0, 428.0, 0.6], [396.0, 430.0, 0.5], [300.0, 420.0, 0.9]]
    mask = np.zeros((480, 832), bool)
    mask[340:432, 290:570] = True
    shape, _, got = fit_foot([person(foot=[*far, *near])], mask)
    assert got["foot"][2][:2] == near[2][:2] and shape.heel_up == pytest.approx(11 / math.dist(near[0][:2], near[2][:2]), abs=0.002)   # the near one, on the floor
    _, _, got = fit_foot([person(foot=[*far, [404.0, 428.0, 0.2], [396.0, 430.0, 0.2], [300.0, 420.0, 0.9]])], mask)
    assert got["foot"][2][:2] == far[2][:2]                                         # the near one read too unsurely: the surest


def test_points_read_on_a_shrunk_picture_come_back_in_its_pixels():
    pts = hand_points(HandShape(), wrist=(416, 330))
    small = [[(x - 416) * 0.3 + 416, (y - 240) * 0.3 + 240, c] for x, y, c in pts]   # shrunk to 30 % about the centre of 832 × 480
    back = unshrink([person(small)], [832, 480], 0.3)[0]["hand_right_keypoints_2d"]
    assert np.allclose(np.array(back).reshape(-1, 3)[:, :2], np.array(pts)[:, :2], atol=2.5)


def test_the_pictures_words():
    cases = json.loads((TESTS / "fixtures" / "ref_words.json").read_text(encoding="utf-8"))["cases"]
    for c in cases:
        assert sheet_words(c["appearance"], c["outfit"], c["marks"], "hand") == c["hand"], c
        assert sheet_words(c["appearance"], c["outfit"], c["marks"], "feet") == c["feet"], c
    assert part_prompt("hand", " long bony fingers. ").endswith("studio light: long bony fingers.")
    assert part_prompt("feet", "").startswith("A pair of feet and shoes seen from the side") and ":" not in part_prompt("feet", "")


def test_the_make_plans_the_hand_from_its_own_words(tmp_path: Path):
    from loom2.story import StoryStore, plan_anim_ref
    from test_groups_d34 import _setup
    ws, cat, groups, _ = _setup(tmp_path)
    st = StoryStore(ws)
    p = st.create_profile("Grisk", "character", groups, appearance="a gaunt grey ghoul with long bony fingers and black claws")
    p, gid, _ = st.ensure_candidates(p.id, "v1", groups)
    r, o = plan_anim_ref(p, p.version(), "hand", "full", width=1280, height=720, count=2, group_id=gid)[0]
    assert r["mentions"] == [] and r["style_id"] is None and (r["width"], r["height"]) == (1024, 1024)       # E62 a: no references, no Look
    assert r["prompt_text"].endswith("studio light: a gaunt grey ghoul, long bony fingers and black claws.")                     # what it is leads (the rig)
    assert o["payload"]["side"] == "hand" and o["surface"] == "anim_ref"
    p = st.patch_profile(p.id, {"versions": [{"id": "v1", "hand_words": "four long fingers"}]})
    r, _ = plan_anim_ref(p, p.version(), "hand", "full", width=1280, height=720, count=1, group_id=gid)[0]
    assert r["prompt_text"].endswith(": four long fingers.")
    r, _ = plan_anim_ref(p, p.version(), "feet", "full", width=1280, height=720, count=1, group_id=gid)[0]
    assert r["prompt_text"].startswith("A pair of feet and shoes") and r["mentions"] == []
    prop = st.create_profile("Cup", "prop", groups)
    with pytest.raises(ValueError, match="only a character"):
        plan_anim_ref(prop, prop.version(), "hand", "full", width=64, height=64, count=1, group_id=gid)


def test_the_keypoints_graph_without_boxes_with_the_shrunk_read_and_the_matte(tmp_path: Path, object_info: dict):
    from loom2.engine.graphs import compile_recipe, recipe_weights
    from loom2.recipes import Keypoints
    from loom2.roster import Roster
    roster = Roster(tmp_path, [], "full")
    for folder, name in (("checkpoints", "sdpose_wholebody_fp16.safetensors"), ("diffusion_models", "rt_detr_v4-x-hgnet_fp16.safetensors"),
                         ("background_removal", "BiRefNet-general.safetensors")):
        (tmp_path / folder).mkdir(exist_ok=True); (tmp_path / folder / name).write_bytes(b"x")
    roster.scan()
    r = Keypoints(asset_id="a", boxes=False, inset=0.3, matte=True)
    c = compile_recipe(r, roster, object_info, 0, "loom2/j", inputs={"image": "0000.png", "read": "000000.png"})
    kinds = {k: n["class_type"] for k, n in c.graph.items()}
    assert "RTDETR_detect" not in kinds.values() and "bboxes" not in c.graph["5"]["inputs"]
    assert c.graph["5"]["inputs"]["image"] == ["30", 0] and c.graph["30"]["inputs"]["image"] == "000000.png"   # SDPose reads the shrunk one
    assert c.graph["41"]["inputs"]["image"] == ["3", 0] and kinds["43"] == "SaveImage"                            # the matte the picture itself
    assert c.problems == [], c.problems
    assert "birefnet" in recipe_weights(r) and "birefnet" not in recipe_weights(Keypoints(asset_id="a"))


@pytest.mark.asyncio
async def test_a_picked_hand_picture_is_read_and_its_shape_lands_on_the_body(tmp_path: Path, object_info: dict):
    from loom2.groups import GroupStore
    from loom2.story import StoryStore, queue_part_fit
    from test_groups_d34 import _png
    from test_lifecycle import Rig
    rig = Rig(tmp_path, object_info)
    try:
        groups = rig.queue.groups = GroupStore(rig.ws, rig.catalogue)
        st = StoryStore(rig.ws)
        pic = rig.catalogue.ingest_file(_png(tmp_path / "hand.png")).id
        p = st.create_profile("Grisk", "character", groups, appearance="a ghoul")
        p = st.set_anim_ref(p.id, "v1", "hand", pic)
        ghoul = HandShape()
        ghoul = ghoul.model_copy(update={"fingers": {n: f.model_copy(update={"lengths": [x * 1.4 for x in f.lengths]}) if n != "thumb" else f
                                                     for n, f in ghoul.fingers.items()}})
        true = hand_points(ghoul, wrist=(416, 330), palm_px=60)
        rig.fake.people = [person([[(x - 416) * 0.3 + 416, (y - 240) * 0.3 + 240, c] for x, y, c in true])]   # read on the picture shrunk to 30 %
        rig.fake.matte = Image.fromarray((_matte(true, {"index": 0.14, "middle": 0.14, "ring": 0.13, "pinky": 0.12}, 60) * 255).astype(np.uint8)).convert("RGB")
        (tmp_path / "models" / "background_removal").mkdir(parents=True, exist_ok=True)              # the subject matte's weight in the fake tree
        (tmp_path / "models" / "background_removal" / "BiRefNet-general.safetensors").write_bytes(b"x" * 16)
        rig.roster.scan()
        rig.queue.load()
        await rig.queue.start()
        job = queue_part_fit(rig.queue, p, "v1", "hand")
        assert job.recipe["boxes"] is False and job.recipe["inset"] == 0.3 and job.recipe["matte"] is True
        done = await rig.wait(job.id)
        assert done.status == "done", done.error
        v = st.profile(p.id).version("v1")
        hs = v.body.hand_shape
        assert isinstance(hs, Hands) and hs.left is None                                          # Q2: mirrored
        assert sum(hs.right.fingers["middle"].lengths) == pytest.approx(0.73 * 1.4, abs=0.03)       # E62's 30 % read, mapped back
        assert hs.right.fingers["middle"].width == pytest.approx(0.14, abs=0.03)
        assert v.hand_points["from"] == pic and len(v.hand_points["hand"]) == 21 and v.hand_note is None
        assert v.body.height_m == 1.75 and v.body_fit_from is None                                # nothing else of the body moved
        assert not list((rig.app.state_dir / "engine_out").rglob("*.png"))                        # the matte read, then gone
        rig.fake.people = [person()]                                                              # a picture with no hand in it
        done = await rig.wait(queue_part_fit(rig.queue, st.profile(p.id), "v1", "hand").id)
        assert done.status == "failed" and "no hand" in (done.error or "")
        v = st.profile(p.id).version("v1")
        assert v.hand_note and "no hand" in v.hand_note and v.body.hand_shape == hs                 # said on the version, the last read kept
        st.set_anim_ref(p.id, "v1", "hand", None)
        assert st.profile(p.id).version("v1").hand_note is None                                   # the note was about that picture
    finally:
        await rig.close()


def test_the_pick_route_reads_the_picture_and_the_bin_names_it(tmp_path: Path):
    from fastapi.testclient import TestClient
    from loom2.api import create_app
    from loom2.config import AppState
    from test_graph_parity_d64 import _pin_review
    from test_groups_d34 import _png
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": "full"})
    _pin_review().full_roster(tmp_path / "models")
    app = create_app(state)
    with TestClient(app, headers={"X-Loom-Token": app.state.services.app.token}) as cl:
        assert cl.post("/project", json={"path": str(tmp_path / "p"), "name": "p", "size_cap_gb": 10}).status_code == 200
        pic = app.state.services.catalogue.ingest_file(_png(tmp_path / "h.png")).id
        p = cl.post("/story/profiles", json={"name": "Grisk", "cls": "character", "appearance": "a ghoul"}).json()
        assert cl.post(f"/story/profiles/{p['id']}/versions/v1/parts/hand/fit").status_code == 422               # no hand picture yet
        r = cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "hand", "asset_id": pic})
        assert r.status_code == 200 and r.json()["versions"][0]["hand_ref_asset_id"] == pic
        jobs = [x for x in cl.get("/jobs").json()["items"] if x["origin"] and x["origin"]["surface"] == "hand_fit"]
        assert len(jobs) == 1 and jobs[0]["recipe"] == {"kind": "keypoints", "asset_id": pic, "model_id": "sdpose-wholebody", "boxes": False, "inset": 0.3, "matte": True}
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/parts/hand/fit")
        assert r.status_code == 200 and r.json()["asset_id"] == pic
        side = app.state.services.catalogue.ingest_file(_png(tmp_path / "s.png")).id                 # D190: a side view is not the feet picture by itself
        cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "side", "asset_id": side})
        feet = lambda: [x for x in cl.get("/jobs").json()["items"] if x["origin"] and x["origin"]["surface"] == "feet_fit"]   # noqa: E731
        assert not feet() and cl.post(f"/story/profiles/{p['id']}/versions/v1/parts/feet/fit").status_code == 422
        cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "feet", "asset_id": side})   # picked as the feet picture: read whole
        assert len(feet()) == 1 and feet()[0]["recipe"]["asset_id"] == side and feet()[0]["recipe"]["inset"] == 1.0
        cl.put(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "feet", "asset_id": None})
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "feet", "count": 1, "words": "black riding boots", "model_id": "zimage-bf16"})
        assert r.status_code == 200, r.text
        made = [x for x in cl.get("/jobs").json()["items"] if x["origin"] and x["origin"]["surface"] == "anim_ref"]
        assert [x["recipe"]["model_id"] for x in made] == ["zimage-bf16"]                          # D190: the card's model, not Klein behind it
        r = cl.post(f"/story/profiles/{p['id']}/versions/v1/anim-ref", json={"side": "hand", "count": 1})
        made = [x for x in cl.get("/jobs").json()["items"] if x["origin"] and x["origin"]["surface"] == "anim_ref"]
        assert sorted(x["recipe"]["model_id"] for x in made) == ["klein-9b", "zimage-bf16"]       # no card named: the clay-reference model
        v = cl.get(f"/story/profiles/{p['id']}").json()["versions"][0]
        assert v["feet_words"] == "black riding boots"
        caps = cl.get("/capabilities").json()["story"]["references"]["character"]
        assert caps["hand"].startswith("A right hand alone") and caps["feet"].startswith("A pair of feet")
        from loom2.bins import uses_of
        assert {"kind": "version", "id": p["id"], "version": "v1", "name": "Grisk v1", "role": "hand_picture"} in uses_of(app.state.services.require_project()[0], pic)
        prop = cl.post("/story/profiles", json={"name": "Cup", "cls": "prop"}).json()
        assert cl.put(f"/story/profiles/{prop['id']}/versions/v1/anim-ref", json={"side": "hand", "asset_id": pic}).status_code == 422
