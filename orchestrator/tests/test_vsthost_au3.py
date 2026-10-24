"""AU3 (proto01_animate 30 §16, D127): loom2's own VST3 host as a sidecar, on tests/fake_vsthost.py (the real host and the SDK's sample
effects on the rig) — not built: said; the scan of the author's folders (an instrument left out, a crashing bundle listed with its reason
while loom2 goes on, the answers kept until a bundle changes); an effect's parameters, its state set, its editor's state; a chain rendered
(a bypassed effect skipped); GET /audio/plugins."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.api import create_app  # noqa: E402
from loom2.config import AppState  # noqa: E402
from loom2.vsthost import VstHost, VstHostError  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_vsthost.py"


def _bundle(folder: Path, name: str, classes: list[dict], crash: bool = False) -> Path:
    b = folder / f"{name}.vst3"
    b.mkdir(parents=True)
    (b / "fake.json").write_text(json.dumps({"classes": classes, "crash": crash}), encoding="utf-8")
    return b


def _app(tmp_path: Path, cli: Path = FAKE) -> AppState:
    app = AppState(tmp_path / "state")
    folder = tmp_path / "vst3"
    _bundle(folder, "Gain", [{"uid": "A" * 32, "name": "Gain", "vendor": "Fake", "version": "1.0", "sub": "Fx|Dynamics"}])
    _bundle(folder, "Synth", [{"uid": "B" * 32, "name": "Synth", "vendor": "Fake", "version": "1.0", "sub": "Instrument|Synth"}])
    _bundle(folder / "nested", "Crashy", [], crash=True)
    app.update_settings({"vsthost": {"cli": str(cli), "folders": [str(folder)]}})
    return app


def test_not_built_is_said(tmp_path: Path):
    host = VstHost(_app(tmp_path, cli=tmp_path / "missing.exe"))
    assert not host.available()
    try:
        host.plugins()
        raise AssertionError("ran without a host")
    except VstHostError as e:
        assert "build_vsthost" in str(e)


def test_scan_state_editor_and_render(tmp_path: Path):
    app = _app(tmp_path)
    host = VstHost(app)
    got = host.plugins()
    assert [p["name"] for p in got["plugins"]] == ["Gain"]                                  # the instrument left out
    assert len(got["failed"]) == 1 and "crashed" in got["failed"][0]["error"] and "loom2 is fine" in got["failed"][0]["error"]
    cache = json.loads((app.state_dir / "vst-scan.json").read_text(encoding="utf-8"))
    assert len(cache["bundles"]) == 3
    gain = got["plugins"][0]
    (Path(gain["bundle"]) / "fake.json").write_text(json.dumps({"classes": [], "crash": True}), encoding="utf-8")
    assert [p["name"] for p in host.plugins()["plugins"]] == ["Gain"]                       # kept: the bundle's time did not move
    assert host.plugins(rescan=True)["plugins"] == []                                        # a rescan asks again
    (Path(gain["bundle"]) / "fake.json").write_text(json.dumps({"classes": [{k: gain[k] for k in ("uid", "name", "vendor", "version", "sub")}]}), encoding="utf-8")
    # an effect's state, parameters and editor
    st = tmp_path / "fx" / "gain.vststate"
    host.state(gain["bundle"], gain["uid"], None, st, {0: 0.5})
    assert host.params(gain["bundle"], gain["uid"], st)["params"][0]["value"] == 0.5
    host.editor(gain["bundle"], gain["uid"], st, st, "Gain — Music")
    assert json.loads(st.read_text(encoding="utf-8")) == {"gain": 0.5, "edited": True}
    # a chain: the gain at 0.5, then a bypassed one
    t = np.arange(48000) / 48000
    src = tmp_path / "in.wav"
    sf.write(str(src), np.stack([0.4 * np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32), 48000, subtype="FLOAT")
    out = tmp_path / "out.wav"
    res = host.render([{"bundle": gain["bundle"], "uid": gain["uid"], "state": st}, {"bundle": gain["bundle"], "uid": gain["uid"], "state": None, "bypass": True}], src, out)
    assert res["effects"] == [{"name": "Gain", "latency": 0}, {"bypassed": True}] and not out.with_suffix(".chain.tsv").exists()
    pcm, _ = sf.read(str(out), dtype="float32", always_2d=True)
    assert abs(float(np.max(np.abs(pcm))) - 0.2) < 1e-3
    try:
        host.render([{"bundle": str(tmp_path / "vst3" / "nested" / "Crashy.vst3"), "uid": "C" * 32, "state": None}], src, out)
        raise AssertionError("a crash went unsaid")
    except VstHostError as e:
        assert "a plug-in crashed" in str(e)


def test_route(tmp_path: Path):
    _app(tmp_path)
    AppState(tmp_path / "state").update_settings({"engine": {"python": str(tmp_path / "missing.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models")})
    with TestClient(create_app(tmp_path / "state")) as cl:
        r = cl.get("/audio/plugins").json()
        assert r["available"] and [p["name"] for p in r["plugins"]] == ["Gain"] and len(r["failed"]) == 1
