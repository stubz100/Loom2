"""Convert a ComfyUI workflow (UI format: nodes, links, positional widget values) into the API prompt format the engine queues, using the
running engine's /object_info as the schema. For spikes that start from ComfyUI's own workflow templates (E14 TRELLIS.2 / Pixal3D), so the
graph is the template's, not a hand transcription.

  from ui_to_api import convert
  api = convert(template_dict, object_info, drop={"PreviewImage", ...})

Widget values are positional in the UI format, in /object_info's input order (required, then optional), with a "control after generate"
value after a seed. A V3 dynamic combo (`COMFY_DYNAMICCOMBO_V3`) takes its key, then the chosen option's own widgets, which the API
names `<combo>.<input>` (the way core DA3Render takes `output.normalization`). A widget the template predates (a node grew an input
since) takes the schema default; a required input that is neither linked nor valued is an error here, not a silently dropped output
node at the engine (ComfyUI runs a prompt whose other outputs validate and reports the bad one only in `node_errors`).
"""
from __future__ import annotations

from typing import Any

UI_ONLY = {"PreviewImage", "MaskPreview", "Note", "MarkdownNote", "Preview3D", "Preview3DAdvanced", "PreviewAny"}
WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COLOR", "LOAD_3D", "COMFY_DYNAMICCOMBO_V3"}
SEED_CONTROLS = ("fixed", "increment", "decrement", "randomize")


def _type(spec: Any) -> Any:
    return spec[0] if isinstance(spec, (list, tuple)) and spec else spec


def _opts(spec: Any) -> dict:
    return spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 and isinstance(spec[1], dict) else {}


def _is_widget(spec: Any) -> bool:
    t = _type(spec)
    return isinstance(t, list) or t in WIDGET_TYPES


def _inputs(info: dict) -> list[tuple[str, Any, bool]]:
    """(name, spec, required) in the order the frontend serialises widget values."""
    return [(name, spec, group == "required") for group in ("required", "optional") for name, spec in (info.get("input", {}).get(group) or {}).items()]


def _take(values: list, k: int, prefix: str, name: str, spec: Any, inputs: dict[str, Any]) -> int:
    """Consume the widget value(s) of one input from values[k:] into inputs; returns the next index."""
    opts = _opts(spec)
    if k >= len(values):
        if "default" in opts:
            inputs[prefix + name] = opts["default"]
        return k
    val = values[k]
    k += 1
    inputs[prefix + name] = val
    if opts.get("control_after_generate") or name in ("seed", "noise_seed") and k < len(values) and values[k] in SEED_CONTROLS:
        k += 1                                                           # the frontend's "control after generate" value follows a seed
    if _type(spec) == "COMFY_DYNAMICCOMBO_V3":
        option = next((o for o in opts.get("options", []) if o.get("key") == val), None)
        for group in ("required", "optional"):
            for sub, sub_spec in (((option or {}).get("inputs") or {}).get(group) or {}).items():
                if _is_widget(sub_spec):
                    k = _take(values, k, f"{prefix}{name}.", sub, sub_spec, inputs)
    return k


def convert(wf: dict, object_info: dict, drop: set[str] | None = None) -> dict:
    drop = UI_ONLY | (drop or set())
    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}                                # [id, from_node, from_slot, to_node, to_slot, type]

    def source(link_id: int) -> list | None:
        """The upstream [node_id, slot] of a link, through frontend-only Reroute nodes."""
        l = links.get(link_id)
        while l is not None:
            src = nodes.get(l[1])
            if src is None:
                return None
            if src["type"] == "Reroute":
                inp = (src.get("inputs") or [{}])[0].get("link")
                l = links.get(inp) if inp is not None else None
                continue
            return [str(l[1]), l[2]]
        return None

    feeds = {l[1] for l in wf["links"]}                                 # nodes something reads from (a preview may pass its input through)
    api: dict[str, dict] = {}
    for nid, n in nodes.items():
        t = n["type"]
        if (t in drop and nid not in feeds) or t == "Reroute" or n.get("mode") in (2, 4):   # 2 = muted, 4 = bypassed
            continue
        info = object_info.get(t)
        if info is None:
            raise KeyError(f"node {nid}: class {t} is not in the engine's object_info")
        inputs: dict[str, Any] = {}
        values = list(n.get("widgets_values") or []) if isinstance(n.get("widgets_values"), list) else []
        k = 0
        for name, spec, _ in _inputs(info):
            if _is_widget(spec):
                k = _take(values, k, "", name, spec, inputs)
        for i in n.get("inputs") or []:
            if i.get("link") is not None:
                s = source(i["link"])
                if s is not None:
                    inputs[i["name"]] = s
        missing = [name for name, spec, required in _inputs(info) if required and name not in inputs]
        if missing:
            raise KeyError(f"node {nid} ({t}): required inputs {missing} are neither linked nor valued (widgets_values {values})")
        api[str(nid)] = {"class_type": t, "inputs": inputs}
    # inputs that point at a dropped node are dropped too (previews feeding nothing else)
    for v in api.values():
        for name, val in list(v["inputs"].items()):
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] not in api:
                del v["inputs"][name]
    return api
