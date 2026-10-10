"""B24 check: load the production build under the Tauri CSP in headless Edge against a live orchestrator and report
CSP violations (exit 1 on any). Usage: `orchestrator/.venv/Scripts/python.exe scripts/csp_check.py` after `npm run build` in frontend/.
Set CSP_OVERRIDE to a policy string to try another one (e.g. "default-src 'self'" as a negative control).

The Tauri shell cannot be driven headless here, so this serves frontend/dist with the exact `csp` string read from
tauri.conf.json as a response header (same policy; the page origin is the dev origin 127.0.0.1:1420 so CORS lets the app talk to the orchestrator), runs the orchestrator in browser mode
(?token=&port= discovery) with a project, an imported image and a document, and greps Edge's console log for
"Content Security Policy". Screenshots land in engine/spikes/out/csp/ (gitignored).
"""
from __future__ import annotations

import http.server
import json
import os
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
OUT = ROOT / "engine" / "spikes" / "out" / "csp"
CSP = os.environ.get("CSP_OVERRIDE") or json.loads((ROOT / "frontend/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))["app"]["security"]["csp"]
ORCH_PORT = 8769
TOKEN = "cspcheck"


class Static(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if "." not in self.path.split("?")[0].rsplit("/", 1)[-1]:
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, *a):
        pass


def api(method: str, path: str, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{ORCH_PORT}{path}", method=method, headers={"X-Loom-Token": TOKEN, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def main() -> int:
    if not DIST.joinpath("index.html").is_file():
        print("no frontend/dist — run `npm run build` first"); return 2
    if not Path(EDGE).is_file():
        print("Edge not found"); return 2
    tmp = Path(tempfile.mkdtemp(prefix="loom2-csp-"))
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([str(ROOT / "orchestrator/.venv/Scripts/python.exe"), "-m", "loom2.main", "--port", str(ORCH_PORT), "--state", str(tmp / "state")],
                            cwd=str(ROOT / "orchestrator"), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # 1420 is the Vite dev origin the orchestrator's CORS allowlist accepts (api.py DEV_ORIGINS); the Vite server must be down
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 1420), Static)
    sport = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        else:
            print("orchestrator did not come up"); return 1
        api("POST", "/project", {"path": str(tmp / "proj"), "name": "CSP", "size_cap_gb": 10})
        src = next((ROOT / "bench" / "inpaint").glob("*.png"))
        asset = api("POST", "/assets/import", {"paths": [str(src)]})["items"][0]
        doc = api("POST", "/documents", {"from_asset": asset["id"]})
        base = f"http://127.0.0.1:{sport}/?token={TOKEN}&port={ORCH_PORT}"
        pages = {"catalogue": base + "&suite=catalogue", "edit": base + f"&suite=edit&doc={doc['id']}", "generate": base + "&suite=generate",
                 "generate-model": base + "&suite=generate&tab=model", "edit-ai": base + f"&suite=edit&doc={doc['id']}&tab=ai",
                 "edit-wasm": base + f"&suite=edit&doc={doc['id']}&wasmprobe=1"}             # D59: the smart-select Worker's WebAssembly
        violations: dict[str, list[str]] = {}
        for name, url in pages.items():
            OUT.mkdir(parents=True, exist_ok=True)
            shot = OUT / f"{name}.png"
            r = subprocess.run([EDGE, "--headless=new", "--window-size=1600,1000", "--hide-scrollbars", "--enable-logging=stderr", "--v=0",
                                "--virtual-time-budget=15000", "--enable-unsafe-webgpu", f"--screenshot={shot}", url],
                               capture_output=True, text=True, timeout=180, errors="replace")
            log = r.stderr + r.stdout
            hits = sorted({m.strip() for m in re.findall(r'"(Refused to [^"]+|[^"]*Content Security Policy[^"]*)"', log)})
            errors = [l for l in log.splitlines() if "CONSOLE" in l and ("Uncaught" in l or "TypeError" in l or "Failed to fetch" in l)]
            if name == "edit-wasm" and "smart-select worker ready" not in log:
                hits.append("the smart-select Worker did not report its WebAssembly module ready" + (" — " + next((l[-200:] for l in log.splitlines() if "smart-select" in l), "") if "smart-select" in log else ""))
            violations[name] = hits
            print(f"[{name}] screenshot {shot.stat().st_size if shot.exists() else 0} bytes · CSP hits {len(hits)} · js errors {len(errors)}")
            for h in hits[:8]:
                print("   ", h[:220])
            for e in errors[:5]:
                print("   ", e[-220:])
        ok = not any(violations.values())
        print("CSP:", "clean" if ok else "VIOLATIONS")
        return 0 if ok else 1
    finally:
        httpd.shutdown()
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=15)
        except Exception:
            orch.kill()


if __name__ == "__main__":
    sys.exit(main())
