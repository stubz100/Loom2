// D59: the Magnetic Lasso (PhotoCraft ui-egui magnetic_lasso_ui.rs @ b37bff98, MIT OR Apache-2.0 — behaviour ported; the tracing runs
// in the smart-select Worker). The first click snaps to the nearest edge; moving the pointer (button up or down) traces from the last
// fastening point to the pointer, guided by the pointer's trail; fastening points drop by distance along the traced border
// (8 + (100 − frequency) · 0.9 screen px); a click fastens the live segment, Alt-click a straight segment (Alt-drag: freehand);
// Backspace removes the last point; clicking the first point, Enter or a double-click closes (traced back to the start, or straight
// with Alt); Esc cancels. The closed border becomes the selection through the polygon lasso's commit.
import { useEditor } from '../editorStore'
import type { SelectionMode } from '../selectionOps'
import { snap, trace } from './client'
import { ensureDocImage } from './source'

type Pt = { x: number; y: number }
const dist = (a: Pt, b: Pt) => Math.hypot(a.x - b.x, a.y - b.y)
const length = (p: Pt[]) => p.reduce((s, q, i) => (i ? s + dist(p[i - 1], q) : 0), 0)
const flat = (p: Pt[]) => p.flatMap((q) => [q.x, q.y])
const pts = (a: number[]) => { const out: Pt[] = []; for (let i = 0; i + 1 < a.length; i += 2) out.push({ x: a[i], y: a[i + 1] }); return out }

class MagneticLasso {
  path: Pt[] = []
  anchors: number[] = []
  trail: Pt[] = []
  live: Pt[] = []
  hover: Pt | null = null
  mode: SelectionMode = 'replace'
  freehand = false
  private busy = false
  private want: Pt | null = null
  private chain: Promise<void> = Promise.resolve()
  onChange: () => void = () => {}

  get active() { return this.path.length > 0 }
  private settings() { const st = useEditor.getState(); return { width: st.magWidth, contrast: st.magContrast / 100 } }
  private zoom() { return Math.max(1e-3, useEditor.getState().zoom) }
  /** Distance along the border between automatic fastening points (document px; Frequency 57 ≈ 47 screen px). */
  private spacing() { const f = Math.min(100, Math.max(0, useEditor.getState().magFrequency)); return (8 + (100 - f) * 0.9) / this.zoom() }
  private closeRadius() { return 8 / this.zoom() }
  nearStart(p: Pt) { const r = this.closeRadius(); return this.active && dist(p, this.path[0]) <= r && length(this.path) + length(this.live) > 2 * r }
  private queue(f: () => Promise<void>) { this.chain = this.chain.then(f, f); return this.chain }

  reset() { this.path = []; this.anchors = []; this.trail = []; this.live = []; this.freehand = false; this.want = null; this.onChange() }
  cancel() { this.reset(); if (useEditor.getState().lassoPoly) useEditor.getState().setLassoPoly(null) }
  private sync() { useEditor.getState().setLassoPoly(this.path.length ? this.path.map((q) => ({ ...q })) : null) }

  /** A press: the first point, a fastening click, an Alt straight segment, or a click on the first point that closes. */
  press(p: Pt, alt: boolean, mode: SelectionMode) {
    return this.queue(async () => {
      if (!this.active) {
        if (!(await ensureDocImage(false))) return
        this.mode = mode
        const s = await snap([p.x, p.y], this.settings())
        this.path = [{ x: s[0], y: s[1] }]; this.anchors = [0]; this.trail = [p]; this.live = []
        this.sync(); this.onChange()
        return
      }
      if (this.nearStart(p)) { await this.closeNow(alt); return }
      if (alt) {                                                         // a straight segment to the raw point; dragging on draws freehand
        this.live = []; this.path.push(p); this.anchors.push(this.path.length - 1); this.trail = [p]; this.freehand = true
        this.sync(); this.onChange()
        return
      }
      await this.follow(p, false)
      this.fastenLive()
    })
  }
  /** The pointer moved (button up or down). */
  move(p: Pt, down: boolean) {
    if (!this.active) return
    this.hover = p
    if (this.freehand && down) {                                       // Alt-drag: freehand points
      if (dist(p, this.path[this.path.length - 1]) >= 0.5) { this.path.push(p); this.trail = [p] }
      this.onChange()
      return
    }
    if (this.busy) { this.want = p; return }                           // latest wins while a trace runs
    this.busy = true
    void this.follow(p, true).finally(() => {
      this.busy = false
      const w = this.want; this.want = null
      if (w && this.active) this.move(w, false)
    })
  }
  release() {
    if (!this.freehand) return
    this.freehand = false
    this.anchors.push(this.path.length - 1); this.sync(); this.onChange()
  }
  /** Backspace: back to the previous fastening point (cancels with only the first left). */
  removeLast() {
    return this.queue(async () => {
      if (!this.active) return
      if (this.anchors.length <= 1) { this.cancel(); return }
      this.anchors.pop()
      this.path = this.path.slice(0, this.anchors[this.anchors.length - 1] + 1)
      this.live = []; this.trail = [this.path[this.path.length - 1]]
      this.sync()
      if (this.hover) await this.follow(this.hover, false)
      this.onChange()
    })
  }
  /** Enter / double-click / ✓: traced back to the first point (straight with Alt), then the selection. */
  close(alt = false) { return this.queue(() => this.closeNow(alt)) }
  private async closeNow(alt: boolean) {
    if (!this.active) return
    this.freehand = false
    this.fastenLive()
    const last = this.path[this.path.length - 1], first = this.path[0]
    if (!alt && dist(last, first) > 0.5) {
      const seg = pts(await trace([last.x, last.y], [first.x, first.y], [], this.settings()))
      if (seg.length > 1) this.path.push(...seg.slice(1))
    }
    if (this.path.length > 1 && dist(this.path[this.path.length - 1], first) < 0.5) this.path.pop()
    const path = this.path, mode = this.mode
    this.reset()
    if (path.length < 3) { useEditor.getState().setLassoPoly(null); return }
    const st = useEditor.getState()
    st.setLassoPoly(path)
    st.closeLassoPoly(mode, 'magnetic lasso')
  }

  private fastenLive() {
    if (this.live.length > 1) { this.path.push(...this.live.slice(1)); this.anchors.push(this.path.length - 1) }
    this.live = []; this.trail = [this.path[this.path.length - 1]]
    this.sync(); this.onChange()
  }
  /** Trace from the last fastening point to (the edge near) q, guided by the trail; with `fasten`, drop points by distance. */
  private async follow(q: Pt, fasten: boolean) {
    if (!this.active) return
    const s = this.settings(), gap = Math.min(8, Math.max(1, s.width / 4))
    if (!this.trail.length || dist(this.trail[this.trail.length - 1], q) >= gap) this.trail.push(q)
    const t = await snap([q.x, q.y], s)
    const from = this.path[this.path.length - 1]
    let live = pts(await trace([from.x, from.y], t, flat(this.trail), s))
    if (live.length < 2) live = [from, { x: t[0], y: t[1] }]
    if (!this.active) return
    this.live = live
    if (fasten) {
      const sp = this.spacing()
      for (let k = 0; k < 64 && length(this.live) >= sp + 1; k++) {
        let acc = 0, i = 1
        for (; i < this.live.length; i++) { const d = dist(this.live[i - 1], this.live[i]); if (acc + d >= sp) break; acc += d }
        const a = this.live[i - 1], b = this.live[i], f = (sp - acc) / Math.max(1e-9, dist(a, b))
        const cut = { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f }
        this.path.push(...this.live.slice(1, i), cut); this.anchors.push(this.path.length - 1)
        this.live = [cut, ...this.live.slice(i)]
        let near = 0
        this.trail.forEach((p, j) => { if (dist(p, cut) < dist(this.trail[near], cut)) near = j })
        this.trail = [cut, ...this.trail.slice(near + 1)]
      }
      if (this.anchors.length && this.path.length) this.sync()
    }
    this.onChange()
  }
}

export const magnetic = new MagneticLasso()
// a tool or lasso-kind change, or another document, drops a border in progress
useEditor.subscribe((s, p) => { if (magnetic.active && (s.tool !== 'lasso' || s.lassoKind !== 'magnetic' || s.doc?.id !== p.doc?.id)) magnetic.reset() })
