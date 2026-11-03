// D161 → C0 (D181, Q2): the animation reference stays a World picture, picked by hand — its slots (front, back, side; a prop's view; a
// place's set picture) with the makes that queue candidates, and the candidates left in the version's bin, each picked into a slot or
// discarded. A section of World's Make (World = Make | Edit): what Clay's Library builds the body, the model and the set from.
import { X } from 'lucide-react'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'
import { markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { AnimRef } from '../../suites/story/CastParts'
import { useWorld } from './worldStore'
import '../../suites/story/story.css'

type Version = Profile['versions'][number]

/** D161: the pictures an A-pose (or a set picture) make left in the version's bin, not yet picked — each picked into a slot or discarded
 *  (its verbs are World's commands on the creation, which a button selects first). */
export function Candidates({ p, v }: { p: Profile; v: Version }) {
  const bin = useWorld((s) => s.bin)
  const picked = new Set([v.anim_ref_asset_id, v.anim_ref_back_asset_id, v.anim_ref_side_asset_id].filter(Boolean))
  const items = (bin?.items ?? []).filter((x) => x.asset.origin?.surface === 'anim_ref' && !picked.has(x.asset.id))
  const place = p.cls === 'place'
  const verbs = place ? ['world.creation.setPicture'] : p.cls === 'character' ? ['world.creation.aposeFront', 'world.creation.aposeBack', 'world.creation.aposeSide'] : ['world.creation.aposeFront']
  const run = (id: string, cmd: string) => { useWorld.getState().select(id); runCommand(cmd) }
  for (const c of [...verbs, 'world.creation.trash']) markUsed(c)
  return (
    <div className="anim-ref-cands" data-testid="anim-ref-candidates">
      <span className="hint">{items.length ? `${items.length} to pick from` : 'no candidates'}<Help text={place
        ? 'What Make set-picture candidates ▶ made: pick the set picture, or discard what is no good. Nothing is picked for you.'
        : 'What the make made: pick the front (and the back), or discard what is no good. Nothing is picked for you; picking the front of a body never touched fits the body to it, in Clay\'s Library.'} /></span>
      {items.map((it) => {
        const side = (it.asset.origin?.payload as { side?: string } | undefined)?.side
        return (
          <div key={it.asset.id} className="anim-ref-cand" data-id={it.asset.id} data-side={side ?? 'front'}
            onContextMenu={(e) => { useWorld.getState().select(it.asset.id); showMenu(e, [...verbs.map((cmd) => ({ cmd })), { sep: true }, { cmd: 'world.creation.trash', label: 'Discard' }]) }}>
            <img src={api.thumbUrl(it.asset.id, 256)} alt="" draggable={false} />
            <span className="anim-ref-cand-verbs">
              {place ? <button type="button" onClick={() => run(it.asset.id, 'world.creation.setPicture')}>Use as the set picture</button> : <>
                <button type="button" onClick={() => run(it.asset.id, 'world.creation.aposeFront')}>{p.cls === 'prop' ? 'Use' : 'Front'}</button>
                {p.cls === 'character' && <button type="button" onClick={() => run(it.asset.id, 'world.creation.aposeBack')}>Back</button>}
                {p.cls === 'character' && <button type="button" onClick={() => run(it.asset.id, 'world.creation.aposeSide')}>Side</button>}</>}
              <button type="button" className="quiet danger" aria-label="Discard" title="Discard: to the Trash" onClick={() => run(it.asset.id, 'world.creation.trash')}><X size={12} /></button>
            </span>
          </div>
        )
      })}
    </div>
  )
}

/** The reference pictures of the version: the slots and their makes (a character, a prop), or a place's set picture candidates. */
export function WorldRefs({ p, v }: { p: Profile; v: Version }) {
  if (p.cls === 'place') return <section className="anim-ref w-sheet cast-page" data-testid="world-refs"><h3>Set picture candidates <Help text="The set picture is the place empty, from eye level — what Clay's Library fits the set to. Make it with the set picture framing above; pick one here." /></h3><Candidates p={p} v={v} /></section>
  return <div className="w-sheet cast-page" data-testid="world-refs"><AnimRef p={p} v={v}><Candidates p={p} v={v} /></AnimRef></div>
}
