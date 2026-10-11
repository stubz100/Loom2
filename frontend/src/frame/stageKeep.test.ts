// D69 (ArtCraft P5): the keep-alive release policy — a hidden heavy stage is unmounted after `ui.editKeepAliveMin` minutes hidden, or at
// once when the orchestrator admits a GPU job under VRAM pressure (`engine.vram_pressure`); the stage on screen is never released.
// Lazy suites: static meta at once, the code loaded once however often it is asked for.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EventFrame } from '../api/types'
import { applyEvent, useSession } from '../store/session'
import { lazySuite, preloadSuite } from './lazySuite'
import { useStageKeep } from './stageKeep'
import type { SuiteDef } from './suiteRegistry'

let now = 0
beforeEach(() => {
  now = 1_000
  vi.spyOn(performance, 'now').mockImplementation(() => now)
  vi.spyOn(console, 'info').mockImplementation(() => undefined)
  useStageKeep.setState({ mounted: [], hiddenAt: {} })
  useSession.setState({ toasts: [] })
})

describe('keep-alive stages', () => {
  it('a visit mounts once; hiding keeps it mounted', () => {
    const k = useStageKeep.getState()
    k.visit('edit'); k.visit('edit'); k.hide('edit')
    expect(useStageKeep.getState().mounted).toEqual(['edit'])
    expect(useStageKeep.getState().hiddenAt.edit).toBe(1_000)
  })
  it('expires only the stages hidden longer than the setting, never the active one', () => {
    const k = useStageKeep.getState()
    k.visit('edit'); k.visit('animate')
    k.hide('edit'); now += 4 * 60_000; k.hide('animate')
    now += 7 * 60_000                                                   // edit hidden 11 min, animate 7 min
    expect(useStageKeep.getState().expire('catalogue', 10)).toEqual(['edit'])
    expect(useStageKeep.getState().mounted).toEqual(['animate'])
    now += 60 * 60_000
    expect(useStageKeep.getState().expire('animate', 10)).toEqual([])   // on screen: kept however long its hiddenAt is
  })
  it('releaseHidden unmounts every stage but the active one', () => {
    const k = useStageKeep.getState()
    k.visit('edit'); k.visit('animate')
    expect(useStageKeep.getState().releaseHidden('animate', 'test')).toEqual(['edit'])
    expect(useStageKeep.getState().mounted).toEqual(['animate'])
  })
})

const pressure = { type: 'engine.vram_pressure', data: { job_id: 'job_00000007', free_gb: 1.2, threshold_gb: 2.5 }, seq: 1, t: 0 } as unknown as EventFrame
const route = (f: EventFrame) => applyEvent(f, useSession.setState, useSession.getState)

describe('engine.vram_pressure', () => {
  it('releases the hidden editor and says so', async () => {
    useStageKeep.getState().visit('edit')
    useSession.setState({ ui: { ...useSession.getState().ui, suite: 'catalogue' } })
    route(pressure)
    await vi.waitFor(() => expect(useStageKeep.getState().mounted).toEqual([]))
    await vi.waitFor(() => expect(useSession.getState().toasts.map((t) => t.text)).toEqual([expect.stringContaining('hidden editor canvas')]))
  })
  it('leaves the editor on screen alone, without a toast', async () => {
    useStageKeep.getState().visit('edit')
    useSession.setState({ ui: { ...useSession.getState().ui, suite: 'edit' } })
    route(pressure)
    await new Promise((ok) => setTimeout(ok, 20))
    expect(useStageKeep.getState().mounted).toEqual(['edit'])
    expect(useSession.getState().toasts).toEqual([])
  })
})

describe('lazy suites', () => {
  it('shows the static meta at once and loads the code once', async () => {
    const Panel = () => null
    const load = vi.fn(async () => ({ id: 'lazyfix', rail: [], Panel, Strip: Panel, Stage: Panel, Inspector: Panel }) as SuiteDef)
    const def = lazySuite({ id: 'lazyfix', rail: [], keepAlive: true }, load, ['Panel', 'Stage'])
    expect(def).toMatchObject({ id: 'lazyfix', keepAlive: true })
    expect(typeof def.Panel).toBe('function')
    expect(def.Strip).toBeUndefined()                                   // only the parts asked for are wrapped
    expect(load).not.toHaveBeenCalled()
    preloadSuite('lazyfix'); preloadSuite('lazyfix'); preloadSuite('unknown')
    expect(load).toHaveBeenCalledTimes(1)
  })
})
