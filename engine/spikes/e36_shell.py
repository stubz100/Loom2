"""Spike E36 (proto01_UIcast 03 §5 as 06 §2.4 changed it; D136 U6/U7, D137 stage 2): a character's clay dummy — its Pixal3D shell (the
image → 3D model of its animation reference) bound to its fitted skeleton. Eight characters: A1's Mara and Ines (their E23d shells) and six
with hard silhouettes, made through the app with CS1's A-pose prompt — a long coat, a long dress, a big hat with a cape, a child, a broad
heavy build, a creature with a tail.

  make     the six: a profile each, its animation reference (Klein, one), its body fitted (SDPose; S8's note), its shell (Pixal3D) — one GPU
           job at a time through the queue (D97); Mara's and Ines' E23d shells imported
  fix      the first make's findings: D109 stood each new shell "upright" by the smallest box, which tilts a figure holding its arms out
           (15–44°) — the turn taken back (tools/upright.undo_upright; the app's shell job no longer turns them); each reference's
           BiRefNet cut-out (the app's subject matte, one short engine job each) for the IoU — a grey coat on a grey wall defeats a colour
           key — and its box written into the shell's GLB, as the app's mesh graph now keeps it (the shell placed by its picture: a bun or
           a hat no longer shrinks it)
  measure  the browser half (frontend/src/spikes/e36Shell.ts, visible Edge, Vite on 1420): both weightings bound, the skeleton cast into the
           shell, the front points, the stretch in four poses, the silhouette and the views
  score    the shell's front silhouette against the reference's figure (E14's aligned IoU), the sheets, results.json

    orchestrator/.venv/Scripts/python.exe engine/spikes/e36_shell.py make|measure|score
Outputs under engine/spikes/out/e36/ (git-ignored); the sheets to .docs/proto01_UIcast/img/e36-*.jpg.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e36"
SRC = ROOT / "engine" / "spikes" / "out" / "cs1" / "proj"                  # A1 after CS1's rig: Mara and Ines refitted, their points kept
E23D = ROOT / "engine" / "spikes" / "out" / "e23d" / "meshes"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
NEW = [
    ("Fisherman", "an old fisherman with a grey beard and a weathered face", "a long yellow oilskin coat to the ankles, black rubber boots", {}),
    ("Dancer", "a young woman with dark hair tied in a bun", "a long flowing blue summer dress to the ankles, flat sandals", {}),
    ("Wanderer", "a tall lean traveller with a narrow face", "a wide-brimmed leather hat, a long dark hooded cape over the shoulders, leather boots", {}),
    ("Pip", "a seven-year-old boy with short brown hair", "a striped t-shirt, blue shorts, white sneakers", {"height_m": 1.2}),
    ("Bruno", "a heavy-set, broad-shouldered dock worker with a round face", "denim overalls over a red flannel shirt, work boots", {"build": "heavy"}),
    ("Skink", "a small green lizard creature standing upright on two legs, a reptile head and a long thick tail", "a short brown leather vest", {"height_m": 1.4}),
]


def log(m: str) -> None:
    print(time.strftime("%H:%M:%S"), m, flush=True)


def state() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save(s: dict) -> None:
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def make() -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    P.OUT = OUT
    app = P.App(OUT / "proj")
    s: dict = {"characters": {}}
    try:
        profiles = {p["name"]: p for p in P.api("GET", "/story/profiles")["items"]}
        for name, glb in (("Mara", "mara.glb"), ("Ines", "ines.glb")):
            mesh = P.api("POST", "/assets/import", {"paths": [str(E23D / glb)]})["items"][0]["id"]
            p = profiles[name]
            s["characters"][name] = {"pid": p["id"], "anim_ref": p["versions"][0]["anim_ref_asset_id"], "mesh": mesh, "source": "E23d", "note": p["versions"][0]["anim_ref_note"]}
        save(s)
        for name, look, outfit, body in NEW:
            c: dict = {"source": "made"}
            t0 = time.time()
            p = P.api("POST", "/story/profiles", {"name": name, "cls": "character", "appearance": f"{name}, {look}", "outfit": outfit})
            c["pid"] = p["id"]
            if body:
                P.api("PATCH", f"/story/profiles/{p['id']}", {"revision": p["revision"], "versions": [{"id": "v1", "body": body}]})
            q = P.api("POST", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "count": 1})
            for jid in q["job_ids"]:
                j = P.wait_job(jid)
                if j["status"] != "done":
                    raise RuntimeError(f"{name}'s reference: {j.get('error')}")
            c["ref_s"] = round(time.time() - t0, 1)
            deadline = time.time() + 120
            while time.time() < deadline and not P.api("GET", f"/story/profiles/{p['id']}")["versions"][0]["anim_ref_asset_id"]:
                time.sleep(1)
            v = P.api("GET", f"/story/profiles/{p['id']}")["versions"][0]
            c["anim_ref"] = v["anim_ref_asset_id"]
            t1 = time.time()
            j = P.wait_job(P.api("POST", f"/story/profiles/{p['id']}/versions/v1/body/fit")["job_id"])
            c["fit_s"] = round(time.time() - t1, 1)
            c["fit_ok"] = j["status"] == "done"
            c["fit_error"] = j.get("error")
            v = P.api("GET", f"/story/profiles/{p['id']}")["versions"][0]
            c["note"] = v["anim_ref_note"]
            t2 = time.time()
            m = P.wait_job(P.api("POST", "/jobs", {"recipe": {"kind": "image_to_mesh", "asset_id": c["anim_ref"]}, "stage": False})["jobs"][0]["id"], timeout=1800)
            c["mesh_s"] = round(time.time() - t2, 1)
            c["mesh"] = ((m.get("result") or {}).get("asset_ids") or [None])[0]
            c["mesh_error"] = m.get("error")
            s["characters"][name] = c
            save(s)
            log(f"{name}: reference {c['ref_s']} s, fit {c['fit_s']} s ({'ok' if c['fit_ok'] else c['fit_error']}, note {c['note']}), shell {c['mesh_s']} s")
    finally:
        app.close()


def fix() -> None:
    from loom2.tools.upright import figure_box, read_glb, set_scene_extras, undo_upright
    import e23a_joins as A
    s = state()
    for name, c in s["characters"].items():
        if c.get("source") != "made" or not c.get("mesh") or c.get("unturned"):
            continue
        rec = json.loads(next((OUT / "proj" / "assets").glob(f"*/{c['mesh']}.json")).read_text(encoding="utf-8"))
        angles = (rec.get("params") or {}).get("upright_deg") or [0.0, 0.0, 0.0]
        undo_upright(OUT / "proj" / rec["path"], [float(a) for a in angles])
        c["unturned"] = angles
        log(f"{name}: the turn {angles} taken back")
    save(s)
    (OUT / "mattes").mkdir(exist_ok=True)
    todo = [n for n in s["characters"] if not (OUT / "mattes" / f"{n}.png").is_file()]
    with A.Session() if todo else nullcontext() as x:
        for name, c in ((n, s["characters"][n]) for n in todo):
            ref = OUT / "proj" / P_asset_path(c["anim_ref"])
            g = {"1": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "BiRefNet-general.safetensors"}},
                 "2": {"class_type": "LoadImage", "inputs": {"image": x.e.upload(ref)}},
                 "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["2", 0]}},
                 "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
                 "99": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": f"e36/matte_{name}"}}}
            h, _, _ = x.e.run(g)
            got = A.download(x.e, h, "99", OUT / "mattes" / name)[0]
            shutil.move(str(got), OUT / "mattes" / f"{name}.png")
            shutil.rmtree(OUT / "mattes" / name, ignore_errors=True)
            log(f"{name}: the cut-out")
    for name, c in s["characters"].items():                              # the box the app's mesh graph now keeps (E36's second finding)
        rec = json.loads(next((OUT / "proj" / "assets").glob(f"*/{c['mesh']}.json")).read_text(encoding="utf-8"))
        glb = OUT / "proj" / rec["path"]
        doc, _ = read_glb(glb)
        if not ((doc.get("scenes") or [{}])[doc.get("scene", 0)].get("extras") or {}).get("loom2", {}).get("figure_box"):
            box = figure_box(OUT / "mattes" / f"{name}.png")
            set_scene_extras(glb, {"figure_box": box})
            log(f"{name}: the figure box {box}")


def measure() -> None:
    s = state()
    P.OUT = OUT
    app = P.App(OUT / "proj")
    try:
        inputs = []
        for name, c in s["characters"].items():
            if not c.get("mesh"):
                continue
            v = P.api("GET", f"/story/profiles/{c['pid']}")["versions"][0]
            inputs.append({"name": name, "body": v["body"], "points": v["body_points"], "mesh": c["mesh"]})
        (OUT / "browser").mkdir(exist_ok=True)
        r = subprocess.run(["node", str(Path(__file__).with_name("e36_browser.cjs")), json.dumps(inputs), str(OUT / "browser")], cwd=str(ROOT / "frontend"),
                           capture_output=True, text=True, encoding="utf-8", timeout=3600, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
        print(r.stdout[-2000:], r.stderr[-3000:])
        if r.returncode != 0:
            raise RuntimeError("the browser half failed")
    finally:
        app.close()


def figure_mask(path: Path) -> np.ndarray:
    """The reference's figure on its plain ground: what differs from the corners' colour, closed and opened a little."""
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    bg = np.median(np.stack([a[2, 2], a[2, -3], a[-3, 2], a[-3, -3]]), axis=0)
    m = Image.fromarray(((np.abs(a - bg).sum(-1) > 45) * 255).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return np.asarray(m) > 127


def score() -> None:
    from e14_mesh import iou_aligned
    s = state()
    rows = json.loads((OUT / "browser" / "results.json").read_text(encoding="utf-8"))
    res: dict = {"characters": {}}
    for row in rows:
        name, c = row["name"], s["characters"][row["name"]]
        ref = OUT / "proj" / P_asset_path(c["anim_ref"])
        sil = np.asarray(Image.open(OUT / "browser" / f"{name}_silhouette.png").convert("L")) > 127
        matte = OUT / "mattes" / f"{name}.png"
        mask = np.asarray(Image.open(matte).convert("L").resize(Image.open(ref).size)) > 127 if matte.is_file() else figure_mask(ref)
        iou = iou_aligned(mask, sil)
        joints = row.get("joints") or []
        markers = row.get("markers") or []
        front = row.get("front") or []
        out = {"source": c.get("source"), "note": c.get("note"), "times": {k: c.get(k) for k in ("ref_s", "fit_s", "mesh_s")}, "iou": round(iou, 3),
               "joints_inside": f"{sum(1 for j in joints if j['inside'])}/{len(joints)}",
               "joints_outside": [j["j"] for j in joints if not j["inside"]],
               "joint_depth_cm_median": round(float(np.median([abs(j["depth_cm"]) for j in joints if j["depth_cm"] is not None] or [np.nan])), 1),
               "face_front_cm": {m["m"]: m["front_cm"] for m in markers if m["m"] in ("nose", "r_eye", "l_eye")},
               "front_err_median": round(float(np.median([f["err"] for f in front] or [np.nan])), 3) if front else None,
               "front_err_worst": max(front, key=lambda f: f["err"]) if front else None}
        for w in ("proximity", "heat"):
            r = row.get(w) or {}
            out[w] = {"bind_ms": r.get("bind_ms"), "triangles": r.get("triangles"), "stretch": r.get("stretch")}
        res["characters"][name] = out
        sheet(name, ref, row)
        log(f"{name}: IoU {out['iou']}, joints inside {out['joints_inside']} (out: {out['joints_outside']}), depth {out['joint_depth_cm_median']} cm, "
            f"front {out['front_err_median']}; over 2× walk/sit/crouch proximity "
            f"{[out['proximity']['stretch'][k]['over2'] for k in ('walk', 'sit', 'crouch')]} heat {[out['heat']['stretch'][k]['over2'] for k in ('walk', 'sit', 'crouch')]}")
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


def P_asset_path(asset_id: str) -> str:
    rec = json.loads(next((OUT / "proj" / "assets").glob(f"*/{asset_id}.json")).read_text(encoding="utf-8"))
    return rec["path"]


def sheet(name: str, ref: Path, row: dict) -> None:
    """The reference, then each weighting's bind, walk, sit and crouch."""
    b = OUT / "browser"
    tiles = [[Image.open(ref).convert("RGB")]]
    for w in ("proximity", "heat"):
        tiles.append([Image.open(b / f"{name}_{w}_{v}.png").convert("RGB") for v in ("bind", "walk", "sit", "crouch")])
    th = 300
    def fit(im: Image.Image) -> Image.Image:
        return im.resize((max(1, round(im.width * th / im.height)), th))
    rows = [[fit(t) for t in r] for r in tiles]
    W = max(sum(t.width for t in r) + 8 * (len(r) - 1) for r in rows) + 120
    out = Image.new("RGB", (W, len(rows) * (th + 8) + 8), (24, 24, 24))
    d = ImageDraw.Draw(out)
    for k, (label, r) in enumerate(zip(("reference", "proximity", "bone heat"), rows)):
        y = 8 + k * (th + 8)
        d.text((8, y + 4), label, fill=(225, 225, 225))
        x = 120
        for t in r:
            out.paste(t, (x, y)); x += t.width + 8
    out.save(IMG / f"e36-{name.lower()}.jpg", quality=84)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["make", "fix", "measure", "score"])
    a = ap.parse_args()
    {"make": make, "fix": fix, "measure": measure, "score": score}[a.step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
