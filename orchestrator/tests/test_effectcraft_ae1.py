"""AE1 (proto01_animate 20 §2, D114): the EffectCraft session beside the orchestrator — the client against the fake, the pin's check."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

from loom2.config import AppState
from loom2.effectcraft import EffectCraft, EffectCraftError

FAKE = Path(__file__).parent / "fake_effectcraft.py"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def ec(tmp_path: Path):
    app = AppState(tmp_path / "state")
    app.update_settings({"effectcraft": {"cli": str(FAKE), "timeout_s": 10.0}})
    c = EffectCraft(app)
    yield c
    c.stop()


def small_png(p: Path) -> Path:
    Image.new("RGB", (8, 8), (10, 20, 30)).save(p)
    return p


def test_argv_and_availability(tmp_path: Path):
    app = AppState(tmp_path / "state")
    c = EffectCraft(app)
    assert c.argv()[-2:] == ["mcp", "--empty"] and c.argv()[0].lower().endswith("effectcraft-cli.exe")
    app.update_settings({"effectcraft": {"cli": str(FAKE)}})
    assert c.argv()[:2] == [sys.executable, str(FAKE)] and c.available()
    app.update_settings({"effectcraft": {"cli": str(tmp_path / "nowhere.exe")}})
    assert not c.available()
    with pytest.raises(EffectCraftError, match="not built"):
        c.ensure()
    assert c.state()["running"] is False


def test_session_roundtrip(ec: EffectCraft, tmp_path: Path):
    comp = ec.command("comp.new", {"name": "Final", "width": 832, "height": 480, "frameRate": 16, "duration": 2})["comp"]
    seq = small_png(tmp_path / "plate_0000.png")
    item = ec.command("file.import", {"paths": [str(seq)], "sequence": True, "frameRate": 16})["items"][0]
    lid = ec.command("layer.addItem", {"item": item, "time": 0})["layer"]
    ec.command("layer.rename", {"layer": lid, "name": "plate"})
    ec.tool("set_property", {"layer": lid, "path": "transform/position", "value": [400, 230]})
    info = ec.tool("get_comp", {})
    assert info["id"] == comp and [l["name"] for l in info["layers"]] == ["plate"] and info["layers"][0]["position"] == [400, 230]
    png = ec.frame(0.5, 416)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    assert im.size == (416, 240) and im.getpixel((0, 0)) == (8, 5, 128)          # the frame number, the revision after 5 edits
    assert Image.open(io.BytesIO(ec.frame(1.0, 0))).size == (832, 480)
    out = tmp_path / "comp.ecproj.tmp"
    ec.save_copy(out)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["comps"][str(comp)]["layers"][0]["name"] == "plate" and ec.tool("get_project", {})["path"] is None   # a copy: the session's file unchanged
    s = ec.state()
    assert s["running"] and s["calls"] >= 8 and s["restarts"] == 0 and s["threads"] == 8 and Path(s["log"]).is_file()


def test_refusals_carry_the_engines_message(ec: EffectCraft):
    with pytest.raises(EffectCraftError, match="unknown command"):
        ec.command("layer.fly", {})
    with pytest.raises(EffectCraftError, match="no composition"):
        ec.frame(0.0, 100)


def test_restart_after_death_reopens_the_project(ec: EffectCraft, tmp_path: Path):
    ec.command("comp.new", {"name": "A", "width": 64, "height": 32, "frameRate": 16, "duration": 1})
    proj = tmp_path / "a.ecproj"
    ec.tool("save_project", {"path": str(proj)})
    ec.open(proj)
    assert ec.project == str(proj) and ec.state()["pid"]
    ec.proc.kill()                                                               # the session dies under us
    ec.proc.wait(timeout=5)
    assert Image.open(io.BytesIO(ec.frame(0.0, 0))).size == (64, 32)             # started again, the project opened again
    assert ec.restarts == 1 and ec.project == str(proj)
    ec.stop()
    assert ec.state()["running"] is False and ec.restarts == 1                   # a deliberate stop is no death
    ec.command("comp.new", {"name": "B"})
    assert ec.restarts == 1


def test_a_timeout_stops_the_session(ec: EffectCraft):
    ec.app.update_settings({"effectcraft": {"cli": str(FAKE), "timeout_s": 0.3}})
    ec.command("comp.new", {"name": "A"})
    with pytest.raises(EffectCraftError, match="timed out"):
        ec.command("fake.sleep", {"seconds": 3})
    assert not ec.alive() and "timed out" in (ec.last_error or "")
    ec.command("comp.new", {"name": "B"})                                        # the next request starts it again
    assert ec.restarts == 1


def _build_script():
    spec = importlib.util.spec_from_file_location("build_effectcraft", ROOT / "scripts" / "build_effectcraft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_pin_check(tmp_path: Path):
    b = _build_script()
    pin = json.loads((ROOT / "engine" / "effectcraft.pin.json").read_text(encoding="utf-8"))
    ok, msg = b.check(pin, tmp_path / "missing.exe")
    assert ok and "not built here" in msg                                        # CI: the binary is never in git
    binary = tmp_path / "effectcraft-cli.exe"
    binary.write_bytes(b"not the binary")
    ok, msg = b.check(pin, binary)
    assert not ok and "rebuild" in msg
    ok, _ = b.check({**pin, "sha256": b.sha256(binary), "bytes": binary.stat().st_size}, binary)
    assert ok
    assert not b.check({**pin, "commit": "abc"}, binary)[0] and not b.check({k: v for k, v in pin.items() if k != "bytes"}, binary)[0]


def test_fake_render_cli(tmp_path: Path, ec: EffectCraft):
    """The fake's `render` writes a PNG a frame, named as EffectCraft names a sequence (`[####]` → the frame number)."""
    import subprocess
    ec.command("comp.new", {"name": "Final", "width": 32, "height": 16, "frameRate": 16, "duration": 0.5})
    proj = tmp_path / "f.ecproj"
    ec.tool("save_project", {"path": str(proj)})
    r = subprocess.run([sys.executable, str(FAKE), "render", "--project", str(proj), "--comp", "Final", "--out", str(tmp_path / "r" / "f_[####].png"),
                        "--format", "png", "--quality", "best"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    frames = sorted((tmp_path / "r").glob("*.png"))
    assert [f.name for f in frames] == [f"f_{i:04d}.png" for i in range(8)] and Image.open(frames[3]).getpixel((0, 0))[0] == 3
