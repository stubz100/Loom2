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


# ---- D100: the headroom is per model (a spec's engine.vram_headroom_gb); the engine restarts when the next job's model wants another --------
class _Alive:
    pid = 1

    def poll(self):
        return None


def test_a_model_may_ask_for_its_own_headroom(tmp_path: Path):
    sup = EngineSupervisor(AppState(tmp_path))
    assert sup.headroom_for(None) == 5.0 and sup.headroom_for(0.0) == 0.0
    assert "--vram-headroom" not in sup._argv(0.0) and sup._argv(2.5)[sup._argv(2.5).index("--vram-headroom") + 1] == "2.5"
    a = AppState(tmp_path / "f")
    a.settings.engine.flags = [*a.settings.engine.flags, "--vram-headroom", "3"]
    assert EngineSupervisor(a).headroom_for(0.0) is None                                        # a typed flag decides for every model


def test_a_spec_value_reaches_the_queue(monkeypatch):
    """E30a (2026-10-18 20:53) lifted Wan Animate's exemption: no spec sets a headroom today, so every model runs with the engine-wide
    value; a spec that sets one is read by the queue."""
    from loom2.models import registry
    from loom2.queue import model_headroom
    from loom2.recipes import parse_recipe
    assert all(s.engine.vram_headroom_gb is None for s in registry.SPECS.values())
    animate = next(s for s in registry.SPECS.values() if s.graph == "wan_animate")
    recipe = parse_recipe({"kind": "i2v", "model_id": animate.id, "start_asset": "ast_1"})
    assert model_headroom(recipe, "full") is None
    monkeypatch.setattr(animate.engine, "vram_headroom_gb", 2.0)
    assert model_headroom(recipe, "full") == 2.0


def test_the_engine_restarts_only_when_the_headroom_changes(tmp_path: Path):
    import asyncio
    sup = EngineSupervisor(AppState(tmp_path))
    calls: list[float | None] = []

    async def restart(model_gb=None):
        calls.append(model_gb)
        sup.headroom_gb = sup.headroom_for(model_gb)
        return {}
    sup.restart = restart                                                                        # type: ignore[method-assign]
    sup.proc = _Alive()                                                                          # type: ignore[assignment]
    sup.headroom_gb = 5.0

    async def answers():
        return True
    sup.client.is_up = answers                                                                   # type: ignore[method-assign]  V15: alive *and* answering
    assert asyncio.run(sup.ensure_running(None)) is False and calls == []                      # the engine-wide value: as launched
    assert asyncio.run(sup.ensure_running(0.0)) is True and calls == [0.0]                     # Wan Animate: restarted without it
    assert asyncio.run(sup.ensure_running(0.0)) is False and calls == [0.0]                    # the next Wan Animate job: no restart
    assert asyncio.run(sup.ensure_running(None)) is True and calls == [0.0, 5.0]               # back to an image model
