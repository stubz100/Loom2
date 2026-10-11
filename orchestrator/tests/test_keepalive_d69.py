"""D69 (ArtCraft P5): a GPU job admitted while the engine's free VRAM is below its reserve + 1 GB broadcasts `engine.vram_pressure`, so the
UI releases the Edit canvas it keeps alive while hidden; with room to spare nothing is said. The job runs either way."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_lifecycle import Rig


@pytest.mark.parametrize("free_gb, expect", [(1.2, True), (12.0, False)])
async def test_a_gpu_job_under_vram_pressure_asks_the_ui_to_release(tmp_path: Path, object_info: dict, free_gb: float, expect: bool):
    rig = Rig(tmp_path, object_info)
    rig.fake.vram_free_gb = free_gb
    seen: list[tuple[str, dict]] = []
    orig = rig.hub.broadcast
    rig.hub.broadcast = lambda t, d=None: (seen.append((t, d)), orig(t, d))[1]          # type: ignore[method-assign]
    try:
        rig.queue.load()
        await rig.queue.start()
        job = rig.queue.submit({"kind": "t2i", "prompt_text": "a cat", "seeds": [7], "width": 64, "height": 64})[0]
        j = await rig.wait(job.id)
        assert j.status == "done", j.error
        pressure = [d for t, d in seen if t == "engine.vram_pressure"]
        if expect:
            threshold = rig.app.settings.engine.reserve_vram_gb + 1.0
            assert pressure == [{"job_id": job.id, "free_gb": free_gb, "threshold_gb": round(threshold, 2)}]
        else:
            assert pressure == []
    finally:
        await rig.close()
