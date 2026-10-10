"""D39 Photoshop compositing semantics: blend formulas (Soft Light, Vivid Light, Hard Mix, the Burn / Dodge edge rule), clipping
groups (clipped layers atop an isolated base), pass-through groups below 100 % opacity, adjustment layers in their own blend mode,
and the compose_version stamp. Expected values come from PhotoCraft's own tests (fitted on Photoshop) and from hand derivations."""
import json
import zipfile
from pathlib import Path

import numpy as np

from loom2 import compose
from loom2.documents import AdjustmentLayer, Document, GroupLayer, Mask, OpenDocument, RasterLayer

W, H = 8, 4


def solid(rgba, w: int = W, h: int = H) -> np.ndarray:
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[...] = rgba
    return out


def left_half(rgba) -> np.ndarray:
    """Opaque `rgba` on the left half, transparent on the right."""
    out = np.zeros((H, W, 4), dtype=np.uint8)
    out[:, : W // 2] = rgba
    return out


def ch(mode: str, cb: float, cs: float) -> float:
    a = np.full((1, 1, 3), cb, dtype=np.float32)
    b = np.full((1, 1, 3), cs, dtype=np.float32)
    return float(compose.blend(mode, a, b)[0, 0, 0])


def flat(nodes: list, pixels: dict, masks: dict | None = None, background: str = "#ffffff") -> np.ndarray:
    dump = [n.model_dump() for n in nodes]
    return compose.Renderer(W, H, pixels, masks, background=background).flatten_u8(dump)


# ---- PC3: formulas ------------------------------------------------------------------------------------------------
def test_vivid_light_source_extremes_win():
    for cb in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert ch("vivid-light", cb, 0.0) == 0.0
        assert ch("vivid-light", cb, 1.0) == 1.0
    assert abs(ch("vivid-light", 0.75, 0.25) - 0.5) < 1e-6
    assert abs(ch("vivid-light", 0.25, 0.75) - 0.5) < 1e-6


def test_hard_mix_matches_photoshop_extremes_and_interior():
    assert ch("hard-mix", 1.0, 0.0) == 1.0              # black source over white → white
    assert ch("hard-mix", 0.0, 1.0) == 0.0              # white over black → black
    assert ch("hard-mix", 1.0 - 1e-5, 0.0) == 1.0       # EDGE: one rounding step below white still counts as white
    assert ch("hard-mix", 1e-5, 1.0) == 0.0
    assert ch("hard-mix", 0.6, 0.4) == 1.0              # cb + cs = 1 → 1
    assert ch("hard-mix", 0.6, 0.3) == 0.0


def test_burn_and_dodge_treat_near_extremes_as_exact():
    assert ch("color-burn", 1.0 - 1e-6, 0.0) == 1.0
    assert ch("color-dodge", 1e-6, 1.0) == 0.0
    assert abs(ch("color-burn", 0.5, 0.5) - 0.0) < 1e-6
    assert abs(ch("color-dodge", 0.25, 0.5) - 0.5) < 1e-6


def test_soft_light_is_photoshops():
    # differs from W3C only where cs > ½ and cb ≤ ¼: Photoshop uses √cb there, W3C a cubic
    assert abs(ch("soft-light", 0.1, 1.0) - np.sqrt(0.1)) < 1e-6       # W3C would give 0.296
    assert abs(ch("soft-light", 0.5, 0.75) - (0.25 + np.sqrt(0.5) * 0.5)) < 1e-6
    assert abs(ch("soft-light", 0.4, 0.2) - (2 * 0.4 * 0.2 + 0.16 * 0.6)) < 1e-6
    assert abs(ch("soft-light", 0.3, 0.5) - 0.3) < 1e-6                 # cs = ½ is the identity


# ---- PC1: clipping groups -----------------------------------------------------------------------------------------
def test_clip_is_to_the_base_not_to_everything_below():
    """The bug D39 fixes: over an opaque background a clipped layer must still show only where its base has pixels."""
    nodes = [RasterLayer(id="blue", clip=True), RasterLayer(id="base")]                 # top first
    out = flat(nodes, {"base": left_half((255, 0, 0, 255)), "blue": solid((0, 0, 255, 255))})
    assert tuple(out[0, 0]) == (0, 0, 255, 255)          # inside the base: the clipped layer
    assert tuple(out[0, W - 1]) == (255, 255, 255, 255)  # outside: the white background, untouched


def test_clip_unit_takes_the_base_opacity_and_mode():
    nodes = [RasterLayer(id="blue", clip=True), RasterLayer(id="base", opacity=0.5)]
    out = flat(nodes, {"base": left_half((255, 0, 0, 255)), "blue": solid((0, 0, 255, 255))})
    assert np.allclose(out[0, 0], (128, 128, 255, 255), atol=1)                         # blue at the base's 50 % over white
    nodes = [RasterLayer(id="blue", clip=True), RasterLayer(id="base", blend="multiply")]
    out = flat(nodes, {"base": left_half((255, 0, 0, 255)), "blue": solid((0, 0, 255, 255))}, background="#808080")
    assert np.allclose(out[0, 0], (0, 0, 128, 255), atol=1)                             # the unit (blue) multiplies onto grey


def test_clipped_layer_blends_with_the_base_as_if_opaque_and_keeps_its_alpha():
    half = left_half((255, 0, 0, 128))                                                  # half-transparent red base
    nodes = [RasterLayer(id="g", clip=True, blend="multiply"), RasterLayer(id="base")]
    out = compose.Renderer(W, H, {"base": half, "g": solid((0, 255, 0, 255))}).flatten([n.model_dump() for n in nodes])
    assert np.allclose(out[0, 0], (0.0, 0.0, 0.0, 128 / 255), atol=1e-3)                # red × green = black, alpha = the base's
    assert out[0, W - 1, 3] == 0.0


def test_clip_run_visibility_and_masks():
    pixels = {"base": left_half((255, 0, 0, 255)), "blue": solid((0, 0, 255, 255))}
    hidden_base = [RasterLayer(id="blue", clip=True), RasterLayer(id="base", visible=False)]
    assert tuple(flat(hidden_base, pixels)[0, 0]) == (255, 255, 255, 255)              # a hidden base hides its clipping group
    hidden_clip = [RasterLayer(id="blue", clip=True, visible=False), RasterLayer(id="base")]
    assert tuple(flat(hidden_clip, pixels)[0, 0]) == (255, 0, 0, 255)
    # the base's mask is part of its shape: masked-out base pixels clip the clipped layer too
    mask = np.zeros((H, W), dtype=np.uint8)
    mask[:, :1] = 255
    masked = [RasterLayer(id="blue", clip=True), RasterLayer(id="base", mask=Mask(linked=False))]
    out = flat(masked, pixels, {"base": mask})
    assert tuple(out[0, 0]) == (0, 0, 255, 255) and tuple(out[0, 2]) == (255, 255, 255, 255)


def test_clipped_adjustment_applies_inside_the_base_only():
    nodes = [AdjustmentLayer(id="inv", type="invert", clip=True), RasterLayer(id="base")]
    out = flat(nodes, {"base": left_half((255, 0, 0, 255))})
    assert tuple(out[0, 0]) == (0, 255, 255, 255)        # the base inverted
    assert tuple(out[0, W - 1]) == (255, 255, 255, 255)  # the background is not


def test_a_clipped_node_without_a_base_renders_normally():
    nodes = [RasterLayer(id="blue", clip=True)]
    assert tuple(flat(nodes, {"blue": left_half((0, 0, 255, 255))})[0, 0]) == (0, 0, 255, 255)


def test_several_clipped_layers_stack_inside_the_base():
    nodes = [RasterLayer(id="top", clip=True, opacity=0.5), RasterLayer(id="mid", clip=True), RasterLayer(id="base")]
    out = flat(nodes, {"base": left_half((255, 0, 0, 255)), "mid": solid((0, 0, 255, 255)), "top": solid((0, 255, 0, 255))})
    assert np.allclose(out[0, 0], (0, 128, 128, 255), atol=1)
    assert tuple(out[0, W - 1]) == (255, 255, 255, 255)


# ---- PC2: pass-through groups and adjustment blend ----------------------------------------------------------------
def test_pass_through_group_below_full_opacity_still_reaches_the_layers_below():
    grp = GroupLayer(id="g", opacity=0.5, passthrough=True, children=[AdjustmentLayer(id="inv", type="invert")])
    out = flat([grp], {}, background="#c08040")
    # an inverted background mixed 50/50 with the original: (192, 128, 64) and (63, 127, 191) → ≈ (128, 128, 128)
    assert np.allclose(out[0, 0], (128, 128, 128, 255), atol=1)


def test_isolated_group_at_half_opacity_is_unchanged():
    grp = GroupLayer(id="g", opacity=0.5, passthrough=False, children=[RasterLayer(id="a")])
    out = flat([grp], {"a": solid((0, 0, 0, 255))})
    assert np.allclose(out[0, 0], (128, 128, 128, 255), atol=1)


def test_adjustment_layer_applies_its_blend_mode():
    grey = "#808080"
    normal = flat([AdjustmentLayer(id="inv", type="invert")], {}, background=grey)
    assert np.allclose(normal[0, 0], (127, 127, 127, 255), atol=1)
    multiply = flat([AdjustmentLayer(id="inv", type="invert", blend="multiply")], {}, background=grey)
    assert np.allclose(multiply[0, 0], (64, 64, 64, 255), atol=1)                       # 0.5 × inverted 0.5
    screen = flat([AdjustmentLayer(id="inv", type="invert", blend="screen", opacity=0.5)], {}, background=grey)
    assert np.allclose(screen[0, 0], (160, 160, 160, 255), atol=1)                      # halfway to screen(0.5, 0.5) = 0.75


def test_saved_documents_record_the_compose_version(tmp_path: Path):
    doc = Document(name="v", w=W, h=H, layers=[RasterLayer(id="a", w=W, h=H)])
    od = OpenDocument(doc, tmp_path / "v.ora")
    od.pixels["a"] = solid((10, 20, 30, 255))
    od.save()
    with zipfile.ZipFile(tmp_path / "v.ora") as z:
        assert json.loads(z.read("loom2.json"))["meta"]["compose_version"] == compose.COMPOSE_VERSION == 3
