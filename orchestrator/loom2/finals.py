"""D111 (PS5, proto01_animate 16): the final shot — a finished Stage scene split into layers and made into the shot. A **final** is a record
`finals/<id>/final.json` with one layer per entity of the scene (the plate, each bound figure, each prop, the shadows) and, beside it, each
layer's passes as PNG sequences at the shot's rate (`finals/<id>/<layer>/<pass>/0000.png …`), rendered by Stage (the client) and uploaded
as content-addressed blobs. Later steps add each layer's own frames (PS5b–c), its mattes (PS5d) and the assembly (PS5e) to the same tree.
Files are truth: the record is written through fsio with its schema version; the folders are the layers.
"""
from __future__ import annotations

import functools
import shutil
import threading
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .fsio import atomic_write_json, new_id, read_json, utc_now
from .recipes import RenderSettings
from .workspace import Workspace

FINAL_SCHEMA_VERSION = 1
FINAL_PLATE_SURFACE = "final_plate"               # PS5b: origin.surface of the plate's Stage shot; ref = the final's id
FINAL_LAYER_SURFACE = "final_layer"               # PS5c: origin.surface of a character layer's batch; ref = the final, payload {layer, batch, batches, seed}
FINAL_PLATE_PATH_SURFACE = "final_plate_path"     # CA3 (D130): origin.surface of the plate generated along the path; ref = the final's id
FINAL_PLATE_KEY_SURFACE = "final_plate_key"       # PF1 (D135): origin.surface of a filled plate's keyframe Fill; ref = the final, payload {frame}
BATCH, CARRY = 77, 5                              # E23a W1: 77-frame batches, the last 5 frames carried into the next (72 new)
CHARACTER_TAIL = "moving exactly as the pose shows. Plain studio background, static camera."
PLATE_LEAD = "The room is empty: there are no people and no objects in it, only the bare walls and floor."   # E28: a plate without the lead grew people
PLATE_PATH_TAIL = "The camera moves slowly through the place; nothing in it moves."   # CA3: E34's clip prompt ended on the camera's move
PLATE_PATH_MAX = 257                               # CA3: LTX-2.3's longest clip (I2V.frames) — a longer plate is projected
FILL_LEAD = ("Continue the surrounding surfaces seamlessly with the same materials and the same light; add nothing that is not already "
             "there. The place:")                  # PF1 (D135, E35d): a keyframe's Fill continues the place's surfaces, it does not re-describe it
KEY_FILL_MIN = 0.002                               # PF1: a keyframe whose bad share is below this is the keyframe as projected (no Fill)
LayerKind = Literal["plate", "figure", "prop", "shadows"]
LayerMethod = Literal["projected", "generated", "filled", "picture", "set", "move", "rendered", "drawn", "stage"]
LayerStatus = Literal["passes", "queued", "running", "done", "failed"]
MAX_FRAMES = 721                                   # 30 s at 24 fps (D96: ≈ 30 s a Shot, a warning beyond)
# the passes each kind of layer brings from Stage (PS5a); a pass with one frame is a still (the plate's frame-0 render)
LAYER_PASSES: dict[str, tuple[str, ...]] = {
    "plate": ("depth", "clay"),                    # the bare set through every frame's camera (its depth: the masks' base; its lit clay: the shadows' base)
    "figure": ("pose", "depth"),                   # the figure alone (with the set): the pose guide, and its depth (its mask against the bare set's)
    "prop": ("beauty", "depth"),                   # the prop alone (with the set): its 3D model rendered (R1), and its depth
    "shadows": ("clay",),                          # everything, lit: the shadows over the bare set's lit clay
}
DEFAULT_METHOD: dict[str, str] = {"plate": "projected", "figure": "move", "prop": "rendered", "shadows": "stage"}


def picture_plate(st: Any) -> str | None:
    """SC3e (D120): the picture a stage's plate is — its first visible picture set's (clean) picture — or None (the plate is projected:
    PS5b's Klein still of the bare set). A set from an image already is the place: the plate is that picture through its relief."""
    o = next((o for o in st.objects if o.kind == "set" and o.preset == "image" and o.visible and o.plate_asset_id), None)
    return o.plate_asset_id if o is not None else None


def built_plate(st: Any) -> str | None:
    """CW7 (proto01_UIcast 04 §5): the picture a stage's built set was skinned from — its first visible built set with a baked face — or
    None. The plate is then the set rendered through each frame's camera (method `set`): no Klein still, no projection to smear, no drift."""
    o = next((o for o in st.objects if o.kind == "set" and o.preset == "built" and o.visible and o.place_set is not None
              and any(f.texture_asset_id for f in o.place_set.faces)), None)
    if o is None:
        return None
    return o.place_set.sources[0].asset_id if o.place_set.sources else next(f.texture_asset_id for f in o.place_set.faces if f.texture_asset_id)


class FinalLayer(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str
    kind: LayerKind
    name: str
    object_id: str | None = None                   # the Stage object (a figure, a prop); None for the plate and the shadows
    method: LayerMethod
    profile_id: str | None = None                  # a figure's character or a prop's Cast prop (D93, D110), and its version
    version: str | None = None
    passes: dict[str, int] = Field(default_factory=dict)       # pass name → frames on disk
    keypoints: bool = False                        # a figure's per-frame COCO-18 keypoints are in keypoints.json (PS5c: where it starts; D107: its soles)
    status: LayerStatus = "passes"
    error: str | None = None
    still_asset_id: str | None = None              # PS5b: the plate's still (a Klein Stage shot of the bare set at frame 0); SC3e: the set's picture
    clip_id: str | None = None                     # CA3 (D130): the plate generated along the path — its LTX clip (frames resized and trimmed into frames/)
    prompt: str | None = None                      # PF1 (D135): the plate's place prompt (its still's) — the keyframes' Fills continue its surfaces
    keys: list[dict[str, Any]] = Field(default_factory=list)   # PF1: the filled plate's keyframes — [{frame, asset_id, filled, job_id, heal}] by frame
    heal: bool = False                             # PF1 (Q29): the frames between keyframes healed by small keyframes of their own
    frames_done: int = 0                           # the layer's own sequence on disk (`frames/`): the projected plate, a character's performance …
    job_ids: list[str] = Field(default_factory=list)   # the jobs that made (or make) the layer
    seed: int = 0                                  # PS5c: a character layer's performance seed (a re-take takes another)
    reference_asset_id: str | None = None          # PS5c: the animation reference placed where the figure starts (E23c: no ghost)
    guide_asset_id: str | None = None              # PS5c: the pose sequence as one video; CA3: the plate's depth sequence
    batches: list[dict[str, Any]] = Field(default_factory=list)   # PS5c: [{k, job_id, clip_id}] in order
    takes: list[dict[str, Any]] = Field(default_factory=list)     # D118 (AE4a): the layer's passes — [{id, preset, strength, model_id, job_id, frames, seed, made_at}]
    source: str | None = None                                      # D118: the take the layer shows (its frames under passes/<id>/), None = the original frames
    body: dict[str, Any] | None = None             # CS3 (proto01_UIcast 06 §2.10): a figure layer's body as its guide was drawn (the figure's own: Cast's then)
    body_hashes: list[str] = Field(default_factory=list)   # CS3: per frame, the body the guide was drawn with (skeleton keys sampled) — Stage says *the skeleton changed* where they differ


class ProcessingLayer(BaseModel):
    """D118 (AE4e): a pass over the flattened stack from a layer down — the composition rendered with only that layer and the ones below
    it, the pass's frames frozen as footage the composition shows right above that layer (`processing/<id>/frames/`). The composition
    says it is stale when the layers below changed since (their signature)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    id: str                                        # proc_<above>
    above: str                                     # the final layer it sits above: that layer and everything below went into it
    preset: str
    strength: float
    model_id: str
    job_id: str
    frames: int
    made_at: str
    signature: str                                 # the layers below as rendered (compositions.below_signature)
    below: list[int] = Field(default_factory=list) # the engine layers that went in, top to bottom


class Final(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    schema_version: int = FINAL_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: new_id("fin"))
    name: str = "Final"
    stage_id: str
    camera_id: str
    stage_revision: int
    range: dict[str, int]                          # the Stage frames (24 fps) it covers: {start, end}
    rate: Literal[16, 24] = 16                     # D102: F16 (RIFE to 24 at the end) or F24
    size: dict[str, int]                           # the layers' size: {w, h} (the pose-driven model's, Draft first, D18)
    frames: int                                    # frames per sequence at the rate
    shot_id: str | None = None                     # the Story shot it is made for (its take lands there, PS5e)
    shot_version: str | None = None                # D125 (A1): that shot's version (the For chip's); None in a final made before it — the current one
    stamps: dict[str, str] = Field(default_factory=dict)          # RC1: what it read of its stage, part by part (shot_graph.stage_stamps); empty before RC1
    layers: list[FinalLayer] = Field(default_factory=list)
    processing: list[ProcessingLayer] = Field(default_factory=list)   # D118 (AE4e): the passes over the stack below a layer
    clip_id: str | None = None                     # PS5e: the assembled shot
    assembly: dict[str, Any] | None = None         # PS5e: what the assembly did (offsets, occlusions, time, the conform)
    assembled_at: str | None = None
    render: RenderSettings = Field(default_factory=RenderSettings)   # AE5: the finished shot's render settings and output modules
    revision: int = 0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


def frames_at(start: int, end: int, rate: int) -> list[float]:
    """The Stage times (in 24 fps frames) a final samples: every frame at F24, every 1.5th at F16 (D102: the motion resampled, not cut)."""
    if end < start:
        return []
    step = 24 / rate
    n = int((end - start) / step + 1e-6) + 1
    return [round(start + i * step, 4) for i in range(n)]


def plate_method_check(method: str, frames: int) -> None:
    """The plate is projected (PS5b), projected and filled (PF1, D135), generated along the path (CA3, D130: at most LTX's longest clip),
    a picture set's picture (SC3e) or a built set rendered (CW7)."""
    if method not in ("projected", "filled", "generated", "picture", "set"):
        raise ValueError(f"the plate is projected, projected and filled, generated along the path, a picture set's picture or a built set (not {method!r})")
    if method == "generated" and frames > PLATE_PATH_MAX:
        raise ValueError(f"a plate generated along the path is at most {PLATE_PATH_MAX} frames (LTX-2.3's longest clip); this final has {frames} — project it")


def check(f: Final) -> None:
    if not 2 <= f.frames <= MAX_FRAMES:
        raise ValueError(f"a final has 2 to {MAX_FRAMES} frames (it has {f.frames})")
    if f.size.get("w", 0) < 128 or f.size.get("h", 0) < 128:
        raise ValueError("the layers' size is at least 128 × 128 (the video models' smallest)")
    ids = [x.id for x in f.layers]
    if len(set(ids)) != len(ids):
        raise ValueError("layer ids must be unique")
    for kind in ("plate", "shadows"):
        if sum(1 for x in f.layers if x.kind == kind) != 1:
            raise ValueError(f"a final has one {kind} layer")
        if next(x for x in f.layers if x.kind == kind).id != kind:            # V42: the routes and finishers find them by id
            raise ValueError(f"the {kind} layer's id is {kind!r}")
    for x in f.layers:
        if x.kind in ("figure", "prop") and not x.object_id:
            raise ValueError(f"layer {x.id}: a {x.kind} layer names its Stage object")
        if x.kind == "plate":
            plate_method_check(x.method, f.frames)
        for name in LAYER_PASSES[x.kind]:
            if x.passes.get(name) not in (f.frames,):
                raise ValueError(f"layer {x.id}: its {name} pass has {x.passes.get(name, 0)} frames, the final {f.frames}")


def plan_batches(n: int) -> list[dict[str, int]]:
    """A performance of n frames in Wan Animate's batches (E23a, W1): one batch of n frames (the model's 4k + 1 grid, at least 9) when it
    fits, else 77-frame batches, each after the first carrying the previous one's last 5 frames and reading the pose guide from where
    those 5 began (offsets 0, 77, 149, …: 72 new frames each). The last batch is only as long as the frames still owed plus the carry, on
    the grid and at least 9 (AE4's follow-up, 2026-10-22: a second batch of 77 frames for the 4 an 81-frame shot needs cost ≈ 4 min a pass)."""
    if n <= BATCH:
        m = max(9, n)
        return [{"frames": m + (-(m - 1) % 4), "offset": 0}]
    count = 1 + -(-(n - BATCH) // (BATCH - CARRY))
    out = [{"frames": BATCH, "offset": 0 if k == 0 else BATCH + (BATCH - CARRY) * (k - 1)} for k in range(count)]
    owed = n - (BATCH + (BATCH - CARRY) * (count - 2))               # the new frames the last batch still has to make
    m = max(9, owed + CARRY)
    out[-1]["frames"] = min(BATCH, m + (-(m - 1) % 4))
    return out


def stitch(batches: list[list[Path]], n: int) -> list[Path]:
    """The batches' frames as one sequence: the first batch whole, every later one without the frames it carried; n frames."""
    out: list[Path] = []
    for k, frames in enumerate(batches):
        out += frames if k == 0 else frames[CARRY:]
    if len(out) < n:
        raise ValueError(f"the batches made {len(out)} frames, the final needs {n}")
    return out[:n]


def to_lab(rgb: "np.ndarray") -> "np.ndarray":
    """sRGB (uint8) to CIE Lab (D65) — the colour distance the key and the assembly measure in."""
    import numpy as np
    c = rgb.astype(np.float32) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = c @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], dtype=np.float32).T
    xyz /= np.array([0.95047, 1.0, 1.08883], dtype=np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def central_blob(m: "np.ndarray") -> "np.ndarray":
    """The blob of a mask that holds its middle (the set pixel nearest the set pixels' median) — the figure, without specks of the ground
    the key let through. PIL's flood fill (no scipy here)."""
    import numpy as np
    from PIL import Image, ImageDraw
    ys, xs = np.nonzero(m)
    if not len(ys):
        return m
    my, mx = np.median(ys), np.median(xs)
    i = int(np.argmin((ys - my) ** 2 + (xs - mx) ** 2))
    im = Image.fromarray((m * 255).astype(np.uint8)).copy()                # its own pixels: fromarray may share a read-only buffer
    ImageDraw.floodfill(im, (int(xs[i]), int(ys[i])), 128, thresh=0)
    return np.asarray(im) == 128


def cutout(ref: Path) -> tuple["np.ndarray", "np.ndarray", tuple[int, int, int]]:
    """A character off its animation reference's plain ground (CA0 makes it on one): pixels ΔE > 14 from the border's median (Lab), the
    largest blob, softened (E23c's key). Returns the cropped image, its alpha and the ground colour."""
    import numpy as np
    from PIL import Image, ImageFilter
    a = np.asarray(Image.open(ref).convert("RGB"))
    lab = to_lab(a)
    border = np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])
    m = np.linalg.norm(lab - np.median(border, axis=0), axis=-1) > 14
    m = central_blob(m)
    if not m.any():
        raise ValueError("no figure stands out from the reference's ground")
    alpha = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0
    ys, xs = np.nonzero(alpha > 0.5)
    ground = tuple(int(v) for v in np.median(np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]), axis=0))
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1], ground   # type: ignore[return-value]


def place_reference(ref: Path, kp: list[list[float]] | None, w: int, h: int, out: Path) -> bool:
    """E23c (D105): the animation reference placed where the figure starts — its cut-out scaled to the figure's height in the first frame
    (nose to ankles is 0.86 of the reference's figure) with its feet on the figure's, on the reference's own ground — so Wan Animate leaves
    no standing copy of the reference behind (the ghost). False (nothing written) when the figure is not whole in the first frame."""
    import numpy as np
    from PIL import Image
    if not kp or len(kp) < 14:
        return False
    k = np.array(kp, dtype=np.float32)
    needed = [0, 8, 10, 11, 13]                                             # nose, the hips, the ankles (COCO-18)
    if (k[needed, 2] <= 0).any():
        return False
    feet = (k[10, :2] + k[13, :2]) / 2
    tall = float(np.linalg.norm(k[0, :2] - feet))
    if tall < 24 or not (0 <= feet[0] < w and 0 <= feet[1] <= h * 1.05):
        return False
    img, alpha, ground = cutout(ref)
    hh = max(8, int(tall / 0.86))
    ww = max(4, int(img.shape[1] * hh / img.shape[0]))
    pi = np.asarray(Image.fromarray(img).resize((ww, hh), Image.LANCZOS), dtype=np.float32)
    pa = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).resize((ww, hh), Image.LANCZOS), dtype=np.float32)[..., None] / 255.0
    canvas = np.full((h, w, 3), ground, dtype=np.float32)
    cx = float((k[8, 0] + k[11, 0]) / 2)
    x0, y0 = int(cx - ww / 2), int(feet[1] + 0.045 * tall - hh)
    sx0, sy0, sx1, sy1 = max(0, -x0), max(0, -y0), min(ww, w - x0), min(hh, h - y0)
    if sx1 <= sx0 or sy1 <= sy0:
        return False
    reg = canvas[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1]
    canvas[y0 + sy0:y0 + sy1, x0 + sx0:x0 + sx1] = reg * (1 - pa[sy0:sy1, sx0:sx1]) + pi[sy0:sy1, sx0:sx1] * pa[sy0:sy1, sx0:sx1]
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).save(out)
    return True


def plate_fill_prompt(place: str | None) -> str:
    """PF1 (D135): a keyframe Fill's prompt — the lead (continue the surfaces, add nothing), then the place as the author wrote it."""
    return f"{FILL_LEAD} {(place or '').strip()}".strip()


def plate_path_frames(n: int) -> int:
    """CA3 (D130): the clip a plate generated along the path is — the final's frames on LTX's 8k + 1 grid (trimmed back to n after)."""
    return n + (-(n - 1) % 8)


def plate_path_size(f: "Final", height: int, mult: int = 64) -> tuple[int, int]:
    """CA3: the clip's size — the video model's height (E34 measured 1024 × 576) at the final's aspect, on the guided clip's grid (LTX's
    IC-LoRA: ×64, the rig's 992 × 576 was refused); the frames are resized to the final's size when they land."""
    h = max(128, height - height % mult)
    w = max(128, round(h * f.size["w"] / f.size["h"] / mult) * mult)
    return w, h


def plate_path_guide(depth: list[Path], w: int, h: int, n: int, out: Path, fps: int) -> None:
    """CA3: the plate's depth pass (the bare set through every frame's camera) as the clip's guide — each frame at the clip's size, the
    last held to n frames (LTX's grid), one near-lossless video (stages.encode_guide)."""
    from PIL import Image

    from .stages import encode_guide
    tmp = out.parent / "_guide"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    paths = []
    for i, src in enumerate(depth):
        with Image.open(src) as im:
            im.convert("RGB").resize((w, h), Image.LANCZOS).save(tmp / f"{i:04d}.png")
        paths.append(tmp / f"{i:04d}.png")
    paths += [paths[-1]] * (n - len(paths))
    try:
        encode_guide(paths, out, fps)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def plate_path_recipe(f: "Final", model_id: str, still_id: str, guide_id: str, prompt: str, size: tuple[int, int], seed: int) -> dict[str, Any]:
    """CA3 (D130, E34): the plate generated along the path — LTX-2.3 from the plate's still, the bare set's depth through the IC-LoRA from
    frame 0 (Stage's guided method), at the final's rate, Draft."""
    place = prompt.strip().rstrip(".")
    return {"kind": "i2v", "model_id": model_id, "start_asset": still_id, "prompt_text": f"{PLATE_LEAD} {place + '. ' if place else ''}{PLATE_PATH_TAIL}",
            "frames": plate_path_frames(f.frames), "fps": f.rate, "width": size[0], "height": size[1], "preset": "draft", "seeds": [seed],
            "guide": {"asset_id": guide_id, "kind": "depth", "strength": 1.0}}


def character_recipe(f: "Final", layer: "FinalLayer", model_id: str, prompt: str, batch: dict[str, int], clip_id: str | None) -> dict[str, Any]:
    """One batch of a character layer: Wan Animate Move (Draft) on the layer's pose guide, with its placed reference, at the final's size
    and rate; a later batch continues the previous one (E23a W1)."""
    return {"kind": "i2v", "model_id": model_id, "start_asset": layer.reference_asset_id, "prompt_text": prompt, "frames": batch["frames"], "fps": f.rate,
            "width": f.size["w"], "height": f.size["h"], "preset": "draft", "seeds": [layer.seed],
            "guide": {"asset_id": layer.guide_asset_id, "kind": "pose", "strength": 1.0},
            "chain": {"clip_id": clip_id, "carry": CARRY, "offset": batch["offset"]}}


_LOCK = threading.RLock()                        # V34: one writer at a time across route threads and finishers (get → patch → save is atomic)


def _locked(fn):
    @functools.wraps(fn)
    def inner(self, *a, **k):
        with _LOCK:
            return fn(self, *a, **k)
    return inner


class FinalStore:
    """The finals on disk (`finals/<id>/final.json` and the layers' folders). V34: every read-modify-write of a record runs under one
    lock, so a finisher landing while a route writes loses nothing; a job is appended with `add_job`, never from a copy read before the
    submit. The composition beside it has its own revision (the client's); the record needs none for these writes."""

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.dir = ws.path / "finals"
        self.dir.mkdir(parents=True, exist_ok=True)

    def folder(self, fid: str) -> Path:
        return self.dir / fid

    def path(self, fid: str) -> Path:
        return self.folder(fid) / "final.json"

    def pass_dir(self, fid: str, layer: str, name: str) -> Path:
        return self.folder(fid) / layer / name

    def frames_dir(self, fid: str, lid: str) -> Path:
        """D118: where the layer's frames are — a take's `passes/<id>/` when one is its source, else its own `frames/`."""
        f = self.get(fid)
        layer = next((x for x in f.layers if x.id == lid), None) if f else None
        if layer is not None and layer.source and any(t.get("id") == layer.source for t in layer.takes):
            return self.pass_dir(fid, lid, f"passes/{layer.source}")
        return self.pass_dir(fid, lid, "frames")

    def processing_dir(self, fid: str, pid: str) -> Path:
        """D118 (AE4e): a processing layer's folder — `in/` (the stack below, rendered) and `frames/` (the pass's result)."""
        return self.folder(fid) / "processing" / pid

    @_locked
    def set_processing(self, fid: str, rec: ProcessingLayer) -> Final:
        """D118 (AE4e): a processing layer recorded (replaced by id when run again); the record's revision moves."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        f.processing = [p for p in f.processing if p.id != rec.id] + [rec]
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def remove_processing(self, fid: str, pid: str) -> Final:
        """D118 (AE4e): a processing layer dropped (its folder too); the composition takes its layer out on the next sync."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        if not any(p.id == pid for p in f.processing):
            raise KeyError(f"{fid} has no processing layer {pid}")
        shutil.rmtree(self.processing_dir(fid, pid), ignore_errors=True)
        f.processing = [p for p in f.processing if p.id != pid]
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    def matte_dir(self, fid: str, lid: str) -> Path:
        """D118 (AE4c): where a character layer's matte is — the shown take's own `matte/` when the pass changed her silhouette (the face
        pass does), else the layer's `matte/` (PS5d)."""
        f = self.get(fid)
        layer = next((x for x in f.layers if x.id == lid), None) if f else None
        if f is not None and layer is not None and layer.source and any(t.get("id") == layer.source for t in layer.takes):
            d = self.pass_dir(fid, lid, f"passes/{layer.source}/matte")
            if len(list(d.glob("*.png"))) == f.frames:
                return d
        return self.pass_dir(fid, lid, "matte")

    def sweep_unfinished(self, fid: str, lid: str) -> int:
        """D118 (AE4c): the folders of passes that never became takes (a chain that failed in the engine) dropped; how many."""
        f = self.get(fid)
        layer = next((x for x in f.layers if x.id == lid), None) if f else None
        if layer is None:
            return 0
        root = self.pass_dir(fid, lid, "passes")
        keep = {t.get("id") for t in layer.takes}
        n = 0
        for d in root.glob("take_*") if root.is_dir() else []:
            if d.is_dir() and d.name not in keep:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        return n

    @_locked
    def add_take(self, fid: str, lid: str, take: dict[str, Any], use: bool = True) -> Final:
        """D118: a pass's result recorded on the layer, and shown as its source when `use`."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        layer.takes = [t for t in layer.takes if t.get("id") != take["id"]] + [take]
        return self.update_layer(fid, lid, takes=layer.takes, source=take["id"] if use else layer.source)

    @_locked
    def set_source(self, fid: str, lid: str, take_id: str | None) -> Final:
        """D118: the layer shows this take (its frames must be on disk), or its original frames with None."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        if take_id is not None:
            if not any(t.get("id") == take_id for t in layer.takes):
                raise KeyError(f"{lid} has no take {take_id}")
            if len(list(self.pass_dir(fid, lid, f"passes/{take_id}").glob("*.png"))) != f.frames:
                raise ValueError(f"the take {take_id} has no frames on disk")
        return self.update_layer(fid, lid, source=take_id)

    @_locked
    def remove_take(self, fid: str, lid: str, take_id: str) -> Final:
        """D118: a take dropped (its frames too); the source falls back to the original when it was this one."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None or not any(t.get("id") == take_id for t in layer.takes):
            raise KeyError(f"{lid} has no take {take_id}")
        shutil.rmtree(self.pass_dir(fid, lid, f"passes/{take_id}"), ignore_errors=True)
        return self.update_layer(fid, lid, takes=[t for t in layer.takes if t.get("id") != take_id], source=None if layer.source == take_id else layer.source)

    def get(self, fid: str) -> Final | None:
        p = self.path(fid)
        return Final.model_validate(read_json(p)) if p.is_file() else None

    def list(self, stage_id: str | None = None) -> list[Final]:
        out = [Final.model_validate(read_json(p)) for p in self.dir.glob("fin_*/final.json")]
        return sorted([f for f in out if stage_id is None or f.stage_id == stage_id], key=lambda f: f.created_at, reverse=True)

    def save(self, f: Final) -> None:
        atomic_write_json(self.path(f.id), f.model_dump())

    def create(self, data: dict[str, Any], passes: dict[str, dict[str, list[Path]]], keypoints: dict[str, Any]) -> Final:
        """A final from its record and, per layer and pass, the frame files (blobs, in order; one file may stand for many frames — a still
        camera's identical renders). The folders are written first, the record last: a failed copy leaves no record."""
        f = Final.model_validate({**data, "id": new_id("fin"), "schema_version": FINAL_SCHEMA_VERSION, "revision": 0, "created_at": utc_now(), "updated_at": utc_now()})
        for x in f.layers:
            x.passes = {name: len(files) for name, files in passes.get(x.id, {}).items()}
            x.keypoints = x.id in keypoints
        check(f)
        try:
            for x in f.layers:
                for name, files in passes.get(x.id, {}).items():
                    d = self.pass_dir(f.id, x.id, name)
                    d.mkdir(parents=True, exist_ok=True)
                    for i, src in enumerate(files):
                        shutil.copyfile(src, d / f"{i:04d}.png")
                if x.id in keypoints:
                    atomic_write_json(self.folder(f.id) / x.id / "keypoints.json", {"schema_version": 1, "frames": keypoints[x.id]})
            self.save(f)
        except Exception:
            shutil.rmtree(self.folder(f.id), ignore_errors=True)
            raise
        return f

    @_locked
    def set_passes(self, fid: str, lid: str, passes: dict[str, list[Path]], keypoints: list[Any] | None, body: dict[str, Any] | None,
                   body_hashes: list[str]) -> Final:
        """CS3: a character layer's passes drawn again (the skeleton changed) — its pass folders and keypoints replaced, the body they were
        drawn with recorded. The frames it performed stay: a re-take from a batch replaces the ones after it."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        if layer.kind != "figure":
            raise ValueError("only a character layer's passes are drawn again")
        counts = {name: len(files) for name, files in passes.items()}
        for name in LAYER_PASSES["figure"]:
            if counts.get(name) != f.frames:
                raise ValueError(f"its {name} pass has {counts.get(name, 0)} frames, the final {f.frames}")
        if body_hashes and len(body_hashes) != f.frames:
            raise ValueError(f"{len(body_hashes)} body hashes for {f.frames} frames")
        for name, files in passes.items():
            d = self.pass_dir(fid, lid, name)
            new = d.with_name(name + ".new")
            shutil.rmtree(new, ignore_errors=True)
            new.mkdir(parents=True)
            for i, src in enumerate(files):
                shutil.copyfile(src, new / f"{i:04d}.png")
            shutil.rmtree(d, ignore_errors=True)
            new.rename(d)
        if keypoints is not None:
            atomic_write_json(self.folder(fid) / lid / "keypoints.json", {"schema_version": 1, "frames": keypoints})
            layer.keypoints = True
        layer.passes, layer.body, layer.body_hashes = counts, body, list(body_hashes)
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def update_layer(self, fid: str, lid: str, **patch: Any) -> Final:
        """One layer's fields changed (its status, still, jobs, frames done); the record's revision moves."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        for k, v in patch.items():
            setattr(layer, k, v)
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def add_job(self, fid: str, lid: str, job_id: str, **patch: Any) -> Final:
        """V34: a job appended to the layer's `job_ids` as they are *now* (a keyframe's Fill landing between the route's read and its write
        used to be overwritten), with the rest of the patch."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        layer = next((x for x in f.layers if x.id == lid), None)
        if layer is None:
            raise KeyError(f"{fid} has no layer {lid}")
        return self.update_layer(fid, lid, job_ids=[*layer.job_ids, job_id], **patch)

    def set_frames(self, fid: str, lid: str, files: list[Path], status: str = "done", still_asset_id: str | None = None) -> Final:
        """A layer's own sequence (`frames/`), one file per frame at the final's count; the layer is done (or runs on: a character's matte).
        SC3e: `still_asset_id` names the picture the frames were rendered from (a picture set's plate)."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        if len(files) != f.frames:
            raise ValueError(f"the layer's frames are {len(files)}, the final has {f.frames}")
        d = self.pass_dir(fid, lid, "frames")
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        for i, src in enumerate(files):
            shutil.copyfile(src, d / f"{i:04d}.png")
        return self.update_layer(fid, lid, frames_done=len(files), status=status, error=None, **({"still_asset_id": still_asset_id} if still_asset_id else {}))

    @_locked
    def set_result(self, fid: str, clip_id: str, stats: dict[str, Any]) -> Final:
        """PS5e: the assembled shot (a clip) and what the assembly did."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        f.clip_id, f.assembly, f.assembled_at = clip_id, stats, utc_now()
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def set_key(self, fid: str, key: dict[str, Any]) -> Final:
        """PF1: a filled plate's keyframe recorded (replacing the one at its frame), the keyframes kept in frame order."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        plate = next(x for x in f.layers if x.id == "plate")
        plate.keys = sorted([k for k in plate.keys if k.get("frame") != key["frame"]] + [key], key=lambda k: k["frame"])
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def key_landed(self, fid: str, frame: int, job_id: str, asset_id: str) -> Final | None:
        """PF1: a keyframe's Fill landed — its asset on the keyframe the job was made for (None when the plate was made again meanwhile)."""
        f = self.get(fid)
        plate = next((x for x in f.layers if x.id == "plate"), None) if f else None
        k = next((k for k in plate.keys if k.get("frame") == frame and k.get("job_id") == job_id), None) if plate else None
        if k is None:
            return None
        k["asset_id"] = asset_id
        f.revision += 1
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def set_render(self, fid: str, settings: RenderSettings) -> Final:
        """AE5: the render settings — the record's revision stays (they change what the next render writes, not what the shot is made of)."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        f.render = settings
        f.updated_at = utc_now()
        self.save(f)
        return f

    @_locked
    def set_clip(self, fid: str, clip_id: str) -> Final:
        """AE1: the finished shot (the composition rendered) is the final's clip now; the record's revision stays, so its composition
        stays fresh (a render changes nothing it was made from)."""
        f = self.get(fid)
        if f is None:
            raise KeyError(fid)
        f.clip_id = clip_id
        f.updated_at = utc_now()
        self.save(f)
        return f

    def keypoints(self, fid: str, lid: str) -> list:
        p = self.folder(fid) / lid / "keypoints.json"
        return list(read_json(p).get("frames") or []) if p.is_file() else []

    def delete(self, fid: str) -> bool:
        d = self.folder(fid)
        if not (d / "final.json").is_file():
            return False
        shutil.rmtree(d)
        return True
