// W27: a Board is one of World's pages or the shot's own; W31: a record's time in the author's clock.
import { describe, expect, it } from 'vitest'
import type { BinNode } from '../../api/types'
import { localTime } from '../../frame/time'
import { boardPages } from './boardPages'

const home = (id: string, path: string, children: BinNode[] = []): BinNode => ({ id, path, name: id, count: 0, total: 0, pages: [], gone: false, page: false, kinds: [], children })

describe('the walkthrough-2 register: Shots', () => {
  it("W27: the Board picker offers World's pages and this shot's, not another shot's, the Episode's or Imports", () => {
    const homes = [home('w', 'world', [home('ines', 'world/character/prf_i', [home('ines_v1', 'world/character/prf_i/v1')])]),
      home('s', 'shots', [home('seal', 'shots/shot_seal', [home('seal_v1', 'shots/shot_seal/v1')]), home('stay', 'shots/shot_stay')]),
      home('imp', 'imports'), home('ep', 'episode')]
    expect([...boardPages(homes, 'shot_seal')!].sort()).toEqual(['ines', 'ines_v1', 'seal', 'seal_v1', 'w'])
    expect(boardPages([], 'shot_seal')).toBeNull()                                                  // not known yet: every page
  })
  it('W31: a UTC time is shown in local time, a zone-less one read as UTC', () => {
    const d = new Date('2026-10-30T15:15:00Z')
    const p = (n: number) => String(n).padStart(2, '0')
    const want = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
    expect(localTime('2026-10-30T15:15:00Z')).toBe(want)
    expect(localTime('2026-10-30T15:15:00+00:00')).toBe(want)
    expect(localTime('2026-10-30T15:15:00')).toBe(want)
    expect(localTime(null)).toBe('')
    expect(localTime('soon')).toBe('soon')
  })
})
