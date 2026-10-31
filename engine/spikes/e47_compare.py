"""Spike E47, phase 3 (journal 2026-10-31 10:06): the three plates of the market walk's shot (v2, frames 48–144, 65 at 16 fps) on the copy
— O Final 2 (the faces before D170), D Final 3 (the facades named and filled under D170), DU Final 4 (D's facades ×4 by SeedVR2) —
compared on frames 5, 32 and 60: the sharpness (the edge filter's variance) of the band the facade fills (the frame's upper 65 %), and
sheets. Outputs under engine/spikes/out/e47/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e47_compare.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from e47_faces import OUT, PROJECT  # noqa: E402

ARMS = {"O": "fin_2c19f94f", "D": "fin_f786010b", "DU": "fin_dd363e30"}
FRAMES = (5, 32, 60)
BAND = 0.65


def sharp(im: Image.Image) -> float:
    g = im.convert("L").crop((0, 0, im.width, int(im.height * BAND)))
    return round(float(np.asarray(g.filter(ImageFilter.FIND_EDGES), dtype=np.float32).var()), 1)


def main() -> int:
    res: dict = {}
    ims: dict = {}
    for arm, fid in ARMS.items():
        for k in FRAMES:
            im = Image.open(PROJECT / "finals" / fid / "plate" / "frames" / f"{k:04d}.png").convert("RGB")
            ims[(arm, k)] = im
            res.setdefault(arm, {})[k] = sharp(im)
        res[arm]["mean"] = round(sum(res[arm][k] for k in FRAMES) / len(FRAMES), 1)
    print(json.dumps(res))
    (OUT / "plates.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    W, H = 424, 240
    sheet = Image.new("RGB", (W * 3, (H + 18) * len(FRAMES)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for r, k in enumerate(FRAMES):
        for c, arm in enumerate(ARMS):
            sheet.paste(ims[(arm, k)].resize((W, H)), (c * W, r * (H + 18) + 18))
            d.text((c * W + 4, r * (H + 18) + 3), f"{arm} frame {k}: sharpness {res[arm][k]}", fill=(230, 230, 230))
    sheet.save(OUT / "plates_sheet.jpg", quality=86)
    full = Image.new("RGB", (848, (480 + 18) * 3), (20, 20, 20))
    d = ImageDraw.Draw(full)
    for r, arm in enumerate(ARMS):
        full.paste(ims[(arm, 32)], (0, r * 498 + 18))
        d.text((4, r * 498 + 3), f"{arm} frame 32 at 848×480", fill=(230, 230, 230))
    full.save(OUT / "plates_frame32.jpg", quality=90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
