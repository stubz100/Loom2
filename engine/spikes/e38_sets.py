"""Spike E38 (proto01_UIcast 04 §7; D136, D137 stage 6): the set builder — a room, a corridor or a street fitted to a picture (MoGe-2's
point map read by orchestrator/loom2/set_fit.py), the picture baked onto its faces (frontend stage/setBake.ts), what it never saw filled.

  make    the pictures, on a copy of A1's project (the engine one job at a time, D97):
            · five truth places — Stage's own built sets of known size (rooms of three sizes, a corridor, a street), a camera each, their
              Klein still from the clay (Stage's Make a frame); the truth is the set and the camera;
            · five found pictures — A1's room still and four Klein places (a kitchen, an alley, a long hall, a field with a fence);
  fit     MoGe-2 on each (the image → set job's relief), the set fitted: the kind, the sizes, the camera; against the truth where known;
  skin    each picture baked onto its fitted set at 1 cm texels: the share unseen or coarse per face, the seams at the corners, the texel the
          picture can fill; the textured set from its camera and from beside it (the sheet);
  second  New angle (left45) of the kitchen and the alley as a second picture, matched by orbiting the first camera about what it looks at
          (the sign chosen where the two bakes agree): the unseen share before and after;
  fill    Klein's Fill on each face's bad texels (PF1's neutral prompt), faces in order of how much each already has, for the kitchen and the
          middle room: the time a face and the look;
  move    E34's orbit and E35d's crane through each fitted set: the share of each frame no picture saw (one picture, then two);
  score   the table and the sheets (.docs/proto01_UIcast/img/e38-*.jpg), results.json.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e38_sets.py make|fit|skin|second|fill|move|score   # Vite on 1420
Outputs under engine/spikes/out/e38/ (git-ignored)."""
from __future__ import annotations

import argparse
import json
import math
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
from PIL import Image, ImageDraw  # noqa: E402

OUT = ROOT / "engine" / "spikes" / "out" / "e38"
A1 = ROOT / "engine" / "spikes" / "out" / "a1" / "project"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
EYE = 1.6                                                                     # an eye-level camera's height (m): the one number the author might give
REFIT = "--refit" in sys.argv
NEUTRAL = "Continue the surrounding surfaces seamlessly: the same materials, the same light."    # PF1 / E35d: a Fill continues, it adds nothing
TRUTH = {
    "room_s": {"set": {"kind": "room", "sizes": {"width": 3.5, "depth": 4.5, "height": 2.6}}, "cam": {"pos": [0.6, 1.5, 1.6], "target": [-0.2, 1.2, -2.0], "focal_mm": 24.0},
               "prompt": "a small bedroom with plastered walls and a wooden floor, soft daylight, photograph"},
    "room_m": {"set": {"kind": "room", "sizes": {"width": 5.0, "depth": 6.0, "height": 2.8}}, "cam": {"pos": [-0.8, 1.6, 2.4], "target": [0.5, 1.1, -3.0], "focal_mm": 24.0},
               "prompt": "a farmhouse kitchen with a tiled floor and painted walls, warm afternoon light, photograph"},
    "room_l": {"set": {"kind": "room", "sizes": {"width": 8.0, "depth": 10.0, "height": 3.5}}, "cam": {"pos": [1.5, 1.7, 4.2], "target": [-1.0, 1.3, -5.0], "focal_mm": 22.0},
               "prompt": "a large empty workshop hall, concrete floor, brick walls, light from high windows, photograph"},
    "corridor": {"set": {"kind": "corridor", "sizes": {"width": 2.2, "height": 2.7, "length": 14.0}}, "cam": {"pos": [0.3, 1.6, 6.0], "target": [0.0, 1.4, -7.0], "focal_mm": 24.0},
                 "prompt": "a long hotel corridor with carpet, patterned wallpaper and ceiling lamps, photograph"},
    "street": {"set": {"kind": "street", "sizes": {"width": 12.0, "length": 40.0, "pavement": 2.0, "height_l": 10.0, "height_r": 8.0}},
               "cam": {"pos": [1.5, 1.7, 12.0], "target": [0.0, 3.0, -20.0], "focal_mm": 24.0},
               "prompt": "a narrow old town street with stone façades and cobblestones, overcast, photograph"},
}
FOUND = {
    "kitchen": "a kitchen interior, wide shot at eye level, cabinets along the walls, daylight, photograph",
    "alley": "a narrow alley between brick buildings, eye level, overcast, photograph",
    "hall": "a long hall with columns along both sides, eye level, soft light, photograph",
    "field": "an open field with a wooden fence and distant hills, eye level, photograph",
}


def load() -> dict:
    p = OUT / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def save(s: dict) -> None:
    (OUT / "state.json").write_text(json.dumps(s, indent=1), encoding="utf-8")


def browser(mode: str, spec: list | dict, timeout: float = 7200) -> dict:
    sp = OUT / f"spec_{mode}.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    t0 = time.time()
    r = subprocess.run(["node", str(Path(__file__).with_name("e38_browser.cjs")), mode, str(sp), str(OUT / "browser")], cwd=str(ROOT / "frontend"),
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
    (OUT / f"browser_{mode}.log").write_text(r.stderr, encoding="utf-8")
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise RuntimeError(f"the browser half failed ({mode})")
    out = json.loads((OUT / "browser" / f"{mode}.json").read_text(encoding="utf-8"))
    out["_s"] = round(time.time() - t0, 1)
    return out


def app() -> P.App:
    P.OUT = OUT
    if not (OUT / "proj").is_dir():
        shutil.copytree(A1, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    return P.App(OUT / "proj")


def model_by_label(label: str) -> str:
    caps = P.api("GET", "/capabilities")
    return next(k for k, m in caps["models"].items() if m.get("label") == label)


def asset_path(aid: str) -> Path:
    return OUT / "proj" / P.api("GET", f"/assets/{aid}")["path"]


def make() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "browser").mkdir(exist_ok=True)
    s = load()
    a = app()
    try:
        pics = s.setdefault("pictures", {})
        stills = []
        for name, t in TRUTH.items():
            if name in pics:
                continue
            st = P.api("POST", "/stages", {"name": f"E38 {name}"})
            cam = {"id": "cam_e38", "name": "Camera", "pos": t["cam"]["pos"], "target": t["cam"]["target"], "roll": 0.0, "focal_mm": t["cam"]["focal_mm"], "sensor_mm": 36.0}
            obj = {"id": "set_e38", "kind": "set", "name": name, "preset": "built", "locked": True, "place_set": {**t["set"], "parts": {}, "faces": [], "sources": []}}
            st = P.api("PUT", f"/stages/{st['id']}", {**st, "objects": [obj], "cameras": [cam], "active_camera": cam["id"]})
            stills.append({"name": name, "stage_id": st["id"], "prompt": t["prompt"]})
        if stills:
            jobs = browser("stills", stills)
            for x in stills:
                j = P.wait_job(jobs[x["name"]], timeout=1800)
                if j["status"] != "done":
                    raise RuntimeError(f"{x['name']}: the still failed: {j.get('error')}")
                pics[x["name"]] = {"asset_id": j["result"]["asset_ids"][0], "truth": TRUTH[x["name"]], "still_s": j.get("wall_s")}
                save(s)
        klein = model_by_label("Klein 9B")
        for name, prompt in FOUND.items():
            if name in pics:
                continue
            j = P.api("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": klein, "prompt_mode": "text", "prompt_text": prompt, "seeds": [38], "width": 1280, "height": 720}})["jobs"][0]
            j = P.wait_job(j["id"], timeout=1800)
            if j["status"] != "done":
                raise RuntimeError(f"{name}: {j.get('error')}")
            pics[name] = {"asset_id": j["result"]["asset_ids"][0], "t2i_s": j.get("wall_s")}
            save(s)
        for name in TRUTH:                                              # the clay pass itself: the true geometry, exactly drawn (MoGe's error alone)
            if f"{name}_clay" in pics:
                continue
            st = next((x for x in P.api("GET", "/stages")["items"] if x["name"] == f"E38 {name}"), None)
            clay = next((ps["assets"].get("clay") for ps in (st or {}).get("passes", []) if ps.get("assets")), None)
            if clay:
                pics[f"{name}_clay"] = {"asset_id": clay, "truth": TRUTH[name]}
        if "a1_room" not in pics:
            fin = next((f for f in P.api("GET", "/finals")["items"] if any(l.get("still_asset_id") for l in f["layers"] if l["id"] == "plate")), None)
            if fin:
                pics["a1_room"] = {"asset_id": next(l["still_asset_id"] for l in fin["layers"] if l["id"] == "plate")}
        save(s)
        print(json.dumps({k: v["asset_id"] for k, v in pics.items()}, indent=1))
    finally:
        a.close()


def fit() -> None:
    from loom2.relief import glb_read, lens_of, mesh_arrays
    from loom2.set_fit import fit_set
    s = load()
    a = app()
    try:
        for name, p in s["pictures"].items():
            relief = (p.get("fit") or {}).get("relief")
            if "fit" in p and not REFIT:
                continue
            j = {"wall_s": (p.get("fit") or {}).get("moge_s"), "result": {"asset_ids": [relief]}}
            if not relief:                                           # MoGe once a picture; --refit reads the relief again
                j = P.api("POST", "/jobs", {"recipe": {"kind": "image_to_set", "asset_id": p["asset_id"]}})["jobs"][0]
                j = P.wait_job(j["id"], timeout=1800)
                if j["status"] != "done":
                    p["fit"] = {"error": j.get("error")}
                    continue
            glb = asset_path(j["result"]["asset_ids"][0])
            doc, binary = glb_read(glb)
            pos, uv, _ = mesh_arrays(doc, binary)
            lens = lens_of(pos, uv) or {}
            t1 = time.time()
            try:
                f = fit_set(pos, uv, lens.get("fov_x"), camera_height_m=EYE)          # E38: the scale from an eye-level camera (MoGe's runs short)
                raw = fit_set(pos, uv, lens.get("fov_x"))
                f["raw"] = {"kind": raw["kind"], "sizes": raw["sizes"], "height_m": raw["height_m"]}
            except ValueError as e:
                f = {"error": str(e)}
            f["moge_s"], f["fit_s"] = j.get("wall_s"), round(time.time() - t1, 2)
            f["relief"] = j["result"]["asset_ids"][0]
            f["lens_read"] = lens.get("fov_x")
            p["fit"] = f
            if "truth" in p and "error" not in f:
                p["compare"] = compare(p["truth"], f)
            save(s)
            print(name, json.dumps(p.get("compare") or {k: f.get(k) for k in ("kind", "sizes", "assumed", "error")}))
    finally:
        a.close()


def compare(t: dict, f: dict) -> dict:
    """The fit against the truth: the kind, the lens, the camera's height and tilt, the sizes (a room's width and depth taken either way round:
    the fit's back is the wall the camera faces most squarely), the camera's distance to the back."""
    tc = t["cam"]
    true_fov = math.degrees(2 * math.atan(18.0 / tc["focal_mm"]))
    dx, dy, dz = (np.asarray(tc["target"]) - np.asarray(tc["pos"])).tolist()
    true_pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    ts, fs = t["set"]["sizes"], f["sizes"]
    out = {"kind": [t["set"]["kind"], f["kind"]], "lens_deg": [round(true_fov, 1), f.get("lens_read")],
           "height_m": [tc["pos"][1], f["height_m"]], "pitch_deg": [round(true_pitch, 1), f["pitch_deg"]], "assumed": f["assumed"]}
    if t["set"]["kind"] in ("room", "corridor") and f["kind"] in ("room", "corridor"):
        tw, td = ts["width"], ts.get("depth", ts.get("length"))
        fw, fd = fs["width"], fs.get("depth", fs.get("length"))
        straight = abs(fw - tw) / tw + abs(fd - td) / td
        turned = abs(fw - td) / td + abs(fd - tw) / tw
        if turned < straight:
            fw, fd = fd, fw
        out["width_pct"] = round(100 * (fw - tw) / tw, 1)
        out["depth_pct"] = round(100 * (fd - td) / td, 1)
        out["height_pct"] = round(100 * (fs["height"] - ts["height"]) / ts["height"], 1)
        out["turned"] = bool(turned < straight)
        out["to_back"] = [round(tc["pos"][2] + td / 2, 2), round(f["camera"]["pos"][2] + fs.get("depth", fs.get("length")) / 2, 2)]
    elif t["set"]["kind"] == "street" and f["kind"] == "street":
        out["width_pct"] = round(100 * (fs["width"] - ts["width"]) / ts["width"], 1)
    raw = f.get("raw") or {}
    out["moge_scale_to_truth"] = round(tc["pos"][1] / raw["height_m"], 3) if raw.get("height_m") else None   # MoGe's own scale against the truth
    out["raw_kind"] = raw.get("kind")
    return out


def face_stats(name: str, faces: list[dict], texel: float) -> dict:
    """Per face: the share unseen (cosine below 0.05), coarse (the picture's pixel over 2 texels), the median picture pixel on the face."""
    d = OUT / "browser" / name
    out = {}
    for f in faces:
        cov = np.asarray(Image.open(d / f"{f['id']}.cov.png").convert("RGB"), dtype=np.float64) / 255.0
        red, green = cov[..., 0], cov[..., 1] * 8.0
        seen = red >= 0.05
        out[f["id"]] = {"unseen": round(float((~seen).mean()), 3), "coarse": round(float((seen & (green > 2.0)).mean()), 3),
                        "pixel_cm": round(float(np.median(green[seen]) * f["texel_m"] * 100), 2) if seen.any() else None, "px": f["px"]}
    return out


EDGES = {"room": [("wall_left", "end", "wall_back", "start"), ("wall_back", "end", "wall_right", "start"), ("floor", "top", "wall_back", "bottom")],
         "corridor": [("wall_left", "end", "wall_back", "start"), ("wall_back", "end", "wall_right", "start"), ("floor", "top", "wall_back", "bottom")],
         "street": [("road", "left", "pavement_left", "right"), ("pavement_left", "left", "facade_left", "start")]}


def seams(name: str, kind: str) -> dict:
    """The colour step across a corner where both faces were seen (mean |Δ| in levels of 255 along the shared edge, 3 texels in)."""
    d = OUT / "browser" / name
    out = {}
    for a, ea, b, eb in EDGES.get(kind, []):
        pa, pb = d / f"{a}.png", d / f"{b}.png"
        if not (pa.is_file() and pb.is_file()):
            continue
        A, B = np.asarray(Image.open(pa).convert("RGBA"), dtype=np.float64), np.asarray(Image.open(pb).convert("RGBA"), dtype=np.float64)
        def strip(M: np.ndarray, e: str) -> np.ndarray:
            if e == "start":
                return M[:, 2]
            if e == "end":
                return M[:, -3]
            if e == "top":
                return M[2, :]
            if e == "bottom":
                return M[-3, :]
            if e == "left":
                return M[:, 2]
            return M[:, -3]
        sa, sb = strip(A, ea), strip(B, eb)
        n = min(len(sa), len(sb))
        sa = np.asarray(Image.fromarray(sa.astype(np.uint8)[None, ...]).resize((n, 1))).reshape(n, 4).astype(np.float64)
        sb = np.asarray(Image.fromarray(sb.astype(np.uint8)[None, ...]).resize((n, 1))).reshape(n, 4).astype(np.float64)
        both = (sa[:, 3] > 0) & (sb[:, 3] > 0)
        if both.sum() > 10:
            out[f"{a}|{b}"] = round(float(np.abs(sa[both, :3] - sb[both, :3]).mean()), 1)
    return out


def placeset(f: dict) -> dict:
    return {"kind": f["kind"], "sizes": f["sizes"], "parts": {}}


def skin() -> None:
    s = load()
    a = app()
    try:
        spec = [{"name": n, "asset_id": p["asset_id"], "set": placeset(p["fit"]), "cam": p["fit"]["camera"], "texel": 0.01}
                for n, p in s["pictures"].items() if "error" not in p.get("fit", {"error": 1})]
        r = browser("bake", spec)
        for x in spec:
            p = s["pictures"][x["name"]]
            p["skin"] = {"faces": face_stats(x["name"], r[x["name"]], 0.01), "seams": seams(x["name"], p["fit"]["kind"]), "bake_s": r["_s"]}
        cams = []
        for x in spec:
            c = x["cam"]
            side = {**c, "pos": [c["pos"][0] + 1.2, c["pos"][1] + 0.4, c["pos"][2] + 0.6]}
            cams.append({"name": x["name"], "set": x["set"], "cams": [c, side],
                         "textures": {f["id"]: str(OUT / "browser" / x["name"] / f"{f['id']}.png") for f in r[x["name"]]}})
        browser("look", cams)
        save(s)
        for x in spec:
            sk = s["pictures"][x["name"]]["skin"]
            print(x["name"], {k: (v["unseen"], v["coarse"], v["pixel_cm"]) for k, v in sk["faces"].items()}, sk["seams"])
    finally:
        a.close()


def asset_url(aid: str) -> str:
    return f"http://127.0.0.1:8792/assets/{aid}/file?token=e28"


def raw_put(path: str, data: bytes) -> dict:
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{P.PORT}{path}", data=data, method="PUT", headers={"X-Loom-Token": P.TOKEN, "Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def subject(p: dict) -> list[float]:
    """What the picture looks at: along its camera's view, at the median depth of the picture's middle (its relief)."""
    from loom2.relief import glb_read, mesh_arrays
    doc, binary = glb_read(asset_path(p["fit"]["relief"]))
    pos, uv, _ = mesh_arrays(doc, binary)
    mid = (np.abs(uv[:, 0] - 0.5) < 0.1) & (np.abs(uv[:, 1] - 0.5) < 0.1) & np.isfinite(pos).all(axis=1)
    depth = float(np.median(-pos[mid, 2])) if mid.any() else 4.0
    c = p["fit"]["camera"]
    f = np.asarray(c["target"]) - np.asarray(c["pos"])
    f /= np.linalg.norm(f)
    return (np.asarray(c["pos"]) + f * depth).tolist()


def orbit_cam(c: dict, centre: list[float], deg: float) -> dict:
    t = math.radians(deg)
    R = np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])
    o = np.asarray(centre)
    pos = R @ (np.asarray(c["pos"]) - o) + o
    return {**c, "pos": [round(float(v), 4) for v in pos], "target": [round(float(v), 4) for v in centre]}


def coverage_arrays(name: str, face: str) -> tuple[np.ndarray, np.ndarray]:
    cov = np.asarray(Image.open(OUT / "browser" / name / f"{face}.cov.png").convert("RGB"), dtype=np.float64) / 255.0
    tex = np.asarray(Image.open(OUT / "browser" / name / f"{face}.png").convert("RGBA"), dtype=np.float64)
    return cov, tex


def unseen_share(names: list[str], faces: list[str]) -> float:
    """Texel-weighted share no picture in `names` saw (cosine below 0.05 in all)."""
    total = bad = 0
    for f in faces:
        reds = [coverage_arrays(n, f)[0][..., 0] for n in names]
        m = np.maximum.reduce(reds)
        total += m.size
        bad += int((m < 0.05).sum())
    return round(bad / max(1, total), 4)


def second() -> None:
    s = load()
    a = app()
    try:
        for name in ("kitchen", "alley"):
            p = s["pictures"].get(name)
            if not p or "error" in p.get("fit", {"error": 1}) or "second" in p:
                continue
            j = P.api("POST", "/jobs", {"recipe": {"kind": "reangle", "asset_id": p["asset_id"], "move": "left45", "method": "auto", "seeds": [38]}})["jobs"][0]
            j = P.wait_job(j["id"], timeout=2400)
            if j["status"] != "done":
                p["second"] = {"error": j.get("error")}
                save(s)
                continue
            aid = j["result"]["asset_ids"][0]
            centre = subject(p)
            cands = {f"{name}__2{sign}": orbit_cam(p["fit"]["camera"], centre, sign * 45.0) for sign in (+1, -1)}
            browser("bake", [{"name": k, "asset_id": aid, "set": placeset(p["fit"]), "cam": c, "texel": 0.01} for k, c in cands.items()])
            faces = list(p["skin"]["faces"].keys())
            agree = {}
            for k in cands:                                          # the orbit's side: where the second bake agrees with the first on what both saw
                diffs = []
                for f in faces:
                    c1, t1 = coverage_arrays(name, f)
                    c2, t2 = coverage_arrays(k, f)
                    both = (c1[..., 0] > 0.2) & (c2[..., 0] > 0.2)
                    if both.sum() > 500:
                        diffs.append(float(np.abs(t1[both, :3] - t2[both, :3]).mean()))
                agree[k] = round(float(np.mean(diffs)), 1) if diffs else 999.0
            best = min(agree, key=agree.get)
            p["second"] = {"asset_id": aid, "reangle_s": j.get("wall_s"), "subject": centre, "camera": cands[best], "name": best, "agree": agree,
                           "unseen_one": unseen_share([name], faces), "unseen_two": unseen_share([name, best], faces)}
            save(s)
            print(name, json.dumps(p["second"]))
    finally:
        a.close()


def fill() -> None:
    s = load()
    a = app()
    try:
        for name in ("kitchen", "room_m"):
            p = s["pictures"].get(name)
            if not p or "skin" not in p or "fill" in p:
                continue
            d = OUT / "browser" / name
            outd = OUT / "browser" / f"{name}_filled"
            outd.mkdir(parents=True, exist_ok=True)
            order = sorted(p["skin"]["faces"].items(), key=lambda kv: kv[1]["unseen"] + kv[1]["coarse"])   # the most seen first (04 §4 step 4)
            runs = []
            for fid, st in order:
                cov, tex = coverage_arrays(name, fid)
                bad = (cov[..., 0] < 0.05) | (cov[..., 1] * 8.0 > 2.0)
                img = tex[..., :3].copy()
                img[tex[..., 3] < 1] = 128.0                         # unseen texels grey before the Fill paints them
                src = outd / f"{fid}_in.png"
                Image.fromarray(img.astype(np.uint8)).save(src)
                if bad.mean() < 0.002:
                    shutil.copyfile(src, outd / f"{fid}.png")
                    runs.append({"face": fid, "bad": round(float(bad.mean()), 3), "fill_s": 0})
                    continue
                t0 = time.time()
                imported = P.api("POST", "/assets/import", {"paths": [str(src)], "suite": "stage"})["items"][0]["id"]
                doc = P.api("POST", "/documents", {"from_asset": imported, "name": f"E38 {name} {fid}"})
                h, w = bad.shape
                raw_put(f"/documents/{doc['id']}/selection?w={w}&h={h}", (bad.astype(np.uint8) * 255).tobytes())
                sub = P.api("POST", f"/documents/{doc['id']}/ai", {"recipe": {"kind": "inpaint", "mode": "fill", "prompt_text": NEUTRAL, "seeds": [38], "expand": 6, "feather": 8}, "stage": False})
                j = P.wait_job(sub["jobs"][0]["id"], timeout=2400)
                if j["status"] != "done":
                    runs.append({"face": fid, "bad": round(float(bad.mean()), 3), "error": j.get("error")})
                    continue
                flat = P.api("POST", f"/documents/{doc['id']}/flatten", {"to_catalogue": True, "name": f"E38 {name} {fid}"})
                P.api("POST", f"/documents/{doc['id']}/close")
                shutil.copyfile(asset_path(flat["asset"]["id"]), outd / f"{fid}.png")
                runs.append({"face": fid, "bad": round(float(bad.mean()), 3), "px": [w, h], "fill_s": j.get("wall_s"), "total_s": round(time.time() - t0, 1)})
                print(name, runs[-1])
            p["fill"] = runs
            save(s)
            c = p["fit"]["camera"]
            browser("look", [{"name": f"{name}_filled", "set": placeset(p["fit"]), "cams": [c, {**c, "pos": [c["pos"][0] + 1.2, c["pos"][1] + 0.4, c["pos"][2] + 0.6]},
                              orbit_cam(c, subject(p), 60.0)], "textures": {r["face"]: str(outd / f"{r['face']}.png") for r in runs if (outd / f"{r['face']}.png").is_file()}}])
    finally:
        a.close()


def inside(p: np.ndarray, f: dict) -> np.ndarray:
    """A camera kept inside its set: 0.25 m in from the walls, 0.3 m under a ceiling (a street's or the ground's: 6 m up)."""
    sz, kind = f["sizes"], f["kind"]
    if kind in ("room", "corridor"):
        w, d, h = sz["width"], sz.get("depth", sz.get("length")), sz["height"]
        return np.array([np.clip(p[0], -w / 2 + 0.25, w / 2 - 0.25), np.clip(p[1], 0.3, h - 0.3), np.clip(p[2], -d / 2 + 0.25, d / 2 - 0.25)])
    if kind == "street":
        w, L = sz["width"], sz["length"]
        return np.array([np.clip(p[0], -w / 2 + 0.25, w / 2 - 0.25), np.clip(p[1], 0.3, 6.0), np.clip(p[2], -L / 2 + 0.25, L / 2 - 0.25)])
    return np.array([p[0], np.clip(p[1], 0.3, 6.0), p[2]])


MATERIAL = {("room_m", "wall_left"): "A plain plastered wall painted pale ochre, nothing on it, lit by the same warm afternoon light.",
            ("room_m", "ceiling"): "A plain white plastered ceiling with wooden beams, the same warm light.",
            ("kitchen", "wall_left"): "Light wooden kitchen cabinet doors in a row, plain, the same daylight."}


def fill2() -> None:
    """The Fill again on the faces the picture saw least, with the face's material named instead of the neutral prompt (D135: the prompt is
    the lever) — beside the neutral run's."""
    s = load()
    a = app()
    try:
        for (name, fid), prompt in MATERIAL.items():
            p = s["pictures"][name]
            if any(r.get("face") == fid for r in p.get("fill_material", [])):
                continue
            outd = OUT / "browser" / f"{name}_material"
            outd.mkdir(parents=True, exist_ok=True)
            cov, tex = coverage_arrays(name, fid)
            bad = (cov[..., 0] < 0.05) | (cov[..., 1] * 8.0 > 2.0)
            src = OUT / "browser" / f"{name}_filled" / f"{fid}_in.png"
            imported = P.api("POST", "/assets/import", {"paths": [str(src)], "suite": "stage"})["items"][0]["id"]
            doc = P.api("POST", "/documents", {"from_asset": imported, "name": f"E38 {name} {fid} material"})
            h, w = bad.shape
            raw_put(f"/documents/{doc['id']}/selection?w={w}&h={h}", (bad.astype(np.uint8) * 255).tobytes())
            sub = P.api("POST", f"/documents/{doc['id']}/ai", {"recipe": {"kind": "inpaint", "mode": "fill", "prompt_text": prompt, "seeds": [38], "expand": 6, "feather": 8}, "stage": False})
            j = P.wait_job(sub["jobs"][0]["id"], timeout=2400)
            flat = P.api("POST", f"/documents/{doc['id']}/flatten", {"to_catalogue": True, "name": f"E38 {name} {fid} material"})
            P.api("POST", f"/documents/{doc['id']}/close")
            shutil.copyfile(asset_path(flat["asset"]["id"]), outd / f"{fid}.png")
            p.setdefault("fill_material", []).append({"face": fid, "prompt": prompt, "fill_s": j.get("wall_s")})
            save(s)
            print(name, fid, j.get("wall_s"))
        for name in ("room_m", "kitchen"):
            p = s["pictures"][name]
            fd, md = OUT / "browser" / f"{name}_filled", OUT / "browser" / f"{name}_material"
            tex = {r["face"]: str((md / f"{r['face']}.png") if (md / f"{r['face']}.png").is_file() else (fd / f"{r['face']}.png")) for r in p["fill"]}
            c = p["fit"]["camera"]
            browser("look", [{"name": f"{name}_material", "set": placeset(p["fit"]), "cams": [c, {**c, "pos": [c["pos"][0] + 1.2, c["pos"][1] + 0.4, c["pos"][2] + 0.6]}, orbit_cam(c, subject(p), 60.0)],
                              "textures": tex}])
    finally:
        a.close()


def moves(c: dict, centre: list[float], n: int = 31, f: dict | None = None) -> dict[str, list[dict]]:
    """E34's orbit (50° about what the camera looks at, closing in a quarter) and E35d's crane (up 1.35 m and 1.3 m in, tilting down),
    each camera kept inside the set."""
    orb, crane = [], []
    pos, tgt = np.asarray(c["pos"]), np.asarray(c["target"])
    fwd = tgt - pos
    fh = np.array([fwd[0], 0.0, fwd[2]]) / max(1e-9, math.hypot(fwd[0], fwd[2]))
    for i in range(n):
        t = i / (n - 1)
        o = orbit_cam(c, centre, 50.0 * t)
        cen = np.asarray(centre)
        op = cen + (np.asarray(o["pos"]) - cen) * (1 - 0.25 * t)
        if f:
            op = inside(op, f)
        orb.append({**c, "pos": op.round(4).tolist(), "target": [round(float(v), 4) for v in centre]})
        cp = pos + np.array([0.0, 1.35 * t, 0.0]) + fh * 1.3 * t
        if f:
            cp = inside(cp, f)
        ct = tgt + np.array([0.0, -0.9 * t, 0.0]) - np.array([fh[2], 0.0, -fh[0]]) * 0.4 * t
        crane.append({**c, "pos": cp.round(4).tolist(), "target": ct.round(4).tolist()})
    return {"orbit": orb, "crane": crane}


def composite(names: list[str], faces: list[str], into: str) -> dict[str, str]:
    """The coverage of several pictures as one: per texel the most head-on (E35d's rule)."""
    d = OUT / "browser" / into
    d.mkdir(parents=True, exist_ok=True)
    out = {}
    for f in faces:
        covs = [coverage_arrays(n, f)[0] for n in names]
        red = np.stack([c[..., 0] for c in covs])
        k = red.argmax(axis=0)
        best = np.take_along_axis(np.stack(covs), k[None, ..., None].repeat(3, -1), 0)[0]
        Image.fromarray((best * 255).astype(np.uint8)).save(d / f"{f}.cov.png")
        out[f] = str(d / f"{f}.cov.png")
    return out


def move() -> None:
    s = load()
    a = app()
    try:
        spec = []
        for name, p in s["pictures"].items():
            if "skin" not in p:
                continue
            ms = moves(p["fit"]["camera"], subject(p), f=p["fit"])
            faces = list(p["skin"]["faces"].keys())
            one = {f: str(OUT / "browser" / name / f"{f}.cov.png") for f in faces}
            for mv, frames in ms.items():
                spec.append({"name": f"{name}__{mv}", "set": placeset(p["fit"]), "coverage": one, "frames": frames})
                if "second" in p and "name" in p["second"]:
                    two = composite([name, p["second"]["name"]], faces, f"{name}__two")
                    spec.append({"name": f"{name}__{mv}__two", "set": placeset(p["fit"]), "coverage": two, "frames": frames})
        r = browser("move", spec)
        for x in spec:
            base, mv = x["name"].split("__")[0], x["name"].split("__", 1)[1]
            u = r[x["name"]]
            s["pictures"][base].setdefault("move", {})[mv] = {"unseen_mean": round(float(np.mean(u["unseen"])), 3), "unseen_max": round(float(np.max(u["unseen"])), 3),
                                                              "coarse_mean": round(float(np.mean(u["coarse"])), 3), "unseen_end": u["unseen"][-1]}
        save(s)
        for n, p in s["pictures"].items():
            if "move" in p:
                print(n, json.dumps(p["move"]))
    finally:
        a.close()


def sheet(rows: list[tuple[str, list[Path]]], path: Path, heads: list[str], tw: int = 320, th: int = 180) -> None:
    cols = max(len(r[1]) for r in rows)
    top = 22
    im = Image.new("RGB", (150 + cols * (tw + 6), top + len(rows) * (th + 6) + 6), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for k, h in enumerate(heads):
        d.text((150 + k * (tw + 6) + 4, 5), h, fill=(225, 225, 225))
    for i, (label, paths) in enumerate(rows):
        d.text((6, top + 6 + i * (th + 6) + th // 2), label, fill=(225, 225, 225))
        for k, q in enumerate(paths):
            if q and Path(q).is_file():
                t = Image.open(q).convert("RGB")
                t.thumbnail((tw, th))
                im.paste(t, (150 + k * (tw + 6), top + 6 + i * (th + 6)))
    im.save(path, quality=86)


def local_path(aid: str) -> Path | None:
    """An asset's file read from the project's catalogue (no app running)."""
    import sqlite3
    row = sqlite3.connect(str(OUT / "proj" / "catalogue.sqlite")).execute("select path from assets where id=?", (aid,)).fetchone()
    return OUT / "proj" / row[0] if row else None


def score() -> None:
    s = load()
    rows = []
    for name, p in s["pictures"].items():
        f = p.get("fit", {})
        line = f"{name:9s} "
        if "error" in f:
            line += f"fit: {f['error']}"
        else:
            line += f"{f.get('kind'):8s} {json.dumps(f.get('sizes'))} assumed {f.get('assumed')} h {f.get('height_m')} pitch {f.get('pitch_deg')} lens {f.get('lens_read')}"
        if "compare" in p:
            c = p["compare"]
            line += f"\n          truth: kind {c['kind']} lens {c['lens_deg']} height {c['height_m']} pitch {c['pitch_deg']} width {c.get('width_pct')} % depth {c.get('depth_pct')} % height {c.get('height_pct')} % to back {c.get('to_back')}"
        if "skin" in p:
            fs = p["skin"]["faces"]
            line += f"\n          skin: unseen {round(float(np.mean([v['unseen'] for v in fs.values()])), 3)} coarse {round(float(np.mean([v['coarse'] for v in fs.values()])), 3)} picture pixel (cm) {[v['pixel_cm'] for v in fs.values()]} seams {p['skin']['seams']}"
        if "second" in p:
            line += f"\n          second: {p['second'].get('unseen_one')} → {p['second'].get('unseen_two')} (agree {p['second'].get('agree')})"
        if "fill" in p:
            line += f"\n          fill: {[(r['face'], r['bad'], r.get('fill_s')) for r in p['fill']]}"
        if "move" in p:
            line += f"\n          move: {json.dumps(p['move'])}"
        print(line)
        b = OUT / "browser"
        pic = local_path(p["asset_id"])
        rows.append((name, [pic, b / name / "look_0.png", b / name / "look_1.png", b / f"{name}__orbit" / "move_030.png", b / f"{name}__crane" / "move_030.png"]))
    heads = ["the picture", "baked, from its camera", "baked, from beside", "50° orbit's end: coverage", "crane's end: coverage (black unseen)"]
    sheet(rows[:5], IMG / "e38-truth.jpg", heads)
    sheet(rows[5:], IMG / "e38-found.jpg", heads)
    B = OUT / "browser"
    fills = [(n, [B / n / "look_1.png", B / f"{n}_filled" / "look_1.png", B / f"{n}_material" / "look_1.png", B / f"{n}_material" / "look_2.png"]) for n in ("room_m", "kitchen")]
    sheet(fills, IMG / "e38-fill.jpg", ["baked, from beside", "filled: the neutral prompt", "filled: the face's material", "the material, 60° round"])
    (OUT / "results.json").write_text(json.dumps(s["pictures"], indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["make", "fit", "skin", "second", "fill", "fill2", "move", "score"])
    ap.add_argument("--refit", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    {"make": make, "fit": fit, "skin": skin, "second": second, "fill": fill, "fill2": fill2, "move": move, "score": score}[a.step]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
