"""Spike E47, between the two finals (journal 2026-10-31 10:06): arm DU — the facades' SeedVR2 ×4 textures (e47_faces.py) set as the faces'
textures on the copy (ingested with the D texture as their parent), the orchestrator stopped meanwhile.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e47_swap.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(Path(__file__).resolve().parent)]
from e47_faces import FACES, OUT, PID, PROJECT, VID  # noqa: E402


def main() -> int:
    from m1_acceptance import port_busy
    from loom2.catalogue import Catalogue
    from loom2.story import StoryStore
    from loom2.workspace import Workspace
    if port_busy(8766):
        raise SystemExit("stop the copy's orchestrator first")
    ws = Workspace(PROJECT)
    cat, st = Catalogue(ws), StoryStore(ws)
    for fid in FACES:
        f = next(x for x in st.profile(PID).version(VID).place_set.faces if x.id == fid)
        rec = cat.make_thumbs(cat.ingest_file(OUT / f"face_DU_{fid}.png", kind="image", move=False, suite="story", lineage_kind="set-upscale",
                                              parents=[f.texture_asset_id], params={"profile_id": PID, "version": VID, "face": fid, "spike": "E47"}))
        st.update_face(PID, VID, fid, texture_asset_id=rec.id)
        print(fid, f.texture_asset_id, "->", rec.id, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
