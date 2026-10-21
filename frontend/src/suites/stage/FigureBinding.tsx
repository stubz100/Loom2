// D93 (C8): a Stage figure bound to a Cast character — the Inspector's character (the Cast's characters as hero tiles, "no character", a
// pinned version beside) and the Outliner's tag (who the figure is). The right-click "Bind to a character ▸" is stageCommands.ts bindItems.
import { useEffect } from 'react'
import { Help } from '../../frame/Help'
import { api } from '../../api/client'
import type { Profile, StageObject } from '../../api/types'
import { CommandRow } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { PresetIcons, type PresetIcon } from '../../frame/PresetIcons'
import { fieldGlyph } from '../../frame/presetGlyphs'
import { profilesForMentions, useStory } from '../story/storyStore'
import { st } from './stageStore'

/** D93 (C8): the hero of the version a figure wears, as a thumbnail URL. */
function heroOf(p: Profile | undefined, vid?: string | null): string | null {
  const v = p?.versions.find((x) => x.id === (vid && p.versions.some((y) => y.id === vid) ? vid : p.current))
  return v?.hero_asset_id ? api.thumbUrl(v.hero_asset_id, 256) : null
}

/** D93 (C8): the character a figure is bound to, on its Outliner row — the hero and the name (and the version when pinned). */
export function BoundTag({ o }: { o: StageObject }) {
  const p = useStory((x) => x.profiles.find((y) => y.id === o.profile_id))
  const prop = o.kind === 'mesh'                                                    // D110 (PS3): a mesh bound to a Cast prop
  const img = prop ? (p ? propThumb(p, o.version) : null) : heroOf(p, o.version)
  return <span className="bound-tag" title={p ? `bound to ${p.name}${o.version ? ` ${o.version}` : ''} — ${prop ? 'its 3D model follows the version' : 'its references and sheet go into the frame'}` : `bound to a ${prop ? 'prop' : 'character'} no longer in Story`}>
    {img ? <img src={img} alt="" /> : <span className="glyph">{fieldGlyph(prop ? 'prop' : 'character')}</span>}{p?.name ?? 'gone'}{o.version ? ` · ${o.version}` : ''}</span>
}

/** D93 (C8): the Inspector's character of a figure — the Cast's characters as hero tiles and "none"; a pinned version (a costume) beside. */
export function FigureCharacter({ o }: { o: StageObject }) {
  const profiles = useStory((x) => x.profiles)
  const loaded = useStory((x) => x.profilesLoaded)
  useEffect(() => { if (!loaded) profilesForMentions() }, [loaded])
  const chars = profiles.filter((p) => p.cls === 'character')
  const p = o.profile_id ? profiles.find((x) => x.id === o.profile_id) : undefined
  const items: PresetIcon[] = [...chars.map((c): PresetIcon => ({ id: c.id, label: c.name, hint: `${c.current} — its reference images and sheet go into this figure's place in the frame`, icon: fieldGlyph('character'), img: heroOf(c) })),
    { id: NONE, label: 'no character', hint: 'a grey figure the prompt describes', icon: fieldGlyph('free') }]
  return (
    <>
      <div className="kv"><span>character</span><span className="hint">{p ? p.name : chars.length ? 'pick who this figure is' : 'no characters in the Cast yet'}{p && <Help text="Its reference images and sheet go into the frame, figure by figure, left to right." />}</span></div>
      <PresetIcons label="the figure's character" size={40} items={items} selected={o.profile_id ?? NONE} onPick={(id) => st().bindFigure(o.id, id === NONE ? null : id)}
        onContext={(id, e) => { if (id === NONE) return; useStory.getState().selectProfile(id); showMenu(e, [{ cmd: 'story.cast.openInStory' }]) }} />
      {p && p.versions.length > 1 && <div className="kv"><span>version</span><select value={o.version ?? ''} aria-label="the character's version" onChange={(e) => st().bindFigure(o.id, p.id, e.target.value || null)}>
        <option value="">current ({p.current})</option>{p.versions.map((v) => <option key={v.id} value={v.id}>{v.label && v.label !== v.id ? `${v.id} · ${v.label}` : v.id}</option>)}</select></div>}
      {p && <div className="kv"><span>body</span><span className="hint">{o.body
        ? `from Cast — ${o.body.height_m.toFixed(2)} m · ${o.body.build}${o.body.attachments.length ? ` · ${o.body.attachments.map((a) => a.kind).join(', ')}` : ''}`
        : 'the default dummy (no body on the Cast sheet)'}</span></div>}{/* CA0: the sheet's body shapes this figure */}
      {p && <div className="verbs"><CommandRow ids={['stage.figure.unbind', 'stage.figure.openInCast']} /></div>}
    </>
  )
}
const NONE = '__none'

// ---- D110 (PS3): props from Story · Props — a mesh bound to a Cast prop, its version's 3D model following ----------------------------
/** The picture of a prop version: its model's view, else its hero. */
function propThumb(p: Profile, vid?: string | null): string | null {
  const v = p.versions.find((x) => x.id === (vid && p.versions.some((y) => y.id === vid) ? vid : p.current))
  const id = v?.model_asset_id ?? v?.hero_asset_id
  return id ? api.thumbUrl(id, 256) : null
}
const openProp = (id: string) => void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id }))   // a prop opens on Props

/** Animate's library: the Cast props, each placed (its 3D model, bound to the prop) at the viewport's centre with a click; one without a
 *  model yet opens in Story · Props to make it. */
export function LibraryProps({ centre }: { centre: () => number[] }) {
  const profiles = useStory((x) => x.profiles)
  const loaded = useStory((x) => x.profilesLoaded)
  useEffect(() => { if (!loaded) profilesForMentions() }, [loaded])
  const props = profiles.filter((p) => p.cls === 'prop')
  if (!props.length) return <span className="hint">None yet. <Help text="Make one in Story · Props: its images first, then its 3D model." /></span>
  return (
    <div className="lib-grid">{props.map((p) => {
      const model = p.versions.find((v) => v.id === p.current)?.model_asset_id
      const img = propThumb(p)
      const place = () => { if (model) st().placeProp(p.id, centre()); else openProp(p.id) }
      return (
        <button key={p.id} className={`mesh-card prop-card${model ? '' : ' no-model'}`} data-id={p.id}
          title={model ? `${p.name} — place its 3D model at the viewport's centre (bound to the prop: its version's model follows)` : `${p.name} has no 3D model yet — open it in Story · Props to make one`}
          onClick={place}
          onContextMenu={(e) => { e.preventDefault(); showMenu(e, [{ label: 'Place in the scene', run: place, disabled: !model }, { label: 'Open in Story · Props', run: () => openProp(p.id) }]) }}>
          {img ? <img src={img} alt="" /> : <span className="glyph">{fieldGlyph('prop')}</span>}<span>{p.name}{model ? '' : ' · no model'}</span>
        </button>
      )
    })}</div>
  )
}

/** The Inspector's prop of a mesh: the Cast props with a model as tiles and "no prop"; a pinned version beside. */
export function MeshProp({ o }: { o: StageObject }) {
  const profiles = useStory((x) => x.profiles)
  const loaded = useStory((x) => x.profilesLoaded)
  useEffect(() => { if (!loaded) profilesForMentions() }, [loaded])
  const props = profiles.filter((p) => p.cls === 'prop' && p.versions.some((v) => v.model_asset_id))
  const p = o.profile_id ? profiles.find((x) => x.id === o.profile_id) : undefined
  const ver = p?.versions.find((v) => v.id === (o.version ?? p.current))
  const items: PresetIcon[] = [...props.map((c): PresetIcon => ({ id: c.id, label: c.name, hint: `${c.current} — its 3D model, made in Story · Props`, icon: fieldGlyph('prop'), img: propThumb(c) })),
    { id: NONE, label: 'no prop', hint: 'a mesh of its own, not a Cast prop', icon: fieldGlyph('free') }]
  return (
    <>
      <div className="kv"><span>prop</span><span className="hint">{p ? `${p.name} — ${ver?.model_asset_id ? 'its version\'s 3D model follows' : 'this version has no 3D model yet (the mesh stays)'}` : props.length ? 'bind it to a Cast prop' : 'no props with a 3D model yet'}</span></div>
      <PresetIcons label="the mesh's prop" size={40} items={items} selected={o.profile_id ?? NONE} onPick={(id) => st().bindProp(o.id, id === NONE ? null : id)}
        onContext={(id, e) => { if (id !== NONE) showMenu(e, [{ label: 'Open in Story · Props', run: () => openProp(id) }]) }} />
      {p && p.versions.length > 1 && <div className="kv"><span>version</span><select value={o.version ?? ''} aria-label="the prop's version" onChange={(e) => st().bindProp(o.id, p.id, e.target.value || null)}>
        <option value="">current ({p.current})</option>{p.versions.map((v) => <option key={v.id} value={v.id}>{v.label && v.label !== v.id ? `${v.id} · ${v.label}` : v.id}{v.model_asset_id ? '' : ' (no model)'}</option>)}</select></div>}
      {p && <div className="verbs"><button className="quiet" onClick={() => openProp(p.id)} title="Open the prop in Story · Props">Open in Story · Props</button></div>}
    </>
  )
}
