// D93 (C8): a Stage figure bound to a Cast character — the Inspector's character (the Cast's characters as hero tiles, "no character", a
// pinned version beside) and the Outliner's tag (who the figure is). The right-click "Bind to a character ▸" is stageCommands.ts bindItems.
import { useEffect } from 'react'
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
  const img = heroOf(p, o.version)
  return <span className="bound-tag" title={p ? `bound to ${p.name}${o.version ? ` ${o.version}` : ''} — its references and sheet go into the frame` : 'bound to a character no longer in the Cast'}>
    {img ? <img src={img} alt="" /> : <span className="glyph">{fieldGlyph('character')}</span>}{p?.name ?? 'gone'}{o.version ? ` · ${o.version}` : ''}</span>
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
      <div className="kv"><span>character</span><span className="hint">{p ? `${p.name} — its references and sheet, figure by figure, left to right` : chars.length ? 'pick who this figure is' : 'no characters in the Cast yet'}</span></div>
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
