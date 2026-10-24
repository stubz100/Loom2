"""D127 (AU3): a stand-in for loom2-vsthost in the offline suite — the same commands and answers (one line of JSON). A "bundle" is a folder
`<name>.vst3` holding `fake.json`: {"classes": [{uid, name, vendor, version, sub}], "crash": bool}; a crashing bundle ends the process with
no answer (exit 3), as a plug-in that crashes would. Every effect is a gain: parameter 0, normalised = the linear gain (default 1.0),
kept in its state file (JSON here; the real host's is binary). `paths` lists none (the system's folders are the real host's)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def answer(obj: dict, code: int = 0) -> int:
    print(json.dumps(obj))
    return code


def bundle(path: str) -> dict:
    p = Path(path) / "fake.json"
    if not p.is_file():
        raise SystemExit(answer({"ok": False, "error": "the bundle did not load: no module"}, 1))
    spec = json.loads(p.read_text(encoding="utf-8"))
    if spec.get("crash"):
        sys.stdout.flush()
        raise SystemExit(3)
    return spec


def load_state(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path and path != "-" else {"gain": 1.0}


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "paths":
        return answer({"ok": True, "paths": []})
    if cmd == "scan":
        return answer({"ok": True, "classes": bundle(argv[1])["classes"]})
    if cmd == "params":
        spec, st = bundle(argv[1]), load_state(argv[3])
        name = next((c["name"] for c in spec["classes"] if c["uid"] == argv[2]), "?")
        return answer({"ok": True, "name": name, "vendor": "Fake", "params": [{"id": 0, "title": "Gain", "units": "", "steps": 0, "value": st["gain"],
                                                                                "shown": f"{st['gain']:.2f}", "automatable": True}]})
    if cmd == "state":
        bundle(argv[1])
        st = load_state(argv[3])
        for kv in argv[5:]:
            k, v = kv.split("=")
            if k == "0":
                st["gain"] = float(v)
        Path(argv[4]).write_text(json.dumps(st), encoding="utf-8")
        return answer({"ok": True, "name": "Gain"})
    if cmd == "editor":
        bundle(argv[1])
        st = load_state(argv[3])
        st["edited"] = True
        Path(argv[4]).write_text(json.dumps(st), encoding="utf-8")
        return answer({"ok": True, "name": "Gain"})
    if cmd == "render":
        import numpy as np
        import soundfile as sf
        data, rate = sf.read(argv[2], dtype="float32", always_2d=True)
        data = data[:, :2] if data.shape[1] >= 2 else np.repeat(data, 2, axis=1)
        effects = []
        for line in Path(argv[1]).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            b, uid, state, bypass = line.split("\t")
            if bypass == "1":
                effects.append({"bypassed": True})
                continue
            bundle(b)
            data = data * load_state(state)["gain"]
            effects.append({"name": "Gain", "latency": 0})
        sf.write(argv[3], data, rate, subtype="FLOAT")
        return answer({"ok": True, "frames": len(data), "rate": rate, "effects": effects})
    return answer({"ok": False, "error": "usage"}, 1)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
