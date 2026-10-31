"""D167 (W43): a final keeps the one depth range Stage rendered every depth pass of it with — a layer drawn again later uses the same."""
from pathlib import Path

from PIL import Image


def test_a_final_keeps_its_depth_range(tmp_path: Path):
    from loom2.finals import FinalStore
    from loom2.routes.finals import FinalCreate
    from loom2.workspace import Workspace
    ws = Workspace.create(tmp_path / "p", name="P")
    png = ws.temp_dir / "g.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (128, 128), 100).save(png)
    body = FinalCreate(stage_id="stg_1", camera_id="cam_1", stage_revision=0, range={"start": 48, "end": 96}, size={"w": 128, "h": 128}, frames=2,
                       depth={"near": 3.0, "far": 30.0})
    data = body.model_dump(exclude={"layers"}) | {"layers": [{"id": "plate", "kind": "plate", "name": "P", "method": "projected"}, {"id": "shadows", "kind": "shadows", "name": "S", "method": "stage"}]}
    f = FinalStore(ws).create(data, {"plate": {"depth": [png] * 2, "clay": [png] * 2}, "shadows": {"clay": [png] * 2}}, {})
    again = FinalStore(ws).get(f.id)
    assert again.depth == {"near": 3.0, "far": 30.0} and again.range == {"start": 48, "end": 96}
    assert FinalCreate(stage_id="s", camera_id="c", stage_revision=0, range={"start": 0, "end": 1}, size={"w": 8, "h": 8}, frames=1).depth is None   # made before D167
