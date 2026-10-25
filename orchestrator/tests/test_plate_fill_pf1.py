"""PF1 (D135, proto01_animate 31 §4h): the plate projected and filled — a keyframe's projected composite and its bad mask (blobs) become an
Edit document with the mask as its selection and a Fill queued (Klein `fill`, expand 48, feather 32, the plate's seed, the place's surfaces
as the prompt); the Fill's finisher flattens the document into the keyframe and closes it; a mask under 0.2 % is the keyframe as projected
(no job); the method switch keeps the still and clears the keyframes; the heal is a tick on the layer."""
from __future__ import annotations

import hashlib
import io
import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_finals_d111 import _final_on_disk  # noqa: E402


def _blob(ws, img) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b = buf.getvalue()
    sha = hashlib.sha256(b).hexdigest()
    d = ws.temp_dir / "blobs"
    d.mkdir(parents=True, exist_ok=True)
    (d / sha).write_bytes(b)
    return sha


def test_the_prompt_and_the_method():
    from loom2.finals import FILL_LEAD, plate_fill_prompt, plate_method_check
    assert plate_fill_prompt("an empty room with white plaster walls") == f"{FILL_LEAD} an empty room with white plaster walls"
    assert plate_fill_prompt(None) == FILL_LEAD
    plate_method_check("filled", 721)                                       # no clip's limit: it is Stage's projection and Fills
    with pytest.raises(ValueError, match="projected and filled"):
        plate_method_check("move", 3)


async def test_a_keyframe_is_filled_and_lands_on_the_plate(tmp_path: Path, object_info: dict, monkeypatch):
    import test_lifecycle
    from fastapi import HTTPException
    from loom2.finals import FILL_LEAD, FINAL_PLATE_KEY_SURFACE, FinalStore
    from loom2.routes.finals import HealBody, KeyBody, PlateMethodBody, final_plate_heal, final_plate_key, final_plate_method
    from loom2.stages import StageStore
    from PIL import Image
    from test_graph_parity_d64 import _pin_review
    monkeypatch.setattr(test_lifecycle, "_tree", lambda root: _pin_review().full_roster(root))
    rig = test_lifecycle.Rig(tmp_path, object_info)
    try:
        st = StageStore(rig.ws).create("Room")
        store = FinalStore(rig.ws)
        f = _final_on_disk(rig.ws, st.id, st.cameras[0].id)
        still = rig.catalogue.ingest_file(store.pass_dir(f.id, "plate", "clay") / "0000.png", kind="image", move=False, suite="stage")
        f = store.update_layer(f.id, "plate", still_asset_id=still.id, status="running", prompt="an empty room with white plaster walls")
        rig.queue.load()
        await rig.queue.start()
        svc = types.SimpleNamespace(queue=rig.queue, hub=rig.queue.hub, app=rig.app, require_project=lambda: (rig.ws, rig.catalogue, rig.queue),
                                    require_documents=lambda: rig.docs)
        comp = Image.new("RGB", (128, 72), (200, 200, 205))
        hole = Image.new("L", (128, 72), 0)
        hole.paste(255, (0, 0, 24, 72))                                      # the left edge: what no keyframe saw
        body = KeyBody(frame=1, image=_blob(rig.ws, comp), mask=_blob(rig.ws, hole))
        with pytest.raises(HTTPException) as e:                              # a projected plate takes no keyframes
            await final_plate_key(svc, f.id, body)
        assert e.value.status_code == 422
        # the row's *Project and fill*: the still kept, running for Stage, the keyframes cleared
        fin = await final_plate_method(svc, f.id, PlateMethodBody(method="filled"))
        plate = next(x for x in fin["layers"] if x["id"] == "plate")
        assert (plate["method"], plate["status"], plate["keys"], plate["still_asset_id"]) == ("filled", "running", [], still.id)
        fin = await final_plate_key(svc, f.id, body)
        plate = next(x for x in fin["layers"] if x["id"] == "plate")
        key = plate["keys"][0]
        assert (key["frame"], key["asset_id"], key["heal"]) == (1, None, False) and abs(key["filled"] - 24 / 128) < 0.01 and plate["seed"] > 0
        job = rig.queue.get(key["job_id"])
        r = job.recipe
        assert (r["kind"], r["mode"], r["expand"], r["feather"], r["seeds"]) == ("inpaint", "fill", 48, 32, [plate["seed"]])
        from loom2.models import registry
        assert r["model_id"] == registry.default_model("inpaint", "full") != registry.default_model("inpaint", "open")   # the variant's own (D26)
        assert r["prompt_text"] == f"{FILL_LEAD} an empty room with white plaster walls"
        assert (job.origin.surface, job.origin.ref, job.origin.payload["frame"]) == (FINAL_PLATE_KEY_SURFACE, f.id, 1)
        od = rig.docs.get(r["document_id"])
        assert od.selection is not None and int((od.selection[:, :24] > 127).mean() * 100) == 100 and not (od.selection[:, 30:] > 127).any()
        j = await rig.wait(job.id, timeout=60)
        assert j.status == "done", (j.error, j.log_tail[-5:])
        plate = next(x for x in store.get(f.id).layers if x.id == "plate")
        landed = plate.keys[0]["asset_id"]
        a = rig.catalogue.get(landed)
        assert a is not None and a.lineage_kind == "plate-key" and (a.w, a.h) == (128, 72)
        assert r["document_id"] not in rig.docs.open                         # the document closed
        # almost nothing to fill: the composite is the keyframe, no job
        none = Image.new("L", (128, 72), 0)
        fin = await final_plate_key(svc, f.id, KeyBody(frame=2, image=_blob(rig.ws, comp), mask=_blob(rig.ws, none)))
        k2 = next(x for x in fin["layers"] if x["id"] == "plate")["keys"][1]
        assert k2["frame"] == 2 and k2["job_id"] is None and k2["asset_id"] and k2["filled"] == 0.0
        # refused: past the last frame, a mask of another size
        with pytest.raises(HTTPException):
            await final_plate_key(svc, f.id, KeyBody(frame=3, image=body.image, mask=body.mask))
        with pytest.raises(HTTPException):
            await final_plate_key(svc, f.id, KeyBody(frame=1, image=body.image, mask=_blob(rig.ws, Image.new("L", (64, 36), 255))))
        # the heal is a tick on the layer
        fin = await final_plate_heal(svc, f.id, HealBody(heal=True))
        assert next(x for x in fin["layers"] if x["id"] == "plate")["heal"] is True
        # the keyframe of a plate made again meanwhile keeps its own
        assert store.key_landed(f.id, 1, "job_gone", "ast_x") is None
    finally:
        await rig.close()


def test_routes_are_listed():
    from loom2.api import create_app
    from test_routes_d37 import flat_routes, route_rows
    rows = {row for r in flat_routes(create_app(Path(".")).routes) for row in route_rows(r)}
    assert {"POST /finals/{fid}/plate/keys", "PUT /finals/{fid}/layers/plate/heal"} <= rows
