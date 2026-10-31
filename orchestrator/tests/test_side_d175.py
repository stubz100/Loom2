"""D175 (M13, E54): a character seen from the side is performed from its side view.

- a layer whose head reads as a side profile on most frames faces the way its nose points; one mostly front or away does not;
- the reference: the back view first when mostly away (D158), else the side view when mostly in profile and the version has one,
  mirrored when the layer faces right (the side view is made facing left), else the front;
- the placed reference is mirrored on demand; the version's side slot, its sentence, and a prop refused a side view.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_profile_d166 import _head  # noqa: E402

LEFT = _head(56, 66, 67, 59, 58)                  # a side profile, the nose to the image's left (Mira, E44)
RIGHT = _head(72, 62, 61, 69, 70)
FRONT = _head(64, 52, 76, 58, 70)
BACK = _head(64, 52, 76, 70, 58)


def test_a_layer_mostly_in_profile_faces_the_way_its_nose_points():
    from loom2.finals import mostly_side
    assert mostly_side([LEFT] * 8 + [FRONT] * 2) == "left"
    assert mostly_side([RIGHT] * 6 + [LEFT] * 2 + [FRONT]) == "right"
    assert mostly_side([LEFT] * 4 + [FRONT] * 4) is None                     # half is not most
    assert mostly_side([BACK] * 9) is None and mostly_side([]) is None


def test_the_reference_a_layer_is_performed_from():
    from loom2.finals import reference_for
    v = SimpleNamespace(anim_ref_asset_id="front", anim_ref_back_asset_id="back", anim_ref_side_asset_id="side")
    assert reference_for(v, [BACK] * 9) == ("back", True, None, False)        # D158 first
    assert reference_for(v, [LEFT] * 9) == ("side", False, "left", False)
    assert reference_for(v, [RIGHT] * 9) == ("side", False, "right", True)    # made facing left: mirrored
    assert reference_for(v, [FRONT] * 9) == ("front", False, None, False)
    plain = SimpleNamespace(anim_ref_asset_id="front", anim_ref_back_asset_id=None, anim_ref_side_asset_id=None)
    assert reference_for(plain, [LEFT] * 9) == ("front", False, None, False)  # no side view: the front serves, as before
    assert reference_for(plain, [BACK] * 9) == ("front", True, None, False)   # no back view: the front, with the words from behind


def test_the_placed_reference_is_mirrored(tmp_path: Path):
    from loom2.finals import place_reference
    ref = np.full((360, 640, 3), 200, np.uint8)                               # a plain light ground, a figure with a mark on its left
    ref[60:320, 300:340] = (40, 40, 40)
    ref[60:120, 300:312] = (220, 30, 30)
    Image.fromarray(ref).save(tmp_path / "ref.png")
    kp = [[0.0, 0.0, 0.0] for _ in range(18)]
    kp[0], kp[8], kp[11], kp[10], kp[13] = [240, 100, 1], [236, 300, 1], [244, 300, 1], [236, 560, 1], [244, 560, 1]
    assert place_reference(tmp_path / "ref.png", kp, 480, 640, tmp_path / "a.png")
    assert place_reference(tmp_path / "ref.png", kp, 480, 640, tmp_path / "b.png", mirror=True)
    a, b = np.asarray(Image.open(tmp_path / "a.png"), np.int16), np.asarray(Image.open(tmp_path / "b.png"), np.int16)
    red = lambda im: np.argwhere((im[..., 0] > 150) & (im[..., 1] < 90))[:, 1].mean()  # noqa: E731
    assert red(a) < 240 < red(b)                                              # the mark swapped sides


def test_the_side_view_slot_and_its_words(tmp_path: Path):
    from loom2.groups import GroupStore
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore, anim_ref_sentence, plan_anim_ref
    from loom2.workspace import Workspace
    s = anim_ref_sentence("character", "side")
    assert "seen from the side in profile, facing left" in s and "anything that hangs behind fully visible" in s
    ws = Workspace.create(tmp_path / "p", name="P", size_cap_gb=10)
    cat = Catalogue(ws)
    store = StoryStore(ws)
    mira = store.create_profile("Mira", "character", GroupStore(ws, cat))
    crate = store.create_profile("Crate", "prop", GroupStore(ws, cat))
    p = store.set_anim_ref(mira.id, "v1", "side", "ast_side")
    assert p.version("v1").anim_ref_side_asset_id == "ast_side" and p.version("v1").anim_ref_asset_id is None
    with pytest.raises(ValueError, match="side view"):
        store.set_anim_ref(crate.id, "v1", "side", "ast_x")
    with pytest.raises(ValueError, match="side view"):
        plan_anim_ref(crate, crate.version("v1"), "side", "full", width=1280, height=720, count=1, group_id="g")
