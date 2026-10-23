// D125 (S7, SP2): a node's place carried along the Flow — forward to the nodes after it that have none (up to the next with a place of its
// own), and backwards to a node connected without one.
import { describe, expect, it } from 'vitest'
import type { FlowNode } from '../../api/types'
import { nodesAfterWithoutPlace, placeBefore } from './storyStore'

const node = (id: string, type: FlowNode['type'], place_id: string | null = null): FlowNode => ({ id, type, place_id }) as unknown as FlowNode
const nodes = Object.fromEntries([node('a', 'shot', 'tavern'), node('b', 'dialogue'), node('c', 'choice'), node('d', 'dialogue'), node('e', 'shot', 'street'), node('f', 'shot')].map((n) => [n.id, n]))
const edges = [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }, { from: 'c', to: 'd' }, { from: 'c', to: 'e' }, { from: 'e', to: 'f' }]

describe('the place carried along the Flow (D125 S7)', () => {
  it('goes forward through logic nodes to the visual nodes without a place, and stops at one with its own', () => {
    expect(nodesAfterWithoutPlace('a', edges, nodes)).toEqual(['b', 'd'])
    expect(nodesAfterWithoutPlace('e', edges, nodes)).toEqual(['f'])
  })
  it('reads the nearest place before a node, through logic nodes', () => {
    expect(placeBefore('c', edges, nodes)).toBe('tavern')
    expect(placeBefore('f', edges, nodes)).toBe('street')
    expect(placeBefore('a', [], nodes)).toBe('tavern')
    expect(placeBefore('b', [], nodes)).toBeNull()
  })
})
