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
