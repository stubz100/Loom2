"""proto01_UIcast CW4 (03 §4): a prop's height in metres, read from its words — image → 3D models come out at unit size, so a cup and a
wardrobe stood alike. The prop version's height is prefilled from its name and sheet with this short table of common things (the first
word found, the longest names first), else 1 m; the author edits it."""
from __future__ import annotations

import re

DEFAULT_PROP_HEIGHT_M = 1.0

# metres, about: a thing standing (or lying) as it usually does
COMMON_HEIGHTS: dict[str, float] = {
    "wine glass": 0.2, "coffee cup": 0.1, "teacup": 0.08, "cup": 0.1, "mug": 0.1, "glass": 0.12, "bottle": 0.3, "can": 0.12, "jar": 0.15,
    "plate": 0.03, "bowl": 0.08, "teapot": 0.2, "kettle": 0.25, "vase": 0.35, "candle": 0.2, "lantern": 0.35, "lamp": 0.5, "floor lamp": 1.6,
    "phone": 0.15, "smartphone": 0.15, "book": 0.25, "notebook": 0.22, "letter": 0.25, "newspaper": 0.4, "camera": 0.1, "laptop": 0.25,
    "radio": 0.25, "clock": 0.3, "grandfather clock": 2.0, "key": 0.07, "coin": 0.03, "pistol": 0.18, "gun": 0.2, "rifle": 1.1,
    "sword": 1.0, "dagger": 0.3, "knife": 0.25, "axe": 0.8, "hammer": 0.3, "shovel": 1.2, "broom": 1.4, "rake": 1.6, "spear": 2.0,
    "staff": 1.6, "cane": 0.9, "walking stick": 0.9, "umbrella": 0.9, "bag": 0.4, "handbag": 0.3, "backpack": 0.5, "suitcase": 0.7,
    "basket": 0.4, "box": 0.4, "crate": 0.6, "barrel": 0.9, "bucket": 0.35, "chest": 0.5, "trunk": 0.6, "sack": 0.7, "flower pot": 0.3,
    "pot": 0.3, "plant": 0.6, "potted plant": 0.6, "bush": 1.2, "tree": 5.0, "rock": 0.6, "boulder": 1.5, "fence": 1.2, "gate": 1.8,
    "door": 2.1, "window": 1.4, "ladder": 2.5, "chair": 0.9, "armchair": 1.0, "stool": 0.65, "bench": 0.85, "table": 0.75,
    "desk": 0.75, "coffee table": 0.45, "bed": 0.6, "sofa": 0.85, "couch": 0.85, "wardrobe": 2.0, "cupboard": 1.8, "bookshelf": 1.9,
    "shelf": 1.8, "dresser": 1.1, "cabinet": 1.2, "fridge": 1.8, "refrigerator": 1.8, "stove": 0.9, "oven": 0.9, "sink": 0.9,
    "bathtub": 0.6, "mirror": 1.2, "television": 0.6, "tv": 0.6, "piano": 1.3, "guitar": 1.0, "violin": 0.6, "drum": 0.5,
    "bicycle": 1.05, "bike": 1.05, "motorcycle": 1.2, "scooter": 1.1, "car": 1.5, "van": 2.0, "truck": 3.0, "bus": 3.0, "boat": 1.5,
    "rowboat": 0.7, "cart": 1.0, "wheelbarrow": 0.7, "pram": 1.0, "statue": 2.0, "sign": 2.2, "signpost": 2.4, "street lamp": 4.5,
    "lamppost": 4.5, "mailbox": 1.2, "postbox": 1.4, "bin": 1.0, "trash can": 1.0, "hydrant": 0.8, "bollard": 1.0, "cone": 0.7,
    "tent": 1.5, "flag": 2.0, "trophy": 0.4, "crown": 0.15, "hat": 0.15, "helmet": 0.3, "shoe": 0.12, "boot": 0.3, "doll": 0.4,
    "teddy bear": 0.4, "ball": 0.22, "globe": 0.45, "telescope": 1.4, "microphone": 0.2, "skull": 0.2, "egg": 0.06, "apple": 0.08,
}
_KEYS = sorted(COMMON_HEIGHTS, key=len, reverse=True)


def prop_height(*words: str | None) -> float:
    """A prop's likely height from its words (name, appearance): the first common thing named, longest names first; else 1 m."""
    text = " " + re.sub(r"[^a-z ]+", " ", " ".join(w or "" for w in words).lower()) + " "
    for k in _KEYS:
        if re.search(rf"\b{re.escape(k)}s?\b", text):
            return COMMON_HEIGHTS[k]
    return DEFAULT_PROP_HEIGHT_M
