"""D40: compose.py against Photoshop's own composites (the merged image stored in each PSD) over the pinned psd-tools corpus.

    python scripts/fetch_corpus.py                                      # once: bench/corpus/psd-tools/ (gitignored)
    orchestrator/.venv/Scripts/python.exe -m pytest orchestrator -m corpus -s   # needs the `oracle` extra (psd-tools)

Out-of-scope files (vector masks, fill layers, effects, adjustments loom2 renders differently by design, …) are listed with their
reason, not failed. The pass count may not drop below bench/corpus/psd-tools.floor.json ("raise, never lower").
"""
import json
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "bench" / "corpus" / "psd-tools"
MANIFEST = REPO / "bench" / "corpus" / "psd-tools.sha256"
FLOOR = REPO / "bench" / "corpus" / "psd-tools.floor.json"

pytestmark = pytest.mark.corpus


def _unavailable(request, why: str) -> None:
    if "corpus" in (request.config.getoption("markexpr") or ""):
        pytest.fail(f"{why} (selected with -m corpus)")
    pytest.skip(why)


def test_compose_matches_photoshop(request):
    try:
        import psd_tools  # noqa: F401
    except ImportError:
        _unavailable(request, "psd-tools missing: uv sync --project orchestrator --extra dev --extra oracle")
    names = [line.split(None, 1)[1].strip() for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    if not all((CORPUS / n).is_file() for n in names):
        _unavailable(request, "psd-tools corpus missing: python scripts/fetch_corpus.py")
    from psd_oracle import run_file

    results = [run_file(CORPUS / n, n) for n in names]
    floor = json.loads(FLOOR.read_text(encoding="utf-8"))
    counts = Counter(r.status for r in results)
    print(f"\ncompose.py vs Photoshop: {dict(counts)} (floor {floor['pass_floor']})")
    for r in results:
        if r.status in ("pass", "fail", "error"):
            print(f"  {r.status:5} {r.name:52} max {r.max_diff:5.1f} p99 {r.p99:5.1f} {r.detail}")
    errors = [f"{r.name}: {r.detail}" for r in results if r.status == "error"]
    assert not errors, "converter or compositor crashed: " + "; ".join(errors)
    unexpected = [r.name for r in results if r.status == "fail" and r.name not in floor["known_failures"]]
    assert counts["pass"] >= floor["pass_floor"], f"{counts['pass']} passes < floor {floor['pass_floor']}; new failures: {unexpected}"
    assert not unexpected, f"in-scope files failing that are not known failures: {unexpected}"
