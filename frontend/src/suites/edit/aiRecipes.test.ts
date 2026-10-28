// D90 (02 §9): Edit's AI runs as commands — the reasons the AI tab shows, the recipes it sends, and the `edit.ai.*` commands' `when`s
// mirroring those reasons (Ctrl+K, the keyboard map and the canvas menu never start a run the tab would refuse). Also the canvas
// menu's AI ▸ group, Merge visible and the dev-only flatten check (01 §11.6).
import { beforeEach, describe, expect, it } from 'vitest'
import type { Capabilities } from '../../api/types'
import { command, isEnabled, type MenuItem } from '../../frame/commands'
import { useSession } from '../../store/session'
import { AI_DEFAULT, useAiPanel, type AiOp, type AiPanelState } from './aiPanelStore'
import { aiReason, aiRecipe, aiSeeds, opCandidates, rerunRecipe, selectPlan, subjectPlan, type AiCtx } from './aiRecipes'
import { aiCtx, canvasMenu, layerMenu, MORE_TOOLS, TOOLS } from './editCommands'
import { useEditor, type DocumentStack, type Node } from './editorStore'

const CAPS = {
  models: {
    klein: { order: 0, label: 'Klein 4B', family: 'flux2', recipes: { inpaint: true, i2i: true }, tiled_refine: true },
    hero: { order: 1, label: 'Hero', family: 'flux2', recipes: { inpaint: true, inpaint_hero: true, i2i: true }, tiled_refine: true },
  },
  tools: {
    matte: { order: 0, label: 'Subject', recipes: { segment: ['subject'] } },
    sam: { order: 1, label: 'SAM 3', recipes: { segment: ['text', 'points', 'box'] } },
    up: { order: 2, label: 'Upscaler', recipes: { upscale_factor: 4 } },
  },
  defaults: { inpaint: 'klein', i2i: 'klein', upscale: 'up', segment: 'matte' },
  content_aware: { available: false },
} as unknown as Capabilities

const OPS: AiOp[] = ['select', 'inpaint', 'refine', 'upscale', 'outpaint']
const ctx = (over: Partial<AiCtx> = {}, p: Partial<AiPanelState> = {}): AiCtx => ({
  p: { ...AI_DEFAULT, ...p }, caps: CAPS, health: () => 'ok', doc: { w: 256, h: 256 }, hasSel: false, activeId: 'a', activeKind: 'raster',
  aiPrompt: { points: [], box: null }, refineParams: () => ({ radius: 2 }), ...over,
})

describe('aiReason: why the AI tab refuses a run', () => {
  it('says "no document" for every operation without one', () => {
    for (const op of OPS) expect(aiReason(ctx({ doc: null }), op)).toBe('no document')
  })
  it('inpaint needs a selection; refine on the selection too; outpaint a side', () => {
    expect(aiReason(ctx(), 'inpaint')).toMatch(/^select the region/)
    expect(aiReason(ctx({ hasSel: true }), 'inpaint')).toBeNull()
    expect(aiReason(ctx({}, { refineSource: 'selection' }), 'refine')).toBe('no selection')
    expect(aiReason(ctx(), 'refine')).toBeNull()
    expect(aiReason(ctx({}, { pad: { left: 0, top: 0, right: 0, bottom: 0 } }), 'outpaint')).toBe('set at least one side')
    expect(aiReason(ctx(), 'outpaint')).toBeNull()
  })
  it('refine / upscale on the active layer need a raster layer; upscale needs its weights', () => {
    expect(aiReason(ctx({ activeKind: 'group' }, { refineSource: 'active' }), 'refine')).toBe('the active layer is not a raster layer')
    expect(aiReason(ctx({ activeKind: 'adjustment' }, { upscaleSource: 'active' }), 'upscale')).toBe('the active layer is not a raster layer')
    expect(aiReason(ctx({ health: (id) => (id === 'up' ? 'missing' : 'ok') }), 'upscale')).toBe('weights missing: fetch up in Models')
    expect(aiReason(ctx({ caps: { ...CAPS, tools: {}, defaults: {} } as unknown as Capabilities }), 'upscale')).toBe('no upscaler offered')
  })
  it('select follows the panel\'s tool and prompt mode', () => {
    expect(aiReason(ctx(), 'select')).toBeNull()                                         // the subject matte needs nothing
    expect(aiReason(ctx({}, { selModel: 'sam', selMode: 'text', selText: ' ' }), 'select')).toBe('type what to select in find')
    expect(aiReason(ctx({}, { selModel: 'sam', selMode: 'points' }), 'select')).toMatch(/^click the subject/)
    expect(aiReason(ctx({ aiPrompt: { points: [{ x: 1, y: 2, label: 1 }], box: null } }, { selModel: 'sam', selMode: 'points' }), 'select')).toBeNull()
    expect(aiReason(ctx({}, { selModel: 'sam', selMode: 'box' }), 'select')).toBe('drag a box on the canvas')
    expect(aiReason(ctx({ health: () => 'missing' }), 'select')).toBe('weights missing: fetch matte in Models')
  })
})

describe('the recipes a run sends', () => {
  it('inpaint: the variant\'s inpaint model, one seed per candidate; Fill Hero picks the hero model\'s count', () => {
    const r = aiRecipe(ctx({ hasSel: true }, { candidates: 3, seedMode: 'fixed', seed: 7, prompt: 'a lamp' }), 'inpaint') as unknown as Record<string, unknown>
    expect(r).toMatchObject({ kind: 'inpaint', mode: 'fill', model_id: 'klein', seeds: [7, 8, 9], prompt_text: 'a lamp', prefill: false })
    expect(opCandidates(ctx({}, { mode: 'fill_hero' }), 'inpaint')).toBe(2)
    expect(opCandidates(ctx(), 'inpaint')).toBe(4)
    expect(opCandidates(ctx(), 'upscale')).toBe(1)
  })
  it('outpaint uses the hero model only when chosen; refine and upscale carry the active layer', () => {
    expect(aiRecipe(ctx({}, { outpaintHero: true }), 'outpaint')).toMatchObject({ kind: 'inpaint', mode: 'outpaint', model_id: 'hero' })
    expect(aiRecipe(ctx(), 'outpaint')).toMatchObject({ model_id: 'klein' })
    expect(aiRecipe(ctx({}, { refineSource: 'active' }), 'refine')).toMatchObject({ kind: 'i2i', model_id: 'klein', source: 'active', layer_id: 'a' })
    expect(aiRecipe(ctx(), 'upscale')).toMatchObject({ kind: 'upscale', model_id: 'up', seeds: [0], refine: false })
  })
  it('select: the panel\'s tool; Select subject: the matte whatever the panel\'s mode', () => {
    const c = ctx({}, { selModel: 'sam', selMode: 'text', selText: 'the crates', selRefine: true })
    expect(selectPlan(c).recipe()).toMatchObject({ kind: 'segment', model_id: 'sam', mode: 'text', text: 'the crates', edge_refine: { radius: 2 } })
    expect(subjectPlan(c).recipe()).toMatchObject({ kind: 'segment', model_id: 'matte', mode: 'subject', text: '', points: [] })
    expect(subjectPlan(ctx({ caps: { ...CAPS, tools: {} } as unknown as Capabilities })).reason).toBe('no subject matte offered')
  })
  it('seeds count up from a fixed seed, at most 4; a re-run drops the per-run fields', () => {
    expect(aiSeeds({ ...AI_DEFAULT, candidates: 9, seedMode: 'fixed', seed: 3 })).toEqual([3, 4, 5, 6])
    expect(aiSeeds({ ...AI_DEFAULT, candidates: 2, seedMode: 'random' }, () => 0.5)).toEqual([2 ** 30, 2 ** 30])
    expect(rerunRecipe({ kind: 'inpaint', seed: 1, job_id: 'j', batch_id: 'b', region: [0, 0, 1, 1], document_id: 'd', prompt_text: 'x' }, 42)).toEqual({ kind: 'inpaint', prompt_text: 'x', seeds: [42] })
  })
})

// ---- the commands, against the real stores ----------------------------------------------------------------------------------------
const raster = (id: string, extra: Partial<Node> = {}): Node => ({ kind: 'raster', id, name: id, opacity: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null, x: 0, y: 0, w: 64, h: 64, ...extra })
const stack = (layers: Node[]): DocumentStack => ({ schema_version: 1, id: 'doc_1', name: 'Doc', w: 256, h: 256, background: 'transparent', source_asset_id: null,
  created_at: '2026-10-16T08:00:00', saved_at: null, revision: 1, layers, has_selection: false, meta: {} }) as unknown as DocumentStack
const items = (m: MenuItem[]): MenuItem[] => m.flatMap((x) => ('items' in x ? [x, ...items(x.items)] : [x]))
const cmds = (m: MenuItem[]) => items(m).filter((x): x is { cmd: string } => 'cmd' in x).map((x) => x.cmd)

describe('edit.ai.* commands mirror the AI tab (D32, D90)', () => {
  beforeEach(() => {
    useSession.setState({ capabilities: CAPS, models: [] })
    useEditor.setState({ doc: null, selection: null, activeId: null, transform: null, candidates: null, tool: 'brush', lassoPoly: null, aiPrompt: { points: [], box: null } })
    useAiPanel.setState({ ...AI_DEFAULT })
  })

  it('each run command is enabled exactly when the tab would run it, in every state', () => {
    const states: [string, () => void][] = [
      ['no document', () => undefined],
      ['a document', () => useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })],
      ['a selection', () => useEditor.setState({ selection: {} as never })],
      ['weights fetched', () => useSession.setState({ models: [{ id: 'matte', health: 'ok' }, { id: 'up', health: 'ok' }] as never })],
      ['refine on the selection, no sides', () => { useEditor.setState({ selection: null }); useAiPanel.setState({ refineSource: 'selection', pad: { left: 0, top: 0, right: 0, bottom: 0 } }) }],
      ['SAM 3 points without a point', () => useAiPanel.setState({ selModel: 'sam', selMode: 'points' })],
    ]
    for (const [what, apply] of states) {
      apply()
      for (const op of OPS) expect(isEnabled(command(`edit.ai.${op}`)!), `${what}: edit.ai.${op}`).toBe(!aiReason(aiCtx(), op))
      useAiPanel.setState({ op: 'inpaint' }); expect(isEnabled(command('edit.ai.stage')!), `${what}: stage`).toBe(!aiReason(aiCtx(), 'inpaint'))
      expect(isEnabled(command('edit.ai.subject')!), `${what}: subject`).toBe(!subjectPlan(aiCtx()).reason)
    }
  })

  it('every AI command has a mouse home and the canvas menu carries AI ▸ beside the selection', () => {
    for (const id of ['edit.ai.select', 'edit.ai.inpaint', 'edit.ai.refine', 'edit.ai.upscale', 'edit.ai.outpaint', 'edit.ai.stage', 'edit.ai.subject', 'edit.ai.rerun', 'edit.ai.copyRecipe'])
      expect(command(id)?.placement.length, id).toBeGreaterThan(0)
    useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })
    const menu = canvasMenu()
    const ai = menu.find((x) => 'items' in x && x.label === 'AI') as { items: MenuItem[] } | undefined
    expect(ai && cmds(ai.items)).toEqual(['edit.ai.subject', 'edit.ai.show.inpaint', 'edit.ai.show.refine', 'edit.ai.show.upscale', 'edit.ai.show.outpaint', 'edit.ai.show.instruct'])   // D151
    expect(isEnabled(command('edit.ai.show.inpaint')!)).toBe(false)                           // "Inpaint the selection…" needs one
    useEditor.setState({ selection: {} as never })
    expect(isEnabled(command('edit.ai.show.inpaint')!)).toBe(true)
    command('edit.ai.show.refine')!.run()
    expect(useAiPanel.getState()).toMatchObject({ op: 'refine', candidates: 4 })
  })

  it('the re-run and copy-recipe commands follow the active layer\'s recipe, also in the layer menu', () => {
    useEditor.setState({ doc: stack([raster('a'), raster('b', { recipe: { kind: 'inpaint', seed: 3 } })]), activeId: 'a' })
    expect(isEnabled(command('edit.ai.rerun')!)).toBe(false)
    expect(cmds(layerMenu())).not.toContain('edit.ai.rerun')
    useEditor.setState({ activeId: 'b' })
    expect(isEnabled(command('edit.ai.rerun')!)).toBe(true)
    expect(cmds(layerMenu())).toEqual(expect.arrayContaining(['edit.ai.rerun', 'edit.ai.copyRecipe', 'edit.layer.mergeVisible']))
  })
})

describe('the first screen and the developer items (D90 02 §10, 01 §11.6)', () => {
  it('Magic wand, Spot healing and Eyedropper sit behind More tools; every tool stays in Tool ▸ with its key', () => {
    expect(TOOLS.filter(([t]) => !MORE_TOOLS.includes(t)).map(([, l]) => l)).toEqual(['Move', 'Marquee', 'Lasso', 'Quick selection', 'AI select', 'Brush', 'Eraser', 'Fill / gradient', 'Crop / canvas', 'Hand', 'Zoom'])
    useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })
    const tool = canvasMenu().find((x) => 'items' in x && x.label === 'Tool') as { items: MenuItem[] }
    expect(cmds(tool.items)).toHaveLength(TOOLS.length)
    expect(command('edit.tool.wand')?.keys).toBe('W')
  })
  it('Compare with the exact flatten is a dev-build command, not in the Document menu', () => {
    useEditor.setState({ doc: stack([raster('a')]), activeId: 'a' })
    expect(cmds(canvasMenu())).not.toContain('edit.compare')
    expect(command('edit.compare')?.placement).toEqual(['inspector'])                       // Vitest runs as a dev build
  })
  it('Merge visible needs two visible layers and merges pixel layers only', () => {
    const toasts: string[] = []
    useSession.setState({ toast: ((t: string) => { toasts.push(t) }) as never })
    useEditor.setState({ doc: stack([raster('a'), raster('b', { visible: false })]), activeId: 'a' })
    expect(isEnabled(command('edit.layer.mergeVisible')!)).toBe(false)
    useEditor.setState({ doc: stack([raster('a'), { ...raster('g'), kind: 'group', children: [] } as Node]) })
    expect(isEnabled(command('edit.layer.mergeVisible')!)).toBe(true)
    command('edit.layer.mergeVisible')!.run()
    expect(toasts[0]).toMatch(/^Merge visible merges pixel layers only/)
  })
})

describe('Instruct (D151): an edit by instruction', () => {
  const model = { label: 'Qwen', short: 'Qwen', health: 'present', missing: [], seconds: 32, vram_gb: 15, approx_gb: 20 }
  const withModel = { ...CAPS, instruct: { models: { 'qwen-edit-x': model }, default: 'qwen-edit-x' } } as unknown as Capabilities
  const noModel = { ...CAPS, instruct: { models: {}, default: null } } as unknown as Capabilities
  const missing = { ...CAPS, instruct: { models: { 'qwen-edit-x': { ...model, health: 'missing', missing: ['a.safetensors'] } }, default: 'qwen-edit-x' } } as unknown as Capabilities
  it('needs a document, a model with its weights, an instruction, and a raster layer when it edits the active one', () => {
    expect(aiReason(ctx({ caps: withModel, doc: null }, { prompt: 'make it dusk' }), 'instruct')).toBe('no document')
    expect(aiReason(ctx({ caps: noModel }, { prompt: 'make it dusk' }), 'instruct')).toBe('no edit-by-instruction model in this build')
    expect(aiReason(ctx({ caps: missing }, { prompt: 'make it dusk' }), 'instruct')).toMatch(/weights missing/)
    expect(aiReason(ctx({ caps: withModel }, { prompt: '  ' }), 'instruct')).toBe('say what to change')
    expect(aiReason(ctx({ caps: withModel, activeKind: 'group' }, { prompt: 'make it dusk', instructSource: 'active' }), 'instruct')).toBe('the active layer is not a raster layer')
    expect(aiReason(ctx({ caps: withModel }, { prompt: 'make it dusk' }), 'instruct')).toBeNull()
  })
  it('sends the kind with the model, what it edits and the instruction; two candidates by default', () => {
    const c = ctx({ caps: withModel, activeId: 'lyr_1' }, { prompt: 'snow on the street', instructSource: 'active', seedMode: 'fixed', seed: 5, candidates: 2 })
    expect(aiRecipe(c, 'instruct')).toEqual({ kind: 'instruct', model_id: 'qwen-edit-x', source: 'active', layer_id: 'lyr_1', seeds: [5, 6], prompt_text: 'snow on the street' })
    expect(opCandidates(c, 'instruct')).toBe(2)
  })
})
