"""PE3: Poisson paste-back (D47), match colour to surroundings (D48), result layers with a mask (D47), Colour to Alpha (D49)."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from loom2 import compose, edit_ai, poisson, tone
from loom2.documents import Document, OpenDocument
from loom2.queue import JobQueue
from loom2.recipes import Inpaint

rng = np.random.default_rng(11)


def _reference_membrane(v: np.ndarray, unknown: np.ndarray) -> np.ndarray:
    v = v.copy()
    v[unknown] = 0
    h, w = unknown.shape
    n = poisson._counts(h, w)
    for _ in range(60000):
        nv = np.where(unknown[..., None], poisson._neighbours(v) / n, v)
        if np.abs(nv - v).max() < 1e-9:
            return nv
        v = nv
    return v


def test_membrane_is_within_an_8bit_step_of_a_converged_solve_on_smooth_data():
    from loom2.matting import gaussian_blur
    h, w = 120, 160
    yy, xx = np.mgrid[0:h, 0:w]
    unknown = ((yy - 60) / 45) ** 2 + ((xx - 80) / 60) ** 2 < 1
    v = gaussian_blur(rng.random((h, w)), 2)[..., None]
    got = poisson.solve_membrane(np.where(unknown[..., None], 0.0, v), unknown)
    assert np.abs(got - _reference_membrane(v, unknown)).max() * 255 < 1.0


def test_seamless_clone_removes_a_constant_offset_and_keeps_texture():
    h, w = 90, 120
    dst = rng.integers(60, 180, (h, w, 3), dtype=np.uint8)
    texture = rng.integers(-20, 20, (h, w, 3))
    src = np.clip(dst.astype(int) + 40 + texture, 0, 255).astype(np.uint8)    # brighter (drift) and with its own texture
    mask = np.zeros((h, w), bool)
    mask[20:70, 30:90] = True
    out = poisson.seamless_clone(src, dst, mask).astype(int)
    assert (out[~mask] == dst[~mask]).all()                                     # outside: the plate
    inside = out[30:60, 40:80] - (dst[30:60, 40:80].astype(int) + texture[30:60, 40:80])
    assert abs(float(inside.mean())) < 4                                        # the +40 drift is gone, the texture stays


def test_lab_round_trip_and_match_colour():
    img = rng.integers(0, 256, (40, 50, 3), dtype=np.uint8)
    assert np.abs(tone.lab_to_srgb(tone.srgb_to_lab(img)).astype(int) - img).max() <= 1
    ref = np.clip(img.astype(int) * 0.8 + 20, 0, 255).astype(np.uint8)
    where = np.ones((40, 50), bool)
    out = tone.match_colour(img, img, ref, where)
    mu_out = tone.lab_stats(tone.srgb_to_lab(out), where)[0]
    mu_ref = tone.lab_stats(tone.srgb_to_lab(ref), where)[0]
    assert np.abs(mu_out - mu_ref).max() < 1.5
    assert np.array_equal(tone.match_colour(img, img, ref, np.zeros((40, 50), bool)), img)   # nothing measured: unchanged


def _plate_and_result():
    """A plate with a gradient, and an 'AI result' that drifted +30 brighter everywhere and painted a red square inside the mask."""
    h, w = 128, 160
    plate = np.zeros((h, w, 3), np.uint8)
    plate[..., 0] = np.linspace(60, 160, w).astype(np.uint8)[None, :]
    plate[..., 1] = 90
    plate[..., 2] = np.linspace(140, 80, h).astype(np.uint8)[:, None]
    result = np.clip(plate.astype(int) + 30, 0, 255).astype(np.uint8)
    result[54:74, 70:90] = (220, 30, 30)
    mask = np.zeros((h, w), np.uint8)
    mask[40:88, 56:104] = 255
    return plate, result, mask


def test_match_colour_removes_drift_but_keeps_the_new_content():
    plate, result, mask = _plate_and_result()
    out = edit_ai.harmonise(result, plate, mask, 4, blend="feather", match_colour=True).astype(int)
    assert np.abs(out[5:30, 5:150] - plate[5:30, 5:150].astype(int)).mean() < 4             # the ring matches the plate again
    assert out[60:70, 75:85, 0].mean() > 180 and out[60:70, 75:85, 1].mean() < 60          # the red square is still red


def test_seamless_blend_leaves_no_step_at_the_seam():
    plate, result, mask = _plate_and_result()
    out = edit_ai.harmonise(result, plate, mask, 4, blend="seamless").astype(int)
    # just inside the contracted mask the result meets the plate: the step across the edge is small, the drift is gone
    step = np.abs(out[60, 61] - plate[60, 61].astype(int)).max()
    assert step <= 3, step
    assert out[60:70, 75:85, 0].mean() > 180                                                  # content kept


def test_assemble_layer_default_path_is_unchanged():
    plate, result, mask = _plate_and_result()
    plan = edit_ai.RegionPlan(x=0, y=0, w=160, h=128, ew=160, eh=128, scale=1.0)
    a = edit_ai.assemble_layer(result, plan, mask, 4)
    b = edit_ai.assemble_layer(result, plan, mask, 4, context=plate)                      # feather, no match: context unused
    assert np.array_equal(a, b) and np.array_equal(a[..., :3], result)


def test_result_layers_carry_a_linked_mask(tmp_path: Path):
    od = OpenDocument(Document(name="m", w=64, h=48), tmp_path / "m.ora")
    events = []
    fake = SimpleNamespace(hub=SimpleNamespace(broadcast=lambda *a: events.append(a)))
    job = SimpleNamespace(id="job1", batch_id="b1", seed=3, result={})
    rgba = np.zeros((20, 30, 4), np.uint8)
    rgba[..., :3] = 200
    rgba[5:15, 5:25, 3] = 255
    rgba[..., 3][rgba[..., 3] == 0] = 40                                                    # a soft edge
    asyncio.run(JobQueue._add_result_layer(fake, job, od, Inpaint(), rgba, 10, 8, "fill", as_mask=True))
    lid = job.result["layers"][0]
    node = od.doc.find(lid)
    assert node.mask is not None and node.mask.linked and node.mask.enabled
    assert (od.pixels[lid][..., 3] == 255).all() and np.array_equal(od.masks[lid], rgba[..., 3])
    # it renders exactly like the old baked alpha
    flat_mask = compose.Renderer(64, 48, od.pixels, od.masks).flatten_u8(od.nodes_dict())
    baked = compose.Renderer(64, 48, {lid: rgba}, {}).flatten_u8([{**n, "mask": None} for n in od.nodes_dict()])
    assert np.abs(flat_mask.astype(int) - baked.astype(int)).max() <= 1


def test_color_to_alpha_unmixes_ink_on_white():
    # black ink at 50 % over white, and pure white, and a pale grey (a = 0.25)
    p = np.array([[[0.5, 0.5, 0.5, 1.0], [1.0, 1.0, 1.0, 1.0], [0.75, 0.75, 0.75, 1.0]]], dtype=np.float32)
    out = compose.FILTERS["color_to_alpha"](p, {"colour": "#ffffff"})
    assert np.allclose(out[0, 0], [0, 0, 0, 0.5], atol=1e-5)
    assert out[0, 1, 3] == 0
    assert np.allclose(out[0, 2], [0, 0, 0, 0.25], atol=1e-5)
    # over white again it gives back the original
    white = np.ones((1, 3, 4), dtype=np.float32)
    back = compose.composite(white, out, "normal")
    assert np.allclose(back[..., :3], p[..., :3], atol=1e-5)
    # thresholds: a ≤ 30 % → transparent, a ≥ 40 % → opaque
    t = compose.FILTERS["color_to_alpha"](p, {"colour": "#ffffff", "transparency_threshold": 30, "opacity_threshold": 40})
    assert t[0, 0, 3] == 1.0 and t[0, 2, 3] == 0.0


def test_refine_match_colour_over_the_whole_image():
    # a refine that drifted warmer and brighter everywhere: matched over the whole image it returns to the plate's statistics
    plate, _, _ = _plate_and_result()
    drifted = np.clip(plate.astype(int) * np.array([1.12, 1.0, 0.9]) + 12, 0, 255).astype(np.uint8)
    plan = edit_ai.RegionPlan(x=0, y=0, w=160, h=128, ew=160, eh=128, scale=1.0)
    out = edit_ai.assemble_layer(drifted, plan, None, 0, context=plate, match_colour=True, match_on="all")
    assert np.abs(out[..., :3].astype(int) - plate.astype(int)).mean() < 3 < np.abs(drifted.astype(int) - plate.astype(int)).mean()
    assert (out[..., 3] == 255).all()
