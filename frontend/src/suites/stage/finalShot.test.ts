// D111 (PS5a): the final's frames at the shot's rate and its layers — the plate, each visible figure and prop (a 3D model, a stand-in, an
// image plane), the shadows; hidden objects, sets, lights and cameras make no layer of their own. SC3e: a picture set's plate is its picture,
// rendered by Stage's beauty pass with every actor hidden and stored as the plate's frames.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setBackend } from '../../api/client'
import type { Final, StageDoc, StageObject } from '../../api/types'
import { useSession } from '../../store/session'
import { batchCount, batchOf, bodyStamp, cameraTravel, framesAt, hasPictureSet, keysFrom, matteWarning, newestFinal, nextFinalStep, performedText, picturePlate, planFinal, plateChoice, shotRange, skeletonChange, useFinals } from './finalShot'
import { useStage } from './stageStore'

const obj = (id: string, kind: StageObject['kind'], extra: Partial<StageObject> = {}): StageObject => ({ id, kind, name: id, preset: null, asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  parent: null, parent_joint: null, locked: false, visible: true, colour_id: 1, pose: null, billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null, ...extra })
const doc = (objects: StageObject[], range = { start: 0, end: 48 }) => ({ objects, range }) as unknown as StageDoc

describe('D111 (PS5a) planning the final', () => {
  it('samples every frame at F24 and every 1.5th at F16 (finals.py frames_at)', () => {
    expect(framesAt(0, 3, 24)).toEqual([0, 1, 2, 3])
    expect(framesAt(0, 240, 16)).toHaveLength(161)
    expect(framesAt(0, 3, 16)).toEqual([0, 1.5, 3])
    expect(framesAt(5, 4, 16)).toEqual([])
  })
  it('makes one layer per visible figure and prop, between the plate and the shadows', () => {
    const p = planFinal(doc([obj('set_a', 'set', { name: 'Room' }), obj('light_1', 'light'), obj('fig_m', 'mannequin', { name: 'Mara', profile_id: 'prf_m' }),
      obj('chest', 'mesh', { name: 'Chest', profile_id: 'prf_c', version: 'v2' }), obj('box', 'prop'), obj('gone', 'mannequin', { visible: false }), obj('card', 'plane')]), 16)
    expect(p.times).toHaveLength(33)
    expect(p.layers.map((l) => `${l.kind}:${l.id}`)).toEqual(['plate:plate', 'figure:fig_m', 'prop:chest', 'prop:box', 'prop:card', 'shadows:shadows'])
    expect(p.layers[0].name).toBe('Room')
    expect(p.layers[1]).toMatchObject({ object_id: 'fig_m', profile_id: 'prf_m' })
    expect(p.layers[2]).toMatchObject({ object_id: 'chest', profile_id: 'prf_c', version: 'v2' })
  })
  it("W40: a final covers its shot version's own range when it has one, else the stage's", async () => {
    const { useStory } = await import('../story/storyStore')
    const d = doc([obj('fig_m', 'mannequin', { name: 'Mara' })])
    useStory.setState({ shots: [{ id: 'sht_a', current: 'v1', versions: [{ id: 'v1', range: { start: 48, end: 96 } }, { id: 'v2', range: null }] }] as never })
    expect(shotRange(d, { shot_id: 'sht_a', version: 'v1' })).toEqual({ start: 48, end: 96 })
    expect(shotRange(d, { shot_id: 'sht_a', version: null })).toEqual({ start: 48, end: 96 })     // the shot's current version
    expect(shotRange(d, { shot_id: 'sht_a', version: 'v2' })).toEqual({ start: d.range.start, end: d.range.end })   // no range of its own: the stage's
    expect(shotRange(d, null)).toEqual({ start: d.range.start, end: d.range.end })
    expect(planFinal(d, 16, { start: 48, end: 96 }).times).toHaveLength(33)
  })
  it("counts a performance's batches as the server plans them (77 frames, 5 carried)", () => {
    expect([9, 77, 78, 149, 150, 161].map(batchCount)).toEqual([1, 1, 2, 2, 3, 3])
  })
})

describe('SC3e the plate of a picture set', () => {
  const B = { host: '127.0.0.1', port: 8766, token: 't' }
  const picture = obj('set_p', 'set', { name: 'Picture set', preset: 'image', asset_id: 'ast_relief', plate_asset_id: 'ast_pic' })
  const fig = obj('fig_m', 'mannequin', { name: 'Mara' })
  const cam = { id: 'cam_1', name: 'Picture camera', pos: [0, 1, 0], target: [0, 1, -1], focal_mm: 26, sensor_mm: 36, roll: 0 }
  const stage = { id: 'stg_1', objects: [picture, fig], cameras: [cam], active_camera: 'cam_1', range: { start: 0, end: 3 }, revision: 4 } as unknown as StageDoc
  const final = { id: 'fin_1', name: 'Final 1', stage_id: 'stg_1', camera_id: 'cam_1', range: { start: 0, end: 3 }, rate: 16, frames: 3, size: { w: 832, h: 480 },
    layers: [{ id: 'plate', kind: 'plate', method: 'picture', status: 'passes', name: 'Picture set' }] } as unknown as Final
  let puts: { path: string; body: unknown }[] = []
  beforeEach(() => {
    puts = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(input instanceof Request ? input.url : String(input))
      const method = input instanceof Request ? input.method : init?.method ?? 'GET'
      if (method === 'PUT' && url.pathname.startsWith('/blobs/')) { puts.push({ path: url.pathname, body: null }); return Response.json({ ok: true }) }   // a Blob body: not read
      if (method === 'PUT' && url.pathname === '/finals/fin_1/layers/plate/frames') {
        const body = input instanceof Request ? await input.json() : JSON.parse(String(init?.body)); puts.push({ path: url.pathname, body })
        return Response.json({ ...final, layers: [{ ...final.layers[0], status: 'done', frames_done: 3, still_asset_id: 'ast_pic' }] })
      }
      return new Response('not stubbed', { status: 500 })
    }))
    setBackend(B)
    useSession.setState({ backend: B })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('knows a stage with a visible picture set', () => {
    expect(hasPictureSet(stage)).toBe(true)
    expect(hasPictureSet({ ...stage, objects: [{ ...picture, visible: false }, fig] } as StageDoc)).toBe(false)
    expect(hasPictureSet({ ...stage, objects: [obj('set_r', 'set', { preset: 'room' })] } as StageDoc)).toBe(false)
  })

  it("renders the beauty pass with every actor hidden through the final's camera, and stores it as the plate's frames", async () => {
    const calls: { kind: string; w: number; h: number; hidden: boolean[] }[] = []
    const render = vi.fn(async (frames: { doc: StageDoc }[], w: number, h: number, kind: string) => {
      calls.push({ kind, w, h, hidden: frames.map((f) => f.doc.objects.find((o) => o.id === 'fig_m')!.visible === false) })
      return { blobs: frames.map((_, i) => new Blob([new Uint8Array([i, i, i])], { type: 'image/png' })), keypoints: [], wholebody: [] }
    })
    useStage.setState({ current: stage, sequenceRenderer: render as never, frame: 0 })
    const done = await picturePlate(final)
    expect(calls).toEqual([{ kind: 'beauty', w: 832, h: 480, hidden: [true, true, true] }])           // F16 over 0–3: 0, 1.5, 3
    expect(puts.filter((p) => p.path.startsWith('/blobs/'))).toHaveLength(3)
    expect((puts.find((p) => p.path.endsWith('/frames'))!.body as { frames: string[] }).frames).toHaveLength(3)
    expect(done.layers[0]).toMatchObject({ status: 'done', still_asset_id: 'ast_pic' })
  })

  it("names the next step for the plate it is (rendered here, not a Klein still)", () => {
    useFinals.setState({ finals: [final], making: null, projecting: null })
    expect(nextFinalStep('stg_1').label).toBe('Render the plate ▶')
    useFinals.setState({ projecting: 'fin_1' })
    expect(nextFinalStep('stg_1')).toMatchObject({ label: 'Rendering the plate…', run: null })
    useFinals.setState({ finals: [{ ...final, layers: [{ ...final.layers[0], method: 'projected' }] } as unknown as Final], projecting: null })
    expect(nextFinalStep('stg_1').label).toBe('Make the plate ▶')
  })
  it("names the step of the stage's newest final, not the list's last (U0 F41: the list is newest first and a new final is prepended)", () => {
    const older = { ...final, id: 'fin_0', name: 'Final 1', created_at: '2026-10-28T10:00:00Z', layers: [{ ...final.layers[0], status: 'done' }] } as unknown as Final
    const newer = { ...final, id: 'fin_2', name: 'Final 2', created_at: '2026-10-28T11:00:00Z' } as unknown as Final
    const elsewhere = { ...final, id: 'fin_9', stage_id: 'stg_9', created_at: '2026-10-28T12:00:00Z' } as unknown as Final
    expect(newestFinal([newer, older, elsewhere], 'stg_1')?.id).toBe('fin_2')
    expect(newestFinal([older, newer], 'stg_1')?.id).toBe('fin_2')
    expect(newestFinal([elsewhere], 'stg_1')).toBeUndefined()
    useFinals.setState({ finals: [newer, older], making: null, projecting: null })
    expect(nextFinalStep('stg_1').label).toBe('Render the plate ▶')
  })
})

describe('CA3 (D130) the plate by the camera’s travel', () => {
  const cam = { id: 'cam', name: 'Camera', pos: [0, 1.6, 4], target: [0, 1.2, 0], focal_mm: 35, sensor_mm: 36, roll: 0 }
  const moving = (to: Partial<typeof cam>) => ({ id: 's', objects: [], cameras: [cam], active_camera: 'cam', range: { start: 0, end: 120 }, size: { w: 1920, h: 1080, fps: 24 },
    keyframes: { camera: { cam: [{ frame: 0, ease: 'linear', pos: cam.pos, target: cam.target, focal_mm: 35 }, { frame: 120, ease: 'linear', pos: to.pos ?? cam.pos, target: to.target ?? cam.target, focal_mm: to.focal_mm ?? 35 }] }, objects: {} } }) as unknown as StageDoc
  const times = framesAt(0, 120, 16)
  it('measures the turn, the orbit and how much more the camera sees', () => {
    const still = cameraTravel(moving({}), 'cam', times)
    expect(still).toEqual({ turn: 0, orbit: 0, widen: 1 })
    const a = (50 * Math.PI) / 180                                                    // E34's move: 50° about the target, a quarter closer
    const orbit = cameraTravel(moving({ pos: [4 * 0.75 * Math.sin(a), 1.6 * 0.75 + 1.2 * 0.25, 4 * 0.75 * Math.cos(a)] }), 'cam', times)
    expect(orbit.orbit).toBeGreaterThan(45); expect(orbit.widen).toBeCloseTo(1, 5)
    const pan = cameraTravel(moving({ target: [1.5, 1.2, 0] }), 'cam', times)
    expect(pan.turn).toBeGreaterThan(20); expect(pan.orbit).toBe(0)
    expect(cameraTravel(moving({ pos: [0, 1.6, 6] }), 'cam', times).widen).toBeGreaterThan(1.4)     // pulling back
    expect(cameraTravel(moving({ focal_mm: 24 }), 'cam', times).widen).toBeGreaterThan(1.4)          // zooming out
    expect(cameraTravel(moving({ pos: [0, 1.6, 3] }), 'cam', times).widen).toBe(1)                    // pushing in shows nothing new
  })
  it("makes a large move's plate projected and filled and a small one's projected (D135)", () => {
    expect(plateChoice({ turn: 50, orbit: 50, widen: 1 })).toEqual({ method: 'filled', why: 'the camera turns 50°' })    // D135: projected and filled
    expect(plateChoice({ turn: 0, orbit: 0, widen: 1.3 })).toEqual({ method: 'filled', why: 'the camera sees 30% more' })
    expect(plateChoice({ turn: 8, orbit: 5, widen: 1.05 })).toEqual({ method: 'projected', why: 'the camera moves little' })
  })
})

describe('CS3 (proto01_UIcast 06 §2.10): the skeleton changed under a drawn character', () => {
  const old = { height_m: 1.66, neck: 1.54 }, now = { height_m: 1.66, neck: 1.0 }
  const stage = (body: object, skeleton: object = {}, end = 240) => ({ id: 'stg', objects: [obj('fig_m', 'mannequin', { name: 'Mara', profile_id: 'prf_m', body: body as never })], cameras: [],
    range: { start: 0, end }, keyframes: { camera: {}, objects: {}, skeleton } }) as unknown as StageDoc
  const final = (d: StageDoc) => {
    const times = framesAt(0, 240, 16)
    return { id: 'fin', stage_id: 'stg', range: { start: 0, end: 240 }, rate: 16, frames: times.length, layers: [{ id: 'fig_m', kind: 'figure', object_id: 'fig_m', ...bodyStamp(d, 'fig_m', times) }] } as unknown as Final
  }
  it('stamps the body per frame, and finds where it changed and the batch that holds it', () => {
    const f = final(stage(old))
    expect(f.layers[0].body).toEqual(old); expect(new Set(f.layers[0].body_hashes).size).toBe(1)
    expect(skeletonChange(f, stage(old), 'fig_m')).toBeNull()                                         // nothing changed
    expect(skeletonChange(f, stage(now), 'fig_m')).toEqual({ index: 0, frame: 0, batch: 0 })          // Cast's changed: from the start
    expect(skeletonChange({ ...f, stage_id: 'other' }, stage(now), 'fig_m')).toBeNull()                // another stage open: no claim
    expect([batchOf(0), batchOf(76), batchOf(77), batchOf(148), batchOf(149)]).toEqual([0, 0, 1, 1, 2])
  })
  it("*Apply from a frame…*: the frames before it held as drawn, Cast's from it — only the batches from there change", () => {
    const d = stage(now)
    const keys = keysFrom(d, 'fig_m', old as never, 150)
    expect(keys).toEqual([{ frame: 0, transition: 0, body: old }, { frame: 150, transition: 0, body: null }])
    const ch = skeletonChange(final(stage(old)), stage(now, { fig_m: keys }), 'fig_m')!
    expect(ch.frame).toBe(150); expect(ch.index).toBe(100); expect(ch.batch).toBe(1)                // F16: frame 150 is the 101st; batch 2 of 3
    const earlier = keysFrom(stage(now, { fig_m: [{ frame: 0, transition: 0, body: null }, { frame: 200, transition: 0, body: { neck: 2 } }] }), 'fig_m', old as never, 150)
    expect(earlier).toEqual([{ frame: 0, transition: 0, body: old }, { frame: 150, transition: 0, body: null }, { frame: 200, transition: 0, body: { neck: 2 } }])   // a key that took Cast's before it holds the old body
  })
})

describe('D163 (E43): a character layer performed in its own window', () => {
  it('says the window and its scale when it queues the batches, else where the reference stands', () => {
    expect(performedText('Tomas', { batches: 1, placed: true, window: 7.54 }, 'queued')).toBe('Tomas: 1 batch of Wan Animate queued in a window of its own — the figure 7.5× larger there, pasted back after its matte')
    expect(performedText('Tomas', { batches: 3, placed: true, window: 12.4 }, 'staged')).toContain('3 batches of Wan Animate staged in a window of its own — the figure 12× larger')
    expect(performedText('Ines', { batches: 1, placed: false, window: null }, 'queued')).toBe('Ines: 1 batch of Wan Animate queued — the figure is not whole at the start: the reference is centred')
  })
  it('warns of a matte that strays from its figure, and is quiet when it holds', () => {
    expect(matteWarning({ frames: 49, strays: [9, 10, 11] })).toBe('the matte strays from the figure on 3 of 49 frames (first: 9)')
    expect(matteWarning({ frames: 49, strays: [] })).toBeNull()
    expect(matteWarning(null)).toBeNull()
  })
})
