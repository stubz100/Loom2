"""D42: atomic replace retries a transient PermissionError (Windows antivirus / indexer locks), with failure injection."""
import errno
import os
from pathlib import Path

import numpy as np
import pytest

from loom2 import fsio
from loom2.documents import Document, OpenDocument, RasterLayer


@pytest.fixture
def no_sleep(monkeypatch):
    waits: list[float] = []
    monkeypatch.setattr(fsio.time, "sleep", waits.append)
    return waits


def flaky_replace(monkeypatch, failures: int, exc: type[OSError] = PermissionError):
    """os.replace that fails `failures` times with `exc`, then works; returns the call log."""
    real = os.replace
    calls: list[tuple[str, str]] = []

    def fake(src, dst):
        calls.append((str(src), str(dst)))
        if len(calls) <= failures:
            raise exc(errno.EACCES if exc is PermissionError else errno.EXDEV, "injected")
        real(src, dst)

    monkeypatch.setattr(fsio.os, "replace", fake)
    return calls


def test_replace_retries_a_locked_target_with_backoff(tmp_path: Path, monkeypatch, no_sleep):
    target = tmp_path / "rec.json"
    target.write_text("old")
    calls = flaky_replace(monkeypatch, failures=3)
    fsio.atomic_write_text(target, "new")
    assert target.read_text() == "new"
    assert len(calls) == 4
    assert no_sleep == [0.01, 0.02, 0.04]                        # doubling from 10 ms
    assert not list(tmp_path.glob("*.tmp"))


def test_replace_gives_up_after_seven_tries_and_keeps_the_old_file(tmp_path: Path, monkeypatch, no_sleep):
    target = tmp_path / "rec.json"
    target.write_text("old")
    calls = flaky_replace(monkeypatch, failures=99)
    with pytest.raises(PermissionError):
        fsio.atomic_write_text(target, "new")
    assert len(calls) == fsio.REPLACE_TRIES == 7
    assert sum(no_sleep) < 0.7
    assert target.read_text() == "old"                          # whole-or-nothing: the old record survives
    assert not list(tmp_path.glob("*.tmp"))                     # and the temp file is gone


def test_other_errors_are_not_retried(tmp_path: Path, monkeypatch, no_sleep):
    calls = flaky_replace(monkeypatch, failures=1, exc=FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        fsio.replace(tmp_path / "a", tmp_path / "b")
    assert len(calls) == 1 and no_sleep == []


def test_atomic_move_across_volumes_still_copies(tmp_path: Path, monkeypatch, no_sleep):
    src = tmp_path / "src.bin"
    src.write_bytes(b"payload")
    real = os.replace
    first = {"done": False}

    def fake(a, b):                                             # the direct rename fails like a cross-volume move; the copy's own replace works
        if not first["done"]:
            first["done"] = True
            raise OSError(errno.EXDEV, "cross-device link")
        real(a, b)

    monkeypatch.setattr(fsio.os, "replace", fake)
    fsio.atomic_move(src, tmp_path / "sub" / "dst.bin")
    assert (tmp_path / "sub" / "dst.bin").read_bytes() == b"payload" and not src.exists()
    assert no_sleep == []


def test_document_save_survives_a_briefly_locked_ora(tmp_path: Path, monkeypatch, no_sleep):
    doc = Document(name="d", w=4, h=4, layers=[RasterLayer(id="a", w=4, h=4)])
    od = OpenDocument(doc, tmp_path / "d.ora")
    od.pixels["a"] = np.full((4, 4, 4), 200, dtype=np.uint8)
    calls = flaky_replace(monkeypatch, failures=2)
    od.save()
    assert (tmp_path / "d.ora").is_file() and len(calls) == 3
    assert not list(tmp_path.glob("*.tmp"))
