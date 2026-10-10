"""Version and build facts for `/version` and Settings · About (D36).

The installers contain the shell only; the orchestrator and the engine run from a checkout (README), so two builds can
differ: the shell reports the commit it was built from (baked in at compile time, handed over as LOOM2_SHELL_* variables)
and the orchestrator reports the commit of the checkout it runs from. Git lookups are cached for the process lifetime.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from . import __version__
from .catalogue import ASSET_SCHEMA_VERSION, INDEX_SCHEMA_VERSION
from .config import APP_SCHEMA_VERSION, REPO_ROOT
from .documents import DOC_SCHEMA_VERSION
from .groups import GROUP_SCHEMA_VERSION
from .queue import QUEUE_SCHEMA_VERSION
from .workspace import PROJECT_SCHEMA_VERSION

SCHEMAS = {"app": APP_SCHEMA_VERSION, "project": PROJECT_SCHEMA_VERSION, "asset": ASSET_SCHEMA_VERSION,
           "index": INDEX_SCHEMA_VERSION, "queue": QUEUE_SCHEMA_VERSION, "document": DOC_SCHEMA_VERSION,
           "group": GROUP_SCHEMA_VERSION}


def version_info(root: Path = REPO_ROOT) -> dict:
    """Everything except the running engine (the caller adds it): app version, checkout commit, shell build, pins."""
    return {
        "app": app_version(root),
        "orchestrator": __version__,
        "git": git_info(str(root)),
        "shell": shell_info(),
        "engine_pin": engine_pin(str(root)),
        "nodes": node_pins(root),
        "schemas": SCHEMAS,
    }


def app_version(root: Path = REPO_ROOT) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip() or __version__
    except OSError:
        return __version__


def shell_info() -> dict | None:
    """What the Tauri shell was built from (None when the orchestrator runs without the shell, e.g. browser dev)."""
    version = os.environ.get("LOOM2_SHELL_VERSION")
    if not version:
        return None
    epoch = os.environ.get("LOOM2_SHELL_BUILD_EPOCH", "")
    built = datetime.fromtimestamp(int(epoch), timezone.utc).isoformat(timespec="seconds") if epoch.isdigit() else None
    return {"version": version, "git_sha": os.environ.get("LOOM2_SHELL_GIT_SHA") or None, "build_time": built}


@lru_cache(maxsize=4)
def git_info(root: str) -> dict | None:
    sha = _git(root, "rev-parse", "--short", "HEAD")
    if sha is None:
        return None
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    return {"sha": sha, "dirty": bool(status), "describe": _git(root, "describe", "--tags", "--always", "--dirty")}


@lru_cache(maxsize=4)
def engine_pin(root: str) -> str | None:
    """The pinned ComfyUI tag (the engine submodule's `git describe`)."""
    comfy = Path(root) / "engine" / "comfyui"
    return _git(str(comfy), "describe", "--tags", "--always") if comfy.exists() else None


def node_pins(root: Path = REPO_ROOT) -> list[dict]:
    """Custom node pins from engine/nodes.lock: `name  repo  commit  date` lines."""
    try:
        text = (root / "engine" / "nodes.lock").read_text(encoding="utf-8")
    except OSError:
        return []
    pins = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and not line.startswith("#") and re.fullmatch(r"[0-9a-f]{7,40}", parts[2]):
            pins.append({"name": parts[0], "repo": parts[1], "commit": parts[2], "date": parts[3]})
    return pins


def _git(cwd: str, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None
