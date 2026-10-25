// AP1b (D141, proto01_UIcast 06 §2.9): the pose editor's pins — a hand or a foot held in the figure's own space while the rest of the pose
// changes (its limb bent by IK that keeps the limb's twist: knees forward, elbows back), the limb the author works taking its pin along;
// the store keeps them through edits, mirrors them, clears them with a preset; a character's own pose stands in for a starter preset.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'
import { setBackend } from '../../../api/client'
import type { Profile, ProfileVersion, StageDoc, StageObject } from '../../../api/types'
import { useStory } from '../../story/storyStore'
import { applyPose, mannequin, POSES } from '../builders'
import { st, useStage } from '../stageStore'
import { chainOf, endsOf, mirrorPins, pinPose, type Pins } from './contact'

const near = (a: number[] | undefined, b: number[] | undefined, tol = 0.002) => !!a && !!b && Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < tol
const kneeZ = (joints: Record<string, number[]>, ground: number) => {
  const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, null)
  applyPose(fig.joints, POSES.stand, joints, ground); fig.root.updateMatrixWorld(true)
  return { knee: fig.joints.r_knee.getWorldPosition(new THREE.Vector3()).z, elbow: fig.joints.r_elbow.getWorldPosition(new THREE.Vector3()).z }
}
const rest = endsOf('stand', undefined, 0, null)
const ALL: Pins = { r_foot: rest.r_foot, l_foot: rest.l_foot, r_hand: rest.r_hand, l_hand: rest.l_hand }

describe('pins (AP1b, D141)', () => {
  it("measures the ends in the figure's own space: the feet on the floor, the hands at the sides", () => {
    expect(rest.r_foot[1]).toBeGreaterThan(0.02); expect(rest.r_foot[1]).toBeLessThan(0.08)        // the ankle a few cm over the floor
    expect(rest.r_foot[0]).toBeCloseTo(-rest.l_foot[0], 4)                                           // +X is the left
    expect(rest.r_hand[1]).toBeGreaterThan(0.7)
    expect(chainOf('r_elbow')).toBe('r_arm'); expect(chainOf('l_knee')).toBe('l_leg'); expect(chainOf('spine')).toBeNull()
  })
  it('holds pinned hands and feet while the hips drop and turn and the spine leans, knees forward and elbows back', () => {
    for (const [joints, ground] of [[{}, 0.12], [{ root: [0, 25, 0] }, 0.08], [{ spine: [-30, 0, 0] }, 0]] as const) {
      const free = endsOf('stand', joints as Record<string, number[]>, ground, null)
      expect(near(free.r_foot, rest.r_foot) && near(free.r_hand, rest.r_hand)).toBe(false)         // unpinned, something moves
      const r = pinPose('stand', joints as Record<string, number[]>, ground, ALL, null, null)
      const now = endsOf('stand', r.joints, ground, null)
      for (const e of ['r_foot', 'l_foot', 'r_hand', 'l_hand'] as const) expect(near(now[e], rest[e])).toBe(true)
      expect(r.pins).toEqual(ALL)
      if (ground > 0.1) {
        const z = kneeZ(r.joints, ground)
        expect(z.knee).toBeGreaterThan(0.1); expect(z.elbow).toBeLessThan(-0.1)                    // a squat's knees, a push's elbows
        expect(Math.abs(r.joints.r_hip[1])).toBeLessThan(1)                                         // no thigh turned half round
      }
    }
  })
  it('lets the limb the author works take its pin along', () => {
    const lifted = { r_shoulder: [-60, 0, -8] }
    const r = pinPose('stand', lifted, 0, ALL, null, 'r_arm')
    expect(r.joints.r_shoulder).toEqual([-60, 0, -8])                                                // as turned
    expect(near(r.pins.r_hand, endsOf('stand', lifted, 0, null).r_hand)).toBe(true)
    expect(near(r.pins.r_hand, rest.r_hand)).toBe(false)
    expect(r.pins.l_hand).toEqual(rest.l_hand)
  })
  it('mirrors pins across the figure', () => {
    expect(mirrorPins({ r_hand: [-0.3, 1, 0.2] })).toEqual({ l_hand: [0.3, 1, 0.2] })
  })
})

const ver = (v: Partial<ProfileVersion>): ProfileVersion => ({ id: 'v1', label: 'v1', state: 'open', group_id: 'grp_1', candidates_group_id: null, hero_asset_id: null, body: null, anim_ref_asset_id: null,
  anim_ref_back_asset_id: null, anim_test_clip_id: null, shell_asset_id: null, shell_from: null, poses: {}, from_idea: null, model_asset_id: null, model_from: null, body_fit_from: null, body_points: null, anim_ref_note: null,
  appearance: '', outfit: '', colours: [], marks: '', trigger: null, lora: null, derived_from: null, created_at: '', locked_at: null, ...v })
const MINE = { preset: 'crouch', joints: { r_knee: [100, 0, 0] }, extra: {}, ground: 0.2, pins: { r_foot: [-0.1, 0.04, 0.2] } }
const MARA = { id: 'prf_m', name: 'Mara', cls: 'character', current: 'v1', schema_version: 2, revision: 0, voice_id: null, created_at: '', updated_at: '', versions: [ver({ poses: { crouch: MINE } })] } as unknown as Profile
const FIG = { id: 'fig_1', kind: 'mannequin', name: 'Mara', preset: 'adult', asset_id: null, body: null, detail: null, path: null, shadow_proxy: null, light: null, parent: null, parent_joint: null, locked: false,
  visible: true, colour_id: 1, pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {} }, billboard: false, profile_id: 'prf_m', version: null,
  transform: { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] } } as unknown as StageObject
const DOC = { schema_version: 2, id: 'stg_1', name: 'Quay', size: { w: 1920, h: 1080, fps: 24 }, objects: [FIG], cameras: [{ id: 'cam_1', name: 'Camera 1', pos: [0, 1.5, 5], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }],
  active_camera: 'cam_1', keyframes: { camera: {}, objects: {} }, range: { start: 0, end: 120 }, passes: [], group_id: null, revision: 1, created_at: '', updated_at: '' } as unknown as StageDoc
const pose = () => useStage.getState().current!.objects[0].pose!
let saved: { url: string; body: unknown }[] = []

describe('the pins in the store (AP1b)', () => {
  beforeEach(() => {
    saved = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(String(input), init)
      if (req.url.includes('/poses/')) {
        const body = JSON.parse(await req.text()); saved.push({ url: decodeURIComponent(req.url), body })
        const v = { ...MARA.versions[0], poses: { ...MARA.versions[0].poses, hold: body } }
        return new Response(JSON.stringify({ ...MARA, versions: [v] }), { status: 200, headers: { 'content-type': 'application/json' } })
      }
      return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })        // the stage's own saves
    }))
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useStory.setState({ profiles: [MARA] })
    useStage.setState({ current: DOC, selected: 'fig_1', frame: 0, undo: [], redo: [] })
  })
  afterEach(() => { vi.unstubAllGlobals(); useStage.setState({ current: null, selected: null }); useStory.setState({ profiles: [] }) })

  it('pins, keeps them through a turn of the hips, mirrors and unpins them; a preset clears them', () => {
    st().pinEnds('fig_1', ['r_foot', 'l_foot'])
    expect(near(pose().pins.r_foot, rest.r_foot)).toBe(true)
    st().setJoints('fig_1', { ...pose().joints, root: [0, 20, 0] }, null)                           // the hips turned in the viewport
    expect(near(endsOf('stand', pose().joints, 0, null).r_foot, rest.r_foot)).toBe(true)
    st().mirrorPose('fig_1')
    expect(Object.keys(pose().pins).sort()).toEqual(['l_foot', 'r_foot'])
    st().unpinEnds('fig_1', ['l_foot'])
    expect(Object.keys(pose().pins)).toEqual(['r_foot'])
    st().applyPose('fig_1', 'sit')
    expect(pose().pins).toEqual({})
  })
  it("takes the character's own version of a starter pose, and saves one for the character", async () => {
    st().applyPose('fig_1', 'crouch')
    expect(pose()).toMatchObject({ preset: 'crouch', ground: 0.2, pins: MINE.pins })
    expect(pose().joints.r_knee).toEqual([100, 0, 0])
    st().pinEnds('fig_1', ['r_hand'])
    await st().saveForCharacter('fig_1', 'hold')
    expect(saved[0].url).toContain('/story/profiles/prf_m/versions/v1/poses/hold')
    expect(saved[0].body).toMatchObject({ preset: 'crouch', ground: 0.2 })
    expect(Object.keys((saved[0].body as { pins: object }).pins).sort()).toEqual(['r_foot', 'r_hand'])
    expect(useStory.getState().profiles[0].versions[0].poses.hold).toBeTruthy()
  })
})
