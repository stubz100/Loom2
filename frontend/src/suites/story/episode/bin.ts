// D90 (B7, Y57): what the Episode's Shots bin offers and what a drop on the lane takes — pure, so the bin's +, the lane's drop and the
// drag ghost agree (D71). A shot offers its final version's clip (the current one when it is final, else the newest final one), else the
// current version's; a card from the Shots bin lands stamped with its shot, a clip from anywhere else lands plain.
import type { DragItem, DragPayload, DropVerdict } from '../../../frame/drag'
import { laneDrop } from '../../../frame/dropRules'

interface ShotLike { id: string; name: string; current: string; owner_node?: string | null; versions: { id: string; state: string; clip_id?: string | null }[] }
interface ClipLike { id: string; asset_id?: string | null }
export interface ShotStamp { id: string; version: string; node: string | null }

/** The version the Episode takes from a shot (Y57): the final one first, else the current. */
export function binVersion<V extends ShotLike['versions'][number]>(sh: { current: string; versions: V[] }): V | undefined {
  const cur = sh.versions.find((v) => v.id === sh.current)
  if (cur?.state === 'final') return cur
  return [...sh.versions].reverse().find((v) => v.state === 'final') ?? cur
}

/** The Shots bin's rows: a shot whose chosen version has a clip in the project, final ones first, then by name. */
export function shotRows<S extends ShotLike, C extends ClipLike>(shots: S[], clips: C[]): { sh: S; v: S['versions'][number]; c: C }[] {
  return shots.flatMap((sh) => { const v = binVersion(sh); const c = v?.clip_id ? clips.find((x) => x.id === v.clip_id) : undefined; return v && c ? [{ sh, v, c }] : [] })
    .sort((a, b) => (a.v.state === b.v.state ? a.sh.name.localeCompare(b.sh.name) : a.v.state === 'final' ? -1 : 1))
}

/** The lane's drop: every clip to the end; a Shots-bin card stamped with the shot whose row offers that clip. */
export function laneTake<S extends ShotLike, C extends ClipLike>(p: DragPayload | DragItem[], clips: C[], shots: S[]): { take: { clip: C; shot?: ShotStamp }[]; verdict: DropVerdict } {
  const base = laneDrop(p, clips)
  if (!base.verdict.ok) return { take: [], verdict: base.verdict }
  const rows = !Array.isArray(p) && p.from === 'shots-bin' ? shotRows(shots, clips) : []
  const take = base.take.map((clip) => { const r = rows.find((x) => x.c.id === clip.id); return r ? { clip, shot: { id: r.sh.id, version: r.v.id, node: r.sh.owner_node ?? null } } : { clip } })
  const stamped = take.filter((t) => t.shot).length
  const label = stamped ? (take.length === 1 ? `Add ${rows.find((x) => x.c.id === take[0].clip.id)?.sh.name ?? 'the shot'} to the end of the episode` : `Add ${take.length} shots to the episode`) : base.verdict.label
  return { take, verdict: { ok: true, label } }
}
