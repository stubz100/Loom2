"""D196 (the author on char01, 2026-11-08: "the clay shell is still disproportionate to the original model … distorted hands and feet"): a
shell's skeleton stands in its shoes. The shell is placed by its picture (the nose, the soles); the skeleton was fitted to the picture's
ratios over the nose → ankle height with the bare dummy's ankle 4 cm over the floor, where SDPose reads a booted ankle 16 cm over the soles —
everything under the nose came out 9 % long against the shell. The sole is solved from the shell's figure box after the fit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.body import SOLE_MAX, Body, _nose_ankle, body_points, dummy_ratios, fit_body, reference_ratios, sole_of  # noqa: E402

from fake_comfy import fake_person  # noqa: E402

TOP, H = 40.0, 400.0                                                           # fake_person's nose and its nose → ankles height (px)


def points(soles_below_ankles: float = 50.0) -> tuple[dict, list]:
    """A fitted picture's points and the shell's figure box: the soles `soles_below_ankles` px under the ankles."""
    p = fake_person(h=H, top=TOP)
    pts = body_points(p, [832, 600])
    return pts, [300, 10, 530, int(TOP + H + soles_below_ankles), 832, 600]


def test_the_sole_puts_the_dummys_ankles_where_the_picture_has_them():
    pts, box = points(50.0)
    b = fit_body(reference_ratios(fake_person(h=H, top=TOP)))[0]
    s = sole_of(pts, box, b)
    assert s > 0.1                                                             # 50 px of 400: an eighth of the height under the ankles
    nose_y, ankle_y = _nose_ankle(b.model_copy(update={"sole": s}))
    assert ankle_y / (nose_y - ankle_y) == pytest.approx(50.0 / H, abs=2e-3)  # the ankles over the floor as the picture's over its soles


def test_no_ratio_moves_with_the_sole():
    assert dummy_ratios(Body(sole=0.12)) == pytest.approx(dummy_ratios(Body()))
    a = fit_body(reference_ratios(fake_person()))[0]
    b = fit_body(reference_ratios(fake_person()), Body(sole=0.12))[0]
    assert {k: getattr(b, k) for k in ("legs", "arms", "torso", "neck", "head", "knee", "elbow")} == {k: getattr(a, k) for k in ("legs", "arms", "torso", "neck", "head", "knee", "elbow")}
    assert b.sole == 0.12                                                      # the fit keeps it (a refit of the same picture)


def test_the_sole_needs_the_box_and_the_ankles():
    pts, box = points(50.0)
    b = Body()
    assert sole_of(pts, None, b) == 0.0 and sole_of(None, box, b) == 0.0
    hidden = {**pts, "pose": [list(r) for r in pts["pose"]]}
    hidden["pose"][10][2] = 0.1                                                # an ankle not seen
    assert sole_of(hidden, box, b) == 0.0
    assert sole_of(*points(-5.0), b) == 0.0                                    # a box ending over the ankles: nothing under them
    assert sole_of(*points(30.0), b) < sole_of(*points(60.0), b) <= SOLE_MAX
    assert sole_of(*points(2000.0), b) == SOLE_MAX
    half = {**pts, "canvas": [416, 300]}                                       # points read on a picture half the matte's size
    half["pose"] = [[x / 2, y / 2, c] for x, y, c in pts["pose"]]
    assert sole_of(half, box, b) == pytest.approx(sole_of(pts, box, b), abs=1e-3)


def test_the_shell_gives_its_version_the_sole_of_its_picture(tmp_path: Path):
    from loom2.catalogue import Catalogue
    from loom2.groups import GroupStore
    from loom2.story import StoryStore, with_sole
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    cat = Catalogue(ws)
    store = StoryStore(ws)
    who = store.create_profile("Mara", "character", GroupStore(ws, cat))
    pts, box = points(50.0)
    store.set_fitted_body(who.id, who.current, Body(), "ast_ref", pts)
    v = store.set_shell(who.id, who.current, "ast_shell", "ast_ref", box).version()
    assert v.body.sole > 0.1
    assert store.set_shell(who.id, who.current, "ast_other", "ast_other_ref", box).version().body.sole == 0.0   # a shell of another picture
    store.set_shell(who.id, who.current, "ast_shell", "ast_ref", box)
    assert store.set_shell(who.id, who.current, None, None).version().body.sole == 0.0                       # cleared
    assert with_sole(Body(sole=0.1), pts, "ast_ref", "ast_ref", None).sole == 0.0                             # a shell made before figure boxes
    cat.close()
