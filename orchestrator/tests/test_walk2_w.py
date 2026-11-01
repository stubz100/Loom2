"""The walkthrough-2 register's fixes (proto01_UI2 12): W21 a face's own Fill seed, W65 a letterboxed set picture found.

- W21: one seed for every face gave the pier's four backdrop panels the identical picture; each face now gets its own from the chain's;
- W65: the Look's "cinematic … film grain" letterboxed the set pictures and the bars were projected into every plate; the bars are found
  (a band of near-black, flat rows from the top and the bottom), a dark picture or a dark sky alone is not a bar.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_each_face_has_its_own_fill_seed():
    from loom2.place_sets import face_seed
    faces = ["backdrop_0", "backdrop_1", "backdrop_2", "backdrop_3", "floor"]
    seeds = [face_seed(1234, f) for f in faces]
    assert len(set(seeds)) == len(faces) and all(0 < s < 2**31 for s in seeds)
    assert seeds == [face_seed(1234, f) for f in faces]                              # the chain's seed still reproduces the run


def _picture(h: int = 360, w: int = 640, top: int = 0, bottom: int = 0, sky: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(0)
    im = rng.integers(60, 200, (h, w, 3)).astype(np.uint8)                           # a busy scene
    if sky is not None:
        im[:sky] = rng.integers(8, 40, (sky, w, 3))                                 # a night sky: dark, not flat
    im[:top] = rng.integers(0, 6, (top, w, 3))                                       # bars: near black, flat (JPEG-ish noise)
    if bottom:
        im[h - bottom:] = rng.integers(0, 6, (bottom, w, 3))
    return im


def test_a_letterboxed_picture_is_found(tmp_path: Path):
    from loom2.place_sets import letterbox
    from loom2.routes.story import _bars
    assert letterbox(_picture(top=45, bottom=45)) == (45, 45)
    assert letterbox(_picture()) == (0, 0)
    assert letterbox(_picture(top=4)) == (0, 0)                                      # a dark seam is not a bar
    assert letterbox(_picture(sky=120)) == (0, 0)                                    # a night sky is not a bar
    veiled = _picture()
    veiled[:30] = (veiled[:30] * 0.4).astype(np.uint8)                                # a semi-transparent bar (the street's): the picture shows through
    assert letterbox(veiled) == (30, 0)
    Image.fromarray(_picture(1080, 1920, top=138, bottom=138)).save(tmp_path / "set.jpg", quality=88)
    top, bottom = _bars(tmp_path / "set.jpg")
    assert abs(top - 138) <= 8 and abs(bottom - 138) <= 8                            # in the picture's own pixels


def test_a_scene_at_a_place_starts_without_the_benchs_scale_figure(tmp_path: Path):
    """W35: a new scene at a World place gets the place's built set, not the bench's unbound "1.75 m for scale" mannequin as cast."""
    from loom2.catalogue import Catalogue
    from loom2.groups import GroupStore
    from loom2.stages import PlaceSet, StageStore
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    store = StoryStore(ws)
    pier = store.create_profile("Harbour pier", "place", GroupStore(ws, Catalogue(ws)))
    store.set_place_set(pier.id, "v1", PlaceSet(kind="ground", sizes={}, faces=[]))
    st = StageStore(ws).scene_stage("Arrival", store.profile(pier.id))
    assert [o.kind for o in st.objects] == ["set"] and st.objects[0].profile_id == pier.id


def test_a_final_shot_puts_its_version_on_the_clay_route():
    """W39: the method card said Final shot while the Recipe said Image to video — a layered final moves an Image to video or stage
    template to clay (by its figures); a Dialogue, a one-pass method or no final leaves it."""
    from types import SimpleNamespace as N

    from loom2.shot_recipe import clay_template
    fig = N(kind="figure")
    one, two = N(layers=[fig, N(kind="prop")]), N(layers=[fig, fig])
    v = lambda t, m=None: N(recipe=N(template=t) if t else None, method=m)  # noqa: E731
    assert clay_template(v("i2v"), one) == "clay1" and clay_template(v("stage"), two) == "clay2" and clay_template(v(None), one) == "clay1"
    assert clay_template(v("dialogue"), one) is None and clay_template(v("i2v", "one_pass"), one) is None and clay_template(v("i2v"), None) is None


def test_an_exported_line_is_named_by_its_shot_and_words(tmp_path: Path):
    """W63: the Resolve export named a voiced line by its asset's file ("ast_….wav"); it is the shot's line by its words now."""
    from types import SimpleNamespace as N

    from loom2.story import StoryStore
    from loom2.timelines import TimelineClip, story_lookup
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    st = StoryStore(ws)
    n = st.create_node("shot", "The seal", 0, 0)
    st.patch_node(n.id, {"lines": [{"text": "You knew my father,  didn't you?", "audio_asset_id": "ast_v1"}]})
    cat = N(get=lambda aid: N(id=aid, path="media/ast_v1.wav", duration_s=1.5) if aid == "ast_v1" else None)
    _, _, audio_of = story_lookup(ws, cat)
    cue = audio_of(TimelineClip(id="c1", clip_id="clp_1", out=24, node_id=n.id))[0]
    assert cue["name"] == "The seal · line 1 · You knew my father, didn't you?" and cue["path"].endswith("ast_v1.wav")


def test_a_reference_make_leaves_the_look_out(tmp_path: Path):
    """D176 (W8): an A-pose or a prop's view is made on a plain studio ground without the Look's style; a place's set picture keeps it."""
    from loom2.catalogue import Catalogue
    from loom2.groups import GroupStore
    from loom2.story import StoryStore, plan_anim_ref
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    st, gs = StoryStore(ws), GroupStore(ws, Catalogue(ws))
    ines, quay = st.create_profile("Ines", "character", gs), st.create_profile("Quay", "place", gs)
    plan = lambda p: plan_anim_ref(p, p.version("v1"), "front", "full", width=640, height=960, count=1, group_id="g", style_id="sty_noir")[0][0]  # noqa: E731
    assert plan(ines)["style_id"] is None and plan(quay)["style_id"] == "sty_noir"


def test_a_coverage_shot_goes_stale_only_with_what_it_reads(tmp_path: Path):
    """D178 (W56): any edit to a shared stage staled every shot of the scene. Two shots on one stage, each its own camera: moving the second's
    camera stales the second only; moving a figure stales both; a version from before the stamps reads the revision."""
    from loom2.stages import StageStore
    from loom2.story import StoryStore, copy_camera, version_stage_stale
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    st, stages = StoryStore(ws), StageStore(ws)
    stg = stages.create("Pier")
    stg = stages.put(stg.id, {"revision": stg.revision, "objects": [{"id": "fig_i", "kind": "mannequin", "name": "Ines", "transform": {"pos": [0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}}]})
    stg, cam2 = copy_camera(ws, stg.id, stg.cameras[0].id)
    a, b = st.create_node("shot", "Wide", 0, 0), st.create_node("shot", "Close", 300, 0)
    st.set_source(a.shot_id, "v1", stg.id, stg.cameras[0].id, stg.revision)
    st.set_source(b.shot_id, "v1", stg.id, cam2.id, stg.revision)
    va, vb = st.shot(a.shot_id).version(), st.shot(b.shot_id).version()
    assert va.stage_stamps and va.stamps_revision == stg.revision and vb.stage_stamps
    moved = stages.put(stg.id, {"revision": stg.revision, "cameras": [c.model_dump() if c.id != cam2.id else {**c.model_dump(), "pos": [3.0, 1.6, 4.0]} for c in stg.cameras]})
    assert not version_stage_stale(va, moved) and version_stage_stale(vb, moved)                 # the other shot's camera: not Wide's business
    walked = stages.put(moved.id, {"revision": moved.revision, "objects": [{**moved.objects[0].model_dump(), "transform": {"pos": [1.0, 0, 0], "rot": [0, 0, 0], "scale": [1, 1, 1]}}]})
    assert version_stage_stale(va, walked) and version_stage_stale(vb, walked)
    old = va.model_copy(update={"stage_stamps": None, "stamps_revision": None})
    assert version_stage_stale(old, moved)                                                    # stamped before D178: the revision, as before


def test_a_part_filled_face_continues_the_seen_tone():
    """D179 (W22, E55): a fill painted paler than the part the picture saw is matched to it across the seam; a face filled whole is left."""
    from loom2.place_sets import seam_match
    from loom2.tone import lab_stats, srgb_to_lab
    rng = np.random.default_rng(1)
    rgb = np.zeros((120, 200, 3), np.uint8)
    rgb[:, :160] = np.clip(rng.normal((40, 90, 95), 6, (120, 160, 3)), 0, 255)          # the seen part: dark teal
    rgb[:, 160:] = np.clip(rng.normal((150, 170, 175), 6, (120, 40, 3)), 0, 255)        # the fill: a paler sky
    filled = np.zeros((120, 200), bool)
    filled[:, 160:] = True
    out = seam_match(rgb, filled)
    lab = srgb_to_lab(out)
    seen, fill = lab_stats(lab, ~filled & (np.arange(200) >= 148)[None, :])[0], lab_stats(lab, filled & (np.arange(200) < 172)[None, :])[0]
    assert float(np.linalg.norm(seen - fill)) < 2.0                                          # the step closed (E55: 15–24 → about 1)
    assert (out[:, :160] == rgb[:, :160]).all()                                              # the seen part untouched
    assert (seam_match(rgb, np.ones((120, 200), bool)) == rgb).all()                         # filled whole: nothing to match
