"""E55 (W22, CPU only, read-only on the walkthrough's project): does matching a filled face's colours to its seen part across the seam close
the tone step the street showed (the projected road a darker trapezoid against the filled cobbles)?

For each filled face of the Last Ferry's Town street and Harbour pier: the texture (seen + filled), the coverage, the fill mask as the app
cuts it (place_sets.fill_mask). The seam bands: the seen pixels within BAND px of the mask, and the filled pixels within BAND px of it. The
step = ΔE (CIE76, Lab means) between the two bands. Matched: the filled region's Lab statistics mapped so its seam band matches the seen
band (Lab means and spreads, as tone.match_colour maps them, measured on the filled band, applied to the whole filled region). Writes before/after crops to engine/spikes/out/e55.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e55_seam.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
from loom2.catalogue import Catalogue  # noqa: E402
from loom2.place_sets import fill_mask, unseen_cos  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.tone import lab_stats, lab_to_srgb, srgb_to_lab  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402

PROJECT = Path("F:/loom2-projects/ux-walk2-last-ferry")
OUT = ROOT / "engine" / "spikes" / "out" / "e55"
BAND = 12


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    out = m.copy()
    for _ in range(r):
        out[1:] |= out[:-1]; out[:-1] |= out[1:]; out[:, 1:] |= out[:, :-1]; out[:, :-1] |= out[:, 1:]
    return out


def step(rgb: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    lab = srgb_to_lab(rgb)
    mu_a, _ = lab_stats(lab, a)
    mu_b, _ = lab_stats(lab, b)
    return float(np.linalg.norm(mu_a - mu_b))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ws = Workspace(PROJECT)
    cat, st = Catalogue(ws), StoryStore(ws)
    rows = []
    for p in st.profiles():
        if p.cls != "place":
            continue
        ps = p.version(p.current).place_set
        if ps is None:
            continue
        for f in ps.faces:
            if not f.filled or not f.coverage_asset_id or f.texture_asset_id == f.baked_asset_id:
                continue
            tex = np.asarray(Image.open(cat.abs_path(cat.get(f.texture_asset_id))).convert("RGB"))
            cov = np.asarray(Image.open(cat.abs_path(cat.get(f.coverage_asset_id))).convert("RGB"))
            if cov.shape[:2] != tex.shape[:2]:
                cov = np.asarray(Image.fromarray(cov).resize((tex.shape[1], tex.shape[0]), Image.Resampling.NEAREST))
            mask = fill_mask(cov, unseen_cos(f.id, ps.kind))
            if mask.mean() < 0.02 or mask.mean() > 0.98:
                rows.append({"place": p.name, "face": f.id, "filled": round(float(mask.mean()), 3), "note": "no seam to match"})
                continue
            seen_band = dilate(mask, BAND) & ~mask
            fill_band = mask & ~dilate(~mask, BAND)
            before = step(tex, seen_band, fill_band)
            # the filled region's stats, measured on its seam band, mapped onto the seen band's
            lab = srgb_to_lab(tex)
            mu_f, sd_f = lab_stats(lab, fill_band)
            mu_s, sd_s = lab_stats(lab, seen_band)
            scale = np.clip(sd_s / np.maximum(sd_f, 1e-6), 0.5, 2.0)
            out = tex.copy()
            m = lab_to_srgb((lab - mu_f) * scale + mu_s)
            out[mask] = m[mask]
            after = step(out, seen_band, fill_band)
            rows.append({"place": p.name, "face": f.id, "filled": round(float(mask.mean()), 3), "step_before": round(before, 2), "step_after": round(after, 2)})
            h = tex.shape[0]
            pair = np.concatenate([tex, np.full((h, 8, 3), 255, np.uint8), out], axis=1)
            Image.fromarray(pair).save(OUT / f"{p.name.replace(' ', '_')}_{f.id}.jpg", quality=88)
    (OUT / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
