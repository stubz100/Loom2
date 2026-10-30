"""D166 (E44, Q32): a head read by its ears before its eyes.

- a side profile (the ears overlapping) is neither front nor away: the guide draws the nose, the near eye and the near ear, and the layer is
  not performed from behind;
- a profile turned away past the side keeps the nose and the near ear, still away;
- a head without its ears or neck in view, a frontal one and a back stay D158's.
"""
import numpy as np


def _head(nose_x: float, ear_r: float, ear_l: float, eye_r: float, eye_l: float) -> list:
    """18 points: the head at y≈20, the neck at (64, 40), the body below, all in view."""
    k = [[64.0, 60.0, 1.0] for _ in range(18)]
    k[0] = [nose_x, 20.0, 1.0]
    k[1] = [64.0, 40.0, 1.0]
    k[2], k[5] = [56.0, 42.0, 1.0], [72.0, 42.0, 1.0]
    k[14], k[15] = [eye_r, 17.0, 1.0], [eye_l, 17.0, 1.0]
    k[16], k[17] = [ear_r, 19.0, 1.0], [ear_l, 19.0, 1.0]
    return k


def test_a_head_is_read_by_its_ears():
    from loom2.finals import head_facing
    side_left = _head(56, 66, 67, 59, 58)                        # walking to the image's left: the ears overlap, the nose ahead (Mira, E44)
    assert head_facing(side_left) == ("side", "left")
    assert head_facing(_head(72, 62, 61, 69, 70)) == ("side", "right")
    turned = _head(72, 74, 64, 66, 62)                           # turned away past the side: the ears half spread, the eyes mirrored (Ines)
    assert head_facing(turned) == ("away_profile", "right")
    assert head_facing(_head(64, 52, 76, 58, 70))[0] == "front"   # the ears a full nose–neck apart, the eyes in order
    assert head_facing(_head(64, 52, 76, 70, 58))[0] == "away"    # a back: the ears apart, the eyes mirrored
    blind = _head(56, 66, 67, 59, 58)
    blind[1][2] = 0.0                                            # no neck in view: D158 decides (the eyes mirrored here)
    assert head_facing(blind)[0] == "away"


def test_the_guide_draws_only_what_a_camera_would_see():
    from loom2.finals import draw_pose, drawn_points
    side = drawn_points(_head(56, 66, 67, 59, 58))
    assert [side[i][2] for i in (0, 15, 17)] == [1.0, 1.0, 1.0] and [side[i][2] for i in (14, 16)] == [0.0, 0.0]   # the near (left) side kept
    turned = drawn_points(_head(72, 74, 64, 66, 62))
    assert [turned[i][2] for i in (0, 16)] == [1.0, 1.0] and [turned[i][2] for i in (14, 15, 17)] == [0.0, 0.0, 0.0]
    back = drawn_points(_head(64, 52, 76, 70, 58))
    assert [back[i][2] for i in (0, 14, 15)] == [0.0, 0.0, 0.0] and [back[i][2] for i in (16, 17)] == [1.0, 1.0]   # D158 as before
    front = _head(64, 52, 76, 58, 70)
    assert drawn_points(front) == front
    img = np.asarray(draw_pose(_head(56, 66, 67, 59, 58), 128, 128))
    assert tuple(img[20, 56]) == (255, 0, 0)                                                 # the side profile's nose is drawn


def test_a_side_profile_is_not_performed_from_behind():
    from loom2.finals import mostly_away
    from loom2.owed import face_fit, head_stats
    walk = [_head(56, 66, 67, 59, 58)] * 10                         # the eyes overlap, mirrored: D158 alone read every frame as away
    assert not mostly_away(walk)
    assert mostly_away([_head(72, 74, 64, 66, 62)] * 10)            # turned away: the back view, as before
    assert head_stats(walk, 128, 128)["facing"] == 1.0 and face_fit(head_stats(walk, 128, 128)) != "away"
