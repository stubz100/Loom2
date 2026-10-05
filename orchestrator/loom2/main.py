"""Entry point: `python -m loom2.main --port 8765 [--state DIR] [--project PATH]`. Prints one READY line on stdout
once the server accepts connections (the shell's handshake, 06 §1) carrying the port and the per-launch token.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import uvicorn

from .api import create_app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="loom2-orchestrator")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--state", default=None, help="app state dir (default: $LOOM2_STATE or <repo>/.loom2_state)")
    ap.add_argument("--project", default=None, help="open this project at start")
    ap.add_argument("--log-level", default=None)
    a = ap.parse_args(argv)

    def ready(svc) -> None:
        line = {"event": "LOOM2_READY", "port": port, "host": host, "token": svc.app.token, "state": str(svc.app.state_dir),
                "project": str(svc.ws.path) if svc.ws else None}
        sys.stdout.write("LOOM2_READY " + json.dumps(line) + "\n")
        sys.stdout.flush()

    app = create_app(Path(a.state) if a.state else None, Path(a.project) if a.project else None, ready_cb=ready)
    svc = app.state.services
    host = a.host or svc.app.settings.api_host
    port = a.port or svc.app.settings.api_port
    level = (a.log_level or svc.app.settings.log_level).lower()
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level=level, access_log=False))

    def request_shutdown() -> None:
        server.should_exit = True

    app.state.request_shutdown = request_shutdown
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
