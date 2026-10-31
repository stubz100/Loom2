"""Spike E46d (M12; journal 2026-10-31 07:38): the facade lead reordered, the elevation first ("A flat elevation of {material}, seen square
on …"), with a material as an author would write it — two seeds of the right fronts on E46b's copy, E46c's route and sheet.
Outputs under engine/spikes/out/e46d/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e46d_facade.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e46c_facade as c  # noqa: E402

c.OUT = c.ROOT / "engine" / "spikes" / "out" / "e46d"
c.ARMS = {"M": "fish market stalls: counters of fish on ice, crates below, lamps above"}

if __name__ == "__main__":
    raise SystemExit(c.main())
