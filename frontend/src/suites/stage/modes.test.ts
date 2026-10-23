// D121 (proto01_animate 26 §5): Animate's three levels as modes — each level's own rail (its column's sections), one panel width for the tab;
// pose mode by the figure (the pose pill), not by the column's scroll; the Final shot card's foot as the final's next step.
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { Composition, Final, StageDoc, StageObject } from '../../api/types'
import { DEFAULT_RAIL, TOP_TABS, widthKeyOf } from '../../frame/railTabs'
import { useSession } from '../../store/session'
import { nextFinalStep, useFinals } from './finalShot'
import { stageSteps, type StepInput } from './steps'
import { st, useStage } from './stageStore'

const OBJ = (id: string, kind: StageObject['kind']): StageObject => ({ id, kind, name: id, preset: null, asset_id: null, transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] },
  parent: null, locked: false, visible: true, colour_id: 1, pose: null, billboard: false, profile_id: null, version: null, body: null, detail: null, path: null, shadow_proxy: null, light: null,
  lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null })
const DOC = { id: 'stg_1', name: 'Room', size: { w: 1280, h: 720, fps: 24 }, objects: [OBJ('fig_1', 'mannequin'), OBJ('box_1', 'prop')],
  cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }], active_camera: 'cam_1',
  keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 12 }, passes: [], revision: 1 } as unknown as StageDoc
type Lay = { id: string; kind: string; name: string; status: string; frames_done: number }
const fin = (id: string, stage: string, layers: Lay[], extra: Partial<Final> = {}): Final => ({ id, stage_id: stage, name: id, frames: 9, rate: 16, layers, assembled_at: null, clip_id: null, ...extra }) as unknown as Final
const lay = (id: string, kind: string, status: string, done = 0): Lay => ({ id, kind, name: kind === 'figure' ? 'Mara' : id, status, frames_done: done })

describe('D121: a level is a mode', () => {
  it('gives each Animate level its own rail and the tab one panel width', () => {
    expect(DEFAULT_RAIL.stage.map((t) => t.id)).toEqual(['shot', 'scene', 'motion', 'camera'])
    expect(DEFAULT_RAIL.animate.map((t) => t.id)).toEqual(['shot', 'performance', 'clips'])                 // AW3: a clip's details under its row
    expect(DEFAULT_RAIL.final.map((t) => t.id)).toEqual(['shot', 'layers', 'output'])
    expect(TOP_TABS.find((t) => t.id === 'animate')?.suites).toEqual(['animate', 'stage', 'final'])
    expect(['stage', 'animate', 'final'].map(widthKeyOf)).toEqual(['animate', 'animate', 'animate'])
    expect(widthKeyOf('generate')).toBe('generate')
  })
})

describe('D121: pose mode by the figure', () => {
  beforeEach(() => useStage.setState({ current: DOC, selected: null, selectedJoint: null, posing: false, selectedCamera: null, stageSelected: false }))
  afterEach(() => useStage.setState({ current: null, selected: null, selectedJoint: null, posing: false }))
  it('poses only a figure, and leaves pose mode when the selection moves on', () => {
    st().select('box_1'); st().setPosing(true)
    expect(useStage.getState().posing).toBe(false)                                       // a prop has no joints
    st().select('fig_1'); st().setPosing(true)
    expect(useStage.getState().posing).toBe(true)
    st().select('fig_1')                                                                  // the same figure again keeps it (and its joint)
    expect(useStage.getState().posing).toBe(true)
    st().select('box_1')
    expect(useStage.getState().posing).toBe(false)
    st().select('fig_1'); st().selectJoint('r_elbow')                                     // a joint picked by name enters pose mode
    expect(useStage.getState()).toMatchObject({ posing: true, selectedJoint: 'r_elbow' })
    st().setPosing(false)                                                                 // Done drops the joint too
    expect(useStage.getState()).toMatchObject({ posing: false, selectedJoint: null })
    st().select('fig_1'); st().setPosing(true); st().selectCamera('cam_1')
    expect(useStage.getState().posing).toBe(false)
  })
})

describe("D121: the Final shot card's next step", () => {
  beforeEach(() => {
    useSession.setState({ jobs: {} } as never)
    useStage.setState({ current: DOC, rendering: false })
    useFinals.setState({ finals: [], making: null, compositions: {} })
  })
  afterEach(() => { useStage.setState({ current: null }); useFinals.setState({ finals: [], making: null, compositions: {} }) })
  const step = () => nextFinalStep('stg_1')
  const set = (f: Final, comps: Record<string, Composition | null> = {}) => useFinals.setState({ finals: [fin('old', 'stg_1', []), fin('other', 'stg_2', []), f], compositions: comps })

  it('makes the final first, and waits while it is split', () => {
    expect(nextFinalStep(null)).toMatchObject({ label: 'Make the final shot… ▶', run: null })
    expect(step().label).toBe('Make the final shot… ▶')
    expect(step().run).toBeTypeOf('function')
    useFinals.setState({ making: { done: 3, total: 12, what: 'Mara · pose' } })
    expect(step()).toMatchObject({ label: 'Splitting…', run: null, why: 'Mara · pose · 3 / 12' })
  })
  it("walks the newest final of this stage in the pipeline's order", () => {
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'passes'), lay('fig_1', 'figure', 'passes'), lay('shadows', 'shadows', 'passes')]))
    expect(step().label).toBe('Make the plate ▶')
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'passes'), lay('shadows', 'shadows', 'passes')]))
    expect(step().label).toBe('Perform Mara ▶')
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'running', 4), lay('shadows', 'shadows', 'passes')]))
    expect(step()).toMatchObject({ label: 'Working…', run: null, why: 'Mara: running' })
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'done', 9), lay('shadows', 'shadows', 'passes')]))
    expect(step().label).toBe('Assemble ▶')
    expect(step().run).toBeTypeOf('function')
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'done', 9)], { assembled_at: '2026-10-22T21:00:00Z' }))
    expect(step().label).toBe('Make the composition ▶')
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'done', 9)], { assembled_at: '2026-10-22T21:00:00Z' }), { f1: { revision: 0 } as unknown as Composition })
    expect(step().label).toBe('Open in Final ▸')
  })
  it('does not assemble while a layer is short of frames, and says so', () => {
    set(fin('f1', 'stg_1', [lay('plate', 'plate', 'done', 9), lay('fig_1', 'figure', 'done', 5)]))
    expect(step()).toMatchObject({ label: 'Assemble ▶', run: null, why: 'a layer is not made yet' })
  })
})

describe('D121 (AW3): the Shot stepper', () => {
  const base: StepInput = { camera: 'Camera 1', passes: null, stills: 0, frameRunning: false, clips: 0, clipRunning: false, final: null, making: false, comp: null }
  const states = (i: Partial<StepInput>) => stageSteps({ ...base, ...i }).map((s) => `${s.id}:${s.state}${s.count ? `:${s.count}` : ''}`)
  it('reads a new stage as nothing done, and sends each step where its verb is', () => {
    expect(states({})).toEqual(['passes:none', 'frame:none', 'clip:none', 'final:none', 'composition:none', 'render:none'])
    expect(stageSteps(base).map((s) => s.cmd)).toEqual(['anim.step.passes', 'stage.frame.make', 'anim.step.clip', 'anim.step.final', 'anim.step.final.open', 'anim.step.final.open'])
    expect(stageSteps(base)[0].tip).toContain('none yet')
  })
  it('marks stale passes, counts the frames and the clips, and shows what runs', () => {
    expect(states({ passes: { n: 5, size: '1280×720', stale: true }, stills: 2, clipRunning: true }).slice(0, 3)).toEqual(['passes:stale', 'frame:fresh:2', 'clip:running'])
    expect(states({ passes: { n: 5, size: '1280×720', stale: false }, frameRunning: true, clips: 3 }).slice(0, 3)).toEqual(['passes:fresh', 'frame:running', 'clip:fresh:3'])
  })
  it('follows the final through its layers, the composition and the render', () => {
    expect(states({ making: true })[3]).toBe('final:running')
    expect(states({ final: { layers: 4, done: 0, running: false, assembled: false } })[3]).toBe('final:none:0/4')
    expect(states({ final: { layers: 4, done: 2, running: false, assembled: false } })[3]).toBe('final:partial:2/4')
    expect(states({ final: { layers: 4, done: 2, running: true, assembled: false } })[3]).toBe('final:running:2/4')
    const done = { final: { layers: 4, done: 4, running: false, assembled: true } }
    expect(states({ ...done, comp: { revision: 3, stale: false, rendered: null, rendering: false } }).slice(3)).toEqual(['final:fresh', 'composition:fresh:r3', 'render:none'])
    expect(states({ ...done, comp: { revision: 3, stale: true, rendered: null, rendering: true } }).slice(4)).toEqual(['composition:stale:r3', 'render:running'])
    expect(states({ ...done, comp: { revision: 5, stale: false, rendered: 3, rendering: false } })[5]).toBe('render:stale')
    expect(states({ ...done, comp: { revision: 5, stale: false, rendered: 5, rendering: false } })[5]).toBe('render:fresh')
  })
})
