"""Frame sheets for the i2v spikes (E4 Wan 2.2, E5 LTX-2.3) — 04 §6 scoring aid.

For every result row: the bench start (and end) frame(s) followed by evenly spaced frames of the clip,
tiled with labels, so identity drift, motion plausibility and end-frame reach can be judged at a glance.

    engine/.venv/Scripts/python.exe engine/spikes/i2v_sheets.py [--results engine/spikes/out/e4_results.jsonl]
                                                                 [--out DIR] [--samples 6] [--scale 0.5]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench" / "i2v"
LABEL_H = 28


def font(size: int):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def clip_frames(path: Path, wanted: list[int]) -> dict[int, Image.Image]:
    out: dict[int, Image.Image] = {}
    with av.open(str(path)) as c:
        for i, fr in enumerate(c.decode(video=0)):
            if i in wanted:
                out[i] = fr.to_image()
            if i >= max(wanted):
                break
    return out


def sheet(tiles: list[tuple[str, Image.Image]], cols: int, scale: float) -> Image.Image:
    tiles = [(l, t.resize((int(t.width * scale), int(t.height * scale)), Image.LANCZOS)) for l, t in tiles]
    tw = max(t.width for _, t in tiles); th = max(t.height for _, t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw, rows * (th + LABEL_H)), (40, 40, 40))
    d = ImageDraw.Draw(img); f = font(18)
    for i, (label, t) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + LABEL_H)
        d.text((x + 6, y + 4), label, fill=(255, 255, 255), font=f)
        img.paste(t, (x, y + LABEL_H))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "engine" / "spikes" / "out" / "e4_results.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--samples", type=int, default=6)
    ap.add_argument("--scale", type=float, default=0.5)
    a = ap.parse_args()
    results = Path(a.results)
    out_dir = Path(a.out) if a.out else results.parent / (results.stem.replace("_results", "") + "_sheets")
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in spec["tasks"]}
    rows = [json.loads(l) for l in results.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows:
        if r.get("status") != "success" or not r.get("outputs"):
            print(f"[skip] {r.get('task')} {r.get('recipe')}: {r.get('status')} {r.get('error')}"); continue
        clip = Path(r["outputs"][0])
        if not clip.exists():
            print(f"[skip] {r['task']}: missing {clip}"); continue
        n = int(r.get("frames") or 81)
        idx = sorted({round(i * (n - 1) / (a.samples - 1)) for i in range(a.samples)})
        frames = clip_frames(clip, idx)
        tiles: list[tuple[str, Image.Image]] = []
        task = tasks.get(r["task"], {})
        for key, val in task.items():                       # bench reference frames (start / end)
            if isinstance(val, str) and val.lower().endswith(".png") and (BENCH / val).exists():
                tiles.append((f"bench {key}", Image.open(BENCH / val).convert("RGB")))
        for i in idx:
            if i in frames:
                tiles.append((f"f{i} ({i / (r.get('fps') or 16):.1f}s)", frames[i]))
        cols = 4 if len(tiles) > 6 else len(tiles)
        parts = [r['task'], r.get('recipe') or '', (r.get('format') or '') if (r.get('format') or 'gguf') != 'gguf' or not r.get('recipe') else '']
        name = "_".join(p for p in parts if p) + ".png"   # e4: task_recipe[_fp8]; e5: task_format
        sheet(tiles, cols, a.scale).save(out_dir / name)
        print(f"[ok] {name}: refs {[l for l, _ in tiles if l.startswith('bench')]}, frames {idx}")
    print("sheets in", out_dir)


if __name__ == "__main__":
    main()
