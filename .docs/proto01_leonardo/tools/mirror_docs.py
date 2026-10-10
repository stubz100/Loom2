"""Re-mirror the Leonardo.Ai API documentation into ../source/.

Usage (from the repo root, orchestrator venv or any Python 3.11+):

    python -I .docs/proto01_leonardo/tools/mirror_docs.py

What it does:
1. downloads the two readme.io indexes (`llms.txt` for the current docs, `llms-v1.0.txt` for the v1 reference that the
   current index leaves out),
2. downloads every page they list as markdown into source/{docs,recipes,reference,reference-v1}/,
3. extracts the OpenAPI definitions embedded in the v2 reference pages into source/openapi-v2-*.json.

Third-party content: the files under source/ are Leonardo.Ai's documentation, kept verbatim as a local reference.
Standard library only. Pages that answer 429 are retried with a back-off.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "source"
INDEXES = {
    "llms.txt": "https://docs.leonardo.ai/llms.txt",
    "llms-v1.0.txt": "https://docs.leonardo.ai/v1.0/llms.txt",
}
# v1 reference pages the v1.0 index does not list but loom2 needs (account balance, cost estimate)
EXTRA = [
    "https://docs.leonardo.ai/v1.0/reference/getuserself.md",
    "https://docs.leonardo.ai/v1.0/reference/pricingcalculator.md",
]
PAGE = re.compile(r"https://docs\.leonardo\.ai/(?:v1\.0/)?(docs|reference|recipes)/[^)\s]+\.md")


def fetch(url: str, tries: int = 5) -> bytes:
    for attempt in range(tries):
        try:
            # the docs host answers 403 to urllib's default user agent
            req = urllib.request.Request(url, headers={"User-Agent": "loom2-docs-mirror/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


def target(url: str) -> Path | None:
    section = url.split("docs.leonardo.ai/", 1)[1].split("/")
    v1 = section[0] == "v1.0"
    kind = section[1] if v1 else section[0]
    if v1 and kind != "reference":
        return None  # v1.0 guides duplicate the current ones
    folder = "reference-v1" if v1 else kind
    return SOURCE / folder / url.rsplit("/", 1)[1]


def extract_openapi() -> None:
    for page in sorted((SOURCE / "reference").glob("*.md")):
        match = re.search(r"```json\n(.*?)\n```", page.read_text(encoding="utf-8"), re.S)
        if not match:
            continue
        spec = json.loads(match.group(1))
        out = SOURCE / f"openapi-v2-{page.stem}.json"
        out.write_text(json.dumps(spec, indent=1), encoding="utf-8")
        print(f"openapi  {out.name}: {', '.join(spec.get('paths', {}))}")


def main() -> int:
    failures = 0
    urls: set[str] = set()
    for name, url in INDEXES.items():
        body = fetch(url)
        (SOURCE / name).write_bytes(body)
        urls.update(m.group(0) for m in PAGE.finditer(body.decode("utf-8")))
    urls.update(EXTRA)
    for url in sorted(urls):
        out = target(url)
        if out is None:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_bytes(fetch(url))
        except Exception as exc:  # noqa: BLE001 — report and continue
            failures += 1
            print(f"FAIL {url}: {exc}", file=sys.stderr)
        time.sleep(0.3)
    extract_openapi()
    print(f"{len(urls)} pages listed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
