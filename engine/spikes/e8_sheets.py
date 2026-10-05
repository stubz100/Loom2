"""Contact sheets for the E8 inpaint bake-off (04 §6).

For each task: an overview sheet (source + every method, half size) and a
detail sheet (full-resolution crops around the repainted region) so the seams,
colour match and identity can be judged side by side.

    engine/.venv/Scripts/python.exe engine/spikes/e8_sheets.py [task-id ...] [--out DIR]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "bench" / "inpaint"
OUT_E8 = ROOT / "engine" / "spikes" / "out" / "e8"
METHODS = ["klein_icm", "klein_base_icm", "klein_lanpaint", "dev_lanpaint", "fill", "qwen_edit"]
LABEL_H = 30
MARGIN = 40


def font(size: int):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tiles_to_sheet(tiles: list[tuple[str, Image.Image]], cols: int) -> Image.Image:
    tw = max(t.width for _, t in tiles)
    th = max(t.height for _, t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + LABEL_H)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    f = font(20)
    for i, (label, t) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + LABEL_H)
        d.text((x + 6, y + 5), label, fill=(255, 255, 255), font=f)
        sheet.paste(t, (x, y + LABEL_H))
    return sheet


def pad_to(img: Image.Image, w: int, h: int) -> Image.Image:
    if img.size == (w, h):
        return img
    canvas = Image.new("RGB", (w, h), (90, 90, 90))
    canvas.paste(img, (0, 0))
    return canvas


def crop_box(task: dict, src_size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = src_size
    if "canvas" in task:                        # outpaint: look at the seam and the new strip
        right = task["canvas"].get("right", 0)
        return (max(0, w - 200), 0, w + right, h)
    if "boxes" in task.get("mask", {}):
        x0, y0, x1, y1 = task["mask"]["boxes"][0]
        return (max(0, x0 - MARGIN), max(0, y0 - MARGIN), min(w, x1 + MARGIN), min(h, y1 + MARGIN))
    return (0, 0, w, h)                         # matte-based masks: whole frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--out", default=str(ROOT / "engine" / "spikes" / "out" / "e8_sheets"))
    a = ap.parse_args()
    spec = json.loads((BENCH / "tasks.json").read_text(encoding="utf-8"))
    src = Image.open(BENCH / spec["source"]).convert("RGB")
    out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
    for task in spec["tasks"]:
        tid = task["id"]
        if a.tasks and tid not in a.tasks:
            continue
        outs = {m: OUT_E8 / f"{tid}_{m}.png" for m in METHODS}
        have = {m: p for m, p in outs.items() if p.exists()}
        if not have:
            print(f"[skip] {tid}: no outputs yet"); continue
        full_w = max(Image.open(p).width for p in have.values())
        full_h = max(Image.open(p).height for p in have.values())
        # overview at half size
        tiles = [("source", pad_to(src, full_w, full_h).resize((full_w // 2, full_h // 2), Image.LANCZOS))]
        for m in METHODS:
            if m in have:
                img = pad_to(Image.open(have[m]).convert("RGB"), full_w, full_h)
                tiles.append((m, img.resize((full_w // 2, full_h // 2), Image.LANCZOS)))
        tiles_to_sheet(tiles, 4).save(out_dir / f"{tid}_overview.png")
        # detail crops at full size
        box = crop_box(task, src.size)
        tiles = [("source", pad_to(src, full_w, full_h).crop(box))]
        for m in METHODS:
            if m in have:
                tiles.append((m, pad_to(Image.open(have[m]).convert("RGB"), full_w, full_h).crop(box)))
        tiles_to_sheet(tiles, 4).save(out_dir / f"{tid}_detail.png")
        print(f"[ok] {tid}: {len(have)} methods, crop {box}")
    print("sheets in", out_dir)


if __name__ == "__main__":
    main()
