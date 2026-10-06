"""The noise filter is a pure function of (seed, x, y) shared with the editor's shaders (adjustFilters.ts): a lowbias32
integer hash feeding Box-Muller. These tests pin the hash against a scalar reference and the statistics of the field."""
import numpy as np

from loom2 import compose


def ref_hash(x: int) -> int:
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def test_hash_matches_scalar_reference():
    xs = np.array([0, 1, 2, 7, 1000, 0xFFFFFFFF, 0x7FEB352D], dtype=np.uint32)
    got = compose._hash32(xs)
    assert [int(v) for v in got] == [ref_hash(int(v)) for v in xs]
    assert ref_hash(0) != 0 or ref_hash(1) != ref_hash(2)              # not degenerate


def test_noise_field_is_deterministic_and_keyed_on_seed_and_position():
    a = compose.noise_field(64, 48, 0)
    b = compose.noise_field(64, 48, 0)
    c = compose.noise_field(64, 48, 1)
    assert a.shape == (48, 64, 3) and a.dtype == np.float32
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    # a wider field keeps the same values at the same (x, y): the key is the position, not the buffer
    wide = compose.noise_field(128, 48, 0)
    assert np.array_equal(wide[:, :64], a)
    # the three channels are independent draws (monochrome repeats channel 0 only in _noise)
    assert not np.array_equal(a[..., 0], a[..., 1])


def test_noise_field_is_unit_normal_and_scalar_pixel_matches_reference():
    f = compose.noise_field(256, 256, 7)
    assert abs(float(f.mean())) < 0.02
    assert abs(float(f.std()) - 1.0) < 0.02
    # one pixel by hand: k = h(h(h(seed) + x) + y), then u = ((k >> 9) + 0.5) / 2**23, Box-Muller
    x, y, seed = 37, 101, 7
    k = ref_hash((ref_hash((ref_hash(seed) + x) & 0xFFFFFFFF) + y) & 0xFFFFFFFF)
    k2 = ref_hash(k)
    u1 = (np.float32((k >> 9)) + np.float32(0.5)) / np.float32(8388608.0)
    u2 = (np.float32((k2 >> 9)) + np.float32(0.5)) / np.float32(8388608.0)
    expected_r = np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)
    assert abs(float(f[y, x, 0]) - float(expected_r)) < 1e-5


def test_noise_filter_applies_amount_and_monochrome():
    base = np.full((32, 32, 4), 0.5, dtype=np.float32)
    mono = compose._noise(base, {"amount": 10, "seed": 3, "monochrome": True})
    col = compose._noise(base, {"amount": 10, "seed": 3, "monochrome": False})
    assert mono.shape == base.shape and np.array_equal(mono[..., 3], base[..., 3])
    assert np.array_equal(mono[..., 0], mono[..., 1]) and np.array_equal(mono[..., 1], mono[..., 2])
    assert not np.array_equal(col[..., 0], col[..., 1])
    d = (mono[..., 0] - 0.5)
    assert 0.07 < float(d.std()) < 0.13                                # σ = amount / 100 = 0.1 before clipping
    assert mono.min() >= 0.0 and mono.max() <= 1.0
