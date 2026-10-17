"""D92: the swatch pack of the seeded World library, made on the rig through the real route — so a fresh project shows pictures, not
glyphs, for every built-in look entry.

A temporary orchestrator (its own state, the default sample model — `default_for = ["swatch"]`, Klein 4B, D91) opens a new project, reads
its library (`GET /story/library` seeds it), takes every entry shown by a picture (a look field's words: scene, art style, lighting, mood,
background, subject action / pose, lead text — the frontend's `needsPicture`; negatives and geometry are drawn) and queues them in one
batch through `POST /preset-icons/make` (run now, the pack's one seed). Per job the wall seconds; the engine's peak VRAM over the pack; the
output sane (the swatch size, not black or flat). A contact sheet goes to engine/spikes/out/sm/pack_sheet.png for a look, and the pack is
installed into the app's state (`.loom2_state/preset_icons`, LOOM2_STATE overrides; the swatches there before are moved aside to
`preset_icons.before-<stamp>/` first). `--only field=value;…` remakes the named ones with `--seed` (a broken swatch, after a look).

    orchestrator/.venv/Scripts/python.exe scripts/swatch_pack.py [--only "mood=eerie;style=photoreal" --seed 91] [--no-install]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "orchestrator"))

import cr_acceptance as cr  # noqa: E402  (the API helpers, the VRAM sampler, the sanity check)

cr.PORT, cr.TOKEN = 8781, "pack"
OUT = ROOT / "engine" / "spikes" / "out" / "sm"
PICTURE_FIELDS = {"scene", "style", "lighting", "mood", "background", "subject.description", "subject.action", "subject.pose", "text"}   # swatches.ts SWATCH_FIELDS
BAR_PEAK_GB = 14.5
api, log = cr.api, cr.log


def contact_sheet(rows: list[tuple[str, str, Image.Image | None]], path: Path, cell: int = 160) -> None:
    """The pack as a grid: each swatch with its field and words under it (a missing one is a grey cell)."""
    cols = 8
    lines = 3
    h = cell + 12 * lines + 6
    sheet = Image.new("RGB", (cols * cell, ((len(rows) + cols - 1) // cols) * h), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except OSError:
        font = ImageFont.load_default()
    for i, (field, value, img) in enumerate(rows):
        x, y = (i % cols) * cell, (i // cols) * h
        if img is not None:
            sheet.paste(img.convert("RGB").resize((cell - 4, cell - 4)), (x + 2, y + 2))
        else:
            d.rectangle([x + 2, y + 2, x + cell - 2, y + cell - 2], fill=(70, 70, 70))
        words = f"{field}: {value}"
        for k in range(lines):
            d.text((x + 3, y + cell + 1 + 12 * k), words[k * 26:(k + 1) * 26], fill=(220, 220, 220), font=font)
    sheet.save(path)


def install(state_tmp: Path, made: list[tuple[str, str]], only: bool) -> Path:
    """The swatches into the app's state, through its own store (the file first, then the index); the old ones moved aside first."""
    from loom2.config import default_state_dir
    from loom2.preset_icons import PresetIconStore, icon_key
    real = default_state_dir()
    dst = real / "preset_icons"
    if dst.is_dir() and not only:
        aside = real / f"preset_icons.before-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copytree(dst, aside)
        log(f"the swatches there before: copied to {aside}")
    src, store = PresetIconStore(state_tmp), PresetIconStore(real)
    meta = {(i.field, i.value): i for i in src.list()}
    for field, value in made:
        rec = meta.get((field, value))
        if rec is not None:
            store.store_from(field, value, src.path(icon_key(field, value)), model_id=rec.model_id, seed=rec.seed)
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help='remake these: "field=value;field=value"')
    ap.add_argument("--seed", type=int, default=0, help="the seed for --only (0: the pack's seed)")
    ap.add_argument("--no-install", action="store_true", help="leave the app's state alone")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlopen(f"http://{cr.ENGINE}/system_stats", timeout=3)
        print("an engine is already listening on 8188: stop it (scripts/engine-stop.ps1)")
        return 2
    except Exception:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="loom2-pack-"))
    from loom2.config import AppState
    AppState(tmp / "state").update_settings({"models_root": os.environ.get("LOOM2_MODELS", "F:/loom2-models"), "mounted_model_trees": [], "variant": "full"})
    env = {**os.environ, "LOOM2_TOKEN": cr.TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch_log = (OUT / "pack_orchestrator.log").open("w", encoding="utf-8")
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(cr.PORT), "--state", str(tmp / "state")], cwd=str(ROOT / "orchestrator"),
                            env=env, stdout=orch_log, stderr=subprocess.STDOUT, text=True)
    failures: list[str] = []
    row: dict = {"stamp": time.strftime("%Y-%m-%d %H:%M"), "part": "pack", "only": a.only}

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text, flush=True)
        if not ok:
            failures.append(text)

    vram = cr.VramSampler()
    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health")
                break
            except Exception:
                time.sleep(0.3)
        proj = tmp / "proj"
        api("POST", "/project", {"path": str(proj), "name": "Pack", "size_cap_gb": 20})
        api("POST", "/queue/unpause", {})
        caps = api("GET", "/capabilities")
        model = next(m for m in caps["sample_models"] if m["default"])
        check(model["health"] in ("present", "verified"), f"the default sample model {model['id']}: weights {model['health']}")
        lib = api("GET", "/story/library")
        if a.only:
            items = [tuple(x.split("=", 1)) for x in a.only.split(";") if "=" in x]
        else:
            items = [(e["field"], e["text"]) for e in lib["entries"] if e["source"] == "builtin" and e["field"] in PICTURE_FIELDS]
        log(f"{len(items)} swatches on {model['id']} at {model['swatch_px']}² (library: {len(lib['entries'])} entries)")
        vram.mark()
        t_all = time.time()
        made = api("POST", "/preset-icons/make", {"items": [{"field": f, "value": v} for f, v in items], "stage": False, **({"seed": a.seed} if a.seed else {})})
        check(all(j["recipe"]["model_id"] == model["id"] for j in made["jobs"]), f"every swatch job runs {model['id']}")
        jobs = cr.wait_jobs([j["id"] for j in made["jobs"]])
        total = round(time.time() - t_all, 1)
        peak = vram.window()
        times, rows, ok_items = [], [], []
        icons = {(i["field"], i["value"]): i for i in api("GET", "/preset-icons")["items"]}
        for (field, value), j in zip(items, jobs):
            done = j["status"] == "done"
            check(done, f"{field}={value}: {j['status']} {j.get('error') or ''}")
            img = None
            if done:
                times.append(float(j["wall_s"]))
                img = cr.asset_image(proj, j["result"]["asset_ids"][0])
                check(cr.sane(img, (model["swatch_px"],) * 2), f"{field}={value}: {img.size}, not black or flat")
                check((field, value) in icons, f"{field}={value}: stored in the pack")
                ok_items.append((field, value))
            rows.append((field, value, img))
        sheet = OUT / ("pack_sheet.png" if not a.only else "pack_sheet_redo.png")
        contact_sheet(rows, sheet)
        row |= {"model": model["id"], "count": len(items), "done": len(ok_items), "total_s": total, "per_job_s": round(sum(times) / len(times), 2) if times else None,
                "first_s": times[0] if times else None, "peak_gb": peak, "sheet": str(sheet.relative_to(ROOT))}
        check(peak <= BAR_PEAK_GB, f"peak VRAM {peak} GB (bar ≤ {BAR_PEAK_GB} GB)")
        log(f"pack: {len(ok_items)}/{len(items)} in {total} s (≈ {row['per_job_s']} s a swatch warm), peak {peak} GB → {sheet}")
        if not a.no_install and ok_items:
            row["installed"] = str(install(tmp / "state", ok_items, bool(a.only)))
            log(f"installed into {row['installed']}")
    except Exception as e:  # noqa: BLE001
        check(False, f"exception: {type(e).__name__}: {e}")
    finally:
        vram.stop = True
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=30)
        except Exception:
            orch.kill()
        orch_log.close()
        shutil.rmtree(tmp, ignore_errors=True)
    row["failures"] = failures
    (OUT / "results.jsonl").open("a", encoding="utf-8").write(json.dumps(row, default=str) + "\n")
    print(json.dumps(row, indent=1, default=str))
    print(f"{len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
