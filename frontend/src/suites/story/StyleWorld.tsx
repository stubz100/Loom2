// D90 (02 §4.1): World › Styles as images — a grid of tiles (the style's sample, its name, ★ on the default) and the style's editor in
// the World Inspector (the sample large, the name, the prompt fragment folded under it — the only place a fragment is written). An image
// dropped from the Catalogue on a tile or on the editor's sample becomes a sample of that style (a copy on its group) and its cover.
import { Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { WorldStyle } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { useDropTarget } from '../../frame/drag'
import { monogram } from '../../frame/presetGlyphs'
import { useSession } from '../../store/session'
import { useAlbum } from '../catalogue/albumStore'
import { addStyleSamples, rowMenu } from './storyCommands'
import { sy, useStory } from './storyStore'
import { sampleDrop, sampleJob, styleFace } from './styleSamples'

const menu = (id: string): MenuItem[] => rowMenu('style', id).map((m) => (m === 'sep' ? sep : m))

/** The style's face (re-rendered when the album tree moves) and whether a sample is being made. */
function useFace(s: WorldStyle): { face: string | null; busy: boolean } {
  const tree = useAlbum((a) => a.tree)
  const busy = useSession((x) => !!sampleJob(x.jobs, s.id))
  return { face: styleFace(s, tree), busy }
}

/** Drops of Catalogue images on a style (the tile, the editor's sample). */
function useSampleDrop(s: WorldStyle) {
  return useDropTarget((p) => sampleDrop(p, s.name).verdict.ok, (p) => void addStyleSamples(s.id, sampleDrop(p, s.name).take), (p) => sampleDrop(p, s.name).verdict)
}

function StyleTile({ s, active, isDefault }: { s: WorldStyle; active: boolean; isDefault: boolean }) {
  const { face, busy } = useFace(s)
  const { ref, over } = useSampleDrop(s)
  return (
    <div ref={ref} className={`style-tile${active ? ' active' : ''}${over ? ' over' : ''}`} data-id={s.id} role="button" tabIndex={-1} aria-pressed={active} aria-label={`style ${s.name}`}
      title={`${s.name}\n${s.fragment.trim() || 'no prompt fragment yet'}`} onClick={() => sy().select({ kind: 'style', id: s.id })} onContextMenu={(e) => showMenu(e, menu(s.id))}>
      <span className="face">
        {face ? <img src={api.thumbUrl(face, 256)} alt="" draggable={false} /> : <span className="mono">{monogram(s.name || '?')}</span>}
        {busy && <span className="busy" title="a sample is being made">…</span>}
        <button className={`quiet star${isDefault ? ' on' : ''}`} title={isDefault ? 'The default style (Generate preselects it) — click to clear' : 'Make it the default style'}
          aria-label={isDefault ? `${s.name} is the default style` : `make ${s.name} the default style`} onClick={(e) => { e.stopPropagation(); sy().setDefaultStyle(isDefault ? null : s.id) }}>
          <Star size={12} fill={isDefault ? 'currentColor' : 'none'} />
        </button>
      </span>
      <span className="name">{s.name || 'untitled'}</span>
    </div>
  )
}

export function StyleGrid() {
  const world = useStory((s) => s.world)
  const selected = useStory((s) => s.selected)
  useEffect(() => { if (!useAlbum.getState().tree) void useAlbum.getState().load() }, [])   // once: the faces need the tree (group.changed reloads it)
  markUsed('story.world.styleSample'); markUsed('story.world.openStyleGroup'); markUsed('story.world.defaultStyle')
  if (!world) return null
  return (
    <div className="style-grid" role="group" aria-label="styles">
      {world.styles.map((s) => <StyleTile key={s.id} s={s} active={selected?.kind === 'style' && selected.id === s.id} isDefault={world.default_style === s.id} />)}
      {!world.styles.length && <div className="empty">No styles yet.</div>}
    </div>
  )
}

/** The selected style's editor (the World Inspector). Keyed by the style id, so the fragment's fold starts open only when it is empty. */
export function StyleEditor({ s, isDefault }: { s: WorldStyle; isDefault: boolean }) {
  const { face, busy } = useFace(s)
  const { ref, over } = useSampleDrop(s)
  const [open, setOpen] = useState(!s.fragment.trim())
  return (
    <>
      <h4>Style · {s.name}</h4>
      <div ref={ref} className={`style-sample${over ? ' over' : ''}`} title="The style's sample (its group's cover) — drop a Catalogue image here to make it the sample">
        {face ? <img src={api.thumbUrl(face, 512)} alt={`the sample of ${s.name}`} draggable={false} /> : <span className="hint">No sample yet — make one, or drop an image here.</span>}
        {busy && <span className="busy">rendering a sample…</span>}
      </div>
      <div className="kv">
        <span>name</span><input type="text" value={s.name} aria-label="selected style name" onChange={(e) => sy().setStyle(s.id, { name: e.target.value })} />
        <span>default</span>
        <label className="check" title="The style Generate, Expand and Stage preselect (★)"><input type="checkbox" checked={isDefault} aria-label="the default style" onChange={(e) => sy().setDefaultStyle(e.target.checked ? s.id : null)} /> ★ the project's default</label>
      </div>
      <details className="style-fragment" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary>prompt fragment</summary>
        <textarea rows={3} value={s.fragment} aria-label="selected style fragment" placeholder="appended after the prompt — e.g. painterly storyboard, ink and wash"
          onChange={(e) => sy().setStyle(s.id, { fragment: e.target.value })} />
      </details>
      <div className="verbs"><CommandButton id="story.world.styleSample" text /><CommandButton id="story.world.openStyleGroup" text /><CommandButton id="story.world.remove" text /></div>
    </>
  )
}
