// AP1b (proto01_UIcast 06 §2.9, D141), the rest: a pin held to a thing or to a joint, and the gaze. A contact names the frame a pin's point
// is read in — a thing's own transform (the hand goes with the prop it rests on), a figure's joint (a hand on another's shoulder, or on the
// figure's own hip: "self") — so the limb follows what it touches, frame by frame through a clip. The gaze names what the head turns to: a
// thing, a figure's face, or the active camera. Pure: the frames come from the document (an off-screen figure posed for a joint), the same
// maths the engine runs on its live scene (engine.ts holdContacts), so the store's solve and the viewport agree.
import * as THREE from 'three'
import type { StageCamera, StageDoc, StageObject } from '../../../api/types'
import { mannequin, POSES, type Joint, type Mannequin } from '../builders'
import { HAND_MARKER, heldWorld, matrixOf } from '../held'
import { ENDS, type End, type Pins } from './contact'

/** What the document stores (stages.py Contact / Gaze — every field written). */
export interface Contact { object_id: string; joint: Joint | null }
export interface Gaze { object_id: string | null; joint: Joint | null; camera: boolean }
/** What the maths reads (a field left out reads as none). */
export interface ContactLike { object_id: string; joint?: Joint | null }
export interface GazeLike { object_id?: string | null; joint?: Joint | null; camera?: boolean }
export type Contacts = Partial<Record<End, ContactLike>>
/** A contact's object for the figure's own joint — what a character's saved pose keeps (a stage's object id means nothing on another). */
export const SELF = 'self'

const mat = new THREE.MeshBasicMaterial()

/** The frames of a document, built on demand: a thing's holder (its transform under its parent's; a held thing in its figure's hand) and a
 *  figure's joints (an off-screen figure in its pose, under its holder). */
export class DocFrames {
  private holders = new Map<string, THREE.Matrix4 | null>()
  private figures = new Map<string, Mannequin | null>()
  private doc: Pick<StageDoc, 'objects' | 'cameras' | 'active_camera'>
  constructor(doc: Pick<StageDoc, 'objects' | 'cameras' | 'active_camera'>) { this.doc = doc }
  object(id: string): StageObject | undefined { return this.doc.objects.find((o) => o.id === id) }
  /** The object's holder in the world (null: no such object, or a loop of parents). */
  holder(id: string, seen = new Set<string>()): THREE.Matrix4 | null {
    if (this.holders.has(id)) return this.holders.get(id)!
    const o = this.object(id)
    let m: THREE.Matrix4 | null = null
    if (o && !seen.has(id)) {
      seen.add(id)
      if (o.parent_joint && o.parent) {
        const fig = this.figure(o.parent, seen)
        const hand = fig?.markers[HAND_MARKER[o.parent_joint]]
        m = hand ? heldWorld(hand, o.transform) : matrixOf(o.transform)
      } else if (o.parent) {
        const p = this.holder(o.parent, seen)
        m = p ? p.clone().multiply(matrixOf(o.transform)) : matrixOf(o.transform)
      } else m = matrixOf(o.transform)
    }
    this.holders.set(id, m)
    return m
  }
  /** A figure in its pose under its holder (world matrices current); null for a thing that is no figure. */
  figure(id: string, seen = new Set<string>()): Mannequin | null {
    if (this.figures.has(id)) return this.figures.get(id)!
    const o = this.object(id)
    let fig: Mannequin | null = null
    if (o?.kind === 'mannequin') {
      const h = this.holder(id, seen)
      fig = mannequin(mat, POSES[o.pose?.preset ?? 'stand'] ?? POSES.stand, o.pose?.joints, o.body as never, o.pose?.ground ?? 0)
      const holder = new THREE.Group()
      if (h) { holder.matrix.copy(h); holder.matrixAutoUpdate = false }
      holder.add(fig.root)
      holder.updateMatrixWorld(true)
    }
    this.figures.set(id, fig)
    return fig
  }
  /** A contact's or a gaze's frame in the world: a joint of a figure (its matrix), else the thing's holder. */
  frame(c: { object_id?: string | null; joint?: Joint | null }, selfId: string): THREE.Matrix4 | null {
    const id = !c.object_id || c.object_id === SELF ? selfId : c.object_id
    if (c.joint) { const fig = this.figure(id); return fig ? fig.joints[c.joint].matrixWorld.clone() : null }
    return this.holder(id)
  }
  /** Where a gaze looks, in the world: the camera, a figure's face (its nose), or a thing's origin. */
  gazePoint(g: GazeLike, selfId: string): THREE.Vector3 | null {
    if (g.camera) {
      const c = this.doc.cameras.find((x) => x.id === this.doc.active_camera) ?? this.doc.cameras[0]
      return c ? new THREE.Vector3(c.pos[0], c.pos[1], c.pos[2]) : null
    }
    if (!g.object_id) return null
    const id = g.object_id === SELF ? selfId : g.object_id
    const fig = this.figure(id)
    if (fig && (!g.joint || g.joint === 'head')) return fig.markers[0].getWorldPosition(new THREE.Vector3())
    if (fig && g.joint) return fig.joints[g.joint].getWorldPosition(new THREE.Vector3())
    const h = this.holder(id)
    return h ? new THREE.Vector3().setFromMatrixPosition(h) : null
  }
}

/** What a live scene or a document gives the solve: the figure's own frame and the frames it touches. */
export interface Frames {
  own: THREE.Matrix4
  frame: (c: { object_id?: string | null; joint?: Joint | null }) => THREE.Matrix4 | null
  gaze: (g: GazeLike) => THREE.Vector3 | null
}

export const docFrames = (doc: Pick<StageDoc, 'objects' | 'cameras' | 'active_camera'>, selfId: string): Frames | null => {
  const f = new DocFrames(doc)
  const own = f.holder(selfId)
  return own ? { own, frame: (c) => f.frame(c, selfId), gaze: (g) => f.gazePoint(g, selfId) } : null
}

/** The pins as the figure's own space sees them now: a pinned end with a contact read in its frame and brought over; the rest as they are. */
export function resolvePins(pins: Pins | null | undefined, contacts: Contacts | null | undefined, f: Frames | null): Pins {
  const out: Pins = {}
  const ownInv = f ? f.own.clone().invert() : null
  for (const end of ENDS) {
    const p = pins?.[end]
    if (!p) continue
    const c = contacts?.[end]
    const m = c && f ? f.frame(c) : null
    if (c && m && ownInv) { const v = new THREE.Vector3(p[0], p[1], p[2]).applyMatrix4(m).applyMatrix4(ownInv); out[end] = [v.x, v.y, v.z].map((x) => Math.round(x * 1e4) / 1e4) }
    else out[end] = [...p]
  }
  return out
}

/** A point of the figure's own space written in a contact's frame (what the pin stores from then on); null when the frame is not there. */
export function toContact(ownPoint: number[], c: ContactLike, f: Frames | null): number[] | null {
  const m = f?.frame(c)
  if (!m || !f) return null
  const v = new THREE.Vector3(ownPoint[0], ownPoint[1], ownPoint[2]).applyMatrix4(f.own).applyMatrix4(m.clone().invert())
  return [v.x, v.y, v.z].map((x) => Math.round(x * 1e4) / 1e4)
}

/** Where the gaze's target is in the figure's own space; null when there is none to look at. */
export function gazeTarget(g: GazeLike | null | undefined, f: Frames | null): THREE.Vector3 | null {
  if (!g || !f || !(g.camera || g.object_id)) return null
  const p = f.gaze(g)
  return p ? p.applyMatrix4(f.own.clone().invert()) : null
}

/** The contacts seen in a mirror: the ends swap sides, a contact to one of the figure's own side joints swaps too (a thing stays a thing). */
export function mirrorContacts(contacts: Contacts | null | undefined): Partial<Record<End, Contact>> {
  const out: Partial<Record<End, Contact>> = {}
  const swap = (j: Joint | null | undefined): Joint | null | undefined => (j && /^[rl]_/.test(j) ? ((j[0] === 'r' ? 'l' : 'r') + j.slice(1)) as Joint : j)
  for (const end of ENDS) { const c = contacts?.[end]; if (c) out[(end[0] === 'r' ? 'l' : 'r') + end.slice(1) as End] = { object_id: c.object_id, joint: (c.object_id === SELF ? swap(c.joint) : c.joint) ?? null } }
  return out
}

/** A pose kept with a character: contacts to the figure's own joints stay ("self"), those to a stage's things become plain pins in the
 *  figure's own space (resolved now), and a gaze stays only at the camera. */
export function portable(pins: Pins, contacts: Contacts, gaze: GazeLike | null | undefined, selfId: string, f: Frames | null): { pins: Pins; contacts: Partial<Record<End, Contact>>; gaze: Gaze | null } {
  const outC: Partial<Record<End, Contact>> = {}, outP: Pins = {}
  const resolved = resolvePins(pins, contacts, f)
  for (const end of ENDS) {
    const p = pins[end], c = contacts[end]
    if (!p) continue
    if (c && (c.object_id === SELF || c.object_id === selfId)) { outC[end] = { object_id: SELF, joint: c.joint ?? null }; outP[end] = [...p] }
    else outP[end] = resolved[end] ?? [...p]
  }
  return { pins: outP, contacts: outC, gaze: gaze?.camera ? { camera: true, object_id: null, joint: null } : null }
}

/** The things a figure can be held to or look at: every other object of the document (and itself for a joint), with the joints a figure offers. */
export function contactChoices(doc: Pick<StageDoc, 'objects'>, selfId: string): { object_id: string; name: string; joints: Joint[] }[] {
  const JOINT_CHOICES: Joint[] = ['head', 'spine', 'root', 'r_shoulder', 'l_shoulder', 'r_elbow', 'l_elbow', 'r_hip', 'l_hip', 'r_knee', 'l_knee']
  return doc.objects.filter((o) => o.id !== selfId && o.kind !== 'light' && o.visible !== false).map((o) => ({ object_id: o.id, name: o.name, joints: o.kind === 'mannequin' ? JOINT_CHOICES : [] }))
    .concat([{ object_id: SELF, name: 'its own', joints: JOINT_CHOICES.filter((j) => j !== 'head') }])
}

export type { StageCamera }
