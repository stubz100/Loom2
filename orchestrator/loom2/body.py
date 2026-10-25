"""CA0 (D94, proto01_animate 01 §9): a character's body — on its Cast version's sheet (story.ProfileVersion.body) and copied onto the Stage
figure bound to that version (stages.StageObject.body), where it shapes the dummy: height, build, proportions, rigid attachments.

proto01_UIcast CS1 (D136, D137): ×1 is an adult (S3 — the dummy's neck 12 cm at 1.75 m, the head's pivot at the jaw), the elbows', knees',
hips' and feet's own factors (S5, S6), the figure (♀ / ♂: the Detailed mannequin, the Simple dummy retired, U18), the rest hand (S2) and a
fit that stays human unless the picture insists (S7)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BodyBuild = Literal["slim", "average", "broad", "heavy"]
AttachmentKind = Literal["tail", "horns", "ears", "wings", "antennae", "hat", "backpack", "other"]
BodyJoint = Literal["root", "spine", "head", "r_shoulder", "l_shoulder", "r_elbow", "l_elbow"]
FigureKind = Literal["female", "male"]
HandPresetName = Literal["open", "relaxed", "fist", "point", "grip", "pinch"]
ELBOW_AT = 29 / 56               # the upper arm's share of the arm (builders.ts: 0.29 + 0.27 at ×1)
KNEE_AT = 44 / 87                # the thigh's share of the leg (0.44 + 0.43)


class BodyAttachment(BaseModel):
    """CA0 (01 §9b N1): a rigid part that follows a joint of the figure — a tail, horns, folded wings. Shown on the Stage dummy and in its
    clay and depth passes; not in the pose pass (Wan Animate guesses its motion from the reference)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: AttachmentKind
    joint: BodyJoint | None = None                # None = the kind's own place (horns, ears, antennae, hat → head; wings, backpack → spine; tail → root)
    size: float = Field(1.0, ge=0.2, le=3.0)
    note: str = Field("", max_length=80)


class HandRest(BaseModel):
    """S2 (proto01_UIcast 03 §3.1): the character's hands at rest — what every pose of its Detailed figure starts from (a key's hand preset
    still turns them): a preset's curl, scaled. The GLB's own flat, fanned hand is never the rest."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    preset: HandPresetName = "relaxed"
    curl: float = Field(1.0, ge=0.0, le=1.6)      # × the preset's curl (0: the open hand)
    spread: float = Field(0.0, ge=-10.0, le=30.0)  # CS2: the fingers fanned (degrees at the knuckles, the index's way out; − closes them)
    thumb: float = Field(0.0, ge=-30.0, le=40.0)   # CS2: the thumb opened from the palm (degrees)


class Body(BaseModel):
    """CA0 (D94, 01 §9 answer 3): the body on the Cast sheet — it shapes the figure's Stage dummy when the figure is bound to this version.
    Height in metres; the proportions are factors of the default dummy (1 = the 1.75 m adult); the build widens or narrows it."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    height_m: float = Field(1.75, ge=0.3, le=4.0)
    build: BodyBuild = "average"
    figure: FigureKind = "female"                  # U18: the Detailed mannequin the character's figures are (♀ / ♂)
    head: float = Field(1.0, ge=0.5, le=2.5)
    torso: float = Field(1.0, ge=0.6, le=1.6)
    shoulders: float = Field(1.0, ge=0.6, le=1.8)
    hips: float = Field(1.0, ge=0.6, le=1.6)       # S7: the hips' width (no longer the fit's fixed anchor)
    arms: float = Field(1.0, ge=0.6, le=1.6)
    elbow: float = Field(ELBOW_AT, ge=0.35, le=0.65)   # S6: the elbow's place, the upper arm's share of the arm
    legs: float = Field(1.0, ge=0.5, le=1.6)
    knee: float = Field(KNEE_AT, ge=0.35, le=0.65)     # S6: the knee's place, the thigh's share of the leg
    neck: float = Field(1.0, ge=0.5, le=3.0)       # CA1b (D104): the neck's length (the head above the shoulders); ×1 an adult's (S3)
    hands: float = Field(1.0, ge=0.5, le=1.6)      # CA1b: the Detailed figure's hands (the pose pass draws them, D101)
    feet: float = Field(1.0, ge=0.5, le=1.6)       # CA1b: the feet (the dummy's and the Detailed figure's); fitted from the toes (S5)
    hand_rest: HandRest = Field(default_factory=HandRest)
    head_forward: float = Field(0.0, ge=-30.0, le=40.0)   # CS2: the head carried forward of the neck (degrees: a stoop +, a proud stance −)
    shoulder_drop: float = Field(1.0, ge=0.0, le=3.0)     # CS2: the shoulders under the neck joint (×1: 0.04 · torso; 0 square, 2–3 sloped)
    feet_out: float = Field(0.0, ge=-20.0, le=45.0)       # CS2: the feet turned out at rest (degrees)
    locks: list[str] = Field(default_factory=list, max_length=16)   # CS2: the factors *Fit again* leaves as the author set them
    attachments: list[BodyAttachment] = Field(default_factory=list, max_length=6)


def rebase_body(raw: dict[str, Any]) -> dict[str, Any]:
    """S3: a body stored before ×1 was an adult (the profile record's schema 2, the stage's 2: the neck 0.06, the head's pivot 0.08·head under
    the nose) as one of now (the neck 0.12, the pivot 0.02·head under the nose, every head point 0.06·head lower on it) — every point of
    the figure where it was: neck = (neck + head) / 2. The records' migrations call it on read (story.Profile, stages.migrate)."""
    n, hd = float(raw.get("neck", 1.0)), float(raw.get("head", 1.0))
    return {**raw, "neck": round(min(3.0, max(0.5, (n + hd) / 2)), 4)}


# ---- CA1b (D104): the body fitted to the character's animation reference -------------------------------------------------------------
BUILD_WIDTH = {"slim": 0.85, "average": 1.0, "broad": 1.15, "heavy": 1.3}      # frontend stage/body.ts
PALM_PER_LEG = 0.147          # the Detailed figure's palm (wrist → the middle finger's base) per leg length, measured on Stage in the A-pose front (CS1, journal 2026-10-25; 0.149 before)
TOES_PER_LEG = 0.058          # S5: the Detailed figure's toes (big toe ↔ small toe, front view) per leg length, measured on Stage (CS1, journal 2026-10-25)
A_POSE_DEG = 22.0             # the reference's stance (frontend stage/turnTest.ts A_POSE): arms 22° away from the body
FITTED = ("head_w", "head_neck", "torso", "shoulders", "hips", "leg", "arm", "palm", "elbow_at", "knee_at", "toes")
PULL = 0.02                   # S7: the weight of each factor's pull toward its adult value, against log-ratio residuals (≈ 2 % of a measure)
DEFAULTS = {"elbow": ELBOW_AT, "knee": KNEE_AT}


def dummy_ratios(b: Body) -> dict[str, float]:
    """The Stage dummy (frontend builders.ts `mannequin`) seen from the front in the A-pose, as SDPose would read it: each measure a fraction
    of the height from the nose to the ankles. Kept in step with builders.ts by tests/test_body_fit_ca1b.py's numbers."""
    w = BUILD_WIDTH.get(b.build, 1.0)
    hip = 0.07 + 0.88 * b.legs
    import math
    leg, arm = 0.87 * b.legs, 0.56 * b.arms
    spine = hip + 0.06
    shoulder_y = spine + 0.44 * b.torso - 0.04 * b.torso * b.shoulder_drop   # the shoulders' midpoint = OpenPose's neck point (CA1b); CS2's drop
    nose_y = spine + 0.44 * b.torso + 0.12 * b.neck * math.cos(math.radians(b.head_forward)) + 0.02 * b.head   # S3: the neck to the pivot (CS2: leaning), the nose
    hip_y = hip - 0.04
    ankle_y = hip_y - leg
    h = nose_y - ankle_y
    sx = 0.21 * b.shoulders * (0.5 + 0.5 * w)
    r = {"head_neck": (nose_y - shoulder_y) / h, "torso": (shoulder_y - hip_y) / h, "shoulders": 2 * sx / h, "hips": 0.2 * w * b.hips / h,
         "leg": leg / h, "arm": arm / h, "palm": PALM_PER_LEG * leg * b.hands / h,
         "head_w": 0.19 * b.head / h,                               # ear to ear (builders.ts: the ear markers at ±0.095·head)
         "elbow_at": b.elbow, "knee_at": b.knee}                    # the joints' places along their limbs (S6)
    if TOES_PER_LEG:
        r["toes"] = TOES_PER_LEG * leg * b.feet / h
    return r


def reference_ratios(person: dict) -> dict[str, float]:
    """The same measures from one SDPose person (OpenPose-18 `pose_keypoints_2d`: 0 nose, 1 neck, 2/5 shoulders, 3/6 elbows, 4/7 wrists,
    8/11 hips, 9/12 knees, 10/13 ankles; the 21-point hands, 0 the wrist and 9 the middle finger's base). Only the measures whose points were
    found; raises ValueError when the figure is not whole (no nose, neck, hips or ankles)."""
    import numpy as np
    b = np.array(person.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
    if len(b) < 14 or (b[[0, 1, 8, 11, 10, 13], 2] < 0.3).any():
        raise ValueError("the reference does not show the whole figure (nose, neck, hips and ankles)")
    ok = lambda *i: all(b[k, 2] >= 0.3 for k in i)  # noqa: E731
    d = lambda i, j: float(np.linalg.norm(b[i, :2] - b[j, :2]))  # noqa: E731
    ank = (b[10, :2] + b[13, :2]) / 2
    hip = (b[8, :2] + b[11, :2]) / 2
    h = float(np.linalg.norm(b[0, :2] - ank))
    if h <= 1:
        raise ValueError("the reference's figure is too small to measure")
    r = {"head_neck": d(0, 1) / h, "torso": float(np.linalg.norm(b[1, :2] - hip)) / h, "hips": d(8, 11) / h,
         "leg": (d(8, 9) + d(9, 10) + d(11, 12) + d(12, 13)) / 2 / h}
    if ok(2, 5):
        r["shoulders"] = d(2, 5) / h
    arms = [d(s, e) + d(e, wr) for s, e, wr in ((2, 3, 4), (5, 6, 7)) if ok(s, e, wr)]
    if arms:
        r["arm"] = sum(arms) / len(arms) / h
    palms = []
    for key in ("hand_left_keypoints_2d", "hand_right_keypoints_2d"):
        q = np.array(person.get(key) or [], float).reshape(-1, 3)
        if len(q) >= 10 and q[0, 2] >= 0.3 and q[9, 2] >= 0.3:
            palms.append(float(np.linalg.norm(q[0, :2] - q[9, :2])))
    if palms:
        r["palm"] = float(np.median(palms)) / h
    if ok(16, 17):
        r["head_w"] = d(16, 17) / h                                  # ear to ear: the head's size
    elbows = [d(s, e) / (d(s, e) + d(e, wr)) for s, e, wr in ((2, 3, 4), (5, 6, 7)) if ok(s, e, wr) and d(s, e) + d(e, wr) > 1]
    if elbows:
        r["elbow_at"] = float(np.mean(elbows))                     # S6: the elbow's place along the arm
    knees = [d(hp, k) / (d(hp, k) + d(k, a)) for hp, k, a in ((8, 9, 10), (11, 12, 13)) if ok(hp, k, a) and d(hp, k) + d(k, a) > 1]
    if knees:
        r["knee_at"] = float(np.mean(knees))                       # S6: the knee's place along the leg
    f = np.array(person.get("foot_keypoints_2d") or [], float).reshape(-1, 3)
    if len(f) >= 6:                                                # S5: COCO-WholeBody's feet — big toe, small toe, heel; left then right
        toes = [float(np.linalg.norm(f[i, :2] - f[i + 1, :2])) for i in (0, 3) if f[i, 2] >= 0.3 and f[i + 1, 2] >= 0.3]
        if toes:
            r["toes"] = float(np.median(toes)) / h
    return r


ARMS_CLOSE = 0.10            # S8: a wrist nearer a hip than this share of the height (across the picture): the arms touch the body


def stance_note(person: dict) -> str | None:
    """S8: what the reference's stance gets wrong for a fit and a test — "arms_close" when a wrist sits within ARMS_CLOSE of the height of
    its hip, across the picture (A1's Mara 0.088, Ines 0.080: arms down, hands on the coat; an A-pose's are ≈ 0.15–0.2 out). None = fine."""
    import numpy as np
    b = np.array(person.get("pose_keypoints_2d") or [], float).reshape(-1, 3)
    if len(b) < 14:
        return None
    h = float(np.linalg.norm(b[0, :2] - (b[10, :2] + b[13, :2]) / 2))
    gaps = [abs(b[w, 0] - b[hp, 0]) / h for w, hp in ((4, 8), (7, 11)) if b[w, 2] >= 0.3 and b[hp, 2] >= 0.3 and h > 1]
    return "arms_close" if gaps and min(gaps) < ARMS_CLOSE else None


def person_of(points: dict[str, Any]) -> dict[str, Any]:
    """CS2: points as the version keeps them (body_points) back into an SDPose person — the skeleton bench's corrected points refitted."""
    flat = lambda rows: [float(v) for r in (rows or []) for v in (list(r) + [1.0, 1.0, 1.0])[:3]]  # noqa: E731
    return {"pose_keypoints_2d": flat(points.get("pose")), "hand_left_keypoints_2d": flat(points.get("hand_left")),
            "hand_right_keypoints_2d": flat(points.get("hand_right")), "foot_keypoints_2d": flat(points.get("feet"))}


def body_points(person: dict, canvas: list | tuple | None) -> dict[str, Any]:
    """CS1: the points a body was fitted to, as the version keeps them (S4's stance, CS2's bench): the body's 18, both hands' 21, the feet's
    6, each [x, y, confidence], and the picture's size."""
    def rows(key: str) -> list[list[float]]:
        flat = [float(v) for v in (person.get(key) or [])]
        return [[round(flat[i], 2), round(flat[i + 1], 2), round(flat[i + 2], 3)] for i in range(0, len(flat) - 2, 3)]
    return {"canvas": list(canvas or []), "pose": rows("pose_keypoints_2d"), "hand_left": rows("hand_left_keypoints_2d"),
            "hand_right": rows("hand_right_keypoints_2d"), "feet": rows("foot_keypoints_2d")}


def fit_body(measured: dict[str, float], body: Body | None = None, locks: tuple[str, ...] | list[str] = ()) -> tuple[Body, dict[str, dict[str, float]]]:
    """The body whose dummy shows the reference's proportions: head (from the ears), neck, torso, shoulders, hips, legs, arms, the elbows'
    and knees' places, hands and feet moved (within the field bounds) until the dummy's ratios meet the measured ones; the height, build,
    figure, rest hand and attachments stay the author's, and so does every factor in `locks` (the skeleton bench's, CS2).
    The factors are relative to a dummy that is scaled to the height afterwards, so their overall size is loosely determined (only the
    fixed offsets of builders.ts move the ratios): S7's pull — each factor drawn toward its adult value with a small weight — holds that
    direction near an adult instead of letting it run to a bound (E23b's Mara, fitted without an anchor, ran to the bounds with every ratio
    met), and keeps a loosely read length human unless the picture insists.
    Returns the body and, per measure, the reference's value against the fitted dummy's."""
    import numpy as np
    b = (body or Body()).model_copy()
    needs = {"head": "head_w", "hands": "palm", "elbow": "elbow_at", "knee": "knee_at", "feet": "toes"}
    keys = ("head", "neck", "torso", "shoulders", "hips", "legs", "arms", "elbow", "knee", "hands", "feet")
    lim = {k: (Body.model_fields[k].metadata[0].ge, Body.model_fields[k].metadata[1].le) for k in keys}
    unknown = [k for k in keys if k not in locks and (k not in needs or needs[k] in measured) and (k != "feet" or TOES_PER_LEG)]
    meas = [k for k in FITTED if k in measured and k in dummy_ratios(b)]
    home = np.log([DEFAULTS.get(k, 1.0) for k in unknown])

    def at(x: np.ndarray) -> Body:
        return b.model_copy(update={k: float(np.clip(np.exp(v), *lim[k])) for k, v in zip(unknown, x)})

    def resid(x: np.ndarray) -> np.ndarray:
        d = dummy_ratios(at(x))
        return np.concatenate([[np.log(d[k] / measured[k]) for k in meas], PULL * (x - home)])

    # Levenberg–Marquardt in log factors: damped, each step at most 0.2 (≈ 22 %), held inside the bounds
    x = np.log([getattr(b, k) for k in unknown])
    lam = 1e-3
    for _ in range(300):
        r = resid(x)
        jac = np.stack([(resid(x + e) - r) / 1e-6 for e in np.eye(len(x)) * 1e-6], axis=1)
        step = np.linalg.solve(jac.T @ jac + lam * np.eye(len(x)), -jac.T @ r)
        step *= min(1.0, 0.2 / max(1e-12, float(np.abs(step).max())))
        nx = np.log([getattr(at(x + step), k) for k in unknown])
        if float(resid(nx) @ resid(nx)) < float(r @ r):
            x, lam = nx, max(1e-6, lam / 3)
        else:
            lam *= 4
        if float(np.abs(step).max()) < 1e-8 or lam > 1e6:
            break
    b = at(x)
    b = b.model_copy(update={k: round(getattr(b, k), 4 if k in DEFAULTS else 3) for k in unknown})
    d = dummy_ratios(b)
    report = {k: {"reference": round(measured[k], 4), "fitted": round(d[k], 4)} for k in meas}
    return b, report
