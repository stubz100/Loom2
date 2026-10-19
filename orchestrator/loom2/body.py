"""CA0 (D94, proto01_animate 01 §9): a character's body — on its Cast version's sheet (story.ProfileVersion.body) and copied onto the Stage
figure bound to that version (stages.StageObject.body), where it shapes the dummy: height, build, proportions, rigid attachments."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BodyBuild = Literal["slim", "average", "broad", "heavy"]
AttachmentKind = Literal["tail", "horns", "ears", "wings", "antennae", "hat", "backpack", "other"]
BodyJoint = Literal["root", "spine", "head", "r_shoulder", "l_shoulder", "r_elbow", "l_elbow"]


class BodyAttachment(BaseModel):
    """CA0 (01 §9b N1): a rigid part that follows a joint of the figure — a tail, horns, folded wings. Shown on the Stage dummy and in its
    clay and depth passes; not in the pose pass (Wan Animate guesses its motion from the reference)."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    kind: AttachmentKind
    joint: BodyJoint | None = None                # None = the kind's own place (horns, ears, antennae, hat → head; wings, backpack → spine; tail → root)
    size: float = Field(1.0, ge=0.2, le=3.0)
    note: str = Field("", max_length=80)


class Body(BaseModel):
    """CA0 (D94, 01 §9 answer 3): the body on the Cast sheet — it shapes the figure's Stage dummy when the figure is bound to this version.
    Height in metres; the proportions are factors of the default dummy (1 = the 1.75 m adult); the build widens or narrows it."""
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    height_m: float = Field(1.75, ge=0.3, le=4.0)
    build: BodyBuild = "average"
    head: float = Field(1.0, ge=0.5, le=2.5)
    torso: float = Field(1.0, ge=0.6, le=1.6)
    shoulders: float = Field(1.0, ge=0.6, le=1.8)
    arms: float = Field(1.0, ge=0.6, le=1.6)
    legs: float = Field(1.0, ge=0.5, le=1.6)
    neck: float = Field(1.0, ge=0.5, le=3.0)       # CA1b (D104): the neck's length (the head above the shoulders); fitted from the reference
    hands: float = Field(1.0, ge=0.5, le=1.6)      # CA1b: the Detailed figure's hands (the pose pass draws them, D101)
    feet: float = Field(1.0, ge=0.5, le=1.6)       # CA1b: the feet (the dummy's and the Detailed figure's)
    attachments: list[BodyAttachment] = Field(default_factory=list, max_length=6)


# ---- CA1b (D104): the body fitted to the character's animation reference -------------------------------------------------------------
BUILD_WIDTH = {"slim": 0.85, "average": 1.0, "broad": 1.15, "heavy": 1.3}      # frontend stage/body.ts
PALM_PER_LEG = 0.149          # the Detailed figure's palm (wrist → the middle finger's base) per leg length, measured on Stage (journal 2026-10-19)
A_POSE_DEG = 22.0             # the reference's stance (frontend stage/turnTest.ts A_POSE): arms 22° away from the body
FITTED = ("head_w", "head_neck", "torso", "shoulders", "hips", "leg", "arm", "palm")


def dummy_ratios(b: Body) -> dict[str, float]:
    """The Stage dummy (frontend builders.ts `mannequin`) seen from the front in the A-pose, as SDPose would read it: each measure a fraction
    of the height from the nose to the ankles. Kept in step with builders.ts by tests/test_body_fit_ca1b.py's numbers."""
    import math
    w = BUILD_WIDTH.get(b.build, 1.0)
    hip = 0.07 + 0.88 * b.legs
    thigh, shin, upper, fore = 0.44 * b.legs, 0.43 * b.legs, 0.29 * b.arms, 0.27 * b.arms
    spine = hip + 0.06
    shoulder_y = spine + 0.4 * b.torso                        # the shoulders' midpoint = OpenPose's neck point (CA1b)
    nose_y = spine + 0.44 * b.torso + 0.06 * b.neck + 0.08 * b.head
    hip_y = hip - 0.04
    ankle_y = hip_y - thigh - shin
    h = nose_y - ankle_y
    sx = 0.21 * b.shoulders * (0.5 + 0.5 * w)
    arm = (upper + fore) * (math.cos(math.radians(A_POSE_DEG)) ** 2 + math.sin(math.radians(A_POSE_DEG)) ** 2) ** 0.5
    return {"head_neck": (nose_y - shoulder_y) / h, "torso": (shoulder_y - hip_y) / h, "shoulders": 2 * sx / h, "hips": 0.2 * w / h,
            "leg": (thigh + shin) / h, "arm": arm / h, "palm": PALM_PER_LEG * (thigh + shin) * b.hands / h,
            "head_w": 0.19 * b.head / h}                              # ear to ear (builders.ts: the ear markers at ±0.095·head)


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
        r["head_w"] = d(16, 17) / h                                  # ear to ear: the head's size, which anchors the fit's scale
    return r


def fit_body(measured: dict[str, float], body: Body | None = None) -> tuple[Body, dict[str, dict[str, float]]]:
    """The body whose dummy shows the reference's proportions: head (from the ears), neck, torso, shoulders, legs, arms and hands moved
    (within the field bounds) until the dummy's ratios meet the measured ones; the height, build, feet and attachments stay the author's.
    The factors are relative to a dummy that is scaled to the height afterwards, so their overall size is nearly free (only the fixed
    offsets of builders.ts move the ratios): the hips' width, which no factor scales, anchors it (E23b's Mara, fitted without it, ran to
    the bounds with every ratio met).
    Returns the body and, per measure, the reference's value against the fitted dummy's."""
    import numpy as np
    b = (body or Body()).model_copy()
    keys = ("head", "neck", "torso", "shoulders", "legs", "arms", "hands")
    lim = {k: (Body.model_fields[k].metadata[0].ge, Body.model_fields[k].metadata[1].le) for k in keys}
    meas = [k for k in FITTED if k in measured]
    unknown = [k for k in keys if (k != "head" or "head_w" in measured) and (k != "hands" or "palm" in measured)]

    def at(x: np.ndarray) -> Body:
        return b.model_copy(update={k: float(np.clip(np.exp(v), *lim[k])) for k, v in zip(unknown, x)})

    def resid(x: np.ndarray) -> np.ndarray:
        d = dummy_ratios(at(x))
        return np.array([np.log(d[k] / measured[k]) for k in meas])

    # Levenberg–Marquardt in log factors: damped, each step at most 0.2 (≈ 22 %), held inside the bounds; the damping keeps a loosely
    # determined direction (no ears: the scale) near where it started instead of running to a bound
    x = np.log([getattr(b, k) for k in unknown])
    lam = 1e-3
    for _ in range(200):
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
    b = b.model_copy(update={k: round(getattr(b, k), 3) for k in unknown})
    d = dummy_ratios(b)
    report = {k: {"reference": round(measured[k], 4), "fitted": round(d[k], 4)} for k in FITTED if k in measured}
    return b, report
