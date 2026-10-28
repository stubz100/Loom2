// AP1b (D141, proto01_UIcast 06 §2.9), the rest: a pin held to a thing or a joint follows it; the gaze turns the head within a neck's reach;
// an arm inside a broad torso is swung clear; a character's saved pose keeps what travels; a clip keeps the contacts and the gaze on its keys.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'
import { setBackend } from '../../../api/client'
import type { StageDoc, StageObject } from '../../../api/types'
import { applyPose, mannequin, POSES } from '../builders'
import { DEFAULT_BODY } from '../body'
import { st, useStage } from '../stageStore'
import { aimHead, clearArms, endsOf, holdPins, type Pins } from './contact'
import { contactChoices, docFrames, gazeTarget, mirrorContacts, portable, resolvePins, SELF, toContact, type Contacts } from './contacts'

const near = (a: number[] | undefined, b: number[] | undefined, tol = 0.003) => !!a && !!b && Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < tol
const T = { pos: [0, 0, 0], rot: [0, 0, 0], scale: [1, 1, 1] }
const figure = (id: string, name: string, extra: Partial<StageObject> = {}): StageObject => ({ id, kind: 'mannequin', name, preset: 'adult', asset_id: null, transform: { ...T }, parent: null, parent_joint: null, locked: false,
  visible: true, colour_id: 1, pose: { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null }, billboard: false, profile_id: null, version: null, body: null, detail: null, shadow_proxy: null, path: null, light: null,
  lens_deg: null, plate_asset_id: null, floor_y: null, height_m: null, place_set: null, ...extra } as unknown as StageObject)
const prop = (id: string, pos: number[]): StageObject => ({ ...figure(id, id), kind: 'prop', preset: 'crate', pose: null, transform: { pos, rot: [0, 0, 0], scale: [1, 1, 1] } } as unknown as StageObject)
const doc = (objects: StageObject[]): StageDoc => ({ schema_version: 2, id: 'st_1', name: 'q', revision: 1, size: { w: 1920, h: 1080, fps: 24 }, objects, cameras: [{ id: 'cam_1', name: 'A', pos: [0, 1.6, 4], target: [0, 1, 0], roll: 0, focal_mm: 35, sensor_mm: 36 }],
  active_camera: 'cam_1', range: { start: 0, end: 48 }, keyframes: { camera: {}, objects: {} }, passes: [], group_id: null, created_at: '', updated_at: '' } as unknown as StageDoc)

describe('contacts (AP1b, the rest)', () => {
  it('reads a pin in the frame it is held to: a hand on a crate goes where the crate goes', () => {
    const me = figure('obj_me', 'Mara'), crate = prop('obj_crate', [0.5, 0, 0.4])
    const d = doc([me, crate])
    const rest = endsOf('stand', {}, 0, null)
    const f = docFrames(d, 'obj_me')!
    const held = toContact(rest.r_hand, { object_id: 'obj_crate' }, f)!                       // the hand's point, written in the crate's space
    expect(near(held, [rest.r_hand[0] - 0.5, rest.r_hand[1], rest.r_hand[2] - 0.4])).toBe(true)
    expect(near(resolvePins({ r_hand: held }, { r_hand: { object_id: 'obj_crate' } }, f).r_hand, rest.r_hand)).toBe(true)   // and back
    const moved = doc([me, prop('obj_crate', [0.5, 0.3, 0.4])])                                 // the crate lifted 30 cm: the target rises with it
    const now = resolvePins({ r_hand: held }, { r_hand: { object_id: 'obj_crate' } }, docFrames(moved, 'obj_me'))
    expect(now.r_hand![1]).toBeCloseTo(rest.r_hand[1] + 0.3, 3)
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, null)         // the arm bent onto it
    holdPins(fig, now)
    const wrist = new THREE.Vector3(0, -fig.limbs.forearm, 0).applyMatrix4(fig.joints.r_elbow.matrixWorld)
    expect(Math.abs(wrist.y - (rest.r_hand[1] + 0.3))).toBeLessThan(0.003)
  })
  it("holds a hand to the figure's own hip through a turn of the hips, and to another figure's shoulder where that figure stands", () => {
    const rest = endsOf('stand', {}, 0, null)
    const me = figure('obj_me', 'Mara'), other = figure('obj_other', 'Ines', { transform: { pos: [1, 0, 0], rot: [0, 90, 0], scale: [1, 1, 1] } })
    const f0 = docFrames(doc([me, other]), 'obj_me')!
    const onHip = toContact(rest.r_hand, { object_id: SELF, joint: 'root' }, f0)!
    const turned = figure('obj_me', 'Mara', { pose: { preset: 'stand', joints: { root: [0, 40, 0] }, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } } as never)
    const back = resolvePins({ r_hand: onHip }, { r_hand: { object_id: SELF, joint: 'root' } }, docFrames(doc([turned, other]), 'obj_me'))
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, { root: [0, 40, 0] }, null)
    fig.root.updateMatrixWorld(true)
    const hip = fig.joints.root.localToWorld(new THREE.Vector3(onHip[0], onHip[1], onHip[2]))     // the point on the turned hips
    expect(near(back.r_hand, [hip.x, hip.y, hip.z])).toBe(true)
    expect(near(back.r_hand, rest.r_hand)).toBe(false)
    const onShoulder = toContact(rest.r_hand, { object_id: 'obj_other', joint: 'l_shoulder' }, f0)!
    const o2 = figure('obj_other', 'Ines', { transform: { pos: [1, 0, 0.5], rot: [0, 90, 0], scale: [1, 1, 1] } })
    const follow = resolvePins({ r_hand: onShoulder }, { r_hand: { object_id: 'obj_other', joint: 'l_shoulder' } }, docFrames(doc([me, o2]), 'obj_me'))
    expect(follow.r_hand![2]).toBeCloseTo(rest.r_hand[2] + 0.5, 3)                              // Ines stepped half a metre: the hand goes along
  })
  it('turns the head to what the figure looks at, a third of the turn on the neck, within what a neck does', () => {
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, null)
    const r = aimHead(fig, new THREE.Vector3(1.5, 1.5, 1.5))                                       // to the figure's left, a little up, ahead
    expect(r.head[1]).toBeGreaterThan(20); expect(r.neck[1]).toBeCloseTo(r.head[1] / 2, 1)
    fig.root.updateMatrixWorld(true)
    const pivot = fig.joints.head.getWorldPosition(new THREE.Vector3())
    const look = new THREE.Vector3(0, 0, 1).transformDirection(fig.joints.head.matrixWorld), want = new THREE.Vector3(1.5, 1.5, 1.5).sub(pivot).normalize()   // the face's +Z
    expect(THREE.MathUtils.radToDeg(look.angleTo(want))).toBeLessThan(1)
    const behind = aimHead(fig, new THREE.Vector3(0, 1.5, -2))                                      // behind: as far as the neck goes, no further
    expect(Math.abs(behind.head[1] + behind.neck[1])).toBeLessThanOrEqual(80.01)
    const f = docFrames(doc([figure('obj_me', 'Mara'), prop('obj_crate', [2, 0, 0])]), 'obj_me')!
    expect(gazeTarget({ camera: true }, f)!.z).toBeCloseTo(4, 3)
    expect(gazeTarget({ object_id: 'obj_crate' }, f)!.x).toBeCloseTo(2, 3)
    expect(gazeTarget(null, f)).toBeNull()
  })
  it('swings an arm clear of a heavy torso and leaves the default body alone', () => {
    const forward = { r_shoulder: [0, 60, 0], l_shoulder: [0, -60, 0], r_elbow: [-90, 0, 0], l_elbow: [-90, 0, 0] }   // the forearms across the belly
    const heavy = { ...DEFAULT_BODY, build: 'heavy' as const }
    const out = clearArms('stand', forward, 0, heavy)
    const moved = (a: number[], b: number[]) => Math.max(...a.map((v, i) => Math.abs(v - b[i])))
    expect(moved(out.r_shoulder, forward.r_shoulder)).toBeGreaterThanOrEqual(3); expect(moved(out.l_shoulder, forward.l_shoulder)).toBeGreaterThanOrEqual(3)
    expect(clearArms('stand', out, 0, heavy)).toEqual(out)                                                         // clear now: nothing more to swing
    expect(out.r_elbow).toEqual(forward.r_elbow)
    expect(clearArms('stand', {}, 0, DEFAULT_BODY)).toEqual({})
    expect(clearArms('stand', forward, 0, null)).toBe(forward)
  })
  it('mirrors the contacts with the ends, and keeps what travels with a character', () => {
    expect(mirrorContacts({ r_hand: { object_id: SELF, joint: 'r_hip' }, l_foot: { object_id: 'obj_crate' } })).toEqual({ l_hand: { object_id: SELF, joint: 'l_hip' }, r_foot: { object_id: 'obj_crate', joint: null } })
    const rest = endsOf('stand', {}, 0, null)
    const d = doc([figure('obj_me', 'Mara'), prop('obj_crate', [0.5, 0, 0.4])])
    const f = docFrames(d, 'obj_me')!
    const onCrate = toContact(rest.r_hand, { object_id: 'obj_crate' }, f)!
    const p = portable({ r_hand: onCrate, l_hand: rest.l_hand }, { r_hand: { object_id: 'obj_crate' }, l_hand: { object_id: 'obj_me', joint: 'root' } }, { object_id: 'obj_crate' }, 'obj_me', f)
    expect(near(p.pins.r_hand, rest.r_hand)).toBe(true); expect(p.contacts.r_hand).toBeUndefined()           // the crate's: a plain pin where the hand is
    expect(p.contacts.l_hand).toEqual({ object_id: SELF, joint: 'root' }); expect(p.gaze).toBeNull()         // its own hip stays; a look at a thing does not
    expect(portable({}, {}, { camera: true }, 'obj_me', f).gaze).toEqual({ camera: true, object_id: null, joint: null })
    expect(contactChoices(d, 'obj_me').map((c) => c.name)).toEqual(['obj_crate', 'its own'])
  })
})

describe('the store (AP1b, the rest)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } })))   // the stage's own saves
    setBackend({ host: '127.0.0.1', port: 8766, token: 't' })
    useStage.setState({ current: doc([figure('obj_me', 'Mara'), prop('obj_crate', [0.5, 0, 0.4])]), selected: 'obj_me', frame: 0, undo: [], redo: [] })
  })
  afterEach(() => { vi.unstubAllGlobals(); useStage.setState({ current: null, selected: null }) })
  const me = () => useStage.getState().current!.objects.find((o) => o.id === 'obj_me')!
  it('pins a hand to the crate, re-holds it in its own space, looks at the camera, and keeps them on a clip', () => {
    st().pinEnds('obj_me', ['r_hand'], { object_id: 'obj_crate', joint: null })
    expect(me().pose!.contacts!.r_hand).toEqual({ object_id: 'obj_crate', joint: null })
    const rest = endsOf('stand', {}, 0, null)
    expect(near(me().pose!.pins!.r_hand, [rest.r_hand[0] - 0.5, rest.r_hand[1], rest.r_hand[2] - 0.4])).toBe(true)
    st().setContact('obj_me', 'r_hand', null)
    expect(me().pose!.contacts).toEqual({}); expect(near(me().pose!.pins!.r_hand, rest.r_hand)).toBe(true)
    st().setContact('obj_me', 'r_hand', { object_id: SELF, joint: 'root' })
    expect(me().pose!.contacts!.r_hand).toEqual({ object_id: SELF, joint: 'root' })
    st().setGaze('obj_me', { camera: true, object_id: null, joint: null })
    expect(me().pose!.gaze?.camera).toBe(true)
    st().pinEnds('obj_me', ['l_foot'])
    st().applyMotion('obj_me', [{ frame: 0, ease: 'linear', transform: { ...T }, pose: { preset: 'stand', joints: {} } }, { frame: 12, ease: 'linear', transform: { ...T }, pose: { preset: 'stand', joints: { root: [0, 10, 0] } } }], 'clip')
    const keys = (useStage.getState().current!.keyframes as { objects: Record<string, { pose: NonNullable<StageObject['pose']> }[]> }).objects.obj_me
    expect(keys).toHaveLength(2)
    for (const k of keys) { expect(k.pose.contacts).toEqual({ r_hand: { object_id: SELF, joint: 'root' } }); expect(k.pose.gaze?.camera).toBe(true); expect(Object.keys(k.pose.pins ?? {})).toEqual(['r_hand']) }   // the plain pin stays off the keys
  })
  it('a preset clears the contacts with the pins and keeps the gaze; unpinning an end drops its contact', () => {
    st().pinEnds('obj_me', ['r_hand', 'l_hand'], { object_id: 'obj_crate', joint: null })
    st().setGaze('obj_me', { object_id: 'obj_crate', joint: null, camera: false })
    st().unpinEnds('obj_me', ['l_hand'])
    expect(Object.keys(me().pose!.contacts!)).toEqual(['r_hand'])
    st().applyPose('obj_me', 'crouch')
    expect(me().pose!.contacts).toEqual({}); expect(me().pose!.pins).toEqual({}); expect(me().pose!.gaze?.object_id).toBe('obj_crate')
    st().setGaze('obj_me', null)
    expect(me().pose!.gaze).toBeNull()
    const contacts: Contacts = { r_hand: { object_id: SELF, joint: 'r_hip' } }
    expect(mirrorContacts(contacts).l_hand?.joint).toBe('l_hip')
    const fig = mannequin(new THREE.MeshBasicMaterial(), POSES.stand, undefined, null)
    applyPose(fig.joints, POSES.stand, {}); expect(fig.joints.head.rotation.y).toBe(0)
    const p: Pins = {}; expect(resolvePins(p, {}, null)).toEqual({})
  })
})
