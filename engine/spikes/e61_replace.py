"""E61 (D184, C5): Wan Animate's *replacement* mode on the hybrid — the character put into the plate itself, with the plate's light,
instead of laid over it. Takes a C5 final on the walk's project (its generated plate, the hero's layer: the pose guide, the reference, the
window it was performed in and the matte SAM 3 made there) and one batch's job record from the project's queue: the batch's graph is
built again exactly as the orchestrator sent it (`pipeline.finalize` on the record's recipe — the reference padded, the pose guide
uploaded — against the engine started by hand, nothing else on the GPU), then patched with the pinned node's two optional inputs —
`background_video` (the plate's frames of that batch, each cropped to the frame's window as `finals.paste_back` reads it, so the engine
sees the street exactly where the hero stands) and `character_mask` (the window matte frames, dilated, as a mask video) — and sent to the
engine. The result is pasted back into the plate by the layer's window math; outputs under engine/spikes/out/e61/: the composed frames,
a sheet beside the overlay's (the final's assembled clip at the same moments), FaceSim on both.
    scripts/engine-start.ps1 -State F:/loom2-projects/_propo02-state     (the orchestrator stopped — one job on the GPU, rule 10)
    orchestrator/.venv/Scripts/python.exe engine/spikes/e61_replace.py <final_id> [batch k = 0] [prompt id: a run made already, read from the history]
    E61_BG=plate (default) | overlay — what the background video is: the plate, or the final's assembly with the hero laid over it
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import av
import httpx
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))
STATE = Path("F:/loom2-projects/_propo02-state")
PROJECT = Path("F:/loom2-projects/propo02-followed")
MODELS = Path("F:/loom2-models")
OUT = ROOT / "engine" / "spikes" / "out" / "e61"
ENGINE = "http://127.0.0.1:8188"
HERO = "ast_5a39c904"                                     # Nora's hero still
DILATE = 6                                               # px at the window's scale
BG = os.environ.get("E61_BG", "plate")                   # plate: the street with nobody where the hero goes; overlay: the final's assembly (the hero
                                                         # laid over the plate — a person in the video for the mode to replace, as it is meant)


class Q:
    """The slice of JobQueue that pipeline.finalize reads — the project, its catalogue, the roster and the engine's client."""

    def __init__(self, app, ws, roster, catalogue, client) -> None:
        self.app, self.ws, self.roster, self.catalogue = app, ws, roster, catalogue
        self.engine = SimpleNamespace(client=client, started_at=None)
        self._oi = None

    async def object_info_fresh(self):
        if self._oi is None:
            self._oi = await self.engine.client.object_info()
        return self._oi

    async def object_info_refresh(self):
        self._oi = await self.engine.client.object_info()
        return self._oi

    def progress(self, job, text: str) -> None:
        print("  ·", text)

    def check_cancel(self, job) -> None:
        pass


def crop_window(plate: Image.Image, win: list[float], size: tuple[int, int]) -> Image.Image:
    """The inverse of finals.paste_back: the frame's region the window covers — at (x0, y0), WINDOW / scale wide and high — scaled to the
    window's size; what falls outside the frame is the plate's edge colour."""
    x0, y0, s = win
    w, h = max(1, round(size[0] / s)), max(1, round(size[1] / s))
    a = np.asarray(plate.convert("RGB"))
    edge = tuple(int(x) for x in np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]).mean(axis=0))
    canvas = Image.new("RGB", (w, h), edge)
    canvas.paste(plate.convert("RGB"), (-round(x0), -round(y0)))
    return canvas.resize(size, Image.LANCZOS)


def mp4_from(ims: list[Image.Image], out: Path, fps: int) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = ims[0].size
    w, h = w - w % 2, h - h % 2
    with av.open(str(out), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        s.options = {"crf": "10", "preset": "medium"}
        for im in ims:
            im = im.convert("RGB")
            if im.size != (w, h):
                im = im.resize((w, h), Image.LANCZOS)
            for pkt in s.encode(av.VideoFrame.from_ndarray(np.asarray(im), format="rgb24")):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return out


def sheet(name: str, frames: list[Path], n: int = 5, h: int = 270) -> Path | None:
    if not frames:
        return None
    picks = [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
    ims = [Image.open(p).convert("RGB") for p in picks]
    ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    out = Image.new("RGB", (sum(im.width for im in ims) + 4 * (n - 1), h), (20, 20, 24))
    x = 0
    for im in ims:
        out.paste(im, (x, 0)); x += im.width + 4
    p = OUT / f"sheet-{name}.png"
    out.save(p)
    return p


def asset_file(asset_id: str) -> Path | None:
    hits = list((PROJECT / "assets").rglob(f"{asset_id}*"))
    return next((h for h in hits if h.is_file() and h.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")), None)


async def build_graph(job, recipe, q: Q) -> dict:
    from loom2.engine.pipeline import finalize
    sub = await finalize(job, recipe, q)
    return sub.compiled.graph


def main() -> None:
    from loom2.finals import WINDOW
    from loom2.queue import JobRecord
    from loom2.recipes import parse_recipe

    fid = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    done_pid = sys.argv[3] if len(sys.argv) > 3 else None                  # a run made already: its outputs read again from the history
    OUT.mkdir(parents=True, exist_ok=True)
    f = json.loads((PROJECT / "finals" / fid / "final.json").read_text(encoding="utf-8"))
    plate = next(x for x in f["layers"] if x["id"] == "plate")
    hero = next(x for x in f["layers"] if x["kind"] == "figure")
    lid, rate, fw, fh = hero["id"], int(f["rate"]), int(f["size"]["w"]), int(f["size"]["h"])
    fin_dir = PROJECT / "finals" / fid
    plate_frames = sorted((fin_dir / "plate" / "frames").glob("*.png"))
    matte = sorted((fin_dir / lid / "window" / "matte").glob("*.png"))
    wins = hero.get("window") or []
    assert plate["status"] == "done" and plate_frames and matte and wins, (plate["status"], len(plate_frames), len(matte), len(wins))
    batch = hero["batches"][k]
    jobs = json.loads((PROJECT / "jobs" / "queue.json").read_text(encoding="utf-8"))["jobs"]
    rec = next((j for j in jobs if j.get("id") == batch["job_id"]), None)
    assert rec, f"the batch's job {batch['job_id']} is no longer in the queue's record"
    job = JobRecord.model_validate(rec)
    recipe = parse_recipe(rec["recipe"])
    length, offset = int(recipe.frames), int(recipe.chain.offset if recipe.chain else 0)
    print(f"final {fid} {fw}×{fh} @ {rate}: plate {len(plate_frames)} frames; {hero['name']}'s layer {lid}, batch {k} = job {job.id}: "
          f"{length} frames from {offset}, {recipe.width}×{recipe.height}, the window moving {wins[offset]} → {wins[min(offset + length, len(wins)) - 1]}")
    eng = httpx.Client(timeout=600)
    idx = list(range(offset, min(offset + length, len(plate_frames))))
    w, h = WINDOW
    t0 = time.time()
    if done_pid:
        pid = done_pid
        hst = eng.get(f"{ENGINE}/history/{pid}").json()[pid]
        secs = 0
    else:
        pid, hst, secs = run_batch(k, job, recipe, plate_frames, matte, wins, rate, idx, eng)
    paste_back_run(f, fid, lid, batch, k, pid, hst, secs, length, offset, idx, wins, plate_frames, rate, eng)


def run_batch(k: int, job, recipe, plate_frames: list[Path], matte: list[Path], wins: list, rate: int, idx: list[int], eng: httpx.Client) -> tuple[str, dict, int]:
    """The batch's graph as the orchestrator sent it — the reference padded and the pose guide uploaded again, against the engine by hand —
    patched with the plate's window crops and the window matte, and run: the prompt id, its history entry and the seconds."""
    from loom2.catalogue import Catalogue
    from loom2.config import AppState
    from loom2.engine.client import ComfyClient
    from loom2.finals import WINDOW
    from loom2.roster import Roster
    from loom2.workspace import Workspace
    t0 = time.time()
    app = AppState(STATE, "full")
    ws = Workspace.open(PROJECT)
    roster = Roster(app.models_root, [Path(p) for p in app.settings.mounted_model_trees], app.settings.variant).scan()
    catalogue = Catalogue(ws, app.settings.thumbnail_sizes)
    client = ComfyClient(timeout=600)
    q = Q(app, ws, roster, catalogue, client)
    graph = asyncio.run(build_graph(job, recipe, q))
    node = next(nid for nid, v in graph.items() if v.get("class_type") == "WanAnimateToVideo")
    w, h = int(graph[node]["inputs"]["width"]), int(graph[node]["inputs"]["height"])
    assert (w, h) == WINDOW == (recipe.width, recipe.height), (w, h, WINDOW, recipe.width, recipe.height)
    print("graph rebuilt:", len(graph), "nodes; WanAnimateToVideo", node, "length", graph[node]["inputs"].get("length"), "offset", graph[node]["inputs"].get("video_frame_offset"), "size", (w, h))
    (OUT / f"graph-{job.id}.json").write_text(json.dumps(graph, indent=1), encoding="utf-8")
    # the plate's frames of the batch, each cropped to its window; the window matte as the mask
    src = plate_frames
    if BG == "overlay":                                                  # the assembly's frames at the final's rate, put beside the plate's by the first run
        over = {int(p.stem): p for p in (OUT / f"overlay-{k}").glob("*.png")}
        assert all(i in over for i in idx), "the overlay's frames are missing — run the plate variant first (it extracts them)"
        src = [over.get(i, plate_frames[i]) for i in range(len(plate_frames))]
    bg = [crop_window(Image.open(src[i]), wins[i], (w, h)) for i in idx]
    mk = [Image.open(matte[i]).convert("L").filter(ImageFilter.MaxFilter(DILATE * 2 + 1)).convert("RGB").resize((w, h), Image.NEAREST) for i in idx]
    bg_mp4, mk_mp4 = mp4_from(bg, OUT / f"background-{k}-{BG}.mp4", rate), mp4_from(mk, OUT / f"mask-{k}.mp4", rate)
    bg[0].save(OUT / f"background-{k}-{BG}-first.png"); mk[0].save(OUT / f"mask-{k}-first.png")

    def upload(path: Path) -> str:
        with path.open("rb") as fh:
            r = eng.post(f"{ENGINE}/upload/image", files={"image": (path.name, fh, "application/octet-stream")}, data={"overwrite": "true"})
        r.raise_for_status()
        return r.json()["name"]

    bg_name, mk_name = upload(bg_mp4), upload(mk_mp4)
    graph["e61bg"] = {"class_type": "LoadVideo", "inputs": {"file": bg_name}}
    graph["e61bgc"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["e61bg", 0]}}
    graph["e61mk"] = {"class_type": "LoadVideo", "inputs": {"file": mk_name}}
    graph["e61mkc"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["e61mk", 0]}}
    graph["e61mask"] = {"class_type": "ImageToMask", "inputs": {"image": ["e61mkc", 0], "channel": "red"}}
    graph[node]["inputs"]["background_video"] = ["e61bgc", 0]
    graph[node]["inputs"]["character_mask"] = ["e61mask", 0]
    for v in graph.values():                                            # the output under a prefix of ours
        if v.get("class_type") in ("SaveImage", "SaveVideo", "VHS_VideoCombine", "SaveAnimatedWEBP") and "filename_prefix" in v.get("inputs", {}):
            v["inputs"]["filename_prefix"] = f"e61/replace-{k}-{BG}"
    (OUT / f"graph-{job.id}-patched.json").write_text(json.dumps(graph, indent=1), encoding="utf-8")
    r = eng.post(f"{ENGINE}/prompt", json={"prompt": graph, "client_id": f"e61-{uuid.uuid4().hex[:8]}"})
    if r.status_code != 200:
        print("refused:", r.text[:2000]); sys.exit(1)
    pid = r.json()["prompt_id"]
    t0 = time.time()
    print("queued", pid)
    while True:
        hst = eng.get(f"{ENGINE}/history/{pid}").json().get(pid)
        if hst and hst.get("status", {}).get("completed"):
            break
        if hst and hst.get("status", {}).get("status_str") == "error":
            print("error:", json.dumps(hst.get("status"))[:2000]); sys.exit(1)
        time.sleep(5)
    secs = round(time.time() - t0)
    print(f"done in {secs} s")
    return pid, hst, secs


def paste_back_run(f: dict, fid: str, lid: str, batch: dict, k: int, pid: str, hst: dict, secs: int, length: int, offset: int, idx: list[int], wins: list,
                   plate_frames: list[Path], rate: int, eng: httpx.Client) -> None:
    w, h = 480, 848
    # the window's result (the graph's own SaveImage — what a LoadVideo echoes is its input), pasted back into the plate by the layer's window math
    win_dir, comp_dir = OUT / f"window-{k}-{BG}", OUT / f"comp-{k}-{BG}"
    for d in (win_dir, comp_dir):
        d.mkdir(exist_ok=True)
        for p in d.glob("*.png"):
            p.unlink()
    n = 0
    for o in (hst.get("outputs") or {}).values():
        for key in ("images", "gifs", "videos"):
            for item in o.get(key, []) or []:
                name, sub, typ = item.get("filename"), item.get("subfolder", ""), item.get("type", "output")
                if typ != "output":
                    continue
                data = eng.get(f"{ENGINE}/view", params={"filename": name, "subfolder": sub, "type": typ}).content
                p = OUT / name
                p.write_bytes(data)
                if name.lower().endswith((".mp4", ".webm", ".mov")):
                    with av.open(str(p)) as c:
                        for fr in c.decode(video=0):
                            fr.to_image().save(win_dir / f"{n:04d}.png"); n += 1
                elif name.lower().endswith(".png"):
                    Image.open(p).convert("RGB").save(win_dir / f"{n:04d}.png"); n += 1
    print("window frames", n)
    for j, i in enumerate(idx[:n]):
        x0, y0, s = wins[i]
        ww, hh = max(1, round(w / s)), max(1, round(h / s))
        canvas = Image.open(plate_frames[i]).convert("RGB")
        canvas.paste(Image.open(win_dir / f"{j:04d}.png").convert("RGB").resize((ww, hh), Image.LANCZOS), (round(x0), round(y0)))
        canvas.save(comp_dir / f"{i:04d}.png")
    comp = sorted(comp_dir.glob("*.png"))
    # the overlay at the same moments: the final's assembled clip (RIFE'd to 24 fps — frame i of 16 ↔ round(1.5 i))
    over_dir = OUT / f"overlay-{k}"
    over_dir.mkdir(exist_ok=True)
    asm = PROJECT / "clips" / str(f.get("clip_id") or "") / "master"
    overlay: list[Path] = []
    if f.get("clip_id") and asm.is_dir():
        cj = json.loads((asm.parent / "clip.json").read_text(encoding="utf-8")) if (asm.parent / "clip.json").is_file() else {}
        ratio = float(cj.get("fps") or 24) / rate
        for i in idx[:n]:
            src = asm / f"{round(i * ratio):06d}.png"
            if src.is_file():
                dst = over_dir / f"{i:04d}.png"
                Image.open(src).convert("RGB").save(dst); overlay.append(dst)
    sh_r, sh_o = sheet(f"replace-{k}-{BG}", comp), sheet(f"overlay-{k}", overlay)
    report = {"final": fid, "layer": lid, "batch": batch, "background": BG, "prompt": pid, "frames": n, "seconds": secs, "window": [w, h], "length": length, "offset": offset,
              "sheets": {"replace": str(sh_r), "overlay": str(sh_o) if sh_o else None}}
    try:
        from loom2.tools.facesim import FaceSim, clip_identity
        fs = FaceSim(MODELS)
        hero_png = asset_file(HERO)
        ref = np.array(Image.open(hero_png).convert("RGB"))[:, :, ::-1]
        pick = lambda d: {kk: d.get(kk) for kk in ("status", "sampled", "with_face", "mean", "min", "min_frame") if kk in d}  # noqa: E731
        report["facesim"] = {"replace": pick(clip_identity(fs, ref, comp, samples=12)), "overlay": pick(clip_identity(fs, ref, overlay, samples=12)) if overlay else None,
                             "replace_window": pick(clip_identity(fs, ref, sorted(win_dir.glob("*.png")), samples=12))}
    except Exception as e:  # noqa: BLE001
        report["facesim"] = {"error": str(e)}
    (OUT / f"result-{k}-{BG}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
