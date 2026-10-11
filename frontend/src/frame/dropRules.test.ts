// D71 (ArtCraft P11): what each send-to target does with a drop, and why it refuses one — the text the drag ghost shows — plus how the
// drag manager picks the target under the pointer (the innermost accepting one; else the innermost refusal that says why).
import { describe, expect, it } from 'vitest'
import { resolveTarget, type DragItem, type DragPayload, type DropTarget } from './drag'
import { beatDrop, editOpenDrop, endDrop, layerDrop, refDrop, startDrop } from './dropRules'

const img = (id: string): DragItem => ({ kind: 'asset', id, media: 'image' })
const clip = (id: string): DragItem => ({ kind: 'asset', id, media: 'video' })
const pay = (...items: DragItem[]): DragPayload => ({ items })

describe('reference slots (refDrop)', () => {
  it('adds one image and counts against the model limit', () => {
    expect(refDrop(['a', 'b'], pay(img('c')), 4)).toEqual({ take: ['c'], verdict: { ok: true, label: 'Add as reference 3 of 4' } })
  })
  it('caps several images at max_refs and says how many did not fit', () => {
    const r = refDrop(['a'], pay(img('b'), img('c'), img('d'), img('e')), 4)
    expect(r.take).toEqual(['b', 'c', 'd'])
    expect(r.verdict).toEqual({ ok: true, label: 'Add 3 references (4 of 4) · 1 over the limit' })
  })
  it('skips clips and duplicates, and says so', () => {
    const r = refDrop(['a'], pay(img('a'), img('b'), clip('v'), img('b')), 10)
    expect(r.take).toEqual(['b'])
    expect(r.verdict).toEqual({ ok: true, label: 'Add as reference 2 of 10 · 1 clip skipped' })
  })
  it('refuses clips, references already there and full slots — with the reason', () => {
    expect(refDrop([], pay(clip('v')), 4).verdict).toEqual({ ok: false, reason: "A clip can't be a reference" })
    expect(refDrop([], pay(clip('v'), clip('w')), 4).verdict).toEqual({ ok: false, reason: "Clips can't be references" })
    expect(refDrop(['a'], pay(img('a')), 4).verdict).toEqual({ ok: false, reason: 'Already a reference' })
    expect(refDrop(['a', 'b', 'c', 'd'], pay(img('e')), 4)).toEqual({ take: [], verdict: { ok: false, reason: 'All 4 reference slots are full' } })
  })
  it('counts unknown media as an image (the server still validates)', () => {
    expect(refDrop([], pay({ kind: 'asset', id: 'x' }), 4).take).toEqual(['x'])
  })
  it('ignores groups in the payload', () => {
    expect(refDrop([], pay({ kind: 'group', id: 'g' }), 4).verdict).toEqual({ ok: false })
  })
})

describe('Animate', () => {
  it('the start slot takes an image, and a second one as the end', () => {
    expect(startDrop(pay(img('a')))).toEqual({ start: 'a', end: undefined, verdict: { ok: true, label: 'Set the start frame' } })
    expect(startDrop(pay(img('a'), img('b')))).toMatchObject({ start: 'a', end: 'b', verdict: { label: 'Set the start and the end frame' } })
    expect(startDrop(pay(img('a'), clip('v'))).end).toBeUndefined()
  })
  it('a clip is not a frame: the slot refuses it, the tab plays it', () => {
    expect(startDrop(pay(clip('v'))).verdict).toEqual({ ok: false, reason: "A clip can't be the start frame" })
    expect(startDrop(pay(clip('v')), { tab: true })).toEqual({ play: 'v', verdict: { ok: true, label: 'Play this clip in Animate' } })
    expect(endDrop(pay(clip('v'))).verdict).toEqual({ ok: false, reason: "A clip can't be the end frame" })
    expect(endDrop(pay(img('b')))).toEqual({ end: 'b', verdict: { ok: true, label: 'Set the end frame' } })
  })
  it('beats take images only', () => {
    expect(beatDrop(pay(img('a'), img('b'))).verdict).toEqual({ ok: true, label: 'Add 2 beats' })
  })
})

describe('Edit', () => {
  it('opens the first image; a clip goes to Animate instead', () => {
    expect(editOpenDrop(pay(clip('v'), img('a'), img('b')))).toEqual({ open: 'a', verdict: { ok: true, label: 'Open in Edit (the first of 3)' } })
    expect(editOpenDrop(pay(clip('v'))).verdict).toEqual({ ok: false, reason: 'Clips open in Animate, not Edit' })
  })
  it('layers take every image, clips skipped', () => {
    expect(layerDrop(pay(img('a'), clip('v'), img('b')), 'at this row')).toEqual({ take: ['a', 'b'], verdict: { ok: true, label: 'Add 2 layers at this row · 1 clip skipped' } })
    expect(layerDrop(pay(clip('v'))).verdict).toEqual({ ok: false, reason: "A clip can't be a layer" })
  })
})

describe('resolveTarget', () => {
  // a chain of plain objects standing in for elements: leaf → mid → root (only parentElement is read)
  const el = (parent: HTMLElement | null) => ({ parentElement: parent }) as unknown as HTMLElement
  const root = el(null), mid = el(root), leaf = el(mid)
  const accepting = (label: string): DropTarget => ({ accept: () => true, drop: () => undefined, describe: () => ({ ok: true, label }) })
  const refusing = (reason: string): DropTarget => ({ accept: () => false, drop: () => undefined, describe: () => ({ ok: false, reason }) })

  it('takes the innermost accepting target with its label', () => {
    const map = new Map([[mid, accepting('inner')], [root, accepting('outer')]])
    expect(resolveTarget(leaf, pay(img('a')), (e) => map.get(e))).toEqual({ el: mid, verdict: { ok: true, label: 'inner' } })
  })
  it('passes over a refusing target to an accepting parent', () => {
    const map = new Map([[leaf, refusing('no')], [root, accepting('yes')]])
    expect(resolveTarget(leaf, pay(img('a')), (e) => map.get(e))).toEqual({ el: root, verdict: { ok: true, label: 'yes' } })
  })
  it('with nothing accepting, reports the innermost reason and no element', () => {
    const map = new Map([[mid, refusing('inner reason')], [root, refusing('outer reason')]])
    expect(resolveTarget(leaf, pay(img('a')), (e) => map.get(e))).toEqual({ el: null, verdict: { ok: false, reason: 'inner reason' } })
  })
  it('an accepting target without describe drops silently', () => {
    const map = new Map<HTMLElement, DropTarget>([[mid, { accept: () => true, drop: () => undefined }]])
    expect(resolveTarget(leaf, pay(img('a')), (e) => map.get(e))).toEqual({ el: mid, verdict: null })
  })
})
