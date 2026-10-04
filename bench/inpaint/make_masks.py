"""Generate the E8 inpaint bench masks from tasks.json (white = repaint, black = keep, soft edge by feather).

Run:  engine/.venv/Scripts/python.exe bench/inpaint/make_masks.py
Writes bench/inpaint/masks/<task-id>.png and a preview overlay bench/inpaint/masks/<task-id>.preview.jpg.
Tasks with mask.from == "birefnet" or a canvas extension get no file here (their mask comes from the matting
model / canvas size at run time).
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
spec = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
src_path = (HERE / spec["source"]).resolve()
w, h = spec["size"]
out = HERE / "masks"
out.mkdir(exist_ok=True)
src = Image.open(src_path).convert("RGB") if src_path.exists() else None
if src is not None and src.size != (w, h):
    raise SystemExit(f"source size {src.size} != spec size {(w, h)}")

for t in spec["tasks"]:
    m = t.get("mask")
    if not m or "boxes" not in m:
        print(f"{t['id']}: no static mask ({'canvas' if 'canvas' in t else m.get('from')})")
        continue
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for x0, y0, x1, y1 in m["boxes"]:
        d.rectangle([x0, y0, x1, y1], fill=255)
    if m.get("feather"):
        mask = mask.filter(ImageFilter.GaussianBlur(m["feather"]))
    mask.save(out / f"{t['id']}.png")
    if src is not None:
        overlay = Image.new("RGB", (w, h), (255, 0, 0))
        prev = Image.composite(overlay, src, mask.point(lambda v: int(v * 0.55)))
        prev.save(out / f"{t['id']}.preview.jpg", quality=85)
    print(f"{t['id']}: mask {mask.size}, boxes {m['boxes']}, feather {m.get('feather', 0)}")
print("done ->", out)
