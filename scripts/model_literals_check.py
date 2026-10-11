"""D65 (ArtCraft P1): model knowledge lives in `orchestrator/loom2/models/specs/*.toml` (and the roster). This check fails when a quoted
roster id — "klein-9b", 'wan22-i2v-high-fp8', … — appears in the orchestrator's or the frontend's code anywhere else.

Exempt: the specs, `roster.py` (the weights catalogue), tests, the generated API files (`frontend/src/api/schema.d.ts`,
`openapi.json`, which carry examples from the schema) and comments.

    orchestrator/.venv/Scripts/python.exe scripts/model_literals_check.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "orchestrator"))

from loom2.roster import ROSTER  # noqa: E402

SOURCES = [(REPO / "orchestrator" / "loom2", ("*.py",)), (REPO / "frontend" / "src", ("*.ts", "*.tsx"))]
EXEMPT = {"orchestrator/loom2/roster.py", "frontend/src/api/schema.d.ts", "frontend/src/api/openapi.json"}
EXEMPT_DIRS = ("orchestrator/loom2/models/specs/",)


def strip_comment(line: str, py: bool) -> str:
    """Drop a trailing comment (good enough for this codebase: no '#' or '//' inside the quoted ids we look for)."""
    if py:
        return line.split("#", 1)[0] if '"' not in line.split("#", 1)[0][-1:] else line
    i = line.find("//")
    return line if i < 0 or line[:i].count("'") % 2 or line[:i].count('"') % 2 or line[:i].count("`") % 2 else line[:i]


def main() -> int:
    ids = sorted({e.id for e in ROSTER}, key=len, reverse=True)
    pat = re.compile(r"""(["'`])(""" + "|".join(re.escape(i) for i in ids) + r""")\1""")
    problems: list[str] = []
    for root, globs in SOURCES:
        for g in globs:
            for p in root.rglob(g):
                rel = p.relative_to(REPO).as_posix()
                if rel in EXEMPT or rel.startswith(EXEMPT_DIRS) or "/tests/" in rel or "node_modules" in rel:
                    continue
                py = p.suffix == ".py"
                in_doc = False
                for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    s = line.strip()
                    if py and s.count('"""') % 2 == 1:
                        in_doc = not in_doc
                        continue
                    if in_doc or s.startswith(("#", "//", "*", "/*")):
                        continue
                    m = pat.search(strip_comment(line, py))
                    if m:
                        problems.append(f"{rel}:{n}: model id {m.group(2)!r} in code — read it from the registry / capabilities (D65)")
    for pr in problems:
        print("FAIL", pr)
    print(f"model_literals_check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
