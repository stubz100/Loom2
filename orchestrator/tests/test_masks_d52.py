"""D52 mask density and feather: compose.derived_mask matches the editor's three-box Gaussian (selectionOps.ts) and density formula,
the renderer applies both, and version-1 documents load with the defaults and save as version 2."""
import json
import zipfile

import numpy as np

from loom2 import compose
from loom2.documents import DOC_SCHEMA_VERSION, Document, Mask, OpenDocument, RasterLayer


def ts_gaussian(v: np.ndarray, sigma: float) -> np.ndarray:
    """A literal transcription of selectionOps.ts gaussian(): running sums in float32, Math.round at the end."""
    h, w = v.shape
    n3 = 3
    w_ideal = (12 * sigma * sigma / n3 + 1) ** 0.5
    wl = int(w_ideal)
    if wl % 2 == 0:
        wl -= 1
    wu = wl + 2
    m = round((12 * sigma * sigma - n3 * wl * wl - 4 * n3 * wl - 3 * n3) / (-4 * wl - 4))
    f = v.astype(np.float32).ravel()
    for i in range(3):
        r = int(np.floor(((wl if i < m else wu) - 1) / 2 + 0.5))
        if r < 1:
            continue
        n = 2 * r + 1
        tmp = np.zeros_like(f)
        out = np.zeros_like(f)
        for y in range(h):
            acc = np.float32(0)
            for k in range(-r, r + 1):
                acc = np.float32(acc + f[y * w + min(w - 1, max(0, k))])
            for x in range(w):
                tmp[y * w + x] = np.float32(acc / n)
                acc = np.float32(acc + f[y * w + min(w - 1, x + r + 1)] - f[y * w + max(0, x - r)])
        for x in range(w):
            acc = np.float32(0)
            for k in range(-r, r + 1):
                acc = np.float32(acc + tmp[min(h - 1, max(0, k)) * w + x])
            for y in range(h):
                out[y * w + x] = np.float32(acc / n)
                acc = np.float32(acc + tmp[min(h - 1, y + r + 1) * w + x] - tmp[max(0, y - r) * w + x])
        f = out
    return np.floor(f + 0.5).clip(0, 255).astype(np.uint8).reshape(h, w)


def test_defaults_leave_the_mask_alone():
    m = np.random.default_rng(1).integers(0, 256, (6, 9), dtype=np.uint8)
    assert np.array_equal(compose.derived_mask(m), m)


def test_density_lifts_black_towards_white():
    m = np.array([[0, 128, 255]], dtype=np.uint8)
    assert compose.derived_mask(m, density=0.0).tolist() == [[255, 255, 255]]
    assert compose.derived_mask(m, density=0.5).tolist() == [[128, 192, 255]]   # 255 − 0.5·255 = 127.5 → 128; 255 − 0.5·127 = 191.5 → 192


def test_feather_matches_the_editor_blur():
    rng = np.random.default_rng(7)
    m = np.zeros((23, 31), dtype=np.uint8)
    m[5:17, 8:22] = 255
    m[rng.random(m.shape) < 0.05] = 128
    for sigma in (0.6, 1.5, 3.0, 4.7):
        got, want = compose.derived_mask(m, feather=sigma), ts_gaussian(m, sigma)
        assert int(np.abs(got.astype(int) - want).max()) <= 1, sigma
        assert (got != want).mean() < 0.01, sigma


def test_feather_softens_a_hard_edge_symmetrically():
    m = np.zeros((1, 40), dtype=np.uint8)
    m[:, 20:] = 255
    out = compose.derived_mask(np.repeat(m, 5, axis=0), feather=3.0)[2]
    assert out[0] == 0 and out[-1] == 255
    assert np.all(np.diff(out.astype(int)) >= 0)
    assert 0 < out[17] < 128 < out[22] < 255
    assert abs(int(out[19]) + int(out[20]) - 255) <= 1


def test_the_renderer_applies_density_and_feather():
    px = np.zeros((4, 8, 4), dtype=np.uint8)
    px[...] = (255, 0, 0, 255)
    black = np.zeros((4, 8), dtype=np.uint8)
    node = RasterLayer(id="a", w=8, h=4, mask=Mask(linked=False, density=0.5)).model_dump()
    out = compose.Renderer(8, 4, {"a": px}, {"a": black}, background="transparent").flatten_u8([node])
    assert int(out[0, 0, 3]) in (127, 128)
    node["mask"]["density"] = 1.0
    node["mask"]["feather"] = 2.0
    half = black.copy()
    half[:, 4:] = 255
    out = compose.Renderer(8, 4, {"a": px}, {"a": half}, background="transparent").flatten_u8([node])
    assert 0 < out[1, 3, 3] < 255 and 0 < out[1, 4, 3] < 255


def test_version_1_documents_load_with_the_defaults_and_save_as_current(tmp_path):
    doc = Document(name="old", w=8, h=4, layers=[RasterLayer(id="a", w=8, h=4, mask=Mask())])
    raw = doc.model_dump()
    raw["schema_version"] = 1
    for k in ("density", "feather"):
        del raw["layers"][0]["mask"][k]
    loaded = Document.model_validate(raw)
    assert loaded.layers[0].mask.density == 1.0 and loaded.layers[0].mask.feather == 0.0
    od = OpenDocument(loaded, tmp_path / "old.ora")
    od.pixels["a"] = np.zeros((4, 8, 4), dtype=np.uint8)
    od.masks["a"] = np.full((4, 8), 255, dtype=np.uint8)
    od.save()
    with zipfile.ZipFile(tmp_path / "old.ora") as z:
        saved = json.loads(z.read("loom2.json"))
    assert saved["schema_version"] == DOC_SCHEMA_VERSION == 2
    assert saved["layers"][0]["mask"]["density"] == 1.0
