"""App state and settings (06 §4 `<app state>`): where loom2 keeps `app.json`, the per-launch API token, the
models root and the engine paths. Everything path-like resolves relative to the repo checkout by default so a
fresh clone runs without configuration; the user overrides live in `app.json`.
"""
from __future__ import annotations

import os
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .fsio import atomic_write_json, new_id, read_json_or, utc_now

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SCHEMA_VERSION = 1
Variant = Literal["full", "open"]


def default_state_dir() -> Path:
    env = os.environ.get("LOOM2_STATE")
    if env:
        return Path(env)
    return REPO_ROOT / ".loom2_state"


class EngineSettings(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    python: str = str(REPO_ROOT / "engine" / ".venv" / "Scripts" / "python.exe")
    main: str = str(REPO_ROOT / "engine" / "comfyui" / "main.py")
    extra_model_paths: str = str(REPO_ROOT / "engine" / "extra_model_paths.yaml")
    host: str = "127.0.0.1"
    port: int = 8188
    flags: list[str] = Field(default_factory=lambda: [
        "--disable-auto-launch", "--use-pytorch-cross-attention", "--disable-pinned-memory", "--preview-method", "none",
    ])
    restart_every_jobs: int = 0          # 0 = never; HIP launch-failure mitigation knob (06 §10)
    stall_timeout_s: int = 420           # no engine event for this long while a job runs → job fails, engine restarts, queue pauses (TDR 2026-10-05)
    reserve_vram_gb: float = 1.5         # ComfyUI --reserve-vram: headroom for the desktop and the editor's WebGPU canvas on the same card
    vram_headroom_gb: float = 5.0        # ComfyUI --vram-headroom: DynamicVRAM keeps this much more free for the job's activations; without it the
                                         # driver spills them to shared memory and FLUX.2 dev with 4–6 references ran 4× slower (2026-10-18 rig)
    health_timeout_s: float = 120.0


class TrainerSettings(BaseModel):
    """LT2 (18 §3c): ai-toolkit in its own venv — never the engine's (scripts/trainer-setup.ps1)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    python: str = str(REPO_ROOT / "trainers" / ".venv" / "Scripts" / "python.exe")
    run: str = str(REPO_ROOT / "trainers" / "ai-toolkit" / "run.py")
    cwd: str = str(REPO_ROOT / "trainers" / "ai-toolkit")
    vae: str = "ai-toolkit/flux2_vae"      # the hub repo whose ae.safetensors the trainer reads (E16; loom2's own repack has diffusers names)
    quantize: str = "qfloat8"              # Quanto on the transformer and the encoder (E16: 13.6 GB on the 4B base)


class VoicesSettings(BaseModel):
    """CN2 (19 §3b): the TTS tiers in their own venv `voices/.venv` — never the engine's (scripts/voices-setup.ps1, voices/AGENTS.md)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    python: str = str(REPO_ROOT / "voices" / ".venv" / "Scripts" / "python.exe")
    run: str = str(REPO_ROOT / "voices" / "tts.py")
    draft_model: str = "hexgrad/Kokoro-82M"                  # Apache-2.0; the CPU beside a running engine (E20: 2.5–4.7 s a line)
    cloning_model: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"     # Apache-2.0; the GPU with the engine stopped (E20: 3–5 s a line at a 2.6 GB peak)


class LipsyncSettings(BaseModel):
    """D118 (AE4d, from E29b): the lip-sync model as a tool — LatentSync 1.5 in its own venv `tools/lipsync/.venv` with the checkout
    `tools/lipsync/LatentSync` (scripts/lipsync-setup.ps1, tools/lipsync/AGENTS.md); never the engine's. The weights are OpenRAIL++: `full` only."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    python: str = str(REPO_ROOT / "tools" / "lipsync" / ".venv" / "Scripts" / "python.exe")
    run: str = str(REPO_ROOT / "tools" / "lipsync" / "sync.py")
    checkout: str = str(REPO_ROOT / "tools" / "lipsync" / "LatentSync")
    steps: int = 20                                          # E29b: 20 steps at guidance 1.5 — the model's own defaults
    guidance: float = 1.5


class EffectCraftSettings(BaseModel):
    """AE1 (proto01_animate 20 §2, D114): the animation editor's engine — the pinned `effectcraft-cli` (engine/effectcraft.pin.json, built by
    scripts/build_effectcraft.py into engine/tools/, never in git) driven as one MCP session beside the orchestrator (loom2/effectcraft.py).
    A `.py` runs under the orchestrator's interpreter (the tests' fake)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    cli: str = str(REPO_ROOT / "engine" / "tools" / "effectcraft" / "effectcraft-cli.exe")
    threads: int = 8            # RAYON_NUM_THREADS: E27 — 8 threads beside a FLUX.2 job cost it 18 % (all 32: 23 %) and drew frames faster (50 / 87 ms at ½ / full)
    timeout_s: float = 120.0    # a request past this kills the session (a frame is ≈ 60 ms; the final render is a CLI job, never sent through it)


class FilmCraftSettings(BaseModel):
    """CE1 (proto01_animate 30 §10, D126): the cut editor's engine — the pinned `filmcraft-cli` (engine/filmcraft.pin.json, built by
    scripts/build_filmcraft.py into engine/tools/, never in git) driven as one MCP session beside the orchestrator (loom2/filmcraft.py); the
    movie is its export in a process of its own. A `.py` runs under the orchestrator's interpreter (the tests' fake)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    cli: str = os.environ.get("LOOM2_FILMCRAFT_CLI") or str(REPO_ROOT / "engine" / "tools" / "filmcraft" / "filmcraft-cli.exe")   # the env: the offline suite keeps it unbuilt
    threads: int = 8            # RAYON_NUM_THREADS of the session (E32: a warm frame is 10 ms at ½; D113's cap beside a GPU job)
    timeout_s: float = 120.0    # a request past this kills the session (the movie's export is a job of its own, never sent through it)


class MotionSettings(BaseModel):
    """CA1 (proto01_animate 02 §5): the motion library's folders. The starter set (CC0, ships with loom2) defaults to <models_root>/motion;
    the local folder holds the author's own downloads (e.g. Mixamo FBX) — never bundled, never in CI or tests."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    starter_dir: str = ""                                    # empty = <models_root>/motion
    local_dir: str = ""                                      # empty = none (Settings › Motion)


# D90 (02 §4.1, §6.3): the scenes the sample images are rendered on — the defaults of Settings › Samples
STYLE_SAMPLE_PROMPT = "a woman in a long coat beside an old bicycle on a cobbled street at dusk, a lit shop window behind her"
SWATCH_PROMPTS: dict[str, str] = {   # `{value}` is the preset; a neutral subject so the swatch shows the value, not the subject
    "lighting": "a simple still life of a white sphere on a table, {value}",
    "mood": "close-up portrait of a person's face and shoulders, {value} mood, the expression and the light show it",   # a face carries a mood (the expression and the light); the empty street corner made the four dark moods one picture (journal 2026-10-17, mood_swatch_scenes.py)
    "style": "a lighthouse on a cliff, {value}",
    "background": "{value}, empty, no people",
    "scene": "{value}",
    "subject.action": "a plain grey mannequin figure {value}, simple studio backdrop",   # D92: a subject's action and pose are pictured on a neutral figure
    "subject.pose": "a plain grey mannequin figure, {value}, full body, simple studio backdrop",
    "subject.description": "{value}, simple studio backdrop",
    "text": "a lighthouse on a cliff. {value}",                                             # the lead text says what kind of picture: shown on the style scene
}


# Every earlier built-in scene: Settings › Samples saves the whole map, so a scene the author never changed was stored verbatim and pinned
# the old default (the street-corner mood, journal 2026-10-17 18:03). A stored entry equal to one of these reads as "the built-in".
PAST_SWATCH_DEFAULTS: dict[str, frozenset[str]] = {
    "mood": frozenset({"an empty street corner, {value} mood"}),
    "text": frozenset({"{value}"}),
}


class SampleSettings(BaseModel):
    """D90: the prompt a style's sample is rendered with (the style's fragment is appended by the server), and the scene each look
    preset's swatch is rendered on. Editable in Settings › Samples; a blank entry is its default again, a scene without `{value}` gets it
    appended. Changing them does not remake existing samples."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    style_prompt: str = STYLE_SAMPLE_PROMPT
    swatch_prompts: dict[str, str] = Field(default_factory=lambda: dict(SWATCH_PROMPTS))
    model_id: str | None = None                  # D91: the sample model (`/capabilities.sample_models`); None — or one this build does not offer — = the default swatch model

    @field_validator("model_id")
    @classmethod
    def _model(cls, v: str | None) -> str | None:
        return (v or "").strip() or None

    @field_validator("style_prompt")
    @classmethod
    def _style(cls, v: str) -> str:
        return v.strip() or STYLE_SAMPLE_PROMPT

    @field_validator("swatch_prompts")
    @classmethod
    def _swatches(cls, v: dict[str, str]) -> dict[str, str]:
        out = dict(SWATCH_PROMPTS)
        for field, t in v.items():
            t = t.strip()
            if t and t not in PAST_SWATCH_DEFAULTS.get(field, ()):   # a built-in saved verbatim follows the built-in, old or new (2026-10-17)
                out[field] = t if "{value}" in t else f"{t}, {{value}}"
        return out


class Settings(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    schema_version: int = APP_SCHEMA_VERSION
    models_root: str = os.environ.get("LOOM2_MODELS", "F:/loom2-models")
    mounted_model_trees: list[str] = Field(default_factory=list)       # D80: none by default — D: is a backup drive, F:/loom2-models holds everything
    vram_budget_gb: float = 16.0
    variant: Variant = os.environ.get("LOOM2_VARIANT", "full")  # type: ignore[assignment]
    hf_home: str = os.environ.get("HF_HOME", "F:/HF_HOME")
    engine: EngineSettings = Field(default_factory=EngineSettings)
    trainer: TrainerSettings = Field(default_factory=TrainerSettings)   # LT2 (D86)
    voices: VoicesSettings = Field(default_factory=VoicesSettings)      # CN2 (D87)
    lipsync: LipsyncSettings = Field(default_factory=LipsyncSettings)   # AE4d (D118): the lip-sync model as a tool
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    thumbnail_sizes: list[int] = Field(default_factory=lambda: [256, 512, 1024])
    log_level: str = "INFO"
    reopen_last_project: bool = True
    h3_licence_confirmed: bool = False      # D17: the author confirms the MiniMax H3 community-licence application is filed
    samples: SampleSettings = Field(default_factory=SampleSettings)     # D90: the scenes of the style samples and the preset swatches
    motion: MotionSettings = Field(default_factory=MotionSettings)      # CA1: the motion library's starter set and local folder
    effectcraft: EffectCraftSettings = Field(default_factory=EffectCraftSettings)   # AE1 (D114): the animation editor's engine
    filmcraft: FilmCraftSettings = Field(default_factory=FilmCraftSettings)         # CE1 (D126): the cut editor's engine


class AppRecord(BaseModel):
    schema_version: int = APP_SCHEMA_VERSION
    settings: Settings = Field(default_factory=Settings)
    last_project: str | None = None
    recents: list[str] = Field(default_factory=list)
    updated_at: str = Field(default_factory=utc_now)


class AppState:
    """`<state>/app.json` plus the per-launch token. Settings changes are written atomically."""

    def __init__(self, state_dir: Path | None = None, variant: str | None = None) -> None:
        self.state_dir = Path(state_dir or default_state_dir())
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "logs").mkdir(exist_ok=True)
        self.app_json = self.state_dir / "app.json"
        self.record = AppRecord.model_validate(read_json_or(self.app_json, AppRecord().model_dump()))
        # C3 (D26): the build variant comes from the shell (LOOM2_VARIANT) and wins over whatever an earlier launch persisted
        self.variant_override: str | None = variant if variant in ("full", "open") else None
        if self.variant_override:
            self.record.settings.variant = self.variant_override  # type: ignore[assignment]
        self.token = os.environ.get("LOOM2_TOKEN") or secrets.token_urlsafe(24)
        # D67: a read-only key for the media URLs <img> / <video> load (`?k=`): it reads pixels and nothing else. Derived from the token,
        # so a launch has exactly one and a script that knows the token can compute it.
        self.media_key = hmac.new(self.token.encode(), b"loom2-media-key", hashlib.sha256).hexdigest()[:32]
        self.session_id = new_id("ses")

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
        if self.variant_override:
            self.record.settings.variant = self.variant_override  # type: ignore[assignment]
        self.save()
        return self.record.settings

    def touch_project(self, path: Path) -> None:
        s = str(Path(path).resolve())
        self.record.last_project = s
        self.record.recents = [s] + [r for r in self.record.recents if r != s]
        self.record.recents = self.record.recents[:20]
        self.save()
