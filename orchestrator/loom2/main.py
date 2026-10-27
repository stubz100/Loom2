"""Entry point: `python -m loom2.main --port 8765 [--state DIR] [--project PATH] [--parent-pid PID]`. Prints one READY line on stdout
once the server accepts connections (the shell's handshake, 06 §1) carrying the port and the per-launch token. V53: the line goes out
after uvicorn has bound its socket, not from the lifespan before it (the shell's first request met ECONNREFUSED for milliseconds).
V54: with `--parent-pid` the orchestrator ends when that process is gone (the e2e runner has no job object).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import uvicorn

from .api import create_app


class ReadyServer(uvicorn.Server):
    """uvicorn's server that prints LOOM2_READY once `startup` has run the lifespan *and* bound the socket."""

    def __init__(self, config: uvicorn.Config, ready_line: dict | None = None) -> None:
        super().__init__(config)
        self.ready_line: dict | None = ready_line

    async def startup(self, sockets=None) -> None:
        await super().startup(sockets)
        if self.started and self.ready_line is not None:
            sys.stdout.write("LOOM2_READY " + json.dumps(self.ready_line) + "\n")
            sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="loom2-orchestrator")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--state", default=None, help="app state dir (default: $LOOM2_STATE or <repo>/.loom2_state)")
    ap.add_argument("--project", default=None, help="open this project at start")
    ap.add_argument("--log-level", default=None)
    ap.add_argument("--parent-pid", type=int, default=None, help="exit when this process is gone (V54: a runner without a job object)")
    a = ap.parse_args(argv)
    server: ReadyServer | None = None

    def ready(svc) -> None:                                   # the lifespan's call: the line is kept and printed once the socket is bound (V53)
        line = {"event": "LOOM2_READY", "port": port, "host": host, "token": svc.app.token, "media_key": svc.app.media_key, "state": str(svc.app.state_dir),
                "project": str(svc.ws.path) if svc.ws else None}
        if server is not None:
            server.ready_line = line

    app = create_app(Path(a.state) if a.state else None, Path(a.project) if a.project else None, ready_cb=ready,
                     variant=os.environ.get("LOOM2_VARIANT"))       # C3: the shell's build variant (D26) is not a setting
    svc = app.state.services
    host = a.host or svc.app.settings.api_host
    port = a.port or svc.app.settings.api_port
    level = (a.log_level or svc.app.settings.log_level).lower()
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = ReadyServer(uvicorn.Config(app, host=host, port=port, log_level=level, access_log=False))

    def request_shutdown() -> None:
        server.should_exit = True

    app.state.request_shutdown = request_shutdown
    if a.parent_pid:
        from .parent import watch_parent
        watch_parent(a.parent_pid, request_shutdown)
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
