// P13 / ST1 (D81): the Stage suite's state — the project's stages (`stages/<id>.json` on the server), the open document, selection, the
// tool and view, a command-pattern undo stack over the document, and debounced saves that carry the document's revision (409 → reload,
// the change is lost and the toast says so). The three.js engine (engine.ts) renders from this store and reports edits back to it;
// project data never lives in the engine or in component state.
import { create } from 'zustand'
import { api, ApiError, http, sha256Hex, unwrap } from '../../api/client'
import { isDocumentPreview, type Asset, type DocumentPreview, type Job, type StageCamera, type StageDoc, type StageObject, type StageTemplate } from '../../api/types'
import { useSession } from '../../store/session'
import { registerTransport } from '../animate/transport'
import { clipFrames, EMPTY_KEYS, keyedFrames as keyedFramesOf, keyframesOf, sampleDoc, withKey, withoutKey, type CameraKey, type Keyframes, type ObjectKey, type SkeletonKey } from './anim'
import { JOINTS, MANNEQUIN_PRESETS, POSES } from './builders'
import { mirrorJoints, type Chain } from './ik'
import { lensGuess, parseLens } from './lens'
import { figureMentions, prebind as prebindOf } from './figures'
import { matrixOf, transformOf } from './held'
import { chainOf, clearArms, endsOf, mirrorPins, pinPose, poseContact, type End, type Pins } from './motion/contact'
import { docFrames, mirrorContacts, portable, resolvePins, toContact, type Contact, type Contacts, type Gaze } from './motion/contacts'
import { setShellPoints } from './proxy'
import type { Keypoint, WholeBody } from './passes'
import { profilesForMentions, useStory, versionPointsOfShell } from '../story/storyStore'
import { navigate } from '../../frame/router'
import { contextSlot } from '../../store/contexts'

/** CA0: the body of a bound figure's Cast version (its pinned version, else the character's current one); null = the preset's dummy;
 *  undefined = the character is not loaded (the figure keeps what it has). */
function castBody(profileId: string | null | undefined, version: string | null | undefined): StageObject['body'] | undefined {
  if (!profileId) return null
  const p = useStory.getState().profiles.find((x) => x.id === profileId)
  if (!p) return undefined
  return p.versions.find((x) => x.id === (version ?? p.current))?.body ?? null
}
/** AP1b (D141): a bound figure's character's own poses (its Cast version's, pinned else the current) — by name; {} unbound or not loaded. */
export function castPoses(o: Pick<StageObject, 'profile_id' | 'version'> | null | undefined): Record<string, NonNullable<StageObject['pose']>> {
  const p = o?.profile_id ? useStory.getState().profiles.find((x) => x.id === o.profile_id) : undefined
  return (p?.versions.find((x) => x.id === (o?.version ?? p.current))?.poses ?? {}) as Record<string, NonNullable<StageObject['pose']>>
}
/** AP1b: the limb whose own joints an edit turned (the first; null when only the root, spine, neck or head turned). */
function movedChain(before: Record<string, number[]>, after: Record<string, number[]>): Chain | null {
  for (const j of JOINTS) {
    const a = before[j] ?? [0, 0, 0], b = after[j] ?? a
    if (chainOf(j) && a.some((v, k) => Math.abs(v - (b[k] ?? 0)) > 0.05)) return chainOf(j)
  }
  return null
}
/** D110 (PS3): the 3D model of the Cast prop version a mesh is bound to (pinned, else the current); undefined while the profile is not
 *  loaded or the version has no model (the mesh keeps what it shows). */
export function castModel(profileId: string | null | undefined, version: string | null | undefined): string | undefined {
  if (!profileId) return undefined
  const p = useStory.getState().profiles.find((x) => x.id === profileId)
  return p?.versions.find((x) => x.id === (version ?? p.current))?.model_asset_id ?? undefined
}
/** CW4 (03 §4): a bound prop version's height (metres); undefined while the profile is not loaded or the version has none. */
function castHeight(profileId: string | null | undefined, version: string | null | undefined): number | undefined {
  const p = profileId ? useStory.getState().profiles.find((x) => x.id === profileId) : undefined
  return p?.versions.find((x) => x.id === (version ?? p.current))?.height_m ?? undefined
}
/** D110: a bound mesh shows its prop version's model — remade, or another version picked, it follows; CW4: at the prop's height. */
function withModel(o: StageObject): StageObject {
  if (o.kind !== 'mesh' || !o.profile_id) return o
  const m = castModel(o.profile_id, o.version), h = castHeight(o.profile_id, o.version)
  const next = m && m !== o.asset_id ? { ...o, asset_id: m } : o
  return h !== undefined && h !== next.height_m ? { ...next, height_m: h } : next
}
/** A new object of a kind with every field at its default (a figure standing, its Detailed mannequin; a light aimed ahead). */
function newObject(cur: StageDoc, kind: Kind, preset: string | null = null, pos?: number[], assetId: string | null = null): StageObject {
  const scale = kind === 'mannequin' ? (MANNEQUIN_PRESETS[preset ?? 'adult']?.scale ?? 1) : 1
  return { id: newId(kind === 'mannequin' ? 'fig' : kind), kind, name: `${NAMES[kind] ?? kind} ${cur.objects.filter((o) => o.kind === kind).length + 1}`, preset, asset_id: assetId,
    transform: { pos: pos ?? [0, 0, 0], rot: [0, 0, 0], scale: [scale, scale, scale] }, parent: null, parent_joint: null,
    locked: false, visible: true, colour_id: (cur.objects.length % 12) + 1, pose: kind === 'mannequin' ? { preset: 'stand', joints: {}, extra: {}, ground: 0, pins: {}, contacts: {}, gaze: null } : null, billboard: kind === 'plane', profile_id: null, version: null, body: null, detail: kind === 'mannequin' ? newDetail(cur.objects) : null, path: null, shadow_proxy: null,
    light: kind === 'light' ? { ...NEW_LIGHT, target: [...NEW_LIGHT.target] } : null,
    lens_deg: null, plate_asset_id: null, floor_y: null, plate_camera_id: null, level: null, things: [], things_document_id: null, height_m: null, place_set: null }
}
/** CW6: a built set bound to a Cast place shows its version's set (pinned, else the current) — refitted, baked or filled, it follows;
 *  kept as it is while the place is not loaded or its version has no set. */
function withPlaceSet(o: StageObject): StageObject {
  if (o.kind !== 'set' || o.preset !== 'built' || !o.profile_id) return o
  const p = useStory.getState().profiles.find((x) => x.id === o.profile_id)
  const ps = p?.versions.find((x) => x.id === (o.version ?? p.current))?.place_set
  return ps && JSON.stringify(ps) !== JSON.stringify(o.place_set) ? { ...o, place_set: ps } : o
}
/** CS2 (D136 U6): the shell of a bound figure's Cast version (pinned, else the current) — its shadow proxy; undefined while the character
 *  is not loaded or the version has none (the figure keeps what it has). */
function castShell(profileId: string | null | undefined, version: string | null | undefined): string | undefined {
  if (!profileId) return undefined
  const p = useStory.getState().profiles.find((x) => x.id === profileId)
  return p?.versions.find((x) => x.id === (version ?? p.current))?.shell_asset_id ?? undefined
}
/** A figure with its Cast body: a body sets the height, so a figure taking one stands at scale 1 (the Child preset's 0.7 would shrink it);
 *  U18 (proto01_UIcast): and its mannequin, ♀ or ♂, is the character's; CS2: and its shell casts its shadow. */
function withBody(o: StageObject, body: StageObject['body'] | undefined): StageObject {
  const shell = castShell(o.profile_id, o.version)
  const sameBody = body === undefined || JSON.stringify(o.body ?? null) === JSON.stringify(body)
  const next = shell !== undefined && shell !== o.shadow_proxy ? { ...o, shadow_proxy: shell } : o
  if (sameBody) return next
  const scale = body && !o.body ? [1, 1, 1] : o.transform.scale
  return { ...next, body, transform: { ...o.transform, scale }, ...(body?.figure ? { detail: body.figure } : {}) }
}
/** A figure bound to another character (or none): the last one's shell is not its shadow. */
const rebound = (x: StageObject, profileId: string | null, version: string | null): StageObject =>
  ({ ...x, profile_id: profileId, version, ...(x.profile_id !== profileId ? { shadow_proxy: null } : {}) })
/** U18: the mannequin a new figure is — the Detailed ♀ unless the stage's figures are all ♂ (the Simple dummy is retired). */
const newDetail = (objects: StageObject[]): 'male' | 'female' => { const f = objects.filter((o) => o.kind === 'mannequin'); return f.length && f.every((o) => o.detail === 'male') ? 'male' : 'female' }

export interface PoseDef { preset?: string | null; joints: Record<string, number[]> }
// ---- ST3 (16 §3e / §7): the Shot tab ----
export interface ShotRef { asset_id: string; note?: string | null }
export interface ShotState { method: string; prompt_text: string; refs: ShotRef[]; count: number; tier: 'draft' | 'full'; use_as_is: boolean }
export interface RenderedPasses { size: { w: number; h: number }; blobs: Record<string, Blob>; keypoints: number[][][]; legend: Record<string, string> }
/** The document's record of a camera's rendered passes (stages/<id>.json `passes[]`). */
export interface PassesEntry { camera_id: string; revision: number; size: { w: number; h: number }; assets: Record<string, string>; keypoints: unknown[]; legend: Record<string, unknown>; rendered_at?: string }
export const DEFAULT_SHOT: ShotState = { method: 'clay', prompt_text: '', refs: [], count: 1, tier: 'draft', use_as_is: false }
const snap16 = (v: number) => Math.max(16, Math.round(v / 16) * 16)
const snapTo = (v: number, m: number) => Math.max(m, Math.round(v / m) * m)
// ---- ST4 (16 §8): keyframes and the clip ----
export type GuideKind = 'depth' | 'pose'
/** CN4 (19 §3d): how the stage becomes a clip — LTX-2.3's IC-LoRA on a pass sequence (ST4), or Wan2.2 Animate performing the pose pass. */
export type ClipMethod = 'guided' | 'animate'
type ClipCaps = { model_id: string; label: string; health: string; seconds?: number | null; kinds: string[]; fps?: number | null; frame_step?: number | null; size: number[]; size_mult?: number | null; frames_max?: number | null; figures_max?: number | null }
/** A rendered pass sequence recorded under a camera's passes entry (`guides[kind]`). */
export interface GuideEntry { asset_id: string; frames: number; fps: number; size: { w: number; h: number }; range: { start: number; end: number }; revision: number; rendered_at?: string }
/** D111 (PS5b): the plate projected along the camera path (engine.renderProjected). */
export type PlateProjector = (frames: { cam: StageCamera; doc: StageDoc }[], w: number, h: number, plate: TexImageSource, proj: StageCamera, projAspect: number, restoreDoc: StageDoc, onProgress?: (done: number, total: number) => void, coverage?: boolean) => Promise<Blob[]>
export type SequenceRenderer = (frames: { cam: StageCamera; doc: StageDoc }[], w: number, h: number, kind: GuideKind | 'clay' | 'proxy' | 'proxymask' | 'beauty', restoreDoc: StageDoc, onProgress?: (done: number, total: number) => void) => Promise<{ blobs: Blob[]; keypoints: Keypoint[][][]; wholebody?: (WholeBody | null)[][] }>
/** A result of this stage: a shot carries `stage_id` in its params, a clip (ST4) only its job's origin. */
const ofStage = (a: Asset, stageId: string): boolean => (a.params as { stage_id?: string }).stage_id === stageId || (a.origin?.suite === 'stage' && a.origin?.ref === stageId)
const withCameraKey = (d: StageDoc, camId: string, key: CameraKey): StageDoc => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, camera: { ...k.camera, [camId]: withKey(k.camera[camId], key) } } } }
const withObjectKey = (d: StageDoc, id: string, key: ObjectKey): StageDoc => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, objects: { ...k.objects, [id]: withKey(k.objects[id], key) } } } }
/** The full joint map a figure shows: the preset's angles under the figure's own edits (ST2). */
export function effectiveJoints(o: StageObject): Record<string, number[]> {
  const preset = POSES[o.pose?.preset ?? 'stand'] ?? POSES.stand
  const out: Record<string, number[]> = {}
  for (const j of JOINTS) out[j] = [...(o.pose?.joints?.[j] ?? preset.j[j] ?? [0, 0, 0])]
  return out
}

export type Tool = 'select' | 'move' | 'rotate' | 'scale' | 'path'                        // CA1: path — clicks on the floor add to the selected figure's path
export type View = 'free' | 'camera'
export type Kind = StageObject['kind']
export interface Transform { pos: number[]; rot: number[]; scale: number[] }

const newId = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`
/** D110 (PS4): a new light — E23c's strength, white, a slightly soft shadow, aimed a metre above the origin. */
export const NEW_LIGHT = { intensity: 2.3, colour: '#ffffff', softness: 0.3, shadows: true, target: [0, 1, 0] }
const NAMES: Record<string, string> = { mannequin: 'Figure', set: 'Set', prop: 'Prop', plane: 'Image', mesh: 'Mesh', light: 'Light' }
/** D119 (SC2): what a stage template holds — the arrangement, not the cast (figures are bound per shot) nor the cameras. */
export const TEMPLATE_KINDS: ReadonlySet<string> = new Set(['set', 'prop', 'mesh', 'plane', 'light'])

interface StageState {
  stages: StageDoc[]
  current: StageDoc | null
  selected: string | null
  tool: Tool
  snap: boolean
  view: View
  guides: boolean
  pip: boolean                                              // D121 (AW4): the active camera's picture-in-picture in the free view
  undo: StageDoc[]; redo: StageDoc[]
  saving: boolean
  frameRequest: { ids: string[] | null; n: number }         // the viewport frames these (null = everything) when n changes
  selectedJoint: string | null                              // ST2: the joint the rotate gizmo is on
  posing: boolean                                           // D121: pose mode on the selected figure (the pose pill) — its joint pickers in the viewport
  setPosing: (on: boolean) => void
  userPoses: Record<string, PoseDef>                        // ST2: the project's saved poses (stages/poses.json)
  posesRevision: number                                     // V28: the library's revision as read — a save names it (409 → reloaded)
  selectJoint: (j: string | null) => void
  /** A pose edit; AP1b: the pinned hands and feet stay (`moved`: the limb the author turned or dragged, whose pin goes with it; undefined =
   *  read from the joints that changed). */
  setJoints: (id: string, joints: Record<string, number[]>, moved?: Chain | null) => void
  /** A preset (or a saved pose's joints) on a figure; AP1b: on a bound figure a preset its character has its own version of takes that. */
  applyPose: (id: string, preset: string | null, joints?: Record<string, number[]>) => void
  /** AP1b: one of the character's own poses (fitted to its body: as saved, its drop and pins with it). */
  applyCharacterPose: (id: string, name: string) => void
  /** AP1b (D141): pin hands or feet where they are now; unpin some (none named: all). */
  pinEnds: (id: string, ends: readonly End[], to?: Contact | null) => void
  unpinEnds: (id: string, ends?: readonly End[]) => void
  /** AP1b, the rest: a pinned end held to a thing or a joint from now on (null: in the figure's own space again), where it is now. */
  setContact: (id: string, end: End, to: Contact | null) => void
  /** AP1b, the rest: what the figure looks at (null: the pose's own head). */
  setGaze: (id: string, gaze: Gaze | null) => void
  /** AP1b: *Save for ‹character›* — the figure's pose into its character version's own library. */
  saveForCharacter: (id: string, name: string) => Promise<void>
  mirrorPose: (id: string) => void
  resetPose: (id: string) => void
  loadPoses: () => Promise<void>
  savePose: (name: string, id: string) => Promise<void>
  deletePose: (name: string) => Promise<void>
  templates: StageTemplate[]                                // D119 (SC2): the project's stage templates (stages/templates.json) — arrangements saved from the Library's panel
  loadTemplates: () => Promise<void>
  saveTemplate: (name: string) => Promise<void>             // the current stage's set, props, meshes, planes and lights under a name (not the figures, not the cameras)
  applyTemplate: (name: string) => void                     // its objects added to the current stage with new ids (parents inside the template kept)
  deleteTemplate: (name: string) => Promise<void>
  // ST3: the Shot tab — passes rendered by the viewport, uploaded as assets; the StageShot job; its results
  shot: ShotState
  shotPreview: DocumentPreview | null
  shotPreviewError: string | null
  rendering: boolean
  shots: Asset[]                                            // this stage's stage-shot results, newest first
  passRenderer: ((cam: StageCamera, w: number, h: number) => Promise<RenderedPasses>) | null   // the mounted viewport registers it
  setShot: (patch: Partial<ShotState>) => void
  addShotRef: (assetId: string) => void
  removeShotRef: (assetId: string) => void
  refreshShotPreview: () => Promise<void>
  passesEntry: () => PassesEntry | null                     // the active camera's passes, if rendered
  passesStale: () => boolean                                // the document moved on since they were rendered (or a save is pending)
  shotSize: () => [number, number]                          // the recipe size: the tier's height at the project's aspect, snapped to 16
  renderPasses: () => Promise<boolean>
  generateShot: () => Promise<Job[] | null>
  loadShots: () => Promise<void>
  onAssetCreated: (a: Asset) => void
  onAssetDeleted: (id: string) => void
  // ST4: keyframes (the document's `keyframes` and `range`), the frame the viewport shows, the pass sequence and the clip
  frame: number
  playing: boolean
  guideKind: GuideKind
  clipMethod: ClipMethod
  shotStart: string | null                                  // the shot (a stage-shot image) the clip starts from
  rendered: { done: number; total: number } | null         // sequence progress
  sequenceRenderer: SequenceRenderer | null                 // the mounted viewport registers it
  plateProjector: PlateProjector | null                     // D111 (PS5b): registered with the sequence renderer
  keys: () => Keyframes
  keyedFrames: () => number[]
  sampledDoc: () => StageDoc | null                         // the document at `frame` (what the viewport shows)
  setFrame: (f: number) => void
  setPlaying: (on: boolean) => void
  setRange: (start: number, end: number) => void
  keyCamera: () => void
  keyObject: (id: string) => void
  /** CA1: the figure's level — Simple (null) or Detailed (the starter set's male / female mannequin follows its joints). */
  setDetail: (id: string, detail: 'male' | 'female') => void
  /** CA1: turns of the Detailed level's own bones (fingers, wrists, feet …) merged into the figure's pose. */
  setExtra: (id: string, extra: Record<string, number[]>, label?: string) => void
  /** CA1: a library clip's baked keys on a figure — the figure's keys in their frames replaced, the range grown to hold them (one undo step). */
  applyMotion: (id: string, keys: ObjectKey[], label: string) => void
  /** CA1: a point clicked on the floor added to the figure's path; the path cleared. */
  addPathPoint: (id: string, p: [number, number]) => void
  clearPath: (id: string) => void
  removeKeyAt: (frame: number) => void
  /** CS3 (proto01_UIcast 06 §2.10, D136 U19): a skeleton key on a figure, replacing one at its frame — `body` null: the figure's own (its
   *  Cast version's) from there; a body: that one held. */
  setSkeletonKey: (id: string, key: SkeletonKey) => void
  /** CS3: a figure's skeleton keys replaced (one undo step; *Apply from a frame…*). */
  setSkeletonKeys: (id: string, keys: SkeletonKey[], label: string) => void
  /** D121 (AW2): one row's key moved on the timeline (`cam:<id>` / `obj:<id>`; CS3 `skl:<id>`) — the key's values kept, a key already there replaced. */
  moveKey: (row: string, from: number, to: number) => void
  /** D121 (AW2): one row's key removed (its right-click on the timeline). */
  removeRowKey: (row: string, frame: number) => void
  setGuideKind: (k: GuideKind) => void
  setClipMethod: (m: ClipMethod) => void
  /** The chosen method's capabilities (model, size, frame step, frames_max …), or null when this build has none. */
  clipCaps: () => ClipCaps | null
  /** Frames the next sequence covers: the range on the method's frame grid, capped at its window. */
  guideFrames: () => number
  /** D111 (PS5a): wait for the pending save, so a render names the stage's saved revision. */
  flush: () => Promise<void>
  setShotStart: (id: string | null) => void
  guideEntry: () => GuideEntry | null
  guideStale: () => boolean                                 // D121: no sequence, or one from another range, length or revision
  guideSize: () => [number, number]                         // the clip model's grid at the project's aspect
  renderGuide: () => Promise<boolean>
  animateShot: () => Promise<Job[] | null>
  // P18 (D84): the project's mesh assets (GLB props) for the Library
  meshes: Asset[]
  loadMeshes: () => Promise<void>
  uploadMeshThumbnail: (assetId: string, view: Blob) => Promise<void>   // the viewport's fitted view replaces the engine's RenderMesh thumbnail, once
  load: () => Promise<void>
  create: (name: string) => Promise<StageDoc | null>
  open: (id: string | null) => Promise<void>
  rename: (name: string) => Promise<void>
  destroy: () => Promise<void>
  /** Apply a document edit (undoable) and save. */
  apply: (fn: (doc: StageDoc) => StageDoc, label: string) => void
  undoEdit: () => void
  redoEdit: () => void
  select: (id: string | null) => void
  selectedCamera: string | null                             // D119 (SC1): a camera selected as an object (its row's editor, its body's gizmo); it is the active one too
  stageSelected: boolean                                    // D119 (SC1): the stage row selected (the frame, the ambient, rename / delete)
  selectCamera: (id: string | null) => void
  selectStage: () => void
  moveCamera: (id: string, pos: number[]) => void           // D119 (SC1): the camera's body dragged — its target follows by the same move
  setTool: (t: Tool) => void
  setSnap: (on: boolean) => void
  setView: (v: View) => void
  setGuides: (on: boolean) => void
  setPip: (on: boolean) => void
  addObject: (kind: Kind, preset?: string | null, pos?: number[], assetId?: string | null) => string | null
  /** CW7 (02 §9): a Cast place's set on the stage, bound (it follows Cast); selected when it is already there. */
  placePlace: (profileId: string) => string | null
  /** CW7: *Make it a Cast place…* — a picture set's picture becomes a new Cast place's set picture, and its set is built from it. */
  setToPlace: (id: string) => Promise<void>
  setFromImage: (assetId: string) => Promise<void>            // SC3 (D120): a Catalogue image → MoGe's relief as a locked set with the picture's camera (a job; the stage reloads when it lands)
  pendingSet: string | null                                   // SC3: the image → set job in flight for the open stage
  /** SC3b (D120): the picture set rebuilt in place with a corrected lens (MoGe's reading wobbles); the stage reloads when it lands. */
  rebuildImageSet: (setId: string, lensDeg: number) => Promise<void>
  updateObject: (id: string, patch: Partial<StageObject>) => void
  /** D129 (HP1): a prop put in a figure's hand (it moves with the hand; its transform is its place on the hand), or taken out where it stands. */
  hold: (id: string, figureId: string, hand: 'r_hand' | 'l_hand') => void
  letGo: (id: string) => void
  setParent: (id: string, parentId: string | null) => void
  worldOf: ((id: string) => Transform | null) | null                    // D129: the mounted viewport registers it (an object's world transform now)
  /** D110 (PS4): the sky light's strength (null = the default: 0.85 under lights, 1.1 without). */
  setAmbient: (v: number | null) => void
  /** D110 (PS4): a light above and in front of a point (the viewport's centre), aimed at it — a sun from the upper front-left. */
  addLight: (at?: number[]) => string | null
  setTransform: (id: string, t: Transform) => void
  removeObject: (id: string) => void
  duplicateObject: (id: string) => void
  addCamera: () => void
  updateCamera: (id: string, patch: Partial<StageCamera>) => void
  removeCamera: (id: string) => void
  setActiveCamera: (id: string) => void
  frameView: (ids: string[] | null) => void                // frame the selection (or everything) in the viewport
  object: (id: string | null) => StageObject | undefined
  activeCamera: () => StageCamera | undefined
  /** D93 (C8): bind a figure to a Cast character (at a version — a costume; null = the current one), or unbind it (`null`). */
  bindFigure: (id: string, profileId: string | null, version?: string | null) => void
  /** D142: Clay opened for a Cast version — its bench stage (made once, kept); `back` is where *← Back* goes (Cast on the version). */
  openBench: (profileId: string, version?: string | null) => Promise<boolean>
  /** CW5: Clay opened on the line-up of these Cast versions and ideas (made again each time); `back` returns to the board it came from. */
  openLineup: (items: { profile_id?: string; version?: string | null; idea_id?: string }[], back?: () => void) => Promise<boolean>
  /** D142: *← Back* from a bench or the line-up. */
  backFromBench: () => void
  /** CW5: the line-up's things copied into a stage (`null`: a new one, named by the author) and that stage opened. */
  sendLineup: (target: string | null) => Promise<void>
  /** CW5: every figure on the stage takes a preset at once (the line-up's *Pose all ▸*). */
  poseAll: (preset: string) => void
  /** CW3 (02 §9): a Cast character's figure at a point — its figure selected when it is already here (one per character). */
  placeCharacter: (profileId: string, pos?: number[]) => void
  /** CW3 (06 §2.7): a bound figure or mesh copied beside it, free — its body and shell, or its model and height, as they are now. */
  freeCopy: (id: string) => void
  /** CW3 (06 §2.7): *Prototype ▸* on a free figure or mesh — a new idea in Cast, Clay's view of it as its picture, the object as its clay. */
  prototypeObject: (id: string) => Promise<void>
  /** CW4: a free mesh's height (metres; null: the model's own size). */
  setHeight: (id: string, h: number | null) => void
  /** D110 (PS3): a Cast prop's 3D model placed in the scene, bound to the prop (its version's model follows); null when it has no model yet. */
  placeProp: (profileId: string, pos?: number[]) => string | null
  /** D110: a mesh bound to a Cast prop and a pinned version (null = the current one), or unbound (it keeps the model it shows). */
  bindProp: (id: string, profileId: string | null, version?: string | null) => void
  /** D93 (C8): the figure mentions the Render tab sends — the visible bound figures at the active camera, left to right. */
  figureMentions: () => { profile_id: string; figure: string; version?: string }[]
  /** D93 (C8, UI4's Make frame ▸ in Stage): bind the speakers to the figures in screen order when the counts match — the number bound, or
   *  null when the counts differ (the author binds them). */
  /** D93 (C8): bind the speakers to the figures left to right; D93 follow-up: a newly bound figure wears the node's pin (`version`). */
  prebindSpeakers: (speakers: { id: string; version?: string | null }[]) => number | null
  /** CA0: bound figures take their Cast version's body (on open, and whenever the profiles change). */
  /** CA0: the bound figures take their Cast bodies; D110: the bound meshes their props' models. */
  syncBodies: () => void
}

let saveTimer: number | null = null
let benchBack: (() => void) | null = null                                     // D142: where *← Back* from a bench or the line-up goes (this session)
let saveChain: Promise<void> = Promise.resolve()                              // V79: one PUT at a time — the next starts from the revision the last reply gave

/** The document's save, one after another: a save that starts while another is in flight waits for its reply and its revision, so the
 *  author's own edits never answer 409 to each other (the old sequence guard dropped the first reply's revision instead). */
function save(get: () => StageState, set: (p: Partial<StageState>) => void): Promise<void> {
  const run = saveChain.then(() => saveNow(get, set))
  saveChain = run.catch(() => undefined)
  return run
}

async function saveNow(get: () => StageState, set: (p: Partial<StageState>) => void): Promise<void> {
  const cur = get().current
  if (!cur) return
  set({ saving: true })
  try {
    const next = await unwrap(http.PUT('/stages/{st_id}', { params: { path: { st_id: cur.id } }, body: cur as never }))
    if (get().current?.id === cur.id) {
      set({ current: { ...get().current!, revision: next.revision, updated_at: next.updated_at }, stages: get().stages.map((s) => (s.id === next.id ? next : s)) })
    }
  } catch (e) {
    const err = e as ApiError
    if (err.status === 409) {
      useSession.getState().toast('The stage changed elsewhere — reloaded; your last change was not saved', 'error')
      await get().open(cur.id)
    } else useSession.getState().toast(`Stage not saved: ${err.detail ?? e}`, 'error')
  } finally { set({ saving: false }) }
}

/** A pose edit (joints, a preset, the Detailed level's own bones): on a keyed figure it is a key at the playhead — the figure as sampled
 *  there, its pose changed — as a transform edit is (ST4); otherwise the figure's pose itself. Before CA1 a pose edit on a keyed figure
 *  changed only the unkeyed pose, which the keys hide: a preset or a hand after a library clip did nothing. */
/** AP1b, the rest: a pose edit that leaves the contacts and the gaze as they are. */
const rest = (p: StageObject['pose']) => ({ contacts: p?.contacts ?? {}, gaze: p?.gaze ?? null })
function editPose(get: () => StageState, id: string, fn: (p: StageObject['pose']) => NonNullable<StageObject['pose']>, label: string): void {
  const cur = get().current
  if (!cur) return
  if (keyframesOf(cur).objects[id]?.length) {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id)
    if (!o) return
    const pose = fn(o.pose)
    get().apply((d) => withObjectKey(d, id, { frame: get().frame, ease: 'ease', transform: { pos: [...o.transform.pos], rot: [...o.transform.rot], scale: [...o.transform.scale] }, pose }), label)
    return
  }
  get().apply((d) => ({ ...d, objects: d.objects.map((x) => (x.id === id ? { ...x, pose: fn(x.pose) } : x)) }), label)
}

/** V84: a render's reply (the passes, the album page, the revision) onto the document as it is *now* — an edit made during the render
 *  stays, and is saved on the new revision; before, the reply replaced the document wholesale and the edit was dropped silently. */
export function takeRendered(next: StageDoc, rendered: StageDoc, get: () => StageState, set: (p: Partial<StageState>) => void): void {
  const cur = get().current
  const edited = !!cur && cur.id === next.id && cur !== rendered
  const doc = edited ? { ...cur!, passes: next.passes, group_id: next.group_id, revision: next.revision, updated_at: next.updated_at } : next
  set({ current: doc, stages: get().stages.map((x) => (x.id === next.id ? next : x)) })
  if (edited) schedule(get, set)
}

function schedule(get: () => StageState, set: (p: Partial<StageState>) => void): void {
  if (saveTimer) window.clearTimeout(saveTimer)
  saveTimer = window.setTimeout(() => { saveTimer = null; void save(get, set) }, 300)
}

/** ST3: a pending or in-flight save completes before the passes are rendered, so they carry the document's real revision. */
async function flushSave(get: () => StageState, set: (p: Partial<StageState>) => void): Promise<void> {
  if (saveTimer) { window.clearTimeout(saveTimer); saveTimer = null; await save(get, set) }
  for (let i = 0; i < 100 && get().saving; i++) await new Promise((r) => window.setTimeout(r, 50))
}

let shotPreviewSeq = 0
const thumbed = new Set<string>()                                            // P18: mesh assets whose thumbnail this session already rendered

/** V28: the pose library saved with the revision it was read at; 409 (another window saved meanwhile) reloads it and says so, and the
 *  caller's change is not applied over it (the author makes it again on the library as it is now). */
async function putPoses(poses: Record<string, PoseDef>, set: (p: Partial<StageState>) => void, get: () => StageState): Promise<void> {
  try {
    const lib = await unwrap(http.PUT('/stages/poses', { body: { revision: get().posesRevision, poses: poses as never } }))
    set({ userPoses: lib.poses as unknown as Record<string, PoseDef>, posesRevision: lib.revision })
  } catch (e) {
    if ((e as ApiError).status !== 409) throw e
    await get().loadPoses()
    throw new ApiError(409, 'the poses changed meanwhile (another window saved) — reloaded; make the change again')
  }
}

export const useStage = create<StageState>()((set, get) => ({
  stages: [], current: null, selected: null, selectedCamera: null, stageSelected: false, posing: false, tool: 'select', snap: false, view: 'free', guides: true, pip: true, undo: [], redo: [], saving: false,
  frameRequest: { ids: null, n: 0 }, selectedJoint: null, userPoses: {}, posesRevision: 0, templates: [], pendingSet: null,
  shot: DEFAULT_SHOT, shotPreview: null, shotPreviewError: null, rendering: false, shots: [], passRenderer: null, worldOf: null,
  frame: 0, playing: false, guideKind: 'depth', clipMethod: 'guided', shotStart: null, rendered: null, sequenceRenderer: null, plateProjector: null,
  meshes: [],

  // ---- P18: mesh props ----
  loadMeshes: async () => {
    try { const r = await unwrap(http.GET('/assets', { params: { query: { kind: 'mesh', sort: 'created_desc', limit: 60 } } })); set({ meshes: r.items as Asset[] }) }
    catch { set({ meshes: [] }) }
  },
  uploadMeshThumbnail: async (assetId, view) => {
    const a = get().meshes.find((m) => m.id === assetId)
    if (!a || (a.params as { thumb_source?: string }).thumb_source === 'client' || thumbed.has(assetId)) return
    thumbed.add(assetId)
    try {
      const rec = (await api.putThumbnail(assetId, view)) as Asset
      set({ meshes: get().meshes.map((m) => (m.id === assetId ? rec : m)) })
    } catch { thumbed.delete(assetId) }
  },

  // ---- ST4: keyframes and the clip ----
  keys: () => { const cur = get().current; return cur ? keyframesOf(cur) : EMPTY_KEYS },
  keyedFrames: () => { const cur = get().current; return cur ? keyedFramesOf(keyframesOf(cur), cur.active_camera) : [] },
  sampledDoc: () => { const cur = get().current; return cur ? sampleDoc(cur, get().frame) : null },
  setFrame: (f) => set({ frame: Math.max(0, Math.min(100000, Math.round(f))) }),
  setPlaying: (playing) => set({ playing }),
  setRange: (start, end) => { const s = Math.max(0, Math.round(start)); const e = Math.max(s + 1, Math.round(end)); get().apply((d) => ({ ...d, range: { start: s, end: e } }), 'range') },
  keyCamera: () => {
    const sd = get().sampledDoc(); const cam = sd?.cameras.find((c) => c.id === sd.active_camera)
    if (!sd || !cam) return
    get().apply((d) => withCameraKey(d, cam.id, { frame: get().frame, ease: 'ease', pos: [...cam.pos], target: [...cam.target], focal_mm: cam.focal_mm }), 'key camera')
  },
  keyObject: (id) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id)
    if (!o) return
    get().apply((d) => withObjectKey(d, id, { frame: get().frame, ease: 'ease', transform: { pos: [...o.transform.pos], rot: [...o.transform.rot], scale: [...o.transform.scale] }, pose: o.pose ? { preset: o.pose.preset, joints: { ...o.pose.joints }, extra: { ...(o.pose.extra ?? {}) }, ground: o.pose.ground ?? 0, pins: { ...(o.pose.pins ?? {}) } } : null }), 'key object')
  },
  addPathPoint: (id, p) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, path: [...(o.path ?? []), [Math.round(p[0] * 1000) / 1000, Math.round(p[1] * 1000) / 1000]] } : o)) }), 'path point'),
  clearPath: (id) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, path: null, shadow_proxy: null } : o)) }), 'clear path'),
  setDetail: (id, detail) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id && o.kind === 'mannequin' ? { ...o, detail } : o)) }), detail === 'male' ? 'figure ♂' : 'figure ♀'),
  setExtra: (id, extra, label = 'hand') => editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: p?.joints ?? {}, extra: { ...(p?.extra ?? {}), ...extra }, ground: p?.ground ?? 0, pins: p?.pins ?? {}, ...rest(p) }), label),
  applyMotion: (id, keys, label) => {
    if (!keys.length) return
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)                      // AP1b, the rest: the contacts and the gaze ride the clip
    const contacts = o?.pose?.contacts ?? {}, gaze = o?.pose?.gaze ?? null
    if (Object.keys(contacts).length || gaze) {
      const pins = Object.fromEntries(Object.entries(o?.pose?.pins ?? {}).filter(([k]) => k in contacts))
      keys = keys.map((k) => (k.pose ? { ...k, pose: { ...k.pose, pins: { ...pins }, contacts: { ...contacts }, gaze } } : k))
    }
    const first = keys[0].frame, last = keys[keys.length - 1].frame
    get().apply((d) => {
      const k = keyframesOf(d)
      const kept = (k.objects[id] ?? []).filter((x) => x.frame < first || x.frame > last)
      return { ...d, keyframes: { ...k, objects: { ...k.objects, [id]: [...kept, ...keys].sort((a, b) => a.frame - b.frame) } }, range: { ...d.range, end: Math.max(d.range.end, last) } }
    }, label)
  },
  removeKeyAt: (frame) => get().apply((d) => {
    const k = keyframesOf(d)
    const camera = Object.fromEntries(Object.entries(k.camera).map(([id, ks]) => [id, d.active_camera === id ? withoutKey(ks, frame) : ks]).filter(([, ks]) => (ks as CameraKey[]).length))
    const objects = Object.fromEntries(Object.entries(k.objects).map(([id, ks]) => [id, withoutKey(ks, frame)]).filter(([, ks]) => (ks as ObjectKey[]).length))
    const skeleton = Object.fromEntries(Object.entries(k.skeleton ?? {}).map(([id, ks]) => [id, withoutKey(ks, frame)]).filter(([, ks]) => (ks as SkeletonKey[]).length))   // CS3
    return { ...d, keyframes: { camera, objects, skeleton } }
  }, 'remove keys'),
  setSkeletonKey: (id, key) => get().apply((d) => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, skeleton: { ...(k.skeleton ?? {}), [id]: withKey(k.skeleton?.[id], key) } } } }, 'skeleton key'),
  setSkeletonKeys: (id, keys, label) => get().apply((d) => { const k = keyframesOf(d); return { ...d, keyframes: { ...k, skeleton: { ...(k.skeleton ?? {}), [id]: [...keys].sort((a, b) => a.frame - b.frame) } } } }, label),
  moveKey: (row, from, to) => {
    const at = row.indexOf(':'), kind = row.slice(0, at), id = row.slice(at + 1)
    if (from === to || to < 0 || (kind !== 'cam' && kind !== 'obj' && kind !== 'skl')) return
    get().apply((d) => {
      const k = keyframesOf(d)
      if (kind === 'skl') { const ks = k.skeleton?.[id] ?? []; const key = ks.find((x) => x.frame === from); return key ? { ...d, keyframes: { ...k, skeleton: { ...k.skeleton, [id]: withKey(withoutKey(ks, from), { ...key, frame: to }) } } } : d }
      if (kind === 'cam') { const ks = k.camera[id] ?? []; const key = ks.find((x) => x.frame === from); return key ? { ...d, keyframes: { ...k, camera: { ...k.camera, [id]: withKey(withoutKey(ks, from), { ...key, frame: to }) } } } : d }
      const ks = k.objects[id] ?? []; const key = ks.find((x) => x.frame === from)
      return key ? { ...d, keyframes: { ...k, objects: { ...k.objects, [id]: withKey(withoutKey(ks, from), { ...key, frame: to }) } } } : d
    }, 'move key')
  },
  removeRowKey: (row, frame) => {
    const at = row.indexOf(':'), kind = row.slice(0, at), id = row.slice(at + 1)
    get().apply((d) => {
      const k = keyframesOf(d)
      const drop = <T extends { frame: number }>(rec: Record<string, T[]>) => { const ks = withoutKey(rec[id], frame); const out = { ...rec }; if (ks.length) out[id] = ks; else delete out[id]; return out }
      return kind === 'cam' ? { ...d, keyframes: { ...k, camera: drop(k.camera) } } : kind === 'obj' ? { ...d, keyframes: { ...k, objects: drop(k.objects) } }
        : kind === 'skl' ? { ...d, keyframes: { ...k, skeleton: drop(k.skeleton ?? {}) } } : d
    }, 'remove key')
  },
  setGuideKind: (guideKind) => set({ guideKind: get().clipMethod === 'animate' ? 'pose' : guideKind }),
  setClipMethod: (clipMethod) => set({ clipMethod, guideKind: clipMethod === 'animate' ? 'pose' : get().guideKind }),     // Animate performs the pose pass
  clipCaps: () => { const st = useSession.getState().capabilities?.stage; return ((get().clipMethod === 'animate' ? st?.animate : st?.clip) ?? null) as ClipCaps | null },
  flush: () => flushSave(get, set),
  guideFrames: () => {
    const cur = get().current, c = get().clipCaps()
    if (!cur) return 0
    const step = c?.frame_step ?? 8
    const n = clipFrames(cur.range.start, cur.range.end, step)
    const max = (c as { frames_max?: number | null } | null)?.frames_max
    return max ? Math.min(n, Math.floor((max - 1) / step) * step + 1) : n                     // Animate: one window (E19: 77 frames)
  },
  setShotStart: (shotStart) => set({ shotStart }),
  guideEntry: () => { const e = get().passesEntry() as (PassesEntry & { guides?: Record<string, GuideEntry> }) | null; return e?.guides?.[get().guideKind] ?? null },
  guideStale: () => { const g = get().guideEntry(); const cur = get().current; return !g || !cur || g.range.start !== cur.range.start || g.frames !== get().guideFrames() || cur.revision > g.revision + 1 },
  guideSize: () => {
    const cur = get().current
    const aspect = cur ? cur.size.w / Math.max(1, cur.size.h) : 16 / 9
    const base = get().clipCaps()?.size
    const h = base && base.length === 2 ? base[1] : 576
    const m = get().clipCaps()?.size_mult ?? 64                     // CA3: the guided clip's grid (LTX's IC-LoRA: 64 — its latent is halved)
    return get().clipMethod === 'animate' ? [snap16(h * aspect), snap16(h)] : [snapTo(h * aspect, m), snapTo(h, m)]   // Wan's grid is 16
  },
  renderGuide: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera()
    if (!cur || !cam) { s.toast('No camera to render the sequence from', 'error'); return false }
    if (!get().sequenceRenderer) (await import('./headless')).ensureHeadless()   // D95 (AN1): no viewport on screen — the headless engine
    const render = get().sequenceRenderer
    if (!render) { s.toast('The stage is not ready to render', 'error'); return false }
    set({ rendering: true, rendered: { done: 0, total: 0 } })
    try {
      await flushSave(get, set)
      const doc = get().current
      if (!doc) return false
      const kind = get().guideKind
      const { start } = doc.range
      const n = get().guideFrames()
      const frames = Array.from({ length: n }, (_, i) => { const d = sampleDoc(doc, start + i); return { cam: d.cameras.find((c) => c.id === cam.id) ?? cam, doc: d } })
      const [w, h] = get().guideSize()
      const out = await render(frames, w, h, kind, sampleDoc(doc, get().frame), (done, total) => set({ rendered: { done, total } }))
      const shas: string[] = []
      for (const blob of out.blobs) {
        const sha = await sha256Hex(await blob.arrayBuffer())
        await api.putBlob(sha, blob)
        shas.push(sha)
      }
      const next = await unwrap(http.POST('/stages/{st_id}/guide', { params: { path: { st_id: doc.id } },
        body: { camera_id: cam.id, revision: doc.revision, kind, fps: doc.size.fps, size: { w, h }, range: { start, end: start + n - 1 }, frames: shas, keypoints: out.keypoints as never } }))
      takeRendered(next, doc, get, set)                                                   // V84: an edit made during the render stays
      s.toast(`${kind === 'depth' ? 'Depth' : 'Pose'} sequence rendered: ${n} frames at ${w}×${h}, ${doc.size.fps} fps`, 'success')
      return true
    } catch (e) { s.toast(`Render sequence failed: ${(e as ApiError).detail ?? e}`, 'error'); return false } finally { set({ rendering: false, rendered: null }) }
  },
  animateShot: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera(), g = get().guideEntry(), start = get().shotStart
    const method = get().clipMethod
    const model = get().clipCaps()?.model_id
    if (!cur || !cam || !g || !start || !model) { s.toast(!g ? 'Render the sequence first' : !start ? (method === 'animate' ? 'Pick the character to perform it (click one of the results)' : 'Pick a frame to start from (click one of the results)') : 'No clip model in this build', 'error'); return null }
    const recipe = { kind: 'i2v', model_id: model, start_asset: start, prompt_text: get().shot.prompt_text.trim(), frames: g.frames, fps: g.fps, width: g.size.w, height: g.size.h,
      preset: 'draft', guide: { asset_id: g.asset_id, kind: get().guideKind, strength: 1.0 }, seeds: [0] }
    try {
      const jobs = await unwrap(http.POST('/jobs', { body: { recipe: recipe as never, stage: false, origin: { suite: 'stage', surface: 'clip', ref: cur.id, payload: { camera_id: cam.id } } } }))
      s.toast(method === 'animate' ? `Queued ${cam.name} performed by the picked character: ${g.frames} frames (Animate)` : `Queued the clip of ${cam.name}: ${g.frames} frames on the ${get().guideKind} sequence`, 'success')
      return jobs.jobs
    } catch (e) { s.toast(`Render clip failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },

  // ---- ST3: the Shot tab ----
  setShot: (patch) => { set({ shot: { ...get().shot, ...patch } }); void get().refreshShotPreview() },
  addShotRef: (assetId) => { const refs = get().shot.refs; if (refs.some((r) => r.asset_id === assetId)) return; get().setShot({ refs: [...refs, { asset_id: assetId, note: null }] }) },
  removeShotRef: (assetId) => get().setShot({ refs: get().shot.refs.filter((r) => r.asset_id !== assetId) }),
  passesEntry: () => { const cur = get().current; const cam = get().activeCamera(); if (!cur || !cam) return null; return ((cur.passes as unknown as PassesEntry[]).find((p) => p.camera_id === cam.id)) ?? null },
  passesStale: () => { const e = get().passesEntry(); const cur = get().current; if (!e || !cur) return true; return cur.revision > e.revision + 1 || saveTimer !== null || get().saving },
  shotSize: () => {
    const cur = get().current
    const aspect = cur ? cur.size.w / Math.max(1, cur.size.h) : 16 / 9
    const h = get().shot.tier === 'full' ? (cur?.size.h ?? 1080) : 720
    return [snap16(h * aspect), snap16(h)]
  },
  refreshShotPreview: async () => {
    const cur = get().current, cam = get().activeCamera()
    if (!cur || !cam) { set({ shotPreview: null, shotPreviewError: null }); return }
    const seq = ++shotPreviewSeq
    const sh = get().shot
    const entry = get().passesEntry()
    const [width, height] = get().shotSize()
    const recipe = { kind: 'stage_shot', stage_id: cur.id, camera_id: cam.id, passes: entry?.assets ?? { clay: 'pending', pose: 'pending' }, method: sh.method,
      prompt_text: sh.prompt_text.trim(), refs: sh.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })), mentions: get().figureMentions(), seeds: [0], width, height }   // D93 (C8): the bound figures
    try {
      const pv = await unwrap(http.POST('/recipes/preview', { body: { recipe: recipe as never } }))
      if (seq === shotPreviewSeq) set({ shotPreview: isDocumentPreview(pv) ? pv : null, shotPreviewError: null })
    } catch (e) {
      if (seq === shotPreviewSeq) set({ shotPreview: null, shotPreviewError: (e as ApiError).detail ?? String(e) })
    }
  },
  renderPasses: async () => {
    const s = useSession.getState()
    const cur = get().current, base = get().activeCamera()
    if (!cur || !base) { s.toast('No camera to render the passes from', 'error'); return false }
    if (!get().passRenderer) (await import('./headless')).ensureHeadless()       // D95 (AN1): Image's From a stage — no viewport on screen
    const render = get().passRenderer
    if (!render) { s.toast('The stage is not ready to render', 'error'); return false }
    set({ rendering: true })
    try {
      await flushSave(get, set)
      const doc = get().current
      if (!doc) return false
      const cam = sampleDoc(doc, get().frame).cameras.find((c) => c.id === base.id) ?? base   // V80 (T8): the camera as the viewport shows it at the playhead, its keys applied
      const [w, h] = get().shotSize()
      const out = await render(cam, w, h)
      const passes: Record<string, string> = {}
      for (const [name, blob] of Object.entries(out.blobs)) {
        const sha = await sha256Hex(await blob.arrayBuffer())
        await api.putBlob(sha, blob)
        passes[name] = sha
      }
      const next = await unwrap(http.POST('/stages/{st_id}/passes', { params: { path: { st_id: doc.id } },
        body: { camera_id: cam.id, revision: doc.revision, size: out.size, passes, keypoints: out.keypoints as never, legend: out.legend as never } }))
      takeRendered(next, doc, get, set)                                                   // V84: an edit made during the render stays
      s.toast(`Passes rendered for ${cam.name} at ${w}×${h}`, 'success')
      void get().refreshShotPreview()
      return true
    } catch (e) { s.toast(`Render passes failed: ${(e as ApiError).detail ?? e}`, 'error'); return false } finally { set({ rendering: false }) }
  },
  generateShot: async () => {
    const s = useSession.getState()
    const cur = get().current, cam = get().activeCamera()
    if (!cur || !cam) return null
    let entry = get().passesEntry()
    if (!entry || (get().passesStale() && !get().shot.use_as_is)) {
      if (!(await get().renderPasses())) return null
      entry = get().passesEntry()
    }
    if (!entry) return null
    const sh = get().shot
    const [width, height] = get().shotSize()
    const recipe = { kind: 'stage_shot', stage_id: cur.id, camera_id: cam.id, passes: entry.assets, method: sh.method, prompt_text: sh.prompt_text.trim(),
      refs: sh.refs.map((r) => ({ asset_id: r.asset_id, note: r.note ?? null })), mentions: get().figureMentions(), seeds: Array.from({ length: Math.max(1, Math.min(4, sh.count)) }, () => 0), width, height }   // D93 (C8)
    try {
      const jobs = await unwrap(http.POST('/jobs', { body: { recipe: recipe as never, stage: false, origin: { suite: 'stage', surface: 'shot', ref: cur.id, payload: { camera_id: cam.id } } } }))
      s.toast(`Queued ${jobs.jobs.length} frame${jobs.jobs.length > 1 ? 's' : ''} of ${cam.name}`, 'success')
      return jobs.jobs
    } catch (e) { s.toast(`Render frame failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  loadShots: async () => {
    const cur = get().current
    if (!cur) { set({ shots: [] }); return }
    try {
      const r = await unwrap(http.GET('/assets', { params: { query: { suite: 'stage', sort: 'created_desc', limit: 60 } } }))
      set({ shots: (r.items as Asset[]).filter((a) => a.lineage_kind === 'stage-shot' && ofStage(a, cur.id)) })
    } catch { set({ shots: [] }) }
  },
  onAssetCreated: (a) => {
    if (a.kind === 'mesh' && !get().meshes.some((x) => x.id === a.id)) set({ meshes: [a, ...get().meshes] })       // P18: a new prop joins the Library
    const cur = get().current
    if (!cur || a.lineage_kind !== 'stage-shot' || !ofStage(a, cur.id) || get().shots.some((x) => x.id === a.id)) return
    set({ shots: [a, ...get().shots] })
  },
  onAssetDeleted: (id) => {                                                                                    // proto01_UIcast CB2: a trashed mesh or shot leaves the lists
    if (get().meshes.some((x) => x.id === id)) set({ meshes: get().meshes.filter((x) => x.id !== id) })
    if (get().shots.some((x) => x.id === id)) set({ shots: get().shots.filter((x) => x.id !== id) })
  },

  selectJoint: (j) => set(j ? { selectedJoint: j, posing: true } : { selectedJoint: null }),   // D121: a joint picked by name enters pose mode
  setPosing: (on) => set(on && get().object(get().selected)?.kind === 'mannequin' ? { posing: true } : { posing: false, selectedJoint: null }),
  setJoints: (id, joints, moved) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    if (!o || JSON.stringify(effectiveJoints(o)) === JSON.stringify(joints)) return        // a gizmo click without a turn commits nothing (no undo entry)
    // AP1b (D141): the pinned limbs bent back onto their pins; the one the author worked takes its pin along
    const pins = (o.pose?.pins ?? {}) as Pins, contacts = (o.pose?.contacts ?? {}) as Contacts
    const frames = Object.keys(contacts).length ? docFrames(get().sampledDoc() ?? get().current!, id) : null
    const which = moved === undefined ? movedChain(effectiveJoints(o), joints) : moved
    const held = Object.keys(pins).length ? pinPose(o.pose?.preset ?? 'stand', joints, o.pose?.ground ?? 0, resolvePins(pins, contacts, frames), o.body as never, which) : { joints, pins }
    for (const end of Object.keys(contacts) as End[]) {                       // a contact pin stays written in its frame: the worked limb's where its end now is, the rest as stored
      const c = contacts[end]
      if (!held.pins[end] || !c) continue
      held.pins[end] = (frames && toContact(held.pins[end]!, c, frames)) ?? pins[end] ?? held.pins[end]
    }
    editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: held.joints, extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: held.pins, ...rest(p) }), 'pose')
  },
  applyPose: (id, preset, joints = {}) => {
    const name = preset ?? 'stand'
    if (!Object.keys(joints).length && castPoses(get().object(id))[name]) { get().applyCharacterPose(id, name); return }   // AP1b: the character's own
    // on a keyed figure the preset is keyed as every joint spelled out, so the keys around it interpolate into it (not a snap at halfway)
    const keyed = !!keyframesOf(get().current ?? { keyframes: {} } as never).objects[id]?.length
    const full = keyed ? { ...Object.fromEntries(JOINTS.map((j) => [j, [...(POSES[name]?.j[j] ?? [0, 0, 0])]])), ...joints } : joints
    // AP1 (D141): a pose on the ground stands on its feet on this figure's body — its lower foot on the floor, the other bent up where it
    // would go under (a run is in the air: as it is)
    const o = get().object(id)
    const on = name !== 'run' && o?.kind === 'mannequin' ? poseContact(name, full, o.body as never) : { ground: 0, joints: full }
    const joints2 = o?.kind === 'mannequin' && o.body ? clearArms(name, on.joints, on.ground, o.body as never) : on.joints   // AP1b, the rest: the arms clear of a broad torso
    editPose(get, id, (p) => ({ preset: name, joints: joints2, extra: p?.extra ?? {}, ground: on.ground, pins: {}, contacts: {}, gaze: p?.gaze ?? null }), 'pose preset'); set({ selectedJoint: null })
  },
  applyCharacterPose: (id, name) => {
    const own = castPoses(get().object(id))[name]
    if (!own) return
    const keyed = !!keyframesOf(get().current ?? { keyframes: {} } as never).objects[id]?.length
    const preset = own.preset ?? 'stand'
    const joints = keyed ? { ...Object.fromEntries(JOINTS.map((j) => [j, [...(POSES[preset]?.j[j] ?? [0, 0, 0])]])), ...own.joints } : { ...own.joints }
    editPose(get, id, (p) => ({ preset, joints, extra: { ...(p?.extra ?? {}), ...(own.extra ?? {}) }, ground: own.ground ?? 0, pins: { ...(own.pins ?? {}) }, contacts: { ...(own.contacts ?? {}) }, gaze: own.gaze ?? p?.gaze ?? null }), 'pose'); set({ selectedJoint: null })
  },
  pinEnds: (id, ends, to = null) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    if (o?.kind !== 'mannequin') return
    const at = endsOf(o.pose?.preset ?? 'stand', effectiveJoints(o), o.pose?.ground ?? 0, o.body as never)
    const frames = to ? docFrames(get().sampledDoc() ?? get().current!, id) : null
    const point = (e: End) => (to && frames ? toContact(at[e], to, frames) : null) ?? at[e]
    editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: p?.joints ?? {}, extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: { ...(p?.pins ?? {}), ...Object.fromEntries(ends.map((e) => [e, point(e)])) },
      contacts: { ...Object.fromEntries(Object.entries(p?.contacts ?? {}).filter(([k]) => !ends.includes(k as End))), ...(to && frames ? Object.fromEntries(ends.map((e) => [e, to])) : {}) }, gaze: p?.gaze ?? null }),
      ends.length > 1 ? 'pin' : `pin ${ends[0]?.replace('_', ' ')}`)
  },
  setContact: (id, end, to) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    if (o?.kind !== 'mannequin' || !o.pose?.pins?.[end]) return
    const frames = docFrames(get().sampledDoc() ?? get().current!, id)
    const own = resolvePins(o.pose.pins as Pins, o.pose.contacts as Contacts, frames)[end]!                     // where the end is held now, in the figure's own space
    const point = (to && frames ? toContact(own, to, frames) : null) ?? own
    editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: p?.joints ?? {}, extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: { ...(p?.pins ?? {}), [end]: point },
      contacts: { ...Object.fromEntries(Object.entries(p?.contacts ?? {}).filter(([k]) => k !== end)), ...(to && frames ? { [end]: to } : {}) }, gaze: p?.gaze ?? null }), to ? 'hold to' : 'release')
  },
  setGaze: (id, gaze) => editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: p?.joints ?? {}, extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: p?.pins ?? {}, contacts: p?.contacts ?? {}, gaze }), gaze ? 'look at' : 'look away'),
  unpinEnds: (id, ends) => editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: p?.joints ?? {}, extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: ends ? Object.fromEntries(Object.entries(p?.pins ?? {}).filter(([k]) => !ends.includes(k as End))) : {},
    contacts: ends ? Object.fromEntries(Object.entries(p?.contacts ?? {}).filter(([k]) => !ends.includes(k as End))) : {}, gaze: p?.gaze ?? null }), 'unpin'),
  saveForCharacter: async (id, name) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    const p = o?.profile_id ? useStory.getState().profiles.find((x) => x.id === o.profile_id) : undefined
    if (!o || !p || !name.trim()) return
    const port = portable((o.pose?.pins ?? {}) as Pins, (o.pose?.contacts ?? {}) as Contacts, o.pose?.gaze as Gaze | null, o.id, docFrames(get().sampledDoc() ?? get().current!, o.id))
    const pose = { preset: o.pose?.preset ?? 'stand', joints: effectiveJoints(o), extra: { ...(o.pose?.extra ?? {}) }, ground: o.pose?.ground ?? 0, ...port }
    if (await useStory.getState().saveCharacterPose(p.id, o.version ?? p.current, name.trim(), pose)) useSession.getState().toast(`"${name.trim()}" saved for ${p.name}${POSES[name.trim()] ? ` — the ${name.trim()} preset takes it on ${p.name}'s figures` : ''}`, 'success')
  },
  // AP1b: the pins mirrored with the joints (not re-solved: the mirrored ends are where the mirrored pins are)
  mirrorPose: (id) => editPose(get, id, (p) => ({ preset: p?.preset ?? 'stand', joints: mirrorJoints(effectiveJoints({ pose: p } as StageObject)), extra: p?.extra ?? {}, ground: p?.ground ?? 0, pins: mirrorPins(p?.pins as Pins), contacts: mirrorContacts(p?.contacts as Contacts), gaze: p?.gaze ?? null }), 'mirror pose'),
  resetPose: (id) => get().applyPose(id, 'stand', {}),
  loadPoses: async () => {
    try { const lib = await unwrap(http.GET('/stages/poses')); set({ userPoses: lib.poses as unknown as Record<string, PoseDef>, posesRevision: lib.revision }) }
    catch { set({ userPoses: {}, posesRevision: 0 }) }
  },
  loadTemplates: async () => { try { set({ templates: (await unwrap(http.GET('/project/stage-templates'))).templates }) } catch { set({ templates: [] }) } },
  saveTemplate: async (name) => {
    const cur = get().current
    if (!cur) return
    const objects = cur.objects.filter((o) => TEMPLATE_KINDS.has(o.kind)).map((o) => ({ ...o, parent: o.parent && cur.objects.some((x) => x.id === o.parent && TEMPLATE_KINDS.has(x.kind)) ? o.parent : null }))
    if (!objects.length) { useSession.getState().toast('Nothing to save: a template holds the set, the props, the planes and the lights — not the figures', 'info'); return }
    const next = [...get().templates.filter((t) => t.name !== name), { name, objects, saved_at: new Date().toISOString(), thumb_asset_id: null }]
    try {
      set({ templates: (await unwrap(http.PUT('/project/stage-templates', { body: { templates: next } as never }))).templates })
      useSession.getState().toast(`Template "${name}" saved: ${objects.length} object${objects.length === 1 ? '' : 's'}`, 'success')
    } catch (e) { useSession.getState().toast(`Save template failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  applyTemplate: (name) => {
    const t = get().templates.find((x) => x.name === name), cur = get().current
    if (!t || !cur) return
    const ids = new Map<string, string>()
    const src = t.objects as unknown as StageObject[]
    for (const o of src) ids.set(o.id, newId(o.kind === 'mannequin' ? 'fig' : o.kind))
    const added = src.map((o, i) => ({ ...o, id: ids.get(o.id)!, parent: o.parent && ids.has(o.parent) ? ids.get(o.parent)! : null, colour_id: ((cur.objects.length + i) % 12) + 1 }))
    get().apply((d) => ({ ...d, objects: [...d.objects, ...added] }), 'template')
    set({ selected: added[added.length - 1]?.id ?? null, selectedCamera: null, stageSelected: false })
    useSession.getState().toast(`"${name}" added: ${added.length} object${added.length === 1 ? '' : 's'}`, 'success')
  },
  deleteTemplate: async (name) => {
    const next = get().templates.filter((t) => t.name !== name)
    try { set({ templates: (await unwrap(http.PUT('/project/stage-templates', { body: { templates: next } as never }))).templates }) }
    catch (e) { useSession.getState().toast(`Delete template failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  savePose: async (name, id) => {
    const o = get().object(id)
    if (!o || !name.trim()) return
    const poses = { ...get().userPoses, [name.trim()]: { preset: o.pose?.preset ?? 'stand', joints: effectiveJoints(o) } }
    try { await putPoses(poses, set, get); useSession.getState().toast(`Pose "${name.trim()}" saved to the project`, 'success') }
    catch (e) { useSession.getState().toast(`Save pose failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  deletePose: async (name) => {
    const poses = { ...get().userPoses }
    delete poses[name]
    try { await putPoses(poses, set, get) }
    catch (e) { useSession.getState().toast(`Delete pose failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  load: async () => { try { set({ stages: (await unwrap(http.GET('/stages'))).items }) } catch { set({ stages: [] }) } },
  create: async (name) => {
    try {
      const st = await unwrap(http.POST('/stages', { body: { name } }))
      set({ stages: [st, ...get().stages] })
      await get().open(st.id)
      return st
    } catch (e) { useSession.getState().toast(`New stage failed: ${(e as ApiError).detail ?? e}`, 'error'); return null }
  },
  open: async (id) => {
    if (!id) { set({ current: null, selected: null, selectedCamera: null, stageSelected: false, undo: [], redo: [] }); return }
    try {
      const st = await unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: id } } }))
      set({ current: st, selected: null, selectedCamera: null, stageSelected: false, posing: false, selectedJoint: null, undo: [], redo: [], stages: get().stages.some((s) => s.id === st.id) ? get().stages.map((s) => (s.id === st.id ? st : s)) : st.purpose === 'stage' ? [st, ...get().stages] : get().stages,   // D142: a bench stays out of the picker
        shot: { ...get().shot, refs: [], use_as_is: false }, shots: [], frame: st.range?.start ?? 0, playing: false, shotStart: null })
      void get().loadShots(); void get().refreshShotPreview()
      if (st.objects.some((o) => o.profile_id)) { profilesForMentions(); get().syncBodies() }        // CA0: the bound figures' bodies
    } catch (e) { useSession.getState().toast(`Open stage failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  rename: async (name) => { const cur = get().current; if (!cur || !name.trim()) return; set({ current: { ...cur, name: name.trim() } }); await save(get, set) },
  destroy: async () => {
    const cur = get().current
    if (!cur) return
    try {
      await unwrap(http.DELETE('/stages/{st_id}', { params: { path: { st_id: cur.id } } }))
      set({ stages: get().stages.filter((s) => s.id !== cur.id) })
      await get().open(null)
    } catch (e) { useSession.getState().toast(`Delete failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },

  apply: (fn, label) => {
    const cur = get().current
    if (!cur) return
    const next = fn(cur)
    if (next === cur) return
    set({ current: next, undo: [...get().undo.slice(-63), cur], redo: [] })
    schedule(get, set)
    void label
  },
  undoEdit: () => { const u = get().undo; const cur = get().current; if (!u.length || !cur) return; set({ current: { ...u[u.length - 1], revision: cur.revision }, undo: u.slice(0, -1), redo: [...get().redo, cur] }); schedule(get, set) },
  redoEdit: () => { const r = get().redo; const cur = get().current; if (!r.length || !cur) return; set({ current: { ...r[r.length - 1], revision: cur.revision }, redo: r.slice(0, -1), undo: [...get().undo, cur] }); schedule(get, set) },
  select: (id) => { const same = !!id && id === get().selected                       // the same figure again keeps its joint and pose mode (the author, 2026-10-22)
    set({ selected: id, selectedJoint: same ? get().selectedJoint : null, posing: same ? get().posing : false, selectedCamera: null, stageSelected: false }) },   // the same figure again keeps its joint (the author, 2026-10-22)
  selectCamera: (id) => { set({ selected: null, selectedJoint: null, posing: false, selectedCamera: id, stageSelected: false }); if (id) get().setActiveCamera(id) },
  selectStage: () => set({ selected: null, selectedJoint: null, posing: false, selectedCamera: null, stageSelected: true }),
  moveCamera: (id, pos) => {
    const c = get().current?.cameras.find((x) => x.id === id)
    if (!c) return
    const d = [pos[0] - c.pos[0], pos[1] - c.pos[1], pos[2] - c.pos[2]]
    get().updateCamera(id, { pos: pos.map((v) => +v.toFixed(4)), target: c.target.map((v, i) => +(v + d[i]).toFixed(4)) })
  },
  setTool: (tool) => set({ tool }),
  setSnap: (snap) => set({ snap }),
  setView: (view) => set({ view }),
  setGuides: (guides) => set({ guides }),
  setPip: (pip) => set({ pip }),

  addObject: (kind, preset = null, pos, assetId = null) => {
    const cur = get().current
    if (!cur) return null
    const o = newObject(cur, kind, preset, pos, assetId)
    get().apply((d) => ({ ...d, objects: [...d.objects, o] }), 'add')
    set({ selected: o.id })
    return o.id
  },
  placePlace: (profileId) => {
    const cur = get().current
    if (!cur) return null
    const here = cur.objects.find((o) => o.kind === 'set' && o.profile_id === profileId)
    if (here) { get().select(here.id); return here.id }
    const p = useStory.getState().profiles.find((x) => x.id === profileId)
    const ps = p?.versions.find((x) => x.id === p.current)?.place_set
    if (!p || !ps) { useSession.getState().toast(`${p?.name ?? 'The place'} has no set yet — Build the set ▶ on its Cast page`, 'info'); return null }
    const o = { ...newObject(cur, 'set', 'built'), name: p.name, locked: true, profile_id: profileId, version: null, place_set: ps }
    get().apply((d) => ({ ...d, objects: [...d.objects, o] }), 'place a Cast set')
    set({ selected: o.id })
    return o.id
  },
  setFromImage: async (assetId) => {
    const cur = get().current
    const s = useSession.getState()
    if (!cur) { s.toast('Open a stage first (the Shot section)', 'info'); return }
    // D123 (SC3c-1): the lens asked before the job — prefilled from what the picture knows; empty lets MoGe read it
    let guess = null
    try { guess = await lensGuess(await unwrap(http.GET('/assets/{asset_id}', { params: { path: { asset_id: assetId } } }))) } catch { /* no guess */ }
    let lens: number | null | 'invalid' = 'invalid'
    let initial = guess ? `${guess.mm} mm` : ''
    let problem = ''
    const how = "A focal length on a 36 mm sensor, or the horizontal angle in degrees; left empty, MoGe reads it from the picture (it wobbles by a few degrees — the set's row can rebuild with a corrected lens)."
    while (lens === 'invalid') {
      const text = await s.askText({ title: "A set from this image — the picture's lens", okLabel: 'Make the set', initial, allowEmpty: true,
        placeholder: 'e.g. 35 mm or 70° — empty: MoGe reads it from the picture',
        text: `${problem}${guess ? `${guess.from} says ${guess.mm} mm. ` : ''}${how}` })
      if (text === null) return                                                     // cancelled: nothing queued
      lens = parseLens(text)
      if (lens === 'invalid') { problem = `"${text}" is not a lens between 20° and 150° (about 5–100 mm). `; initial = text }
    }
    try {
      const r = await unwrap(http.POST('/stages/{st_id}/image-set', { params: { path: { st_id: cur.id } }, body: { asset_id: assetId, lens_deg: lens, relief: 'cut' } }))
      set({ pendingSet: r.job_id })
      s.toast(`Making a set from the picture${lens ? ` at ${lens}°` : ''} — a few seconds once MoGe is loaded; the stage reloads with it`, 'info')
    } catch (e) { s.toast(`Set from an image failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  rebuildImageSet: async (setId, lensDeg) => {
    const cur = get().current
    const o = cur?.objects.find((x) => x.id === setId)
    if (!cur || !o?.plate_asset_id) return
    try {
      const r = await unwrap(http.POST('/stages/{st_id}/image-set', { params: { path: { st_id: cur.id } }, body: { asset_id: o.plate_asset_id, lens_deg: lensDeg, relief: null, replace_set_id: setId } }))
      set({ pendingSet: r.job_id })
      useSession.getState().toast(`Rebuilding ${o.name} at ${lensDeg}° — seconds once MoGe is loaded; the stage reloads with it`, 'info')
    } catch (e) { useSession.getState().toast(`Rebuild the set failed: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  updateObject: (id, patch) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, ...patch } : o)) }), 'edit'),
  hold: (id, figureId, hand) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id
    ? { ...o, parent: figureId, parent_joint: hand, transform: { pos: [0, -0.04, 0.03], rot: [0, 0, 0], scale: o.transform.scale } } : o)) }), 'hold'),
  letGo: (id) => {
    const world = get().worldOf?.(id) ?? null                                                       // where it stands now (the viewport's engine)
    get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, parent: null, parent_joint: null, ...(world ? { transform: world } : {}) } : o)) }), 'let go')
  },
  setParent: (id, parentId) => {                                     // proto01_UIcast CB4: it stays where it stands — its transform re-expressed in the new parent's frame
    const worldOf = get().worldOf
    const world = worldOf?.(id) ?? null, pw = parentId ? worldOf?.(parentId) ?? null : null
    const local = !world ? null : !parentId ? world : pw ? transformOf(matrixOf(pw).invert().multiply(matrixOf(world))) : null
    get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, parent: parentId, parent_joint: null, ...(local ? { transform: local } : {}) } : o)) }), parentId ? 'parent' : 'unparent')
  },
  setAmbient: (v) => get().apply((d) => ({ ...d, ambient: v }), 'ambient'),
  addLight: (at) => {
    const c = at ?? [0, 0, 0]
    const id = get().addObject('light', null, [c[0] - 2.5, 3, c[2] + 2])
    if (id) get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, light: { ...NEW_LIGHT, target: [c[0], 1, c[2]] } } : o)) }), 'aim light')
    return id
  },
  setTransform: (id, t) => {
    const cur = get().current
    if (cur && keyframesOf(cur).objects[id]?.length) {                   // ST4: a keyed object takes the edit as a key at this frame
      const o = get().sampledDoc()?.objects.find((x) => x.id === id)
      get().apply((d) => withObjectKey(d, id, { frame: get().frame, ease: 'ease', transform: t, pose: o?.pose ? { preset: o.pose.preset, joints: { ...o.pose.joints }, extra: { ...(o.pose.extra ?? {}) }, ground: o.pose.ground ?? 0, pins: { ...(o.pose.pins ?? {}) } } : null }), 'key object')
      return
    }
    get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, transform: t } : o)) }), 'transform')
  },
  removeObject: (id) => {
    const worldOf = get().worldOf
    get().apply((d) => {
      const gone = new Set<string>([id])
      let grew = true
      while (grew) { grew = false; for (const o of d.objects) if (o.parent && !o.parent_joint && gone.has(o.parent) && !gone.has(o.id)) { gone.add(o.id); grew = true } }
      return { ...d, objects: d.objects.filter((o) => !gone.has(o.id)).map((o) => (o.parent_joint && o.parent && gone.has(o.parent)          // D129: a held thing is let go where it is
        ? { ...o, parent: null, parent_joint: null, transform: worldOf?.(o.id) ?? o.transform } : o)) }
    }, 'remove')
    const sel = get().selected                                                            // V88: a selected child of the removed parent went with it
    if (sel && !get().current?.objects.some((o) => o.id === sel)) set({ selected: null })
  },
  duplicateObject: (id) => {
    const src = get().object(id)
    if (!src) return
    const nid = newId(src.kind === 'mannequin' ? 'fig' : src.kind)
    const copy: StageObject = { ...src, id: nid, name: `${src.name} copy`, transform: { ...src.transform, pos: [src.transform.pos[0] + 0.6, src.transform.pos[1], src.transform.pos[2]] }, locked: false,
      profile_id: null, version: null, body: null, detail: src.detail ?? null, path: null, shadow_proxy: null }                        // D93 (C8): one figure per character — the copy is unbound
    get().apply((d) => ({ ...d, objects: [...d.objects, copy] }), 'duplicate')
    set({ selected: nid })
  },
  addCamera: () => {
    const cur = get().current
    if (!cur) return
    const base = get().activeCamera()
    const id = newId('cam')
    const cam: StageCamera = { id, name: `Camera ${cur.cameras.length + 1}`, pos: base ? [...base.pos] : [0, 1.5, 4], target: base ? [...base.target] : [0, 1, 0], roll: 0, focal_mm: base?.focal_mm ?? 35, sensor_mm: 36 }
    get().apply((d) => ({ ...d, cameras: [...d.cameras, cam], active_camera: id }), 'add camera')
  },
  updateCamera: (id, patch) => {
    const cur = get().current
    const keyed = 'pos' in patch || 'target' in patch || 'focal_mm' in patch
    if (cur && keyed && keyframesOf(cur).camera[id]?.length) {           // ST4: a keyed camera takes a move as a key at this frame
      const cam = get().sampledDoc()?.cameras.find((c) => c.id === id)
      if (cam) { get().apply((d) => withCameraKey(d, id, { frame: get().frame, ease: 'ease', pos: [...(patch.pos ?? cam.pos)], target: [...(patch.target ?? cam.target)], focal_mm: patch.focal_mm ?? cam.focal_mm }), 'key camera'); return }
    }
    get().apply((d) => ({ ...d, cameras: d.cameras.map((c) => (c.id === id ? { ...c, ...patch } : c)) }), 'camera')
  },
  removeCamera: (id) => get().apply((d) => {
    if (d.cameras.length <= 1) return d
    const cameras = d.cameras.filter((c) => c.id !== id)
    return { ...d, cameras, active_camera: d.active_camera === id ? cameras[0].id : d.active_camera }
  }, 'remove camera'),
  setActiveCamera: (id) => get().apply((d) => (d.active_camera === id ? d : { ...d, active_camera: id }), 'active camera'),
  frameView: (ids) => set({ frameRequest: { ids, n: get().frameRequest.n + 1 } }),
  object: (id) => (id ? get().current?.objects.find((o) => o.id === id) : undefined),
  activeCamera: () => { const c = get().current; return c?.cameras.find((x) => x.id === c.active_camera) ?? c?.cameras[0] },
  openBench: async (profileId, version = null) => {
    try {
      const r = await unwrap(http.POST('/stages/bench', { body: { profile_id: profileId, version } }))
      await get().open(r.stage.id)
      benchBack = () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: profileId, version: r.stage.bound?.version ?? version }))
      navigate({ suite: 'stage' })
      return true
    } catch (e) { useSession.getState().toast(`The bench: ${(e as ApiError).detail ?? e}`, 'error'); return false }
  },
  openLineup: async (items, back) => {
    try {
      const st = await unwrap(http.POST('/stages/lineup', { body: { items: items.map((x) => ({ profile_id: x.profile_id ?? null, version: x.version ?? null, idea_id: x.idea_id ?? null, variant_id: null })) } }))
      await get().open(st.id)
      benchBack = back ?? null
      navigate({ suite: 'stage' })
      const left = items.length - st.objects.filter((o) => o.kind !== 'set').length
      if (left > 0) useSession.getState().toast(`${left} left out: an idea needs its clay (Make the clay ▶), a prop its 3D model; places come with their sets`, 'info')
      return true
    } catch (e) { useSession.getState().toast(`The line-up: ${(e as ApiError).detail ?? e}`, 'error'); return false }
  },
  backFromBench: () => {
    const cur = get().current
    const back = benchBack ?? (cur?.bound ? () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: cur.bound!.profile_id, version: cur.bound!.version }))
      : () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: '' })))
    benchBack = null
    back()
  },
  sendLineup: async (target) => {
    const cur = get().current
    if (!cur || cur.purpose !== 'lineup') return
    const things = cur.objects.filter((o) => !(o.kind === 'set' && o.preset === 'lineup'))
    let id = target
    if (!id) {
      const name = await useSession.getState().askText({ title: 'Send the line-up to a new stage', text: 'Its figures and props, where they stand; the new stage opens.', placeholder: 'stage name', initial: 'Line-up' })
      if (!name?.trim()) return
      try { id = (await unwrap(http.POST('/stages', { body: { name: name.trim() } }))).id } catch (e) { useSession.getState().toast(`New stage: ${(e as ApiError).detail ?? e}`, 'error'); return }
    }
    benchBack = null
    await get().open(id)
    const d = get().current
    if (!d || d.id !== id) return
    const bound = new Set(d.objects.filter((o) => o.kind === 'mannequin' && o.profile_id).map((o) => o.profile_id))
    const added = things.map((o, k) => ({ ...o, id: newId(o.kind === 'mannequin' ? 'fig' : o.kind), colour_id: ((d.objects.length + k) % 12) + 1,
      ...(o.kind === 'mannequin' && o.profile_id && bound.has(o.profile_id) ? { profile_id: null, version: null } : {}) }))   // one figure per character: a second stands free
    get().apply((doc) => ({ ...doc, objects: [...doc.objects, ...added] }), 'from the line-up')
    useSession.getState().toast(`${added.length} from the line-up in ${d.name}`, 'success')
  },
  poseAll: (preset) => { for (const o of get().current?.objects ?? []) if (o.kind === 'mannequin') get().applyPose(o.id, preset) },
  placeCharacter: (profileId, pos) => {
    const here = get().current?.objects.find((o) => o.kind === 'mannequin' && o.profile_id === profileId)
    if (here) { get().select(here.id); return }
    const id = get().addObject('mannequin', 'adult', pos)
    if (!id) return
    get().bindFigure(id, profileId)
    const name = useStory.getState().profiles.find((p) => p.id === profileId)?.name
    if (name) get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, name } : o)) }), 'name')   // the character's name, not "Figure 3"
  },
  freeCopy: (id) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    const set = o?.kind === 'set' && o.preset === 'built' && !!o.place_set
    if (!o || !o.profile_id || (o.kind !== 'mannequin' && o.kind !== 'mesh' && !set)) return
    const nid = newId(o.kind === 'mannequin' ? 'fig' : o.kind)
    const dx = set ? (o.place_set!.sizes.width ?? 5) + 1 : 0.8                             // CW7: a set's copy beside it, not inside it
    const copy: StageObject = { ...JSON.parse(JSON.stringify(o)) as StageObject, id: nid, name: `${o.name} (free)`, profile_id: null, version: null, parent: null, parent_joint: null,
      transform: { ...o.transform, pos: [o.transform.pos[0] + dx, o.transform.pos[1], o.transform.pos[2]] }, colour_id: ((get().current?.objects.length ?? 0) % 12) + 1 }
    get().apply((d) => ({ ...d, objects: [...d.objects, copy] }), 'free copy')
    get().select(nid)
  },
  prototypeObject: async (id) => {
    const o = get().sampledDoc()?.objects.find((x) => x.id === id) ?? get().object(id)
    const s = useSession.getState()
    if (!o || o.profile_id || (o.kind !== 'mannequin' && o.kind !== 'mesh')) return
    const { viewport } = await import('./stageCommands')
    const blob = await viewport.snapshot?.(id)
    if (!blob) { s.toast('Prototype: the viewport is not ready', 'error'); return }
    try {
      const sha = await sha256Hex(await blob.arrayBuffer())
      await api.putBlob(sha, blob)
      const fig = o.kind === 'mannequin'
      const idea = await unwrap(http.POST('/story/ideas/from-clay', { body: { cls: fig ? 'character' : 'prop', name: o.name.slice(0, 80) || (fig ? 'figure' : 'prop'), blob: sha,
        clay: fig ? { kind: 'figure', body: o.body as never, shell_asset_id: o.shadow_proxy ?? null, model_asset_id: null, height_m: null }
          : { kind: 'model', body: null, shell_asset_id: null, model_asset_id: o.asset_id ?? null, height_m: o.height_m ?? null } } }))
      void import('../story/ideasStore').then((m) => { if (m.useIdeas.getState().loaded) void m.useIdeas.getState().load() })
      s.toast(`New ${fig ? 'character' : 'prop'} idea “${idea.name}” on Cast's Ideas board`, 'success', { label: 'Open', run: () => void import('../../store/origin').then((m) => m.goToIdea(idea.id)) })
    } catch (e) { s.toast(`Prototype: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  setHeight: (id, h) => get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id && o.kind === 'mesh' && !o.profile_id ? { ...o, height_m: h } : o)) }), 'height'),
  setToPlace: async (id) => {
    const o = get().object(id)
    const s = useSession.getState()
    if (!o || o.kind !== 'set' || o.preset !== 'image' || !o.plate_asset_id) return
    const name = await s.askText({ title: 'Make it a Cast place', text: "A Cast place with this set's picture as its set picture; Build the set ▶ fits a room, a corridor or a street to it (the camera at eye level). The picture set stays here.",
      initial: o.name, placeholder: 'the place\'s name', okLabel: 'Make the place' })
    if (!name?.trim()) return
    try {
      const p = await unwrap(http.POST('/story/profiles', { body: { name: name.trim(), cls: 'place', hero_asset_id: null, appearance: '' } }))
      await unwrap(http.PUT('/story/profiles/{pid}/versions/{vid}/anim-ref', { params: { path: { pid: p.id, vid: p.current } }, body: { side: 'front', asset_id: o.plate_asset_id } }))
      await unwrap(http.POST('/story/profiles/{pid}/versions/{vid}/set/fit', { params: { path: { pid: p.id, vid: p.current } }, body: { camera_height_m: 1.6 } }))
      void useStory.getState().loadProfiles()
      s.toast(`${p.name} is a Cast place — its set is being built from the picture`, 'success', { label: 'Open', run: () => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: p.id })) })
    } catch (e) { s.toast(`Make it a Cast place: ${(e as ApiError).detail ?? e}`, 'error') }
  },
  bindFigure: (id, profileId, version = null) => {
    const o = get().object(id)
    if (!o || o.kind !== 'mannequin') return
    get().apply((d) => ({ ...d, objects: d.objects.map((x) => (x.id === id ? withBody(rebound(x, profileId, profileId ? version : null), castBody(profileId, version))
      : profileId && x.profile_id === profileId ? { ...rebound(x, null, null), body: null } : x)) }), profileId ? 'bind figure' : 'unbind figure')   // one figure per character: it moves
    void get().refreshShotPreview()
  },
  placeProp: (profileId, pos) => {
    const p = useStory.getState().profiles.find((x) => x.id === profileId)
    const model = castModel(profileId, null)
    if (!p || p.cls !== 'prop' || !model) return null
    const id = get().addObject('mesh', null, pos, model)
    if (!id) return null
    get().apply((d) => ({ ...d, objects: d.objects.map((o) => (o.id === id ? { ...o, name: p.name, profile_id: profileId, version: null } : o)) }), 'place prop')
    return id
  },
  bindProp: (id, profileId, version = null) => {
    const o = get().current?.objects.find((x) => x.id === id)
    if (!o || o.kind !== 'mesh') return
    get().apply((d) => ({ ...d, objects: d.objects.map((x) => (x.id === id ? withModel({ ...x, profile_id: profileId, version: profileId ? version : null }) : x)) }), profileId ? 'bind prop' : 'unbind prop')
  },
  figureMentions: () => { const d = get().sampledDoc(); return d ? figureMentions(d.objects, d.cameras.find((c) => c.id === d.active_camera) ?? d.cameras[0]) : [] },
  prebindSpeakers: (speakers) => {
    const d = get().current
    if (!d) return null
    const map = prebindOf(d.objects, get().activeCamera(), speakers)
    if (!map) return null
    const pinOf = (pid: string) => speakers.find((s) => s.id === pid)?.version ?? null
    get().apply((doc) => ({ ...doc, objects: doc.objects.map((x) => { if (!(x.id in map)) return x; const ver = x.profile_id === map[x.id] ? x.version : pinOf(map[x.id]); return withBody(rebound(x, map[x.id], ver), castBody(map[x.id], ver)) }) }), 'bind the speakers')
    void get().refreshShotPreview()
    return Object.keys(map).length
  },
  syncBodies: () => {
    const d = get().current
    if (!d || !d.objects.some((o) => (o.kind === 'mannequin' || o.kind === 'mesh' || o.kind === 'set') && o.profile_id)) return
    const next = d.objects.map((o) => (o.kind === 'mannequin' && o.profile_id ? withBody(o, castBody(o.profile_id, o.version)) : o.kind === 'set' ? withPlaceSet(o) : withModel(o)))
    if (next.every((o, i) => o === d.objects[i])) return
    const doc = get().current                                                             // V86: an external Cast change is not the stage's undo step
    if (!doc) return
    set({ current: { ...doc, objects: doc.objects.map((o) => next.find((x) => x.id === o.id) ?? o) } })
    schedule(get, set)
  },
}))

// CS2: a character's shell binds in the stance of the reference it was made from
setShellPoints(versionPointsOfShell)
// CA0: a Cast sheet's body edited (or the profiles loaded) — the open stage's bound figures follow
useStory.subscribe((s, prev) => { if (s.profiles !== prev.profiles) st().syncBodies() })
// SC3 (D120): the image → set job landed (or failed) — the stage is reloaded with its relief and the picture's camera
useSession.subscribe((s, prev) => {
  if (s.jobs === prev.jobs) return
  const id = useStage.getState().pendingSet
  if (!id) return
  const j = s.jobs[id]
  if (!j || j.status === 'queued' || j.status === 'running') return
  useStage.setState({ pendingSet: null })
  const cur = useStage.getState().current
  if (j.status === 'done') {
    const r = j.result as { stage_id?: string; relief?: { fov_x?: number } | null } | null
    if (cur && r?.stage_id === cur.id) void useStage.getState().open(cur.id)
    const rebuilt = !!(j.recipe as { replace_set_id?: string | null }).replace_set_id                   // SC3b: a rebuild in place
    s.toast(rebuilt ? `The set is rebuilt${r?.relief?.fov_x ? ` — its lens ${r.relief.fov_x}°` : ''}` : r?.relief?.fov_x ? `The set is on the stage with its camera — the picture's lens reads ${r.relief.fov_x}°` : 'The set is on the stage with its camera', 'success')
  } else s.toast(`Set from an image ${j.status}: ${j.error ?? ''}`, 'error')
})

/** SC3 (D120): how far the active camera stands from the picture's camera against E30's budget — within ±0.25 m and ±5°, or an orbit
 *  of ±10° about the picture's depth (the camera moved under a metre, turned under 10°): the picture's edge stays under a tenth of the frame. */
export function imageSetBudget(doc: StageDoc, o: StageObject): { within: boolean; text: string } {
  const pc = doc.cameras.find((c) => c.id === o.plate_camera_id)
  const ac = doc.cameras.find((c) => c.id === doc.active_camera)
  if (!pc || !ac) return { within: true, text: 'the picture camera is gone' }
  const d = Math.hypot(ac.pos[0] - pc.pos[0], ac.pos[1] - pc.pos[1], ac.pos[2] - pc.pos[2])
  const dir = (c: StageCamera) => { const v = [c.target[0] - c.pos[0], c.target[1] - c.pos[1], c.target[2] - c.pos[2]]; const n = Math.hypot(v[0], v[1], v[2]) || 1; return v.map((x) => x / n) }
  const a = dir(ac), b = dir(pc)
  const ang = (Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))) * 180) / Math.PI
  const within = (d <= 0.25 && ang <= 5) || (d <= 0.75 && ang <= 10)
  const how = `${d.toFixed(2)} m, ${ang.toFixed(0)}° from the picture's camera`
  return { within, text: within ? `within the picture's budget (${how})` : `beyond the picture's budget (${how}): its edge will show` }
}

export const st = () => useStage.getState()

// D121 (AW2): the Clay level's transport — the scene's frame, its range as the work area, its keys as the marks (registered with the stage's code)
{
  const s = () => useStage.getState()
  registerTransport('stage', {
    ready: () => !!s().current, playing: () => s().playing, play: (on) => s().setPlaying(on ?? !s().playing),
    frame: () => s().frame, seek: (f) => s().setFrame(f), step: (d) => { s().setPlaying(false); s().setFrame(s().frame + d) },
    home: () => { s().setPlaying(false); s().setFrame(s().current?.range.start ?? 0) }, end: () => { s().setPlaying(false); s().setFrame(s().current?.range.end ?? 0) },
    setIn: () => { const f = s().frame; s().setRange(f, Math.max(f + 1, s().current!.range.end)) }, setOut: () => { const f = s().frame; s().setRange(Math.min(f - 1, s().current!.range.start), f) },
    marks: () => s().keyedFrames(),
  })
}

/** U1 (D157, 06 §5.3): the open stage per context (Shots: a shot's scene) — the stage a context had open is opened again on returning. */
export const stageContext = contextSlot<string | null>(() => useStage.getState().current?.id ?? null, (id) => { if (id && useStage.getState().current?.id !== id) void useStage.getState().open(id) })
