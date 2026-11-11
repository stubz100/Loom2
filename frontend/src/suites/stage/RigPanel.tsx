// D190 (proto01_rig 00 §15): the skeleton panel — Clay's Library column while a character is on Skeleton (its Figure | Skeleton switch).
// The part (Body · Hands · Feet & legs) is switched here. For the hands and the feet the panel holds the picture in use, the pictures to pick
// it from — those made as one first, then the A-pose views and the rest of the version's pictures; nothing is picked for the author — and the
// make: the picture's own words, a model card (any text-to-image model of the build, the clay-reference model first: E62 measured Klein 9B's
// clean close-up), how many. The viewport keeps the points and the 3D; the Inspector the numbers.
import { useEffect, useMemo, useState } from 'react'
import { api, http, unwrap } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { ModelCards } from '../../frame/ModelCards'
import { defaultFirstItems, imageModelItems } from '../../frame/modelCardItems'
import { onRecords } from '../../store/records'
import { useSession } from '../../store/session'
import { sheetWords } from '../../ui2/world/refWords'
import { partRead } from '../story/partRead'
import { useStory } from '../story/storyStore'
import { setUi, useUi } from './benchState'
import { picturesFor, type BinItem, type Part } from './rigPictures'

type Version = Profile['versions'][number]
const ON_THE_WAY = ['queued', 'running', 'staged'] as string[]

/** The version's pictures (its bin), read again when a creation lands, moves or goes. */
function useVersionBin(pid: string, vid: string): BinItem[] | null {
  const key = `${pid}/${vid}`
  const [bin, setBin] = useState<{ key: string; items: BinItem[] } | null>(null)
  useEffect(() => {
    let live = true
    const load = () => void unwrap(http.GET('/story/profiles/{pid}/versions/{vid}/bin', { params: { path: { pid, vid } } }))
      .then((b) => { if (live) setBin({ key, items: b.items }) }).catch(() => undefined)
    load()
    const off = onRecords('rig.panel.bin', ['group.changed', 'asset.deleted', 'asset.updated'], load)
    return () => { live = false; off() }
  }, [key, pid, vid])
  return bin?.key === key ? bin.items : null
}

const VIEW_LABEL = (v: Version, id: string) => (id === v.anim_ref_side_asset_id ? 'side view' : id === v.anim_ref_back_asset_id ? 'back view' : id === v.anim_ref_asset_id ? 'A-pose' : '')

export default function RigPanel() {
  const p = useStory((s) => s.profile())
  const v = useStory((s) => s.version())
  const u = useUi()
  if (!p || !v || p.cls !== 'character') return null
  return (
    <div className="rig-panel" data-testid="rig-panel">
      <div className="segmented rig-parts" role="group" aria-label="the part" data-testid="rig-parts">{/* RG3's parts, in the panel (D190) */}
        <CommandButton id="cast.rig.body" text size={13} active={u.part === 'body'} /><CommandButton id="cast.rig.hands" text size={13} active={u.part === 'hands'} /><CommandButton id="cast.rig.feet" text size={13} active={u.part === 'feet'} />
      </div>
      {u.part === 'body' ? <BodyRefs v={v} /> : <PartPicture key={`${u.part}/${p.id}/${v.id}`} p={p} v={v} part={u.part === 'hands' ? 'hand' : 'feet'} />}
    </div>
  )
}

/** The body: the A-pose it is fitted to (picked in World), the fit and the shell. */
function BodyRefs({ v }: { v: Version }) {
  const views = [['A-pose', v.anim_ref_asset_id], ['back view', v.anim_ref_back_asset_id], ['side view', v.anim_ref_side_asset_id]] as const
  return (
    <section className="rig-sec" data-testid="rig-body-refs">
      <h4>The reference <Help text="The skeleton is fitted to the A-pose picked in World (its back view shows the other side); the shell is made from it. The A-pose is made and picked in World › Make." /></h4>
      <div className="rig-thumbs">{views.filter(([, id]) => !!id).map(([label, id]) => <span key={label} className="rig-thumb still" title={label}><img src={api.thumbUrl(id!, 256)} alt={label} draggable={false} /><small>{label}</small></span>)}
        {!v.anim_ref_asset_id && <span className="hint">no A-pose picked</span>}</div>
      <div className="w-verbs"><CommandButton id="story.cast.fitBody" text /><CommandButton id="cast.shell.make" text /></div>
    </section>
  )
}

/** A hand or the feet: the picture in use and its read, the pictures to pick it from, the make. */
function PartPicture({ p, v, part }: { p: Profile; v: Version; part: Part }) {
  const jobs = useSession((s) => s.jobs)
  const items = useVersionBin(p.id, v.id)
  const [more, setMore] = useState(false)
  const cur = (part === 'hand' ? v.hand_ref_asset_id : v.feet_ref_asset_id) ?? null
  const read = partRead(v, part, jobs, p.id)
  const groups = useMemo(() => (items ? picturesFor(items, v, part) : null), [items, v, part])
  const making = Object.values(jobs).filter((j) => j.origin?.surface === 'anim_ref' && j.origin.ref === p.id && ON_THE_WAY.includes(j.status)
    && (j.origin.payload as { version?: string; side?: string } | null)?.version === v.id && (j.origin.payload as { side?: string } | null)?.side === part).length
  const what = part === 'hand' ? 'hand' : 'feet'
  const pick = (id: string) => void useStory.getState().setAnimRef(part, id)
  const discard = (id: string) => void unwrap(http.POST('/assets/trash', { body: { ids: [id] } })).catch((e) => useSession.getState().toast(`Discard: ${(e as { detail?: string }).detail ?? e}`, 'error'))
  const thumb = (it: BinItem) => {
    const id = it.asset.id, on = id === cur, label = VIEW_LABEL(v, id)
    return (
      <button key={id} type="button" className={`rig-thumb${on ? ' picked' : ''}`} data-id={id} aria-pressed={on}
        title={on ? `the ${what} picture in use` : `Use as the ${what} picture — it is read at once`} onClick={() => { if (!on) pick(id) }}
        onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ label: `Use as the ${what} picture`, run: () => pick(id), disabled: on }, { sep: true },
          { label: 'Discard', danger: true, disabled: on || it.roles.includes('hero') || !!label, run: () => discard(id) }]) }}>
        <img src={api.thumbUrl(id, 256)} alt="" draggable={false} />{label && <small>{label}</small>}
      </button>
    )
  }
  return (
    <>
      <section className="rig-sec" data-testid={`rig-${part}-pick`}>
        <h4>The {what} picture <Help text={part === 'hand'
          ? 'The picture the hand is read from: a hand alone, palm to the camera. Click one below to use it — it is read at once (SDPose, a few seconds) and its points show in the viewport to correct. Nothing is picked for you.'
          : 'The picture the feet are read from: the feet and shoes from the side — or the A-pose side view, read as the whole figure. Click one below to use it; it is read at once. Nothing is picked for you.'} /></h4>
        <div className="rig-current">
          {cur ? <img src={api.thumbUrl(cur, 256)} alt={`the ${what} picture`} /> : <span className="rig-none-pic hint">none picked</span>}
          <div className="rig-current-side">
            <span className={`hint${read.state === 'failed' ? ' warn' : ''}`} data-read={read.state} title={read.note ?? ''}>{cur ? read.text : `no ${what} picture`}</span>
            <div className="w-verbs"><CommandButton id={part === 'hand' ? 'story.cast.readHand' : 'story.cast.readFeet'} text size={12} /><CommandButton id={part === 'hand' ? 'story.cast.clearHandRef' : 'story.cast.clearFeetRef'} text size={12} label="Clear" /></div>
          </div>
        </div>
        <div className="rig-thumbs" data-testid={`rig-${part}-candidates`}>
          {groups ? [...groups.made, ...groups.views].map(thumb) : null}
          {making > 0 && <span className="rig-thumb making hint">{making} on the way…</span>}
          {groups && !groups.made.length && !groups.views.length && !making && <span className="hint">none made yet</span>}
        </div>
        {!!groups?.others.length && <button type="button" className="link" onClick={() => setMore(!more)}>{more ? 'fewer pictures' : `${p.name}'s other pictures (${groups.others.length})`}</button>}
        {more && groups && <div className="rig-thumbs">{groups.others.map(thumb)}</div>}
      </section>
      <PartMake v={v} part={part} />
    </>
  )
}

/** The make: the picture's own words (blank: the sheet's about the hands or the feet, greyed), the model card, how many. */
function PartMake({ v, part }: { v: Version; part: Part }) {
  const u = useUi()
  const caps = useSession((s) => s.capabilities)
  const def = caps?.story?.model_id ?? null
  const items = useMemo(() => defaultFirstItems(imageModelItems(caps, (c) => !!c.recipes.t2i), def), [caps, def])
  const model = u.partModel && items.some((m) => m.id === u.partModel && !m.off) ? u.partModel : def
  const secs = useEstimate(model)
  const field = part === 'hand' ? 'hand_words' : 'feet_words'
  const open = v.state === 'open'
  const fromSheet = sheetWords(v.appearance, v.outfit, v.marks, part)
  const total = secs != null ? secs * u.partCount : null
  const what = part === 'hand' ? 'hand' : 'feet'
  return (
    <section className="rig-sec" data-testid={`rig-${part}-make`}>
      <h4>Make candidates <Help text={`Pictures of the ${what} alone, square, from the words below — the sheet and the references are not sent (they draw the whole person, E62). They land above, to pick from.`} /></h4>
      <label className="w-field"><span>words <Help text={part === 'hand' ? "The hand's own words: the skin, the fingers, the nails or claws, rings, gloves. Blank: the sheet's words about the hands, greyed." : "The feet's own words: the shoes or boots, the heels, the hems, bare feet. Blank: the sheet's words about the feet, greyed."} /></span>
        <textarea rows={2} value={v[field] ?? ''} aria-label={`${part} words`} disabled={!open} placeholder={fromSheet || (part === 'hand' ? 'long bony grey fingers with black claws' : 'black riding boots with a 5 cm heel')}
          onChange={(e) => useStory.getState().setSheet({ [field]: e.target.value })} /></label>
      <div className="w-field"><span>model <Help text="Any text-to-image model of this build: the picture is made from its words alone. Klein 9B, first, drew the clean close-up E62 measured (about 20 s a picture)." /></span>
        <ModelCards label={`${what} picture model`} testId="rig-models" items={items} value={model} onPick={(id) => setUi({ partModel: id === def ? null : id })} /></div>
      <div className="kv"><span>how many</span><span className="segmented" role="group" aria-label="how many pictures">{[1, 2, 3, 4].map((n) =>
        <button key={n} type="button" className={u.partCount === n ? 'active' : ''} aria-pressed={u.partCount === n} onClick={() => setUi({ partCount: n })}>{n}</button>)}</span></div>
      <div className="w-verbs"><CommandButton id="cast.rig.make" text label={`Make ${u.partCount} ${what} picture${u.partCount === 1 ? '' : 's'} ▶${total ? ` ≈ ${total < 90 ? `${Math.round(total)} s` : `${Math.round(total / 60)} min`}` : ''}`} /></div>
    </section>
  )
}

/** The model's time for one square picture, as the Make column estimates it (the recipe's preview); null while unknown. */
function useEstimate(model: string | null): number | null {
  const [got, setGot] = useState<{ model: string; secs: number | null } | null>(null)
  useEffect(() => {
    if (!model) return
    let live = true
    const recipe = { kind: 't2i', model_id: model, prompt_mode: 'text', prompt_text: 'a hand', width: 1024, height: 1024, seeds: [0], tier: 'draft' }
    void unwrap(http.POST('/recipes/preview', { body: { recipe: recipe as never } }))
      .then((pv) => { if (live) setGot({ model, secs: (pv as { estimate?: { seconds?: number | null } }).estimate?.seconds ?? null }) })
      .catch(() => { if (live) setGot({ model, secs: null }) })
    return () => { live = false }
  }, [model])
  return got && got.model === model ? got.secs : null
}
