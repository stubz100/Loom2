"""Check the agent docs (D35): every CLAUDE.md / AGENTS.md carries a "Verified at <commit> on <date>" line, and every
backticked repository path in them still exists.

    orchestrator/.venv/Scripts/python.exe scripts/agents_check.py      # exit 1 on any finding (CI runs it)

A backticked token counts as a path when it looks like one (segments joined by "/", no spaces, wildcards or <placeholders>)
and its first segment exists at the repository root or next to the doc. Paths inside git submodules are skipped: CI checks
the repository out without them.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", ".venv", "dist", "target", "__pycache__", ".loom2_state"}
VERIFIED = re.compile(r"^Verified at [0-9a-f]{7,40} on \d{4}-\d{2}-\d{2}\b", re.M)
TICKS = re.compile(r"`([^`\n]+)`")
PATHLIKE = re.compile(r"^\.?[\w.\-]+(/[\w.\-]+)+/?$")


def agent_docs() -> list[Path]:
    found = []
    for path in REPO.rglob("*.md"):
        if path.name not in ("AGENTS.md", "CLAUDE.md"):
            continue
        rel = path.relative_to(REPO)
        if any(part in SKIP_DIRS for part in rel.parts) or is_submodule(rel):
            continue
        found.append(path)
    return sorted(found)


def check(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    rel = doc.relative_to(REPO).as_posix()
    problems = [] if VERIFIED.search(text) else [f"{rel}: missing a 'Verified at <commit> on <YYYY-MM-DD>' line"]
    for token in sorted(set(TICKS.findall(text))):
        target = resolve(token, doc.parent)
        if target is None:
            continue
        if not target.exists():
            problems.append(f"{rel}: `{token}` does not exist")
    return problems


def resolve(token: str, doc_dir: Path) -> Path | None:
    """The path a token refers to, or None when the token is not a checkable repository path."""
    token = token.strip()
    if not PATHLIKE.match(token):
        return None
    first = token.split("/", 1)[0]
    for base in (REPO, doc_dir):
        if (base / first).exists():
            candidate = base / token
            return None if is_submodule(candidate.relative_to(REPO)) else candidate
    return None


def is_submodule(rel: Path) -> bool:
    posix = rel.as_posix()
    return any(posix == sub or posix.startswith(sub + "/") for sub in submodules())


_SUBMODULES: list[str] | None = None


def submodules() -> list[str]:
    global _SUBMODULES
    if _SUBMODULES is None:
        gm = REPO / ".gitmodules"
        text = gm.read_text(encoding="utf-8") if gm.exists() else ""
        _SUBMODULES = [m.strip() for m in re.findall(r"^\s*path\s*=\s*(.+)$", text, re.M)]
    return _SUBMODULES


def main() -> int:
    docs = agent_docs()
    if not docs:
        print("agents_check: no CLAUDE.md / AGENTS.md found")
        return 1
    problems = [p for doc in docs for p in check(doc)]
    for p in problems:
        print(p)
    print(f"agents_check: {len(docs)} docs, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
