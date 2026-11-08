// The review of 2026-11-06 (register K1–K116), Story and the Flow: K73 node saves wait out a pause and a Flow read never puts back what is
// being typed; K77 a shot's lip-sync uses only its own lines; K79 / K80 a variable's name and an enum's values as typed; K81 the Shot
// templates load with the Flow; K83 one board read per change and the same shots kept; K96 the world's flush waits for a save on its way, a
// spoken line's words compared trimmed; K116 a selection of several on the canvas stays.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { FlowNode } from '../../api/types'
import { useSession } from '../../store/session'
import { lineVoiceStale } from './board'
import { canvasSelection } from './flow/types'
import { containedRect, pointIn } from './placeThingsStore'
import { enumValues, lipsyncLine, sameRecords, useStory, variableName } from './storyStore'

const node = (id: string, extra: Partial<FlowNode> = {}): FlowNode => ({
  schema_version: 1, id, type: 'shot', title: id, lines: [], options: [], cond: null, set: [], target: null, text: '', shot_id: null, shot_version: null, board_group_id: null, place_id: null,
  speaker_versions: {}, colour: null, beat_id: null, scene_id: null, own: [], revision: 1, created_at: '', updated_at: '', ...extra })

type Call = { method: string; path: string; body?: Record<string, unknown> }
let calls: Call[] = []
let server: Record<string, FlowNode> = {}
let hold: Promise<void> | null = null                                            // a GET /story/flow held until released

beforeEach(() => {
  calls = []
  server = { n1: node('n1') }
  hold = null
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : null
    const url = new URL(req ? req.url : String(input))
    const method = (req?.method ?? init?.method ?? 'GET').toUpperCase()
    const text = method === 'GET' ? '' : await (req ? req.text() : Promise.resolve(String(init?.body ?? '')))
    const body = text ? JSON.parse(text) as Record<string, unknown> : undefined
    calls.push({ method, path: url.pathname, body })
    if (method === 'GET' && url.pathname === '/story/flow') {
      const snap = Object.values(server).map((n) => ({ ...n }))
      if (hold) await hold
      return Response.json({ nodes: snap, graph: { schema_version: 1, revision: 1, nodes: snap.map((n) => ({ id: n.id, x: 0, y: 0 })), edges: [], start: null, updated_at: '' } })
    }
    if (method === 'PATCH' && url.pathname.startsWith('/story/flow/nodes/')) {
      const id = url.pathname.split('/').pop()!
      if (body?.revision !== server[id].revision) return Response.json({ detail: 'stale' }, { status: 409 })
      server[id] = { ...server[id], ...(body as Partial<FlowNode>), revision: server[id].revision + 1 }
      return Response.json(server[id])
    }
    if (url.pathname === '/story/scenes' || url.pathname === '/story/shot-templates' || url.pathname === '/story/shots') return Response.json({ items: [] })
    if (url.pathname === '/story/shots/cards') return Response.json({ items: [], guide_s: 30 })
    if (url.pathname === '/finals' || url.pathname === '/timelines') return Response.json({ items: [] })
    if (method === 'PUT' && url.pathname === '/story/world') return Response.json({ revision: 2, updated_at: 'now' })
    return Response.json({ items: [] })
  }))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
  useSession.setState({ toasts: [] })
  useStory.setState({ flowNodes: { n1: node('n1') }, flowGraph: null, nodeId: null })
})
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('K73: the Flow\'s node saves', () => {
  it('typed words wait out a pause: one PATCH with the last state, not one per keystroke', async () => {
    vi.useFakeTimers()
    const st = useStory.getState()
    void st.patchNode('n1', { title: 'T' }); void st.patchNode('n1', { title: 'Th' })
    const last = st.patchNode('n1', { title: 'The ferry' })
    expect(calls.filter((c) => c.method === 'PATCH')).toEqual([])
    await vi.advanceTimersByTimeAsync(500)
    await last
    const patches = calls.filter((c) => c.method === 'PATCH')
    expect(patches.map((c) => c.body?.title)).toEqual(['The ferry'])
    expect(server.n1.title).toBe('The ferry')
  })
  it('a pick goes at once, with what was typed', async () => {
    void useStory.getState().patchNode('n1', { title: 'Typed' })
    await useStory.getState().patchNode('n1', { place_id: 'prf_place' })
    expect(calls.filter((c) => c.method === 'PATCH').map((c) => [c.body?.title, c.body?.place_id])).toEqual([['Typed', 'prf_place']])
  })
  it('a Flow read that left before a keystroke does not put the old words back; an older read overtaken is not applied', async () => {
    let release!: () => void
    hold = new Promise<void>((r) => { release = r })
    const read = useStory.getState().loadFlow()                                    // e.g. a broadcast of the last save
    void useStory.getState().patchNode('n1', { title: 'typed meanwhile' })
    release(); await read
    expect(useStory.getState().flowNodes.n1.title).toBe('typed meanwhile')
    await useStory.getState().settleFlow()
    expect(server.n1.title).toBe('typed meanwhile')
    server.n2 = node('n2')                                                         // a node another writer makes, then deletes
    const reads = () => calls.filter((c) => c.path === '/story/flow').length
    const before = reads()
    hold = new Promise<void>((r) => { release = r })
    const older = useStory.getState().loadFlow()
    await vi.waitFor(() => expect(reads()).toBe(before + 1))                       // its reply holds n2
    delete server.n2
    hold = null
    await useStory.getState().loadFlow()
    expect(useStory.getState().flowNodes.n2).toBeUndefined()
    release(); await older
    expect(useStory.getState().flowNodes.n2).toBeUndefined()                       // the overtaken reply did not bring it back
  })
})

describe('K81 and K83: what the Flow reads', () => {
  it('the Shot templates load with the Flow, once per project', async () => {
    useSession.setState({ project: { open: true, path: 'F:/p/k81' } as never })
    await useStory.getState().loadFlow(); await useStory.getState().loadFlow()
    expect(calls.filter((c) => c.path === '/story/shot-templates').length).toBe(1)
  })
  it('two asks for the board in one turn are one read', async () => {
    const a = useStory.getState().loadBoard(), b = useStory.getState().loadBoard()
    await Promise.all([a, b])
    expect(calls.filter((c) => c.path === '/finals').length).toBe(1)
  })
  it('the same shots from the server keep the list (no board, no details read again)', () => {
    const shots = [{ id: 'sht_1', name: 'S', revision: 2, versions: [] }]
    expect(sameRecords(shots, [{ id: 'sht_1', name: 'S', revision: 2, versions: [] }])).toBe(true)
    expect(sameRecords(shots, [{ id: 'sht_1', name: 'S2', revision: 3, versions: [] }])).toBe(false)
    expect(sameRecords(shots, [])).toBe(false)
  })
})

describe('K96: the world flush', () => {
  it('waits for a save already on its way', async () => {
    let release!: () => void
    const gate = new Promise<void>((r) => { release = r })
    type Fetch = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    const f = globalThis.fetch as unknown as { getMockImplementation: () => Fetch | undefined; mockImplementation: (fn: Fetch) => void }
    const inner = f.getMockImplementation()!
    f.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => { const r = await inner(input, init); if (new URL(input instanceof Request ? input.url : String(input)).pathname === '/story/world') await gate; return r })
    useStory.setState({ world: { revision: 1, logline: '' } as never })
    useStory.getState().edit({ logline: 'A ferry' })
    void useStory.getState().flush()                                               // the save leaves
    let done = false
    const second = useStory.getState().flush().then(() => { done = true })
    await Promise.resolve(); await Promise.resolve()
    expect(done).toBe(false)
    release(); await second
    expect(useStory.getState().world?.revision).toBe(2)
  })
})

describe('the pure parts', () => {
  it('K77: the picked line only when it is the shot\'s own, else its first that fits', () => {
    const lines = [{ node_id: 'a', index: 0, too_long: true }, { node_id: 'a', index: 1, too_long: false }]
    expect(lipsyncLine(lines, { node_id: 'b', index: 0 })).toEqual(lines[1])                  // another shot's line is not taken
    expect(lipsyncLine(lines, { node_id: 'a', index: 0 })).toEqual(lines[0])                  // picked: said too long by the verb
    expect(lipsyncLine(lines, { node_id: null, index: null })).toEqual(lines[1])
    expect(lipsyncLine([], { node_id: 'a', index: 0 })).toBeUndefined()
  })
  it('K79: a name as typed, refused when empty or taken; K80: values as typed', () => {
    expect(variableName(' has letter ', ['mood'])).toEqual({ name: 'has_letter' })
    expect(variableName('2nd', [])).toEqual({ name: '_2nd' })
    expect(variableName('mood', ['mood'])).toEqual({ why: 'There is a variable named mood already' })
    expect(variableName('  ', [])).toHaveProperty('why')
    expect(enumValues('calm, storm,, calm ,fog')).toEqual(['calm', 'storm', 'fog'])
  })
  it('K96: a voiced line is stale only when its words changed, not for a space after them', () => {
    expect(lineVoiceStale({ audio_asset_id: 'ast_a', audio_text: 'Hello', text: 'Hello ' })).toBe(false)
    expect(lineVoiceStale({ audio_asset_id: 'ast_a', audio_text: 'Hello', text: 'Hello there' })).toBe(true)
    expect(lineVoiceStale({ audio_asset_id: null, audio_text: null, text: 'Hello' })).toBe(false)
  })
  it('K116: the canvas keeps its own selection of several while it holds the store\'s node; else the store\'s node alone', () => {
    const own = new Set(['a', 'b'])
    expect(['a', 'b', 'c'].map(canvasSelection(own, 'b'))).toEqual([true, true, false])     // Ctrl-click / Shift-drag
    expect(['a', 'b', 'c'].map(canvasSelection(own, 'c'))).toEqual([false, false, true])    // picked in the outline
    expect(['a', 'b'].map(canvasSelection(own, null))).toEqual([false, false])
  })
  it("K82: the things sheet maps a click against the picture as drawn (letterboxed), not the box", () => {
    expect(containedRect(800, 300, 1920, 1080)).toEqual({ x: (800 - 1920 * 300 / 1080) / 2, y: 0, w: 1920 * 300 / 1080, h: 300 })   // bars left and right
    expect(containedRect(800, 600, 1600, 900)).toEqual({ x: 0, y: 75, w: 800, h: 450 })
    const r = containedRect(800, 600, 1600, 900)
    expect(pointIn(400, 75 + 225, { left: r.x, top: r.y, width: r.w, height: r.h }, { w: 1600, h: 900 })).toEqual({ x: 800, y: 450 })   // the middle is the middle
  })
})
