// D121 (AW2): the one timeline's arithmetic and the one transport — a frame's place on a track and back, a drag in frames, the ruler's ticks,
// a motion clip's bake read as a bar; each level's transport behind one command set, the level on screen deciding which runs.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { runCommand } from '../../frame/commands'
import { useSession } from '../../store/session'
import './animateCommands'
import { deltaFrames, frameAt, keyRuns, pct, stageSpan, ticks } from './timelineMath'
import { neighbour, registerTransport, transport, TRANSPORT_IDS, type Transport } from './transport'

describe('the timeline arithmetic (D121 AW2)', () => {
  it('places a frame on a track and reads the frame under a pointer back', () => {
    expect(pct(0, [0, 100])).toBe('0%')
    expect(pct(25, [0, 100])).toBe('25%')
    expect(pct(30, [10, 50])).toBe('50%')
    expect(frameAt(150, 100, 200, [0, 100])).toBe(25)                          // 50 px into a 200 px track over 100 frames
    expect(frameAt(-40, 100, 200, [0, 100])).toBe(0)                            // clamped to the span
    expect(frameAt(900, 100, 200, [0, 100])).toBe(100)
    expect(deltaFrames(30, 300, [0, 120])).toBe(12)
    expect(deltaFrames(-1, 300, [0, 120])).toBe(-0)
  })
  it('ticks a second at the frame rate with its label, fewer minor ticks as the span grows', () => {
    const t = ticks([0, 48], 24)
    expect(t.filter((x) => x.major).map((x) => x.label)).toEqual(['0s', '1s', '2s'])
    expect(t.length).toBe(25)                                                   // every 2 frames over 48
    expect(ticks([0, 480], 24).every((x) => x.frame % 24 === 0)).toBe(true)
  })
  it("reads a figure's keys: a motion clip's bake as a bar, the rest as keys", () => {
    expect(keyRuns([0, 8, 1, 2, 3, 4, 20, 21])).toEqual({ runs: [[0, 4]], singles: [8, 20, 21] })
    expect(keyRuns([5, 5, 6])).toEqual({ runs: [], singles: [5, 6] })
    expect(keyRuns([])).toEqual({ runs: [], singles: [] })
  })
  it("shows the stage past its range and its last key, with room to drag", () => {
    expect(stageSpan(120, [])).toEqual([0, 132])
    expect(stageSpan(120, [300])).toEqual([0, 330])
  })
})

describe('the one transport (D121 AW2)', () => {
  afterEach(() => { useSession.setState((s) => ({ ui: { ...s.ui, suite: 'catalogue' } })) })
  const fake = (calls: string[], frame = 10, marks: number[] = []): Transport => ({
    ready: () => true, playing: () => false, play: () => calls.push('play'), frame: () => frame, seek: (f) => calls.push(`seek ${f}`), step: (d) => calls.push(`step ${d}`),
    home: () => calls.push('home'), end: () => calls.push('end'), marks: () => marks,
  })
  it('runs the transport of the level on screen, and none outside Animate', () => {
    const clay: string[] = [], fin: string[] = []
    registerTransport('stage', fake(clay, 10, [0, 8, 24]))
    registerTransport('final', fake(fin))
    useSession.setState((s) => ({ ui: { ...s.ui, suite: 'stage' } }))
    for (const id of ['anim.play', 'anim.stepForward', 'anim.back10', 'anim.home', 'anim.prevKey', 'anim.nextKey']) runCommand(id)
    expect(clay).toEqual(['play', 'step 1', 'step -10', 'home', 'seek 8', 'seek 24'])
    useSession.setState((s) => ({ ui: { ...s.ui, suite: 'final' } }))
    runCommand('anim.play'); runCommand('anim.end')
    expect(fin).toEqual(['play', 'end'])
    expect(runCommand('anim.setIn')).toBe(false)                              // no work area at Final
    useSession.setState((s) => ({ ui: { ...s.ui, suite: 'catalogue' } }))
    expect(transport()).toBeNull()
    expect(runCommand('anim.play')).toBe(false)
  })
  it('jumps between marks, strictly before or after the frame', () => {
    expect(neighbour([0, 8, 8, 24], 8, -1)).toBe(0)
    expect(neighbour([0, 8, 24], 8, 1)).toBe(24)
    expect(neighbour([0, 8, 24], 0, -1)).toBeNull()
    expect(TRANSPORT_IDS.has('anim.play') && TRANSPORT_IDS.has('anim.nextKey')).toBe(true)
  })
  it('keeps the clip player at Performance its own (the shuttle needs the animate level)', () => {
    const spy = vi.fn()
    registerTransport('stage', { ...fake([]), play: spy })
    useSession.setState((s) => ({ ui: { ...s.ui, suite: 'stage' } }))
    expect(runCommand('anim.shuttleStop')).toBe(false)
  })
})
