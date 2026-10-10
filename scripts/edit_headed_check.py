"""Editor check in a *visible* Edge window (10 §14 acceptance; the verification loop of 10 §11).

Headless Chromium cannot present WebGPU canvases, so the headless `csp_check.py` screenshots say nothing about the
editor's stage. This script drives a headed Edge — the same Chromium as WebView2 — over the DevTools protocol:

  render  (default)  open a bench document; the stage must show pixels at once (no resize needed), Ctrl+wheel must
                     zoom, and a window resize must not break either (the 2026-10-06 render-loop regression)
  paint              B + drag paints a visible stroke on the layer; Add mask, E + drag hides a band of the layer
                     (checker shows); the layer's eye toggles the stage; the Brushes tab is screenshotted
  cmpdiag            GPU preview vs exact flatten after each feature in isolation (mask, group, every adjustment
                     and filter type, transform, flips, rotations) — pinpoints a compositor mismatch
  grid               D40 parity grid: seeded noise in every deterministic mode × plain / masked / clipped / isolated group /
                     pass-through group at 50 %, each GPU preview against the exact flatten (p99 ≤ 1; ≤ 2 for the dividing modes)
  brush              PE4: opacity caps a stroke, thin lines, selection clip, lock transparency, eraser, Shift-click / line mode,
                     Alt-click / chip colour pick, smoothing catch-up — by mouse events
  selection          PE2: selection maths in the page, then every selection tool / command by mouse, undone and redone
  psd                builds a stack with every exported construct (fill, lock, clip, adjustment layers, pass-through and
                     isolated groups, a filter layer), exports a PSD and reads it back with psd-tools (D41; `--extra oracle`)
  animate            writes a 24-frame test clip (frame index burned in as a 7-bit code, E6 style) into the project,
                     opens the Animate suite on it and checks: the player shows frame n when asked for frame n (all
                     frames, forwards, backwards and random), in/out + extract range harvest frames with lineage,
                     onion skin, filmstrip and compare views render, the Inputs slot takes a start frame and the
                     preview snaps the size — no page exception. (Nothing is submitted to the engine.)
  perf               03 §6 budgets in the real window (M7 slice 2): Catalogue first paint cold / warm and scroll fps on the
                     10k synthetic project (PROJECT=F:/loom2-projects/synthetic-10k, made by make_synthetic_assets.py),
                     editor fps while six 4K layers with advanced blends re-render every frame, Animate player frame
                     latency on a 121-frame 1024×576 proxy. Numbers only — the budgets are judged in the journal.
  tour               runs every Edit command (tools, view, layers, masks, selection, transform, brush, files) through
                     the dev command hook with a document open, checks the resulting state, answers the in-app
                     dialogs, and reports any page exception or crash overlay per step

Needs the orchestrator venv (PIL, websockets) and the frontend dev server on 1420 (`npm run dev` in frontend/, or
`npx vite --host 127.0.0.1 --port 1420 --strictPort`). Starts its own orchestrator (port 8769, temp state) and closes
everything afterwards. Env: EXTRA="&renderer=webgl" (or "&probe=0") appends dev deep-link flags; OUT= output folder.

    orchestrator/.venv/Scripts/python.exe scripts/edit_headed_check.py [render|paint|tour|cmpdiag|grid|brush|selection|psd|animate|perf]
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
EDGE = next((p for p in ("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe") if Path(p).exists()), None)
OUT = Path(os.environ.get("OUT") or (ROOT / ".loom2_state" / "headed"))
PORT, TOKEN, DBG, DEV = 8769, "headed", 9333, 1420
STORE = "window.__loom2Editor.getState()"
ZOOM_SEL = f"Math.round({STORE}.zoom * 1000) / 1000"          # dev builds expose the editor store (10 §11a)


def api(method: str, path: str, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, headers={"X-Loom-Token": TOKEN, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


class CDP:
    def __init__(self, ws_url: str) -> None:
        self.ws = connect(ws_url, max_size=50 * 2**20)
        self.n = 0
        self.events: list[dict] = []

    def call(self, method: str, timeout: float = 120.0, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv(timeout=timeout))          # a reload mid-call never answers: fail loudly, not forever
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})
            if "method" in msg:
                self.events.append(msg)

    def page_errors(self) -> list[str]:
        """Uncaught exceptions, console.error lines and browser log errors since the last call; drained."""
        out: list[str] = []
        for ev in self.events:
            m, pr = ev.get("method"), ev.get("params", {})
            if m == "Runtime.exceptionThrown":
                d = pr.get("exceptionDetails", {})
                out.append("exception: " + (d.get("exception", {}).get("description") or d.get("text", "?")).split("\n")[0])
            elif m == "Runtime.consoleAPICalled" and pr.get("type") == "error":
                out.append("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in pr.get("args", []))[:200])
            elif m == "Log.entryAdded" and pr.get("entry", {}).get("level") == "error":
                out.append("log: " + str(pr["entry"].get("text", ""))[:200])
        self.events.clear()
        toasts = self.eval("(() => { const t = [...document.querySelectorAll('.toast.error')].map((e) => e.textContent); document.querySelectorAll('.toast.error button[aria-label=dismiss]').forEach((b) => b.click()); return t })()") or []
        out += ["error toast: " + str(t)[:200] for t in toasts]
        crash = self.eval("document.getElementById('crash')?.textContent || ''")
        if crash:
            out.append("crash overlay: " + crash.split("\n")[0][:200])
            self.eval("document.getElementById('crash')?.remove(); 1")
        return out

    def eval(self, expr: str, timeout: float = 120.0):
        r = self.call("Runtime.evaluate", timeout=timeout, expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def wait_for(self, expr: str, timeout: float = 60.0, settle: float = 0.0) -> bool:
        """Poll a page predicate across navigations: a call lost to a context switch is a short timeout, not a hang."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.eval(expr, timeout=5.0):
                    if settle:
                        time.sleep(settle)
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def shot(self, path: Path) -> Image.Image:
        data = base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"])
        path.write_bytes(data)
        return Image.open(BytesIO(data)).convert("RGB")

    def key(self, ch: str) -> None:
        self.call("Input.dispatchKeyEvent", type="keyDown", key=ch, code=f"Key{ch.upper()}", text=ch)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=ch, code=f"Key{ch.upper()}")

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 12) -> None:
        self.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
        self.call("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1)
        for i in range(1, steps + 1):
            self.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + (x1 - x0) * i / steps, y=y0 + (y1 - y0) * i / steps, button="left", buttons=1)
            time.sleep(0.02)
        self.call("Input.dispatchMouseEvent", type="mouseReleased", x=x1, y=y1, button="left", buttons=0, clickCount=1)

    def ctrl_wheel(self, x: float, y: float, n: int = 1) -> None:
        for _ in range(n):
            self.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
            self.call("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=-240, modifiers=2)
            time.sleep(0.3)


def stage_bright(im: Image.Image) -> float:
    """Share of non-dark pixels in the stage area (a 1600×1000 window): ~0 % when nothing is drawn, 20 %+ with a document."""
    w, h = im.size
    st = im.crop((int(w * 0.24), int(h * 0.09), int(w * 0.78), int(h * 0.96)))
    px = list(st.getdata())
    return sum(1 for p in px if max(p) > 60) / len(px) * 100


def tour(cdp: CDP, tmp: Path) -> list[str]:
    """Every Edit command once, with state checks. Returns the failed step descriptions."""
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    run = lambda cid: f"{C}.runCommand('{cid}')"  # noqa: E731
    COUNT = f"(() => {{ let n = 0; const w = (xs) => xs.forEach((x) => {{ n++; if (x.children) w(x.children) }}); w({S}.doc.layers); return n }})()"
    ACTIVE = f"(() => {{ const s = {S}; let hit = null; const w = (xs) => xs.forEach((x) => {{ if (x.id === s.activeId) hit = x; if (x.children) w(x.children) }}); w(s.doc.layers); return hit }})()"

    ANY = object()                                                   # expect=ANY: truthy; expect=None: null

    def step(name: str, js: str, check: str | None = None, expect=ANY, settle: float = 0.3) -> None:
        ran = cdp.eval(js)
        time.sleep(settle)
        got = cdp.eval(check) if check else None
        errs = cdp.page_errors()
        ok = (ran is not False) and (check is None or (bool(got) if expect is ANY else got == expect)) and not errs
        detail = f" → {got!r}" if check else ""
        if expect is not ANY and got != expect:
            detail += f" (expected {expect!r})"
        if ran is False:
            detail += " (command disabled or unknown)"
        print(("ok   " if ok else "FAIL ") + name + detail + ("".join("\n       " + e for e in errs)))
        if not ok:
            fails.append(name)

    def answer_dialog(text: str | None = None) -> bool:
        """Fill the in-app ask dialog (if any) and confirm it; returns whether one was open."""
        has = cdp.eval("!!document.querySelector('.modal.ask')")
        if not has:
            return False
        if text is not None:
            cdp.eval("(() => { const i = document.querySelector('.modal.ask input'); i.focus(); i.select(); return 1 })()")
            cdp.call("Input.insertText", text=text)
            time.sleep(0.1)
        cdp.eval("(() => { const b = [...document.querySelectorAll('.modal.ask .foot button')].pop(); b.click(); return 1 })()")
        time.sleep(0.3)
        return True

    print("--- tools")
    for t in ["move", "marquee", "lasso", "wand", "ai", "brush", "eraser", "fill", "eyedropper", "crop", "hand", "zoom"]:
        step(f"tool {t}", run(f"edit.tool.{t}"), f"{S}.tool", t, settle=0.1)
    print("--- view")
    z0 = cdp.eval(f"{S}.zoom")
    step("zoom in", run("edit.view.zoomIn"), f"{S}.zoom > {z0}")
    step("zoom out", run("edit.view.zoomOut"), f"Math.abs({S}.zoom - {z0}) < 1e-6")
    step("zoom 100 %", run("edit.view.100"), f"{S}.zoom", 1)
    step("zoom 200 %", run("edit.view.200"), f"{S}.zoom", 2)
    step("fit", run("edit.view.fit"), f"{S}.zoom < 2")
    g0 = cdp.eval(f"{S}.pixelGrid")
    step("pixel grid", run("edit.view.grid"), f"{S}.pixelGrid", not g0)
    cdp.eval(run("edit.view.grid"))
    o0 = cdp.eval(f"{S}.overlay")
    step("mask overlay", run("edit.view.overlay"), f"{S}.overlay", not o0)
    cdp.eval(run("edit.view.overlay"))
    step("before on", run("edit.view.before"), f"{S}.before", True)
    step("before off", run("edit.view.before"), f"{S}.before", False)
    print("--- layers")
    n0 = cdp.eval(COUNT)
    base_id = cdp.eval(f"{S}.doc.layers[{S}.doc.layers.length - 1].id")
    step("new layer", run("edit.layer.new"), COUNT, n0 + 1)
    step("duplicate", run("edit.layer.duplicate"), COUNT, n0 + 2)
    step("merge down", run("edit.layer.mergeDown"), COUNT, n0 + 1)
    cdp.eval(run("edit.layer.rename")); time.sleep(0.3)
    had = answer_dialog("Tour layer")
    step("rename via in-app prompt", "1", f"{ACTIVE}.name", "Tour layer" if had else "(no dialog opened)")
    step("hide layer", run("edit.layer.visibility"), f"{ACTIVE}.visible", False)
    step("show layer", run("edit.layer.visibility"), f"{ACTIVE}.visible", True)
    step("solo", run("edit.layer.solo"), f"{S}.doc.layers.filter((l) => l.visible).length", 1)
    step("undo solo", run("edit.undo"), f"{S}.doc.layers.filter((l) => l.visible).length", n0 + 1)
    step("lock", run("edit.layer.lock"), f"{ACTIVE}.locked", True)
    step("unlock", run("edit.layer.lock"), f"{ACTIVE}.locked", False)
    step("move layer down", run("edit.layer.down"), f"{S}.doc.layers.findIndex((l) => l.id === {S}.activeId)", 1)
    step("move layer up", run("edit.layer.up"), f"{S}.doc.layers.findIndex((l) => l.id === {S}.activeId)", 0)
    step("new empty group", run("edit.layer.newGroup"), COUNT, n0 + 2)
    cdp.eval(f"{S}.setActive('{base_id}', false)")
    step("group the active layer", run("edit.layer.group"), f"{ACTIVE}.kind", "group")
    adj = cdp.eval(f"JSON.stringify({C}.commandsFor('edit').map((c) => c.id).filter((i) => i.startsWith('edit.layer.adjustment.')))")
    flt = cdp.eval(f"JSON.stringify({C}.commandsFor('edit').map((c) => c.id).filter((i) => i.startsWith('edit.layer.filter.')))")
    n = cdp.eval(COUNT)
    for cid in json.loads(adj) + json.loads(flt):
        n += 1
        step(cid.replace("edit.layer.", "add "), run(cid), COUNT, n, settle=0.15)
    print("--- masks (on the first raster, from the Zoom tool)")
    cdp.eval(f"{S}.setTool('zoom'); {S}.setActive('{base_id}', false); 1")
    step("add mask → editing it on the brush", run("edit.mask.add"), f"JSON.stringify([{S}.editingMask, {S}.tool, !!{ACTIVE}.mask])", "[true,\"brush\",true]")
    step("mask hint shown under the layers", "1", "!!document.querySelector('.mask-hint')", True)
    step("disable mask", run("edit.mask.toggle"), f"{ACTIVE}.mask.enabled", False)
    step("enable mask", run("edit.mask.toggle"), f"{ACTIVE}.mask.enabled", True)
    step("edit pixels", run("edit.mask.edit"), f"{S}.editingMask", False)
    step("edit mask", run("edit.mask.edit"), f"{S}.editingMask", True)
    step("load mask as selection", run("edit.mask.load"), f"!!{S}.selection", True)
    step("remove mask", run("edit.mask.remove"), f"{ACTIVE}.mask", None)
    step("mask from selection", run("edit.mask.fromSelection"), f"!!{ACTIVE}.mask", True)
    step("deselect", run("edit.sel.none"), f"{S}.selection", None)
    print("--- selection")
    step("select all", run("edit.sel.all"), f"!!{S}.selection", True)
    step("invert", run("edit.sel.invert"), f"!!{S}.selection", True)
    step("feather… (opens the Selection panel)", run("edit.sel.feather"))
    step("quick mask on", run("edit.sel.quickMask"), f"{S}.quickMask", True)
    step("quick mask off", run("edit.sel.quickMask"), f"{S}.quickMask", False)
    cdp.eval(run("edit.sel.all"))
    h = cdp.eval(f"{S}.history.length")
    step("clear selected pixels", run("edit.sel.clear"), f"{S}.history.length", h + 1)
    step("undo clear", run("edit.undo"), f"{S}.history.length", h)
    w0 = cdp.eval(f"{S}.doc.w")
    step("crop to selection (all → unchanged size, selection consumed)", run("edit.sel.crop"), f"JSON.stringify([{S}.doc.w, {S}.selection])", f"[{w0},null]")
    print("--- transform")
    step("free transform", run("edit.transform"), f"!!{S}.transform && {S}.tool === 'move'", True)
    step("cancel transform", run("edit.transform.cancel"), f"{S}.transform", None)
    step("free transform again", run("edit.transform"), f"!!{S}.transform", True)
    step("apply transform", run("edit.transform.apply"), f"{S}.transform", None, settle=0.8)
    h = cdp.eval(f"{S}.history.length")
    for i, cid in enumerate(["edit.layer.flipH", "edit.layer.flipH", "edit.layer.flipV", "edit.layer.flipV", "edit.layer.rot90", "edit.layer.rot270", "edit.layer.rot180", "edit.layer.rot180"]):
        step(cid.replace("edit.layer.", ""), run(cid), f"{S}.history.length", h + i + 1, settle=0.5)
    print("--- brush and colours")
    sz = cdp.eval(f"{S}.brush.size")
    step("larger brush", run("edit.brush.larger"), f"{S}.brush.size > {sz}")
    step("smaller brush", run("edit.brush.smaller"), f"{S}.brush.size", sz)
    hd = cdp.eval(f"{S}.brush.hardness")
    step("harder", run("edit.brush.harder"), f"{S}.brush.hardness >= {hd}")
    step("softer", run("edit.brush.softer"), f"Math.abs({S}.brush.hardness - {hd}) < 0.011")
    bg = cdp.eval(f"{S}.brush.background")
    step("swap colours", run("edit.colour.swap"), f"{S}.brush.color", bg)
    step("default colours", run("edit.colour.default"), f"{S}.brush.color", "#000000")
    print("--- delete with undo toast")
    cdp.eval(f"(() => {{ const s = {S}; let id = null; const w = (xs) => xs.forEach((x) => {{ if (x.name === 'Tour layer') id = x.id; if (x.children) w(x.children) }}); w(s.doc.layers); if (id) s.setActive(id, false); return id }})()")
    n = cdp.eval(COUNT)
    step("delete layer (no confirm)", run("edit.layer.delete"), COUNT, n - 1)
    step("undo offered in a toast", "(() => { const b = [...document.querySelectorAll('.toast button')].find((x) => x.textContent === 'Undo'); if (!b) return false; b.click(); return true })()", COUNT, n)
    print("--- undo / redo ×8")
    f0 = cdp.eval(f"{S}.future.length")
    for _ in range(8):
        cdp.eval(run("edit.undo")); time.sleep(0.15)
    step("undo ×8", "1", f"{S}.future.length", f0 + 8)
    for _ in range(8):
        cdp.eval(run("edit.redo")); time.sleep(0.15)
    step("redo ×8", "1", f"{S}.future.length", f0)
    print("--- files")
    cdp.eval(run("edit.save"))
    t0 = time.time()
    while time.time() - t0 < 15 and cdp.eval(f"{S}.saving || {S}.docDirty"):
        time.sleep(0.3)
    step("save", "1", f"{S}.docDirty", False)
    before = api("GET", "/assets?limit=1000")
    n_assets = before.get("total", len(before.get("items", []))) if isinstance(before, dict) else len(before)
    cdp.eval(run("edit.saveToCatalogue"))
    t0 = time.time()
    while time.time() - t0 < 15:
        after = api("GET", "/assets?limit=1000")
        n_after = after.get("total", len(after.get("items", []))) if isinstance(after, dict) else len(after)
        if n_after > n_assets:
            break
        time.sleep(0.4)
    step(f"save to catalogue (assets {n_assets} → {n_after})", "1") if n_after > n_assets else (fails.append("save to catalogue") or print(f"FAIL save to catalogue (assets {n_assets} → {n_after})"))
    cdp.eval(run("edit.exportPng")); time.sleep(2.5)
    pngs = list((tmp / "dl").glob("*.png"))
    step("export PNG downloads a file", "1", "1") if pngs else (fails.append("export PNG") or print("FAIL export PNG: no .png downloaded"))
    cdp.eval(run("edit.exportPsd"))
    t0 = time.time()
    while time.time() - t0 < 25 and not list((tmp / "dl").glob("*.psd")):
        time.sleep(0.5)
    psds = list((tmp / "dl").glob("*.psd"))
    step("export PSD downloads a file", "1", "1") if psds else (fails.append("export PSD") or print("FAIL export PSD: no .psd downloaded"))
    cdp.eval(run("edit.compare"))
    t0 = time.time()
    while time.time() - t0 < 20 and not cdp.eval(f"!!{S}.lastCompare"):
        time.sleep(0.4)
    step("compare with the exact flatten (p99 ≤ 4/255)", "1", f"JSON.stringify({S}.lastCompare && [{S}.lastCompare.rgb_mean, {S}.lastCompare.rgb_p99, {S}.lastCompare.rgb_max])")
    cmp_ = cdp.eval(f"{S}.lastCompare && {S}.lastCompare.rgb_p99")
    if cmp_ is None or cmp_ > 4:
        fails.append("compare p99"); print(f"FAIL compare p99 = {cmp_!r}")
    cdp.eval(run("edit.layer.new")); time.sleep(0.3)
    cdp.eval(run("edit.close")); time.sleep(0.4)
    had = answer_dialog()
    step("close with unsaved changes asks in-app, then closes", "1", f"{S}.doc === null && {had and 'true' or 'false'}", True)
    errs = cdp.page_errors()
    if errs:
        print("FAIL trailing page errors: " + "; ".join(errs)); fails.append("trailing errors")
    return fails


def cmpdiag(cdp: CDP) -> list[str]:
    """Compare the GPU preview with the exact flatten after each feature, one at a time, on the bench document."""
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731

    def compare(label: str) -> None:
        cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
        t0 = time.time()
        while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
            time.sleep(0.3)
        r = cdp.eval("JSON.stringify(window.__cmp && window.__cmp.rgb_p99 !== undefined ? [window.__cmp.rgb_mean, window.__cmp.rgb_p99, window.__cmp.rgb_max] : window.__cmp)")
        errs = cdp.page_errors()
        p99 = None
        try:
            p99 = json.loads(r)[1]
        except Exception:
            pass
        ok = p99 is not None and p99 <= 4 and not errs
        print(("ok   " if ok else "FAIL ") + f"{label}: [mean, p99, max] = {r}" + "".join("\n       " + e for e in errs))
        if not ok:
            fails.append(label)

    compare("base layer only")
    run("edit.mask.add"); time.sleep(0.3); compare("white mask on the base layer")
    cdp.eval(f"(() => {{ const s = {S}; const m = s.masks.get(s.activeId); m.ctx.fillStyle = '#000'; m.ctx.fillRect(0, 0, m.width / 2, m.height); m.refresh(); m.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.4)
    compare("mask black on the left half")
    run("edit.mask.remove"); time.sleep(0.3); compare("mask removed")
    run("edit.layer.group"); time.sleep(0.3); compare("base inside a pass-through group")
    cdp.eval(f"{S}.updateNode({S}.activeId, {{ passthrough: false }}, 'group mode'); 1"); time.sleep(0.3); compare("… isolated group")
    cdp.eval(f"{S}.updateNode({S}.activeId, {{ opacity: 0.5 }}, 'opacity'); 1"); time.sleep(0.3); compare("… isolated group at 50 %")
    run("edit.undo"); run("edit.undo"); run("edit.undo"); time.sleep(0.4); compare("group undone")
    for cid in json.loads(cdp.eval(f"JSON.stringify({C}.commandsFor('edit').map((c) => c.id).filter((i) => /^edit\\.layer\\.(adjustment|filter)\\./.test(i)))")):
        run(cid); time.sleep(0.4); compare(cid.replace("edit.layer.", "") + " (defaults, above the base)")
        run("edit.layer.delete"); time.sleep(0.3)
    cdp.eval(f"{S}.setActive({S}.doc.layers[0].id, false); 1")
    run("edit.transform"); time.sleep(0.2); run("edit.transform.apply"); time.sleep(0.8); compare("identity free transform applied")
    run("edit.layer.flipH"); run("edit.layer.flipH"); time.sleep(0.6); compare("flipH ×2")
    run("edit.layer.rot90"); time.sleep(0.6); compare("rot90")
    run("edit.layer.rot270"); time.sleep(0.6); compare("rot270 (back)")
    run("edit.layer.new"); time.sleep(0.3); compare("empty raster layer above")

    # D39: Photoshop clipping, pass-through mixing, adjustment blend modes and formulas
    def paint(rect: str, colour: str) -> None:
        cdp.eval(f"(() => {{ const s = {S}; const p = s.pixels.get(s.activeId); p.ctx.fillStyle = '{colour}'; p.ctx.fillRect({rect}); p.refresh(); p.dirty = true; s.touch(); s.bump(); return 1 }})()")
        time.sleep(0.3)

    def patch(js: str, label: str) -> None:
        cdp.eval(f"{S}.updateNode({S}.activeId, {js}, '{label}'); 1"); time.sleep(0.4)

    paint("0, 0, p.width / 2, p.height", "rgba(200, 40, 40, 0.6)")                     # the base: half-transparent red, left half
    base_id = cdp.eval(f"{S}.activeId")
    compare("D39 half-transparent base")
    run("edit.layer.new"); time.sleep(0.3)
    paint("0, p.height / 4, p.width, p.height / 2", "rgb(30, 90, 220)")               # a blue band across the whole width
    patch("{ clip: true }", "clip")
    compare("D39 clipped band (only inside the base)")
    patch("{ blend: 'multiply' }", "blend"); compare("D39 clipped band in multiply")
    cdp.eval(f"{S}.updateNode('{base_id}', {{ opacity: 0.5, blend: 'screen' }}, 'base'); 1"); time.sleep(0.4)
    compare("D39 clip unit takes the base's opacity and mode")
    cdp.eval(f"{S}.updateNode('{base_id}', {{ opacity: 1, blend: 'normal' }}, 'base'); 1"); time.sleep(0.3)
    run("edit.layer.adjustment.invert"); time.sleep(0.4)
    patch("{ clip: true }", "clip"); compare("D39 clipped invert adjustment")
    patch("{ clip: false, blend: 'multiply' }", "blend"); compare("D39 invert adjustment in multiply")
    cdp.eval(f"{S}.addLayer('adjustment', {{ type: 'exposure', params: {{ exposure: 0.7, offset: 0.02, gamma: 1.2 }} }}); 1"); time.sleep(0.4)
    compare("D40 exposure in linear light (0.7 EV, offset 0.02, gamma 1.2)")
    run("edit.layer.delete"); time.sleep(0.3)
    cdp.eval(f"{S}.setActive({S}.doc.layers[0].id, false); 1"); time.sleep(0.2)
    patch("{ blend: 'normal' }", "blend")
    run("edit.layer.group"); time.sleep(0.3)
    patch("{ opacity: 0.5 }", "opacity"); compare("D39 pass-through group at 50 % holding an adjustment")
    patch("{ opacity: 1 }", "opacity")
    run("edit.undo"); run("edit.undo"); run("edit.undo"); time.sleep(0.4)
    run("edit.layer.new"); time.sleep(0.3)
    paint("0, 0, p.width, p.height", "rgb(140, 200, 60)")
    for mode in ("soft-light", "vivid-light", "hard-mix", "color-burn", "color-dodge"):
        patch(f"{{ blend: '{mode}' }}", "blend"); compare(f"D39 {mode} over the stack")
    return fails


def grid(cdp: CDP) -> list[str]:
    """D40 parity grid (PhotoCraft's gpu/tests/parity.rs idea): a seeded-noise layer in every deterministic blend mode, over a
    half-transparent base, × {plain, masked, clipped, inside an isolated group, inside a pass-through group at 50 %}; each
    GPU preview compared with compose.py's exact flatten. Dissolve is seeded noise on both sides but not the same noise (10 §3)."""
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    rows: list[tuple[str, str, float, float]] = []
    DIVIDING = {"color-dodge", "vivid-light", "divide"}
    run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731
    modes = [m for m in json.loads(cdp.eval(f"JSON.stringify({S}.blendModes ?? null)") or "null") or [] if m != "dissolve"] or [
        "normal", "darken", "multiply", "color-burn", "linear-burn", "lighten", "screen", "color-dodge", "linear-dodge", "overlay", "soft-light", "hard-light",
        "vivid-light", "linear-light", "pin-light", "hard-mix", "difference", "exclusion", "subtract", "divide", "hue", "saturation", "color", "luminosity"]

    def compare() -> tuple[float, float] | None:
        cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
        t0 = time.time()
        while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
            time.sleep(0.2)
        r = json.loads(cdp.eval("JSON.stringify(window.__cmp && window.__cmp.rgb_p99 !== undefined ? [window.__cmp.rgb_p99, window.__cmp.rgb_max] : null)") or "null")
        return (r[0], r[1]) if r else None

    def js(expr: str) -> None:
        cdp.eval(f"(() => {{ const s = {S}; {expr}; return 1 }})()"); time.sleep(0.25)

    run("edit.layer.new"); time.sleep(0.3)
    js("const p = s.pixels.get(s.activeId); p.ctx.fillStyle = 'rgba(200, 60, 40, 0.6)'; p.ctx.fillRect(0, 0, p.width / 2, p.height); p.refresh(); p.dirty = true; s.touch(); s.bump()")
    base = cdp.eval(f"{S}.activeId")
    run("edit.layer.new"); time.sleep(0.3)
    # seeded noise (mulberry32): rgb uniform, alpha 64–255, the same every run
    js("const p = s.pixels.get(s.activeId); const im = p.ctx.createImageData(p.width, p.height); let a = 20261010; const rnd = () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }; for (let i = 0; i < im.data.length; i += 4) { im.data[i] = rnd() * 256; im.data[i + 1] = rnd() * 256; im.data[i + 2] = rnd() * 256; im.data[i + 3] = 64 + rnd() * 192 } p.ctx.putImageData(im, 0, 0); p.refresh(); p.dirty = true; s.touch(); s.bump()")
    noise = cdp.eval(f"{S}.activeId")

    def sweep(structure: str) -> None:
        for mode in modes:
            js(f"s.updateNode('{noise}', {{ blend: '{mode}' }}, 'blend')")
            r = compare()
            p99, mx = r if r else (999.0, 999.0)
            rows.append((structure, mode, p99, mx))
            # the division modes amplify the 8-bit rounding of the GPU backdrop (compose.py accumulates in float32): p99 ≤ 2 there
            ok = r is not None and p99 <= (2 if mode in DIVIDING else 1)
            if not ok:
                fails.append(f"{structure} / {mode}")
            print(("ok   " if ok else "FAIL ") + f"{structure:22} {mode:13} p99 {p99:g} max {mx:g}")

    sweep("plain")
    js(f"s.setActive('{noise}', false)"); run("edit.mask.add"); time.sleep(0.3)
    js(f"const m = s.masks.get('{noise}'); m.ctx.fillStyle = '#000'; m.ctx.fillRect(0, 0, m.width, m.height / 3); m.ctx.fillStyle = '#808080'; m.ctx.fillRect(0, m.height / 3, m.width, m.height / 3); m.refresh(); m.dirty = true; s.touch(); s.bump()")
    sweep("masked")
    run("edit.mask.remove"); time.sleep(0.3)
    js(f"s.updateNode('{noise}', {{ clip: true }}, 'clip')")
    sweep("clipped to the base")
    js(f"s.updateNode('{noise}', {{ clip: false }}, 'clip')")
    js(f"s.setActive('{noise}', false)"); run("edit.layer.group"); time.sleep(0.3)
    group = cdp.eval(f"{S}.activeId")
    js(f"s.updateNode('{group}', {{ passthrough: false }}, 'group')")
    sweep("isolated group")
    js(f"s.updateNode('{group}', {{ passthrough: true, opacity: 0.5 }}, 'group')")
    sweep("pass-through group 50 %")
    worst = max(rows, key=lambda r: r[2]) if rows else None
    print(f"grid: {len(rows)} cases, {len(fails)} over budget (p99 ≤ 1; ≤ 2 for dodge / vivid / divide)" + (f"; worst {worst[0]} / {worst[1]} p99 {worst[2]:g} max {worst[3]:g}" if worst else "") + f" (base {base})")
    return fails


def brush_check(cdp: CDP) -> list[str]:
    """PE4 (D50 / D51): the brush model and the painting modifiers, by mouse events on a fresh transparent layer."""
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text)
        if not ok:
            fails.append(text)

    geo = json.loads(cdp.eval(f"JSON.stringify((() => {{ const r = document.querySelector('.edit-canvas').getBoundingClientRect(); const s = {S}; return {{ x: r.left, y: r.top, zoom: s.zoom, px: s.pan.x, py: s.pan.y, w: s.doc.w, h: s.doc.h }} }})())"))

    def scr(x: float, y: float) -> tuple[float, float]:                # document pixels → screen
        return geo["x"] + geo["px"] + x * geo["zoom"], geo["y"] + geo["py"] + y * geo["zoom"]

    def stroke(pts: list[tuple[float, float]], modifiers: int = 0, hold: float = 0.0) -> None:
        sx, sy = scr(*pts[0])
        cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=sx, y=sy)
        cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=sx, y=sy, button="left", buttons=1, clickCount=1, modifiers=modifiers)
        for a, b in zip(pts, pts[1:]):
            for i in range(1, 7):
                x, y = scr(a[0] + (b[0] - a[0]) * i / 6, a[1] + (b[1] - a[1]) * i / 6)
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y, button="left", buttons=1, modifiers=modifiers)
        if hold:
            time.sleep(hold)
        ex, ey = scr(*pts[-1])
        cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=ex, y=ey, button="left", buttons=0, clickCount=1, modifiers=modifiers)
        time.sleep(0.4)

    def px(x: int, y: int) -> list[int]:
        return json.loads(cdp.eval(f"JSON.stringify(Array.from({S}.pixels.get({S}.activeId).ctx.getImageData({x}, {y}, 1, 1).data))"))

    def region_max_alpha(x0: int, y0: int, x1: int, y1: int) -> int:
        return cdp.eval(f"(() => {{ const d = {S}.pixels.get({S}.activeId).ctx.getImageData({x0}, {y0}, {x1 - x0}, {y1 - y0}).data; let m = 0; for (let i = 3; i < d.length; i += 4) m = Math.max(m, d[i]); return m }})()")

    def brush(**kw) -> None:
        cdp.eval(f"{S}.setBrush({json.dumps(kw)}); 1")

    W, H = geo["w"], geo["h"]
    run("edit.tool.brush"); cdp.eval(f"{S}.setView({{ brushLine: false, pickOnce: false }}); 1")
    run("edit.layer.new"); time.sleep(0.3)
    brush(size=24, hardness=1, opacity=0.5, flow=1, spacing=0.1, smoothing=0, color="#ff0000")
    zig = [(W * 0.2, H * 0.3), (W * 0.4, H * 0.3), (W * 0.2, H * 0.32), (W * 0.4, H * 0.31), (W * 0.2, H * 0.3)]
    stroke(zig)
    a = region_max_alpha(int(W * 0.18), int(H * 0.25), int(W * 0.42), int(H * 0.37))
    check(120 <= a <= 129, f"opacity 50 % caps a stroke that crosses itself (max alpha {a}, the old dabs reached 255)")
    run("edit.undo"); time.sleep(0.3)
    check(region_max_alpha(int(W * 0.18), int(H * 0.25), int(W * 0.42), int(H * 0.37)) == 0, "undo of the stroke")
    # a thin diagonal line has no gaps
    brush(size=2, hardness=1, opacity=1, flow=1, spacing=0.1)
    stroke([(W * 0.1, H * 0.6), (W * 0.3, H * 0.75)])
    gaps = cdp.eval(f"(() => {{ const d = {S}.pixels.get({S}.activeId).ctx; let worst = 255; for (let t = 0.05; t <= 0.95; t += 0.01) {{ const x = Math.round({W * 0.1} + {W * 0.2} * t), y = Math.round({H * 0.6} + {H * 0.15} * t); let m = 0; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) m = Math.max(m, d.getImageData(x + dx, y + dy, 1, 1).data[3]); worst = Math.min(worst, m) }} return worst }})()")
    check(gaps >= 120, f"a 2-px diagonal line has no gaps (weakest point along it: alpha {gaps})")
    run("edit.undo"); time.sleep(0.3)
    # selection clip
    brush(size=30, opacity=1, flow=1, hardness=1)
    cdp.eval(f"(() => {{ const s = {S}; s.editSelection('test', () => {{ const sel = s.ensureSelection(); sel.ctx.fillStyle = '#fff'; sel.ctx.fillRect(0, 0, {W // 2}, {H}); sel.refresh() }}); return 1 }})()"); time.sleep(0.3)
    run("edit.tool.brush"); time.sleep(0.2)
    stroke([(W * 0.3, H * 0.5), (W * 0.7, H * 0.5)])
    check(px(int(W * 0.35), int(H * 0.5))[3] > 200 and px(int(W * 0.65), int(H * 0.5))[3] == 0, "painting stays inside the selection")
    run("edit.undo"); run("edit.sel.none"); time.sleep(0.3)
    # lock transparency: a half-alpha patch keeps its alpha when painted over
    cdp.eval(f"(() => {{ const s = {S}; const p = s.pixels.get(s.activeId); p.ctx.fillStyle = 'rgba(0, 0, 255, 0.5)'; p.ctx.fillRect(40, 40, 60, 60); p.refresh(); p.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.3)
    run("edit.layer.lockAlpha"); time.sleep(0.2)
    brush(color="#00ff00")
    stroke([(20, 70), (140, 70)])
    la = px(70, 70), px(120, 70)
    check(la[0][3] in (127, 128) and la[0][1] > 200 and la[1][3] == 0, f"lock transparency: the colour changes, the alpha does not ({la})")
    run("edit.layer.lockAlpha"); time.sleep(0.2)
    # eraser at 50 % over an opaque patch removes half
    cdp.eval(f"(() => {{ const s = {S}; const p = s.pixels.get(s.activeId); p.ctx.fillStyle = '#ffffff'; p.ctx.fillRect(200, 40, 80, 60); p.refresh(); p.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.3)
    run("edit.tool.eraser"); brush(opacity=0.5, size=30)
    stroke([(210, 70), (270, 70), (210, 72), (270, 70)])
    e = px(240, 70)[3]
    check(125 <= e <= 130, f"a 50 % eraser stroke leaves alpha ≈ 128 however often it crosses ({e})")
    # Shift-click: a straight line from the last stroke's end
    run("edit.tool.brush"); brush(opacity=1, size=6, color="#ffff00")
    stroke([(300, 150), (300, 151)])
    stroke([(420, 210)], modifiers=8)
    mid = px(360, 180)
    check(mid[3] > 200 and mid[0] > 200 and mid[1] > 200, f"Shift-click draws a straight line from the last point ({mid})")
    # line mode: a wiggly drag paints the straight segment start → end
    cdp.eval(f"{S}.setView({{ brushLine: true }}); 1")
    stroke([(100, 300), (160, 360), (220, 280), (300, 300)])
    straight, off = px(200, 300), px(160, 360)
    check(straight[3] > 200 and off[3] == 0, f"line mode paints only the straight segment ({straight[3]}, off-line {off[3]})")
    cdp.eval(f"{S}.setView({{ brushLine: false }}); 1")
    # Alt-click picks the colour; the pick chip is one-shot
    cdp.eval(f"{S}.setBrush({{ color: '#123456' }}); 1")
    stroke([(70, 70)], modifiers=1)
    picked = (cdp.eval(f"{S}.brush.color") or "").lower()
    check(picked != "#123456" and int(picked[3:5], 16) > int(picked[1:3], 16), f"Alt-click picks the composite colour under the pointer — green over the image ({picked})")
    run("edit.brush.pick"); cdp.eval(f"{S}.setBrush({{ color: '#123456' }}); 1")
    stroke([(240, 70)])
    check(cdp.eval(f"{S}.pickOnce") is False and (cdp.eval(f"{S}.brush.color") or "").lower() != "#123456", "the pick chip picks once and disarms")
    # smoothing: a lagging brush still ends where the pointer was released
    brush(smoothing=0.9, size=8, opacity=1, color="#ff00ff")
    stroke([(500, 100), (600, 100)])
    end = px(598, 100)
    check(end[3] > 200, f"with heavy smoothing the stroke still reaches the release point ({end})")
    errs = cdp.page_errors()
    check(not errs, "no page errors" + ("".join("\n       " + x for x in errs)))
    return fails


def selection_check(cdp: CDP) -> list[str]:
    """PE2 (D43 / D44): selection maths in the page (distance transform vs brute force, modify, combine), then every selection tool
    and command driven by mouse events, each undone and redone."""
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text)
        if not ok:
            fails.append(text)

    # ---- maths, imported straight from the Vite dev server ----
    maths = cdp.eval("""(async () => {
      const m = await import('/src/suites/edit/selectionOps.ts')
      const out = []
      let seed = 7; const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff }
      let worst = 0
      for (let t = 0; t < 5; t++) {
        const w = 47, h = 31, inside = new Uint8Array(w * h)
        for (let i = 0; i < inside.length; i++) inside[i] = rnd() < 0.04 ? 1 : 0
        inside[0] = 1
        const d = m.edt(inside, w, h)
        for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
          let best = 1e9
          for (let yy = 0; yy < h; yy++) for (let xx = 0; xx < w; xx++) if (inside[yy * w + xx]) best = Math.min(best, Math.hypot(x - xx, y - yy))
          worst = Math.max(worst, Math.abs(best - d[y * w + x]))
        }
      }
      out.push(worst)
      const w = 41, v = new Uint8Array(w * w); v[20 * w + 20] = 255
      const e = m.expand(v, w, w, 10)
      let discOk = true
      for (let y = 0; y < w; y++) for (let x = 0; x < w; x++) { const r = Math.hypot(x - 20, y - 20); if (r <= 10 && e[y * w + x] !== 255) discOk = false; if (r >= 11 && e[y * w + x] !== 0) discOk = false }
      out.push(discOk, e[20 * w + 31] === 0 && e[31 * w + 31] === 0)
      const a = new Uint8Array([0, 100, 255, 255]), b = new Uint8Array([255, 255, 0, 128])
      out.push(Array.from(m.combine(a, b, 'add')).join(), Array.from(m.combine(a, b, 'subtract')).join(), Array.from(m.combine(a, b, 'intersect')).join(), Array.from(m.combine(null, b, 'intersect')).join())
      const sq = new Uint8Array(30 * 30); for (let y = 10; y < 20; y++) for (let x = 10; x < 20; x++) sq[y * 30 + x] = 255
      const c = m.contract(sq, 30, 30, 2), f = m.feather(sq, 30, 30, 6)
      out.push(c[15 * 30 + 12] === 255 && c[15 * 30 + 10] === 0, f[15 * 30 + 10] > 0 && f[15 * 30 + 10] < 255 && f[15 * 30 + 15] > 200)
      return JSON.stringify(out)
    })()""")
    r = json.loads(maths) if maths else [None] * 8
    check(r[0] is not None and r[0] < 1e-4, f"EDT equals brute force (worst error {r[0]})")
    check(r[1] is True and r[2] is True, "expanding a point gives a round disc with an anti-aliased rim")
    check(r[3:7] == ["255,255,255,255", "0,0,255,127", "0,100,0,128", "0,0,0,0"], f"combine add / subtract / intersect / intersect-with-nothing {r[3:7]}")
    check(r[7] is True, "contract and feather")

    # ---- tools by mouse ----
    geo = json.loads(cdp.eval(f"JSON.stringify((() => {{ const r = document.querySelector('.edit-canvas').getBoundingClientRect(); const s = {S}; return {{ x: r.left, y: r.top, zoom: s.zoom, px: s.pan.x, py: s.pan.y, w: s.doc.w, h: s.doc.h }} }})())"))

    def scr(fx: float, fy: float) -> tuple[float, float]:
        return geo["x"] + geo["px"] + fx * geo["w"] * geo["zoom"], geo["y"] + geo["py"] + fy * geo["h"] * geo["zoom"]

    def sel() -> list | None:
        return json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; if (!s.selection) return null; const d = s.selection.toRaw(); let n = 0, soft = 0, h = 7; for (let i = 0; i < d.length; i++) {{ if (d[i] > 127) n++; if (d[i] > 0 && d[i] < 255) soft++; h = (h * 31 + d[i]) | 0 }} return [n, soft, h] }})())"))

    def click(fx: float, fy: float, count: int = 1, modifiers: int = 0) -> None:
        x, y = scr(fx, fy)
        cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        for c in range(1, count + 1):
            cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=c, modifiers=modifiers)
            cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", buttons=0, clickCount=c, modifiers=modifiers)
        time.sleep(0.35)

    def drag(a: tuple[float, float], b: tuple[float, float], modifiers: int = 0) -> None:
        (x0, y0), (x1, y1) = scr(*a), scr(*b)
        cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
        cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1, modifiers=modifiers)
        for i in range(1, 9):
            cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + (x1 - x0) * i / 8, y=y0 + (y1 - y0) * i / 8, button="left", buttons=1, modifiers=modifiers)
        cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=x1, y=y1, button="left", buttons=0, clickCount=1, modifiers=modifiers)
        time.sleep(0.5)

    cdp.eval(f"{S}.setView({{ selectionMode: 'replace', marqueeFeather: 0, marqueeStyle: 'normal', lassoKind: 'freehand', wandContiguous: true, wandMerged: false, wandAA: true }}); 1")
    run("edit.tool.marquee"); time.sleep(0.2)
    h0 = cdp.eval(f"{S}.history.length")
    drag((0.2, 0.2), (0.6, 0.6))
    a = sel()
    check(a is not None and a[0] > 1000, f"marquee selects ({a and a[0]} px)")
    run("edit.undo"); time.sleep(0.3)
    check(sel() is None, "undo of the first marquee leaves no selection")
    run("edit.redo"); time.sleep(0.3)
    check(sel() == a, "redo restores it exactly")
    drag((0.4, 0.4), (0.8, 0.8), modifiers=1 | 8)                         # Shift+Alt: intersect
    b = sel()
    check(b is not None and 0 < b[0] < a[0] * 0.5, f"Shift+Alt drag intersects ({b and b[0]} of {a[0]} px)")
    run("edit.undo"); time.sleep(0.3)
    check(sel() == a, "undo of the intersect restores the marquee")
    run("edit.sel.invert"); time.sleep(0.3)
    inv = sel()
    check(inv is not None and inv[0] > geo["w"] * geo["h"] - a[0] - 50, "invert")
    run("edit.undo"); time.sleep(0.3)
    check(sel() == a, "undo of invert")
    cdp.eval(f"{S}.setView({{ selModifyPx: 8 }}); 1")
    for op, cmp in (("expand", lambda n: n > a[0]), ("contract", lambda n: n < a[0]), ("border", lambda n: 0 < n < a[0]), ("smooth", lambda n: abs(n - a[0]) < a[0] * 0.05), ("feather", lambda n: True)):
        run(f"edit.sel.{op}"); time.sleep(0.4)
        m = sel()
        soft = op == "feather" and m is not None and m[1] > 100
        check(m is not None and cmp(m[0]) and (soft or op != "feather"), f"{op} by 8 px ({m and m[0]} px, {m and m[1]} soft)")
        run("edit.undo"); time.sleep(0.3)
        check(sel() == a, f"undo of {op}")
    cdp.eval(f"{S}.setView({{ marqueeFeather: 12 }}); 1")
    drag((0.1, 0.1), (0.3, 0.3))
    f = sel()
    check(f is not None and f[1] > 200, f"marquee feather 12 px gives a soft edge ({f and f[1]} soft px)")
    cdp.eval(f"{S}.setView({{ marqueeFeather: 0, marqueeStyle: 'ratio', marqueeW: 2, marqueeH: 1 }}); 1")
    drag((0.1, 0.1), (0.5, 0.15))
    rr = json.loads(cdp.eval(f"JSON.stringify((() => {{ const d = {S}.selection.toRaw(), w = {S}.doc.w; let x0 = 1e9, x1 = -1, y0 = 1e9, y1 = -1; for (let i = 0; i < d.length; i++) if (d[i] > 127) {{ const x = i % w, y = (i - x) / w; x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y) }} return [x1 - x0 + 1, y1 - y0 + 1] }})())"))
    check(abs(rr[0] / max(1, rr[1]) - 2) < 0.05, f"fixed ratio 2:1 ({rr[0]} × {rr[1]})")
    cdp.eval(f"{S}.setView({{ marqueeStyle: 'normal' }}); 1")
    # polygonal lasso: three corners, then close by clicking the first; then a cancelled one
    run("edit.tool.lasso"); cdp.eval(f"{S}.setView({{ lassoKind: 'polygon' }}); 1"); time.sleep(0.2)
    before_poly = sel()
    for pt in ((0.2, 0.2), (0.7, 0.25), (0.5, 0.7)):
        click(*pt)
    check(cdp.eval(f"({S}.lassoPoly || []).length") == 3, "polygon collects three corners")
    click(0.2, 0.2)
    p = sel()
    check(cdp.eval(f"{S}.lassoPoly") is None and p is not None and p != before_poly and p[0] > 1000, f"clicking the first corner closes the polygon ({p and p[0]} px)")
    click(0.1, 0.8); click(0.3, 0.85)
    run("edit.sel.polyCancel"); time.sleep(0.2)
    check(cdp.eval(f"{S}.lassoPoly") is None and sel() == p, "⊘ cancels an open polygon and leaves the selection alone")
    click(0.1, 0.8); click(0.3, 0.85); click(0.2, 0.95, count=2)
    check(cdp.eval(f"{S}.lassoPoly") is None and sel() != p, "a double-click closes the polygon")
    cdp.eval(f"{S}.setView({{ lassoKind: 'freehand' }}); 1")
    # wand on the bench image, contiguous vs global, and on all layers
    run("edit.tool.wand"); cdp.eval(f"{S}.setView({{ tolerance: 24 }}); {S}.setActive({S}.doc.layers[{S}.doc.layers.length - 1].id, false); 1"); time.sleep(0.2)
    click(0.5, 0.5)
    w1 = sel()
    cdp.eval(f"{S}.setView({{ wandContiguous: false }}); 1")
    click(0.5, 0.5)
    w2 = sel()
    check(w1 is not None and w2 is not None and w2[0] >= w1[0], f"wand: global ({w2 and w2[0]} px) ⊇ contiguous ({w1 and w1[0]} px)")
    check(w1 is not None and w1[1] > 0, f"wand anti-aliases its edge ({w1 and w1[1]} soft px)")
    cdp.eval(f"{S}.setView({{ wandContiguous: true, wandMerged: true }}); 1")
    click(0.5, 0.5)
    check(sel() is not None, "wand samples all layers")
    cdp.eval(f"{S}.setView({{ wandMerged: false }}); 1")
    # layer transparency
    run("edit.layer.new"); time.sleep(0.3)
    cdp.eval(f"(() => {{ const s = {S}; const p = s.pixels.get(s.activeId); p.ctx.fillStyle = '#fff'; p.ctx.fillRect(10, 10, 50, 40); p.refresh(); p.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.3)
    run("edit.sel.fromLayer"); time.sleep(0.3)
    lt = sel()
    check(lt is not None and lt[0] == 2000, f"select layer transparency ({lt and lt[0]} px, expect 50 × 40)")
    # D45 Refine Edge on the server: a marquee over the bench image gets soft, image-aware edges; one undo step restores it
    run("edit.tool.marquee"); cdp.eval(f"{S}.setView({{ selectionMode: 'replace', marqueeFeather: 0 }}); {S}.setRefineEdge(null); 1"); time.sleep(0.2)
    drag((0.25, 0.25), (0.75, 0.75))
    before_refine = sel()
    n_hist = cdp.eval(f"{S}.history.length")
    cdp.eval(f"{S}.setRefineEdge({{ radius: 12, feather: 1 }}); 1")
    run("edit.sel.refine")
    t0 = time.time()
    while time.time() - t0 < 30 and cdp.eval(f"{S}.history.length") == n_hist:
        time.sleep(0.3)
    ref = sel()
    check(ref is not None and before_refine is not None and ref != before_refine and ref[1] > before_refine[1] + 50, f"refine edge softens the edge ({before_refine and before_refine[1]} → {ref and ref[1]} soft px)")
    check(cdp.eval(f"{S}.history[{S}.history.length - 1].label") == "refine edge", "refine edge is one history step")
    run("edit.undo"); time.sleep(0.3)
    check(sel() == before_refine, "undo of refine edge")
    cdp.eval(f"{S}.setRefineEdge(null); 1")
    labels = cdp.eval(f"JSON.stringify({S}.history.slice({h0}).map((e) => e.label))")
    print(f"     history since the start: {labels}")
    pre = sel()
    run("edit.sel.none"); time.sleep(0.2)
    check(sel() is None, "deselect")
    run("edit.undo"); time.sleep(0.3)
    check(pre is not None and sel() == pre, "undo of deselect brings the selection back")
    # D46 clipboard — the system clipboard is stubbed in this page so the check never touches the author's real one
    cdp.eval("navigator.clipboard.write = async () => {}; navigator.clipboard.read = async () => { throw new Error('stubbed') }; 1")
    cdp.eval(f"{S}.setActive({S}.doc.layers[{S}.doc.layers.length - 1].id, false); 1"); time.sleep(0.2)   # the bench layer
    run("edit.tool.marquee"); cdp.eval(f"{S}.setView({{ selectionMode: 'replace', marqueeFeather: 0, marqueeStyle: 'normal' }}); 1"); time.sleep(0.2)
    drag((0.1, 0.1), (0.4, 0.5))
    count = lambda: cdp.eval(f"(() => {{ let n = 0; const w = (ls) => ls.forEach((l) => {{ n++; if (l.children) w(l.children) }}); w({S}.doc.layers); return n }})()")  # noqa: E731
    run("edit.copy"); time.sleep(0.3)
    clip = json.loads(cdp.eval(f"JSON.stringify({S}.clipboard && [{S}.clipboard.canvas.width, {S}.clipboard.canvas.height, {S}.clipboard.x, {S}.clipboard.y])") or "null")
    check(clip is not None and clip[0] > 50 and clip[1] > 50, f"copy fills the clipboard ({clip})")
    n0 = count()
    run("edit.paste"); time.sleep(0.6)
    node = json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; const n = s.doc.layers.find((l) => l.id === s.activeId); return n && [n.name, n.x, n.y, n.w, n.h] }})())"))
    check(count() == n0 + 1 and node and node[3:] == clip[:2] and abs(node[1] + node[3] / 2 - geo["w"] / 2) <= 1, f"paste adds a layer centred on the document ({node})")
    run("edit.undo"); time.sleep(0.3)
    check(count() == n0, "undo removes the pasted layer")
    run("edit.pasteInPlace"); time.sleep(0.6)
    node = json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; const n = s.doc.layers.find((l) => l.id === s.activeId); return n && [n.x, n.y] }})())"))
    check(node == clip[2:], f"paste in place keeps the position ({node} vs {clip[2:]})")
    run("edit.undo"); time.sleep(0.3)
    cdp.eval(f"{S}.setActive({S}.doc.layers[{S}.doc.layers.length - 1].id, false); 1"); time.sleep(0.2)
    run("edit.layer.viaCopy"); time.sleep(0.6)
    check(count() == n0 + 1 and "copy" in (cdp.eval(f"{S}.doc.layers.find((l) => l.id === {S}.activeId)?.name") or ""), "layer via copy")
    run("edit.undo"); time.sleep(0.3)
    cdp.eval(f"{S}.setActive({S}.doc.layers[{S}.doc.layers.length - 1].id, false); 1"); time.sleep(0.2)
    base_id = cdp.eval(f"{S}.activeId")
    run("edit.layer.viaCut"); time.sleep(0.8)
    probe = json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; const n = s.doc.layers.find((l) => l.id === '{base_id}'); const lp = s.pixels.get('{base_id}'); const x = Math.round(s.doc.w * 0.25) - (n.x ?? 0), y = Math.round(s.doc.h * 0.3) - (n.y ?? 0); return [lp.ctx.getImageData(x, y, 1, 1).data[3]] }})())"))
    check(count() == n0 + 1 and probe == [0], f"layer via cut moves the pixels (source alpha there {probe})")
    run("edit.undo"); run("edit.undo"); time.sleep(0.4)
    cdp.eval(f"{S}.setActive({S}.doc.layers[{S}.doc.layers.length - 1].id, false); 1"); time.sleep(0.2)
    run("edit.copyMerged"); time.sleep(0.6)
    merged = json.loads(cdp.eval(f"JSON.stringify({S}.clipboard && [{S}.clipboard.canvas.width, {S}.clipboard.canvas.height])") or "null")
    check(merged == clip[:2], f"copy merged takes the selected part of the composite ({merged})")
    # Ctrl+V from another app: the browser's paste event carries a file
    cdp.eval("""(() => { const c = document.createElement('canvas'); c.width = 40; c.height = 30; const x = c.getContext('2d'); x.fillStyle = '#3c8'; x.fillRect(0, 0, 40, 30);
      c.toBlob((b) => { const dt = new DataTransfer(); dt.items.add(new File([b], 'other-app.png', { type: 'image/png' })); window.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })) }, 'image/png'); return 1 })()""")
    time.sleep(0.8)
    node = json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; const n = s.doc.layers.find((l) => l.id === s.activeId); return n && [n.name, n.w, n.h] }})())"))
    check(node == ["Pasted image", 40, 30], f"Ctrl+V with an image from another app adds it as a layer ({node})")
    # an OS file dropped on the canvas (Tauri hands over its path): imported into the Catalogue first, so the layer has lineage
    n1 = count()
    cdp.eval(f"{S}.dropFiles([{json.dumps(str(ROOT / 'bench' / 'inpaint' / 'source.png'))}]); 1")
    t0 = time.time()
    while time.time() - t0 < 15 and count() == n1:
        time.sleep(0.3)
    lin = cdp.eval(f"{S}.doc.layers.find((l) => l.id === {S}.activeId)?.lineage_asset_id || null")
    check(count() == n1 + 1 and bool(lin), f"a dropped file becomes a layer with lineage ({lin})")
    # D49 Ink from white: a 50 % grey square on white becomes black ink at alpha ≈ 50 %, the white goes; one undo step
    run("edit.layer.new"); time.sleep(0.3)
    cdp.eval(f"(() => {{ const s = {S}; const p = s.pixels.get(s.activeId); p.ctx.fillStyle = '#ffffff'; p.ctx.fillRect(0, 0, p.width, p.height); p.ctx.fillStyle = '#808080'; p.ctx.fillRect(20, 20, 40, 40); p.refresh(); p.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.3)
    run("edit.layer.inkFromWhite"); time.sleep(0.4)
    ink = json.loads(cdp.eval(f"JSON.stringify((() => {{ const p = {S}.pixels.get({S}.activeId); return [Array.from(p.ctx.getImageData(30, 30, 1, 1).data), Array.from(p.ctx.getImageData(5, 5, 1, 1).data)] }})())"))
    check(ink[0][3] in (127, 128) and max(ink[0][:3]) <= 2 and ink[1][3] == 0, f"ink from white: grey → black ink at alpha ½, white → transparent ({ink})")
    check(cdp.eval(f"{S}.history[{S}.history.length - 1].label") == "ink from white", "ink from white is one history step")
    run("edit.undo"); time.sleep(0.3)
    back = json.loads(cdp.eval(f"JSON.stringify(Array.from({S}.pixels.get({S}.activeId).ctx.getImageData(30, 30, 1, 1).data))"))
    check(back == [128, 128, 128, 255], f"undo restores the paper ({back})")
    errs = cdp.page_errors()
    check(not errs, "no page errors" + ("".join("\n       " + e for e in errs)))
    return fails


def psd_check(cdp: CDP, tmp: Path) -> list[str]:
    """D41: build a stack with every exported construct, export a PSD and read it back with psd-tools (the `oracle` extra)."""
    try:
        from psd_tools import PSDImage
        from psd_tools.constants import BlendMode
    except ImportError:
        print("FAIL psd-tools missing: uv sync --project orchestrator --extra dev --extra oracle"); return ["psd-tools missing"]
    S, C = STORE, "window.__loom2Commands"
    fails: list[str] = []
    run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731

    def js(expr: str) -> None:
        cdp.eval(f"(() => {{ const s = {S}; {expr}; return 1 }})()"); time.sleep(0.3)

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text)
        if not ok:
            fails.append(text)

    run("edit.layer.new"); time.sleep(0.3)
    js("const p = s.pixels.get(s.activeId); p.ctx.fillStyle = 'rgb(200, 40, 40)'; p.ctx.fillRect(0, 0, p.width / 2, p.height); p.refresh(); p.dirty = true; s.touch(); s.bump()")
    js("s.updateNode(s.activeId, { name: 'filled', fill: 0.5, locked: true })")
    run("edit.layer.new"); time.sleep(0.3)
    js("const p = s.pixels.get(s.activeId); p.ctx.fillStyle = 'rgb(30, 90, 220)'; p.ctx.fillRect(0, p.height / 4, p.width, p.height / 2); p.refresh(); p.dirty = true; s.touch(); s.bump()")
    js("s.updateNode(s.activeId, { name: 'clipped', clip: true, blend: 'multiply' })")
    js("s.addLayer('adjustment', { type: 'levels', name: 'levels', params: { in_black: 10, in_white: 240, gamma: 1.2, out_black: 5, out_white: 250 } })")
    run("edit.layer.group"); time.sleep(0.3)
    js("s.updateNode(s.activeId, { name: 'pass group' })")
    js("s.addLayer('adjustment', { type: 'curves', name: 'curves', blend: 'screen', opacity: 0.5, params: { rgb: [[0, 0], [128, 150], [255, 255]] } })")
    run("edit.layer.group"); time.sleep(0.3)
    js("s.updateNode(s.activeId, { name: 'iso group', passthrough: false, blend: 'multiply' })")
    js("s.addLayer('adjustment', { type: 'hue_saturation', name: 'huesat', params: { hue: 20, saturation: 10, lightness: -5 } })")
    js("s.addLayer('adjustment', { type: 'exposure', name: 'exposure', params: { exposure: 0.5, offset: 0.01, gamma: 1.1 } })")
    js("s.addLayer('adjustment', { type: 'invert', name: 'invert', visible: false })")
    js("s.addLayer('filter', { type: 'gaussian_blur', name: 'blur' })")
    for f in (tmp / "dl").glob("*.psd"):
        f.unlink()
    run("edit.exportPsd")
    t0 = time.time()
    while time.time() - t0 < 25 and not list((tmp / "dl").glob("*.psd")):
        time.sleep(0.5)
    psds = list((tmp / "dl").glob("*.psd"))
    check(bool(psds), "export PSD downloads a file")
    if not psds:
        return fails
    time.sleep(0.5)
    psd = PSDImage.open(psds[0])
    by = {layer.name: layer for layer in psd.descendants()}
    check(by.get("filled") is not None and abs(by["filled"].fill_opacity - 127.5) <= 1, f"fill opacity 0.5 → {getattr(by.get('filled'), 'fill_opacity', None)}/255")
    locks = getattr(by.get("filled"), "locks", None)
    check(locks is not None and bool(getattr(locks, "composite", False)) and bool(getattr(locks, "position", False)), f"a locked layer is Lock All ({locks})")
    check(by.get("clipped") is not None and by["clipped"].clipping and by["clipped"].blend_mode == BlendMode.MULTIPLY, "clipped layer: clipping + multiply")
    lv = by.get("levels")
    check(lv is not None and lv.kind == "levels", f"levels is an adjustment layer (kind {getattr(lv, 'kind', None)})")
    if lv is not None and lv.kind == "levels":
        m = lv.master
        check((m.input_floor, m.input_ceiling, m.output_floor, m.output_ceiling, round(m.gamma / 100, 2)) == (10, 240, 5, 250, 1.2), f"levels values {m}")
    cv = by.get("curves")
    check(cv is not None and cv.kind == "curves" and cv.blend_mode == BlendMode.SCREEN and cv.opacity == 128, f"curves adjustment in screen at 50 % (kind {getattr(cv, 'kind', None)})")
    check(by.get("pass group") is not None and by["pass group"].blend_mode == BlendMode.PASS_THROUGH, "pass-through group → pass through")
    check(by.get("iso group") is not None and by["iso group"].blend_mode == BlendMode.MULTIPLY, "isolated group keeps its mode")
    hs = by.get("huesat")
    check(hs is not None and hs.kind == "huesaturation", f"hue/saturation adjustment (kind {getattr(hs, 'kind', None)})")
    ex = by.get("exposure")
    check(ex is not None and ex.kind == "exposure" and abs(ex.exposure - 0.5) < 1e-3 and abs(ex.gamma - 1.1) < 1e-3, f"exposure values ({getattr(ex, 'exposure', None)}, {getattr(ex, 'gamma', None)})")
    inv = by.get("invert")
    check(inv is not None and inv.kind == "invert" and not inv.visible, "hidden invert adjustment")
    check("blur" not in by, "filter layer skipped (no Photoshop equivalent)")
    toast = cdp.eval("[...document.querySelectorAll('.toast')].map((t) => t.textContent).join(' | ')")
    check("filter layer" in (toast or "") and "slightly differently" in (toast or ""), f"export toast names the skipped and approximate layers: {toast!r}")
    return fails


def make_coded_clip(project: Path, *, frames: int, fps: int, size: tuple[int, int], asset_id: str) -> str:
    """A clip whose every frame carries its index as 7 white/black squares (E6's code), straight into clips/<id>/."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "orchestrator"))
    from PIL import ImageDraw

    from loom2.clips import ClipStore
    from loom2.workspace import Workspace

    w, h = size
    tmpd = project / "_temp" / "coded"
    tmpd.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(frames):
        im = Image.new("RGB", (w, h), (20 + i * 6, 40, 120 - i * 3))
        d = ImageDraw.Draw(im)
        d.rectangle([int(w * 0.3 + i * 4), int(h * 0.45), int(w * 0.3 + i * 4) + 40, int(h * 0.45) + 40], fill=(240, 166, 58))
        for b in range(7):
            v = 255 if (i >> (6 - b)) & 1 else 0
            d.rectangle([16 + b * 16, 16, 16 + b * 16 + 14, 30], fill=(v, v, v))
        p = tmpd / f"{i:03d}.png"
        im.save(p)
        paths.append(p)
    store = ClipStore(Workspace(project))
    rec = store.create(paths, model_id="wan22-i2v-high-fp8", preset="draft", prompt="coded test clip", seed=1, fps=fps, start_asset_id=asset_id)
    rec = store.encode_proxy(rec)
    return rec.id


def make_4k_document(port: int) -> str:
    """Six 3840×2160 raster layers (noise + gradients, three with advanced blends) through the documents API."""
    import numpy as np

    d = api("POST", "/documents", {"w": 3840, "h": 2160, "name": "perf 6×4K"})
    did = d["id"]
    layers = []
    rng = np.random.default_rng(3)
    blends = ["normal", "multiply", "screen", "overlay", "soft-light", "normal"]
    for i in range(6):
        lid = f"lyr_perf{i}"
        layers.append({"id": lid, "kind": "raster", "name": f"4K layer {i}", "x": 0, "y": 0, "w": 3840, "h": 2160, "visible": True, "locked": False, "opacity": 0.9 if i else 1.0,
                       "fill": 1.0, "blend": blends[i], "clip": False, "mask": None, "passthrough": True, "children": None, "type": None, "params": None})
    d["layers"] = layers
    api("PUT", f"/documents/{did}", d)
    yy, xx = np.mgrid[0:2160, 0:3840].astype(np.float32)
    for i in range(6):
        rgba = np.empty((2160, 3840, 4), dtype=np.uint8)
        rgba[..., 0] = ((xx / 3840) * 255 + rng.integers(0, 40, (2160, 3840))).clip(0, 255)
        rgba[..., 1] = ((yy / 2160) * 255 * (i + 1) / 6).clip(0, 255)
        rgba[..., 2] = rng.integers(0, 255, (2160, 3840))
        rgba[..., 3] = 255 if i == 0 else 160
        req = urllib.request.Request(f"http://127.0.0.1:{port}/documents/{did}/layers/lyr_perf{i}/pixels?w=3840&h=2160", data=rgba.tobytes(), method="PUT",
                                     headers={"X-Loom-Token": TOKEN, "Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=120) as r:
            r.read()
    api("POST", f"/documents/{did}/save")
    return did


def perf_check(cdp: CDP, doc_id: str, clip_id: str, base_url: str) -> list[str]:
    fails: list[str] = []

    def report(ok: bool, text: str) -> None:
        print(("ok   " if ok else "OVER ") + text)
        if not ok:
            fails.append(text)

    def first_paint(url: str) -> tuple[float, int]:
        """Navigate, then poll the new document until the first Catalogue tile exists; performance.now() in that document is
        the time since its navigation started (± the 50 ms poll)."""
        cdp.call("Page.navigate", url=url)
        t0 = time.time()
        while time.time() - t0 < 30:
            try:
                v = cdp.eval("(() => { const n = document.querySelectorAll('.tile').length; return JSON.stringify([performance.now(), n]) })()", timeout=5.0)
                if v:
                    now, n = json.loads(v)
                    if n > 0:
                        return float(now), int(n)
            except Exception:
                pass
            time.sleep(0.05)
        return float("inf"), 0

    cat_url = f"{base_url}&suite=catalogue"
    tp, n = first_paint(cat_url)
    counts = api("GET", "/assets/counts")
    total = counts.get("all") if isinstance(counts, dict) else None
    raf = json.loads(cdp.eval("(() => new Promise((res) => { let f = 0; const t0 = performance.now(); const step = (t) => { f++; if (t - t0 < 1000) requestAnimationFrame(step); else res(JSON.stringify({fps: f / ((t - t0) / 1000), visible: document.visibilityState})) }; requestAnimationFrame(step) }))()"))
    print(f"     window animation-frame rate {raf['fps']:.0f} Hz ({raf['visible']}) · project holds {total} assets")
    print(f"     app boot → first Catalogue tile: {tp:.0f} ms ({n} tiles) — page load, handshake and project info included")
    switch_js = """(() => new Promise((res) => { const S = window.__loom2Session; S.getState().setSuite('models'); setTimeout(() => { const t0 = performance.now(); S.getState().setSuite('catalogue');
        const tick = () => { const n = document.querySelectorAll('.tile').length; if (n > 0 || performance.now() - t0 > 20000) res(JSON.stringify([performance.now() - t0, n])); else requestAnimationFrame(tick) }; tick() }, 600) }))()"""
    sw = json.loads(cdp.eval(switch_js, timeout=40))
    report(sw[0] < 1000, f"Catalogue first paint on a warm index (switch back into the suite): {sw[0]:.0f} ms to {sw[1]} tiles (budget < 1000 ms)")
    time.sleep(1.0)
    scroll = cdp.eval("""(() => new Promise((res) => { const el = document.querySelector('.cat-grid') || document.querySelector('.stage'); let frames = 0, long = 0, last = performance.now(); const t0 = last;
        const step = (t) => { if (t - last > 1000 / %s * 1.5) long++; last = t; frames++; el.scrollTop += 36; if (t - t0 < 3000) requestAnimationFrame(step); else res(JSON.stringify({fps: frames / ((t - t0) / 1000), long, scrolled: el.scrollTop})) }; requestAnimationFrame(step) }))()""" % max(1.0, raf["fps"]))
    sc = json.loads(scroll)
    hz = max(1.0, raf["fps"])
    report(sc["fps"] >= hz * 0.9 and sc["long"] <= 6, f"Catalogue scroll for 3 s: {sc['fps']:.0f} fps at a {hz:.0f} Hz display, {sc['long']} frames over {1000 / hz * 1.5:.0f} ms, scrolled {sc['scrolled']:.0f} px (budget: every display frame)")
    errs = cdp.page_errors()
    if errs:
        report(False, "page errors during the Catalogue pass: " + "; ".join(errs))

    # editor: six 4K layers re-rendered every animation frame (zoom nudged each frame forces a full composite)
    cdp.call("Page.navigate", url=f"{base_url}&suite=edit&doc={doc_id}")
    if not cdp.wait_for("!!(window.__loom2Editor && window.__loom2Editor.getState().doc && window.__loom2App)", timeout=120, settle=2.0):
        report(False, "editor did not open the 6×4K document within 120 s")
        return fails
    layers = cdp.eval("window.__loom2Editor.getState().doc.layers.length")
    renderer = cdp.eval("document.querySelector('.badge-renderer')?.textContent?.trim()")
    # the display runs at whatever it runs at (29 Hz on the author's 4K panel), so the budget is time per composite: CPU submit +
    # GPU completion (queue.onSubmittedWorkDone on WebGPU; gl.finish on WebGL2) for a full re-render of the stack
    comp_js = """(() => new Promise(async (res) => { const app = window.__loom2App; const ed = window.__loom2Editor.getState(); const z0 = ed.zoom; const times = [];
        const gpu = app.renderer.gpu && app.renderer.gpu.device; const gl = app.renderer.gl;
        for (let i = 0; i < 40; i++) { window.__loom2Editor.getState().setView({ zoom: z0 * (i % 2 ? 1.004 : 1.0) }); await new Promise((r) => requestAnimationFrame(r));
          const t0 = performance.now(); app.render(); if (gpu) await gpu.queue.onSubmittedWorkDone(); else if (gl) gl.finish(); times.push(performance.now() - t0) }
        window.__loom2Editor.getState().setView({ zoom: z0 }); times.sort((a, b) => a - b); res(JSON.stringify({p50: times[20], p95: times[38], max: times[39], n: times.length})) }))()"""
    comp = json.loads(cdp.eval(comp_js, timeout=120))
    report(layers == 6 and comp["p95"] <= 16.7, f"Editor composite of {layers} × 4K layers (multiply / screen / overlay / soft-light) on {renderer}: p50 {comp['p50']:.1f} ms · p95 {comp['p95']:.1f} ms · max {comp['max']:.1f} ms per full re-render (budget 16.7 ms = 60 fps)")
    cdp.eval("window.__loom2Editor.getState().setTool('brush'); 1")
    stroke_js = """(() => new Promise((res) => { const host = document.querySelector('.edit-canvas'); const r = host.getBoundingClientRect(); const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const ev = (type, x, y) => host.dispatchEvent(new PointerEvent(type, { bubbles: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button: 0, buttons: type === 'pointerup' ? 0 : 1, isPrimary: true }));
        const lags = []; ev('pointerdown', cx - 200, cy); let i = 0;
        const work = []; const step = () => { const t0 = performance.now(); ev('pointermove', cx - 200 + i * 8, cy + Math.sin(i / 5) * 40); work.push(performance.now() - t0); requestAnimationFrame((t) => { lags.push(t - t0); if (++i < 50) step(); else { ev('pointerup', cx + 200, cy); lags.sort((a, b) => a - b); work.sort((a, b) => a - b); res(JSON.stringify({p50: lags[25], p95: lags[47], max: lags[49], work50: work[25], work95: work[47]})) } }) }; step() }))()"""
    br = json.loads(cdp.eval(stroke_js))
    report(br["p95"] <= 1000 / max(1.0, raf["fps"]) * 1.15, f"Brush on the 4K document: pointer move → next presented frame p50 {br['p50']:.1f} ms · p95 {br['p95']:.1f} ms · max {br['max']:.1f} ms; handler CPU p50 {br['work50']:.1f} ms · p95 {br['work95']:.1f} ms (budget ≤ 1 display frame = {1000 / max(1.0, raf['fps']):.1f} ms at {raf['fps']:.0f} Hz)")
    cdp.eval("window.__loom2Editor.getState().undo(); 1")
    errs = cdp.page_errors()
    if errs:
        report(False, "page errors during the editor pass: " + "; ".join(errs))

    # Animate: frame latency on the 121-frame 1024×576 proxy, sequential and random
    cdp.call("Page.navigate", url=f"{base_url}&suite=animate&clip={clip_id}")
    if not cdp.wait_for("!!(window.__loom2Animate && document.querySelector('.anim-canvas'))", timeout=60, settle=2.0):
        report(False, "Animate did not open the clip within 60 s")
        return fails
    READ = ("(() => { const c = document.querySelector('.anim-canvas'); if (!c) return -2; const ctx = c.getContext('2d'); let v = 0;"
            " for (let b = 0; b < 7; b++) { const px = ctx.getImageData(16 + b * 16 + 7, 23, 1, 1).data; v = (v << 1) | (px[0] > 127 ? 1 : 0) } return v })()")
    lat_js = """(() => new Promise(async (res) => { const read = () => %s; const A = window.__loom2Animate.getState(); const lat = (frames) => new Promise(async (ok) => { const out = [];
        for (const n of frames) { const t0 = performance.now(); A.setFrame(n); await new Promise((r2) => { const poll = () => { if (read() === n || performance.now() - t0 > 2000) r2(); else requestAnimationFrame(poll) }; poll() }); out.push(performance.now() - t0) }
        out.sort((a, b) => a - b); ok({p50: out[Math.floor(out.length / 2)], p95: out[Math.floor(out.length * 0.95)], n: out.length}) });
        try { const seq = await lat(Array.from({length: 60}, (_, i) => i + 1)); const rnd = await lat([97, 3, 55, 120, 20, 88, 41, 7, 66, 110, 33, 72]); res(JSON.stringify({seq, rnd})) } catch (e) { res(JSON.stringify({error: String(e)})) } }))()""" % READ
    lat = json.loads(cdp.eval(lat_js, timeout=200))
    if "error" in lat:
        report(False, f"Animate latency measurement failed: {lat['error']}")
        return fails
    report(lat["seq"]["p95"] <= 41.7 and lat["rnd"]["p95"] <= 80, f"Animate player frame latency (1024×576, GOP 6): sequential p50 {lat['seq']['p50']:.0f} / p95 {lat['seq']['p95']:.0f} ms · random p50 {lat['rnd']['p50']:.0f} / p95 {lat['rnd']['p95']:.0f} ms (budget: a 24 fps frame = 41.7 ms)")
    errs = cdp.page_errors()
    if errs:
        report(False, "page errors during the Animate pass: " + "; ".join(errs))
    return fails


def animate_check(cdp: CDP, clip_id: str, asset_id: str, clip_b: str | None = None) -> list[str]:
    fails: list[str] = []
    A, C = "window.__loom2Animate.getState()", "window.__loom2Commands"
    READ = ("(() => { const c = document.querySelector('.anim-canvas'); if (!c) return -2; const ctx = c.getContext('2d'); let v = 0;"
            " for (let b = 0; b < 7; b++) { const px = ctx.getImageData(16 + b * 16 + 7, 23, 1, 1).data; v = (v << 1) | (px[0] > 127 ? 1 : 0) } return v })()")

    def check(ok: bool, text: str, errs: list[str] | None = None) -> None:
        errs = errs if errs is not None else cdp.page_errors()
        ok = ok and not errs
        print(("ok   " if ok else "FAIL ") + text + "".join("\n       " + e for e in errs))
        if not ok:
            fails.append(text)

    def shown(expect: int, tries: int = 30) -> int:
        """Wait until the canvas shows a frame code (decode is async)."""
        v = -1
        for _ in range(tries):
            v = cdp.eval(READ)
            if v == expect:
                break
            time.sleep(0.1)
        return v

    cur = cdp.eval(f"{A}.current")
    check(cur == clip_id, f"deep link selected the clip ({cur})")
    check(shown(0) == 0, "frame 0 decoded and drawn (code 0)")
    cdp.shot(OUT / "animate-player.png")
    # forwards through every frame with the command
    wrong = []
    for n in range(1, 24):
        cdp.eval(f"{C}.runCommand('anim.stepForward')")
        got = shown(n)
        if got != n:
            wrong.append((n, got))
    check(not wrong, f"stepping forward shows every frame exactly (wrong: {wrong[:5]})")
    cdp.eval(f"{C}.runCommand('anim.home')"); shown(0)
    jumps = [17, 3, 22, 9, 0, 23, 11]
    wrong = [(n, cdp.eval(f"{A}.setFrame({n}); 1") and shown(n)) for n in jumps]
    wrong = [(n, g) for n, g in wrong if g != n]
    check(not wrong, f"random access frames decode exactly (wrong: {wrong})")
    cdp.eval(f"{C}.runCommand('anim.end')"); shown(23)
    wrong = []
    for n in range(22, 10, -1):
        cdp.eval(f"{C}.runCommand('anim.stepBack')")
        if shown(n) != n:
            wrong.append(n)
    check(not wrong, f"stepping backwards is exact too (wrong: {wrong[:5]})")
    # play for a moment, then pause: the frame advanced and the counter agrees with the canvas
    cdp.eval(f"{A}.setFrame(0); {C}.runCommand('anim.play'); 1"); time.sleep(0.8); cdp.eval(f"{C}.runCommand('anim.play')")
    time.sleep(0.3)
    f = cdp.eval(f"{A}.frame"); code = shown(f)
    check(2 <= f <= 23 and code == f and cdp.eval(f"{A}.playing") is False, f"play advanced to frame {f} and the canvas shows {code}")
    # in / out + harvest
    cdp.eval(f"{A}.setFrame(4); {C}.runCommand('anim.setIn'); {A}.setFrame(20); {C}.runCommand('anim.setOut'); 1")
    rng = cdp.eval(f"JSON.stringify({A}.range())")
    check(rng == "[4,20]", f"in/out set from the playhead → range {rng}")
    cdp.eval(f"window.__loom2Animate.setState({{ extractEvery: 8 }}); {C}.runCommand('anim.extractRange')")
    t0 = time.time()
    while time.time() - t0 < 15 and cdp.eval(f"({A}.pins['{clip_id}'] || []).length") < 3:
        time.sleep(0.3)
    pins = cdp.eval(f"JSON.stringify(({A}.pins['{clip_id}'] || []).map((p) => p.frame).sort((a, b) => a - b))")
    clip = api("GET", f"/clips/{clip_id}")
    check(pins == "[4,12,20]" and len(clip["extracted_asset_ids"]) == 3, f"extract range every 8th between 4 and 20 → pins {pins}, {len(clip['extracted_asset_ids'])} assets with frame-extract lineage")
    ex = api("GET", f"/assets/{clip['extracted_asset_ids'][0]}") if clip["extracted_asset_ids"] else {}
    check(ex.get("suite") == "animate" and ex.get("params", {}).get("frame_index") == 4 and ex.get("thumb_status") == "done", "the harvested frame is a Catalogue image with its frame index and a thumbnail")
    check(cdp.eval("document.querySelectorAll('.timeline .marker.pin').length") == 3, "the timeline shows the three harvested pins")
    # onion, filmstrip, compare
    cdp.eval(f"{C}.runCommand('anim.onion')"); time.sleep(0.3)
    check(cdp.eval("!!document.querySelector('.anim-player img.onion')"), "onion skin overlays the start still")
    cdp.eval(f"{C}.runCommand('anim.onion')")
    cdp.eval(f"{C}.runCommand('anim.view.filmstrip')"); time.sleep(0.8)
    n_thumbs = cdp.eval("document.querySelectorAll('.filmstrip button').length")
    check(n_thumbs == 24, f"filmstrip shows one thumbnail per frame for a short clip ({n_thumbs})")
    cdp.eval(f"{C}.runCommand('anim.view.compare')"); time.sleep(0.8)
    check(cdp.eval("document.querySelectorAll('.anim-compare .side').length") == 2 and cdp.eval("!!document.querySelector('.anim-compare img.still')"), "compare view: player A beside the start still")
    if clip_b:
        READ_B = READ.replace("document.querySelector('.anim-canvas')", "document.querySelectorAll('.anim-compare .side canvas')[1]")
        cdp.eval(f"window.__loom2Animate.setState({{ compareWith: '{clip_b}' }}); {A}.setFrame(12); 1")
        want_b = round(12 / 23 * 47)                                   # B's frame at the same normalised time (12 of 0..23 → 25 of 0..47)
        a_code, b_code = -1, -1
        for _ in range(40):
            a_code, b_code = cdp.eval(READ), cdp.eval(READ_B)
            if a_code == 12 and b_code == want_b:
                break
            time.sleep(0.1)
        check(a_code == 12 and b_code == want_b, f"compare syncs two clips by normalised time: A frame 12 of 24 ↔ B frame {b_code} of 48 (expected {want_b})")
        cdp.eval("window.__loom2Animate.setState({ compareWith: null }); 1")
    cdp.eval(f"{C}.runCommand('anim.view.player')"); time.sleep(0.3)
    # the panel: a start frame makes the preview snap and arms Animate (not clicked: the engine is off)
    cdp.eval(f"{A}.setStart('{asset_id}'); 1")
    t0 = time.time()
    while time.time() - t0 < 10 and not cdp.eval(f"!!{A}.preview"):
        time.sleep(0.3)
    pv = cdp.eval(f"JSON.stringify({A}.preview && [{A}.preview.width, {A}.preview.height, {A}.preview.frames, {A}.preview.fps, {A}.preview.missing.length])")
    check(pv is not None and pv.startswith("[832,480,81,16,"), f"preview for the start frame: [w, h, frames, fps, missing] = {pv}")
    check(cdp.eval("!!document.querySelector('.slot img')"), "the Inputs slot shows the start frame")
    armed = cdp.eval("(() => { const b = [...document.querySelectorAll('button.primary')].find((x) => x.textContent.startsWith('Animate')); return b ? !b.disabled : null })()")
    check(armed is True or armed is None, f"Animate button armed when weights are present ({armed}; None = panel not visible)")
    cdp.eval("(() => { const b = [...document.querySelectorAll('button')].find((x) => (x.getAttribute('title') || x.getAttribute('aria-label') || '').startsWith('Length')); b && b.click(); return 1 })()"); time.sleep(0.4)
    cdp.shot(OUT / "animate-length.png")
    cdp.eval("(() => { const b = [...document.querySelectorAll('button')].find((x) => (x.getAttribute('title') || x.getAttribute('aria-label') || '').startsWith('Inputs')); b && b.click(); return 1 })()"); time.sleep(0.4)
    cdp.shot(OUT / "animate-inputs.png")
    print(f"     screenshots: {OUT / 'animate-player.png'}, animate-length.png, animate-inputs.png")
    return fails


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "render"
    if not EDGE:
        print("Edge not found"); return 2
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{DEV}/", timeout=3)
    except Exception:
        print(f"frontend dev server not reachable on {DEV}: run `npm run dev` in frontend/ first"); return 2
    OUT.mkdir(parents=True, exist_ok=True)
    extra = os.environ.get("EXTRA", "")
    tag = extra.replace("&", "_").replace("=", "-") or ""
    tmp = Path(tempfile.mkdtemp(prefix="loom2-headed-"))
    env = {**os.environ, "LOOM2_TOKEN": TOKEN, "PYTHONIOENCODING": "utf-8"}
    orch = subprocess.Popen([sys.executable, "-m", "loom2.main", "--port", str(PORT), "--state", str(tmp / "state")],
                            cwd=str(ROOT / "orchestrator"), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    edge = None
    failures: list[str] = []

    def check(ok: bool, text: str) -> None:
        print(("ok   " if ok else "FAIL ") + text)
        if not ok:
            failures.append(text)

    try:
        t0 = time.time()
        while time.time() - t0 < 60:
            try:
                api("GET", "/health"); break
            except Exception:
                time.sleep(0.3)
        project_path = os.environ.get("PROJECT") if mode == "perf" else None
        if project_path:
            api("POST", "/project/open", {"path": project_path})
            proj_dir = Path(project_path)
        else:
            api("POST", "/project", {"path": str(tmp / "proj"), "name": "Headed", "size_cap_gb": 10})
            proj_dir = tmp / "proj"
        asset = api("POST", "/assets/import", {"paths": [str(ROOT / "bench/inpaint/source.png")]})["items"][0]
        if mode == "animate":
            clip_id = make_coded_clip(tmp / "proj", frames=24, fps=16, size=(320, 192), asset_id=asset["id"])
            clip_b = make_coded_clip(tmp / "proj", frames=48, fps=16, size=(320, 192), asset_id=asset["id"])      # the compare partner (twice the frames)
            url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=animate&clip={clip_id}{extra}"
        elif mode == "perf":
            perf_doc = make_4k_document(PORT)
            perf_clip = make_coded_clip(proj_dir, frames=121, fps=24, size=(1024, 576), asset_id=asset["id"])
            url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=catalogue{extra}"
        else:
            doc = api("POST", "/documents", {"from_asset": asset["id"]})
            url = f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}&suite=edit&doc={doc['id']}{extra}"
        edge = subprocess.Popen([EDGE, f"--remote-debugging-port={DBG}", f"--user-data-dir={tmp / 'edge'}", "--no-first-run", "--no-default-browser-check",
                                 "--window-size=1600,1000", "--window-position=40,40", "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                                 "--disable-backgrounding-occluded-windows", "--disable-features=CalculateNativeWinOcclusion", "--new-window", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws_url = None
        t0 = time.time()
        while time.time() - t0 < 30 and not ws_url:
            try:
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{DBG}/json", timeout=3)):
                    if t.get("type") == "page" and f"127.0.0.1:{DEV}" in t.get("url", ""):
                        ws_url = t["webSocketDebuggerUrl"]
            except Exception:
                time.sleep(0.5)
        if not ws_url:
            print("no page target"); return 1
        cdp = CDP(ws_url)
        cdp.call("Page.enable"); cdp.call("Runtime.enable"); cdp.call("Log.enable")
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=3.0)   # a fresh Vite server may re-optimise deps and reload once
        cdp.call("Page.reload")                                     # start from a warm, settled page
        cdp.wait_for("document.readyState === 'complete' && !!document.querySelector('.frame')", timeout=60, settle=1.0)
        (tmp / "dl").mkdir()
        cdp.call("Browser.setDownloadBehavior", behavior="allow", downloadPath=str(tmp / "dl"))
        # wait for the renderer badge (the editor booted) plus a moment for the first frame
        t0 = time.time()
        badge = None
        while time.time() - t0 < 30 and not badge:
            badge = cdp.eval("document.querySelector('.anim-canvas') ? 'player' : null" if mode == "animate" else "document.querySelector('.tile, .cat-grid') ? 'catalogue' : null" if mode == "perf" else "document.querySelector('.badge-renderer')?.textContent?.trim() || null")
            if badge in (None, "…"):
                badge = None; time.sleep(0.5)
        time.sleep(1.5)
        if mode == "perf":
            failures += perf_check(cdp, perf_doc, perf_clip, f"http://127.0.0.1:{DEV}/?token={TOKEN}&port={PORT}")
            try:
                cdp.call("Browser.close")
            except Exception:
                pass
            print(f"\nperf: {'all budgets met' if not failures else f'{len(failures)} over budget'}")
            return 1 if failures else 0
        if mode == "animate":
            failures += animate_check(cdp, clip_id, asset["id"], clip_b)
            try:
                cdp.call("Browser.close")
            except Exception:
                pass
            print(f"\nanimate: {'all checks passed' if not failures else f'{len(failures)} FAILED'}")
            return 1 if failures else 0
        canvas = cdp.eval("(() => { const c = document.querySelector('.edit-canvas canvas'); if (!c) return null; const r = c.getBoundingClientRect(); return { w: c.width, h: c.height, cssW: r.width, cssH: r.height, x: r.x, y: r.y } })()")
        dpr = cdp.eval("window.devicePixelRatio") or 1
        im0 = cdp.shot(OUT / f"{mode}{tag}-0.png")
        b0 = stage_bright(im0)
        print(f"renderer badge {badge!r} · canvas {canvas} · dpr {dpr}")
        check(badge is not None and canvas is not None, "editor booted (renderer badge + canvas present)")
        check(b0 > 10, f"stage shows the document right away: {b0:.1f} % bright (expect > 10)")
        if not canvas:
            return 1
        cx, cy = canvas["x"] + canvas["cssW"] / 2, canvas["y"] + canvas["cssH"] / 2

        def region_diff(a: Image.Image, b: Image.Image, box) -> float:
            """Mean per-channel difference inside a CSS-pixel box (screenshots are in device pixels)."""
            box = tuple(int(v * dpr) for v in box)
            pa, pb = list(a.crop(box).getdata()), list(b.crop(box).getdata())
            return sum(abs(x[0] - y[0]) + abs(x[1] - y[1]) + abs(x[2] - y[2]) for x, y in zip(pa, pb)) / (3 * len(pa))

        if mode == "render":
            zoom0 = cdp.eval(ZOOM_SEL)
            cdp.ctrl_wheel(cx, cy, 3); time.sleep(1.0)
            zoom1 = cdp.eval(ZOOM_SEL)
            im1 = cdp.shot(OUT / f"{mode}{tag}-1.png")
            check(zoom1 != zoom0 and stage_bright(im1) > b0 + 5, f"Ctrl+wheel zooms and re-renders: zoom {zoom0} → {zoom1}, bright {b0:.1f} → {stage_bright(im1):.1f} %")
            cdp.call("Browser.setWindowBounds", windowId=cdp.call("Browser.getWindowForTarget")["windowId"], bounds={"width": 1500, "height": 950})
            time.sleep(1.5)
            im2 = cdp.shot(OUT / f"{mode}{tag}-2.png")
            check(stage_bright(im2) > 10, f"stage still drawn after a window resize: {stage_bright(im2):.1f} %")
            cdp.ctrl_wheel(cx, cy, 1); time.sleep(1.0)
            zoom2 = cdp.eval(ZOOM_SEL)
            check(zoom2 != zoom1, f"zoom keeps working after the resize: {zoom1} → {zoom2}")
        elif mode == "paint":
            cdp.eval("document.body.focus(); 1")
            cdp.key("b"); time.sleep(0.2)
            tool = cdp.eval(f"{STORE}.tool")
            check(tool == "brush", f"B selects the brush (tool = {tool!r})")
            band = (canvas["x"] + canvas["cssW"] * 0.25, cy - 40, canvas["x"] + canvas["cssW"] * 0.75, cy + 40)
            before = cdp.shot(OUT / f"{mode}{tag}-paint0.png")
            cdp.drag(canvas["x"] + canvas["cssW"] * 0.3, cy, canvas["x"] + canvas["cssW"] * 0.7, cy); time.sleep(0.6)
            after = cdp.shot(OUT / f"{mode}{tag}-paint1.png")
            hist = cdp.eval(f"JSON.stringify({STORE}.history.map(h => h.label))")
            d1 = region_diff(before, after, band)
            check(d1 > 5, f"brush stroke is visible on the stage: band changed by {d1:.1f}/255 (history {hist})")
            added = cdp.eval("(() => { const b = document.querySelector('button[aria-label=\"Add mask\"]'); if (!b) return false; b.click(); return true })()")
            time.sleep(0.5)
            check(bool(added) and bool(cdp.eval(f"{STORE}.editingMask")), "Add mask (Layers toolbar) adds a mask and switches to editing it")
            cdp.key("e"); time.sleep(0.2)
            before2 = cdp.shot(OUT / f"{mode}{tag}-mask0.png")
            cdp.drag(canvas["x"] + canvas["cssW"] * 0.3, cy + 60, canvas["x"] + canvas["cssW"] * 0.7, cy + 60); time.sleep(0.6)
            after2 = cdp.shot(OUT / f"{mode}{tag}-mask1.png")
            d2 = region_diff(before2, after2, (band[0], cy + 20, band[2], cy + 100))
            check(d2 > 5, f"eraser on the mask hides the layer there (checker shows): band changed by {d2:.1f}/255")
            cdp.eval("document.querySelector('.layer-row button.eye')?.click(); 1"); time.sleep(0.5)
            hidden = cdp.shot(OUT / f"{mode}{tag}-hidden.png")
            d3 = region_diff(after2, hidden, (canvas["x"] + canvas["cssW"] * 0.2, canvas["y"] + canvas["cssH"] * 0.3, canvas["x"] + canvas["cssW"] * 0.8, canvas["y"] + canvas["cssH"] * 0.7))
            check(d3 > 20, f"layer eye off re-renders the stage: changed by {d3:.1f}/255")
            cdp.eval("document.querySelector('.layer-row button.eye')?.click(); 1"); time.sleep(0.3)
            cdp.eval("(() => { const b = [...document.querySelectorAll('button')].find(b => (b.getAttribute('title') || b.getAttribute('aria-label') || '').startsWith('Brushes')); b && b.click(); return !!b })()")
            time.sleep(0.5)
            cdp.shot(OUT / f"{mode}{tag}-brushes.png")
            print(f"     Brushes tab screenshot: {OUT / f'{mode}{tag}-brushes.png'}")
        elif mode == "tour":
            failures += tour(cdp, tmp)
        elif mode == "cmpdiag":
            failures += cmpdiag(cdp)
        elif mode == "brush":
            failures += brush_check(cdp)
        elif mode == "selection":
            failures += selection_check(cdp)
        elif mode == "grid":
            failures += grid(cdp)
        elif mode == "psd":
            (tmp / "dl").mkdir(exist_ok=True)
            failures += psd_check(cdp, tmp)
        else:
            print(f"unknown mode {mode!r}"); return 2
        try:
            cdp.call("Browser.close")
        except Exception:
            pass
        print(f"\n{mode}{tag}: {'all checks passed' if not failures else f'{len(failures)} FAILED'} · screenshots in {OUT}")
        return 1 if failures else 0
    finally:
        try:
            api("POST", "/shutdown")
        except Exception:
            pass
        try:
            orch.wait(timeout=15)
        except Exception:
            orch.kill()
        if edge:
            try:
                edge.wait(timeout=10)
            except Exception:
                edge.kill()


if __name__ == "__main__":
    raise SystemExit(main())
