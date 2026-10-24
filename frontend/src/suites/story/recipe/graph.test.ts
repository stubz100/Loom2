// RC1 (D96, proto01_animate 28): the recipe graph's columns (the longest path from a source, W6's left-to-right) and what each node opens.
import { describe, expect, it } from 'vitest'
import { layout, targetOf, type GraphNode } from './graph'

const node = (id: string, kind: string, ref: Record<string, string> = {}): GraphNode => ({ id, kind, label: id, sub: null, state: 'done', reasons: [], thumb: null, ref, seconds: null })

describe('the recipe graph (RC1)', () => {
  it('puts each node in the column of its longest path from a source, in the server\'s order within a column', () => {
    const nodes = ['character:m', 'stage', 'anim_ref:m', 'camera', 'motion:fig_m', 'plate', 'layer:fig_m', 'composition', 'take'].map((id) => node(id, id.split(':')[0]))
    const edges = [['character:m', 'anim_ref:m'], ['stage', 'camera'], ['stage', 'motion:fig_m'], ['camera', 'plate'], ['anim_ref:m', 'layer:fig_m'], ['motion:fig_m', 'layer:fig_m'],
      ['camera', 'layer:fig_m'], ['plate', 'composition'], ['layer:fig_m', 'composition'], ['composition', 'take']].map(([from, to]) => ({ from, to }))
    const at = layout({ nodes, edges })
    expect(Object.fromEntries(Object.entries(at).map(([k, v]) => [k, v.col]))).toEqual({ 'character:m': 0, stage: 0, 'anim_ref:m': 1, camera: 1, 'motion:fig_m': 1, plate: 2, 'layer:fig_m': 2, composition: 3, take: 4 })
    expect([at['anim_ref:m'].row, at.camera.row, at['motion:fig_m'].row]).toEqual([0, 1, 2])
    expect(at.take.x).toBeGreaterThan(at.composition.x)
  })
  it('opens each node where it is made', () => {
    const clay = { route: 'clay2', final_id: 'fin_1' }
    expect(targetOf(node('character:m', 'character', { profile_id: 'prf_m', version: 'v1' }), clay)).toEqual({ kind: 'cast', profileId: 'prf_m', version: 'v1' })
    expect(targetOf(node('motion:fig_m', 'motion', { object_id: 'fig_m' }), clay)).toEqual({ kind: 'clay', section: 'motion', objectId: 'fig_m' })
    expect(targetOf(node('layer:fig_m', 'layer'), clay)).toEqual({ kind: 'performance', card: 'final' })
    expect(targetOf(node('finish', 'finish'), clay)).toEqual({ kind: 'final', section: 'layers' })
    expect(targetOf(node('take', 'take'), clay)).toEqual({ kind: 'final', section: 'output' })
    expect(targetOf(node('take', 'take'), { route: 'i2v', final_id: null })).toEqual({ kind: 'shots' })
    expect(targetOf(node('step:clip', 'clip'), { route: 'stage', final_id: null })).toEqual({ kind: 'performance', card: 'clip' })
    expect(targetOf(node('step:frame', 'frame'), { route: 'i2v', final_id: null })).toEqual({ kind: 'image' })
  })
})
