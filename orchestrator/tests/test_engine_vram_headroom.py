"""The engine is launched with `--vram-headroom` from `Settings.engine.vram_headroom_gb` (2026-10-18 rig: without it DynamicVRAM let FLUX.2
dev's activations spill to shared memory — 4 references 564 s → 170 s, 6 references 1000 s → 238 s per Draft image). A flag the author
typed in `flags` wins; 0 leaves it out; an app.json saved before the field existed gets the default."""
from __future__ import annotations

import json
from pathlib import Path

from loom2.config import AppState
from loom2.engine.supervisor import EngineSupervisor


def _argv(state: Path) -> list[str]:
    return EngineSupervisor(AppState(state))._argv()


def test_default_headroom_is_passed(tmp_path: Path):
    argv = _argv(tmp_path)
    i = argv.index("--vram-headroom")
    assert argv[i + 1] == "5.0"
    assert argv.count("--reserve-vram") == 1


def test_saved_settings_without_the_field_get_the_default(tmp_path: Path):
    # the author's app.json stores the engine block verbatim (flags list included) from before the field existed
    engine = {"flags": ["--disable-auto-launch", "--use-pytorch-cross-attention", "--disable-pinned-memory", "--preview-method", "none"], "reserve_vram_gb": 1.5}
    (tmp_path / "app.json").write_text(json.dumps({"settings": {"engine": engine}}), encoding="utf-8")
    assert "--vram-headroom" in _argv(tmp_path)


def test_a_flag_in_flags_wins_and_zero_leaves_it_out(tmp_path: Path):
    a = AppState(tmp_path / "a")
    a.settings.engine.flags = [*a.settings.engine.flags, "--vram-headroom", "2"]
    argv = EngineSupervisor(a)._argv()
    assert argv.count("--vram-headroom") == 1 and argv[argv.index("--vram-headroom") + 1] == "2"
    b = AppState(tmp_path / "b")
    b.settings.engine.vram_headroom_gb = 0
    assert "--vram-headroom" not in EngineSupervisor(b)._argv()
