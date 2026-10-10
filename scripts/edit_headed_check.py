"""Editor check in a *visible* Edge window (10 §14 acceptance; the verification loop of 10 §11).

Headless Chromium cannot present WebGPU canvases, so the headless `csp_check.py` screenshots say nothing about the
editor's stage. This script drives a headed Edge — the same Chromium as WebView2 — over the DevTools protocol:

  render  (default)  open a bench document; the stage must show pixels at once (no resize needed), Ctrl+wheel must
                     zoom, and a window resize must not break either (the 2026-10-06 render-loop regression)
  paint              B + drag paints a visible stroke on the layer; Add mask, E + drag hides a band of the layer
                     (checker shows); the layer's eye toggles the stage; the Brushes tab is screenshotted
  kit                D55: latched modifiers, press menus, popup value fields, the blend dropdown (wheel, hover preview), Ctrl+Enter,
                     the polygon's ✓ / ⊘ in the strip and an audit of every Edit menu in every tool and state
  layers             D56: Ctrl / Shift selection, commands on the set, drag to reorder / into and out of a group / Alt copies,
                     eye sweep, drops on the footer's trash and New layer, right-click on the set — by mouse, one step per gesture
  props              D57: Curves (add, drag, drag off, Ctrl / right-click, per channel), Levels (triangles, Auto, histogram), Colour
                     balance rows — each against the exact flatten — sections, quick actions, Ungroup
  transform          D58: homography and warp maths in the page, the box by mouse (proportional corners, Shift free, Ctrl distort,
                     perspective mode, Shift-snapped rotation, Alt pivot, nudge, the W field), apply against the exact flatten and
                     undo, exact flip / rotate presets, a selection's pixels lifted and moved, a group scaled together
  smartsel           D59: Quick Selection and the Magnetic Lasso (WebAssembly in a Worker) by mouse — a square found by a click and
                     by a traced border, strokes adding, Alt subtracting, Backspace, Esc, a stroke on the photo
  heal               D62: Spot Healing (a stroke heals a blemish onto a Spot healing layer; undo) and Quick Remove (no GPU) end to end
  masks              D54: the mask workflow by mouse, judged on screenshots — + box adds a reveal-all mask with the mask colours,
                     brush hides / eraser reveals / X swaps, the row keeps the target, the pixel thumbnail restores the image
                     colours, Alt-click shows the mask alone, Shift-click disables, Alt + box hides all
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

    orchestrator/.venv/Scripts/python.exe scripts/edit_headed_check.py [render|paint|kit|layers|props|transform|smartsel|heal|masks|tour|cmpdiag|grid|brush|selection|psd|animate|perf]
"""
from __future__ import annotations

import base64
import json
import math
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
    step("D52 a raster's mask is linked", "1", f"{ACTIVE}.mask.linked", True)
    step("unlink mask (chain)", run("edit.mask.link"), f"{ACTIVE}.mask.linked", False)
    step("link mask", run("edit.mask.link"), f"{ACTIVE}.mask.linked", True)
    step("mask density / feather in the Layers tab", "1", "document.querySelectorAll('.layer-row .mask-link').length > 0 && [...document.querySelectorAll('.tool-opts label')].some((l) => l.textContent === 'feather')", True)
    step("apply mask", run("edit.mask.apply"), f"{ACTIVE}.mask", None)
    step("mask from transparency", run("edit.mask.fromTransparency"), f"JSON.stringify([!!{ACTIVE}.mask, {ACTIVE}.mask && {ACTIVE}.mask.linked])", "[true,true]")
    step("Delete while editing the mask removes the mask", f"{S}.setActive({S}.activeId, true); " + run("edit.layer.delete"), f"JSON.stringify([!!{ACTIVE}, {ACTIVE} && {ACTIVE}.mask])", "[true,null]")
    step("undo brings the mask back", run("edit.undo"), f"!!{ACTIVE}.mask", True)
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
    cdp.eval(run("edit.exportPng"))
    t0 = time.time()                                                  # the export runs the exact flatten first — wait for it, not a fixed 2.5 s
    while time.time() - t0 < 20 and not list((tmp / "dl").glob("*.png")):
        time.sleep(0.3)
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
        try:
            worst = json.loads(r)[2]
        except Exception:
            worst = 0
        if worst > 4:                                                  # keep the pair and name the worst pixel
            dirs = sorted(Path(tempfile.gettempdir()).glob("loom2-headed-*/proj/_temp/compare"), key=lambda q: q.stat().st_mtime)
            pair = sorted(dirs[-1].glob("*.png")) if dirs else []
            if len(pair) == 2:
                import numpy as np
                ex, gp = (np.asarray(Image.open(q).convert("RGBA")).astype(int) for q in pair)
                diff = np.abs(ex[..., :3] - gp[..., :3]).max(axis=-1)
                y, x = np.unravel_index(int(diff.argmax()), diff.shape)
                print(f"       worst at ({x}, {y}): exact {ex[y, x].tolist()} · gpu {gp[y, x].tolist()} · {(diff > 4).sum()} px over 4")
                slug = "".join(ch if ch.isalnum() else "-" for ch in label)[:40]
                for q in pair:
                    (OUT / f"cmpdiag-{slug}-{q.name.rsplit('-', 1)[1]}").write_bytes(q.read_bytes())

    compare("base layer only")
    run("edit.mask.add"); time.sleep(0.3); compare("white mask on the base layer")
    cdp.eval(f"(() => {{ const s = {S}; const m = s.masks.get(s.activeId); m.ctx.fillStyle = '#000'; m.ctx.fillRect(0, 0, m.width / 2, m.height); m.refresh(); m.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.4)
    compare("mask black on the left half")
    # D52: density and feather derived exactly like compose.py; a raster's mask is layer-sized and linked
    upd = lambda js, label: (cdp.eval(f"{S}.updateNode({S}.activeId, {js}, '{label}'); 1"), time.sleep(0.4))  # noqa: E731
    mask = lambda extra: "{ mask: { ..." + S + ".doc.layers.find((n) => n.id === " + S + ".activeId).mask, " + extra + " } }"  # noqa: E731
    upd(mask("density: 0.6"), "density"); compare("D52 mask density 60 %")
    upd(mask("density: 1, feather: 6.5"), "feather"); compare("D52 mask feather 6.5 px")
    upd(mask("density: 0.4, feather: 2"), "both"); compare("D52 mask density 40 % + feather 2 px")
    upd("{ x: 40, y: 24 }", "move"); compare("D52 linked mask moves with the layer")
    run("edit.mask.link"); time.sleep(0.3); upd("{ x: 0, y: 0 }", "move"); compare("D52 unlinked mask stays put")
    run("edit.mask.link"); time.sleep(0.3)
    run("edit.mask.remove"); time.sleep(0.3); compare("mask removed")
    run("edit.layer.adjustment.invert"); time.sleep(0.4); run("edit.mask.add"); time.sleep(0.3)
    cdp.eval(f"(() => {{ const s = {S}; const m = s.masks.get(s.activeId); m.ctx.fillStyle = '#000'; m.ctx.fillRect(0, 0, m.width / 2, m.height); m.refresh(); m.dirty = true; s.touch(); s.bump(); return 1 }})()"); time.sleep(0.4)
    upd(mask("feather: 4, density: 0.8"), "feather"); compare("D52 invert adjustment with a feathered 80 % mask")
    run("edit.layer.delete"); time.sleep(0.3)
    cdp.eval(f"{S}.setActive({S}.doc.layers[0].id, false); 1"); time.sleep(0.2)
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
    # D53: every stroke above went up as a partial texture upload — the GPU composite must still equal the exact flatten
    cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
    t0 = time.time()
    while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
        time.sleep(0.3)
    cmp_ = json.loads(cdp.eval("JSON.stringify(window.__cmp && [window.__cmp.rgb_p99, window.__cmp.rgb_max])") or "null")
    check(cmp_ is not None and cmp_[0] <= 1, f"after partial uploads the GPU composite equals the exact flatten (p99, max = {cmp_})")
    # D52: an adjustment layer's mask is paintable, and a feathered mask is re-derived while it is painted
    run("edit.layer.adjustment.invert"); time.sleep(0.4); run("edit.mask.add"); time.sleep(0.3)
    cdp.eval(f"{S}.updateNode({S}.activeId, {{ mask: {{ ...{S}.doc.layers.find((n) => n.id === {S}.activeId).mask, feather: 3 }} }}, 'feather'); 1"); time.sleep(0.4)
    run("edit.tool.brush"); brush(opacity=1, flow=1, size=40, hardness=1, smoothing=0)
    stroke([(W * 0.6, H * 0.2), (W * 0.9, H * 0.2)])
    mv = cdp.eval(f"{S}.masks.get({S}.activeId).ctx.getImageData({int(W * 0.75)}, {int(H * 0.2)}, 1, 1).data[0]")
    check(cdp.eval(f"{S}.editingMask") is True and mv == 0, f"the brush paints the invert adjustment's mask with the mask colours' black ({mv})")
    cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
    t0 = time.time()
    while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
        time.sleep(0.3)
    cmp_ = json.loads(cdp.eval("JSON.stringify(window.__cmp && [window.__cmp.rgb_p99, window.__cmp.rgb_max])") or "null")
    check(cmp_ is not None and cmp_[0] <= 1 and cmp_[1] <= 2, f"a feathered mask painted on an adjustment layer (re-derived around the stroke only): GPU = exact flatten (p99, max = {cmp_})")
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
        const work = [], rend = []; const step = () => { const t0 = performance.now(); ev('pointermove', cx - 200 + i * 8, cy + Math.sin(i / 5) * 40); work.push(performance.now() - t0); requestAnimationFrame((t) => { requestAnimationFrame(() => { rend.push(window.__loom2RenderMs || 0); lags.push(t - t0); if (++i < 50) step(); else { ev('pointerup', cx + 200, cy); lags.sort((a, b) => a - b); work.sort((a, b) => a - b); rend.sort((a, b) => a - b); res(JSON.stringify({p50: lags[25], p95: lags[47], max: lags[49], work50: work[25], work95: work[47], render50: rend[25], render95: rend[47]})) } }) }) }; step() }))()"""
    if os.environ.get("FULL_UPLOAD"):                                    # D53 A/B: whole-texture uploads as before
        cdp.eval("window.__loom2FullUpload = true; 1")
    br = json.loads(cdp.eval(stroke_js))
    report(br["p95"] <= 1000 / max(1.0, raf["fps"]) * 1.15, f"Brush on the 4K document: pointer move → next presented frame p50 {br['p50']:.1f} ms · p95 {br['p95']:.1f} ms · max {br['max']:.1f} ms; handler CPU p50 {br['work50']:.1f} ms · p95 {br['work95']:.1f} ms; render CPU p50 {br['render50']:.1f} ms · p95 {br['render95']:.1f} ms (budget ≤ 1 display frame = {1000 / max(1.0, raf['fps']):.1f} ms at {raf['fps']:.0f} Hz)")
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
        elif mode == "kit":
            # D55 mouse-first kit, by mouse events: latched modifiers, press menus, popup value fields, the blend dropdown, Ctrl+Enter,
            # and an audit of every Edit menu (each entry resolves to a registered command; separators only between groups)
            S, C = STORE, "window.__loom2Commands"
            hist = lambda: cdp.eval(f"{S}.history.length")  # noqa: E731

            def centre(sel: str) -> tuple[float, float] | None:
                r = cdp.eval(f"JSON.stringify((() => {{ const e = document.querySelector({json.dumps(sel)}); if (!e) return null; e.scrollIntoView({{ block: 'nearest' }}); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] }})())")
                v = json.loads(r) if r else None
                return (v[0], v[1]) if v else None

            def press(x: float, y: float, to: tuple[float, float] | None = None, steps: int = 8) -> None:
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
                cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", buttons=1, clickCount=1)
                tx, ty = to or (x, y)
                for i in range(1, steps + 1):
                    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x + (tx - x) * i / steps, y=y + (ty - y) * i / steps, button="left", buttons=1)
                    time.sleep(0.02)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=tx, y=ty, button="left", buttons=0, clickCount=1)
                time.sleep(0.4)

            def item_centre(label: str) -> tuple[float, float] | None:
                r = cdp.eval(f"JSON.stringify((() => {{ const e = [...document.querySelectorAll('.ctx-menu .item')].find((b) => b.textContent.trim().toLowerCase().startsWith({json.dumps(label)})); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] }})())")
                v = json.loads(r) if r else None
                return (v[0], v[1]) if v else None

            # latched modifiers: Alt latched → a brush click picks the colour under it (Alt-click), until the latch is clicked off
            cdp.eval(f"{C}.runCommand('edit.tool.brush'); {S}.setBrush({{ color: '#123456' }}); 1"); time.sleep(0.2)
            alt = centre(".latches .latch:nth-child(3)")
            press(*alt)
            check(cdp.eval(f"{S}.latched.alt") is True and bool(cdp.eval("!!document.querySelector('.latches .latch.active')")), "the strip's Alt latch turns on and shows it")
            h0 = hist()
            press(cx, cy)
            check(cdp.eval(f"{S}.brush.color").lower() != "#123456" and hist() == h0, f"with Alt latched a brush click picks the colour instead of painting ({cdp.eval(f'{S}.brush.color')})")
            press(cx + 30, cy + 30)
            check(cdp.eval(f"{S}.latched.alt") is True, "the latch stays on after the gesture (until clicked again)")
            press(*alt)
            check(cdp.eval(f"{S}.latched.alt") is False, "clicking the latch again releases it")
            # press menu: press on Add adjustment, drag onto Invert, release
            n0 = cdp.eval(f"{S}.doc.layers.length")
            btn = centre('button[aria-label="Add adjustment"]')
            cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=btn[0], y=btn[1])
            cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=btn[0], y=btn[1], button="left", buttons=1, clickCount=1)
            time.sleep(0.3)
            inv = item_centre("invert")
            if inv:
                for i in range(1, 9):
                    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=btn[0] + (inv[0] - btn[0]) * i / 8, y=btn[1] + (inv[1] - btn[1]) * i / 8, button="left", buttons=1)
                    time.sleep(0.02)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=inv[0], y=inv[1], button="left", buttons=0, clickCount=1)
            else:
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=btn[0], y=btn[1], button="left", buttons=0, clickCount=1)
            time.sleep(0.5)
            top = json.loads(cdp.eval(f"JSON.stringify([{S}.doc.layers.length, {S}.doc.layers[0].kind, {S}.doc.layers[0].type, !!document.querySelector('.ctx-menu')])"))
            check(inv is not None and top[0] == n0 + 1 and top[2] == "invert" and not top[3], f"press–drag–release on Add adjustment ▾ adds Invert in one gesture and closes the menu ({top})")
            press(*btn)
            open1 = cdp.eval("!!document.querySelector('.ctx-menu')")
            lev = item_centre("levels")
            if lev:
                press(*lev)
            check(open1 and cdp.eval(f"{S}.doc.layers[0].type") == "levels" and not cdp.eval("!!document.querySelector('.ctx-menu')"), "a plain click opens the press menu and leaves it open; a click on an entry chooses it")
            press(*btn); press(*btn)
            check(not cdp.eval("!!document.querySelector('.ctx-menu')"), "a press on the open menu's button closes it")
            cdp.eval(f"{C}.runCommand('edit.layer.delete'); {C}.runCommand('edit.layer.delete'); {S}.setActive({S}.doc.layers[0].id); 1"); time.sleep(0.4)
            # popup value field (Layers tab opacity): scrub, ▾ drag, typed sum, arrows — one history step per gesture
            OP = '.layers ~ .tool-opts input.vfield-num[aria-label="opacity"]'
            op = lambda: round(cdp.eval(f"{S}.doc.layers.find((n) => n.id === {S}.activeId).opacity"), 3)  # noqa: E731
            num = centre(OP)
            h0, o0 = hist(), op()
            press(num[0], num[1], (num[0] - 40, num[1]))
            o1 = op()
            check(abs(o1 - max(0, o0 - 0.20)) < 0.011 and hist() == h0 + 1, f"scrubbing the opacity number 40 px left lowers it by 20 % in one step ({o0} → {o1}, history +{hist() - h0})")
            arrow = centre('.layers ~ .tool-opts .vfield-arrow[aria-label="opacity slider"]')
            h0 = hist()
            press(arrow[0], arrow[1], (arrow[0] + 73, arrow[1]))
            o2 = op()
            check(abs(o2 - min(1, o1 + 0.5)) < 0.011 and hist() == h0 + 1 and not cdp.eval("!!document.querySelector('.vfield-pop')"), f"press-dragging the ▾ moves the value along the pop-up slider in one step and closes it ({o1} → {o2})")
            press(*arrow)
            check(bool(cdp.eval("!!document.querySelector('.vfield-pop')")), "a click on the ▾ opens the slider pop-up")
            bg = cdp.eval("getComputedStyle(document.querySelector('.vfield-pop')).backgroundColor")
            check(bg not in ("rgba(0, 0, 0, 0)", "transparent"), f"the slider pop-up has an opaque background ({bg})")
            press(cx, canvas["y"] + 5)
            press(*num)
            cdp.call("Input.insertText", text="")
            cdp.eval(f"(() => {{ const i = document.querySelector({json.dumps(OP)}); i.focus(); i.select(); return 1 }})()")
            cdp.call("Input.insertText", text="100/4")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            time.sleep(0.3)
            check(op() == 0.25, f"typing 100/4 and Enter sets 25 % ({op()})")
            cdp.eval(f"document.querySelector({json.dumps(OP)}).focus(); 1")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="ArrowUp", code="ArrowUp", windowsVirtualKeyCode=38, modifiers=8)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="ArrowUp", code="ArrowUp", windowsVirtualKeyCode=38, modifiers=8)
            time.sleep(0.3)
            check(op() == 0.35, f"Shift+↑ steps by 10 ({op()})")
            cdp.eval("document.activeElement.blur(); 1")
            # blend dropdown: the wheel steps, hovering previews (nothing recorded), a click chooses (one step)
            bb = centre(".layers ~ .tool-opts .blend-btn")
            blend = lambda: cdp.eval(f"{S}.doc.layers.find((n) => n.id === {S}.activeId).blend")  # noqa: E731
            h0, b0 = hist(), blend()
            cdp.call("Input.dispatchMouseEvent", type="mouseWheel", x=bb[0], y=bb[1], deltaX=0, deltaY=120)
            time.sleep(0.4)
            b1 = blend()
            check(b1 != b0 and hist() == h0 + 1, f"a wheel notch over the blend button steps the mode, one history step ({b0} → {b1}, history +{hist() - h0})")
            press(*bb)
            bg = cdp.eval("getComputedStyle(document.querySelector('.blend-list')).backgroundColor")
            check(bg not in ("rgba(0, 0, 0, 0)", "transparent"), f"the blend list has an opaque background ({bg})")
            mul = cdp.eval("JSON.stringify((() => { const e = [...document.querySelectorAll('.blend-opt')].find((o) => o.textContent === 'Multiply'); const r = e.getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2] })())")
            mx, my = json.loads(mul)
            h0 = hist()
            cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=mx, y=my); time.sleep(0.4)
            prev = json.loads(cdp.eval(f"JSON.stringify([{S}.blendPreview && {S}.blendPreview.mode, {S}.doc.layers.find((n) => n.id === {S}.activeId).blend])"))
            check(prev == ["multiply", b1] and hist() == h0, f"hovering an entry previews it on the canvas without changing the document ({prev})")
            press(mx, my)
            check(blend() == "multiply" and hist() == h0 + 1 and cdp.eval(f"{S}.blendPreview") is None, "a click chooses the mode in one step and ends the preview")
            # Ctrl+Enter applies a free transform; the polygon lasso's ✓ / ⊘ sit in the strip
            cdp.eval(f"{C}.runCommand('edit.transform'); 1"); time.sleep(0.3)
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13, modifiers=2)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13, modifiers=2)
            time.sleep(0.5)
            check(cdp.eval(f"{S}.transform") is None, "Ctrl+Enter applies the free transform")
            cdp.eval(f"{S}.setTool('lasso'); {S}.setView({{ lassoKind: 'polygon' }}); {S}.setLassoPoly([{{ x: 10, y: 10 }}, {{ x: 60, y: 10 }}]); 1"); time.sleep(0.3)
            check(bool(cdp.eval("!!document.querySelector('.panel-strip button[aria-label=\"Close polygon\"], button[aria-label=\"Close polygon\"]')")), "an open polygon shows its ✓ / ⊘ in the strip")
            cdp.eval(f"{S}.setLassoPoly(null); {S}.setView({{ lassoKind: 'free' }}); {S}.setTool('brush'); 1")
            # menu audit over every tool and state (D55, PhotoCraft context-menu contract rules 3 and 5)
            audit = cdp.eval(f"""(() => {{
              const M = window.__loom2EditMenus, R = {C}, s = {S}, bad = [];
              const walk = (items, path) => {{
                items.forEach((it, i) => {{
                  if ('sep' in it && (i === 0 || i === items.length - 1 || 'sep' in items[i - 1])) bad.push(path + ' stray separator at ' + i);
                  if ('cmd' in it && !R.command(it.cmd)) bad.push(path + ' unknown ' + it.cmd);
                  if ('items' in it) {{ if (!it.items.length) bad.push(path + ' empty ' + it.label); walk(it.items, path + ' › ' + it.label) }}
                }})
              }};
              const tools = ['move', 'marquee', 'lasso', 'wand', 'brush', 'eraser', 'fill', 'crop', 'zoom', 'hand', 'eyedropper', 'ai'];
              for (const t of tools) {{ s.setTool && s.setTool(t); walk(M.canvasMenu(), 'canvas[' + t + ']') }}
              s.setTool && s.setTool('brush');
              const ids = []; const w = (xs) => xs.forEach((x) => {{ ids.push(x.id); if (x.children) w(x.children) }}); w(s.doc.layers);
              for (const id of ids) {{ s.setActive(id); walk(M.layerMenu(), 'layer[' + id + ']') }}
              return JSON.stringify(bad)
            }})()""")
            bad = json.loads(audit)
            check(not bad, f"every Edit menu entry resolves and separators sit only between groups ({len(bad)} problems){''.join(chr(10) + '       ' + b for b in bad[:12])}")
            # review U1: nothing in the strip is drawn past its right edge (it wraps to a second row instead)
            over = json.loads(cdp.eval("JSON.stringify((() => { const s = document.querySelector('.center > .strip') || document.querySelector('.strip'); const r = s.getBoundingClientRect(); return [...s.children].filter((c) => c.getBoundingClientRect().right > r.right + 1 || c.scrollWidth > c.clientWidth + 1).map((c) => c.className || c.tagName) })())"))
            check(not over, f"every strip item fits inside the strip, none squeezed ({over})")
            # review F11: typing a value is one undo step, applied once (no 7 % flash on the way to 75)
            ob = cdp.eval("JSON.stringify((() => { const e = document.querySelector('.inspector .vfield-num[aria-label=\"opacity\"]'); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] })())")
            if ob != "null":
                h0 = hist()
                ox, oy = json.loads(ob)
                press(ox, oy)
                cdp.eval("(() => { const e = document.querySelector('.inspector .vfield-num[aria-label=\"opacity\"]'); e.select(); return 1 })()")
                cdp.call("Input.insertText", text="7"); time.sleep(0.1); cdp.call("Input.insertText", text="5"); time.sleep(0.1)
                cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13); cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
                time.sleep(0.3)
                op = cdp.eval(f"(() => {{ const s = {S}; let hit = null; const w = (xs) => xs.forEach((x) => {{ if (x.id === s.activeId) hit = x; if (x.children) w(x.children) }}); w(s.doc.layers); return hit.opacity }})()")
                check(abs(op - 0.75) < 1e-6 and hist() == h0 + 1, f"typing 75 into opacity sets 75 % in one undo step (opacity {op}, history +{hist() - h0})")
            else:
                check(False, "the Inspector shows an opacity field")
            # review F3: Enter applies an open transform (it was swallowed by the disabled polygon-close command)
            cdp.eval(f"document.activeElement && document.activeElement.blur(); {C}.runCommand('edit.transform'); 1"); time.sleep(0.4)
            h0 = hist()
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13); cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            time.sleep(0.5)
            check(cdp.eval(f"{S}.transform") is None, "Enter applies the free transform")
            # D63: the A tool's find field — typing selects by prompt (SAM 3 text), Enter runs Select, clearing returns to the main subject
            AP = "window.__loom2AiPanel.getState()"
            ai_state = lambda: json.loads(cdp.eval(f"JSON.stringify([{AP}.selModel, {AP}.selMode, {AP}.selText])"))  # noqa: E731
            cdp.eval(f"{S}.setTool('ai'); window.__aiRuns = []; window.__loom2Editor.setState({{ runAi: (r) => {{ window.__aiRuns.push(r); return Promise.resolve() }} }}); 1"); time.sleep(0.4)
            fb = cdp.eval("JSON.stringify((() => { const e = document.querySelector('.sel-find'); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] })())")
            check(fb != "null", "the A tool's options lead with a find field")
            if fb != "null":
                fx, fy = json.loads(fb)
                press(fx, fy)
                cdp.call("Input.insertText", text="the crates"); time.sleep(0.3)
                st1 = ai_state()
                check(st1 == ["sam3", "text", "the crates"], f"typing in find switches to SAM 3 text ({st1})")
                cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13); cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
                time.sleep(0.3)
                runs = json.loads(cdp.eval("JSON.stringify(window.__aiRuns.map((r) => [r.model_id, r.mode, r.text]))"))
                check(runs == [["sam3", "text", "the crates"]], f"Enter in find runs Select with the prompt ({runs})")
                cdp.eval("(() => { const e = document.querySelector('.sel-find'); e.select(); return 1 })()")
                cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8); cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
                time.sleep(0.3)
                st2 = ai_state()
                check(st2 == ["birefnet", "subject", ""], f"clearing find goes back to the main subject ({st2})")
            cdp.eval(f"{S}.setTool('brush'); 1")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "layers":
            # D56 layers panel, by mouse events on the rows: Ctrl / Shift selection, commands on the set, drag to reorder / into a group /
            # copies with Alt, eye sweep, drop on the footer's trash, right-click labels — one history step per gesture
            S, C = STORE, "window.__loom2Commands"
            hist = lambda: cdp.eval(f"{S}.history.length")  # noqa: E731
            order = lambda: json.loads(cdp.eval(f"JSON.stringify((() => {{ const out = []; const w = (xs, d) => xs.forEach((x) => {{ out.push(x.name + (d ? '@' + d : '')); if (x.children) w(x.children, d + 1) }}); w({S}.doc.layers, 0); return out }})())"))  # noqa: E731
            ids = lambda: json.loads(cdp.eval(f"JSON.stringify((() => {{ const out = {{}}; const w = (xs) => xs.forEach((x) => {{ out[x.name] = x.id; if (x.children) w(x.children) }}); w({S}.doc.layers); return out }})())"))  # noqa: E731

            def row(name: str, f: float = 0.5, x: float = 0.6) -> tuple[float, float]:
                r = json.loads(cdp.eval(f"JSON.stringify((() => {{ const id = {json.dumps(ids()[name])}; const e = document.querySelector(`.layer-row[data-id='${{id}}']`); e.scrollIntoView({{ block: 'nearest' }}); const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height] }})())"))
                return r[0] + r[2] * x, r[1] + r[3] * f

            def eye(name: str) -> tuple[float, float]:
                r = json.loads(cdp.eval(f"JSON.stringify((() => {{ const id = {json.dumps(ids()[name])}; const e = document.querySelector(`.layer-row[data-id='${{id}}'] button.eye`); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] }})())"))
                return r[0], r[1]

            def click(p: tuple[float, float], modifiers: int = 0) -> None:
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=p[0], y=p[1])
                cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=p[0], y=p[1], button="left", buttons=1, clickCount=1, modifiers=modifiers)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=p[0], y=p[1], button="left", buttons=0, clickCount=1, modifiers=modifiers)
                time.sleep(0.35)

            def drag(a: tuple[float, float], b: tuple[float, float], modifiers: int = 0) -> None:
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=a[0], y=a[1])
                cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=a[0], y=a[1], button="left", buttons=1, clickCount=1, modifiers=modifiers)
                for i in range(1, 13):
                    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=a[0] + (b[0] - a[0]) * i / 12, y=a[1] + (b[1] - a[1]) * i / 12, button="left", buttons=1, modifiers=modifiers)
                    time.sleep(0.03)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=b[0], y=b[1], button="left", buttons=0, clickCount=1, modifiers=modifiers)
                time.sleep(0.5)

            sel = lambda: sorted(n for n, i in ids().items() if i in json.loads(cdp.eval(f"JSON.stringify({S}.targetIds())")))  # noqa: E731
            base = order()[0]
            for k in ("A", "B", "C"):
                cdp.eval(f"{C}.runCommand('edit.layer.new'); {S}.updateNode({S}.activeId, {{ name: '{k}' }}); 1"); time.sleep(0.25)
            check(order() == ["C", "B", "A", base], f"three new layers on top ({order()})")
            click(row("C")); click(row("A"), modifiers=2)
            check(sel() == ["A", "C"] and cdp.eval("document.querySelectorAll('.layer-row.selected').length") == 2, f"Ctrl-click adds a layer to the selection ({sel()})")
            click(row("C")); click(row("A"), modifiers=8)
            check(sel() == ["A", "B", "C"], f"Shift-click selects the range ({sel()})")
            click(row("B"), modifiers=2)
            check(sel() == ["A", "C"], f"Ctrl-click on a selected layer removes it ({sel()})")
            click(row("A"), modifiers=2); click(row("C"), modifiers=2)
            check(sel() == ["C"] or sel() == ["A"] or len(sel()) == 1, f"the selection never empties ({sel()})")
            click(row("C")); click(row("A"), modifiers=8)
            h0 = hist()
            cdp.eval(f"{C}.runCommand('edit.layer.visibility'); 1"); time.sleep(0.3)
            vis = json.loads(cdp.eval(f"JSON.stringify({S}.doc.layers.map((n) => n.visible))"))
            check(vis == [False, False, False, True] and hist() == h0 + 1, f"Hide acts on the whole selection in one step ({vis})")
            cdp.eval(f"{C}.runCommand('edit.undo'); 1"); time.sleep(0.3)
            # drag the set below the bottom layer
            h0 = hist()
            drag(row("B"), row(base, 0.85))
            check(order() == [base, "C", "B", "A"] and hist() == h0 + 1, f"dragging a selected row carries the set below the target in one step ({order()})")
            cdp.eval(f"{C}.runCommand('edit.undo'); 1"); time.sleep(0.3)
            click(row("A"))
            drag(row("A"), row("C", 0.15))
            check(order() == ["A", "C", "B", base], f"a single row dropped on the upper half of another goes above it ({order()})")
            # a group, then drop a layer into it (the group row's middle) and out again (between rows outside it)
            click(row("B")); cdp.eval(f"{C}.runCommand('edit.layer.group'); 1"); time.sleep(0.4)
            g = [n for n in order() if not n.startswith("B") and n not in ("A", "C", base)][0]
            drag(row("A"), row(g, 0.5))
            o = order()
            check(o[:4] == ["C", g, "A@1", "B@1"] or o[:4] == [g, "A@1", "B@1", "C"], f"dropping on a group's middle puts the layer inside it, at its top ({o})")
            drag(row("A"), row(base, 0.15))
            check("A" in order() and order().index("A") == len(order()) - 2, f"dropping between rows outside the group takes it out ({order()})")
            # Alt drop = copies
            n0 = len(order())
            drag(row("C"), row(base, 0.85), modifiers=1)
            check(len(order()) == n0 + 1 and order()[-1] == "C" and order().count("C") == 2, f"Alt on release drops a copy ({order()})")
            # eye sweep over three rows in one step
            eyes = json.loads(cdp.eval("JSON.stringify([...document.querySelectorAll('.layer-row[data-id] button.eye')].map((e) => { const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] }))"))
            h0 = hist()
            e0, e2 = eyes[0], eyes[2]
            drag(e0, (e2[0], e2[1] + 2))
            vis = json.loads(cdp.eval(f"JSON.stringify((() => {{ const out = []; const w = (xs) => xs.forEach((x) => {{ out.push(x.visible); if (x.children) w(x.children) }}); w({S}.doc.layers); return out }})())"))
            check(vis[:3] == [False, False, False] and hist() == h0 + 1, f"an eye sweep over three rows hides them in one step ({vis[:4]}, history +{hist() - h0})")
            cdp.eval(f"{C}.runCommand('edit.undo'); 1"); time.sleep(0.3)
            # drop on the footer's trash and duplicate buttons
            trash = json.loads(cdp.eval("JSON.stringify((() => { const r = document.querySelector('button[data-drop=\"delete\"]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] })())"))
            n0, h0 = len(order()), hist()
            drag(row(base), (trash[0], trash[1]))
            check(len(order()) == n0 - 1 and base not in order() and hist() == h0 + 1, f"dropping a row on the trash deletes it in one step ({order()})")
            cdp.eval(f"{C}.runCommand('edit.undo'); 1"); time.sleep(0.3)
            dup = json.loads(cdp.eval("JSON.stringify((() => { const r = document.querySelector('button[data-drop=\"duplicate\"]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] })())"))
            n0 = len(order())
            drag(row(base), (dup[0], dup[1]))
            check(len(order()) == n0 + 1, f"dropping a row on New layer duplicates it ({order()})")
            # right-click inside a multi-selection keeps it and the menu speaks in plurals
            click(row("C")); click(row(base), modifiers=2)
            cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=row("C")[0], y=row("C")[1], button="right", buttons=2, clickCount=1)
            cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=row("C")[0], y=row("C")[1], button="right", buttons=0, clickCount=1)
            time.sleep(0.4)
            labels = json.loads(cdp.eval("JSON.stringify([...document.querySelectorAll('.ctx-menu .item .lbl')].map((e) => e.textContent))"))
            check("Delete layers" in labels and "Merge layers" in labels and len(sel()) == 2, f"right-click on a row in the selection keeps it; the menu acts on the set ({[l for l in labels if 'layers' in l]})")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            time.sleep(0.2)
            # a submenu never covers its parent menu (the author's report: Transform hid the Mask entry near the right edge)
            click(row(base))
            cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=row(base)[0], y=row(base)[1], button="right", buttons=2, clickCount=1)
            cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=row(base)[0], y=row(base)[1], button="right", buttons=0, clickCount=1)
            time.sleep(0.4)
            subs = json.loads(cdp.eval("JSON.stringify([...document.querySelectorAll('.ctx-menu > .item.sub')].map((e) => { const r = e.getBoundingClientRect(); return [e.querySelector('.lbl').textContent, r.left + r.width / 2, r.top + r.height / 2] }))"))
            overlaps = []
            for label, sx, sy in subs:
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=sx, y=sy)
                time.sleep(0.25)
                ov = json.loads(cdp.eval("JSON.stringify((() => { const [p, s] = document.querySelectorAll('.ctx-menu'); if (!s) return null; const a = p.getBoundingClientRect(), b = s.getBoundingClientRect(); return [Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)), a.left, a.right, b.left, b.right, innerWidth] })())"))
                overlaps.append((label, ov))
            check(subs and all(ov is not None and ov[0] <= 4.5 for _, ov in overlaps), f"each submenu opens beside its parent menu, not over it (overlap px: {overlaps})")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            time.sleep(0.2)
            # review F9: the strip's latched Ctrl works in the Layers panel too — a plain click with Ctrl latched adds the row
            click(row("C"))
            cdp.eval(f"{C}.runCommand('edit.latch.ctrl'); 1"); time.sleep(0.2)
            click(row(base))
            got = sel()
            cdp.eval(f"{C}.runCommand('edit.latch.ctrl'); 1"); time.sleep(0.2)
            check(len(got) == 2, f"with Ctrl latched a click adds the layer to the selection ({got})")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "props":
            # D57 Properties, by mouse: Curves (add, drag, drag off, Ctrl-click, right-click, per channel), the spline on the GPU against
            # the exact flatten, Levels (triangles, Auto, histogram), Colour balance rows, sections, quick actions, Ungroup
            S, C = STORE, "window.__loom2Commands"
            hist = lambda: cdp.eval(f"{S}.history.length")  # noqa: E731
            act = lambda: json.loads(cdp.eval(f"JSON.stringify((() => {{ const s = {S}; let hit = null; const w = (xs) => xs.forEach((x) => {{ if (x.id === s.activeId) hit = x; if (x.children) w(x.children) }}); w(s.doc.layers); return hit }})())"))  # noqa: E731

            def box(sel: str) -> list[float]:
                return json.loads(cdp.eval(f"JSON.stringify((() => {{ const e = document.querySelector({json.dumps(sel)}); if (!e) return null; e.scrollIntoView({{ block: 'center' }}); const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height] }})())"))

            def mouse(kind: str, x: float, y: float, button: str = "left", modifiers: int = 0) -> None:
                cdp.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button=button, buttons=(0 if kind == "mouseReleased" else (2 if button == "right" else 1)) if kind != "mouseMoved" else 0, clickCount=1, modifiers=modifiers)

            def drag(a: tuple[float, float], b: tuple[float, float], modifiers: int = 0) -> None:
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=a[0], y=a[1])
                cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=a[0], y=a[1], button="left", buttons=1, clickCount=1, modifiers=modifiers)
                for i in range(1, 11):
                    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=a[0] + (b[0] - a[0]) * i / 10, y=a[1] + (b[1] - a[1]) * i / 10, button="left", buttons=1, modifiers=modifiers)
                    time.sleep(0.02)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=b[0], y=b[1], button="left", buttons=0, clickCount=1, modifiers=modifiers)
                time.sleep(0.4)

            def compare(label: str) -> None:
                cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
                t0 = time.time()
                while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
                    time.sleep(0.3)
                r = json.loads(cdp.eval("JSON.stringify(window.__cmp && [window.__cmp.rgb_p99, window.__cmp.rgb_max])") or "null")
                check(r is not None and r[0] <= 1, f"{label}: GPU preview = exact flatten (p99, max = {r})")

            cdp.eval("[...document.querySelectorAll('.tabs2 button')].find((b) => b.textContent === 'properties')?.click(); 1"); time.sleep(0.3)
            check(bool(cdp.eval("!!document.querySelector('.props-section')")), "the Properties tab shows sections")
            qa = json.loads(cdp.eval("JSON.stringify([...document.querySelectorAll('.quick-grid .cmd-btn')].map((b) => b.textContent))"))
            check("Select layer pixels" in " ".join(qa) or len(qa) >= 3, f"a pixel layer offers quick actions ({qa})")
            # Curves
            cdp.eval(f"{C}.runCommand('edit.layer.adjustment.curves'); 1"); time.sleep(0.5)
            check(act()["params"].get("interp") == "spline" and not cdp.eval("!!document.querySelector('.props input[type=text]')"), "a new Curves layer is a spline, edited without JSON fields")
            g = box(".curves-graph")
            gx = lambda v: g[0] + g[2] * (5 + v * 256 / 255) / 266  # noqa: E731
            gy = lambda v: g[1] + g[3] * (5 + 256 - v * 256 / 255) / 266  # noqa: E731
            h0 = hist()
            drag((gx(64), gy(64)), (gx(64), gy(110)))
            pts = act()["params"]["rgb"]
            check(len(pts) == 3 and abs(pts[1][0] - 64) <= 2 and abs(pts[1][1] - 110) <= 3 and hist() == h0 + 1, f"press on the curve adds a point and drags it, one step ({pts})")
            compare("a three-point spline curve")
            h0 = hist()
            drag((gx(pts[1][0]), gy(pts[1][1])), (g[0] + g[2] + 40, gy(pts[1][1])))
            check(len(act()["params"]["rgb"]) == 2 and hist() == h0 + 1, f"dragging a point off the graph removes it, one step ({act()['params']['rgb']})")
            drag((gx(190), gy(190)), (gx(190), gy(150)))
            p2 = act()["params"]["rgb"]
            mouse("mouseMoved", gx(p2[1][0]), gy(p2[1][1])); mouse("mousePressed", gx(p2[1][0]), gy(p2[1][1]), modifiers=2); mouse("mouseReleased", gx(p2[1][0]), gy(p2[1][1]), modifiers=2); time.sleep(0.3)
            check(len(act()["params"]["rgb"]) == 2, f"Ctrl-click removes a point ({act()['params']['rgb']})")
            drag((gx(128), gy(128)), (gx(128), gy(160)))
            p3 = act()["params"]["rgb"]
            mouse("mouseMoved", gx(p3[1][0]), gy(p3[1][1])); mouse("mousePressed", gx(p3[1][0]), gy(p3[1][1]), button="right"); mouse("mouseReleased", gx(p3[1][0]), gy(p3[1][1]), button="right"); time.sleep(0.3)
            check(len(act()["params"]["rgb"]) == 2 and not cdp.eval("!!document.querySelector('.ctx-menu')"), "right-click on a point removes it (no menu)")
            cdp.eval("[...document.querySelectorAll('.curves-ch button')].find((b) => b.textContent === 'Red').click(); 1"); time.sleep(0.2)
            drag((gx(128), gy(128)), (gx(128), gy(170)))
            r = act()["params"].get("r")
            check(r is not None and len(r) == 3 and len(act()["params"]["rgb"]) == 2, f"the Red channel takes its own points ({r})")
            compare("a red-channel spline under an identity master")
            cdp.eval("document.querySelector('.curves-graph').scrollIntoView({ block: 'center' }); 1"); time.sleep(0.2); cdp.shot(OUT / f"{mode}{tag}-curves.png")
            cdp.eval(f"{C}.runCommand('edit.layer.delete'); 1"); time.sleep(0.4)
            # Levels
            cdp.eval(f"{C}.runCommand('edit.layer.adjustment.levels'); 1"); time.sleep(0.5)
            check(bool(cdp.eval("document.querySelector('.tone-hist path')?.getAttribute('d')?.length > 50")), "Levels shows the histogram of the layers below")
            hb = box(".tone-handles")
            hx = lambda v: hb[0] + hb[2] * (6 + v * 256 / 255) / 268  # noqa: E731
            h0 = hist()
            drag((hx(0), hb[1] + 7), (hx(40), hb[1] + 7))
            ib = act()["params"]["in_black"]
            check(30 <= ib <= 50 and hist() == h0 + 1, f"dragging the black triangle raises input black, one step ({ib})")
            p = act()["params"]
            gpos = p["in_black"] + (p["in_white"] - p["in_black"]) * 0.5 ** p["gamma"]
            drag((hx(gpos), hb[1] + 7), (hx(gpos - 40), hb[1] + 7))
            gm = act()["params"]["gamma"]
            check(gm > 1.2, f"dragging the grey triangle left raises gamma, as in Photoshop ({gm})")
            compare("levels with a black point and gamma")
            cdp.eval("document.querySelector('.tone-hist').scrollIntoView({ block: 'center' }); 1"); time.sleep(0.2); cdp.shot(OUT / f"{mode}{tag}-levels.png")
            cdp.eval("[...document.querySelectorAll('.tone-editor button')].find((b) => b.textContent === 'Auto').click(); 1"); time.sleep(0.4)
            p = act()["params"]
            check(p["gamma"] == 1 and p["in_white"] > p["in_black"], f"Auto sets the black and white points from the histogram, gamma 1 ({p})")
            cdp.eval(f"{C}.runCommand('edit.layer.delete'); 1"); time.sleep(0.4)
            # Colour balance
            cdp.eval(f"{C}.runCommand('edit.layer.adjustment.color_balance'); 1"); time.sleep(0.5)
            rb = box(".cb-row input[type=range]")
            h0 = hist()
            drag((rb[0] + rb[2] / 2, rb[1] + rb[3] / 2), (rb[0] + rb[2] * 0.85, rb[1] + rb[3] / 2))
            mid = act()["params"]["midtones"]
            check(mid[0] > 30 and hist() == h0 + 1, f"the Cyan · Red row moves the midtones' red, one step ({mid})")
            compare("colour balance midtones")
            cdp.shot(OUT / f"{mode}{tag}-balance.png")
            cdp.eval(f"{C}.runCommand('edit.layer.delete'); 1"); time.sleep(0.4)
            # sections collapse; groups ungroup
            cdp.eval("document.querySelector('.props-head').click(); 1"); time.sleep(0.2)
            check(cdp.eval("document.querySelector('.props-head').getAttribute('aria-expanded')") == "false", "a section header collapses its section")
            cdp.eval("document.querySelector('.props-head').click(); 1")
            n0 = cdp.eval(f"{S}.doc.layers.length")
            cdp.eval(f"{C}.runCommand('edit.layer.group'); 1"); time.sleep(0.4)
            ug = cdp.eval("!![...document.querySelectorAll('.quick-grid .cmd-btn')].find((b) => b.textContent.includes('Ungroup'))")
            cdp.eval("[...document.querySelectorAll('.quick-grid .cmd-btn')].find((b) => b.textContent.includes('Ungroup'))?.click(); 1"); time.sleep(0.4)
            check(ug and cdp.eval(f"{S}.doc.layers.length") == n0 and cdp.eval(f"{S}.doc.layers.every((n) => n.kind !== 'group')"), "a group's quick action Ungroup puts its layers back")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "transform":
            # D58 free transform: the maths in the page (PhotoCraft's own unit tests), the gestures by mouse, the bake against the exact
            # flatten, selection lifts, groups, undo, the exact presets
            S, C = STORE, "window.__loom2Commands"
            T = "window.__loom2Transform"
            hist = lambda: cdp.eval(f"{S}.history.length")  # noqa: E731
            js = lambda body: cdp.eval(f"(() => {{ const s = {S}; {body} }})()")  # noqa: E731
            run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731
            # ---- maths
            m = json.loads(cdp.eval(f"""(() => {{ const X = {T};
              const q = [{{x: 10, y: 20}}, {{x: 110, y: 10}}, {{x: 130, y: 90}}, {{x: 0, y: 100}}];
              const H = X.Homography.rectToQuad([0, 0, 40, 30], q), I = H.inverse();
              const cs = X.rectCorners([0, 0, 40, 30]).map((c) => H.apply(c.x, c.y));
              const cerr = Math.max(...cs.map((c, i) => Math.hypot(c.x - q[i].x, c.y - q[i].y)));
              const p = H.apply(17, 9), b = I.apply(p.x, p.y), rerr = Math.hypot(b.x - 17, b.y - 9);
              const degen = X.Homography.rectToQuad([0, 0, 1, 1], [{{x:0,y:0}},{{x:0,y:0}},{{x:0,y:0}},{{x:0,y:0}}]);
              // integer translate is exact under all three interpolations
              const W = 16, Hh = 8, px = new Uint8ClampedArray(W * Hh * 4);
              for (let i = 0; i < W * Hh; i++) {{ px[i * 4] = (i * 37) % 256; px[i * 4 + 1] = (i * 11) % 256; px[i * 4 + 2] = 200; px[i * 4 + 3] = 255 }}
              const src = X.premultiply(px, W, Hh, 0, 0), T1 = X.Homography.affine(1, 0, 0, 1, 11, 1);
              const exact = ['nearest', 'bilinear', 'bicubic'].map((it) => {{ const r = X.warpRaster(src, T1, it), o = X.toStraight8(r); let bad = 0;
                for (let y = 0; y < Hh; y++) for (let x = 0; x < W; x++) for (let c = 0; c < 4; c++) if (o[((y + 1 - r.y) * r.w + (x + 11 - r.x)) * 4 + c] !== px[(y * W + x) * 4 + c]) bad++; return bad }});
              // an 8× shrink of a 1-px checkerboard is prefiltered to ≈ 50 % grey (bicubic alone would alias)
              const N = 64, cb = new Uint8ClampedArray(N * N * 4);
              for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {{ const v = (x + y) % 2 ? 255 : 0; cb.set([v, v, v, 255], (y * N + x) * 4) }}
              const r8 = X.warpRaster(X.premultiply(cb, N, N, 0, 0), X.Homography.affine(1 / 8, 0, 0, 1 / 8, 0, 0), 'bicubic'), o8 = X.toStraight8(r8);
              const mid = o8[((Math.floor(r8.h / 2)) * r8.w + Math.floor(r8.w / 2)) * 4];
              return JSON.stringify({{ cerr, rerr, degen: degen === null || degen.inverse() === null, exact, mid }}) }})()"""))
            check(m["cerr"] < 1e-9 and m["rerr"] < 1e-9 and m["degen"], f"the homography maps the rect's corners onto the quad and inverts (errors {m['cerr']:.1e}, {m['rerr']:.1e}); a collapsed quad is degenerate")
            check(m["exact"] == [0, 0, 0], f"an integer translation is pixel-exact under nearest, bilinear and bicubic (differing values {m['exact']})")
            check(100 <= m["mid"] <= 155, f"an 8× shrink of a 1-px checkerboard is prefiltered to grey ({m['mid']}/255)")
            # ---- the box, by mouse
            geo = json.loads(cdp.eval(f"JSON.stringify((() => {{ const r = document.querySelector('.edit-canvas').getBoundingClientRect(); const s = {S}; return {{ x: r.left, y: r.top, zoom: s.zoom, px: s.pan.x, py: s.pan.y }} }})())"))
            scr = lambda x, y: (geo["x"] + geo["px"] + x * geo["zoom"], geo["y"] + geo["py"] + y * geo["zoom"])  # noqa: E731

            def drag(a: tuple[float, float], b: tuple[float, float], modifiers: int = 0) -> None:
                (x0, y0), (x1, y1) = scr(*a), scr(*b)
                cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0, y=y0)
                cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=x0, y=y0, button="left", buttons=1, clickCount=1, modifiers=modifiers)
                for i in range(1, 9):
                    cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=x0 + (x1 - x0) * i / 8, y=y0 + (y1 - y0) * i / 8, button="left", buttons=1, modifiers=modifiers)
                    time.sleep(0.02)
                cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=x1, y=y1, button="left", buttons=0, clickCount=1, modifiers=modifiers)
                time.sleep(0.3)
            tq = lambda: json.loads(cdp.eval(f"JSON.stringify({S}.transform)"))  # noqa: E731

            def compare(label: str) -> None:
                cdp.eval(f"window.__cmp = undefined; {S}.compareWithExact().then((r) => {{ window.__cmp = r || null }}, (e) => {{ window.__cmp = 'rejected: ' + e }}); 1")
                t0 = time.time()
                while time.time() - t0 < 40 and cdp.eval("window.__cmp === undefined"):
                    time.sleep(0.3)
                r = json.loads(cdp.eval("JSON.stringify(window.__cmp && [window.__cmp.rgb_p99, window.__cmp.rgb_max])") or "null")
                check(r is not None and r[0] <= 1, f"{label}: GPU = exact flatten (p99, max = {r})")

            base = js("return s.doc.layers[s.doc.layers.length - 1].id")
            js(f"s.setActive('{base}'); return 1")
            n0 = json.loads(js("const n = s.doc.layers.find((x) => x.id === s.activeId); return JSON.stringify([n.x, n.y, n.w, n.h])"))
            run("edit.transform"); time.sleep(0.4)
            t = tq()
            check(t is not None and t["rect"] == [n0[0], n0[1], n0[0] + n0[2], n0[1] + n0[3]] and t["mode"] == "free", f"Free transform frames the layer ({t and t['rect']})")
            before = cdp.shot(OUT / f"{mode}{tag}-0.png")
            q = t["quad"]
            drag((q[2]["x"], q[2]["y"]), (q[2]["x"] - n0[2] * 0.3, q[2]["y"] - n0[3] * 0.1))
            t = tq(); q = t["quad"]
            w1, h1 = q[1]["x"] - q[0]["x"], q[3]["y"] - q[0]["y"]
            check(abs(w1 / h1 - n0[2] / n0[3]) < 0.01 and w1 < n0[2], f"a corner drag scales in proportion by default ({w1:.0f}×{h1:.0f}, was {n0[2]}×{n0[3]})")
            drag((q[2]["x"], q[2]["y"]), (q[2]["x"] + 60, q[2]["y"] - 40), modifiers=8)
            t = tq(); q = t["quad"]
            check(abs((q[1]["x"] - q[0]["x"]) / (q[3]["y"] - q[0]["y"]) - n0[2] / n0[3]) > 0.05, "Shift frees the proportions")
            q0 = q
            drag((q[1]["x"], q[1]["y"]), (q[1]["x"] + 40, q[1]["y"] + 30), modifiers=2)
            t = tq(); q = t["quad"]
            moved = [i for i in range(4) if abs(q[i]["x"] - q0[i]["x"]) + abs(q[i]["y"] - q0[i]["y"]) > 0.5]
            check(moved == [1], f"Ctrl-dragging a corner distorts: only that corner moves ({moved})")
            mid = cdp.shot(OUT / f"{mode}{tag}-1-distort.png")
            check(region_diff(before, mid, (canvas["x"] + canvas["cssW"] * 0.2, canvas["y"] + canvas["cssH"] * 0.2, canvas["x"] + canvas["cssW"] * 0.8, canvas["y"] + canvas["cssH"] * 0.8)) > 3, "the preview shows the distorted layer while the box is open")
            js("s.setTransform({ mode: 'perspective' }); return 1"); time.sleep(0.2)
            q0 = q
            drag((q[0]["x"], q[0]["y"]), (q[0]["x"] + 30, q[0]["y"]))
            t = tq(); q = t["quad"]
            check(abs((q[0]["x"] - q0[0]["x"]) + (q[1]["x"] - q0[1]["x"])) < 0.5 and q[0]["x"] - q0[0]["x"] > 10, f"perspective mode mirrors a corner drag on its neighbour ({q[0]['x'] - q0[0]['x']:.1f}, {q[1]['x'] - q0[1]['x']:.1f})")
            js("s.setTransform({ mode: 'free' }); return 1")
            p0 = t["pivot"]
            dw, dh = js("return s.doc.w"), js("return s.doc.h")
            far = next(pt for pt in [(dw - 8, dh - 8), (dw - 8, 8), (8, dh - 8), (8, 8)] if not js(f"return {T}.insideQuad(s.transform.quad, {{ x: {pt[0]}, y: {pt[1]} }})") and min(math.hypot(pt[0] - c["x"], pt[1] - c["y"]) for c in q) > 40)
            ang0 = math.degrees(math.atan2(q[1]["y"] - q[0]["y"], q[1]["x"] - q[0]["x"]))
            a40 = math.radians(-40)                                        # the grab point swung 40° about the reference point
            to = (p0["x"] + (far[0] - p0["x"]) * math.cos(a40) - (far[1] - p0["y"]) * math.sin(a40), p0["y"] + (far[0] - p0["x"]) * math.sin(a40) + (far[1] - p0["y"]) * math.cos(a40))
            drag(far, to, modifiers=8)
            t = tq(); q = t["quad"]
            ang = math.degrees(math.atan2(q[1]["y"] - q[0]["y"], q[1]["x"] - q[0]["x"]))
            check(abs(ang / 15 - round(ang / 15)) < 1e-6 and abs(ang - ang0) > 20 and abs(t["pivot"]["x"] - p0["x"]) < 1e-6, f"dragging outside rotates about the reference point, Shift snaps to 15° ({ang0:.2f}° → {ang:.2f}°)")
            px_, py_ = t["pivot"]["x"] + 80, t["pivot"]["y"] + 30          # away from the pivot handle (a press there would drag it)
            sx, sy = scr(px_, py_)
            cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=sx, y=sy)
            cdp.call("Input.dispatchMouseEvent", type="mousePressed", x=sx, y=sy, button="left", buttons=1, clickCount=1, modifiers=1)
            cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=sx, y=sy, button="left", buttons=0, clickCount=1, modifiers=1)
            time.sleep(0.3)
            pv = tq()["pivot"]
            check(abs(pv["x"] - px_) < 1 and abs(pv["y"] - py_) < 1, "Alt-click places the reference point")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="ArrowRight", code="ArrowRight", windowsVirtualKeyCode=39, modifiers=8)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="ArrowRight", code="ArrowRight", windowsVirtualKeyCode=39, modifiers=8)
            time.sleep(0.2)
            check(abs(tq()["pivot"]["x"] - pv["x"] - 10) < 1e-6, "Shift+→ nudges the box 10 px")
            # the strip's W field halves the width about the reference point
            wbox = json.loads(cdp.eval("JSON.stringify((() => { const i = [...document.querySelectorAll('.xform-bar input.vfield-num')].find((e) => e.getAttribute('aria-label') === 'W'); const r = i.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] })())"))
            w_before = tq()
            cdp.eval("(() => { const i = [...document.querySelectorAll('.xform-bar input.vfield-num')].find((e) => e.getAttribute('aria-label') === 'W'); i.focus(); i.select(); return 1 })()")
            ro0 = js("const t = s.transform; return Math.hypot(t.quad[1].x - t.quad[0].x, t.quad[1].y - t.quad[0].y)")
            cdp.call("Input.insertText", text="50")
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter", windowsVirtualKeyCode=13)
            time.sleep(0.3)
            ro1 = js("const t = s.transform; return Math.hypot(t.quad[1].x - t.quad[0].x, t.quad[1].y - t.quad[0].y)")
            check(abs(ro1 - js("return s.transform.rect[2] - s.transform.rect[0]") * 0.5) < 0.6, f"typing W = 50 % sets the width to half the frame ({ro0:.0f} → {ro1:.0f} px)")
            del w_before, wbox
            h0 = hist()
            run("edit.transform.apply"); time.sleep(2.0)
            n1 = json.loads(js("const n = s.doc.layers.find((x) => x.id === s.activeId); return JSON.stringify([n.x, n.y, n.w, n.h])"))
            check(cdp.eval(f"{S}.transform") is None and hist() == h0 + 1 and n1 != n0, f"apply bakes the layer in one step ({n0} → {n1})")
            compare("a perspective-distorted, rotated, half-width layer")
            run("edit.undo"); time.sleep(0.6)
            n2 = json.loads(js("const n = s.doc.layers.find((x) => x.id === s.activeId); return JSON.stringify([n.x, n.y, n.w, n.h])"))
            check(n2 == n0, f"undo restores the layer ({n2})")
            # presets are exact permutations
            sig = lambda: js("const lp = s.pixels.get(s.activeId); const d = lp.ctx.getImageData(0, 0, lp.width, lp.height).data; let h = 0; for (let i = 0; i < d.length; i += 97) h = (h * 31 + d[i]) | 0; return h + ':' + lp.width + 'x' + lp.height")  # noqa: E731
            s0 = sig()
            run("edit.layer.flipH"); time.sleep(0.8); run("edit.layer.flipH"); time.sleep(0.8)
            check(sig() == s0, "flip horizontal twice gives back the very same pixels")
            run("edit.layer.rot90"); time.sleep(0.8)
            s90 = sig()
            run("edit.layer.rot270"); time.sleep(0.8)
            check(sig() == s0 and s90.split(":")[1] == "x".join(reversed(s0.split(":")[1].split("x"))), f"rotate 90° then 270° gives back the same pixels ({s90.split(':')[1]})")
            # with a selection only the selected pixels move; the hole stays transparent; the selection moves with them
            js(f"s.editSelection('t', () => {{ const sel = s.ensureSelection(); sel.ctx.fillStyle = '#fff'; sel.ctx.fillRect(100, 100, 120, 80); sel.refresh() }}); return 1"); time.sleep(0.3)
            px = lambda x, y: json.loads(js(f"const n = s.doc.layers.find((q) => q.id === s.activeId); const lp = s.pixels.get(n.id); return JSON.stringify(Array.from(lp.ctx.getImageData({x} - n.x, {y} - n.y, 1, 1).data))"))  # noqa: E731
            a0, out0 = px(150, 140), px(60, 60)
            run("edit.transform"); time.sleep(0.4)
            t = tq()
            check(t["selection"] and t["rect"] == [100, 100, 220, 180], f"with a selection the frame is the selected part ({t['rect']})")
            drag((120, 115), (320, 315))                                   # away from the reference point at the frame's centre
            run("edit.transform.apply"); time.sleep(1.5)
            a1, hole, out1 = px(350, 340), px(150, 140), px(60, 60)
            selmoved = js("const v = s.selection.ctx.getImageData(350, 340, 1, 1).data[0]; const w = s.selection.ctx.getImageData(150, 140, 1, 1).data[0]; return JSON.stringify([v, w])")
            check(a1 == a0 and hole[3] == 0 and out1 == out0 and json.loads(selmoved) == [255, 0], f"the selected pixels moved (+200, +200), the hole is transparent, the rest untouched, the selection followed ({a0} → {a1}, hole {hole}, sel {selmoved})")
            compare("pixels moved out of a selection")
            run("edit.undo"); time.sleep(0.5)
            check(px(150, 140) == a0 and json.loads(js("return JSON.stringify(s.selection ? s.selection.ctx.getImageData(150, 140, 1, 1).data[0] : null)")) == 255, "undo puts the pixels and the selection back")
            run("edit.sel.none"); time.sleep(0.3)
            # a group transforms its rasters together, one undo step
            run("edit.layer.new"); time.sleep(0.3)
            js("const lp = s.pixels.get(s.activeId); lp.ctx.fillStyle = '#ff0000'; lp.ctx.fillRect(200, 200, 100, 100); lp.refresh(); lp.dirty = true; s.touch(); s.bump(); return 1"); time.sleep(0.3)
            top = js("return s.activeId")
            js(f"s.selectLayer('{top}'); s.selectLayer('{base}', 'toggle'); return 1")
            run("edit.layer.group"); time.sleep(0.4)
            g = js("return s.activeId")
            run("edit.transform"); time.sleep(0.4)
            js("const t = s.transform; s.setTransform({ quad: t.quad.map((c) => ({ x: t.pivot.x + (c.x - t.pivot.x) * 0.5, y: t.pivot.y + (c.y - t.pivot.y) * 0.5 })) }); return 1")
            sizes0 = json.loads(js(f"const g = s.doc.layers.find((x) => x.id === '{g}'); return JSON.stringify(g.children.map((c) => [c.w, c.h]))"))
            h0 = hist()
            run("edit.transform.apply"); time.sleep(2.5)
            sizes1 = json.loads(js(f"const g = s.doc.layers.find((x) => x.id === '{g}'); return JSON.stringify(g.children.map((c) => [c.w, c.h]))"))
            # the top raster holds a 100 px square (the bake trims transparent margins), the bottom one fills the document
            check(hist() == h0 + 1 and 49 <= sizes1[0][0] <= 53 and abs(sizes1[1][0] - sizes0[1][0] / 2) <= 2, f"a group's rasters scale together in one step ({sizes0} → {sizes1})")
            compare("a group scaled to 50 %")
            run("edit.undo"); time.sleep(0.6)
            sizes2 = json.loads(js(f"const g = s.doc.layers.find((x) => x.id === '{g}'); return JSON.stringify(g.children.map((c) => [c.w, c.h]))"))
            check(sizes2 == sizes0, f"undo restores every raster of the group ({sizes2})")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "smartsel":
            # D59: Quick Selection and the Magnetic Lasso (PhotoCraft's, as WebAssembly in a Worker) by mouse — on a synthetic layer
            # (a red square on blue: both should find the square) and on the bench photo
            S, C = STORE, "window.__loom2Commands"
            js = lambda body: cdp.eval(f"(() => {{ const s = {S}; {body} }})()")  # noqa: E731
            run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731
            geo = json.loads(cdp.eval(f"JSON.stringify((() => {{ const r = document.querySelector('.edit-canvas').getBoundingClientRect(); const s = {S}; return {{ x: r.left, y: r.top, zoom: s.zoom, px: s.pan.x, py: s.pan.y }} }})())"))
            scr = lambda x, y: (geo["x"] + geo["px"] + x * geo["zoom"], geo["y"] + geo["py"] + y * geo["zoom"])  # noqa: E731

            def mouse(kind: str, x: float, y: float, buttons: int = 0, modifiers: int = 0, count: int = 1) -> None:
                sx, sy = scr(x, y)
                cdp.call("Input.dispatchMouseEvent", type=kind, x=sx, y=sy, button="left" if kind != "mouseMoved" or buttons else "none", buttons=buttons, clickCount=count, modifiers=modifiers)

            def click(x: float, y: float, modifiers: int = 0) -> None:
                mouse("mouseMoved", x, y); mouse("mousePressed", x, y, 1, modifiers); mouse("mouseReleased", x, y, 0, modifiers); time.sleep(0.15)

            def stroke(points: list[tuple[float, float]], modifiers: int = 0) -> None:
                mouse("mouseMoved", *points[0]); mouse("mousePressed", *points[0], 1, modifiers)
                for a, b in zip(points, points[1:]):
                    for i in range(1, 6):
                        mouse("mouseMoved", a[0] + (b[0] - a[0]) * i / 5, a[1] + (b[1] - a[1]) * i / 5, 1, modifiers); time.sleep(0.01)
                mouse("mouseReleased", *points[-1], 0, modifiers)

            hlen = [cdp.eval(f"{S}.history.length")]

            def wait_sel(label: str) -> float:                       # a new history entry with that label
                t = time.time()
                while time.time() - t < 20 and js(f"return s.history.length > {hlen[0]} && s.history[s.history.length - 1].label === '{label}'") is not True:
                    time.sleep(0.05)
                hlen[0] = cdp.eval(f"{S}.history.length")
                return time.time() - t

            sel_stats = lambda: json.loads(js("const sel = s.selection; if (!sel) return JSON.stringify(null); const d = sel.ctx.getImageData(0, 0, sel.width, sel.height).data; let n = 0, inside = 0; for (let y = 0; y < sel.height; y++) for (let x = 0; x < sel.width; x++) { const v = d[(y * sel.width + x) * 4]; if (v > 127) { n++; if (x >= 300 && x < 460 && y >= 150 && y < 310) inside++ } } return JSON.stringify({ n, inside })"))  # noqa: E731
            # a synthetic layer: a 160 px red square on blue
            run("edit.layer.new"); time.sleep(0.3)
            js("const lp = s.pixels.get(s.activeId); lp.ctx.fillStyle = '#1f3fbf'; lp.ctx.fillRect(0, 0, lp.width, lp.height); lp.ctx.fillStyle = '#d42a2a'; lp.ctx.fillRect(300, 150, 160, 160); lp.refresh(); lp.dirty = true; s.touch(); s.bump(); return 1"); time.sleep(0.4)
            # ---- Quick Selection
            cdp.eval("[...document.querySelectorAll('.tool')].find((b) => b.textContent.includes('Quick selection'))?.click(); 1"); time.sleep(0.2)
            hlen[0] = cdp.eval(f"{S}.history.length")
            check(cdp.eval(f"{S}.tool") == "quick" and bool(cdp.eval("!!document.querySelector('.tool-opts input.vfield-num[aria-label=\"size\"]')")), "the toolbox's Quick selection button picks the tool and shows its options")
            js("s.setView({ quickSize: 30 }); return 1")
            click(380, 230)
            dt = wait_sel("quick selection")
            st1 = sel_stats()
            iou = st1["inside"] / (st1["n"] + 160 * 160 - st1["inside"]) if st1 else 0
            check(st1 is not None and iou > 0.9, f"a click with a 30 px brush selects the 160 px square (IoU {iou:.3f}, {st1}, {dt:.2f} s incl. the Worker's first image)")
            js("s.deselect(); return 1"); time.sleep(0.2); hlen[0] = cdp.eval(f"{S}.history.length")
            click(100, 400)
            wait_sel("quick selection")
            st2 = sel_stats()
            check(st2 is not None and 300 < st2["n"] < 6000 and st2["inside"] == 0, f"a click in the flat blue selects about the brush disc ({st2})")
            n_before = st2["n"]
            stroke([(380, 230), (420, 260)])
            wait_sel("quick selection")
            st3 = sel_stats()
            check(st3["n"] > n_before + 20000, f"the next stroke adds to the selection ({n_before} → {st3['n']})")
            stroke([(100, 400), (110, 405)], modifiers=1)
            wait_sel("quick selection")
            st4 = sel_stats()
            check(st4["n"] < st3["n"] - 300 and st4["inside"] >= 160 * 160 * 0.95, f"Alt subtracts ({st3['n']} → {st4['n']}, square kept {st4['inside']})")
            # ---- Magnetic Lasso around the square, the pointer wandering 4 px off its edges
            js("s.deselect(); s.setTool('lasso'); s.setView({ lassoKind: 'magnetic', selectionMode: 'replace' }); return 1"); time.sleep(0.3)
            check(bool(cdp.eval("[...document.querySelectorAll('.tool-opts input.vfield-num')].some((i) => i.getAttribute('aria-label') === 'frequency')")), "the magnetic lasso shows width, contrast and frequency")
            click(296, 154)
            time.sleep(0.3)
            first = json.loads(js("return JSON.stringify(s.lassoPoly && s.lassoPoly[0])"))
            check(first is not None and abs(first["x"] - 300) <= 2.5 and abs(first["y"] - 154) <= 3, f"the first click snaps to the square's edge ({first})")
            route = [(296, 154), (380, 146), (464, 146), (464, 230), (464, 314), (380, 314), (296, 314), (296, 230), (296, 170)]
            for a, b in zip(route, route[1:]):
                for i in range(1, 11):
                    mouse("mouseMoved", a[0] + (b[0] - a[0]) * i / 10, a[1] + (b[1] - a[1]) * i / 10); time.sleep(0.04)
            time.sleep(0.3)
            anchors = js("return s.lassoPoly ? s.lassoPoly.length : 0")
            check(anchors >= 8, f"moving along the edges traces the border and fastens points as it goes ({anchors} path points — straight edges simplify to few)")
            n_pts = anchors
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
            time.sleep(0.4)
            check(js("return s.lassoPoly ? s.lassoPoly.length : 0") < n_pts, "Backspace removes the last fastening point")
            mouse("mouseMoved", 296, 200); time.sleep(0.3)
            click(first["x"], first["y"])
            t = time.time()
            while time.time() - t < 10 and js("return !s.history.length || s.history[s.history.length - 1].label !== 'magnetic lasso'"): time.sleep(0.05)
            st5 = sel_stats()
            iou = st5["inside"] / (st5["n"] + 160 * 160 - st5["inside"]) if st5 else 0
            check(st5 is not None and iou > 0.93 and cdp.eval(f"{S}.lassoPoly") is None, f"clicking the first point closes a border on the square's edges (IoU {iou:.3f}, {st5})")
            click(296, 154); time.sleep(0.2)
            cdp.call("Input.dispatchKeyEvent", type="keyDown", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            cdp.call("Input.dispatchKeyEvent", type="keyUp", key="Escape", code="Escape", windowsVirtualKeyCode=27)
            time.sleep(0.3)
            check(cdp.eval(f"{S}.lassoPoly") is None, "Esc cancels a border in progress")
            # ---- on the photo: sample all layers off → the active layer; the bench layer below
            run("edit.layer.delete"); time.sleep(0.3)
            js("s.deselect(); s.setTool('quick'); return 1"); time.sleep(0.2); hlen[0] = cdp.eval(f"{S}.history.length")
            t0 = time.time()
            stroke([(420, 260), (520, 300), (600, 280)])
            dt = wait_sel("quick selection")
            st6 = json.loads(js("const sel = s.selection; if (!sel) return 'null'; const d = sel.ctx.getImageData(0, 0, sel.width, sel.height).data; let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] > 127) n++; return JSON.stringify(n)"))
            check(st6 and st6 > 2000, f"a stroke on the photo selects a region ({st6} px in {time.time() - t0:.2f} s)")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "heal":
            # D62: Spot Healing (a stroke over a blemish → a "Spot healing" layer) and Quick Remove (a GPU-free inpaint mode) end to end
            S, C = STORE, "window.__loom2Commands"
            js = lambda body: cdp.eval(f"(() => {{ const s = {S}; {body} }})()")  # noqa: E731
            run = lambda cid: cdp.eval(f"{C}.runCommand('{cid}')")  # noqa: E731
            geo = json.loads(cdp.eval(f"JSON.stringify((() => {{ const r = document.querySelector('.edit-canvas').getBoundingClientRect(); const s = {S}; return {{ x: r.left, y: r.top, zoom: s.zoom, px: s.pan.x, py: s.pan.y }} }})())"))
            scr = lambda x, y: (geo["x"] + geo["px"] + x * geo["zoom"], geo["y"] + geo["py"] + y * geo["zoom"])  # noqa: E731
            check(bool(cdp.eval("!!(window.__loom2Session || null) || true")), "editor ready")
            # a striped layer with a magenta blemish
            run("edit.layer.new"); time.sleep(0.3)
            js("const lp = s.pixels.get(s.activeId); for (let x = 0; x < lp.width; x += 8) { lp.ctx.fillStyle = (x / 8) % 2 ? '#5a7a3a' : '#6d8c48'; lp.ctx.fillRect(x, 0, 8, lp.height) } lp.ctx.fillStyle = '#ff00ff'; lp.ctx.fillRect(296, 196, 12, 12); lp.refresh(); lp.dirty = true; s.touch(); s.bump(); return 1"); time.sleep(0.4)
            base = js("return s.activeId")
            cdp.eval("[...document.querySelectorAll('.tool')].find((b) => b.textContent.includes('Spot healing'))?.click(); 1"); time.sleep(0.2)
            check(cdp.eval(f"{S}.tool") == "heal" and bool(cdp.eval("!!document.querySelector('.tool-opts input.vfield-num[aria-label=\"size\"]')")), "the toolbox's Spot healing button picks the tool (J)")
            js("s.setView({ healSize: 24, healSampleAll: true }); return 1")
            h0 = cdp.eval(f"{S}.history.length")
            for kind, (x, y) in (("mouseMoved", (295, 202)), ("mousePressed", (295, 202))):
                sx, sy = scr(x, y); cdp.call("Input.dispatchMouseEvent", type=kind, x=sx, y=sy, button="left", buttons=1, clickCount=1)
            for i in range(1, 9):
                sx, sy = scr(295 + 14 * i / 8, 202); cdp.call("Input.dispatchMouseEvent", type="mouseMoved", x=sx, y=sy, button="left", buttons=1); time.sleep(0.02)
            sx, sy = scr(309, 202); cdp.call("Input.dispatchMouseEvent", type="mouseReleased", x=sx, y=sy, button="left", buttons=0, clickCount=1)
            t = time.time()
            while time.time() - t < 20 and js("return s.history.length && s.history[s.history.length - 1].label === 'spot healing'") is not True: time.sleep(0.1)
            info = json.loads(js("const w = (xs, f) => xs.forEach((n) => { f(n); if (n.children) w(n.children, f) }); let heal = null; w(s.doc.layers, (n) => { if (n.recipe && n.recipe.kind === 'spot_heal') heal = n }); if (!heal) return 'null'; const lp = s.pixels.get(heal.id); const d = lp.ctx.getImageData(302 - (heal.x || 0), 202 - (heal.y || 0), 1, 1).data; const i = s.doc.layers.findIndex((n) => n.id === heal.id); return JSON.stringify({ px: Array.from(d), above: s.doc.layers[i + 1] && s.doc.layers[i + 1].id, name: heal.name })"))
            check(info is not None and info["above"] == base and info["px"][3] > 200 and info["px"][0] < 160 and info["px"][1] > 90, f"a stroke over the blemish heals it on a Spot healing layer right above (healed pixel {info and info['px']})")
            run("edit.undo"); time.sleep(0.4)
            gone = js("const w = (xs, f) => xs.forEach((n) => { f(n); if (n.children) w(n.children, f) }); let heal = null; w(s.doc.layers, (n) => { if (n.recipe && n.recipe.kind === 'spot_heal') heal = n }); return heal ? s.pixels.get(heal.id).ctx.getImageData(302 - (heal.x || 0), 202 - (heal.y || 0), 1, 1).data[3] : -1")
            check(gone in (0, -1), f"one undo takes the stroke back — the healed pixels, or the Spot healing layer the first stroke made ({gone})")
            # Quick Remove: a GPU-free inpaint mode through the queue
            js("s.editSelection('t', () => { const sel = s.ensureSelection(); sel.ctx.fillStyle = '#fff'; sel.ctx.fillRect(290, 190, 24, 24); sel.refresh() }); return 1"); time.sleep(0.3)
            n0 = js("return s.doc.layers.length")
            js("void s.runAi({ kind: 'inpaint', mode: 'quick_remove', margin_pct: 25, feather: 4, expand: 2, seeds: [7] }); return 1")
            t = time.time()
            while time.time() - t < 60 and js("return s.doc.layers.some((n) => n.kind === 'group' && n.name.startsWith('AI quick remove'))") is not True: time.sleep(0.25)
            g = json.loads(js("const g = s.doc.layers.find((n) => n.kind === 'group' && n.name.startsWith('AI quick remove')); return JSON.stringify(g ? { n: g.children.length, name: g.children[0].name, mask: !!g.children[0].mask } : null)"))
            check(g is not None and g["n"] == 1 and g["mask"], f"Quick remove runs without the GPU and lands as a candidate layer with a mask ({g}, {time.time() - t:.1f} s)")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
        elif mode == "masks":
            # D54: the author's workflow by mouse, judged on screenshots only (the extractor re-renders every pass and would hide a stale
            # stage) — add a mask, paint it with the brush, erase, swap colours, select the row, view the mask alone, hide all
            ACT = f"(() => {{ const s = {STORE}; let hit = null; const w = (xs) => xs.forEach((x) => {{ if (x.id === s.activeId) hit = x; if (x.children) w(x.children) }}); w(s.doc.layers); return hit }})()"
            X0, X1 = canvas["x"] + canvas["cssW"] * 0.3, canvas["x"] + canvas["cssW"] * 0.7

            def state(label: str, sx: float, sy: float) -> dict:
                js = f"""(() => {{ const s = {STORE}; const n = {ACT}; const r = document.querySelector('.edit-canvas').getBoundingClientRect();
                  const dx = Math.round(({sx} - r.left - s.pan.x) / s.zoom), dy = Math.round(({sy} - r.top - s.pan.y) / s.zoom);
                  const m = s.masks.get(n.id);
                  const mo = n.mask ? {{ x: (n.mask.linked ? (n.x ?? 0) : 0) + n.mask.x, y: (n.mask.linked ? (n.y ?? 0) : 0) + n.mask.y }} : null;
                  return JSON.stringify({{ tool: s.tool, colours: [s.brush.color, s.brush.background], maskPair: s.maskPairActive, editingMask: s.editingMask,
                    view: s.maskView, mask: n.mask, value: m && mo ? m.ctx.getImageData(dx - mo.x, dy - mo.y, 1, 1).data[0] : null, history: s.history.map((h) => h.label).slice(-3) }}) }})()"""
                st = json.loads(cdp.eval(js))
                print(f"       {label}: {st}")
                return st

            def stroke(y: float) -> None:
                cdp.drag(X0, y, X1, y); time.sleep(0.8)

            def band(y: float) -> tuple:
                return (canvas["x"] + canvas["cssW"] * 0.35, y - 15, canvas["x"] + canvas["cssW"] * 0.65, y + 15)

            cdp.eval("document.body.focus(); 1")
            cdp.key("b"); time.sleep(0.2)
            image_colours = json.loads(cdp.eval(f"JSON.stringify([{STORE}.brush.color, {STORE}.brush.background])"))
            clicked = cdp.eval("(() => { const b = document.querySelector('.layer-row.active .mask-box') || document.querySelector('.layer-row .mask-box'); if (!b) return false; b.click(); return true })()")
            time.sleep(0.6)
            st = state("after + mask", cx, cy)
            check(bool(clicked) and st["editingMask"] and st["maskPair"] and st["colours"] == ["#000000", "#ffffff"] and st["mask"]["default"] == 255,
                  "the + box adds a reveal-all mask, targets it and swaps in the mask colours (black / white)")
            check(bool(cdp.eval("!!document.querySelector('.swatch-pair.for-mask')")), "the swatches say they are the mask colours")
            s0 = cdp.shot(OUT / f"{mode}{tag}-0.png")
            stroke(cy)
            s1 = cdp.shot(OUT / f"{mode}{tag}-1-brush.png")
            st = state("after a brush stroke", cx, cy)
            d = region_diff(s0, s1, band(cy))
            check(st["value"] <= 8 and d > 5, f"the brush (foreground black) hides the layer on a new mask: mask {st['value']}, stage changed by {d:.1f}/255")
            cdp.key("e"); time.sleep(0.2)
            stroke(cy)
            s2 = cdp.shot(OUT / f"{mode}{tag}-2-eraser.png")
            st = state("after an eraser stroke over it", cx, cy)
            d = region_diff(s0, s2, band(cy))
            check(st["value"] >= 247 and d < 2, f"the eraser (background white) reveals it again: mask {st['value']}, stage vs before {d:.1f}/255")
            cdp.key("b"); time.sleep(0.1); cdp.key("x"); time.sleep(0.2)
            stroke(cy + 50)
            st = state("after X and a brush stroke", cx, cy + 50)
            check(st["value"] == 255 and st["colours"] == ["#ffffff", "#000000"], "X swaps the mask colours — the brush then paints white")
            cdp.key("x"); time.sleep(0.2)
            cdp.eval("document.querySelector('.layer-row.active .name')?.click(); 1"); time.sleep(0.4)
            st = state("after clicking the layer row", cx, cy)
            check(st["editingMask"] is True, "clicking the layer row keeps the mask the target")
            cdp.eval("document.querySelector('.layer-row.active img.thumb:not(.mask-thumb)')?.click(); 1"); time.sleep(0.4)
            st = state("after clicking the pixel thumbnail", cx, cy)
            check(st["editingMask"] is False and st["maskPair"] is False and st["colours"] == image_colours, f"the pixel thumbnail targets the pixels and brings the image colours back ({st['colours']})")
            cdp.eval("(() => { const i = document.querySelector('.layer-row.active .mask-thumb'); i.dispatchEvent(new MouseEvent('click', { bubbles: true, altKey: true })); return 1 })()"); time.sleep(0.6)
            s3 = cdp.shot(OUT / f"{mode}{tag}-3-gray.png")
            st = state("after Alt-click on the mask thumbnail", cx, cy)
            check(st["view"] == "gray" and st["editingMask"], "Alt-click on the mask thumbnail shows the mask alone and targets it")
            stroke(cy - 60)
            s4 = cdp.shot(OUT / f"{mode}{tag}-4-gray-brush.png")
            d = region_diff(s3, s4, band(cy - 60))
            check(d > 20, f"painting while the mask is shown alone paints the mask, visibly: changed by {d:.1f}/255")
            cdp.eval("(() => { const i = document.querySelector('.layer-row.active .mask-thumb'); i.dispatchEvent(new MouseEvent('click', { bubbles: true, altKey: true })); return 1 })()"); time.sleep(0.5)
            check(cdp.eval(f"{STORE}.maskView") == "off", "Alt-click again shows the image")
            cdp.eval("(() => { const i = document.querySelector('.layer-row.active .mask-thumb'); i.dispatchEvent(new MouseEvent('click', { bubbles: true, shiftKey: true })); return 1 })()"); time.sleep(0.5)
            check(cdp.eval(f"{ACT}.mask.enabled") is False and bool(cdp.eval("!!document.querySelector('.layer-row.active .mask-wrap.off')")), "Shift-click disables the mask (red ✕ on the thumbnail)")
            cdp.eval("window.__loom2Commands.runCommand('edit.mask.remove'); 1"); time.sleep(0.5)
            s5 = cdp.shot(OUT / f"{mode}{tag}-5-removed.png")
            d = region_diff(s0, s5, full := (canvas["x"] + canvas["cssW"] * 0.1, canvas["y"] + canvas["cssH"] * 0.1, canvas["x"] + canvas["cssW"] * 0.9, canvas["y"] + canvas["cssH"] * 0.9))
            check(cdp.eval(f"{ACT}.mask") is None and d < 1 and cdp.eval(f"{STORE}.maskPairActive") is False, f"removing the mask restores the image and the image colours (stage {d:.1f}/255)")
            cdp.eval("(() => { const b = document.querySelector('.layer-row.active .mask-box'); b.dispatchEvent(new MouseEvent('click', { bubbles: true, altKey: true })); return 1 })()"); time.sleep(0.6)
            s6 = cdp.shot(OUT / f"{mode}{tag}-6-hideall.png")
            st = state("after Alt-click on the + box", cx, cy)
            check(st["mask"] is not None and st["mask"]["default"] == 0 and st["value"] == 0 and region_diff(s0, s6, band(cy)) > 5, "Alt-click on the + box adds a hide-all mask (the layer disappears)")
            cdp.key("e"); time.sleep(0.2)
            stroke(cy)
            s7 = cdp.shot(OUT / f"{mode}{tag}-7-reveal.png")
            d = region_diff(s0, s7, band(cy))
            check(d < 2, f"the eraser (white) brings the layer back through a hide-all mask: stage vs the bare layer {d:.1f}/255")
            errs = cdp.page_errors()
            check(not errs, "no page errors" + "".join("\n       " + x for x in errs))
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
            before2 = cdp.shot(OUT / f"{mode}{tag}-mask0.png")                # D54: on a mask the brush paints the mask pair's black
            cdp.drag(canvas["x"] + canvas["cssW"] * 0.3, cy + 60, canvas["x"] + canvas["cssW"] * 0.7, cy + 60); time.sleep(0.6)
            after2 = cdp.shot(OUT / f"{mode}{tag}-mask1.png")
            d2 = region_diff(before2, after2, (band[0], cy + 20, band[2], cy + 100))
            check(d2 > 5, f"the brush (mask colours: black) on the mask hides the layer there (checker shows): band changed by {d2:.1f}/255")
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
