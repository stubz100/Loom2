// D90 (02 §5, §4.2): makers in context — "Make frame ▸" / "Make clip ▸" open Generate or Animate *for* a shot version: the maker gets
// the For chip (store/origin.ts), its results come back as the version's takes (the server's `for_shot` finisher hook), and it starts
// from what the shot has: Generate from the owner node's words (a Shot node's line, a Dialogue node's speakers as @mentions) and the
// node's board (an album group) as references; Animate from the version's frame as the start and the Shot node's line as the motion.
// The pure parts (the target version, the pre-fill, the board's order, the board drop) are tested; the two actions below them are not.
import { http, unwrap, type ApiError } from '../../api/client'
import type { FlowNode, GroupPage, Profile, Shot, ShotVersion } from '../../api/types'
import type { DragPayload, DropVerdict } from '../../frame/drag'
import { forLabel, useMakeFor, type MakeFor } from '../../store/origin'
import { useSession } from '../../store/session'
import type { MentionRef } from '../generate/generateStore'
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

/** What Generate starts from (where sensible): a Shot node's line (else its title); a Dialogue node's title, its speakers as @mentions of
 *  their profiles (D73 / D85: each one's current reference set rides along as references). `text` null: the prompt is left as it is. */
export function framePrefill(node: FlowNode | undefined, profiles: Profile[]): { text: string | null; mentions: MentionRef[] } {
  if (!node) return { text: null, mentions: [] }
  const speakers = node.type === 'dialogue' ? [...new Set(node.lines.map((l) => l.speaker).filter((x): x is string => !!x))] : []
  const mentions = speakers.map((id) => profiles.find((p) => p.id === id)).filter((p): p is Profile => !!p)
    .map((p) => ({ group_id: p.versions.find((v) => v.id === p.current)?.group_id ?? '', name: p.name, profile_id: p.id }))
  const words = (node.type === 'shot' ? node.text.trim() || node.title.trim() : node.type === 'dialogue' ? node.title.trim() : '').replace(/[\s.]+$/, '')
  const who = mentions.map((m) => `@${m.name}`).join(' and ')
  const text = [who, words].filter(Boolean).join(', ')
  return { text: text || null, mentions }
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

/** Make frame ▸ Generate: the For chip set, the panel pre-filled (the node's words, the board's references within the model's limit). */
export async function makeFrameFor(s: Shot, v: ShotVersion, nodeId?: string | null): Promise<void> {
  const st = useStory.getState()
  const f = forShot(s, v, nodeId)
  const node = f.node_id ? st.flowNodes[f.node_id] : undefined
  useMakeFor.getState().set('generate', f)
  const { useGenerate } = await import('../generate/generateStore')
  const g = useGenerate.getState()
  const pre = framePrefill(node, st.profiles)
  if (pre.text) { g.set({ text: pre.text, ...(g.panel.prompt_mode === 'json' ? { prompt_mode: 'text' as const } : {}) }); pre.mentions.forEach((m) => g.addMention(m)) }
  let refs = 0
  if (node?.board_group_id) {
    try {
      const ids = boardRefs(await unwrap(http.GET('/groups/{gid}', { params: { path: { gid: node.board_group_id } } })))
      if (ids.length) { g.set({ refs: [] }); refs = useGenerate.getState().addRefs(ids) }
    } catch (e) { toast(`The board could not be read: ${(e as ApiError).detail ?? e}`, 'error') }
  }
  useSession.getState().setSuite('generate')
  toast(`Generate for ${forLabel(f)} — the results come back as its takes${refs ? `; ${refs} reference${refs === 1 ? '' : 's'} from the board` : ''}`)
}

/** Make clip ▸ Animate: the For chip set, the version's frame as the start, a Shot node's line as the motion. */
export async function makeClipFor(s: Shot, v: ShotVersion, nodeId?: string | null): Promise<void> {
  const st = useStory.getState()
  const f = forShot(s, v, nodeId)
  useMakeFor.getState().set('animate', f)
  const { useAnimate } = await import('../animate/animateStore')
  const an = useAnimate.getState()
  if (v.frame_asset_id) an.setStart(v.frame_asset_id)
  const line = clipPrefill(f.node_id ? st.flowNodes[f.node_id] : undefined)
  if (line) an.set({ prompt: line })
  useSession.getState().setSuite('animate')
  toast(`Animate for ${forLabel(f)} — ${v.frame_asset_id ? 'its frame is the start; ' : 'it has no frame yet: set a start; '}the clips come back as its takes`)
}
