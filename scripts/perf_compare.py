"""Compare the newest frontend perf baseline with the previous one (D68, ArtCraft P6 §4; ArtCraft's `perf:desktop` method).

    python scripts/perf_compare.py [--dir bench/perf] [--threshold 10] [--fail-over PCT] [NEW.json [OLD.json]]

`npm run perf` (frontend/) writes `bench/perf/<yyyy-mm-dd>.json`. This prints every metric of the newest file beside the previous file's,
with the delta; `*_ms`, `long_frames` and `starved_frames` are better lower, `fps` better higher, the rest is context. A change beyond
`--threshold` percent is marked; `--fail-over PCT` exits 1 when a metric got worse by more than PCT percent (for CI, once baselines
come from one runner class).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def flatten(metrics: dict, prefix: str = "") -> dict[str, float]:
    """`{"a_ms": {"median": 3, "runs": [...]}, "scroll": {"fps": 60}}` → `{"a_ms": 3, "scroll.fps": 60}` (a stat counts by its median)."""
    out: dict[str, float] = {}
    for k, v in metrics.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and "median" in v:
            out[key] = float(v["median"])
        elif isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
    return out


def direction(key: str) -> int:
    """-1: lower is better, +1: higher is better, 0: context."""
    leaf = key.rsplit(".", 1)[-1]
    if leaf.endswith("_ms") or leaf in ("long_frames", "starved_frames"):
        return -1
    if leaf == "fps":
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="NEW [OLD]; default: the two newest files in --dir")
    ap.add_argument("--dir", default=str(REPO / "bench" / "perf"))
    ap.add_argument("--threshold", type=float, default=10.0, help="mark changes beyond this percentage")
    ap.add_argument("--fail-over", type=float, default=None, help="exit 1 when a metric got worse by more than this percentage")
    a = ap.parse_args()
    files = [Path(f) for f in a.files] or sorted(Path(a.dir).glob("*.json"), reverse=True)[:2]
    if not files:
        print(f"no perf files in {a.dir}: run `npm run perf` in frontend/")
        return 1
    new = json.loads(files[0].read_text(encoding="utf-8"))
    old = json.loads(files[1].read_text(encoding="utf-8")) if len(files) > 1 else None
    nm = flatten(new.get("metrics", {}))
    om = flatten(old.get("metrics", {})) if old else {}

    def head(d: dict, f: Path) -> str:
        return f"{f.name}: {d.get('commit')}{' +dirty' if d.get('dirty') else ''} | {d.get('variant')} | {d.get('assets')} assets | {d.get('browser')} | {d.get('machine', {}).get('cpu', '?')}"

    print("new  " + head(new, files[0]))
    if not old:
        print("(no previous file: this is the first baseline)")
    else:
        print("old  " + head(old, files[1]))
        if old.get("assets") != new.get("assets") or old.get("machine") != new.get("machine"):
            print("note: the project size or the machine differs: the deltas are not like for like")
    width = max((len(k) for k in nm), default=10)
    print(f"\n{'metric':<{width}}  {'old':>10}  {'new':>10}  {'delta':>10}  {'%':>7}")
    worse: list[str] = []
    for k, v in nm.items():
        o = om.get(k)
        if o is None:
            print(f"{k:<{width}}  {'-':>10}  {v:>10.1f}")
            continue
        d = v - o
        pct = (d / o * 100) if o else 0.0
        sign = direction(k)
        mark = ""
        if sign and abs(pct) > a.threshold:
            mark = "  better" if d * sign > 0 else "  WORSE"
            if d * sign < 0 and a.fail_over is not None and abs(pct) > a.fail_over:
                worse.append(f"{k} {o:.1f} -> {v:.1f} ({pct:+.0f} %)")
        print(f"{k:<{width}}  {o:>10.1f}  {v:>10.1f}  {d:>+10.1f}  {pct:>+6.0f}%{mark}")
    for k in sorted(set(om) - set(nm)):
        print(f"{k:<{width}}  {om[k]:>10.1f}  {'-':>10}   (gone)")
    if worse:
        print(f"\n{len(worse)} metric(s) worse by more than {a.fail_over} %: " + "; ".join(worse))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
