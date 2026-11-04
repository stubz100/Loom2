"""E62 a (D187, proto01_rig 00 §5): can a hand picture be read?

Through the product path on the running orchestrator (one GPU job at a time, the queue's): a hand picture for each subject — a Cast character
of the open project by its @mention (its sheet and references ride along, D85/D93), or a humanoid by words alone — on the reference model
(Klein 9B, /capabilities.story) and on FLUX.2 dev (the t2i default). Each picture is read by SDPose twice: the product's keypoints job (RT-DETR
boxes the people first) and the same compiled graph without the boxes, sent to the engine directly (SDPose then reads the whole picture).
The hand is matted against its plain background (the border's colour, flood-filled from the edges), and measured: the palm's length and
width, each finger's three segments, each finger's width at its two inner segments' middles. Overlays and a sheet go to out/e62/.

    orchestrator/.venv/Scripts/python.exe engine/spikes/e62_hands.py make  nora,man,woman            # in the project that has them
    orchestrator/.venv/Scripts/python.exe engine/spikes/e62_hands.py make  ghoul,dwarf,goblin
    orchestrator/.venv/Scripts/python.exe engine/spikes/e62_hands.py read                             # every made picture not read yet
    orchestrator/.venv/Scripts/python.exe engine/spikes/e62_hands.py sheet
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("LOOM2_BASE", "http://127.0.0.1:8766")
TOKEN = os.environ.get("LOOM2_TOKEN", "devtoken")
OUT = Path(__file__).resolve().parent / "out" / "e62"
OUT.mkdir(parents=True, exist_ok=True)
STATE = OUT / "e62a.json"

HAND = ("{who} right hand alone, seen from the front with the palm facing the camera, the fingers straight and spread apart, the whole hand "
        "and the wrist inside the picture, plain light grey background, soft even studio light{words}")
FEET = ("{who} feet and shoes seen from the side, standing on the floor, from the knees down, the whole foot, the sole and the heel inside "
        "the picture, plain light grey background, soft even studio light{words}")
SUBJECTS = {
    "nora": {"profile": "Nora"},
    "nora-words": {"profile": "Nora", "sheet": True},                                     # her words, not her references
    "nora-feet": {"profile": "Nora", "sheet": True, "feet": True},
    "man-feet": {"profile": "Man with a newspaper", "sheet": True, "feet": True},
    "woman-feet": {"profile": "Woman with shopping", "sheet": True, "feet": True},
    "ghoul-feet": {"who": "A gaunt grey ghoul's", "words": ": bare grey bony feet with long clawed toes", "feet": True},
    "dwarf-feet": {"who": "A stocky dwarf's", "words": ": heavy round-toed leather boots with thick soles", "feet": True},
    "heel-feet": {"who": "A woman's", "words": ": black patent stiletto shoes with a 10 cm heel", "feet": True},
    "man": {"profile": "Man with a newspaper"},
    "woman": {"profile": "Woman with shopping"},
    "ghoul": {"who": "A gaunt grey ghoul's", "words": ": a large hand with very long, thin, bony fingers and long black claws"},
    "dwarf": {"who": "A stocky dwarf's", "words": ": a broad hand with short, thick, chunky fingers and blunt nails"},
    "goblin": {"who": "A green goblin's", "words": ": a hand with only four fingers - three long fingers and a thumb - and pointed nails"},
}
FINGERS = {"thumb": [1, 2, 3, 4], "index": [5, 6, 7, 8], "middle": [9, 10, 11, 12], "ring": [13, 14, 15, 16], "pinky": [17, 18, 19, 20]}
EDGES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16),
         (0, 17), (17, 18), (18, 19), (19, 20)]


def api(method: str, path: str, body: dict | None = None, raw: bool = False):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Loom-Token": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if raw else json.loads(data)


def wait(job_id: str, timeout: float = 1800) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = next((x for x in api("GET", "/jobs")["items"] if x["id"] == job_id), None)
        if j and j["status"] in ("done", "failed", "cancelled"):
            return j
        time.sleep(3)
    raise TimeoutError(job_id)


def load() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {"pictures": []}


def save(st: dict) -> None:
    STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")


def make(names: list[str]) -> None:
    caps = api("GET", "/capabilities")
    models = {"klein": caps["story"]["model_id"], "dev": caps["defaults"]["t2i"]}
    profiles = api("GET", "/story/profiles")["items"]
    project = api("GET", "/project")
    st = load()
    for name in names:
        sub = SUBJECTS[name]
        mentions, who = [], sub.get("who", "")
        words = sub.get("words", "")
        if "profile" in sub:
            p = next((x for x in profiles if x["name"] == sub["profile"]), None)
            if p is None:
                print("no profile", sub["profile"], "in", project["name"]); continue
            who = f"{p['name']}'s"
            if sub.get("sheet"):                                           # the sheet's words alone: a reference set draws the whole person
                v = next(x for x in p["versions"] if x["id"] == p["current"])
                words = ": " + "; ".join(x for x in (v.get("appearance"), v.get("outfit")) if x)
            else:
                mentions = [{"group_id": "", "name": p["name"], "profile_id": p["id"], "version": p["current"]}]
        prompt = (FEET if sub.get("feet") else HAND).format(who=who, words=words)
        for mk, mid in models.items():
            recipe = {"kind": "t2i", "model_id": mid, "prompt_mode": "text", "prompt_text": prompt, "width": 1024, "height": 1024, "seeds": [62],
                      "mentions": mentions, **({"turbo": True} if caps["models"][mid].get("turbo") else {})}
            t0 = time.time()
            job = api("POST", "/jobs", {"recipe": recipe, "stage": False, "origin": {"suite": "generate", "surface": "sketch"}})["jobs"][0]
            j = wait(job["id"])
            aid = (j.get("result") or {}).get("asset_ids", [None])[0]
            print(name, mk, j["status"], f"{time.time() - t0:.0f} s", aid, (j.get("error") or "")[:200])
            st["pictures"].append({"subject": name, "feet": bool(sub.get("feet")), "model": mk, "model_id": mid, "asset_id": aid, "job": j["id"], "project": project["path"],
                                   "seconds": round(time.time() - t0, 1), "prompt": prompt})
            save(st)


def engine_history(port: int, prompt_id: str, timeout: float = 600) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/history/{prompt_id}", timeout=30) as r:
            h = json.loads(r.read())
        if prompt_id in h and h[prompt_id].get("outputs"):
            return h[prompt_id]
        if prompt_id in h and h[prompt_id].get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(h[prompt_id]["status"])[:800])
        time.sleep(1)
    raise TimeoutError(prompt_id)


def people_of(text: str) -> tuple[list, list]:
    frames = json.loads(text)
    frame = (frames[0] if isinstance(frames, list) and frames else frames) or {}
    return frame.get("people") or [], [frame.get("canvas_width"), frame.get("canvas_height")]


def read() -> None:
    st = load()
    eng = api("GET", "/engine")
    for pic in st["pictures"]:
        if not pic.get("asset_id") or pic.get("boxes") is not None:
            continue
        j = wait(api("POST", "/jobs", {"recipe": {"kind": "keypoints", "asset_id": pic["asset_id"]}, "stage": False})["jobs"][0]["id"])
        pic["boxes"] = {"status": j["status"], "people": (j.get("result") or {}).get("people") or [], "error": j.get("error")}
        graph = json.loads((Path(pic["project"]) / "jobs" / "graphs" / f"{j['id']}.json").read_text(encoding="utf-8"))
        graph.pop("2", None); graph.pop("4", None)                         # RT-DETR and its boxes: SDPose reads the whole picture
        graph["5"]["inputs"].pop("bboxes", None)
        req = urllib.request.Request(f"http://127.0.0.1:{eng['port']}/prompt", data=json.dumps({"prompt": graph}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            pid = json.loads(r.read())["prompt_id"]
        h = engine_history(eng["port"], pid)
        out = next(iter(h["outputs"].values()))
        text = (out.get("text") or [""])[0]
        people, canvas = people_of(text)
        pic["nobox"] = {"people": people, "canvas": canvas}
        print(pic["subject"], pic["model"], "boxes:", len(pic["boxes"]["people"]), "people; no boxes:", len(people))
        save(st)


# ---- a2: the product's subject matte, and SDPose on the hand shrunk into a larger canvas ---------------------------------------------
def engine_port() -> int:
    return int(api("GET", "/engine")["port"])


def engine_run(graph: dict) -> dict:
    port = engine_port()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/prompt", data=json.dumps({"prompt": graph}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        pid = json.loads(r.read())["prompt_id"]
    return engine_history(port, pid)


def engine_upload(img: Image.Image, name: str) -> str:
    buf = io.BytesIO(); img.save(buf, "PNG")
    boundary = "----e62" + str(int(time.time() * 1000))
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"http://127.0.0.1:{engine_port()}/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["name"]


def engine_image(out: dict) -> Image.Image:
    im = out["images"][0]
    q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
    with urllib.request.urlopen(f"http://127.0.0.1:{engine_port()}/view?{q}", timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).copy()


def picture(pic: dict) -> Image.Image:
    """The picture, cached beside the sheet; found in its own project's assets folder when another project is open."""
    cache = OUT / "img" / f"{pic['asset_id']}.png"
    if not cache.is_file():
        cache.parent.mkdir(exist_ok=True)
        local = sorted((Path(pic["project"]) / "assets").glob(f"*/{pic['asset_id']}.png"))
        if local:
            cache.write_bytes(local[0].read_bytes())
        else:
            cache.write_bytes(api("GET", f"/assets/{pic['asset_id']}/file", raw=True))
    return Image.open(cache).convert("RGB")


def read2(scales=(0.5, 0.3)) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orchestrator"))
    from loom2.roster import ROSTER_BY_ID
    st = load()
    birefnet, sdpose = ROSTER_BY_ID["birefnet"].name, ROSTER_BY_ID["sdpose-wholebody"].name
    for pic in st["pictures"]:
        if not pic.get("asset_id"):
            continue
        img = picture(pic)
        name = engine_upload(img, f"e62-{pic['asset_id']}.png")
        if not (OUT / f"mask-{pic['asset_id']}.png").is_file():                                   # BiRefNet, the product's subject matte
            h = engine_run({"100": {"class_type": "LoadImage", "inputs": {"image": name}},
                            "1": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": birefnet}},
                            "2": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["1", 0], "image": ["100", 0]}},
                            "5": {"class_type": "MaskToImage", "inputs": {"mask": ["2", 0]}},
                            "99": {"class_type": "SaveImage", "inputs": {"images": ["5", 0], "filename_prefix": "e62/matte"}}})
            engine_image(h["outputs"]["99"]).convert("L").save(OUT / f"mask-{pic['asset_id']}.png")
        for s in scales:
            key = f"inset{int(s * 100)}"
            if pic.get(key):
                continue
            W, H = img.size
            bg = tuple(int(x) for x in np.median(np.concatenate([np.asarray(img)[0], np.asarray(img)[-1]]), axis=0))
            canvas = Image.new("RGB", (W, H), bg)
            small = img.resize((round(W * s), round(H * s)), Image.LANCZOS)
            ox, oy = (W - small.width) // 2, (H - small.height) // 2
            canvas.paste(small, (ox, oy))
            n2 = engine_upload(canvas, f"e62-{pic['asset_id']}-{key}.png")
            g = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": sdpose}}, "3": {"class_type": "LoadImage", "inputs": {"image": n2}},
                 "5": {"class_type": "SDPoseKeypointExtractor", "inputs": {"model": ["1", 0], "vae": ["1", 2], "image": ["3", 0], "batch_size": 1}},
                 "6": {"class_type": "PreviewAny", "inputs": {"source": ["5", 0]}}}
            out = next(iter(engine_run(g)["outputs"].values()))
            people, canvas_wh = people_of((out.get("text") or [""])[0])
            for p in people:                                                                    # back to the picture's own pixels
                for k in ("hand_left_keypoints_2d", "hand_right_keypoints_2d", "foot_keypoints_2d", "pose_keypoints_2d"):
                    a = p.get(k)
                    if a:
                        p[k] = [((v - ox) / s if i % 3 == 0 else (v - oy) / s if i % 3 == 1 else v) for i, v in enumerate(a)]
            pic[key] = {"people": people, "scale": s}
            print(pic["subject"], pic["model"], key, len(people), "people")
        save(st)


# ---- the measures -----------------------------------------------------------------------------------------------------------------
def best_hand(people: list) -> tuple[str | None, np.ndarray | None]:
    best, side = None, None
    for p in people:
        for key in ("hand_right_keypoints_2d", "hand_left_keypoints_2d"):
            a = np.array(p.get(key) or [], float).reshape(-1, 3) if p.get(key) else None
            if a is None or len(a) != 21:
                continue
            if best is None or a[:, 2].mean() > best[:, 2].mean():
                best, side = a, key
    return side, best


def matte(img: Image.Image) -> np.ndarray:
    a = np.asarray(img.convert("RGB")).astype(np.int32)
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, axis=0)
    fg = (np.abs(a - bg).sum(axis=2) > 36).astype(np.uint8) * 255
    m = Image.fromarray(fg, "L")
    for x, y in ((0, 0), (m.width - 1, 0), (0, m.height - 1), (m.width - 1, m.height - 1)):
        if m.getpixel((x, y)) == 0:
            ImageDraw.floodfill(m, (x, y), 128)
    return np.asarray(m) != 128                                             # the hand: all that the border's background does not reach


def mask_of(pic: dict, img: Image.Image) -> np.ndarray:
    f = OUT / f"mask-{pic['asset_id']}.png"
    return (np.asarray(Image.open(f).convert("L").resize(img.size)) > 127) if f.is_file() else matte(img)   # BiRefNet's, else the border's colour


def width_at(mask: np.ndarray, p: np.ndarray, q: np.ndarray) -> float:
    mid, d = (p + q) / 2, q - p
    n = np.array([-d[1], d[0]]) / max(1e-6, float(np.hypot(*d)))
    h, w = mask.shape
    tot = 0.0
    for s in (1, -1):
        t = 0
        while t < 400:
            x, y = mid + s * t * n
            xi, yi = int(round(x)), int(round(y))
            if not (0 <= xi < w and 0 <= yi < h) or not mask[yi, xi]:
                break
            t += 1
        tot += t                                                            # the march's length, whether it left the hand or ran out
    return tot


def best_foot(people: list) -> tuple[np.ndarray | None, np.ndarray | None]:
    """The foot SDPose is surest of — its big toe, small toe and heel — and that side's ankle (COCO-18: 10 the right, 13 the left)."""
    best, ank = None, None
    for p in people:
        f = np.array(p.get("foot_keypoints_2d") or [], float).reshape(-1, 3)
        b = np.array(p.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
        for k, ai in ((0, 13), (3, 10)):                                   # COCO-WholeBody: the left foot first
            if len(f) < k + 3:
                continue
            tri = f[k:k + 3]
            if best is None or tri[:, 2].mean() > best[:, 2].mean():
                best, ank = tri, (b[ai] if len(b) > ai else None)
    return best, ank


def measure_feet(pic: dict, variant: str) -> dict | None:
    F, A = best_foot(pic.get(variant, {}).get("people") or [])
    if F is None:
        return None
    img = picture(pic)
    mask = mask_of(pic, img)
    big, small, heel = F[0, :2], F[1, :2], F[2, :2]
    length = float(np.hypot(*(big - heel)))
    rows = np.where(mask.any(axis=1))[0]
    floor = float(rows.max()) if len(rows) else float(img.height)
    out = {"conf": round(float(F[:, 2].mean()), 2), "length_px": round(length), "pitch_deg": round(float(np.degrees(np.arctan2(big[1] - heel[1], abs(big[0] - heel[0]) or 1))), 1),
           "heel_up": round((floor - heel[1]) / max(1, length), 2), "toe_up": round((floor - big[1]) / max(1, length), 2),
           "ankle_up": round((floor - A[1]) / max(1, length), 2) if A is not None and A[2] >= 0.3 else None, "matte_share": round(float(mask.mean()), 3)}
    pic.setdefault("measures", {})[variant] = out
    return out


def measure(pic: dict, variant: str) -> dict | None:
    if pic.get("feet"):
        return measure_feet(pic, variant)
    side, H = best_hand(pic.get(variant, {}).get("people") or [])
    if H is None:
        return None
    img = picture(pic)
    mask = mask_of(pic, img)
    L = lambda i, j: float(np.hypot(*(H[i, :2] - H[j, :2])))              # noqa: E731
    palm = L(0, 9)
    out = {"side": side, "conf": round(float(H[:, 2].mean()), 2), "low": int((H[:, 2] < 0.3).sum()), "palm_px": round(palm), "palm_w_px": round(L(5, 17)),
           "fingers": {}, "matte_share": round(float(mask.mean()), 3)}
    for f, ix in FINGERS.items():
        segs = [L(ix[k], ix[k + 1]) for k in range(3)]
        wid = [width_at(mask, H[ix[k], :2], H[ix[k + 1], :2]) for k in (0, 1)]
        out["fingers"][f] = {"len_palm": round(sum(segs) / max(1, palm), 2), "w_len": round(float(np.mean(wid)) / max(1, sum(segs)), 2),
                             "w_palm": round(float(np.mean(wid)) / max(1, palm), 2)}
    # four fingers drawn as five: two chains whose tips sit closer than a tenth of the palm
    tips = [H[ix[3], :2] for ix in FINGERS.values()][1:]
    out["tips_merged"] = sum(1 for i in range(len(tips)) for k in range(i + 1, len(tips)) if np.hypot(*(tips[i] - tips[k])) < 0.1 * palm)
    pic.setdefault("measures", {})[variant] = out
    return out


def overlay(pic: dict, variant: str, size: int = 360) -> Image.Image:
    img = picture(pic)
    mask = mask_of(pic, img)
    tint = np.asarray(img).copy()
    tint[~mask] = (tint[~mask] * 0.55).astype(np.uint8)                      # the matte: the background darkened
    im = Image.fromarray(tint)
    d = ImageDraw.Draw(im)
    side, H = best_hand(pic.get(variant, {}).get("people") or []) if not pic.get("feet") else (None, None)
    r = max(3, im.width // 160)
    if pic.get("feet"):
        F, A = best_foot(pic.get(variant, {}).get("people") or [])
        if F is not None:
            for (a, b), col in (((2, 0), (255, 200, 0)), ((0, 1), (0, 220, 120))):
                d.line([tuple(F[a, :2]), tuple(F[b, :2])], fill=col, width=max(2, r))
            if A is not None and A[2] >= 0.3:
                d.line([tuple(A[:2]), tuple(F[2, :2])], fill=(255, 80, 200), width=max(2, r))
                d.ellipse((A[0] - r, A[1] - r, A[0] + r, A[1] + r), fill=(255, 80, 200))
            for x, y, c in F:
                d.ellipse((x - r, y - r, x + r, y + r), fill=(40, 120, 255) if c >= 0.3 else (255, 40, 40))
    if H is not None:
        for k, (a, b) in enumerate(EDGES):
            hue = k / len(EDGES)
            col = tuple(int(255 * c) for c in __import__("colorsys").hsv_to_rgb(hue, 1, 1))
            if H[a, 2] >= 0.3 and H[b, 2] >= 0.3:
                d.line([tuple(H[a, :2]), tuple(H[b, :2])], fill=col, width=max(2, r))
        for x, y, c in H:
            d.ellipse((x - r, y - r, x + r, y + r), fill=(40, 120, 255) if c >= 0.3 else (255, 40, 40))
    im = im.resize((size, size), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    m = pic.get("measures", {}).get(variant)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    label = f"{pic['subject']} · {pic['model']} · {variant}"
    if pic.get("feet"):
        label += f"\nconf {m['conf']} · pitch {m['pitch_deg']}° · heel up {m['heel_up']} · ankle up {m['ankle_up']}" if m else "\nno foot found"
    else:
        label += f"\nconf {m['conf']} · middle {m['fingers']['middle']['len_palm']}× palm · w/len {m['fingers']['middle']['w_len']}" if m else "\nno hand found"
    d.rectangle((0, 0, size, 36), fill=(0, 0, 0))
    d.text((6, 2), label, fill=(240, 240, 240), font=font)
    return im


def sheet() -> None:
    st = load()
    rows = []
    for pic in st["pictures"]:
        if not pic.get("asset_id"):
            continue
        vs = [v for v in ("boxes", "nobox", "inset50", "inset30") if pic.get(v)]
        for v in vs:
            measure(pic, v)
        rows.append([overlay(pic, v) for v in vs])
    save(st)
    per_row = max(len(r) for r in rows)                                        # a picture a row, its readings across
    pairs = rows
    W, Hh = 360 * per_row + 6 * (per_row - 1), 360
    canvas = Image.new("RGB", (W, len(pairs) * (Hh + 6)), (20, 20, 22))
    for r, row in enumerate(pairs):
        for c, im in enumerate(row):
            canvas.paste(im, (c * 366, r * (Hh + 6)))
    out = OUT / "e62a-sheet.png"
    canvas.save(out)
    print("sheet", out)
    for pic in st["pictures"]:
        for v, m in (pic.get("measures") or {}).items():
            if not m:
                print(f"{pic['subject']:7s} {pic['model']:5s} {v:6s} nothing found"); continue
            if pic.get("feet"):
                print(f"{pic['subject']:10s} {pic['model']:5s} {v:7s} conf {m['conf']:.2f} length {m['length_px']:4d}px pitch {m['pitch_deg']:5.1f}° heel up {m['heel_up']} toe up {m['toe_up']} ankle up {m['ankle_up']}")
                continue
            f = m["fingers"]
            print(f"{pic['subject']:7s} {pic['model']:5s} {v:6s} conf {m['conf']:.2f} low {m['low']:2d} palm {m['palm_px']:4d}px  "
                  + "  ".join(f"{k[:2]} {f[k]['len_palm']:.2f}/{f[k]['w_len']:.2f}" for k in FINGERS) + f"  merged tips {m['tips_merged']}")


# ---- E62 b: does Wan Animate draw the fingers the guide gives? -------------------------------------------------------------------------
GHOUL = ("A gaunt grey ghoul, tall and thin, in a ragged dark hooded robe, bare bony arms, very large hands with very long thin bony fingers "
         "and long black claws, standing")
B_STATE = OUT / "e62b.json"


def ghoul() -> None:
    """The ghoul through the product path in the open project: its picture (FLUX.2 dev), the profile, its A-pose candidates (dev, D186's
    card), the first picked, the body fitted to it (the shell follows by itself, D183)."""
    caps = api("GET", "/capabilities")
    dev = caps["defaults"]["t2i"]
    st = json.loads(B_STATE.read_text(encoding="utf-8")) if B_STATE.is_file() else {}
    if not st.get("hero"):
        j = wait(api("POST", "/jobs", {"recipe": {"kind": "t2i", "model_id": dev, "prompt_mode": "text", "prompt_text": GHOUL + ", full body, plain light background",
                                                  "width": 768, "height": 1344, "seeds": [62], "turbo": True}, "stage": False,
                                       "origin": {"suite": "generate", "surface": "sketch"}})["jobs"][0]["id"])
        st["hero"] = j["result"]["asset_ids"][0]; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8"); print("hero", st["hero"])
    if not st.get("profile"):
        p = api("POST", "/story/profiles", {"name": "Ghoul", "cls": "character", "hero_asset_id": st["hero"], "appearance": GHOUL})
        st["profile"] = p["id"]; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8"); print("profile", p["id"])
    pid = st["profile"]
    if not st.get("aref"):
        r = api("POST", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "count": 2, "model_id": dev})
        js = [wait(x) for x in r["job_ids"]]
        ids = [x["result"]["asset_ids"][0] for x in js if x["status"] == "done"]
        print("A-pose candidates", ids, [x["status"] for x in js])
        api("PUT", f"/story/profiles/{pid}/versions/v1/anim-ref", {"side": "front", "asset_id": ids[0]})
        st["aref"] = ids[0]; st["aref_candidates"] = ids; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    if not st.get("fit"):
        r = api("POST", f"/story/profiles/{pid}/versions/v1/body/fit")
        j = wait(r["job_id"]); print("fit", j["status"], (j.get("error") or "")[:200])
        st["fit"] = j["id"]; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    t0 = time.time()
    while time.time() - t0 < 1800:                                            # the shell (Pixal3D, ≈ 4 min), queued by the fit
        v = api("GET", f"/story/profiles/{pid}")["versions"][0]
        if v.get("shell_asset_id"):
            st["shell"] = v["shell_asset_id"]; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8"); print("shell", v["shell_asset_id"], f"{time.time() - t0:.0f} s"); break
        time.sleep(10)


def widen(fid: str, lid: str, factor: float) -> None:
    """The layer's stored hands with every finger lengthened by `factor` from its knuckle (the thumb from its base) — keypoints.json kept
    beside as keypoints.orig.json; a windowed layer's guide is drawn from these at its next perform."""
    project = Path(api("GET", "/project")["path"])
    p = project / "finals" / fid / lid / "keypoints.json"
    orig = p.with_name("keypoints.orig.json")
    if not orig.is_file():
        orig.write_bytes(p.read_bytes())
    data = json.loads(orig.read_text(encoding="utf-8"))
    n = 0
    for wb in data.get("wholebody") or []:
        if not wb:
            continue
        for side in ("left", "right"):
            pts = wb.get(side)
            if not pts or len(pts) < 21:
                continue
            for ix in FINGERS.values():
                base = np.array(pts[ix[0]][:2], float)
                for k in ix[1:]:
                    q = np.array(pts[k][:2], float)
                    pts[k][0], pts[k][1] = (base + (q - base) * factor).tolist()
            n += 1
    p.write_text(json.dumps(data), encoding="utf-8")
    print("widened", n, "hands by", factor)


def perform(fid: str, lid: str, seed: int, timeout: float = 3600) -> dict:
    """The layer performed through the product's route with this seed; waits for it to be done (performed and matted)."""
    api("POST", f"/finals/{fid}/layers/{lid}/run", {"seed": seed, "from_batch": 0, "stage": False})
    t0, last = time.time(), ""
    while time.time() - t0 < timeout:
        f = api("GET", f"/finals/{fid}")
        layer = next(x for x in f["layers"] if x["id"] == lid)
        state = f"{layer['status']} {layer.get('frames_done')}/{f['frames']}"
        if state != last:
            print(f"  {time.time() - t0:5.0f} s  {state}"); last = state
        if layer["status"] in ("done", "failed"):
            return {"layer": layer, "seconds": round(time.time() - t0)}
        time.sleep(5)
    raise TimeoutError(lid)


def keep(fid: str, lid: str, tag: str) -> Path:
    """The layer's frames and its guide drawn for this perform, copied beside the sheet."""
    import shutil
    project = Path(api("GET", "/project")["path"])
    base = project / "finals" / fid / lid
    dst = OUT / "b" / tag
    shutil.rmtree(dst, ignore_errors=True)
    for sub in ("frames", "window/pose", "pose"):
        src = base / sub
        if src.is_dir():
            shutil.copytree(src, dst / sub.replace("/", "_"))
    takes = sorted((base / "passes").glob("*")) if (base / "passes").is_dir() else []
    if takes:                                                                  # D118: a take's own frames when it is the source
        shutil.copytree(takes[-1], dst / "take")
    print("kept", tag, [p.name for p in dst.iterdir()])
    return dst


def ab(fid: str, lid: str, factor: float, seed: int = 62) -> None:
    st = json.loads(B_STATE.read_text(encoding="utf-8")) if B_STATE.is_file() else {}
    if not st.get("A"):
        r = perform(fid, lid, seed); keep(fid, lid, "A")
        st["A"] = {"seconds": r["seconds"], "status": r["layer"]["status"], "error": r["layer"].get("error")}; B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    widen(fid, lid, factor)
    r = perform(fid, lid, seed); keep(fid, lid, "B")
    st["B"] = {"seconds": r["seconds"], "status": r["layer"]["status"], "error": r["layer"].get("error"), "factor": factor}
    B_STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    print("A", st["A"], "B", st["B"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sheet"
    if cmd == "make":
        make(sys.argv[2].split(","))
    elif cmd == "read":
        read()
    elif cmd == "read2":
        read2()
    elif cmd == "sheet":
        sheet()
    elif cmd == "ghoul":
        ghoul()
    elif cmd == "widen":
        widen(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif cmd == "ab":
        ab(sys.argv[2], sys.argv[3], float(sys.argv[4]))
