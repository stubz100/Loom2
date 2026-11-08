// The review of 2026-11-06 (journal 10:18 and 11:55), Clay's items: K56 a key keeps the holds and the gaze, K57 a pose edit under a gaze
// keeps the pose's own head, K58 undo keeps the render records and Cast's bodies, K62 the engine outlives a render in flight, K63 a removed
// object leaves no key or hold behind, K93 (open saves first and a 409 reloads its own stage; the scene picker's key; the back-to-camera rows;
// path geometries freed), K108 (undo reconciles the selection; F in the camera view), K61 (the benches free what they rebuild).
import * as THREE from 'three'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Profile, StageDoc, StageObject } from '../../api/types'
import { useSession } from '../../store/session'
import { sceneListKey } from '../../ui2/clay/clayStore'
import { useStory } from '../story/storyStore'
import { keyframesOf, objectSampler, sampleCamera, sampleDoc, type ObjectKey } from './anim'
import { POSES } from './builders'
import { StageEngine, withOwnHead } from './engine'
import { clearContent, disposeObject, loadOnce } from './gpu'
import { keyedPose, removedFrom, st, undoneTo, useStage } from './stageStore'
import { awayStretches } from './tracks'

const T = (pos: number[], rot = [0, 0, 0]) => ({ pos, rot, scale: [1, 1, 1] })
const obj = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: kind === 'mannequin' ? 'adult' : null, asset_id: null,
  transform: T([0, 0, 0]), parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1,
  pose: kind === 'mannequin' ? { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } : null,
  billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null,
  plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra }) as unknown as StageObject
const CAM = { id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }
const DOC = (objects: StageObject[], extra: Partial<StageDoc> = {}) => ({ schema_version: 4, id: 'stg_1', name: 'Quay', purpose: 'stage', bound: null, size: { w: 1920, h: 1080, fps: 24 }, objects,
  cameras: [CAM], active_camera: 'cam_1', ambient: null, keyframes: { camera: {}, objects: {} }, tracks: {}, length: 0,
  range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '', ...extra }) as unknown as StageDoc
const key = (frame: number, pos: number[], pose: ObjectKey['pose'] = null): ObjectKey => ({ frame, ease: 'linear', transform: T(pos), pose })

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })
const tick = () => new Promise<void>((r) => (globalThis as unknown as { setImmediate: (fn: () => void) => void }).setImmediate(r))
const settle = async () => { for (let i = 0; i < 10; i++) await tick() }

const HOLD = { r_hand: { object_id: 'table', joint: null } }
const GAZE = { camera: false, object_id: 'table', joint: null }

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  vi.stubGlobal('fetch', vi.fn(async () => json({})))
  setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
})
afterEach(() => {
  vi.unstubAllGlobals(); vi.useRealTimers()
  useStage.setState({ current: null, selected: null, selectedCamera: null, posing: false, selectedJoint: null, stages: [], undo: [], redo: [], frame: 0, view: 'free', mode: 'build', saving: false })
  useStory.setState({ profiles: [] })
})

describe('K56: a key keeps the figure\'s holds and gaze', () => {
  const pose = { preset: 'stand', joints: { head: [0, 10, 0] }, extra: {}, ground: 0, pins: { r_hand: [0, 0.8, 0] }, contacts: HOLD, gaze: GAZE }
  const keyed = () => DOC([obj('fig', 'mannequin', { pose }), obj('table', 'prop', { transform: T([1, 0, 0]) })],
    { keyframes: { camera: {}, objects: { fig: [key(0, [0, 0, 0], pose as never), key(40, [2, 0, 0], pose as never)] } } } as never)
  it('Key object writes the whole pose — the contacts and the gaze with the pins', () => {
    useStage.setState({ current: keyed(), frame: 10 })
    st().keyObject('fig')
    const k = keyframesOf(st().current!).objects.fig.find((x) => x.frame === 10)!
    expect(k.pose!.contacts).toEqual(HOLD)                                                     // was dropped: the prop-space pin read as the figure's own
    expect(k.pose!.gaze).toEqual(GAZE)
    expect(k.pose!.pins).toEqual({ r_hand: [0, 0.8, 0] })
  })
  it('a move of a keyed figure (the gizmo, the Inspector) keys its whole pose too', () => {
    useStage.setState({ current: keyed(), frame: 20 })
    st().setTransform('fig', T([5, 0, 0]))
    const k = keyframesOf(st().current!).objects.fig.find((x) => x.frame === 20)!
    expect(k.transform.pos).toEqual([5, 0, 0])
    expect(k.pose).toMatchObject({ contacts: HOLD, gaze: GAZE, pins: { r_hand: [0, 0.8, 0] } })
  })
  it('keyedPose copies every field (no shared arrays)', () => {
    const p = keyedPose(pose as never)!
    expect(p).toEqual({ ...pose })
    expect(p.joints).not.toBe(pose.joints)
    expect(keyedPose(null)).toBeNull()
  })
})

describe('K57: a pose edit under a gaze keeps the pose\'s own neck and head', () => {
  it('the live neck and head (the gaze\'s turn) are replaced by the pose\'s, the rest as read', () => {
    const live = { neck: [0, 25, 0], head: [5, 40, 0], r_elbow: [30, 0, 0] }
    const out = withOwnHead(live, { preset: 'stand', joints: { head: [0, 5, 0] }, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: GAZE } as never)
    expect(out.head).toEqual([0, 5, 0])                                                         // the pose's own
    expect(out.neck).toEqual(POSES.stand.j.neck ?? [0, 0, 0])                                   // the preset's
    expect(out.r_elbow).toEqual([30, 0, 0])
  })
})

describe('K58 / K108: undo and redo', () => {
  it('K58: an undo after a render keeps the passes, the album page and the revision', () => {
    useStage.setState({ current: DOC([obj('crate', 'prop')]), undo: [], redo: [] })
    st().apply((d) => ({ ...d, objects: [...d.objects, obj('stool', 'prop')] }), 'add')
    const passes = [{ camera_id: 'cam_1', revision: 2, assets: { clay: 'sha' } }]
    useStage.setState({ current: { ...st().current!, passes, group_id: 'grp_1', revision: 3 } as never })   // the render's reply (takeRendered)
    st().undoEdit()
    expect(st().current!.objects.map((o) => o.id)).toEqual(['crate'])
    expect(st().current!.passes).toEqual(passes)                                                // was [], PUT to the server: the record gone
    expect(st().current!.group_id).toBe('grp_1')
    expect(st().current!.revision).toBe(3)
    st().redoEdit()
    expect(st().current!.objects.map((o) => o.id)).toEqual(['crate', 'stool'])
    expect(st().current!.passes).toEqual(passes)
  })
  it('K58: a bound figure keeps the body Cast gave it since (an undo step never owned it)', () => {
    const B1 = { height_m: 1.7 }, B2 = { height_m: 1.9 }
    useStory.setState({ profiles: [{ id: 'prf_m', name: 'Mara', cls: 'character', current: 'v1', versions: [{ id: 'v1', body: B2, shell_asset_id: 'ast_shell' }] } as unknown as Profile] })
    const snap = DOC([obj('fig', 'mannequin', { profile_id: 'prf_m', body: B1 as never })])
    const cur = DOC([obj('fig', 'mannequin', { profile_id: 'prf_m', body: B2 as never, shadow_proxy: 'ast_shell' }), obj('crate', 'prop')])
    const doc = undoneTo(snap, cur)
    expect(doc.objects[0].body).toEqual(B2)
    expect(doc.objects[0].shadow_proxy).toBe('ast_shell')
  })
  it('K108: an undo that takes the selected thing away clears the selection and pose mode; a camera too', () => {
    useStage.setState({ current: DOC([obj('crate', 'prop')]), undo: [], redo: [] })
    const id = st().addObject('mannequin', 'adult', [1, 0, 0])!
    useStage.setState({ posing: true, selectedJoint: 'head' })
    expect(st().selected).toBe(id)
    st().undoEdit()
    expect(st().selected).toBeNull()
    expect(st().posing).toBe(false)
    expect(st().selectedJoint).toBeNull()
    st().addCamera()
    const cam = st().current!.active_camera!
    useStage.setState({ selectedCamera: cam })
    st().undoEdit()
    expect(st().selectedCamera).toBeNull()
  })
  it('K108: F in the camera view goes to the free view and frames there; Record frames nothing', () => {
    useStage.setState({ current: DOC([obj('crate', 'prop')]), view: 'camera', mode: 'build' })
    const n = st().frameRequest.n
    st().frameView(['crate'])
    expect(st().view).toBe('free')
    expect(st().frameRequest).toEqual({ ids: ['crate'], n: n + 1 })
    useStage.setState({ mode: 'record', view: 'camera' })
    st().frameView(null)
    expect(st().view).toBe('camera')
    expect(st().frameRequest.n).toBe(n + 1)
  })
})

describe('K63: a removed object leaves nothing that names it', () => {
  it('its keys, skeleton keys and blocks go; a hold on it becomes a pin where the hand is; a look at it ends', () => {
    const pose = { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: { r_hand: [0, 0.8, 0] }, contacts: HOLD, gaze: GAZE }
    const d = DOC([obj('fig', 'mannequin', { pose: pose as never }), obj('table', 'prop', { transform: T([1, 0, 0]) })], {
      keyframes: { camera: {}, objects: { table: [key(0, [1, 0, 0]), key(20, [3, 0, 0])], fig: [key(10, [0, 0, 0], pose as never)] }, skeleton: { table: [{ frame: 0, transition: 0, body: null }] } },
      tracks: { table: [] } } as never)
    const out = removedFrom(d, 'table')
    expect(out.objects.map((o) => o.id)).toEqual(['fig'])
    const k = keyframesOf(out)
    expect(Object.keys(k.objects)).toEqual(['fig'])                                             // the transport's marks go with it
    expect(Object.keys(k.skeleton ?? {})).toEqual([])
    expect(out.tracks).toEqual({})
    const fig = out.objects[0]
    expect(fig.pose!.contacts).toEqual({})
    expect(fig.pose!.gaze).toBeNull()
    expect(fig.pose!.pins!.r_hand).toEqual([1, 0.8, 0])                                         // the base pose read at the table's place
    const atTen = k.objects.fig[0].pose!
    expect(atTen.contacts).toEqual({})
    expect(atTen.pins!.r_hand).toEqual([2, 0.8, 0])                                             // the key read where the table was at frame 10
    expect(atTen.gaze).toBeNull()
    expect(removedFrom(d, 'nothing')).toBe(d)
  })
  it('the store removes through it (one undo step), a held thing let go where it stands', () => {
    useStage.setState({ current: DOC([obj('fig', 'mannequin'), obj('cup', 'prop', { parent: 'fig', parent_joint: 'r_hand' as never, transform: T([0, -0.04, 0.03]) })]), undo: [], redo: [],
      worldOf: (id: string) => (id === 'cup' ? T([0.3, 1, 0.1]) : null) })
    st().removeObject('fig')
    expect(st().current!.objects).toHaveLength(1)
    expect(st().current!.objects[0]).toMatchObject({ id: 'cup', parent: null, parent_joint: null, transform: T([0.3, 1, 0.1]) })
    expect(st().undo).toHaveLength(1)
  })
})

describe('K93: open() saves the pending edit first; a 409 reloads only its own stage', () => {
  it('a pending edit is PUT to its stage before the next one is read', async () => {
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      calls.push(`${req.method} ${new URL(req.url).pathname}`)
      if (req.method === 'PUT') return json({ ...DOC([]), name: 'Quay', revision: 2 })
      if (req.method === 'GET' && req.url.includes('/stages/stg_2')) return json({ ...DOC([]), id: 'stg_2', name: 'Pier' })
      return json({ items: [] })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })                                   // the client takes the fetch it is given
    useStage.setState({ current: DOC([]), stages: [], undo: [], redo: [] })
    st().apply((d) => ({ ...d, name: 'Quay edited' }), 'rename')
    const opened = st().open('stg_2')
    await settle(); await opened
    expect(calls.filter((c) => c.includes('/stages/stg_'))).toEqual(['PUT /stages/stg_1', 'GET /stages/stg_2'])   // the edit was saved to stg_1 (it went to stg_2 or nowhere)
    expect(st().current!.id).toBe('stg_2')
    await vi.advanceTimersByTimeAsync(500)
    expect(calls.filter((c) => c.startsWith('PUT'))).toHaveLength(1)
  })
  it('a 409 for a stage no longer open does not reopen it', async () => {
    const calls: string[] = []
    let answer: ((r: Response) => void) | null = null
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      calls.push(`${req.method} ${new URL(req.url).pathname}`)
      if (req.method === 'PUT') return new Promise<Response>((r) => { answer = r })
      if (req.method === 'GET' && req.url.includes('/stages/stg_2')) return json({ ...DOC([]), id: 'stg_2', name: 'Pier' })
      return json({ items: [] })
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })                                   // the client takes the fetch it is given
    const toast = vi.spyOn(useSession.getState(), 'toast')
    useStage.setState({ current: DOC([]), stages: [], undo: [], redo: [] })
    st().apply((d) => ({ ...d, name: 'Quay edited' }), 'rename')
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(answer).not.toBeNull()                                                               // the PUT is in flight
    await st().open('stg_2')
    expect(st().current!.id).toBe('stg_2')
    answer!(json({ detail: 'revision' }, 409))
    await settle()
    expect(calls.filter((c) => c === 'GET /stages/stg_1')).toHaveLength(0)                    // was reopened over the stage the author went to
    expect(st().current!.id).toBe('stg_2')
    expect(toast.mock.calls.at(-1)?.[0]).toContain('Quay')
    toast.mockRestore()
  })
})

describe('K93: the scene picker re-reads on a list change only', () => {
  it('a save\'s new revision is no change; a stage made, removed or renamed is', () => {
    const a = [{ id: 's1', name: 'Quay', revision: 1 }, { id: 's2', name: 'Pier', revision: 4 }]
    expect(sceneListKey(a, a[0])).toBe(sceneListKey(a.map((s) => ({ ...s, revision: s.revision + 1 })), { ...a[0], revision: 9 } as never))
    expect(sceneListKey(a, a[0])).not.toBe(sceneListKey([a[0], { ...a[1], name: 'Jetty' }], a[0]))
    expect(sceneListKey(a, a[0])).not.toBe(sceneListKey([...a, { id: 's3', name: 'Ferry', revision: 0 }], a[0]))
    expect(sceneListKey(a, a[0])).not.toBe(sceneListKey(a, { ...a[0], name: 'Quay 2' }))
  })
})

describe('K93: the back-to-camera rows sample the figure and the camera alone', () => {
  it('give what the whole document sampled per frame gave', () => {
    const turn = (frame: number, yaw: number, x: number): ObjectKey => ({ frame, ease: 'linear', transform: T([x, 0, 0], [0, yaw, 0]) })
    const doc = DOC([obj('fig', 'mannequin'), obj('crate', 'prop')], { keyframes: { camera: { cam_1: [{ frame: 0, ease: 'linear', pos: [0, 1.5, 5], target: [0, 1, 0], focal_mm: 35 }, { frame: 30, ease: 'linear', pos: [0, 1.5, -5], target: [0, 1, 0], focal_mm: 35 }] },
      objects: { fig: [turn(0, 0, 0), turn(15, 90, 1), turn(30, 0, 0)] } } } as never)
    const brute: [number, number][] = []
    let open: number | null = null
    for (let f = 0; f <= 30; f++) {
      const d = sampleDoc(doc, f), o = d.objects[0], c = d.cameras[0]
      const a = (o.transform.rot[1] * Math.PI) / 180, vx = c.pos[0] - o.transform.pos[0], vz = c.pos[2] - o.transform.pos[2]
      const away = (Math.sin(a) * vx + Math.cos(a) * vz) / Math.hypot(vx, vz) < Math.cos((110 * Math.PI) / 180)
      if (away && open === null) open = f
      if (!away && open !== null) { brute.push([open, f - 1]); open = null }
    }
    if (open !== null) brute.push([open, 30])
    expect(brute.length).toBeGreaterThan(0)
    expect(awayStretches(doc, 'fig', 'cam_1', 0, 30)).toEqual(brute)
    expect(objectSampler(doc, 'fig')!(15).transform.rot[1]).toBe(90)
    expect(objectSampler(doc, 'nobody')).toBeNull()
    expect(sampleCamera(CAM, keyframesOf(doc).camera.cam_1, 15).pos[2]).toBeCloseTo(0)
  })
})

describe('K62: the engine is not freed under a render', () => {
  it('dispose waits for the render in flight, then frees once', async () => {
    const e = Object.create(StageEngine.prototype) as unknown as { busy: number; disposeAfter: boolean; disposed: boolean; running: boolean; raf: number
      release: () => void; dispose: () => void; working: <T>(run: () => Promise<T>) => Promise<T> }
    Object.assign(e, { busy: 0, disposeAfter: false, disposed: false, running: true, raf: 0 })
    const release = vi.fn(() => { e.disposed = true })
    e.release = release
    let done: (v: string) => void = () => {}
    const render = e.working(() => new Promise<string>((r) => { done = r }))
    e.dispose()
    expect(release).not.toHaveBeenCalled()                                                     // the sequence goes on with its shells and crowds
    expect(e.running).toBe(false)                                                               // the viewport stops drawing at once
    done('frames')
    expect(await render).toBe('frames')
    expect(release).toHaveBeenCalledTimes(1)
    e.dispose()
    expect(release).toHaveBeenCalledTimes(1)
  })
})

describe('K93 / K61: what the views rebuild is freed', () => {
  it('a path changed or gone frees its line and dots, never the shared materials', () => {
    const e = Object.create(StageEngine.prototype) as unknown as { syncPaths: (d: StageDoc) => void; paths: Map<string, { line: THREE.Line; dots: THREE.Mesh[] }> }
    const pathMat = new THREE.LineBasicMaterial(), pathDot = new THREE.MeshBasicMaterial()
    Object.assign(e, { scene: new THREE.Scene(), paths: new Map(), pathMat, pathDot })
    const fig = (path: number[][] | null) => DOC([obj('fig', 'mannequin', { path: path as never })])
    e.syncPaths(fig([[0, 0], [1, 1]]))
    const first = e.paths.get('fig')!
    const line = vi.spyOn(first.line.geometry, 'dispose'), dot = vi.spyOn(first.dots[0].geometry, 'dispose'), mats = [vi.spyOn(pathMat, 'dispose'), vi.spyOn(pathDot, 'dispose')]
    e.syncPaths(fig([[0, 0], [2, 2]]))
    expect(line).toHaveBeenCalledTimes(1); expect(dot).toHaveBeenCalledTimes(1)
    const second = vi.spyOn(e.paths.get('fig')!.line.geometry, 'dispose')
    e.syncPaths(fig(null))
    expect(e.paths.size).toBe(0)
    expect(second).toHaveBeenCalledTimes(1)
    for (const m of mats) expect(m).not.toHaveBeenCalled()
  })
  it('clearContent frees and empties a pane; a skinned mesh\'s skeleton goes too', () => {
    const g = new THREE.Group(), box = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial())
    const bone = new THREE.Bone(), skin = new THREE.SkinnedMesh(new THREE.BoxGeometry(), new THREE.MeshBasicMaterial())
    skin.add(bone); skin.bind(new THREE.Skeleton([bone]))
    g.add(box, skin)
    const spies = [vi.spyOn(box.geometry, 'dispose'), vi.spyOn(box.material as THREE.Material, 'dispose'), vi.spyOn(skin.skeleton, 'dispose')]
    clearContent(g)
    expect(g.children).toHaveLength(0)
    for (const s of spies) expect(s).toHaveBeenCalledTimes(1)
    expect(disposeObject(new THREE.Group())).toEqual({ geometries: 0, materials: 0, textures: 0 })
  })
  it('loadOnce parses an asset once, another asset afresh, a failure again', async () => {
    const slot: { current: { id: string; p: Promise<string> } | null } = { current: null }
    const load = vi.fn(async (id: string) => { if (id === 'bad') throw new Error('404'); return `glb:${id}` })
    expect(await loadOnce(slot, 'a', load)).toBe('glb:a')
    expect(await loadOnce(slot, 'a', load)).toBe('glb:a')
    expect(load).toHaveBeenCalledTimes(1)
    expect(await loadOnce(slot, 'b', load)).toBe('glb:b')
    await expect(loadOnce(slot, 'bad', load)).rejects.toThrow('404')
    await settle()
    expect(slot.current).toBeNull()
    expect(load).toHaveBeenCalledTimes(3)
  })
})
