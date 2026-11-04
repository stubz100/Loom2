"""C6 (D181, propo02 04 §4.7; 05 Q12, Q13): the Bin's kinds — a closed vocabulary.

A thing in the Bin is told apart by what made it: the lineage kind its job stamped (`AssetRecord.lineage_kind`, one of LINEAGE_KINDS — a job
cannot land outside it, `Catalogue.ingest_file` refuses a stranger), else its asset kind read in the class of the home it is in (a picture in
a shot's home is a still, a video there a take). Each maps to a **shelf**: the third level of every home in the tree, a node with a count,
and the chip that filters a home's grid. The roles World gives a thing (hero, reference, A-pose …) stay its badges; the shelves are what the
index can count without a record read (B0). Working files (Q13: masks, depth, coverage) are a shelf shown always, never hidden.
"""
from __future__ import annotations

from typing import Literal

LINEAGE_KINDS: tuple[str, ...] = (
    "stage-pass", "clay-view", "plate-key",                                   # the passes a camera renders (depth, pose, masks; a clay view; a plate's key)
    "frame-extract", "stage-shot", "reangle",                                 # a frame harvested from a clip; a still from the stage's passes; a new angle of a picture
    "render", "final", "animatic",                                            # a final's render, its assembly; Record's animatic
    "shell", "animation-thumb", "image-to-mesh",                              # a character's shell, a pose's thumbnail, a prop's model
    "image-to-set", "set-fill", "set-bake", "set-coverage", "set-thing", "set-thing-cutout", "place-thing", "clean-plate",   # a place's set
    "set-crowd", "set-walkers",                                               # a place's life
    "voice-clone",                                                            # a character's cloned voice (CN2)
)
LineageKind = Literal["stage-pass", "clay-view", "plate-key", "frame-extract", "stage-shot", "reangle", "render", "final", "animatic", "shell", "animation-thumb", "image-to-mesh",
                      "image-to-set", "set-fill", "set-bake", "set-coverage", "set-thing", "set-thing-cutout", "place-thing", "clean-plate", "set-crowd", "set-walkers", "voice-clone"]

SHELF_OF_LINEAGE: dict[str, str] = {
    "stage-pass": "passes", "clay-view": "passes", "plate-key": "passes",
    "frame-extract": "stills", "stage-shot": "stills", "reangle": "pictures",
    "render": "composition", "final": "final", "animatic": "animatic",
    "shell": "body", "animation-thumb": "poses", "image-to-mesh": "model",
    "image-to-set": "set", "set-fill": "set", "set-bake": "set", "set-coverage": "set", "set-thing": "set", "set-thing-cutout": "set", "place-thing": "set", "clean-plate": "set",
    "set-crowd": "life", "set-walkers": "life",
    "voice-clone": "voice",
}
assert set(SHELF_OF_LINEAGE) == set(LINEAGE_KINDS)

HomeClass = Literal["character", "prop", "place", "look", "sketches", "clay", "shot", "episode", "imports", "other"]

# a thing with no lineage kind: its asset kind, read in the home's class
_BY_KIND: dict[str, dict[str, str]] = {
    "image": {"shot": "stills", "*": "pictures"},
    "document-render": {"*": "pictures"},
    "mask": {"*": "working"},
    "video": {"shot": "takes", "episode": "movies", "character": "body", "*": "clips"},
    "audio": {"character": "voice", "*": "sounds"},
    "mesh": {"*": "model"},
}

SHELF_LABEL: dict[str, str] = {
    "pictures": "pictures", "body": "body", "poses": "poses", "voice": "voice", "model": "model", "set": "set", "life": "life",
    "animatic": "animatic", "stills": "stills", "passes": "passes", "takes": "takes", "composition": "composition", "final": "final",
    "clips": "clips", "movies": "movies", "sounds": "sounds", "working": "working files",
}
SHELF_ORDER: tuple[str, ...] = ("pictures", "body", "poses", "voice", "model", "set", "life", "animatic", "stills", "passes", "takes", "composition", "final",
                                "clips", "movies", "sounds", "working")
assert set(SHELF_ORDER) == set(SHELF_LABEL) >= set(SHELF_OF_LINEAGE.values())


def home_class(path: str) -> HomeClass:
    """The class of a home from its path: world/character/<id>/<v> → character, shots/<id>/<v> → shot, episode/<id> → episode …"""
    parts = (path or "").split("/")
    if parts[0] == "world":
        if len(parts) == 1:
            return "other"
        return {"character": "character", "prop": "prop", "place": "place", "look": "look", "sketches": "sketches"}.get(parts[1], "other")   # type: ignore[return-value]
    return {"shots": "shot", "episode": "episode", "imports": "imports", "clay": "clay"}.get(parts[0], "other")   # type: ignore[return-value]


def shelf_of(lineage_kind: str | None, asset_kind: str, cls: str) -> str:
    """The shelf a thing sits on: its lineage kind's, else its asset kind's in this class of home."""
    if lineage_kind and lineage_kind in SHELF_OF_LINEAGE:
        return SHELF_OF_LINEAGE[lineage_kind]
    by = _BY_KIND.get(asset_kind) or {"*": "pictures"}
    return by.get(cls, by["*"])


def shelf_sql(shelf: str, cls: str) -> tuple[str, list[str]]:
    """The SQL that picks a shelf's things in a home of this class (the index's `kind` and `lineage_kind` columns): the lineage kinds that
    map to it, or the asset kinds whose default in this class is it with no lineage kind. (fragment, args); a shelf nothing maps to picks
    nothing."""
    lineages = [k for k, s in SHELF_OF_LINEAGE.items() if s == shelf]
    kinds = [k for k, by in _BY_KIND.items() if by.get(cls, by["*"]) == shelf]
    parts, args = [], []
    if lineages:
        parts.append(f"lineage_kind IN ({','.join('?' * len(lineages))})"); args.extend(lineages)
    if kinds:
        parts.append(f"(lineage_kind IS NULL AND kind IN ({','.join('?' * len(kinds))}))"); args.extend(kinds)
    if not parts:
        return "0", []
    return "(" + " OR ".join(parts) + ")", args


def shelves(counts: dict[tuple[str | None, str], int], cls: str) -> list[dict[str, object]]:
    """The shelves of a home with their counts, in the Bin's order, from (lineage_kind, asset_kind) → n."""
    out: dict[str, int] = {}
    for (lk, kind), n in counts.items():
        s = shelf_of(lk, kind, cls)
        out[s] = out.get(s, 0) + n
    return [{"id": s, "label": SHELF_LABEL[s], "count": out[s]} for s in SHELF_ORDER if out.get(s)]
