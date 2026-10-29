// D161 (the author, 2026-10-29): World's Build — what Clay needs of the entity version, beside its bin (its words and the pictures made
// from them are Make's): the animation reference (front, back) with its test animation and the A-pose candidates to pick from or discard,
// a character's body (height, build, attachments, the figure's sliders, ♀ / ♂, hands at rest) with its fit, skeleton and shell, a prop's 3D
// model turning with its height, a place's set picture candidates and its set builder, and the Line-up of the class at their sizes in Clay.
// A make fills no slot: its pictures are candidates until the author picks.
import { X } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { AnimRef, PropModel } from '../../suites/story/CastParts'
import { CastBody } from '../../suites/story/CastBody'
import { useStory } from '../../suites/story/storyStore'
import { useWorld } from './worldStore'
import '../../suites/story/story.css'

const PlaceSetSection = lazy(() => import('../../suites/story/CastSet').then((m) => ({ default: m.PlaceSetSection })))   // CW6: three.js only for a place

type Version = Profile['versions'][number]

/** D161: the pictures an A-pose (or a set picture) make left in the version's bin, not yet picked — each picked into a slot or discarded
 *  (its verbs are World's commands on the creation, which a button selects first). */
function Candidates({ p, v }: { p: Profile; v: Version }) {
  const bin = useWorld((s) => s.bin)
  const picked = new Set([v.anim_ref_asset_id, v.anim_ref_back_asset_id].filter(Boolean))
  const items = (bin?.items ?? []).filter((x) => x.asset.origin?.surface === 'anim_ref' && !picked.has(x.asset.id))
  const place = p.cls === 'place'
  const verbs = place ? ['world.creation.setPicture'] : p.cls === 'character' ? ['world.creation.aposeFront', 'world.creation.aposeBack'] : ['world.creation.aposeFront']
  const run = (id: string, cmd: string) => { useWorld.getState().select(id); runCommand(cmd) }
  for (const c of [...verbs, 'world.creation.trash']) markUsed(c)
  return (
    <div className="anim-ref-cands" data-testid="anim-ref-candidates">
      <span className="hint">{items.length ? `${items.length} to pick from` : 'no candidates'}<Help text={place
        ? 'What Make set-picture candidates ▶ made: pick the set picture, or discard what is no good. Nothing is picked for you.'
        : 'What the make made: pick the front (and the back), or discard what is no good. Nothing is picked for you; picking the front of a body never touched fits the body to it.'} /></span>
      {items.map((it) => {
        const side = (it.asset.origin?.payload as { side?: string } | undefined)?.side
        return (
          <div key={it.asset.id} className="anim-ref-cand" data-id={it.asset.id} data-side={side ?? 'front'}
            onContextMenu={(e) => { useWorld.getState().select(it.asset.id); showMenu(e, [...verbs.map((cmd) => ({ cmd })), { sep: true }, { cmd: 'world.creation.trash', label: 'Discard' }]) }}>
            <img src={api.thumbUrl(it.asset.id, 256)} alt="" draggable={false} />
            <span className="anim-ref-cand-verbs">
              {place ? <button type="button" onClick={() => run(it.asset.id, 'world.creation.setPicture')}>Use as the set picture</button> : <>
                <button type="button" onClick={() => run(it.asset.id, 'world.creation.aposeFront')}>{p.cls === 'prop' ? 'Use' : 'Front'}</button>
                {p.cls === 'character' && <button type="button" onClick={() => run(it.asset.id, 'world.creation.aposeBack')}>Back</button>}</>}
              <button type="button" className="quiet danger" aria-label="Discard" title="Discard: to the Trash" onClick={() => run(it.asset.id, 'world.creation.trash')}><X size={12} /></button>
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function WorldBuild() {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  if (!p) return <div className="w-empty">Pick or make one in the header.</div>
  const v = p.versions.find((x) => x.id === (vid ?? p.current)) ?? p.versions[0]
  return (
    <div className="w-sheet cast-page" data-testid="world-build">
      {(p.cls === 'character' || p.cls === 'prop') && <AnimRef p={p} v={v}><Candidates p={p} v={v} /></AnimRef>}
      {p.cls === 'character' && <section className="w-build-body"><h3>Body</h3><CastBody p={p} v={v} /><div className="w-verbs"><CommandButton id="cast.shell.make" text /></div></section>}
      {p.cls === 'prop' && <PropModel p={p} v={v} />}
      {p.cls === 'place' && <section className="anim-ref"><h3>Set picture candidates</h3><Candidates p={p} v={v} /></section>}{/* the make is the set builder's (Make set-picture candidates ▶) */}
      {p.cls === 'place' && <Suspense fallback={<section className="place-set" />}><PlaceSetSection p={p} v={v} /></Suspense>}
      {p.cls !== 'place' && <div className="w-verbs"><CommandButton id="world.lineup" text /></div>}
    </div>
  )
}
