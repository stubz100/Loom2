"""CS3 (proto01_UIcast 06 §2.5 and §2.10, D136 U6/U8/U19, D137 stage 2): the shell in the shots and the skeleton over time, on the rig —
the real engine on a fresh copy of E36's project (A1 after CS1's rig, Mara's and Ines' versions with their shells):

1. the shell in the passes: Stage makes a new final from A1's stage (the Final shot card's own path) — Mara's figure is her shell now
   (CS2: the version's shell is the figure's; CS3: its clay, the guide's face and feet landmarks on it, the hand rig's hands). Her depth
   pass's silhouette against the SAM 3 matte of what Wan Animate drew (CS1's performance): the shell's against the Detailed mannequin's;
2. Wan Animate again on Mara's layer, the same seed: SDPose on Wan's frames as CS1's rig read them (the hand's reach, nose → neck), the
   guide's nose against Wan's figure's, and the new silhouette against its own matte;
3. *the skeleton changed*: Mara's neck changed in Cast, then *Apply from a frame…* at a frame in the second batch — skeleton keys hold the
   frames before it, the guide is drawn again, only the second batch is performed again (the first's job and clip kept).

    orchestrator/.venv/Scripts/python.exe scripts/cs3_acceptance.py          (Vite on 1420 for the browser half)
    … scripts/cs3_acceptance.py --silhouettes                               (the silhouette check again on the last run's project)
    … scripts/cs3_acceptance.py --apose                                     (D139 on the last run's project: Mara drawn again in the A-pose,
                                                                             her shell made again — the arms apart from the body)
    … scripts/cs3_acceptance.py --fingers                                   (D140 on the last run's project: the fit refused arms-down, two
                                                                             references drawn with spread fingers and fitted)

Results: engine/spikes/out/cs3/results.json; the sheets: .docs/proto01_UIcast/img/cs3-*.jpg.
"""
from __future__ import annotations

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
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "orchestrator"), str(ROOT / "scripts"), str(ROOT / "engine" / "spikes")]
import e28_props as P  # noqa: E402
from cs1_acceptance import measures, people_of  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

SRC = ROOT / "engine" / "spikes" / "out" / "e36" / "proj"
OUT = ROOT / "engine" / "spikes" / "out" / "cs3"
IMG = ROOT / ".docs" / "proto01_UIcast" / "img"
FRAMES = list(range(0, 81, 10))
APPLY_AT = 118                                          # a Stage frame in the second batch (F16: the 80th of 81 frames)


def browser(*args: str) -> dict:
    r = subprocess.run(["node", str(ROOT / "scripts" / "cs3_browser.cjs"), *args], cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8",
                       timeout=1800, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
    if r.returncode != 0:
        raise RuntimeError(f"the browser half failed: {r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def layer_dir(fid: str, lid: str) -> Path:
    return OUT / "proj" / "finals" / fid / lid


def iou(a: np.ndarray, b: np.ndarray) -> float:
    return float((a & b).sum() / max(1, (a | b).sum()))


def silhouettes(fid: str, lid: str, matte_of: str) -> float:
    """The figure's silhouette as Stage drew it — where its layer's depth (the figure with the set) differs from the plate's (the bare set)
    — against the SAM 3 matte of Wan's figure in `matte_of`'s performance: the median IoU."""
    out = []
    for i in FRAMES:
        d = np.asarray(Image.open(layer_dir(fid, lid) / "depth" / f"{i:04d}.png").convert("L")).astype(int)
        bare = np.asarray(Image.open(layer_dir(fid, "plate") / "depth" / f"{i:04d}.png").convert("L")).astype(int)
        fig = np.abs(d - bare) > 6
        m = np.asarray(Image.open(layer_dir(matte_of, lid) / "matte" / f"{i:04d}.png").convert("L").resize(fig.shape[::-1])) > 127
        out.append(iou(fig, m))
    return float(np.median(out))


def silhouettes_again() -> int:
    """The silhouette check measured again on a finished run's project (the first run thresholded the depth alone: the set counted too)."""
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    finals = {json.loads(f.read_text(encoding="utf-8"))["name"]: f.parent.name for f in (OUT / "proj" / "finals").glob("fin_*/final.json")}
    old, new = finals["CS1 after"], finals["CS3 shell"]
    before, after, own = silhouettes(old, "fig_m", old), silhouettes(new, "fig_m", old), silhouettes(new, "fig_m", new)
    res["silhouette_vs_wan"] = {"detailed": round(before, 3), "shell": round(after, 3)}
    res["silhouette_vs_own_matte"] = round(own, 3)
    for c in res["checks"]:
        if c["name"] == "the depth silhouette nearer Wan's figure with the shell":
            c.update(ok=after > before, detail=f"IoU against CS1's SAM 3 matte: the Detailed mannequin {before:.3f} → the shell {after:.3f} (measured again: the figure apart from the set)")
            print(f"{'PASS' if c['ok'] else 'FAIL'} {c['name']} {c['detail']}")
    print(f"the shell against its own performance's matte: {own:.3f}")
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for c in res["checks"] if c["ok"])
    print(f"cs3_acceptance: {ok}/{len(res['checks'])}")
    return 0 if ok == len(res["checks"]) else 1


def wan_people(fid: str, lid: str, tag: str) -> list[dict | None]:
    keep = OUT / "frames" / tag
    keep.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in FRAMES:
        dst = keep / f"{lid}_{i:04d}.png"
        shutil.copy(layer_dir(fid, lid) / "frames" / f"{i:04d}.png", dst)
        paths.append(str(dst))
    recs = P.api("POST", "/assets/import", {"paths": paths})["items"]
    return [pp[0] if (pp := people_of(r["id"])) else None for r in recs]


def nose_gap(fid: str, lid: str, people: list[dict | None]) -> float:
    """The guide's nose against Wan's figure's (SDPose), over nose → ankles: the median of the frames read."""
    kp = json.loads((layer_dir(fid, lid) / "keypoints.json").read_text(encoding="utf-8"))["frames"]
    gaps = []
    for i, person in zip(FRAMES, people):
        g = np.array(kp[i], float)
        if person is None or g.shape[0] < 14:
            continue
        b = np.array(person.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
        if len(b) < 14 or b[0, 2] < 0.3:
            continue
        h = float(np.linalg.norm(g[0, :2] - (g[10, :2] + g[13, :2]) / 2))
        gaps.append(float(np.linalg.norm(g[0, :2] - b[0, :2])) / max(h, 1))
    return float(np.median(gaps)) if gaps else float("nan")


def med(rows: list[dict | None], k: str) -> float:
    v = [r[k] for r in (measures(p) if p else None for p in rows) if r and np.isfinite(r[k])]
    return float(np.median(v)) if v else float("nan")


def strip(path: Path, rows: list[tuple[str, list[Path]]]) -> None:
    tiles = [[Image.open(p).convert("RGB") for p in ps] for _, ps in rows]
    w, h = tiles[0][0].size
    s = 0.42
    tw, th = int(w * s), int(h * s)
    cols = max(len(r) for r in tiles)
    out = Image.new("RGB", (130 + cols * (tw + 8), len(rows) * (th + 8) + 8), (24, 24, 24))
    d = ImageDraw.Draw(out)
    for r, ((label, _), ts) in enumerate(zip(rows, tiles)):
        d.text((8, 8 + r * (th + 8) + 4), label, fill=(225, 225, 225))
        for c, t in enumerate(ts):
            out.paste(t.resize((tw, th)), (130 + c * (tw + 8), 8 + r * (th + 8)))
    out.save(path, quality=86)


def wait_layer(fid: str, lid: str, timeout: float = 3600) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        lay = next(x for x in P.api("GET", f"/finals/{fid}")["layers"] if x["id"] == lid)
        if lay["status"] in ("done", "failed"):
            break
        time.sleep(5)
    for jid in lay.get("job_ids") or []:
        P.wait_job(jid)
    return next(x for x in P.api("GET", f"/finals/{fid}")["layers"] if x["id"] == lid)


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    res: dict = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    P.OUT = OUT
    shutil.copytree(SRC, OUT / "proj", ignore=shutil.ignore_patterns("_temp"))
    app = P.App(OUT / "proj")
    try:
        old = next(f for f in P.api("GET", "/finals")["items"] if f["name"] == "CS1 after")
        mara = next(x for x in old["layers"] if x["id"] == "fig_m")
        prof = P.api("GET", f"/story/profiles/{mara['profile_id']}")
        shell = prof["versions"][0]["shell_asset_id"]
        # 1 · the shell in the passes
        t0 = time.time()
        new_id = browser("make", old["stage_id"], str(old["rate"]), str(old["size"]["w"]), str(old["size"]["h"]))["final_id"]
        res["make_s"] = round(time.time() - t0, 1)
        new = P.api("GET", f"/finals/{new_id}")
        lay = next(x for x in new["layers"] if x["id"] == "fig_m")
        st = P.api("GET", f"/stages/{old['stage_id']}")
        fig = next(o for o in st["objects"] if o["id"] == mara["object_id"])
        check("Mara's figure is her shell (the version's, CS2)", fig["shadow_proxy"] == shell, f"{fig['shadow_proxy']} · the version's {shell}")
        check("the layer stamps its body per frame (CS3)", len(lay["body_hashes"]) == new["frames"] and lay["body"] is not None, f"{len(lay['body_hashes'])} hashes, neck ×{(lay['body'] or {}).get('neck')}")
        before, after = silhouettes(old["id"], "fig_m", old["id"]), silhouettes(new_id, "fig_m", old["id"])
        res["silhouette_vs_wan"] = {"detailed": round(before, 3), "shell": round(after, 3)}
        check("the depth silhouette nearer Wan's figure with the shell", after > before, f"IoU against CS1's SAM 3 matte: the Detailed mannequin {before:.3f} → the shell {after:.3f}")
        kp_old = json.loads((layer_dir(old["id"], "fig_m") / "keypoints.json").read_text(encoding="utf-8"))["frames"]
        kp_new = json.loads((layer_dir(new_id, "fig_m") / "keypoints.json").read_text(encoding="utf-8"))["frames"]
        shift = float(np.median([np.linalg.norm(np.array(kp_new[i][0][:2]) - np.array(kp_old[i][0][:2])) for i in FRAMES]))
        res["nose_shift_px"] = round(shift, 1)
        check("the guide's nose moved onto the shell (a landmark, U8)", shift > 0.5, f"median {shift:.1f} px from the dummy's")
        strip(IMG / "cs3-1-mara-shell.jpg", [("the Detailed (CS1)", [layer_dir(old["id"], "fig_m") / "depth" / f"{i:04d}.png" for i in (10, 40, 70)]),
                                             ("the shell (CS3)", [layer_dir(new_id, "fig_m") / "depth" / f"{i:04d}.png" for i in (10, 40, 70)]),
                                             ("Wan's figure (CS1)", [layer_dir(old["id"], "fig_m") / "frames" / f"{i:04d}.png" for i in (10, 40, 70)]),
                                             ("the new guide", [layer_dir(new_id, "fig_m") / "pose" / f"{i:04d}.png" for i in (10, 40, 70)])])
        # 2 · Wan Animate again on the shell's guide, the same seed
        t1 = time.time()
        P.api("POST", f"/finals/{new_id}/layers/fig_m/run", {"seed": mara["seed"]})
        lay = wait_layer(new_id, "fig_m")
        res["perform_s"] = round(time.time() - t1, 1)
        check("Mara's layer performed on the shell's guide (the same seed)", lay["status"] == "done" and lay["frames_done"] == new["frames"], f"{lay['status']} · {res['perform_s']} s")
        ref = measures((people_of(prof["versions"][0]["anim_ref_asset_id"]) or [{}])[0]) or {}                 # the reference as SDPose reads it
        wan_old, wan_new = wan_people(old["id"], "fig_m", "cs1"), wan_people(new_id, "fig_m", "cs3")
        row = {k: {"reference": round(ref.get(k, float("nan")), 4), "cs1": round(med(wan_old, k), 4), "cs3": round(med(wan_new, k), 4)} for k in ("hand", "neck")}
        res["measures"] = row
        gaps = {"cs1": round(nose_gap(old["id"], "fig_m", wan_old), 4), "cs3": round(nose_gap(new_id, "fig_m", wan_new), 4)}
        res["nose_gap"] = gaps
        own = silhouettes(new_id, "fig_m", new_id)
        res["silhouette_vs_own_matte"] = round(own, 3)
        check("Wan's figure against the guide and the reference (reported)", True,
              f"reach {row['hand']['cs1']:.3f} → {row['hand']['cs3']:.3f} (ref {row['hand']['reference']:.3f}); nose → neck {row['neck']['cs1']:.3f} → {row['neck']['cs3']:.3f} (ref {row['neck']['reference']:.3f}); "
              f"the guide's nose to Wan's {gaps['cs1']:.3f} → {gaps['cs3']:.3f}; the shell's silhouette against its own matte {own:.3f}")
        # 3 · the skeleton changed: Mara's neck in Cast, applied from a frame in the second batch
        performed = lay
        prof = P.api("GET", f"/story/profiles/{prof['id']}")
        body = prof["versions"][0]["body"]
        P.api("PATCH", f"/story/profiles/{prof['id']}", {"revision": prof["revision"], "versions": [{"id": "v1", "body": {**body, "neck": round(body["neck"] * 0.8, 3)}}]})
        t2 = time.time()
        out = browser("apply", old["stage_id"], new_id, "fig_m", str(APPLY_AT))
        lay = wait_layer(new_id, "fig_m")
        res["apply_s"] = round(time.time() - t2, 1)
        keys = [(k["frame"], k["body"] is None) for k in out["keys"]]
        check("the keys hold the frames before it, Cast's from it", keys == [(old["range"]["start"], False), (APPLY_AT, True)], str(keys))
        same = [a == b for a, b in zip(performed["body_hashes"], lay["body_hashes"])]
        first = same.index(False) if False in same else -1
        res["first_changed_frame"] = first
        check("the guide changed only from the key on", first > 0 and all(same[:first]) and not any(same[first:]), f"frames 0–{first - 1} as drawn, {first}–{len(same) - 1} new")
        kept = performed["batches"][0]["job_id"] == lay["batches"][0]["job_id"] and performed["batches"][0]["clip_id"] == lay["batches"][0]["clip_id"]
        redone = performed["batches"][1]["job_id"] != lay["batches"][1]["job_id"]
        check("only the second batch performed again", kept and redone and lay["status"] == "done" and lay["frames_done"] == new["frames"],
              f"batch 1 kept: {kept}, batch 2 again: {redone} · {res['apply_s']} s")
        strip(IMG / "cs3-2-skeleton-key.jpg", [("before the key", [OUT / "frames" / "cs3" / f"fig_m_{i:04d}.png" for i in (60, 70, 80)]),
                                                ("after (batch 2 again)", [layer_dir(new_id, "fig_m") / "frames" / f"{i:04d}.png" for i in (60, 70, 80)])])
    finally:
        app.close()
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"cs3_acceptance: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


def runs_across(sil: Path) -> int:
    """How many pieces the shell's front silhouette has across the forearms (the rows at 48–58 % of its height, the median): an arm, the
    body, an arm (3) — or one blob, the arms fused to the body (1)."""
    a = np.asarray(Image.open(sil).convert("L")) > 127
    ys = np.nonzero(a.any(axis=1))[0]
    top, bottom = int(ys.min()), int(ys.max())
    counts = []
    for y in range(int(top + 0.42 * (bottom - top)), int(top + 0.52 * (bottom - top))):    # image rows run down: 48–58 % of the height up
        row = a[y].astype(int)
        counts.append(int(((row[1:] - row[:-1]) == 1).sum() + row[0]))
    return int(np.median(counts))


def apose() -> int:
    """D139 on the rig: Mara's shell refused on her arms-down reference; the reference drawn again in the A-pose (CS1's prompt), fitted, the
    shell made from it; both shells bound as E36 binds them — the arms apart from the body in the new one."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    P.OUT = OUT
    app = P.App(OUT / "proj")
    res: dict = {}
    try:
        old = next(f for f in P.api("GET", "/finals")["items"] if f["name"] == "CS1 after")
        pid = next(x for x in old["layers"] if x["id"] == "fig_m")["profile_id"]
        v0 = P.api("GET", f"/story/profiles/{pid}")["versions"][0]
        import urllib.error
        try:
            P.api("POST", f"/story/profiles/{pid}/versions/v1/shell")
            refused = ""
        except urllib.error.HTTPError as e:
            refused = f"{e.code} {e.read().decode('utf-8', 'replace')}"
        check("Mara's shell refused on her arms-down reference (D139)", "arms against the body" in refused, refused[-140:])
        t0 = time.time()
        made = []
        for jid in P.api("POST", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "count": 1})["job_ids"]:
            made += (P.wait_job(jid).get("result") or {}).get("asset_ids") or []
        if not made:
            raise RuntimeError("the A-pose reference was not drawn")
        P.api("PUT", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "asset_id": made[0]})   # a version with a reference: the candidate is the author's pick
        P.wait_job(P.api("POST", f"/story/profiles/{pid}/versions/v1/body/fit")["job_id"])
        v1 = P.api("GET", f"/story/profiles/{pid}")["versions"][0]
        res["reference_s"] = round(time.time() - t0, 1)
        check("the reference drawn again stands in the A-pose", v1["anim_ref_asset_id"] != v0["anim_ref_asset_id"] and v1["anim_ref_note"] is None,
              f"note {v1['anim_ref_note']} · {res['reference_s']} s")
        t1 = time.time()
        P.wait_job(P.api("POST", f"/story/profiles/{pid}/versions/v1/shell")["job_id"], timeout=1800)
        deadline = time.time() + 60
        while time.time() < deadline and P.api("GET", f"/story/profiles/{pid}")["versions"][0]["shell_asset_id"] in (None, v0["shell_asset_id"]):
            time.sleep(1)
        v2 = P.api("GET", f"/story/profiles/{pid}")["versions"][0]
        res["shell_s"] = round(time.time() - t1, 1)
        check("the shell made from it", v2["shell_asset_id"] not in (None, v0["shell_asset_id"]) and v2["shell_from"] == v2["anim_ref_asset_id"], f"{v2['shell_asset_id']} · {res['shell_s']} s")
        inputs = [{"name": "Mara_down", "body": v0["body"], "points": v0["body_points"], "mesh": v0["shell_asset_id"]},
                  {"name": "Mara_apose", "body": v2["body"], "points": v2["body_points"], "mesh": v2["shell_asset_id"]}]
        out = OUT / "apose"
        out.mkdir(exist_ok=True)
        r = subprocess.run(["node", str(ROOT / "engine" / "spikes" / "e36_browser.cjs"), json.dumps(inputs), str(out)], cwd=str(ROOT / "frontend"), capture_output=True,
                           text=True, encoding="utf-8", timeout=1800, env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
        if r.returncode != 0:
            raise RuntimeError(f"the browser half failed: {r.stderr[-1500:]}")
        rows = {x["name"]: x for x in json.loads((out / "results.json").read_text(encoding="utf-8"))}
        down, up = runs_across(out / "Mara_down_silhouette.png"), runs_across(out / "Mara_apose_silhouette.png")
        res["pieces_across_the_forearms"] = {"arms_down": down, "a_pose": up}
        res["joints_inside"] = {k: f"{sum(1 for j in rows[k]['joints'] if j['inside'])}/{len(rows[k]['joints'])}" for k in rows}
        check("the arms apart from the body in the new shell", down < 3 <= up, f"pieces across the forearms: arms down {down}, A-pose {up}; joints inside {res['joints_inside']}")
        ref = lambda a: OUT / "proj" / json.loads(next((OUT / "proj" / "assets").glob(f"*/{a}.json")).read_text(encoding="utf-8"))["path"]   # noqa: E731
        strip(IMG / "cs3-3-mara-apose-shell.jpg", [("arms down (A1)", [ref(v0["anim_ref_asset_id"]), out / "Mara_down_heat_bind.png", out / "Mara_down_heat_walk.png", out / "Mara_down_heat_sit.png"]),
                                                  ("the A-pose", [ref(v2["anim_ref_asset_id"]), out / "Mara_apose_heat_bind.png", out / "Mara_apose_heat_walk.png", out / "Mara_apose_heat_sit.png"])])
    finally:
        app.close()
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "apose.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"cs3_acceptance --apose: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


def fingers() -> int:
    """D140 on the rig: the fit refused on an arms-down reference (Ines'); Ines and Mara drawn again with the new prompt (the palms toward
    the camera, the wrists straight, the fingers spread) and fitted on the palm (the whole hand was measured and not kept: journal);
    *From the picture* reads the rest hand from Mara's hero (the dev page, Vite on 1420)."""
    import urllib.error
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)
    P.OUT = OUT
    app = P.App(OUT / "proj")
    res: dict = {}
    try:
        old = next(f for f in P.api("GET", "/finals")["items"] if f["name"] == "CS1 after")
        who = {x["name"]: x["profile_id"] for x in old["layers"] if x["kind"] == "figure"}
        ines, mara = who["Ines"], who["Mara"]
        try:
            if P.api("GET", f"/story/profiles/{ines}")["versions"][0]["anim_ref_note"] != "arms_close":
                raise LookupError
            P.api("POST", f"/story/profiles/{ines}/versions/v1/body/fit")
            refused = ""
        except LookupError:
            refused = ""
        except urllib.error.HTTPError as e:
            refused = f"{e.code} {e.read().decode('utf-8', 'replace')}"
        if P.api("GET", f"/story/profiles/{ines}")["versions"][0]["anim_ref_note"] == "arms_close" or refused:
            check("Ines' fit refused on her arms-down reference (D140)", "only on an A-pose" in refused, refused[-120:])
        else:
            print("(Ines' reference was drawn again in an earlier run: no arms-down picture to refuse)")
        for name, pid in (("Ines", ines), ("Mara", mara)):
            t0 = time.time()
            made = []
            for jid in P.api("POST", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "count": 1})["job_ids"]:
                made += (P.wait_job(jid).get("result") or {}).get("asset_ids") or []
            P.api("PUT", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "asset_id": made[0]})
            j = P.wait_job(P.api("POST", f"/story/profiles/{pid}/versions/v1/body/fit")["job_id"])
            v = P.api("GET", f"/story/profiles/{pid}")["versions"][0]
            fit = (j.get("result") or {}).get("fit") or {}
            person = ((j.get("result") or {}).get("people") or [{}])[0]
            palm = fit.get("palm", {}).get("reference")
            res[name] = {"seconds": round(time.time() - t0, 1), "note": v["anim_ref_note"], "hands": (v["body"] or {}).get("hands"), "measures": sorted(fit),
                         "hand": fit.get("hand"), "palm_read": palm, "people": len((j.get("result") or {}).get("people") or [])}
            check(f"{name} drawn again in the A-pose and fitted", j["status"] == "done" and v["anim_ref_note"] is None and "palm" in fit,
                  f"note {v['anim_ref_note']}; measures {sorted(fit)}; hands ×{(v['body'] or {}).get('hands')} · {res[name]['seconds']} s")
            res[name]["reference"] = made[0]
        hero = P.api("GET", f"/story/profiles/{mara}")
        hero_id = next((x.get("hero_asset_id") for x in hero["versions"] if x.get("hero_asset_id")), None)
        inputs = {"body": hero["versions"][0]["body"], "hero": hero_id}
        r = subprocess.run(["node", "-e", """
const { chromium } = require('playwright')
;(async () => {
  const [inp] = [JSON.parse(process.argv[1])]
  const browser = await chromium.launch({ channel: 'msedge', headless: false })
  const page = await browser.newPage()
  await page.goto('http://127.0.0.1:1420/?token=e28&port=8792')
  await page.waitForTimeout(2000)
  const out = await page.evaluate(async (x) => {
    const m = await import('/src/suites/stage/benchState.ts'), b = await import('/src/suites/stage/body.ts')
    const body = { ...b.DEFAULT_BODY, ...x.body, hand_rest: { ...b.DEFAULT_BODY.hand_rest, ...(x.body.hand_rest ?? {}) } }
    const pts = await m.readPicture(x.hero)
    return { hands: !!pts && (pts.hand_left?.length ?? 0) + (pts.hand_right?.length ?? 0), pick: await m.handFromPicture(body, pts) }
  }, inp)
  console.log(JSON.stringify(out)); await browser.close()
})().catch((e) => { console.error(e); process.exit(1) })""", json.dumps(inputs)], cwd=str(ROOT / "frontend"), capture_output=True, text=True, encoding="utf-8", timeout=600,
                           env={**os.environ, "NODE_PATH": str(ROOT / "frontend" / "node_modules")})
        pick = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {"error": r.stderr[-400:]}
        res["from_the_hero"] = pick
        check("From the picture reads Mara's hero (reported)", r.returncode == 0, json.dumps(pick)[:200])
    finally:
        app.close()
    res["checks"] = [{"name": a, "ok": b, "detail": c} for a, b, c in checks]
    (OUT / "fingers.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    ok = sum(1 for _, b, _ in checks if b)
    print(f"cs3_acceptance --fingers: {ok}/{len(checks)}")
    return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(silhouettes_again() if "--silhouettes" in sys.argv else apose() if "--apose" in sys.argv else fingers() if "--fingers" in sys.argv else main())
