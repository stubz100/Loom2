"""D111 (PS5e): the final shot's assembly — its layers composited into the shot, frame by frame, on the CPU (a queue job of its own).

  1. the plate (its projected frames), darkened by Stage's shadows: the lit clay of everything over the bare set's (D106's dummy source),
     1 on every actor;
  2. the props (their 3D models rendered, R1) and the characters (their performances, matted) in Stage's depth order, far to near; where a
     prop is nearer the camera than a character, the prop hides her (E28b: the figure's depth grown over her matte);
  3. each character set on its shadow by her contact offset (D107): her soles against her figure's in Stage, one offset per shot (the
     median over the frames her feet show), the anchor pins' default.

An actor's mask is where its Stage depth differs from the bare set's (E23b); a character's alpha is her SAM 3 matte kept inside that mask
grown 36 px (E23b), softened, and moved by her offset. The frames go into a clip (PNG master, proxy, Catalogue asset); at F16 they are also
conformed to 24 fps when the local RIFE is there (D27: native master, RIFE for viewing).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

from .finals import Final, FinalStore

GROW = 36                                          # E23b: a character's matte kept inside her figure's mask grown this far
DEPTH_EPS = 0.5 / 255                              # an actor's mask: its depth differs from the bare set's by more than this


def gray(p: Path) -> np.ndarray:
    with Image.open(p) as im:
        return np.asarray(im.convert("L"), dtype=np.float32) / 255.0


def rgb(p: Path) -> np.ndarray:
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB"), dtype=np.float32)


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    """A square dilation by r px through a summed-area table (E23b's fast path)."""
    a = (m > 0).astype(np.int32)
    if r <= 0:
        return a > 0
    c = np.pad(a, ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
    k = 2 * r + 1
    s = c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]
    return s > 0


def soft(m: np.ndarray, r: float) -> np.ndarray:
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255.0


def max_filter(a: np.ndarray, r: int) -> np.ndarray:
    """A (2r+1)² grey max filter, separable."""
    for ax in (0, 1):
        p = np.pad(a, [(r, r) if k == ax else (0, 0) for k in range(2)], mode="edge")
        n = a.shape[ax]
        a = np.max([np.take(p, range(k, k + n), axis=ax) for k in range(2 * r + 1)], axis=0)
    return a


def shift(a: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """An image (H × W or H × W × C) moved by (dx, dy) px, bilinear, the edges empty."""
    if abs(dx) < 1e-3 and abs(dy) < 1e-3:
        return a
    chans = a[..., None] if a.ndim == 2 else a
    out = np.stack([np.asarray(Image.fromarray(chans[..., c].astype(np.float32), mode="F").transform(
        (chans.shape[1], chans.shape[0]), Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR, fillcolor=0.0)) for c in range(chans.shape[2])], axis=-1)
    return out[..., 0] if a.ndim == 2 else out


def soles(m: np.ndarray) -> tuple[float, float] | None:
    """Where a figure meets the floor in the frame: the lowest row of its mask and the middle of its lowest 4 % (E23e)."""
    ys, xs = np.nonzero(m)
    if len(ys) < 50:
        return None
    top, bot = ys.min(), ys.max()
    low = ys >= bot - 0.04 * (bot - top)
    return float(np.median(xs[low])), float(bot)


def contact_offset(stage_masks: list[np.ndarray], mattes: list[np.ndarray], h: int) -> tuple[float, float]:
    """D107: the move that sets a character's soles on her figure's — the median over the frames where both show and the feet are in the
    picture (a sole on the frame's bottom edge is cut off, not standing there); (0, 0) when no frame tells."""
    v = []
    for sm, mt in zip(stage_masks, mattes):
        a, b = soles(mt > 0.5), soles(sm)
        if a and b and a[1] < h - 2 and b[1] < h - 2:
            v.append((b[0] - a[0], b[1] - a[1]))
    if not v:
        return 0.0, 0.0
    d = np.median(np.array(v), axis=0)
    return float(d[0]), float(d[1])


def _frames(d: Path) -> list[Path]:
    return sorted(d.glob("*.png"))


def check_ready(store: FinalStore, f: Final) -> list[str]:
    """What is missing before the final can be assembled (empty: ready)."""
    out = []
    for x in f.layers:
        if x.kind == "plate" and x.frames_done != f.frames:
            out.append("the plate is not projected yet")
        if x.kind == "figure":
            if x.frames_done != f.frames:
                out.append(f"{x.name} is not performed yet")
            elif len(_frames(store.pass_dir(f.id, x.id, "matte"))) != f.frames:
                out.append(f"{x.name} has no matte yet")
    return out


def mix_audio(timing: list[dict[str, Any]], seconds: float, out: Path) -> Path | None:
    """D118 (AE4b): the composition's audio layers mixed into one WAV of the shot's length — each line's samples from `in - start` to
    `out - start` placed at `in` (numpy; a rate that differs from the first line's is resampled linearly). None when no line plays."""
    import soundfile as sf
    tracks = []
    for a in timing:
        p = Path(a["path"])
        if not p.is_file() or a["out"] <= a["in"]:
            continue
        data, sr = sf.read(str(p), dtype="float32", always_2d=True)
        tracks.append((a, data, sr))
    if not tracks:
        return None
    sr = tracks[0][2]
    n = int(round(seconds * sr))
    mix = np.zeros((n, 2), dtype=np.float32)
    for a, data, rate in tracks:
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        if rate != sr:
            m = int(round(len(data) * sr / rate))
            xs = np.linspace(0, len(data) - 1, m)
            data = np.stack([np.interp(xs, np.arange(len(data)), data[:, k]) for k in range(2)], axis=1).astype(np.float32)
        s0 = max(0, int(round((a["in"] - a["start"]) * sr)))
        s1 = min(len(data), int(round((a["out"] - a["start"]) * sr)))
        at = int(round(a["in"] * sr))
        if s1 <= s0 or at >= n:
            continue
        seg = data[s0:s1][: max(0, n - at)]
        mix[at:at + len(seg)] += seg
    peak = float(np.abs(mix).max()) if n else 0.0
    if peak > 0.99:
        mix *= 0.99 / peak
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mix, sr)
    return out


def assemble_frames(store: FinalStore, f: Final, out_dir: Path, progress=None, comp_dir: Path | None = None) -> dict[str, Any]:
    """Composite the final's layers into `out_dir/NNNN.png`; returns what it did (offsets, occlusions, the stack order, time).

    With `comp_dir` (AE1, proto01_animate 20 §2) it also writes the **composition's footage** from the same per-frame rules, so the editable
    composition and this composite agree by construction: `shadow/` (Stage's ratio as grey, to multiply), `<prop>/` (its beauty with its depth
    alpha), `<figure>_matte/` (her alpha with a nearer prop's cut, in her own frame — her contact offset is the layer's position there)."""
    t0 = time.time()
    missing = check_ready(store, f)
    if missing:
        raise ValueError("; ".join(missing))
    out_dir.mkdir(parents=True, exist_ok=True)
    n, w, h = f.frames, f.size["w"], f.size["h"]
    pd = lambda lid, name: _frames(store.pass_dir(f.id, lid, name))   # noqa: E731
    md = lambda lid: _frames(store.matte_dir(f.id, lid))               # noqa: E731  (AE4c: the shown take's matte when the pass changed her silhouette)
    plate = _frames(store.frames_dir(f.id, "plate"))
    bare_d, bare_c = pd("plate", "depth"), pd("plate", "clay")
    shadows = pd("shadows", "clay")
    props = [x for x in f.layers if x.kind == "prop"]
    figs = [x for x in f.layers if x.kind == "figure"]
    if comp_dir:
        for name in ["shadow", *(x.id for x in props), *(f"{x.id}_matte" for x in figs)]:
            shutil.rmtree(comp_dir / name, ignore_errors=True)
            (comp_dir / name).mkdir(parents=True)
    # the characters' contact offsets (D107), one per layer over the shot
    offsets: dict[str, tuple[float, float]] = {}
    for x in figs:
        dep, mt = pd(x.id, "depth"), md(x.id)
        step = max(1, n // 24)                                               # two dozen frames tell the median
        sm = [np.abs(gray(dep[i]) - gray(bare_d[i])) > DEPTH_EPS for i in range(0, n, step)]
        mm = [gray(mt[i]) * dilate(sm[k], GROW) for k, i in enumerate(range(0, n, step))]
        offsets[x.id] = contact_offset(sm, mm, h)
    hidden = {x.id: 0 for x in figs}
    orders: list[tuple[str, ...]] = []
    for i in range(n):
        bd = gray(bare_d[i])
        layers: list[dict[str, Any]] = []
        actors = np.zeros((h, w), bool)
        for x in props:
            dep = gray(pd(x.id, "depth")[i])
            m = np.abs(dep - bd) > DEPTH_EPS
            actors |= m
            layers.append({"id": x.id, "kind": "prop", "img": rgb(pd(x.id, "beauty")[i]), "alpha": soft(m.astype(np.float32), 0.7), "depth": np.where(m, dep, 0.0),
                           "order": float(np.median(dep[m])) if m.any() else 0.0})
        for x in figs:
            dep = gray(pd(x.id, "depth")[i])
            sm = np.abs(dep - bd) > DEPTH_EPS
            actors |= sm
            mt = gray(md(x.id)[i]) * dilate(sm, GROW)
            al = soft(mt, 1.2) * dilate(mt > 0.5, 3)
            dx, dy = offsets[x.id]
            grown = max_filter(np.where(sm, dep, 0.0), 15)
            fill = float(np.median(dep[sm])) if sm.any() else 0.0
            layers.append({"id": x.id, "kind": "figure", "img": shift(rgb(_frames(store.frames_dir(f.id, x.id))[i]), dx, dy), "alpha": np.clip(shift(al, dx, dy), 0, 1),
                           "alpha0": al, "offset": (dx, dy), "depth": shift(np.where(grown > 0, grown, fill), dx, dy), "order": fill})
        ratio = np.clip(gray(shadows[i]) / np.maximum(8 / 255, gray(bare_c[i])), 0.0, 1.0)
        ratio[dilate(actors, 2)] = 1.0
        out = rgb(plate[i]) * ratio[..., None]
        stack = sorted(layers, key=lambda x: x["order"])                     # far to near (the depth pass is brighter nearer)
        orders.append(tuple(lay["id"] for lay in stack))
        for lay in stack:
            al = lay["alpha"]
            if lay["kind"] == "figure":
                for p in (q for q in layers if q["kind"] == "prop"):      # a nearer prop hides her
                    nearer = (p["alpha"] > 0.05) & (p["depth"] > lay["depth"] + 1.5 / 255)
                    if nearer.any():
                        hidden[lay["id"]] += int((nearer & (al > 0.5)).sum())
                        al = np.minimum(al, np.where(nearer, 1 - p["alpha"], 1.0))
                        if comp_dir:                                      # the same cut in her own (unmoved) frame
                            dx, dy = lay["offset"]
                            lay["alpha0"] = np.minimum(lay["alpha0"], 1 - np.clip(shift(np.where(nearer, p["alpha"], 0.0), -dx, -dy), 0, 1))
            out = out * (1 - al[..., None]) + lay["img"] * al[..., None]
        Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(out_dir / f"{i:06d}.png")
        if comp_dir:
            Image.fromarray((ratio * 255 + 0.5).astype(np.uint8)).convert("RGB").save(comp_dir / "shadow" / f"{i:04d}.png")
            for lay in layers:
                if lay["kind"] == "prop":
                    rgba = np.dstack([lay["img"], lay["alpha"] * 255])
                    Image.fromarray(np.clip(rgba + 0.5, 0, 255).astype(np.uint8), "RGBA").save(comp_dir / lay["id"] / f"{i:04d}.png")
                else:
                    Image.fromarray((np.clip(lay["alpha0"], 0, 1) * 255 + 0.5).astype(np.uint8)).save(comp_dir / f"{lay['id']}_matte" / f"{i:04d}.png")
        if progress:
            progress(i + 1, n)
    stack_order = max(set(orders), key=orders.count) if orders else ()
    return {"frames": n, "offsets_px": {k: [round(v[0], 1), round(v[1], 1)] for k, v in offsets.items()}, "hidden_px": hidden,
            "stack": list(stack_order), "stack_frames": orders.count(stack_order), "seconds": round(time.time() - t0, 1)}

def rife_binary() -> Path | None:
    """The local rife-ncnn-vulkan (E9, D27) under engine/tools, when it was installed; None otherwise (the clip stays at its rate)."""
    root = Path(__file__).resolve().parents[2] / "engine" / "tools"
    return next(iter(sorted(root.glob("rife-ncnn-vulkan-*/rife-ncnn-vulkan.exe"))), None)


def conform_24_alpha(src: Path, dst: Path, n16: int) -> list[Path] | None:
    """AE5: F16 to 24 fps keeping the alpha — RIFE reads and writes RGB, so the colour and the alpha (as a grey picture) are conformed in two
    runs and put back together; None without the binary. RIFE shifts a flat grey by a few levels (the AE5 rig: an opaque 255 came back 250),
    so an opaque sequence keeps 255 without a second run, and the alpha's near-ends are snapped back (≤ 8 → 0, ≥ 247 → 255)."""
    srcs = sorted(src.glob("*.png"))
    opaque = all(Image.open(p).convert("RGBA").getchannel("A").getextrema()[0] == 255 for p in srcs)
    col, alp = dst.parent / f"{dst.name}-rgb-in", dst.parent / f"{dst.name}-a-in"
    for d in (col, alp):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    for i, p in enumerate(srcs):
        im = Image.open(p).convert("RGBA")
        im.convert("RGB").save(col / f"{i:06d}.png")
        im.getchannel("A").convert("RGB").save(alp / f"{i:06d}.png")
    c = conform_24(col, dst.parent / f"{dst.name}-rgb", n16)
    a = (c if opaque else conform_24(alp, dst.parent / f"{dst.name}-a", n16)) if c is not None else None
    if c is None or a is None:
        return None
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    out = []
    for i, (pc, pa) in enumerate(zip(c, a)):
        im = Image.open(pc).convert("RGB")
        if opaque:
            im.putalpha(255)
        else:
            al = np.asarray(Image.open(pa).convert("L")).copy()
            al[al <= 8], al[al >= 247] = 0, 255
            im.putalpha(Image.fromarray(al))
        q = dst / f"{i:06d}.png"
        im.save(q)
        out.append(q)
    for d in (col, alp, dst.parent / f"{dst.name}-rgb", dst.parent / f"{dst.name}-a"):
        shutil.rmtree(d, ignore_errors=True)
    return out


def write_prores(frames: list[Path], dst: Path, fps: float, alpha: bool) -> dict[str, Any]:
    """AE5: a ProRes 4444 (10-bit 4:4:4, `prores_ks` profile 4444) of the master's frames at its rate, with their alpha when `alpha`."""
    import av
    from fractions import Fraction
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part" + dst.suffix)
    first = Image.open(frames[0])
    w, h = first.size
    with av.open(str(tmp), "w", format="mov") as c:
        s = c.add_stream("prores_ks", rate=Fraction(fps).limit_denominator(1001))
        s.width, s.height = w, h
        s.pix_fmt = "yuva444p10le" if alpha else "yuv444p10le"
        s.options = {"profile": "4", "vendor": "apl0"}
        for p in frames:
            im = Image.open(p).convert("RGBA" if alpha else "RGB")
            for pkt in s.encode(av.VideoFrame.from_ndarray(np.asarray(im), format="rgba" if alpha else "rgb24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    from .fsio import replace
    replace(tmp, dst)
    return {"path": dst, "frames": len(frames), "w": w, "h": h, "fps": fps, "alpha": alpha, "bytes": dst.stat().st_size}


def conform_24(src: Path, dst: Path, n16: int) -> list[Path] | None:
    """F16 to 24 fps with RIFE v4.6 (E9: ≈ 2 s for 81 → 121 frames; D102: F16 then RIFE), or None without the binary."""
    import shutil
    import subprocess
    exe = rife_binary()
    if exe is None or n16 < 2:
        return None
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    n24 = round((n16 - 1) * 24 / 16) + 1
    subprocess.run([str(exe), "-i", str(src), "-o", str(dst), "-n", str(n24), "-m", str(exe.parent / "rife-v4.6"), "-f", "%06d.png", "-g", "0"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = sorted(dst.glob("*.png"))
    return out if len(out) == n24 else None
