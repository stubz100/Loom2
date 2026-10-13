"""P18 (D84): freeze the ComfyUI template's Pixal3D branch as loom2's API graph fixture. Re-run when the engine pin (and with it the
template package) moves:

    engine/.venv/Scripts/python.exe scripts/make_mesh_graph.py [--capture engine/spikes/out/object_info_v0.39.0.json] [--out orchestrator/loom2/engine/pixal3d_graph.json]

What it does to the template (`3d_pixal3d_trellis2_image_to_model.json`, converted by `engine/spikes/ui_to_api.py` against the engine's
object_info): sets the method switch to Pixal3D and resolves every `ComfySwitchNode` with a constant switch to its chosen source, drops the
TRELLIS.2-only nodes and every preview (their consumers rewired to what the preview showed), blanks every loader's file name (the builder
fills them from the roster — D65: no model ids in code or fixtures) and records which node plays which role, keeps the rest as the
template has it. `graphs.build_mesh` then sets the image, the seeds, the resolution, the face count and the outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "engine" / "spikes"))
from ui_to_api import convert  # noqa: E402

TEMPLATE = REPO / "engine" / ".venv" / "Lib" / "site-packages" / "comfyui_workflow_templates_json" / "templates" / "3d_pixal3d_trellis2_image_to_model.json"
PREVIEWS = {"PreviewImage": "images", "MaskPreview": "mask", "PreviewAny": "source"}
LOADERS = {"UNETLoader": "unet_name", "VAELoader": "vae_name", "CLIPVisionLoader": "clip_name", "LoadMoGeModel": "model_name", "LoadBackgroundRemovalModel": "bg_removal_name"}


def is_link(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], int)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", default="engine/spikes/out/object_info_v0.39.0.json")
    ap.add_argument("--out", default="orchestrator/loom2/engine/pixal3d_graph.json")
    a = ap.parse_args()
    cap = json.loads((REPO / a.capture).read_text(encoding="utf-8"))
    oi = cap.get("object_info", cap)
    g = convert(json.loads(TEMPLATE.read_text(encoding="utf-8")), oi)
    # the method switch: Pixal3D
    for k, v in g.items():
        if v["class_type"] == "PrimitiveBoolean":
            v["inputs"]["value"] = False
    # resolve the switches whose condition is a constant (a literal or a PrimitiveBoolean)
    def const_of(x):
        if isinstance(x, bool):
            return x
        if is_link(x) and g.get(x[0], {}).get("class_type") == "PrimitiveBoolean":
            return bool(g[x[0]]["inputs"]["value"])
        return None
    rewire: dict[str, list] = {}                                           # "<id>" → the link that replaces output 0 of that node
    for k, v in g.items():
        if v["class_type"] == "ComfySwitchNode":
            c = const_of(v["inputs"]["switch"])
            if c is None:
                raise SystemExit(f"switch {k} is not constant")
            rewire[k] = v["inputs"]["on_true" if c else "on_false"]
        elif v["class_type"] in PREVIEWS:
            rewire[k] = v["inputs"][PREVIEWS[v["class_type"]]]
    def resolve(link):
        seen = 0
        while is_link(link) and link[0] in rewire and seen < 10:
            link = rewire[link[0]]; seen += 1
        return link
    for v in g.values():
        for name, val in list(v["inputs"].items()):
            if is_link(val):
                v["inputs"][name] = resolve(val)
    # keep what the output node reaches
    save = next(k for k, v in g.items() if v["class_type"] == "Save3DAdvanced")
    keep: list[str] = []
    stack = [save]
    while stack:
        k = stack.pop()
        if k in keep:
            continue
        keep.append(k)
        for val in g[k]["inputs"].values():
            if is_link(val) and val[0] in g:
                stack.append(val[0])
    g = {k: g[k] for k in sorted(keep, key=int)}
    roles: dict[str, str] = {}
    for k, v in g.items():
        ct = v["class_type"]
        if ct in LOADERS:
            name = v["inputs"][LOADERS[ct]]
            role = {"UNETLoader": "model", "CLIPVisionLoader": "dino", "LoadMoGeModel": "moge", "LoadBackgroundRemovalModel": "matte"}.get(ct)
            if ct == "VAELoader":
                role = "shape_vae" if "shape" in name else "texture_vae"
            roles[k] = role
            v["inputs"][LOADERS[ct]] = ""
        if ct == "LoadImage":
            roles[k] = "image"
            v["inputs"]["image"] = ""
        if ct == "DecimateMesh":
            roles[k] = "decimate"
            v["inputs"]["target_face_count"] = 50000
        if ct == "Trellis2UpsampleStage":
            roles[k] = "upsample"
            v["inputs"]["target_resolution"] = int(v["inputs"]["target_resolution"])      # the widget holds a string; the node wants INT
        if ct == "KSampler":
            roles.setdefault(k, "sampler")
        if ct == "Save3DAdvanced":
            roles[k] = "save"
            v["inputs"]["filename_prefix"] = ""
        if ct == "MeshSmoothNormals" and any(is_link(x) and x[0] == k for w in g.values() for x in w["inputs"].values() if w["class_type"] == "MeshToFile3D"):
            roles[k] = "final_mesh"
    out = {"source": TEMPLATE.name, "engine": (cap.get("system_stats") or {}).get("system", {}).get("comfyui_version"), "roles": roles, "graph": g}
    (REPO / a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"pixal3d graph: {len(g)} nodes, roles {roles} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
