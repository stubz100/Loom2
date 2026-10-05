"""App state and settings (06 §4 `<app state>`): where loom2 keeps `app.json`, the per-launch API token, the
models root and the engine paths. Everything path-like resolves relative to the repo checkout by default so a
fresh clone runs without configuration; the user overrides live in `app.json`.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .fsio import atomic_write_json, read_json_or, utc_now

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SCHEMA_VERSION = 1
Variant = Literal["full", "open"]


def default_state_dir() -> Path:
    env = os.environ.get("LOOM2_STATE")
    if env:
        return Path(env)
    return REPO_ROOT / ".loom2_state"


class EngineSettings(BaseModel):
    python: str = str(REPO_ROOT / "engine" / ".venv" / "Scripts" / "python.exe")
    main: str = str(REPO_ROOT / "engine" / "comfyui" / "main.py")
    extra_model_paths: str = str(REPO_ROOT / "engine" / "extra_model_paths.yaml")
    host: str = "127.0.0.1"
    port: int = 8188
    flags: list[str] = Field(default_factory=lambda: [
        "--disable-auto-launch", "--use-pytorch-cross-attention", "--disable-pinned-memory", "--preview-method", "none",
    ])
    restart_every_jobs: int = 0          # 0 = never; HIP launch-failure mitigation knob (06 §10)
    health_timeout_s: float = 120.0


class Settings(BaseModel):
    schema_version: int = APP_SCHEMA_VERSION
    models_root: str = os.environ.get("LOOM2_MODELS", "F:/loom2-models")
    mounted_model_trees: list[str] = Field(default_factory=lambda: ["D:/comfyui/ComfyUI/models"])
    vram_budget_gb: float = 16.0
    variant: Variant = os.environ.get("LOOM2_VARIANT", "full")  # type: ignore[assignment]
    hf_home: str = os.environ.get("HF_HOME", "F:/HF_HOME")
    engine: EngineSettings = Field(default_factory=EngineSettings)
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    thumbnail_sizes: list[int] = Field(default_factory=lambda: [256, 512, 1024])
    log_level: str = "INFO"


class AppRecord(BaseModel):
    schema_version: int = APP_SCHEMA_VERSION
    settings: Settings = Field(default_factory=Settings)
    last_project: str | None = None
    recents: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now)


class AppState:
    """`<state>/app.json` plus the per-launch token. Settings changes are written atomically."""

    def __init__(self, state_dir: Path | None = None) -> None:
        self.state_dir = Path(state_dir or default_state_dir())
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "logs").mkdir(exist_ok=True)
        self.app_json = self.state_dir / "app.json"
        self.record = AppRecord.model_validate(read_json_or(self.app_json, AppRecord().model_dump()))
        self.token = os.environ.get("LOOM2_TOKEN") or secrets.token_urlsafe(24)

    @property
    def settings(self) -> Settings:
        return self.record.settings

    @property
    def models_root(self) -> Path:
        return Path(self.settings.models_root)

    @property
    def logs_dir(self) -> Path:
        return self.state_dir / "logs"

    def save(self) -> None:
        self.record.updated_at = utc_now()
        atomic_write_json(self.app_json, self.record.model_dump())

    def update_settings(self, patch: dict) -> Settings:
        merged = self.record.settings.model_dump()
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        self.record.settings = Settings.model_validate(merged)
        self.save()
        return self.record.settings

    def touch_project(self, path: Path) -> None:
        s = str(Path(path).resolve())
        self.record.last_project = s
        self.record.recents = [s] + [r for r in self.record.recents if r != s]
        self.record.recents = self.record.recents[:20]
        self.save()
