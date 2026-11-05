"""RG1 (D187, D188; proto01_rig 00 §4, §9, §10): a character's own hands and feet — read from a hand picture and a feet picture of its own,
made from words about the hand or the shoes alone (never the character's references or its whole sheet: E62 a drew the whole person).

**The hand** (R2) is a shape in palm lengths (the wrist to the middle finger's knuckle = 1), in the palm's frame: the wrist at the origin, +y
toward the middle knuckle, +x toward the thumb — so one shape serves either hand, mirrored (Q2). Each finger has its base (the thumb's
first joint, a finger's knuckle), its direction, its three segments, its width and an optional claw of its own (Q5); the hand has a finger
count (Q4: three, four or five — neither model draws four fingers when asked, so it is set by hand) and a claw. Its size stays the body's
`hands` factor, fitted from the A-pose's palm. Read by SDPose without person boxes on the picture shrunk to 30 % of its canvas (E62 a: 0.84–
0.99 against 0.44–0.57 at its size), the widths from BiRefNet's subject matte.

**The foot** (F2) is a shape in foot lengths (the heel point to the big toe = 1), read on a side view: the pitch from the heel point to the
toe (E62 c: boots 2–6°, flat shoes 6–11°, bare clawed feet 15–20°, stilettos 30–55°), the ankle's height and place, the heel's and the
toe's heights over the floor, the ball's place (not read: 0.72, placed by hand in the Feet & legs view), and — on a full figure (the A-pose
side view, D175) — the foot's length against the leg's.

None of this draws anything yet (RG1): the clay hand (RG2) and the guide (R5, F5) read it next."""
from __future__ import annotations

import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FingerName = Literal["thumb", "index", "middle", "ring", "pinky"]
FINGERS: tuple[str, ...] = ("thumb", "index", "middle", "ring", "pinky")
CHAINS: dict[str, tuple[int, int, int, int]] = {"thumb": (1, 2, 3, 4), "index": (5, 6, 7, 8), "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16),
                                                "pinky": (17, 18, 19, 20)}   # SDPose's 21 points a hand: 0 the wrist
HIDDEN = {5: (), 4: ("pinky",), 3: ("ring", "pinky")}   # Q4: the fingers a count hides (a goblin's three fingers and a thumb: 4)
HAND_INSET = 0.3                 # E62 a: a hand read best shrunk to 30 % of its canvas, without boxes
FEET_INSET = 0.4                 # E62 c (a): feet close-ups 30–50 %
MIN_CONF = 0.5                   # a read surer than this on average is kept
POINT_CONF = 0.3                 # a point this sure counts


class Finger(BaseModel):
    """One finger (or the thumb) in palm lengths, in the palm's frame (+x toward the thumb)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    base: list[float] = Field(min_length=2, max_length=2)          # the knuckle (the thumb: its first joint)
    angle: float = Field(0.0, ge=-180.0, le=180.0)                 # its first segment from +y, degrees, + toward the thumb (any way: a misread may point back)
    lengths: list[float] = Field(min_length=3, max_length=3)       # its three segments, knuckle to tip
    width: float = Field(0.19, ge=0.03, le=0.8)
    claw: float | None = Field(None, ge=0.0, le=1.0)               # Q5: its own claw; None = the hand's

    @field_validator("lengths")
    @classmethod
    def _lengths(cls, v: list[float]) -> list[float]:
        if any(not 0.02 <= x <= 1.5 for x in v):
            raise ValueError("a finger's segment is 0.02–1.5 palm lengths")
        return [round(float(x), 3) for x in v]

    @field_validator("base")
    @classmethod
    def _base(cls, v: list[float]) -> list[float]:
        if any(abs(x) > 2.0 for x in v):
            raise ValueError("a finger's base lies within two palm lengths of the wrist")
        return [round(float(x), 3) for x in v]


def _f(base: tuple[float, float], angle: float, length: float, split: tuple[float, float, float], width: float) -> Finger:
    return Finger(base=list(base), angle=angle, lengths=[length * s for s in split], width=width)


SPLIT = (0.45, 0.30, 0.25)       # a finger's segments' shares, knuckle to tip
THUMB_SPLIT = (0.40, 0.33, 0.27)


def human_fingers() -> dict[str, Finger]:
    """The default hand: the humans E62 a read (Followed's three on Klein at 30 %) — the middle finger 0.73 palms, the index 0.67, the ring
    0.64, the pinky 0.48, the thumb's chain 0.77; the fingers 0.19 palms wide, the thumb 0.23."""
    return {"thumb": _f((0.30, 0.28), 45.0, 0.77, THUMB_SPLIT, 0.23), "index": _f((0.27, 0.96), 8.0, 0.67, SPLIT, 0.19),
            "middle": _f((0.0, 1.0), 0.0, 0.73, SPLIT, 0.19), "ring": _f((-0.20, 0.95), -8.0, 0.64, SPLIT, 0.18),
            "pinky": _f((-0.38, 0.86), -16.0, 0.48, SPLIT, 0.16)}


class HandShape(BaseModel):
    """R2: one hand's own skeleton, in palm lengths."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    count: Literal[3, 4, 5] = 5                                    # Q4: the fingers it has (the thumb counted)
    palm_width: float = Field(0.66, ge=0.2, le=1.5)                # the index knuckle to the pinky's
    claw: float = Field(0.0, ge=0.0, le=1.0)                       # Q5: every finger's claw unless it has its own
    fingers: dict[FingerName, Finger] = Field(default_factory=human_fingers)

    @field_validator("fingers")
    @classmethod
    def _five(cls, v: dict[str, Finger]) -> dict[str, Finger]:
        if set(v) != set(FINGERS):
            raise ValueError("a hand keeps all five fingers (a count hides some)")
        return v

    def shown(self) -> list[str]:
        """The fingers drawn (Q4: the guide draws only these, R5)."""
        return [f for f in FINGERS if f not in HIDDEN[self.count]]


class Hands(BaseModel):
    """Q2: one hand fitted and mirrored — `left` None is the right mirrored; *Unlink* gives the left a shape of its own."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    right: HandShape = Field(default_factory=HandShape)
    left: HandShape | None = None


class FootShape(BaseModel):
    """F2: one foot, in foot lengths (the heel point to the big toe), seen from the side."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    pitch: float = Field(6.0, ge=-30.0, le=75.0)                   # the heel point over the toe, degrees (a heel raises it)
    ankle_up: float = Field(0.44, ge=0.05, le=2.0)                 # the ankle over the floor
    ankle_at: float = Field(0.20, ge=-0.5, le=1.0)                 # the ankle along the foot, from the heel
    heel_up: float = Field(0.25, ge=0.0, le=1.5)                   # the heel point over the floor (≈ 0.25 in a flat shoe)
    toe_up: float = Field(0.15, ge=0.0, le=1.0)                    # the big toe's point over the floor
    ball_at: float = Field(0.72, ge=0.3, le=0.95)                  # the ball along the foot (not read; placed by hand, F4)
    length_leg: float | None = Field(None, ge=0.05, le=1.0)        # the foot against the leg (hip → knee → ankle), from a full figure
    stiff: bool = False                                            # D189 (Q10): a stiff sole (a boot, a clog) — the shoe bends at the ankle only
    place: dict[str, list[float]] | None = None                    # RG3 (F4): the heel, the ball and the toe placed by hand on the shell — metres
    #                                                                from the ankle in the figure's frame (+x its left, +z ahead), the right foot's
    #                                                                (the left mirrored unless unlinked); None = found from the shape and the shell

    @field_validator("place")
    @classmethod
    def _place(cls, v: dict[str, list[float]] | None) -> dict[str, list[float]] | None:
        if v is None:
            return None
        if set(v) != {"heel", "ball", "toe"}:
            raise ValueError("a foot is placed by its heel, its ball and its toe")
        out = {}
        for k, xyz in v.items():
            if len(xyz) != 3 or any(not isinstance(x, (int, float)) or abs(x) > 0.6 for x in xyz):
                raise ValueError(f"{k}: three offsets of at most 0.6 m from the ankle")
            out[k] = [round(float(x), 4) for x in xyz]
        return out


class Feet(BaseModel):
    """F2: one foot fitted and mirrored, as the hands (Q2)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    right: FootShape = Field(default_factory=FootShape)
    left: FootShape | None = None


# ---- the pictures' words (Q4: their own, prefilled from the sheet) ------------------------------------------------------------------------
HAND_SENTENCE = ("A right hand alone, seen from the front with the palm facing the camera, the fingers straight and spread apart, the whole "
                 "hand and the wrist inside the picture, plain light grey background, soft even studio light")
FEET_SENTENCE = ("A pair of feet and shoes seen from the side, standing on the floor, from the knees down, the whole foot, the sole and the "
                 "heel inside the picture, plain light grey background, soft even studio light")
# What a sheet's clause must name to be about the hand or the feet (tests/fixtures/ref_words.json holds the client's copy, frontend
# ui2/world/refWords.ts, to the same rule).
HAND_WORDS = r"\b(hands?|fingers?|fingernails?|nails?|claws?|clawed|talons?|knuckles?|palms?|thumbs?|rings?|gloves?|gloved|mittens?|wrists?|bracelets?|skin|scales|scaly|fur|furred)\b"
FEET_WORDS = (r"\b(shoes?|boots?|booted|heels?|heeled|stilettos?|sandals?|sneakers?|trainers?|clogs?|slippers?|loafers?|brogues?|pumps?|"
              r"barefoot|bare|feet|foot|toes?|socks?|stockings?|tights|trousers|jeans|skirts?|dress|robes?|gowns?|hems?|leggings|breeches|"
              r"hooves|hoofed|paws?|skin|scales|scaly|fur|furred)\b")


def _clauses(*texts: str) -> list[str]:
    out = []
    for t in texts:
        for c in re.split(r"[,;.]|\bwith\b|\band\b(?=\s+(?:a|an|the|wearing|with)\b)", t or ""):   # "a ghoul with long fingers": the ghoul stays out
            c = c.strip().strip(",;").strip()
            if c:
                out.append(c)
    return out


def sheet_words(appearance: str, outfit: str, marks: str, part: Literal["hand", "feet"]) -> str:
    """The sheet's clauses about the hand (skin, nails, claws, rings, gloves) or the feet (the shoes, the hems, bare skin), led by what the
    character is when the sheet starts by saying so ("A gaunt grey ghoul", not "Nora") — what a hand or feet picture's words start from when
    the author has not written them (Q4: they are its own and edited freely)."""
    rx = re.compile(HAND_WORDS if part == "hand" else FEET_WORDS, re.IGNORECASE)
    first = next(iter(_clauses(appearance)), "")
    seen: list[str] = [first] if re.match(r"(?i)(a|an|the)\b", first) else []   # what the character is leads ("A gaunt grey ghoul": the rig drew a
    for c in _clauses(appearance, outfit, marks):                                # human hand with black nails without it, a grey bony one with it); a name does not
        if rx.search(c) and c.lower() not in (s.lower() for s in seen):
            seen.append(c)
    return ", ".join(seen)


def part_prompt(part: Literal["hand", "feet"], words: str) -> str:
    """E62's measured shape: the sentence, then the words after a colon."""
    w = (words or "").strip().strip(",;.").strip()
    return (HAND_SENTENCE if part == "hand" else FEET_SENTENCE) + (f": {w}" if w else "") + "."


# ---- reading the points ------------------------------------------------------------------------------------------------------------------
def unshrink(people: list[dict], canvas: tuple[int, int] | list[int], inset: float) -> list[dict]:
    """The points SDPose read on the picture shrunk to `inset` of its canvas (centred, pipeline.inset_image) back in the picture's pixels."""
    if inset >= 0.999:
        return people
    w, h = int(canvas[0]), int(canvas[1])
    ox, oy = (w - round(w * inset)) // 2, (h - round(h * inset)) // 2
    out = []
    for p in people:
        q = dict(p)
        for k in ("pose_keypoints_2d", "hand_left_keypoints_2d", "hand_right_keypoints_2d", "foot_keypoints_2d", "face_keypoints_2d"):
            a = p.get(k)
            if a:
                q[k] = [((v - ox) / inset if i % 3 == 0 else (v - oy) / inset if i % 3 == 1 else v) for i, v in enumerate(a)]
        out.append(q)
    return out


def best_hand(people: list[dict]) -> list[list[float]] | None:
    """The surest of the hands read (whichever side SDPose took a lone hand for), 21 × [x, y, confidence]."""
    best, conf = None, -1.0
    for p in people:
        for key in ("hand_right_keypoints_2d", "hand_left_keypoints_2d"):
            a = [float(v) for v in (p.get(key) or [])]
            if len(a) < 63:
                continue
            pts = [a[i:i + 3] for i in range(0, 63, 3)]
            c = sum(x[2] for x in pts) / 21
            if c > conf:
                best, conf = pts, c
    return best


def best_foot(people: list[dict]) -> tuple[list[list[float]], list[float] | None, list[list[float]] | None] | None:
    """The foot to measure — its big toe, small toe and heel — with that side's ankle and the leg above it (hip, knee, ankle) when the body
    was read too (COCO-WholeBody's feet: the left first; OpenPose-18: 8–10 the right leg, 11–13 the left). The near foot when it was read
    surely enough: the lowest in the picture, standing on the floor the matte sees (the rig: Klein drew the ghoul's feet from three-quarters
    front and SDPose was surer of the far one, its heel then read 0.75 foot lengths up); else the surest."""
    feet = []
    for p in people:
        f = [float(v) for v in (p.get("foot_keypoints_2d") or [])]
        b = [float(v) for v in (p.get("pose_keypoints_2d") or [])]
        body = [b[i:i + 3] for i in range(0, len(b) - 2, 3)]
        for k, leg in ((0, (11, 12, 13)), (3, (8, 9, 10))):
            if len(f) < (k + 3) * 3:
                continue
            tri = [f[(k + j) * 3:(k + j) * 3 + 3] for j in range(3)]
            chain = [body[i] for i in leg] if len(body) > leg[2] else None
            sure = tri[0][2] >= POINT_CONF and tri[2][2] >= POINT_CONF and (tri[0][2] + tri[2][2]) / 2 >= MIN_CONF
            feet.append((sure, (tri[0][1] + tri[2][1]) / 2, sum(x[2] for x in tri) / 3, tri, chain[2] if chain else None, chain))
    if not feet:
        return None
    sure = [x for x in feet if x[0]]
    pick = max(sure, key=lambda x: x[1]) if sure else max(feet, key=lambda x: x[2])
    return pick[3], pick[4], pick[5]


def _width_at(mask: Any, p: tuple[float, float], q: tuple[float, float], reach: int = 400) -> float:
    """The matte's width across the segment p → q at its middle (a march each way until it leaves the matte)."""
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / n, dx / n
    h, w = mask.shape[:2]
    tot = 0
    for s in (1, -1):
        t = 0
        while t < reach:
            x, y = int(round(mx + s * t * nx)), int(round(my + s * t * ny))
            if not (0 <= x < w and 0 <= y < h) or not mask[y, x]:
                break
            t += 1
        tot += t
    return float(tot)


def fit_hand(people: list[dict], mask: Any = None, base: HandShape | None = None) -> tuple[HandShape, dict[str, Any], list[list[float]]]:
    """R2: a hand's shape from SDPose's 21 points (in the picture's pixels) and the subject matte (a bool array, or None: the widths stay
    the base's). The count and the claws stay the author's (`base`); a finger read unsurely keeps the base's. Returns the shape, a report
    and the 21 points. Raises ValueError when no hand was read surely enough."""
    H = best_hand(people)
    if H is None:
        raise ValueError("no hand found in the picture")
    conf = sum(x[2] for x in H) / 21
    if H[0][2] < POINT_CONF or H[9][2] < POINT_CONF or conf < MIN_CONF:
        raise ValueError(f"the hand was read too unsurely ({conf:.2f}) — make another hand picture, the hand flat and the fingers spread")
    base = base or HandShape()
    ox, oy = H[0][0], H[0][1]
    palm = math.hypot(H[9][0] - ox, H[9][1] - oy)
    if palm < 8:
        raise ValueError("the hand is too small in the picture to measure")
    ey = ((H[9][0] - ox) / palm, (H[9][1] - oy) / palm)
    ex = (-ey[1], ey[0])
    to = lambda i: ((H[i][0] - ox) * ex[0] + (H[i][1] - oy) * ex[1], (H[i][0] - ox) * ey[0] + (H[i][1] - oy) * ey[1])  # noqa: E731
    thumb = [to(i)[0] for i in (2, 3, 4) if H[i][2] >= POINT_CONF]
    if thumb and sum(thumb) / len(thumb) < 0:                       # +x toward the thumb, whichever hand it is
        ex = (-ex[0], -ex[1])
    dist = lambda i, j: math.hypot(H[i][0] - H[j][0], H[i][1] - H[j][1])  # noqa: E731
    fingers: dict[str, Finger] = {}
    read, kept, widths = [], [], {}
    for name, ch in CHAINS.items():
        old = base.fingers[name]
        if min(H[i][2] for i in ch) < POINT_CONF:
            fingers[name] = old
            kept.append(name)
            continue
        b0, b1 = to(ch[0]), to(ch[1])
        segs = [max(0.02, min(1.5, dist(ch[k], ch[k + 1]) / palm)) for k in range(3)]
        fingers[name] = old.model_copy(update={"base": [round(max(-2.0, min(2.0, b0[0] / palm)), 3), round(max(-2.0, min(2.0, b0[1] / palm)), 3)],
                                               "angle": round(math.degrees(math.atan2(b1[0] - b0[0], b1[1] - b0[1])), 1),
                                               "lengths": [round(s, 3) for s in segs]})
        read.append(name)
        if mask is not None and name != "thumb":                    # E62: the thumb's march crosses the palm — it follows the fingers
            ws = [_width_at(mask, H[ch[k]][:2], H[ch[k + 1]][:2]) / palm for k in (0, 1)]
            widths[name] = [x for x in ws if 0.06 <= x <= 0.6]      # 0: the point off the finger; past 0.6: fingers touching
    every = sorted(x for ws in widths.values() for x in ws)
    if every:                                                       # the hand's own width — the lower third: fingers touching only ever read
        mid = every[len(every) // 3]                                # wider (Followed's woman: two read 0.5 against 0.15) — and a finger's
        #                                                             own where it agrees with it
        own = {n: [x for x in ws if 0.6 * mid <= x <= 1.5 * mid] for n, ws in widths.items()}
        for name in read:
            w = mid * 1.2 if name == "thumb" else (sum(own[name]) / len(own[name]) if own.get(name) else mid)
            fingers[name] = fingers[name].model_copy(update={"width": round(max(0.03, min(0.8, w)), 3)})
        widths = {n: ws for n, ws in own.items() if ws}
    pw = base.palm_width
    if H[5][2] >= POINT_CONF and H[17][2] >= POINT_CONF:
        pw = round(max(0.2, min(1.5, dist(5, 17) / palm)), 3)
    shape = base.model_copy(update={"fingers": fingers, "palm_width": pw})
    report = {"conf": round(conf, 3), "palm_px": round(palm, 1), "read": read, "kept": kept, "widths": sorted(widths),
              "middle_palm": round(sum(fingers["middle"].lengths), 3)}
    return shape, report, [[round(x, 2), round(y, 2), round(c, 3)] for x, y, c in H]


def fit_foot(people: list[dict], mask: Any = None, base: FootShape | None = None, floor_at: float | None = None) -> tuple[FootShape, dict[str, Any], dict[str, Any]]:
    """F2: a foot's shape from SDPose's foot points on a side view (the big toe, the small toe, the heel; the ankle when the body was read)
    and the subject matte's lowest row as the floor (else `floor_at`, the floor a read kept — RG3's refit —, else the lowest foot point). The
    ball's place, the stiff sole and a placement by hand stay the base's. Returns the shape, a report and the points used. Raises ValueError
    when no foot was read surely enough."""
    got = best_foot(people)
    if got is None:
        raise ValueError("no foot found in the picture")
    tri, ankle, leg = got
    big, small, heel = tri
    conf = (big[2] + heel[2]) / 2
    if big[2] < POINT_CONF or heel[2] < POINT_CONF or conf < MIN_CONF:
        raise ValueError(f"the foot was read too unsurely ({conf:.2f}) — make another feet picture, from the side, the whole shoe in view")
    base = base or FootShape()
    length = math.hypot(big[0] - heel[0], big[1] - heel[1])
    if length < 8:
        raise ValueError("the foot is too small in the picture to measure")
    floor = float(floor_at) if floor_at is not None else max(big[1], heel[1], small[1] if small[2] >= POINT_CONF else -1e9)
    if mask is not None:
        rows = [y for y in range(mask.shape[0]) if mask[y].any()]
        if rows:
            floor = float(max(rows))
    fwd = 1.0 if big[0] >= heel[0] else -1.0
    up = {"pitch": round(math.degrees(math.atan2(big[1] - heel[1], abs(big[0] - heel[0]) or 1.0)), 1),
          "heel_up": round(max(0.0, min(1.5, (floor - heel[1]) / length)), 3),
          "toe_up": round(max(0.0, min(1.0, (floor - big[1]) / length)), 3)}
    if ankle is not None and ankle[2] >= POINT_CONF:
        up["ankle_up"] = round(max(0.05, min(2.0, (floor - ankle[1]) / length)), 3)
        up["ankle_at"] = round(max(-0.5, min(1.0, (ankle[0] - heel[0]) * fwd / length)), 3)
    if leg is not None and all(x[2] >= POINT_CONF for x in leg):
        L = math.hypot(leg[0][0] - leg[1][0], leg[0][1] - leg[1][1]) + math.hypot(leg[1][0] - leg[2][0], leg[1][1] - leg[2][1])
        if L > 1:
            up["length_leg"] = round(max(0.05, min(1.0, length / L)), 3)
    up["pitch"] = max(-30.0, min(75.0, up["pitch"]))
    shape = base.model_copy(update=up)
    report = {"conf": round(conf, 3), "length_px": round(length, 1), **up}
    r = lambda p: [round(p[0], 2), round(p[1], 2), round(p[2], 3)] if p else None  # noqa: E731
    return shape, report, {"foot": [r(big), r(small), r(heel)], "ankle": r(ankle), "leg": [r(x) for x in leg] if leg else None, "floor": round(floor, 1)}
