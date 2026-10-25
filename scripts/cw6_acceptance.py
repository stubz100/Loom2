"""CW6 (proto01_UIcast 04 §3–6, D143, D137 stage 6): a place's set built from its picture, on the rig — the real engine on a fresh copy of
E38's project:

1. three places in Cast: a farmhouse kitchen whose set picture is drawn by *Make the set picture ▶* (Klein, the place's sheet and the
   empty-place sentence), E38's alley picture, and the clay pass of E38's medium room (Stage's exact render: the truth 5 × 6 × 2.8 m);
2. *Build the set ▶* on each — MoGe-2, the fit scaled by the camera's height (1.6 m), the set on the version; the truth room's sizes
   against the truth (D143: ±10 % on exact geometry);
3. the bake in the app's own page — each place opened in Story › Cast, its set builder bakes the fitted set by itself (stage/setBake.ts),
   the faces uploaded;
4. *Fill ▶* on each — Klein's Fill face after face, the most seen first, each with its material named (the kitchen's walls and floor
   named by hand, the others the faces' nouns), one GPU job at a time (the browser closed);
5. the bench (D142) of each place and looks at the filled set as the engine draws it: from the picture's camera, from a 35° orbit and
   from above the floor, with the bake alone beside it.

    orchestrator/.venv/Scripts/python.exe scripts/cw6_acceptance.py          (Vite on 1420 for the browser half)
    … scripts/cw6_acceptance.py --reuse                                     (the last run's project: the looks and the sheet again)

Results: engine/spikes/out/cw6/results.json; the sheet: .docs/proto01_UIcast/img/cw6-sets.jpg.
"""
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
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from e38_sets import TRUTH, inside, orbit_cam  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "e38" / "proj"
OUT = ROOT / "engine" / "spikes" / "out" / "cw6"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
PLACES = {
    "kitchen": {"name": "Farm kitchen", "appearance": "a farmhouse kitchen with whitewashed walls, a terracotta tile floor and a wooden-beamed ceiling, soft daylight",
                "materials": {"wall_left": "whitewashed plaster, a little uneven", "wall_right": "whitewashed plaster, a little uneven", "wall_back": "whitewashed plaster, a little uneven",
                              "floor": "worn terracotta tiles", "ceiling": "white plaster between dark wooden beams"}},
    "alley": {"name": "Old alley", "appearance": "a narrow old alley between brick buildings, overcast", "picture": "alley"},
    "room": {"name": "Clay room (truth)", "appearance": "a plain grey room", "picture": "room_m_clay", "truth": True},
}
E38_TRUTH = {"room": TRUTH["room_m"]}


def browser(*args: str) -> dict:
    r = subprocess.run(["node", str(ROOT / "scripts" / "cw6_browser.cjs"), *args], cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                       timeout=3600, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
    (OUT / f"browser_{args[0]}.log").write_text(r.stderr, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(f"the browser half failed: {r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def version(pid: str) -> dict:
    p = P.api("GET", f"/story/profiles/{pid}")
    return next(v for v in p["versions"] if v["id"] == p["current"])


def wait_faces(pid: str, timeout: float = 2400) -> list[dict]:
    """The set's Fill chain to its end: no face filling, none queued (each landing queues the next)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        ps = version(pid)["place_set"]
        jobs = [j for j in P.api("GET", "/jobs")["items"] if (j.get("origin") or {}).get("surface") == "set_fill" and (j.get("origin") or {}).get("ref") == pid]
        if not any(f["fill_job_id"] for f in ps["faces"]) and jobs and all(j["status"] in ("done", "failed", "cancelled") for j in jobs):
            return jobs
        time.sleep(3)
    raise TimeoutError(f"{pid}: the Fill did not end")


def truth_pct(ps: dict, key: str) -> dict:
    """The fit against E38's truth as E38 measured it: the width, the height and the back wall's distance from the camera (the depth behind
    the camera is assumed, a third of what is ahead — 04 §3)."""
    t = E38_TRUTH[key]
    ts, fs = t["set"]["sizes"], ps["sizes"]
    cz = ps["sources"][0]["camera"]["pos"][2]
    back = cz + fs.get("depth", fs.get("length", 0.0)) / 2
    t_back = t["cam"]["pos"][2] + ts["depth"] / 2
    return {"width": round(100 * (fs["width"] - ts["width"]) / ts["width"], 1), "height": round(100 * (fs["height"] - ts["height"]) / ts["height"], 1),
            "back_wall": round(100 * (back - t_back) / t_back, 1)}


def cams(ps: dict) -> list[dict]:
    """From the picture's camera; a 35° orbit about a point 3 m ahead; up near the ceiling looking down at the floor ahead — kept inside."""
    c = ps["sources"][0]["camera"]
    pos, tgt = np.asarray(c["pos"]), np.asarray(c["target"])
    fwd = (tgt - pos) / (np.linalg.norm(tgt - pos) or 1.0)
    flat = np.array([fwd[0], 0.0, fwd[2]]) / (math.hypot(fwd[0], fwd[2]) or 1.0)
    centre = (pos + flat * 3.0) * np.array([1, 0, 1]) + np.array([0, 1.2, 0])
    f = {"kind": ps["kind"], "sizes": ps["sizes"]}
    orb = orbit_cam(c, centre.tolist(), 35.0)
    orb["pos"] = [round(float(v), 4) for v in inside(np.asarray(orb["pos"]), f)]
    up = {**c, "pos": [round(float(v), 4) for v in inside(pos + np.array([0, 0.9, 0]) - flat * 0.5, f)], "target": [round(float(v), 4) for v in (pos + flat * 2.5) * np.array([1, 0, 1])]}
    return [c, orb, up]


REFILL = {"kitchen": ["floor"], "alley": ["wall_left", "wall_right"]}   # the first rig: a window and pots on the floor; plain beige for brick


def run(reuse: bool, refill: bool = False) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    proj = OUT / "proj"
    state = OUT / "state.json"
    s = json.loads(state.read_text(encoding="utf-8")) if reuse and state.is_file() else {}
    if not reuse:
        shutil.rmtree(proj, ignore_errors=True)
        shutil.copytree(SRC, proj, ignore=shutil.ignore_patterns("_temp"))
    e38 = json.loads((ROOT / "engine" / "spikes" / "out" / "e38" / "state.json").read_text(encoding="utf-8"))["pictures"]
    P.OUT = OUT
    app = P.App(proj)
    res: dict = s.setdefault("results", {})
    try:
        if "places" not in s:
            # 1. the places and their set pictures
            for key, d in PLACES.items():
                p = P.api("POST", "/story/profiles", {"name": d["name"], "cls": "place", "appearance": d["appearance"]})
                s.setdefault("places", {})[key] = p["id"]
                if "picture" in d:
                    P.api("PUT", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "asset_id": e38[d["picture"]]["asset_id"]})
                else:
                    t0 = time.time()
                    r = P.api("POST", f"/story/profiles/{p['id']}/versions/v1/anim-ref", {"side": "front", "count": 1})
                    j = P.wait_job(r["job_ids"][0], timeout=1800)
                    res[key] = {"set_picture_s": round(time.time() - t0, 1), "set_picture_job": j["status"]}
                    if j["status"] != "done":
                        raise RuntimeError(f"{key}: the set picture failed: {j.get('error')}")
                    prompt = j["recipe"]["prompt_text"]
                    res[key]["set_picture_prompt"] = prompt
                aid = version(p["id"])["anim_ref_asset_id"]
                res.setdefault(key, {}).update({"set_picture": aid, "set_picture_path": str(proj / P.api("GET", f"/assets/{aid}")["path"])})
            state.write_text(json.dumps(s, indent=1), encoding="utf-8")
        if True:                                                               # each step below runs where the last run stopped (--reuse)
            # 2. Build the set ▶ (MoGe-2, the fit at 1.6 m)
            for key, pid in s["places"].items():
                if res[key].get("fit_s"):
                    ps = version(pid)["place_set"]
                    if PLACES[key].get("truth") and ps:
                        res[key]["truth_pct"] = truth_pct(ps, key)
                    continue
                t0 = time.time()
                j = P.api("POST", f"/story/profiles/{pid}/versions/v1/set/fit", {"camera_height_m": 1.6})
                job = P.wait_job(j["job_id"], timeout=1800)
                ps = version(pid)["place_set"]
                res[key].update({"fit_s": round(time.time() - t0, 1), "fit_job": job["status"], "fit_error": (job.get("result") or {}).get("set_error"),
                                 "kind": ps and ps["kind"], "sizes": ps and ps["sizes"], "assumed": ps and ps["sources"][0]["assumed"]})
                truth = PLACES[key].get("truth")
                if truth and ps:
                    res[key]["truth_pct"] = truth_pct(ps, key)
                print(key, json.dumps({k: res[key].get(k) for k in ("kind", "sizes", "assumed", "fit_error", "truth_pct")}))
            state.write_text(json.dumps(s, indent=1), encoding="utf-8")
            # 3. the bake, in the app's own page (no GPU job runs meanwhile)
            todo = [pid for key, pid in s["places"].items() if not res[key].get("bake")]
            if todo:
                P.drain()
                baked = browser("bake", str(OUT / "shots"), *todo)
                for key, pid in s["places"].items():
                    if pid in todo:
                        ps = version(pid)["place_set"]
                        res[key]["bake"] = {**baked.get(pid, {}), "faces": {f["id"]: {"seen": f["seen"], "bad": f["bad"], "texel_m": f["texel_m"]} for f in ps["faces"]}}
                state.write_text(json.dumps(s, indent=1), encoding="utf-8")
            # 4. Fill ▶ — the materials named on the kitchen first
            for key, pid in s["places"].items():
                if res[key].get("fill"):
                    continue
                mats = PLACES[key].get("materials")
                if mats:
                    p = P.api("GET", f"/story/profiles/{pid}")
                    ps = version(pid)["place_set"]
                    ps["faces"] = [{**f, "material": mats.get(f["id"], f["material"])} for f in ps["faces"]]
                    P.api("PUT", f"/story/profiles/{pid}/versions/v1/set", {"revision": p["revision"], "place_set": ps})
                t0 = time.time()
                r = P.api("POST", f"/story/profiles/{pid}/versions/v1/set/fill", {})
                jobs = wait_faces(pid)
                ps = version(pid)["place_set"]
                res[key]["fill"] = {"order": r["faces"], "s": round(time.time() - t0, 1), "per_face_s": [j.get("wall_s") for j in sorted(jobs, key=lambda x: x["created_at"])],
                                    "failed": [j["origin"]["payload"]["face"] for j in jobs if j["status"] != "done"], "filled": [f["id"] for f in ps["faces"] if f["filled"]]}
                print(key, json.dumps(res[key]["fill"]))
                state.write_text(json.dumps(s, indent=1), encoding="utf-8")
        if refill:                                                             # the faces whose first Fill looked wrong, filled again with the prompt as it is now
            for key, faces in REFILL.items():
                pid = s["places"][key]
                before = {f["id"]: f["texture_asset_id"] for f in version(pid)["place_set"]["faces"]}
                t0 = time.time()
                r = P.api("POST", f"/story/profiles/{pid}/versions/v1/set/fill", {"faces": faces})
                jobs = [j for j in wait_faces(pid) if (j["origin"]["payload"] or {}).get("again")]
                after = {f["id"]: f for f in version(pid)["place_set"]["faces"]}
                res[key]["refill"] = {"faces": r["faces"], "s": round(time.time() - t0, 1), "prompts": {j["origin"]["payload"]["face"]: j["recipe"]["prompt_text"] for j in jobs},
                                      "new": [f for f in faces if after[f]["filled"] and after[f]["texture_asset_id"] != before.get(f)], "first": {f: before.get(f) for f in faces}}
                print(key, json.dumps({k: v for k, v in res[key]["refill"].items() if k != "prompts"}))
            state.write_text(json.dumps(s, indent=1), encoding="utf-8")
        # 5. the benches and the looks
        P.drain()
        spec = []
        for key, pid in s["places"].items():
            ps = version(pid)["place_set"]
            if not ps:
                continue
            bench = P.api("POST", "/stages/bench", {"profile_id": pid})["stage"]
            res[key]["bench"] = {"stage_id": bench["id"], "objects": [o["kind"] for o in bench["objects"]], "camera": bench["cameras"][0]["pos"] == ps["sources"][0]["camera"]["pos"]}
            cs = cams(ps)
            spec.append({"name": f"{key}_filled", "set": ps, "faces": {f["id"]: f["texture_asset_id"] for f in ps["faces"] if f["texture_asset_id"]}, "cams": cs})
            spec.append({"name": f"{key}_baked", "set": ps, "faces": {f["id"]: f["baked_asset_id"] for f in ps["faces"] if f["baked_asset_id"]}, "cams": cs[1:2]})
        (OUT / "look.json").write_text(json.dumps(spec), encoding="utf-8")
        browser("look", str(OUT / "shots"), str(OUT / "look.json"))
        kitchen = res.get("kitchen", {}).get("bench", {}).get("stage_id")
        if kitchen:
            browser("bench", str(OUT / "shots"), kitchen, "kitchen")
        state.write_text(json.dumps(s, indent=1), encoding="utf-8")
    finally:
        app.close()
    return s


def checks(s: dict) -> list[tuple[str, bool, str]]:
    r = s["results"]
    out = []
    k = r.get("kitchen", {})
    out.append(("the set picture drawn from the place's sheet", k.get("set_picture_job") == "done" and bool(k.get("set_picture")) and "empty" in (k.get("set_picture_prompt") or ""),
                f"{k.get('set_picture_s')} s"))
    for key in PLACES:
        x = r.get(key, {})
        out.append((f"{key}: fitted", bool(x.get("kind")), f"{x.get('kind')} {x.get('sizes')} assumed {x.get('assumed')} · {x.get('fit_s')} s" + (f" · {x['fit_error']}" if x.get("fit_error") else "")))
    t = r.get("room", {}).get("truth_pct") or {}
    out.append(("the clay room within ±12 % of the truth (D143: ±10 %)", r.get("room", {}).get("kind") == "room" and all(abs(v) <= 12 for v in t.values()) and bool(t), json.dumps(t)))
    for key in PLACES:
        b = r.get(key, {}).get("bake") or {}
        out.append((f"{key}: baked in the page", b.get("faces") and len(b["faces"]) >= 4 and b.get("seconds") is not None, f"{len(b.get('faces') or {})} faces in {b.get('seconds')} s"))
    for key in PLACES:
        f = r.get(key, {}).get("fill") or {}
        out.append((f"{key}: every face to fill filled", bool(f) and not f.get("failed") and set(f.get("order") or []) <= set(f.get("filled") or []),
                    f"{len(f.get('filled') or [])} faces in {f.get('s')} s ({f.get('per_face_s')})"))
    for key in PLACES:
        b = r.get(key, {}).get("bench") or {}
        out.append((f"{key}: the bench is the set from the picture's camera", b.get("objects", [None])[0] == "set" and b.get("camera") is True, json.dumps(b.get("objects"))))
    return out


def sheet(s: dict) -> Path:
    sh = OUT / "shots"
    rows = []
    for key, pid in s["places"].items():
        pic = s["results"][key].get("set_picture_path")
        rows.append((PLACES[key]["name"], [pic, sh / f"{pid}_cast.png", sh / f"{key}_filled_look_0.png", sh / f"{key}_baked_look_0.png", sh / f"{key}_filled_look_1.png", sh / f"{key}_filled_look_2.png"]))
    heads = ["the set picture", "Cast: the set over it", "filled, from its camera", "baked only, 35° round", "filled, 35° round", "filled, from above"]
    tw, th, top = 300, 169, 22
    im = Image.new("RGB", (130 + len(heads) * (tw + 6), top + len(rows) * (th + 6) + 6), (24, 24, 24))
    d = ImageDraw.Draw(im)
    for k, h in enumerate(heads):
        d.text((130 + k * (tw + 6) + 4, 5), h, fill=(225, 225, 225))
    for i, (label, paths) in enumerate(rows):
        d.text((6, top + 6 + i * (th + 6) + th // 2), label, fill=(225, 225, 225))
        for k, q in enumerate(paths):
            if q and Path(q).is_file():
                t = Image.open(q).convert("RGB")
                t.thumbnail((tw, th))
                im.paste(t, (130 + k * (tw + 6), top + 6 + i * (th + 6)))
    out = IMG / "cw6-sets.jpg"
    im.save(out, quality=86)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--refill", action="store_true", help="with --reuse: the kitchen's floor and the alley's walls filled again (the prompt's rule since the first run)")
    a = ap.parse_args()
    s = run(a.reuse, a.refill)
    res = checks(s)
    for name, ok, note in res:
        print(("PASS" if ok else "FAIL"), name, "·", note)
    print(f"{sum(ok for _, ok, _ in res)}/{len(res)}")
    s["checks"] = [{"name": n, "ok": ok, "note": note} for n, ok, note in res]
    (OUT / "results.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    print(sheet(s))
    return 0 if all(ok for _, ok, _ in res) else 1


if __name__ == "__main__":
    raise SystemExit(main())
