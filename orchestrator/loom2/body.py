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
