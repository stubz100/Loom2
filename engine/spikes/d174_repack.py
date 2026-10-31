"""D174 (journal 2026-10-31 17:35 and after): the rig's walkers segment packed again with the edge fade (place_sets.edge_fade, added after the
rig's Clay check showed a walker cut at the segment's edge) — the same loop and matte, no GPU; the copy's orchestrator stopped meanwhile.

    orchestrator/.venv/Scripts/python.exe engine/spikes/d174_repack.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import PID, PROJECT, VID  # noqa: E402


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.clips import ClipStore
    from loom2.fsio import new_id
    from loom2.place_sets import edge_fade, walker_masks
    from loom2.stages import SetWalkers
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8766):
        raise SystemExit("stop the copy's orchestrator first")
    ws = Workspace(PROJECT)
    cat, store, clips = Catalogue(ws), StoryStore(ws), ClipStore(ws)
    face = next(f for f in store.profile(PID).version(VID).place_set.faces if f.id == "facade_right")
    seg = next(w for w in face.walkers if w.status == "done")
    loop = clips.get(seg.clip_id)
    frames = [np.asarray(Image.open(clips.frame_path(loop.id, i)).convert("RGB")) for i in range(loop.frames)]
    masks = [np.asarray(Image.open(clips.dir(loop.id) / "matte" / f"{i:06d}.png").convert("L"), dtype=np.float32) / 255.0 for i in range(loop.frames)]
    height_m = face.texel_m * Image.open(cat.abs_path(cat.get(face.texture_asset_id))).height
    kept, n_kept, n_dropped = walker_masks(masks, loop.h / height_m)
    ramp = edge_fade(loop.w, seg.to_m - seg.from_m)
    tmp = ws.temp_dir / "set_walkers" / new_id("swalk")
    tmp.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (rgb, m) in enumerate(zip(frames, kept)):
        a = np.repeat((m * ramp[None, :] * 255).round().astype(np.uint8)[..., None], 3, axis=2)
        Image.fromarray(np.concatenate([rgb, a], axis=1)).save(tmp / f"{i:06d}.png")
        paths.append(tmp / f"{i:06d}.png")
    rec = clips.create(paths, model_id=loop.model_id, preset=loop.preset, prompt=loop.prompt, seed=loop.seed, fps=loop.fps, start_asset_id=loop.start_asset_id,
                       params={"walkers_of": loop.id, "packed": "colour | mask", "kept": n_kept, "dropped": n_dropped, "repacked": "edge fade"})
    rec = clips.encode_proxy(rec)
    asset = cat.make_thumbs(cat.ingest_file(ws.path / rec.proxy_path, kind="video", in_place=True, suite="story", lineage_kind="set-walkers",
                                            parents=[loop.asset_id] if loop.asset_id else [], params={"clip_id": rec.id, "walkers_of": loop.id},
                                            frames=rec.frames, w=rec.w, h=rec.h), clips.frame_path(rec.id, 0))
    rec.asset_id = asset.id
    clips.save(rec)
    walkers = [SetWalkers(**(w.model_dump() | ({"asset_id": asset.id, "kept": n_kept, "dropped": n_dropped} if w.id == seg.id else {}))) for w in face.walkers]
    store.update_face(PID, VID, "facade_right", walkers=walkers)
    print("repacked", seg.id, "→", asset.id, "kept", n_kept, "dropped", n_dropped, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
