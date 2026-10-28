// U1 (D157, proto01_UI2 06 §5.3): the router seam — navigate sets the tab, then the suite, and tells the new shell; every old place maps onto
// a layer; and no module but the router changes `ui.suite` (so the new shell hears every navigation).
import { afterEach, describe, expect, it } from 'vitest'
import { useSession } from '../store/session'
import { currentPlace, layerOf, navigate, onNavigate, useRailState, type Place } from './router'

const SOURCES = import.meta.glob<string>(['../**/*.ts', '../**/*.tsx', '!../**/*.test.ts', '!../**/*.test.tsx', '!../**/*.d.ts', '!../spikes/**'], { query: '?raw', import: 'default', eager: true })

describe('U1: the router', () => {
  afterEach(() => useSession.getState().setSuite('catalogue'))
  it('opens the suite on the named tab and tells every listener where it went, the tab resolved', () => {
    const heard: Place[] = []
    const off = onNavigate((p) => heard.push(p))
    navigate({ suite: 'story', tab: 'cast' })
    expect(useSession.getState().ui.suite).toBe('story')
    expect(useRailState.getState().active.story).toBe('cast')
    navigate({ suite: 'story' })                                                            // no tab: the one the suite remembers
    expect(currentPlace()).toEqual({ suite: 'story', tab: 'cast' })
    off()
    navigate({ suite: 'generate' })
    expect(heard).toEqual([{ suite: 'story', tab: 'cast' }, { suite: 'story', tab: 'cast' }])
  })
  it("maps the old places onto D157's layers", () => {
    expect([layerOf({ suite: 'generate' }), layerOf({ suite: 'edit' }), layerOf({ suite: 'story', tab: 'world' }), layerOf({ suite: 'story', tab: 'cast' })]).toEqual(['world', 'world', 'world', 'world'])
    expect([layerOf({ suite: 'stage' }), layerOf({ suite: 'animate' }), layerOf({ suite: 'final' }), layerOf({ suite: 'story', tab: 'flow' }), layerOf({ suite: 'story', tab: 'shots' })]).toEqual(['shots', 'shots', 'shots', 'shots', 'shots'])
    expect([layerOf({ suite: 'story', tab: 'episode' }), layerOf({ suite: 'catalogue' })]).toEqual(['episode', 'bin'])
  })
  it('is the only module that changes the suite — stores and commands navigate', () => {
    const callers = Object.keys(SOURCES).filter((p) => p !== './router.ts' && p !== '../store/session.ts' && /\.setSuite\(/.test(SOURCES[p]))
    expect(callers).toEqual([])
  })
})
