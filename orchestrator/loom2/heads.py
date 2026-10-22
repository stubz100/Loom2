"""D118 (AE4c, from spike E29b — journal 2026-10-21 22:14): the head as its own layer. A character's head in a full shot is a few dozen
pixels tall, too small for a face or a lip-sync model to work on; the field's practice (and the author's idea) is to crop the head, work
at the models' own size and paste back. Here: the head box tracked from the figure's COCO-18 keypoints (Stage's, stored on the final),
the crop at 512², the paste back under a mask grown beyond the new head's silhouette and feathered — the halo the author saw on E29b
was the old head's remains around a plain feathered square — and, for Lip-sync, the line windows an S2V talking head is rendered for.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CROP = 512                                        # the head crop's side: Wan Animate's and S2V's working size for a face (E29b)
SMOOTH = 9                                        # the box's centre and side smoothed over this many frames
GROW = 0.06                                       # the paste mask grown by this fraction of the box side beyond the head's silhouette
SOFT = 0.04                                       # … and feathered by this fraction (a Gaussian's σ)
EDGE = 0.12                                       # E29b's rounded-square feather: the paste never reaches the crop's hard edge
MIN_SIDE = 48.0


def head_boxes(kps: list, n: int, w: int, h: int, smooth: int = SMOOTH) -> list[tuple[int, int, int]]:
    """(x0, y0, side) per frame from COCO-18 keypoints (0 nose, 1 neck, 14 / 15 eyes, 16 / 17 ears; [x, y, visible]): the head's centre
    over the visible head points, a square of 2.6 × the nose–neck distance (at least 1.8 × the ear spread), smoothed, the head in the
    upper part of the box, clamped to the picture. E29b's tracker."""
    cs, ss = [], []
    for i in range(n):
        k = np.array(kps[min(i, len(kps) - 1)], dtype=float).reshape(-1, 3)
        head = [j for j in (0, 14, 15, 16, 17) if j < len(k) and k[j][2] > 0]
        pts = k[head, :2] if head else k[:1, :2]
        c = pts.mean(axis=0)
        nose_neck = float(np.hypot(*(k[0][:2] - k[1][:2]))) if len(k) > 1 and k[0][2] > 0 and k[1][2] > 0 else 40.0
        ears = float(np.hypot(*(k[16][:2] - k[17][:2]))) if len(k) > 17 and k[16][2] > 0 and k[17][2] > 0 else 0.0
        cs.append(c)
        ss.append(max(2.6 * nose_neck, 1.8 * ears, MIN_SIDE))
    cs_a, ss_a = np.array(cs), np.array(ss)
    pad = smooth // 2
    boxes = []
    for i in range(n):
        c = cs_a[max(0, i - pad):i + pad + 1].mean(axis=0)
        side = int(round(min(float(ss_a[max(0, i - pad):i + pad + 1].mean()), w, h)))
        x0 = int(round(max(0, min(w - side, c[0] - side / 2))))
        y0 = int(round(max(0, min(h - side, c[1] - side * 0.56))))
        boxes.append((x0, y0, side))
    return boxes


def box_crop(im: Image.Image, box: tuple[int, int, int], size: int = CROP) -> Image.Image:
    x0, y0, s = box
    return im.crop((x0, y0, x0 + s, y0 + s)).resize((size, size), Image.LANCZOS)


def feather_square(size: int, soft: float = EDGE) -> np.ndarray:
    """E29b's paste feather: a rounded square inset by `soft` / 2 of the side, blurred by as much — 0 at the crop's edge, 1 inside."""
    m = Image.new("L", (size, size), 0)
    inset = int(size * soft / 2)
    ImageDraw.Draw(m).rounded_rectangle([inset, inset, size - inset, size - inset], radius=int(size * 0.18), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(size * soft / 2))
    return np.asarray(m, dtype=np.float32) / 255.0


def paste_mask(alpha: np.ndarray, old_sil: np.ndarray | None, grow: float = GROW, soft: float = SOFT) -> np.ndarray:
    """Where the rendered head replaces the layer, at the box's size: the union of the new head's silhouette and the old one's (so the old
    head's remains are covered — E29b's halo), grown by `grow` of the side, feathered by `soft`, inside the rounded square."""
    s = alpha.shape[0]
    u = np.maximum(alpha, old_sil) if old_sil is not None else alpha
    im = Image.fromarray((np.clip(u, 0, 1) * 255 + 0.5).astype(np.uint8))
    r = int(round(grow * s))
    if r > 0:
        im = im.filter(ImageFilter.MaxFilter(2 * r + 1))
    im = im.filter(ImageFilter.GaussianBlur(max(0.5, soft * s)))
    m = np.asarray(im, dtype=np.float32) / 255.0
    return np.clip(m * feather_square(s), 0.0, 1.0)


RGB_GROW, RGB_SOFT = 0.02, 0.01                  # the colour paste: the head's own silhouette with a hair-thin margin


def paste_head(base: np.ndarray, head: Image.Image, box: tuple[int, int, int], old_sil: np.ndarray | None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The rendered head (RGBA at the crop size: its colour and its silhouette) back onto the layer's frame at the box. The colour comes
    in under the head's own silhouette with a hair-thin margin only — the render's background around the head is shaded (a soft darkening
    the model paints) and a wider paste carried it in as a dark rim (rig 2026-10-22); what the old head leaves beyond the new one is cut
    by the *matte* instead, updated under the wider mask (paste_mask: the union of the silhouettes, grown and feathered). Returns the frame
    as uint8 RGB, the matte's mask P (box size) and the head's silhouette at the box size."""
    x0, y0, s = box
    h = head.convert("RGBA").resize((s, s), Image.LANCZOS)
    arr = np.asarray(h, dtype=np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3] / 255.0
    p_rgb = paste_mask(alpha, None, RGB_GROW, RGB_SOFT)
    p = paste_mask(alpha, old_sil)
    out = np.asarray(base, dtype=np.float32).copy()
    region = out[y0:y0 + s, x0:x0 + s]
    out[y0:y0 + s, x0:x0 + s] = region * (1 - p_rgb[..., None]) + rgb * p_rgb[..., None]
    return np.clip(out + 0.5, 0, 255).astype(np.uint8), p, alpha


def paste_take(take_dir: Path, heads: list[Path], base: list[Path], mattes: list[Path], comp_mattes: list[Path], boxes: list[tuple[int, int, int]], n: int) -> None:
    """A take's frames from its rendered heads (RGBA at the crop size, kept under `head/`): each pasted back onto the base frame at its
    box; the layer's matte updated in the box (the old one outside the mask, the new head's silhouette inside) into `matte/`, and the
    composition's matte footage likewise into `matte_comp/` — a nearer prop's cut kept as the ratio of the old composition matte to the
    old matte. Runs again on a kept take (the rig's re-paste, AE4d's tools)."""
    hd, md, cd = take_dir / "head", take_dir / "matte", take_dir / "matte_comp"
    keep_heads = heads and heads[0].parent == hd
    for d in ([md, cd] if keep_heads else [hd, md, cd]):
        if d.exists():
            for old in d.glob("*.png"):
                old.unlink()
    hd.mkdir(parents=True, exist_ok=True)
    if len(mattes) == n:
        md.mkdir(exist_ok=True)
    if len(comp_mattes) == n and len(mattes) == n:
        cd.mkdir(exist_ok=True)
    for i in range(n):
        x0, y0, s = boxes[i]
        old = None
        old_full = None
        if len(mattes) == n:
            old_full = np.asarray(Image.open(mattes[i]).convert("L"), dtype=np.float32) / 255.0
            old = old_full[y0:y0 + s, x0:x0 + s]
        with Image.open(heads[i]) as him:
            him = him.convert("RGBA")
            if not keep_heads:
                him.save(hd / f"{i:04d}.png")
            out, p, alpha = paste_head(np.asarray(Image.open(base[i]).convert("RGB")), him, boxes[i], old)
        Image.fromarray(out).save(take_dir / f"{i:04d}.png")
        if old is not None and old_full is not None:
            new_full = old_full.copy()
            new_full[y0:y0 + s, x0:x0 + s] = old * (1 - p) + alpha * p
            Image.fromarray((np.clip(new_full, 0, 1) * 255 + 0.5).astype(np.uint8)).save(md / f"{i:04d}.png")
            if len(comp_mattes) == n:
                cm_full = np.asarray(Image.open(comp_mattes[i]).convert("L"), dtype=np.float32) / 255.0
                cm = cm_full[y0:y0 + s, x0:x0 + s]
                cut = np.where(old > 0.02, np.clip(cm / np.maximum(old, 1e-3), 0, 1), 1.0)
                cm_full[y0:y0 + s, x0:x0 + s] = cm * (1 - p) + alpha * cut * p
                Image.fromarray((np.clip(cm_full, 0, 1) * 255 + 0.5).astype(np.uint8)).save(cd / f"{i:04d}.png")


def windows(timing: list[dict[str, Any]], rate: int, n: int, batch: int = 77, step: int = 4, least: int = 9) -> list[dict[str, Any]]:
    """The Lip-sync windows from the lines on the composition (AE4b's audio layers: `in`, `out`, `start` in seconds, `path`): the shot
    frames each line plays over, cut into runs of at most `batch` frames on the model's 4n + 1 grid (rounded up, so a run may reach a
    little past the line — the mouth closes on silence). Each carries where its audio starts in the line's file."""
    out: list[dict[str, Any]] = []
    for t in sorted(timing, key=lambda x: float(x.get("in", 0.0))):
        f0 = max(0, int(round(float(t["in"]) * rate)))
        f1 = min(n, int(round(float(t["out"]) * rate)))
        while f0 < f1 and f0 < n:
            run = min(batch, f1 - f0)
            m = max(least, run)
            frames = m + (-(m - 1) % step)
            frames = min(frames, batch)
            out.append({"k": len(out), "f0": f0, "f1": min(n, f0 + frames), "frames": frames, "file_t0": f0 / rate - float(t.get("start", 0.0)),
                        "path": t.get("path"), "layer": t.get("layer"), "text": t.get("text"), "asset_id": t.get("asset_id")})
            f0 += frames
    return out


def slice_audio(src: Path, t0: float, seconds: float, out: Path) -> Path:
    """`seconds` of the line's file from `t0` (zero-padded at either end) as a WAV for the talking-head model."""
    import soundfile as sf
    data, sr = sf.read(str(src), dtype="float32", always_2d=True)
    total = int(round(seconds * sr))
    a, b = int(round(t0 * sr)), int(round(t0 * sr)) + total
    seg = np.zeros((total, data.shape[1]), dtype=np.float32)
    sa, sb = max(0, a), min(len(data), b)
    if sb > sa:
        seg[sa - a:sa - a + (sb - sa)] = data[sa:sb]
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), seg, sr)
    return out
