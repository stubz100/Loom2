"""D90 (02 §6.3): the preset swatch pack — one small generated image per *look* preset (Generate's prompt-field presets and the user's
snippets), made locally once as a staged t2i job on the spec named `default_for = ["swatch"]` (an open-licence model, so both variants
make it), kept in **app state**, not in the project, and re-made per item.

    <state>/preset_icons/index.json      {schema_version, items: {key: PresetIcon}}  — the record of what each file shows
    <state>/preset_icons/<key>.webp      the swatch, ICON_PX on its long side

`icon_key(field, value)` is the first 16 hex digits of sha1(field + "\\n" + value) over UTF-8, both exactly as given (no trimming, no
case folding); every reply carries the key, so a client need not compute it. The job that makes a swatch is an ordinary Generate job:
its result stays in the Catalogue with its lineage (`origin.surface == "swatch"`), and `engine.finishers.AssetFinisher` copies a
downscaled version here (`store_from`).
"""
from __future__ import annotations

import hashlib
import io
import re
import threading
import time
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, ConfigDict

from .config import SWATCH_PROMPTS
from .fsio import StateError, atomic_write_bytes, atomic_write_json, read_json_or, utc_now
from .models import registry

PRESET_ICONS_SCHEMA_VERSION = 1
ICON_PX = 256                                   # the stored swatch's long side (the tiles draw at ≈ 40–64 px, 2× dpr and a hover loupe)
SWATCH_PX = 512                                 # the job's square size: the smallest that still reads as a look on Klein 4B
SWATCH_SEED = 90                                # a pack reads as a set when its swatches share a seed; 0 asks the queue for a random one
KEY_RE = re.compile(r"^[0-9a-f]{16}$")
SURFACE = "swatch"                              # JobOrigin.surface of a swatch job (the finisher's hook)
EVENT = "preset_icons.changed"

# The scene each field's value is shown on — the defaults live in config (Settings › Samples, D90); `{value}` is the preset.
PROMPTS = SWATCH_PROMPTS
_lock = threading.Lock()                        # the finisher (a worker thread) and the routes both write the index


class PresetIcon(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    key: str
    field: str
    value: str
    updated_at: str
    model_id: str | None = None                 # lineage at write time: the model, seed and the Catalogue asset it came from
    seed: int | None = None
    asset_id: str | None = None


class PresetIconList(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    items: list[PresetIcon]


def icon_key(field: str, value: str) -> str:
    return hashlib.sha1(f"{field}\n{value}".encode("utf-8")).hexdigest()[:16]


def swatch_prompt(field: str, value: str, prompts: dict[str, str] | None = None) -> str:
    return (prompts or PROMPTS).get(field, "{value}").replace("{value}", value)


def swatch_recipe(field: str, value: str, variant: str | None, seed: int = SWATCH_SEED, prompts: dict[str, str] | None = None) -> dict:
    """One square Draft t2i on the variant's swatch model (D65: the spec says which), its own sampling preset otherwise."""
    return {"kind": "t2i", "model_id": registry.default_model("swatch", variant), "prompt_mode": "text", "prompt_text": swatch_prompt(field, value, prompts),
            "width": SWATCH_PX, "height": SWATCH_PX, "seeds": [seed]}


class PresetIconStore:
    def __init__(self, state_dir: Path) -> None:
        self.dir = Path(state_dir) / "preset_icons"
        self.index_path = self.dir / "index.json"

    def path(self, key: str) -> Path:
        if not KEY_RE.match(key):
            raise KeyError(key)
        return self.dir / f"{key}.webp"

    def _read(self) -> dict[str, dict]:
        try:
            data = read_json_or(self.index_path, {"schema_version": PRESET_ICONS_SCHEMA_VERSION, "items": {}})
        except StateError:                                          # a torn index is moved aside, never trusted (files are truth)
            self.index_path.replace(self.index_path.with_name(f"index.json.corrupt-{time.strftime('%Y%m%d-%H%M%S')}"))
            return {}
        if not isinstance(data, dict) or int(data.get("schema_version", 0)) > PRESET_ICONS_SCHEMA_VERSION:
            raise StateError("the preset icon index was written by a newer loom2")
        items = data.get("items") or {}
        return {k: v for k, v in items.items() if isinstance(v, dict) and KEY_RE.match(k)}

    def _write(self, items: dict[str, dict]) -> None:
        atomic_write_json(self.index_path, {"schema_version": PRESET_ICONS_SCHEMA_VERSION, "items": items})

    def list(self) -> list[PresetIcon]:
        """The index's items whose file exists, by field and value."""
        with _lock:
            items = self._read()
        out = []
        for k, v in items.items():
            try:
                rec = PresetIcon.model_validate(v)
            except ValueError:                                      # a hand-edited entry: skipped, the swatch can be made again
                continue
            if rec.key == k and (self.dir / f"{k}.webp").is_file():
                out.append(rec)
        return sorted(out, key=lambda i: (i.field, i.value.lower()))

    def store_from(self, field: str, value: str, src: Path, model_id: str | None = None, seed: int | None = None,
                   asset_id: str | None = None) -> PresetIcon:
        """The finisher's half: `src` (the job's result) → a ≤ ICON_PX webp under the key, then the index — the file first, so an
        index entry never names a missing swatch."""
        key = icon_key(field, value)
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((ICON_PX, ICON_PX), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=85, method=4)
        rec = PresetIcon(key=key, field=field, value=value, updated_at=utc_now(), model_id=model_id, seed=seed, asset_id=asset_id)
        with _lock:
            atomic_write_bytes(self.path(key), buf.getvalue())
            items = self._read()
            items[key] = rec.model_dump()
            self._write(items)
        return rec

    def delete(self, key: str) -> bool:
        p = self.path(key)
        with _lock:
            items = self._read()
            found = items.pop(key, None) is not None or p.is_file()
            if found:
                self._write(items)                      # the index first: a leftover file without an entry is not listed
                p.unlink(missing_ok=True)
        return found
