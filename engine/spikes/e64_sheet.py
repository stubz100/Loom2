"""E64 (D192): the rooftop FLF task (bench 03) side by side — the bench's start and end frames, then the product's Wan 2.2 Draft FLF clip
and LTX-2.3 Draft clip of the m6 acceptance (2026-10-28, v0.39.0) and H3's clips from out/e64/, each at the same seven moments of its
own length (0, 1/6 … 1), so the end-frame reach, the rise and the identity read at a glance. To out/e64/sheet.png.

    engine/.venv/Scripts/python.exe engine/spikes/e64_sheet.py [h3 clip …]   # default: every run in out/e64/runs.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
BENCH = ROOT / "bench" / "i2v" / "frames"
N = 7
H = 180
LABEL = 26


def font(size: int):
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def frames(path: Path) -> tuple[list[Image.Image], int]:
    with av.open(str(path)) as c:
        all_ = [f.to_image() for f in c.decode(video=0)]
    return [all_[round(k * (len(all_) - 1) / (N - 1))] for k in range(N)], len(all_)


def fit(img: Image.Image) -> Image.Image:
    return img.resize((round(img.width * H / img.height), H))


def h3_label(r: dict | None, p: Path) -> str:
    if not r:
        return f"H3 FL2V · {p.stem}"
    steps = f"{r['steps']} steps" + (" turbo LoRA" if r["lora"] else ", no LoRA")
    return f"H3 FL2V ({r['size'].replace('x', '×')}, {steps}, seed {r['seed']}, {r['engine_s']:.0f} s{' cold' if 'cold' in r.get('note', '') else ''})"


def main() -> None:
    runs = [json.loads(x) for x in (OUT / "e64" / "runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    by_clip = {Path(r["clip"]).name: r for r in runs if r.get("clip")}
    h3 = [Path(p) for p in sys.argv[1:]] or [Path(r["clip"]) for r in runs if r.get("clip") and Path(r["clip"]).is_file()]
    rows: list[tuple[str, list[Image.Image]]] = []
    start, end = Image.open(BENCH / "rooftop-night_s20261004.png").convert("RGB"), Image.open(BENCH / "rooftop-standing_s20261004.png").convert("RGB")
    rows.append(("bench 03: the start and end frames (960×544)", [start] + [Image.new("RGB", start.size, (20, 20, 24))] * (N - 2) + [end]))
    for label, p in [("Wan 2.2 Draft FLF (product, 832×480, 81 f @ 16, 104 s)", OUT / "m6" / "clp_d9159ec9.mp4"),
                     ("LTX-2.3 Draft, end + a beat at 60 (product, 1024×576, 121 f @ 24, 175 s)", OUT / "m6" / "clp_81de7776.mp4")] + \
                    [(h3_label(by_clip.get(p.name), p), p) for p in h3]:
        fs, n = frames(p)
        rows.append((f"{label} · {n} frames", fs))
    tiles = [[fit(i) for i in fs] for _, fs in rows]
    w = max(sum(t.width for t in r) + 4 * (N - 1) for r in tiles)
    sheet = Image.new("RGB", (w, len(rows) * (H + LABEL) + 4), (12, 12, 14))
    dr = ImageDraw.Draw(sheet)
    f = font(16)
    y = 0
    for (label, _), r in zip(rows, tiles):
        dr.text((6, y + 3), label, fill=(255, 210, 80), font=f)
        x = 0
        for t in r:
            sheet.paste(t, (x, y + LABEL)); x += t.width + 4
        y += H + LABEL
    dst = OUT / "e64" / "sheet.png"
    sheet.save(dst)
    print(dst, sheet.size)


if __name__ == "__main__":
    main()
