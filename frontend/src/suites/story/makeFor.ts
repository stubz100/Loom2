// D90 (02 §5, §4.2): makers in context — "Make frame ▸" / "Make clip ▸" open Generate or Animate *for* a shot version: the maker gets
// the For chip (store/origin.ts), its results come back as the version's takes (the server's `for_shot` finisher hook), and it starts
// from what the shot has: Generate from the owner node's words (a Shot node's line, a Dialogue node's speakers as @mentions) and the
// node's board (an album group) as references; Animate from the version's frame as the start and the Shot node's line as the motion.
// The pure parts (the target version, the pre-fill, the board's order, the board drop) are tested; the two actions below them are not.
// D93 (C7): a Dialogue node's speakers become one linked subject card each (their Cast character — at the version the shot's stage binds to
// it, else the current one — with the figure's pose when one is bound), the node's place links the scene, Generate switches to Tree mode.
import { http, unwrap, type ApiError } from '../../api/client'
import type { FlowNode, GroupPage, Profile, Shot, ShotVersion, StageObject } from '../../api/types'
import type { DragPayload, DropVerdict } from '../../frame/drag'
import { forLabel, useMakeFor, type MakeFor } from '../../store/origin'
import { useSession } from '../../store/session'
import type { FramePrefill } from '../generate/generateStore'
import { poseWords } from '../stage/poseWords'
import { useStory } from './storyStore'

/** The version to make for: the one asked for (a node pins one) when it is open, else the shot's current one when that is open; null when
 *  both are final (a retake is a new version). */
export function makeTarget(s: Shot | undefined, want?: string | null): ShotVersion | null {
  if (!s) return null
  const pick = (id: string | null | undefined) => s.versions.find((v) => v.id === id && v.state === 'open') ?? null
  return pick(want) ?? pick(s.current)
}

/** The For context of a shot version (the node: the one Make came from, else the shot's owner). */
export const forShot = (s: Shot, v: ShotVersion, nodeId?: string | null): MakeFor => ({ kind: 'shot', shot_id: s.id, version: v.id, name: s.name, node_id: nodeId ?? s.owner_node ?? null })

/** A Dialogue node's speakers in the order they first speak (Cast characters only; a speaker deleted from the Cast is skipped). */
export function speakersOf(node: FlowNode | undefined, profiles: Profile[]): Profile[] {
  const ids = node?.type === 'dialogue' ? [...new Set(node.lines.map((l) => l.speaker).filter((x): x is string => !!x))] : []
  return ids.map((id) => profiles.find((p) => p.id === id && p.cls === 'character')).filter((p): p is Profile => !!p)
}

type Figure = Pick<StageObject, 'profile_id' | 'version' | 'pose'>
/** D93 follow-up: the version a speaker is made at — the shot's stage binding wins (a figure bound to the character with a version of its
 *  own: what the Stage render sends), else the node's pin (`FlowNode.speaker_versions`), else the current one. `overrides`: the node's pin the
 *  stage overrode (the Inspector's hint and Make frame's toast say so). A pin or binding to a version deleted since counts as none. */
export function speakerVersion(p: Profile, node: Pick<FlowNode, 'speaker_versions'> | undefined, figures: Figure[] = []): { version: string; from: 'stage' | 'node' | 'current'; overrides: string | null } {
  const has = (v: string | null | undefined): v is string => !!v && p.versions.some((x) => x.id === v)
  const fig = figures.find((f) => f.profile_id === p.id)?.version
  const pin = node?.speaker_versions?.[p.id]
  if (has(fig)) return { version: fig, from: 'stage', overrides: has(pin) && pin !== fig ? pin : null }
  if (has(pin)) return { version: pin, from: 'node', overrides: null }
  return { version: p.current, from: 'current', overrides: null }
}

/** A line as a subject's action: "saying <the line>" — no quote marks (a quoted phrase is lettered into the image as text). */
export const lineAction = (text: string): string => { const t = text.trim().replace(/^["“'‘]+|["”'’]+$/g, '').replace(/[\s.]+$/, '').trim(); return t ? `saying ${t}` : '' }

/** What Generate starts from (where sensible): a Shot node's line (else its title) as the lead text; a Dialogue node's title as the lead text
 *  and D93 (C7) one linked subject card per speaker — the version the shot's stage binds to that character (a figure's `profile_id` /
 *  `version`), else the node's pin for that speaker (D93 follow-up), else the current one (`speakerVersion`), the figure's pose in words — the first line as its speaker's action ("saying …": a line is something the
 *  character does in this shot; "this shot" is composed into the look, after the sheet, so it would read as appearance); the node's place
 *  links the scene. `text` null: the lead text is left as it is. */
export function framePrefill(node: FlowNode | undefined, profiles: Profile[], figures: Figure[] = []): FramePrefill {
  if (!node) return { text: null, subjects: [], place: null }
  const first = node.type === 'dialogue' ? node.lines.find((l) => l.speaker && l.text.trim()) : undefined
  const subjects = speakersOf(node, profiles).map((p) => {
    const fig = figures.find((f) => f.profile_id === p.id)
    const sv = speakerVersion(p, node, figures).version
    const version = sv !== p.current ? sv : undefined
    const action = first?.speaker === p.id ? lineAction(first.text) : ''
    return { profile_id: p.id, ...(version ? { version } : {}), ...(action ? { action } : {}), ...(fig?.pose ? { pose: poseWords(fig.pose) } : {}) }
  })
  const place = node.place_id && profiles.some((p) => p.id === node.place_id && p.cls === 'place') ? node.place_id : null
  const words = (node.type === 'shot' ? node.text.trim() || node.title.trim() : node.type === 'dialogue' ? node.title.trim() : '').replace(/[\s.]+$/, '')
  return { text: words || null, subjects, place }
}

/** The Shot node's line as Animate's motion prompt (a Dialogue node's words are speech, not motion), or null. */
export const clipPrefill = (node: FlowNode | undefined): string | null => (node?.type === 'shot' && node.text.trim() ? node.text.trim() : null)

/** A board's images as references, in the order a mention would give them (D73): the cover first, then the page by position (top to
 *  bottom, left to right); clips, meshes and trashed assets are skipped. */
export function boardRefs(page: Pick<GroupPage, 'group' | 'assets'>): string[] {
  const ok = (id: string) => { const a = page.assets[id]; return !!a && a.kind === 'image' && !a.trashed_at }
  const placed = page.group.items.filter((i) => i.kind === 'asset').sort((a, b) => a.y - b.y || a.x - b.x).map((i) => i.id)
  return [...new Set([...(page.group.cover_id ? [page.group.cover_id] : []), ...placed])].filter(ok)
}

/** A drop on a Flow node (D71's rule, shared by accept / drop / the ghost): one group card becomes the node's board; images are refused. */
export function boardDrop(p: DragPayload, node: string): { group: string | null; verdict: DropVerdict } {
  const groups = p.items.filter((i) => i.kind === 'group')
  if (!p.items.length) return { group: null, verdict: { ok: false } }
  if (!groups.length) return { group: null, verdict: { ok: false, reason: 'A board is a group — drop a group card from Places or a page' } }
  if (groups.length > 1) return { group: null, verdict: { ok: false, reason: 'One board per node — drop one group' } }
  return { group: groups[0].id, verdict: { ok: true, label: `Make ${p.label ? `"${p.label}"` : 'the group'} the board of ${node}` } }
}

const toast = (text: string, kind: 'info' | 'error' = 'info') => useSession.getState().toast(text, kind)

/** D125 (I1): Image › Make opened on a section of its column (the rail's tab, and the column scrolled there once it renders). */
function landOn(suite: 'generate', section: string): void {
  useSession.getState().setSuite(suite)
  void import('../../frame/suiteRegistry').then((m) => m.setRailTab(suite, section))
  const go = (n: number) => { const el = document.getElementById(`gen-sec-${section}`); if (el) el.scrollIntoView({ block: 'start' }); else if (n) requestAnimationFrame(() => go(n - 1)) }
  requestAnimationFrame(() => go(20))
}

/** The figures of the stage a shot version is made on (its `stage_id`) — Make frame ▸ reads their bound characters' versions and poses. */
async function stageFigures(v: ShotVersion): Promise<StageObject[]> {
  if (!v.stage_id) return []
  try { return (await unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: v.stage_id } } }))).objects.filter((o) => o.kind === 'mannequin') } catch { return [] }
}

/** Make frame ▸ Generate: the For chip set, the panel pre-filled (the node's words, D93 (C7) a linked card per speaker and the place as the
 *  scene — Tree mode, the board's references within the model's limit). */
export async function makeFrameFor(s: Shot, v: ShotVersion, nodeId?: string | null): Promise<void> {
  const st = useStory.getState()
  const f = forShot(s, v, nodeId)
  const node = f.node_id ? st.flowNodes[f.node_id] : undefined
  useMakeFor.getState().set('generate', f)
  const { useGenerate } = await import('../generate/generateStore')
  const g = useGenerate.getState()
  const figs = await stageFigures(v)
  const pre = framePrefill(node, st.profiles, figs)
  const over = speakersOf(node, st.profiles).flatMap((p) => { const sv = speakerVersion(p, node, figs); return sv.overrides ? [`${p.name} at ${sv.version} (the stage's binding, not the node's ${sv.overrides})`] : [] })
  g.applyFrame(pre)                                                       // D125 (I1): the shot's own content, never the last shot's
  let refs = 0
  if (node?.board_group_id) {
    try {
      const ids = boardRefs(await unwrap(http.GET('/groups/{gid}', { params: { path: { gid: node.board_group_id } } })))
      if (ids.length) refs = useGenerate.getState().addRefs(ids)
    } catch (e) { toast(`The board could not be read: ${(e as ApiError).detail ?? e}`, 'error') }
  }
  useGenerate.setState({ source: 'prompt' })                              // D125 (I1): on Prompt, the chip in the column's head
  landOn('generate', 'prompt')
  const who = pre.subjects.length ? `; ${pre.subjects.length} subject${pre.subjects.length === 1 ? '' : 's'} from the speakers` : ''
  toast(`Generate for ${forLabel(f)} — the results come back as its takes${who}${over.length ? ` (${over.join('; ')})` : ''}${pre.place ? '; the scene is its place' : ''}${refs ? `; ${refs} reference${refs === 1 ? '' : 's'} from the board` : ''}`)
}

/** Make clip ▸ Animate: the For chip set, the version's frame as the start, a Shot node's line as the motion. U0 (F29, FE#1): the shot's
 *  own content only — the last shot's start, end, beats, words and camera move never carry over (The seal was queued with Departure's
 *  prompt and zoom-out); the model and the production settings stay. */
export async function makeClipFor(s: Shot, v: ShotVersion, nodeId?: string | null): Promise<void> {
  const st = useStory.getState()
  const f = forShot(s, v, nodeId)
  useMakeFor.getState().set('animate', f)
  const { useAnimate } = await import('../animate/animateStore')
  const an = useAnimate.getState()
  const line = clipPrefill(f.node_id ? st.flowNodes[f.node_id] : undefined)
  an.set({ end: null, beats: [], prompt: line ?? '', camera: null })
  an.setStart(v.frame_asset_id ?? null)
  void import('../animate/routeStore').then((r) => r.useAnimRoute.getState().set('i2v'))   // D121: the frame is the start of an image-to-video clip
  useSession.getState().setSuite('animate')
  toast(`Animate for ${forLabel(f)} — ${v.frame_asset_id ? 'its frame is the start; ' : 'it has no frame yet: set a start; '}the clips come back as its takes`)
}
