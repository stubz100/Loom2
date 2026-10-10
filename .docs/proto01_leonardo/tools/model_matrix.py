"""Regenerate the model tables in ../02-model-catalogue.md from the mirrored v2 OpenAPI definition.

Usage (after tools/mirror_docs.py):

    python -I .docs/proto01_leonardo/tools/model_matrix.py

Rewrites everything between the `<!-- matrix:start -->` and `<!-- matrix:end -->` markers; the prose around them is
hand-written and left alone. Standard library only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "source" / "openapi-v2-creategeneration.json"
DOC = ROOT / "02-model-catalogue.md"

AUDIO = {"music-v1", "sound-effects-v2", "dialogue-v3", "seed-audio-1.0"}
THREE_D = {"rodin-v2"}
UTILITY = {"aurora-upscaler-creative", "aurora-upscaler-precise", "remove-bg"}
# parameters every table already shows in its own column
SHOWN = {"prompt", "guidances", "width", "height", "duration", "quantity", "seed", "negative_prompt",
         "motion_has_audio", "audio", "prompt_enhance", "style_ids"}


def size(props: dict) -> str:
    w, h = props.get("width", {}), props.get("height", {})
    if not w:
        return "—"
    if "enum" in w:
        ws = [v for v in w["enum"] if v]
        hs = [v for v in h.get("enum", []) if v]
        if not ws:
            return "from input"
        return f"listed pairs, ≤ {max(ws)}×{max(hs)}"
    lo, hi = w.get("minimum"), w.get("maximum")
    if hi and hi > 100_000:
        hi = None
    return f"{lo or '?'}–{hi or '?'} px" if lo or hi else "free"


def enum_of(prop: dict) -> list:
    if "enum" in prop:
        return prop["enum"]
    vals = []
    for alt in prop.get("oneOf", []) + prop.get("anyOf", []):
        vals += alt.get("enum", [])
    return vals


def options(props: dict) -> str:
    parts = []
    for key, prop in props.items():
        if key in SHOWN or prop.get("deprecated"):
            continue
        values = enum_of(prop)
        parts.append(f"`{key}`" + (f" ({' / '.join(map(str, values))})" if values and len(values) <= 6 else ""))
    return ", ".join(parts) or "—"


def guidances(props: dict) -> str:
    g = props.get("guidances", {}).get("properties", {})
    return ", ".join(f"{k}×{v.get('maxItems', '?')}" for k, v in g.items() if v.get("maxItems", 1)) or "—"


def durations(props: dict) -> str:
    vals = enum_of(props.get("duration", {}))
    if not vals:
        return "—"
    return f"{min(vals)}–{max(vals)} s" if len(vals) > 3 else " / ".join(f"{v}" for v in vals) + " s"


def yes(props: dict, *keys: str) -> str:
    return "✓" if any(k in props for k in keys) else ""


def kind(model: str, props: dict) -> str:
    if model in AUDIO:
        return "audio"
    if model in THREE_D:
        return "3d"
    if model in UTILITY:
        return "utility"
    if "duration" in props or "start_frame" in props.get("guidances", {}).get("properties", {}):
        return "video"
    return "image"


HEADERS = {
    "image": ("Model id", "Title", "Size", "Max qty", "Seed", "Neg", "Enhance", "Styles", "Guidances (max items)", "Other parameters"),
    "video": ("Model id", "Title", "Size", "Duration", "Audio", "Seed", "Guidances (max items)", "Other parameters"),
    "utility": ("Model id", "Title", "Size", "Guidances (max items)", "Other parameters"),
    "audio": ("Model id", "Title", "Max qty", "Duration", "Guidances (max items)", "Other parameters"),
    "3d": ("Model id", "Title", "Guidances (max items)", "Other parameters"),
}
TITLES = {
    "image": "Image generation and reference editing",
    "video": "Video generation",
    "utility": "Upscale and background removal",
    "audio": "Audio",
    "3d": "3D",
}


def row(kind_: str, model: str, title: str, props: dict) -> list[str]:
    qty = str(props.get("quantity", {}).get("maximum", "—"))
    if kind_ == "image":
        return [f"`{model}`", title, size(props), qty, yes(props, "seed"), yes(props, "negative_prompt"),
                yes(props, "prompt_enhance"), yes(props, "style_ids"), guidances(props), options(props)]
    if kind_ == "video":
        return [f"`{model}`", title, size(props), durations(props), yes(props, "motion_has_audio", "audio", "audio_setting"),
                yes(props, "seed"), guidances(props), options(props)]
    if kind_ == "utility":
        return [f"`{model}`", title, size(props), guidances(props), options(props)]
    if kind_ == "audio":
        return [f"`{model}`", title, qty, durations(props), guidances(props), options(props)]
    return [f"`{model}`", title, guidances(props), options(props)]


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    post = spec["paths"]["/generations"]["post"]
    mapping = post["requestBody"]["content"]["application/json"]["schema"]["discriminator"]["mapping"]
    tables: dict[str, list[list[str]]] = {k: [] for k in HEADERS}
    for model, ref in mapping.items():
        schema = schemas[ref.rsplit("/", 1)[1]]
        props = schema["properties"]["parameters"].get("properties", {})
        k = kind(model, props)
        tables[k].append(row(k, model, schema.get("title", ""), props))
    out = [f"Generated from `source/openapi-v2-creategeneration.json` ({spec['info']['version']}, "
           f"{len(mapping)} models) by `tools/model_matrix.py`.", ""]
    for k, rows in tables.items():
        out += [f"### {TITLES[k]} ({len(rows)})", "", "| " + " | ".join(HEADERS[k]) + " |",
                "| " + " | ".join("---" for _ in HEADERS[k]) + " |"]
        out += ["| " + " | ".join(r) + " |" for r in rows]
        out.append("")
    text = DOC.read_text(encoding="utf-8")
    block = "<!-- matrix:start -->\n" + "\n".join(out) + "<!-- matrix:end -->"
    text = re.sub(r"<!-- matrix:start -->.*?<!-- matrix:end -->", lambda _: block, text, flags=re.S)
    DOC.write_text(text, encoding="utf-8")
    print(f"{DOC.name}: {', '.join(f'{k} {len(v)}' for k, v in tables.items())}")


if __name__ == "__main__":
    main()
