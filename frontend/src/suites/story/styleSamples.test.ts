import { describe, expect, it } from 'vitest'
import type { AlbumNode, Job, WorldStyle } from '../../api/types'
import { DEFAULT_ID, NONE_ID, SAMPLE_PX, SAMPLE_SEED, findNode, pickSampleModel, pickerId, pickerItems, pickerValue, sampleDrop, sampleJob, sampleOptions, sampleRecipe, sampleValue, styleFace, styleGroupName } from './styleSamples'

const node = (id: string, cover: string[] = [], children: AlbumNode[] = []): AlbumNode => ({ id, name: id, children, cover_ids: cover, assets: cover.length, groups: children.length, total: cover.length, revision: 1 })
const tree = node('album', [], [node('g1', ['a1', 'a2']), node('g2', [], [node('g3', ['a9'])])])
const sty = (id: string, group_id: string | null = null, fragment = ''): WorldStyle => ({ id, name: `Style ${id}`, fragment, group_id })

describe('D90 styles as images', () => {
  it('finds a style\'s face: its group\'s cover, nested groups too; none without a group or a sample', () => {
    expect(findNode(tree, 'g3')?.id).toBe('g3')
    expect(styleFace(sty('a', 'g1'), tree)).toBe('a1')
    expect(styleFace(sty('b', 'g3'), tree)).toBe('a9')
    expect(styleFace(sty('c', 'g2'), tree)).toBeNull()
    expect(styleFace(sty('d', null), tree)).toBeNull()
    expect(styleFace(sty('e', 'gone'), tree)).toBeNull()
    expect(styleFace(sty('a', 'g1'), null)).toBeNull()
  })

  it('builds a one-image square t2i carrying the style id; the first sample shares the set seed', () => {
    const r = sampleRecipe('sty_1', 'm', true)
    expect(r).toMatchObject({ kind: 't2i', model_id: 'm', prompt_mode: 'text', style_id: 'sty_1', seeds: [SAMPLE_SEED] })
    expect(r.width).toBe(r.height); expect((r.width as number) % 16).toBe(0)
    expect(sampleRecipe('sty_1', 'm', false).seeds).toEqual([0])
    expect(sampleRecipe('sty_1', 'm', true, 'a lighthouse at dawn').prompt_text).toBe('a lighthouse at dawn')    // D90: Settings › Samples
    expect(sampleRecipe('sty_1', 'm', true, '  ').prompt_text).toBe(sampleRecipe('sty_1', 'm', true).prompt_text)  // blank = the default scene
    expect(styleGroupName('Ink wash')).toBe('Style · Ink wash')
  })

  it('takes images dropped on a tile and refuses clips (the ghost says why)', () => {
    expect(sampleDrop([{ kind: 'asset', id: 'x' }, { kind: 'asset', id: 'x' }], 'Ink').take).toEqual(['x'])
    expect(sampleDrop([{ kind: 'asset', id: 'x', media: 'image' }], 'Ink').verdict).toEqual({ ok: true, label: 'Make it the sample of Ink' })
    expect(sampleDrop([{ kind: 'asset', id: 'v', media: 'video' }], 'Ink').verdict.ok).toBe(false)
    expect(sampleDrop([{ kind: 'asset', id: 'v', media: 'video' }], 'Ink').verdict.reason).toContain('clip')
    expect(sampleDrop([{ kind: 'group', id: 'g' }], 'Ink').verdict).toEqual({ ok: false })
    expect(sampleDrop([{ kind: 'asset', id: 'a' }, { kind: 'asset', id: 'b' }, { kind: 'asset', id: 'c', media: 'video' }], 'Ink').take).toEqual(['a', 'b'])
  })

  it('finds a style\'s pending sample job by its origin', () => {
    const j = (id: string, status: string, ref: string, created_at: string) => ({ id, status, created_at, origin: { suite: 'story', surface: 'style', ref } }) as unknown as Job
    const jobs = { a: j('a', 'done', 's1', '1'), b: j('b', 'queued', 's1', '2'), c: j('c', 'running', 's2', '3') }
    expect(sampleJob(jobs, 's1')?.id).toBe('b')
    expect(sampleJob(jobs, 's3')).toBeUndefined()
  })

  it('maps the picker value (undefined = default, null = none) to tiles and back; the fragment is the tooltip', () => {
    for (const v of [undefined, null, 'sty_1']) expect(pickerValue(pickerId(v))).toBe(v)
    expect(pickerId(undefined)).toBe(DEFAULT_ID); expect(pickerId(null)).toBe(NONE_ID)
    const styles = [sty('1', 'g1', 'ink and wash'), sty('2')]
    const items = pickerItems(styles, '1', (s) => styleFace(s, tree), (id) => `t/${id}`)
    expect(items.map((i) => i.id)).toEqual([DEFAULT_ID, NONE_ID, '1', '2'])
    expect(items[0]).toMatchObject({ label: 'Default · Style 1', img: 't/a1' })
    expect(items[2]).toMatchObject({ badge: '★', hint: 'ink and wash', img: 't/a1' })
    expect(items[3]).toMatchObject({ badge: undefined, img: null, hint: 'no prompt fragment yet' })
    expect(pickerItems(styles, null, () => null, (id) => id)[0].label).toBe('Default · none')
  })
})

describe('D91 the sample model', () => {
  const m = (id: string, extra: Partial<{ default: boolean; health: string; style_px: number; label: string }> = {}) =>
    ({ id, label: extra.label ?? id.toUpperCase(), short: id, health: extra.health ?? 'verified', missing: [], default: !!extra.default, style_px: extra.style_px ?? 768, swatch_px: 512, license: 'apache-2.0' })
  const caps = { defaults: { swatch: 'small', t2i: 'big' }, sample_models: [m('small', { default: true, label: 'Small' }), m('quick', { style_px: 1024 }), m('slow', { health: 'missing' })] }

  it('uses the setting when the build offers it, else the default — as the server does for the swatches', () => {
    expect(pickSampleModel(caps, 'quick')).toMatchObject({ id: 'quick', style_px: 1024 })
    expect(pickSampleModel(caps, null)?.id).toBe('small')
    expect(pickSampleModel(caps, 'gone')?.id).toBe('small')                        // not offered here (another variant, a removed spec)
    expect(pickSampleModel({ defaults: { swatch: 'small' }, sample_models: [] }, 'quick')).toMatchObject({ id: 'small', style_px: SAMPLE_PX })   // an older server
    expect(pickSampleModel(null, 'quick')).toBeNull()
  })

  it("renders the style sample at the model's size", () => {
    const r = sampleRecipe('sty_1', 'quick', true, null, 1024)
    expect([r.width, r.height]).toEqual([1024, 1024])
  })

  it('lists "default · <label>" first, the others after, a missing one marked; the value maps the setting', () => {
    expect(sampleOptions(caps.sample_models)).toEqual([{ value: '', label: 'default · Small' }, { value: 'quick', label: 'QUICK' }, { value: 'slow', label: 'SLOW (not fetched)' }])
    expect(sampleOptions([])).toEqual([{ value: '', label: 'default' }])
    expect(sampleValue('quick', caps.sample_models)).toBe('quick')
    expect(sampleValue('small', caps.sample_models)).toBe('')                       // the default is the empty choice
    expect(sampleValue('gone', caps.sample_models)).toBe('')
    expect(sampleValue(null, caps.sample_models)).toBe('')
  })
})
