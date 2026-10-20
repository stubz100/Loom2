// D115: Expand's cells and the recipe each one runs — the panel as it stands, the pose content replaced by the cell's.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Capabilities } from '../../api/types'
import { useSession } from '../../store/session'
import { DEFAULT_PANEL, expandCells, recipeForCell, type Panel, type PoseSet } from './generateStore'

const CAPS = { defaults: { t2i: 'fixture-turbo' }, models: { 'fixture-turbo': { order: 1, short: 'Turbo', turbo: true, recipes: {} } } } as unknown as Capabilities
const SHOTS = ['close-up', 'portrait', 'waist-up', 'full-body'], ANGLES = ['front', 'three-quarter left', 'back'], EXPR = ['neutral', 'smile', 'sad']
const PHRASES = { shots: { 'waist-up': 'a waist-up medium shot', 'close-up': 'a close-up of the face' }, angles: { 'three-quarter left': 'a three-quarter view from the left', front: 'seen from the front' } }

beforeEach(() => useSession.setState({ capabilities: CAPS }))
afterEach(() => useSession.setState({ capabilities: null }))

describe('D115 expandCells', () => {
  it('orders the chosen cells as the coverage does and drops duplicates', () => {
    const poses: PoseSet = { cells: [{ shot: 'full-body', angle: 'back', expression: 'sad' }, { shot: 'close-up', angle: 'front', expression: 'smile' },
      { shot: 'close-up', angle: 'front', expression: 'neutral' }, { shot: 'close-up', angle: 'front', expression: 'smile' }], expressions: ['neutral'] }
    expect(expandCells(poses, SHOTS, ANGLES, EXPR).map((c) => `${c.shot}/${c.angle}/${c.expression}`)).toEqual(['close-up/front/neutral', 'close-up/front/smile', 'full-body/back/sad'])
    expect(expandCells({ cells: [], expressions: ['smile'] }, SHOTS, ANGLES, EXPR)).toEqual([])
  })
})

describe('D115 recipeForCell', () => {
  const tree: Panel = { ...DEFAULT_PANEL, prompt_mode: 'tree', text: 'soft light', count: 2, tree: {
    scene: 'a harbour at dawn', style: 'ink wash', lighting: 'low sun', composition: 'rule of thirds',
    subjects: [{ description: 'a fisher', position: 'left', action: 'mending a net', pose: 'kneeling', color_match: 'exact' },
      { description: 'Mara', profile_id: 'prf_m', action: 'waving', pose: 'standing', position: 'right', color_match: 'exact' }],
    camera: { angle: 'low', lens: '35mm' } } }
  it('replaces the pose content in a tree prompt: every subject\'s action, pose and position go, the linked subject takes the expression, the shot and angle phrases land', () => {
    const r = recipeForCell(tree, { shot: 'waist-up', angle: 'three-quarter left', expression: 'smile' }, PHRASES)
    const j = r.prompt_json as { subjects: Record<string, string>[]; composition: string; camera: Record<string, string>; style: string; lighting: string }
    expect(j.composition).toBe('a waist-up medium shot')
    expect(j.camera).toEqual({ angle: 'a three-quarter view from the left', lens: '35mm' })
    expect(j.subjects[0]).not.toHaveProperty('action')
    expect(j.subjects[0]).not.toHaveProperty('pose')
    expect(j.subjects[1].pose).toBe('smile expression')
    expect(j.subjects[1]).not.toHaveProperty('action')
    expect(j.style).toBe('ink wash')
    expect(j.lighting).toBe('low sun')                                        // everything but the pose stays
    expect(r.prompt_text).toBe('soft light')
    expect(r.seeds).toHaveLength(2)                                           // the panel's count per cell
    expect(tree.tree.subjects![1].action).toBe('waving')                      // the panel itself is untouched
  })
  it('falls back to the first subject without a link, and appends the sentence in Text mode', () => {
    const free: Panel = { ...tree, tree: { ...tree.tree, subjects: [tree.tree.subjects![0]] } }
    const j = recipeForCell(free, { shot: 'close-up', angle: 'front', expression: 'sad' }, PHRASES).prompt_json as { subjects: Record<string, string>[] }
    expect(j.subjects[0].pose).toBe('sad expression')
    const text: Panel = { ...DEFAULT_PANEL, prompt_mode: 'text', text: 'Mara in a grey coat, walking. ' }
    const r = recipeForCell(text, { shot: 'close-up', angle: 'front', expression: 'sad' }, PHRASES)
    expect(r.prompt_text).toBe('Mara in a grey coat, walking. a close-up of the face, seen from the front, sad expression.')
    const unknown = recipeForCell(tree, { shot: 'knee', angle: 'above', expression: 'neutral' }, PHRASES).prompt_json as { composition: string; camera: { angle: string } }
    expect(unknown.composition).toBe('knee')                                  // an id without a phrase is sent as it is
    expect(unknown.camera.angle).toBe('above')
  })
})
