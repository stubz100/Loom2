"""Review register R1–R10 (2026-10-10): Quick Remove against a document that changes under it, admission and cancel; the mask
default outside its extent; /heal's size, area and time bounds; the settings audit's reads; blob writes off the loop; a missing
native extension refused at submission; a document from a newer loom2 refused."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import threading
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from loom2 import native
from loom2.api import create_app
from loom2.compose import Renderer
from loom2.config import AppState
from loom2.engine.graphs import estimate_vram_gb, recipe_weights
from loom2.queue import JobQueue
from loom2.recipes import Inpaint


def texture(h: int = 48, w: int = 64) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w]
    rgb = np.stack([(np.sin(x / 3.0) * 40 + 120), (np.cos(y / 4.0) * 40 + 110), np.full_like(x, 90.0)], -1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


class FakeFill:
    """A content-aware fill that waits until the test lets it finish (the document changes meanwhile)."""

    def __init__(self) -> None:
        self.entered, self.release = threading.Event(), threading.Event()

    def __call__(self, rgb, hole, seed: int = 1):
        self.entered.set()
        assert self.release.wait(20), "the test never released the fill"
        out = np.asarray(rgb).copy()
        out[np.asarray(hole)] = (10, 20, 30)
        return out


@pytest.fixture
def fake_native(monkeypatch):
    fill = FakeFill()
    monkeypatch.setattr(native, "_pc", object())                 # available() → True without the wheel
    monkeypatch.setattr(native, "content_aware_fill", fill)
    return fill


def _app(tmp_path: Path, variant: str = "full", **settings):
    state = tmp_path / "state"
    AppState(state).update_settings({"engine": {"python": str(tmp_path / "missing-python.exe"), "health_timeout_s": 1}, "models_root": str(tmp_path / "models"),
                                     "mounted_model_trees": [], "variant": variant, **settings})
    app = create_app(state, variant=variant)
    return app, TestClient(app), {"X-Loom-Token": app.state.services.app.token}


def _doc_with_selection(c: TestClient, H: dict, tmp_path: Path) -> str:
    assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "r", "size_cap_gb": 10}, headers=H).status_code == 200
    Image.fromarray(texture()).save(tmp_path / "in.png")
    asset = c.post("/assets/import", json={"paths": [str(tmp_path / "in.png")]}, headers=H).json()["items"][0]["id"]
    did = c.post("/documents", json={"from_asset": asset}, headers=H).json()["id"]
    sel = np.zeros((48, 64), np.uint8); sel[20:30, 30:40] = 255
    assert c.put(f"/documents/{did}/selection", params={"w": 64, "h": 48}, content=sel.tobytes(), headers={**H, "Content-Type": "application/octet-stream"}).status_code == 200
    return did


def _quick_remove(c: TestClient, H: dict, did: str) -> str:
    r = c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "quick_remove"}}, headers=H)
    assert r.status_code == 200, r.text
    job = r.json()["jobs"][0]
    assert job["status"] == "queued", job
    c.post("/queue/unpause", headers=H)
    return job["id"]


def _wait(c: TestClient, jid: str, timeout: float = 30.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = c.get(f"/jobs/{jid}").json()
        if job["status"] in ("done", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {jid} did not end: {job}")


def _layers(doc: dict) -> list[dict]:
    out = []
    for n in doc["layers"]:
        out.append(n)
        out += n.get("children") or []
    return out


# ---- R1 ---------------------------------------------------------------------------------------------------------------
def test_review_r1_quick_remove_does_not_resurrect_a_deleted_document(tmp_path, fake_native):
    app, c, H = _app(tmp_path)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        ora = app.state.services.documents.path_for(did)
        jid = _quick_remove(c, H, did)
        assert fake_native.entered.wait(20)
        assert c.delete(f"/documents/{did}", headers=H).status_code == 200
        fake_native.release.set()
        job = _wait(c, jid)
        assert job["status"] == "failed" and "deleted" in (job["error"] or ""), job
        assert not ora.exists()                                              # the stale copy was not saved back
        assert c.get(f"/documents/{did}").status_code in (400, 404)


def test_review_r1_quick_remove_lands_in_the_reopened_copy(tmp_path, fake_native):
    app, c, H = _app(tmp_path)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        c.post(f"/documents/{did}/save", headers=H)
        jid = _quick_remove(c, H, did)
        assert fake_native.entered.wait(20)
        assert c.post(f"/documents/{did}/close", headers=H).status_code == 200
        assert c.get(f"/documents/{did}").status_code == 200                # a fresh copy is open now
        fake_native.release.set()
        job = _wait(c, jid)
        assert job["status"] == "done", job
        names = [n["name"] for n in _layers(c.get(f"/documents/{did}").json())]
        assert "quick remove" in names                                       # in the copy the store serves, not the closed one
        c.post(f"/documents/{did}/close", headers=H)
        assert "quick remove" in [n["name"] for n in _layers(c.get(f"/documents/{did}").json())]   # and on disk


# ---- R2 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("density,expect", [(0.5, 128), (0.0, 255), (1.0, 0), (0.3, 179)])
def test_review_r2_mask_default_0_goes_through_density(density, expect):
    px = {"l": np.full((4, 8, 4), 255, np.uint8)}
    masks = {"l": np.zeros((4, 4), np.uint8)}                                # black over the left half; the right half is outside
    node = {"id": "l", "kind": "raster", "x": 0, "y": 0, "mask": {"enabled": True, "linked": True, "x": 0, "y": 0, "density": density, "feather": 0.0, "default": 0}}
    out = Renderer(8, 4, px, masks).flatten_u8([node])
    assert int(out[0, 6, 3]) == expect                                      # maskDerived.outsideValue: round(255 − d·255)
    assert int(out[0, 1, 3]) == expect                                      # inside: the black mask through the same density


# ---- R3 ---------------------------------------------------------------------------------------------------------------
def test_review_r3_quick_remove_is_admitted_without_a_model(tmp_path, fake_native):
    qr = Inpaint(mode="quick_remove", model_id="klein-9b")
    assert estimate_vram_gb(qr) == 0.0 and recipe_weights(qr, "open") == []
    app, c, H = _app(tmp_path, variant="open", vram_budget_gb=12)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        # the AI fill with the same panel model is refused by the open-variant gate; Quick Remove loads no weights
        assert c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "fill", "model_id": "klein-9b"}}, headers=H).status_code == 422
        fake_native.release.set()
        jid = _quick_remove(c, H, did)
        job = _wait(c, jid)
        assert job["status"] == "done" and job["vram_estimate_gb"] == 0.0, job


# ---- R4 ---------------------------------------------------------------------------------------------------------------
def test_review_r4_quick_remove_honours_cancel(tmp_path, fake_native):
    app, c, H = _app(tmp_path)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        jid = _quick_remove(c, H, did)
        assert fake_native.entered.wait(20)
        assert c.post(f"/jobs/{jid}/cancel", headers=H).status_code == 200
        fake_native.release.set()
        job = _wait(c, jid)
        assert job["status"] == "cancelled", job
        assert "quick remove" not in [n["name"] for n in _layers(c.get(f"/documents/{did}").json())]
        assert jid not in app.state.services.queue._cancel_requested


# ---- R5 ---------------------------------------------------------------------------------------------------------------
def test_review_r5_quick_remove_is_not_resumable_before_its_layer_lands(tmp_path, fake_native, monkeypatch):
    seen: list[bool] = []
    orig = JobQueue._add_result_layer

    async def spy(self, job, *a, **kw):
        on_disk = json.loads(self.ws.queue_path.read_text(encoding="utf-8"))
        seen.append(next(j for j in on_disk["jobs"] if j["id"] == job.id)["resumable"])
        return await orig(self, job, *a, **kw)
    monkeypatch.setattr(JobQueue, "_add_result_layer", spy)
    app, c, H = _app(tmp_path)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        fake_native.release.set()
        job = _wait(c, _quick_remove(c, H, did))
        assert job["status"] == "done", job
    assert seen == [False]                                                   # persisted before the layer was added


# ---- R6 ---------------------------------------------------------------------------------------------------------------
def test_review_r6_heal_bounds_size_area_and_time(tmp_path, monkeypatch):
    from loom2.routes import retouch
    monkeypatch.setattr(native, "_pc", object())

    def slow_heal(rgba, cov, seed):
        time.sleep(0.5)
        return rgba
    monkeypatch.setattr(retouch, "spot_heal", slow_heal)
    app, c, H = _app(tmp_path)
    H = {**H, "Content-Type": "application/octet-stream"}
    w, h = 8, 4
    body = bytes(w * h * 5)
    with c:
        assert c.post("/heal", params={"w": w, "h": h}, content=body[:-1], headers=H).status_code == 400
        assert c.post("/heal", params={"w": w, "h": h}, content=body + b"x", headers=H).status_code == 413
        r = c.post("/heal", params={"w": 4096, "h": 1025}, content=b"", headers=H)
        assert r.status_code == 400 and "2048" in r.text                    # each side fits, the area does not
        assert c.post("/heal", params={"w": 4097, "h": 1}, content=b"", headers=H).status_code == 400
        monkeypatch.setattr(retouch, "HEAL_TIMEOUT_S", 0.05)
        assert c.post("/heal", params={"w": w, "h": h}, content=body, headers=H).status_code == 504
        monkeypatch.setattr(retouch, "HEAL_TIMEOUT_S", 60.0)
        r = c.post("/heal", params={"w": w, "h": h}, content=body, headers=H)
        assert r.status_code == 200 and len(r.content) == w * h * 4


# ---- R8 ---------------------------------------------------------------------------------------------------------------
def test_review_r8_blob_put_writes_off_the_event_loop(tmp_path, monkeypatch):
    from loom2.routes import blobs
    on_loop: list[bool] = []
    real = blobs.replace

    def spy(src, dst):
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:
            on_loop.append(False)
        real(src, dst)
    monkeypatch.setattr(blobs, "replace", spy)
    monkeypatch.setattr(blobs, "FLUSH_BYTES", 1000)                         # several slices
    app, c, H = _app(tmp_path)
    data = bytes(range(256)) * 20
    sha = hashlib.sha256(data).hexdigest()
    with c:
        assert c.post("/project", json={"path": str(tmp_path / "proj"), "name": "b", "size_cap_gb": 10}, headers=H).status_code == 200
        r = c.put(f"/blobs/{sha}", content=data, headers=H)
        assert r.status_code == 200 and r.json() == {"sha256": sha, "bytes": len(data)}
        assert c.get(f"/blobs/{sha}").content == data
        assert c.put(f"/blobs/{'0' * 64}", content=data, headers=H).status_code == 400
        tmps = list((app.state.services.ws.temp_dir / "blobs").glob("*.tmp"))
    assert on_loop == [False] and tmps == []


# ---- R9 ---------------------------------------------------------------------------------------------------------------
def test_review_r9_missing_native_extension_is_refused_up_front(tmp_path, monkeypatch):
    monkeypatch.setattr(native, "_pc", None)
    app, c, H = _app(tmp_path)
    with c:
        assert c.get("/capabilities").json()["content_aware"]["available"] is False
        assert c.post("/heal", params={"w": 2, "h": 2}, content=bytes(20), headers={**H, "Content-Type": "application/octet-stream"}).status_code == 503
        did = _doc_with_selection(c, H, tmp_path)
        r = c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "quick_remove"}}, headers=H)
        assert r.status_code == 422 and "native extension" in r.text
        r = c.post(f"/documents/{did}/ai", json={"recipe": {"kind": "inpaint", "mode": "remove", "prefill": True}}, headers=H)
        assert r.status_code == 422 and "native extension" in r.text
        assert app.state.services.queue.jobs == {}                           # refused before a job record exists


# ---- R10 --------------------------------------------------------------------------------------------------------------
def test_review_r10_a_document_from_a_newer_loom2_is_refused(tmp_path):
    from loom2.documents import DOC_SCHEMA_VERSION
    app, c, H = _app(tmp_path)
    with c:
        did = _doc_with_selection(c, H, tmp_path)
        c.post(f"/documents/{did}/save", headers=H)
        c.post(f"/documents/{did}/close", headers=H)
        ora = app.state.services.documents.path_for(did)
        with zipfile.ZipFile(ora) as z:
            entries = {n: z.read(n) for n in z.namelist()}
        meta = json.loads(entries["loom2.json"])
        meta["schema_version"] = DOC_SCHEMA_VERSION + 1
        entries["loom2.json"] = json.dumps(meta).encode("utf-8")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for n, b in entries.items():
                z.writestr(n, b)
        ora.write_bytes(buf.getvalue())
        before = ora.read_bytes()
        r = c.get(f"/documents/{did}")
        assert r.status_code == 409 and "newer loom2" in r.text, r.text
        assert c.post(f"/documents/{did}/save", headers=H).status_code == 409
        assert ora.read_bytes() == before                                     # never rewritten in the older format
