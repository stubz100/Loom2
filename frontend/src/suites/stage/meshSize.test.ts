// W38: a prop's height on its model — its height, or a flat thing's longest side.
import { describe, expect, it } from 'vitest'
import { sizedExtent } from './meshSize'

describe('W38: the extent a prop is sized by', () => {
  it('a standing thing by its height, a flat one (a letter) by its longest side', () => {
    expect(sizedExtent(0.4, 1.0, 0.4)).toBe(1.0)                                               // a lamp
    expect(sizedExtent(1.6, 0.75, 0.8)).toBe(0.75)                                             // a table: its height, not its length
    expect(sizedExtent(1.0, 0.02, 0.7)).toBe(1.0)                                              // the letter (unit-sized): its length
  })
})
