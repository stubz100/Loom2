// U1 (D157, proto01_UI2 06 §5.3): the seams the new shell stands on — the records' fan-out (subscribers hear the frames the session does not
// keep, one failing never stops the next), the context slots (a context's state kept on leaving and restored on returning), the Make panel's
// slot over the real store, and the key hosts the shell mounts.
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { describe, expect, it, vi } from 'vitest'
import type { EventFrame } from '../api/types'
import { KeyHosts, keyHostIds, registerKeyHost } from '../frame/keyHosts'
import { makeContext, useGenerate } from '../suites/generate/generateStore'
import { contextSlot } from './contexts'
import { onRecords } from './records'
import { applyEvent, useSession } from './session'

const frame = (type: string, data: unknown) => ({ type, data, ts: 0 }) as unknown as EventFrame

describe('U1: the records own the fan-out', () => {
  it('hands the frames the session does not keep to their subscribers, and keeps its own', () => {
    const heard: string[] = []
    const off = onRecords('test.a', ['hello', 'resync'], (f) => heard.push(f.type))                  // kinds today's holders ignore
    const bad = onRecords('test.b', ['hello'], () => { throw new Error('a broken subscriber') })
    const after = onRecords('test.c', ['hello'], (f) => heard.push(`c:${f.type}`))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})
    applyEvent(frame('hello', { version: 'x' }), useSession.setState, useSession.getState)
    applyEvent(frame('queue.state', { paused: false, counts: {} }), useSession.setState, useSession.getState)   // the session's own: not published
    expect(heard).toEqual(['hello', 'c:hello'])
    expect(err).toHaveBeenCalledOnce()
    off(); bad(); after(); err.mockRestore()
    applyEvent(frame('hello', { version: 'y' }), useSession.setState, useSession.getState)
    expect(heard).toHaveLength(2)
  })
})

describe('U1: the context slots', () => {
  it("keeps a context's state when it is left and restores it on return; a new context keeps what is there", () => {
    let v = 'shared'
    const slot = contextSlot(() => v, (x) => { v = x })
    slot.enter('ines/v1'); v = 'soaked, hood up'
    slot.enter('tomas/v1'); expect(v).toBe('soaked, hood up')               // never seen: what is on screen
    v = 'at the helm'
    slot.enter('ines/v1'); expect(v).toBe('soaked, hood up')
    slot.enter('ines/v1'); expect(slot.key).toBe('ines/v1')                // the same key again: nothing moves
    slot.enter('tomas/v1'); expect(v).toBe('at the helm')
    slot.forget('ines/v1'); expect(slot.saved('ines/v1')).toBeUndefined()
  })
  it("the Make panel's slot saves and restores the real panel", () => {
    vi.spyOn(useGenerate.getState(), 'refreshPreview').mockResolvedValue(undefined as never)
    makeContext.enter('world/character/prf_i/v1')
    useGenerate.getState().set({ text: 'Ines on the quay' })
    makeContext.enter('world/place/prf_q/v1')
    useGenerate.getState().set({ text: 'the quay, empty, eye level' })
    makeContext.enter('world/character/prf_i/v1')
    expect(useGenerate.getState().panel.text).toBe('Ines on the quay')
    makeContext.enter('world/place/prf_q/v1')
    expect(useGenerate.getState().panel.text).toBe('the quay, empty, eye level')
  })
})

describe('U1: the shell mounts the key hosts', () => {
  it('renders every registered host once, a host registered again replacing the first', () => {
    const mounted: string[] = []
    registerKeyHost('test.one', function One() { mounted.push('one'); return null })
    registerKeyHost('test.two', function Two() { mounted.push('two'); return null })
    registerKeyHost('test.two', function TwoAgain() { mounted.push('two again'); return null })
    expect(keyHostIds()).toEqual(expect.arrayContaining(['test.one', 'test.two']))
    const host = document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(<KeyHosts />))
    expect(mounted).toEqual(expect.arrayContaining(['one', 'two again']))
    expect(mounted).not.toContain('two')
    act(() => root.unmount())
  })
})
