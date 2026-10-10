"""Export the orchestrator's OpenAPI document to frontend/src/api/openapi.json (D38). `npm run api:types` then regenerates
schema.d.ts from it; CI runs both and fails when either file differs from the commit.

    orchestrator/.venv/Scripts/python.exe scripts/export_openapi.py            # write
    orchestrator/.venv/Scripts/python.exe scripts/export_openapi.py --check    # exit 1 when the committed file is stale

The document must not depend on the machine: defaults read from the environment (LOOM2_VARIANT, LOOM2_MODELS, HF_HOME) are
pinned before `loom2` is imported, and the checkout path inside defaults (the engine's python / main paths) becomes `<repo>`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "frontend" / "src" / "api" / "openapi.json"


def render() -> str:
    os.environ["LOOM2_VARIANT"] = "full"
    for name in ("LOOM2_MODELS", "HF_HOME"):
        os.environ.pop(name, None)
    sys.path.insert(0, str(REPO / "orchestrator"))
    from loom2.api import create_app   # noqa: E402 — after the environment is pinned
    with tempfile.TemporaryDirectory() as state:
        schema = create_app(Path(state)).openapi()
    text = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    for spelling in {str(REPO), REPO.as_posix()}:
        text = text.replace(json.dumps(spelling)[1:-1], "<repo>")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="compare with the committed file instead of writing it")
    args = ap.parse_args()
    text = render()
    current = OUT.read_bytes().decode("utf-8").replace("\r\n", "\n") if OUT.exists() else ""
    if args.check:
        stale = current != text
        print(f"export_openapi: {OUT.relative_to(REPO).as_posix()} is {'STALE — run scripts/export_openapi.py and npm run api:types' if stale else 'current'}")
        return 1 if stale else 0
    OUT.write_bytes(text.encode("utf-8"))
    print(f"export_openapi: wrote {OUT.relative_to(REPO).as_posix()} ({len(json.loads(text)['paths'])} paths, "
          f"{len(json.loads(text)['components']['schemas'])} schemas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
