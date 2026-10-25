// proto01_UIcast CW1–CW2 (D136 U1–U4; 06 §2.1–2.2; 02 §3–5): Cast's Ideas board — the panel's list beside the kept profiles (one
// class switch for both), the idea's bench in the Stage (its variants, the one in focus, its clay, what Image made for it) and its
// Inspector. Ideas stay out of production: no @mention, no place in Flow's pickers or Shots. Every verb is a registry command
// (storyCommands.ts: story.idea.*) or a menu entry; a picture dropped on a row is a variant, on the list a new idea.
import { useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { markUsed, sep, type MenuItem } from '../../frame/commands'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { Help } from '../../frame/Help'
import { clayWords, focusOf, useIdeas, type Idea, type IdeaVariant } from './ideasStore'
import { ideaMenu } from './ideaVerbs'
import { addToIdea, newIdeaFrom } from './prototype'
import { CLASS_LABEL, useStory, type ProfileClass } from './storyStore'

const ideas = () => useIdeas.getState()
const imageIds = (p: Parameters<typeof onlyAssets>[0]) => p.items.filter((i) => i.kind === 'asset' && i.media !== 'video' && i.media !== 'mesh').map((i) => i.id)

/** A variant's right-click on the bench's strip. */
function variantMenu(i: Idea, v: IdeaVariant): MenuItem[] {
  return [
    { label: 'Put in focus', run: () => void ideas().patch(i.id, { focus: v.id }) },
    ...(i.cls === 'character' ? [{ label: 'Make the clay ▶', run: () => void ideas().makeClay(i.id, v.id) }] : []),
    { label: `Keep ▶ as a new ${CLASS_LABEL[i.cls]}`, run: () => void ideas().keep(i.id, v.id) },
    sep, { label: 'Remove from the idea', run: () => void ideas().removeVariant(i.id, v.id) },
  ]
}

// ------------------------------------------------------------------ Panel · the board
function IdeaRow({ i, active, picked }: { i: Idea; active: boolean; picked: boolean }) {
  const v = focusOf(i)
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && imageIds(p).length > 0, (p) => void addToIdea(i.id, imageIds(p)), (p) => ({ ok: true, label: `Add ${imageIds(p).length > 1 ? `${imageIds(p).length} variants` : 'a variant'} to ${i.name}` }))
  return (
    <button ref={ref} className={`story-row profile-row idea-row${active ? ' active' : ''}${picked ? ' picked' : ''}${over ? ' drop-over' : ''}`} role="listitem" data-id={i.id} aria-pressed={picked}
      onClick={(e) => (e.ctrlKey || e.metaKey ? ideas().togglePick(i.id) : ideas().select(i.id))} onContextMenu={(e) => { ideas().select(i.id); showMenu(e, ideaMenu(i)) }}>
      {v ? <img className="pthumb" src={api.thumbUrl(v.asset_id, 256)} alt="" /> : <span className="pthumb empty" />}
      <span className="pname">{i.name}<span className="muted"> · {CLASS_LABEL[i.cls]} idea</span>
        <span className="owes">{i.variants.length} variant{i.variants.length === 1 ? '' : 's'}{v?.clay ? ` · ${clayWords(v)}` : ''}</span></span>
      <span className="n">{picked ? <span title="picked for the line-up">☑</span> : null}{i.kept.length ? <span title="kept in Cast">kept ✓</span> : null}</span>
    </button>
  )
}

/** The Ideas board: the class switch's ideas (search by name); a picture dropped on the list starts an idea of that class. */
export function IdeasList({ filter, q }: { filter: 'all' | ProfileClass; q: string }) {
  const list = useIdeas((s) => s.ideas)
  const loaded = useIdeas((s) => s.loaded)
  const ideaId = useIdeas((s) => s.ideaId)
  const picked = useIdeas((s) => s.picked)
  useEffect(() => { if (!ideas().loaded) void ideas().load() }, [])
  const cls: ProfileClass = filter === 'all' ? 'character' : filter
  const { ref, over } = useDropTarget((p) => onlyAssets(p) && imageIds(p).length > 0, (p) => void newIdeaFrom(cls, imageIds(p)), () => ({ ok: true, label: `A new ${cls} idea` }))
  const shown = list.filter((i) => (filter === 'all' || i.cls === filter) && (!q || i.name.toLowerCase().includes(q)))
  markUsed('story.idea.new'); markUsed('story.idea.lineup')
  return (
    <>
      <div ref={ref} className={`story-list${over ? ' drop-over' : ''}`} role="list" aria-label="ideas">
        {shown.map((i) => <IdeaRow key={i.id} i={i} active={ideaId === i.id} picked={picked.includes(i.id)} />)}
        {!shown.length && <div className="empty hint">{!loaded ? 'loading…' : list.length ? 'No idea matches.' : 'No ideas yet — Prototype ▸ on any picture, or drop pictures here'}</div>}
      </div>
      <div className="verbs"><CommandButton id="story.idea.new" text /><CommandButton id="story.idea.lineup" text />
        {picked.length > 0 && <button type="button" className="quiet" onClick={() => useIdeas.setState({ picked: [] })} title="Clear the ideas picked for the line-up">{picked.length} picked ✕</button>}
        <Help text="Ctrl-click ideas to pick several for the line-up; without a pick it lines up those shown that have their clay." /></div>
    </>
  )
}

// ------------------------------------------------------------------ Stage · the idea's bench
function Variant({ i, v }: { i: Idea; v: IdeaVariant }) {
  const focus = i.focus === v.id
  return (
    <button type="button" role="listitem" className={`cand-card variant-card${focus ? ' picked' : ''}`} data-id={v.id} onClick={() => void ideas().patch(i.id, { focus: v.id })}
      onContextMenu={(e) => showMenu(e, variantMenu(i, v))} title={v.made_from.prompt || 'a picture'}>
      <img src={api.thumbUrl(v.asset_id, 256)} alt="" />
      <span className="cell">{v.clay ? clayWords(v) : v.note || (v.made_from.seed != null ? `seed ${v.made_from.seed}` : 'a picture')}</span>
    </button>
  )
}

function Clay({ i, v }: { i: Idea; v: IdeaVariant }) {
  const c = v.clay
  if (c?.model_asset_id) return (                                                                    // CW3: a prop's model (Prototype ▸ on a mesh in Clay)
    <div className="idea-clay" data-step={c.step}>
      <img className="aref" src={api.thumbUrl(c.model_asset_id, 256)} alt="the model" />
      <div className="kv"><span>model</span><span>from Clay</span><span>height</span><span>{c.height_m ? `${c.height_m.toFixed(2)} m` : 'its own size'}</span></div>
    </div>
  )
  if (i.cls !== 'character') return <span className="hint">A {CLASS_LABEL[i.cls]}'s clay: Prototype ▸ on a mesh in Clay, or Keep ▶ then its 3D model in Cast{i.cls === 'place' ? ' (places get their set builder later)' : ''}.</span>
  if (!c) return <span className="hint">no clay yet</span>
  const pts = ((c.body_points as { pose?: unknown[] } | null)?.pose ?? []).length
  return (
    <div className="idea-clay" data-step={c.step}>
      {c.anim_ref_asset_id && <img className="aref" src={api.thumbUrl(c.anim_ref_asset_id, 256)} alt="the A-pose picture" title="the A-pose picture drawn from the variant" />}
      <div className="kv">
        <span>state</span><span className={c.step === 'failed' ? 'warn' : ''}>{clayWords(v)}</span>
        <span>body</span><span>{c.body ? `fitted · ${c.body.height_m.toFixed(2)} m · ${pts} points` : '—'}</span>
        <span>shell</span><span>{c.shell_asset_id ? 'made (Pixal3D)' : c.step === 'shell' ? 'in the background…' : '—'}</span>
      </div>
      {c.shell_asset_id && <img className="aref" src={api.thumbUrl(c.shell_asset_id, 256)} alt="the shell" title="the shell, made from the A-pose picture" />}
    </div>
  )
}

function MadeFor({ i }: { i: Idea }) {
  const kept = new Set(i.variants.map((v) => v.made_from.asset_id))
  if (!i.made_for.length) return <span className="hint">nothing yet — Explore in Image makes for it</span>
  return (
    <div className="story-cands" role="list" aria-label="made for this idea">
      {i.made_for.map((id) => (
        <div key={id} role="listitem" className="cand-card made-card" data-id={id}
          onContextMenu={(e) => showMenu(e, [{ label: 'Add as a variant', run: () => void ideas().addVariant(i.id, id) }])}>
          <img src={api.thumbUrl(id, 256)} alt="" />
          <span className="cell">{kept.has(id) ? 'a variant ✓' : 'made for it'}</span>
          {!kept.has(id) && <span className="tools"><button type="button" className="quiet" title="Add as a variant (a copy on the idea's page)" onClick={() => void ideas().addVariant(i.id, id)}>＋ variant</button></span>}
        </div>
      ))}
    </div>
  )
}

export function IdeaBench() {
  const i = useIdeas((s) => s.ideas.find((x) => x.id === s.ideaId))
  const profiles = useStory((s) => s.profiles)
  markUsed('story.idea.explore'); markUsed('story.idea.clay'); markUsed('story.idea.keep'); markUsed('story.idea.rename'); markUsed('story.idea.delete')
  const { ref, over } = useDropTarget((p) => !!i && onlyAssets(p) && imageIds(p).length > 0, (p) => { if (i) void addToIdea(i.id, imageIds(p)) }, (p) => ({ ok: true, label: `Add ${imageIds(p).length > 1 ? `${imageIds(p).length} variants` : 'a variant'}` }))
  if (!i) return <div className="story-empty"><div>Pick an idea on the left, or start one: <b>Prototype ▸</b> on any picture in Image or the Catalogue copies it into a new idea; nothing in an idea is production until <b>Keep ▶</b>.<div className="quick-cards"><CommandButton id="story.idea.new" text /></div></div></div>
  const v = focusOf(i)
  const kept = i.kept.map((k) => ({ k, p: profiles.find((p) => p.id === k.profile_id) }))
  return (
    <div ref={ref} className={`cast-page idea-bench${over ? ' drop-over' : ''}`} data-idea={i.id}>
      <div className="cast-head">
        <div className="hero-card" onContextMenu={(e) => showMenu(e, ideaMenu(i))}>{v ? <img src={api.thumbUrl(v.asset_id, 512)} alt="" /> : <span className="hint">no picture yet — drop one here</span>}</div>
        <div className="cast-fields">
          <h2>{i.name} <span className="muted">— {CLASS_LABEL[i.cls]} idea — {i.variants.length} variant{i.variants.length === 1 ? '' : 's'}</span></h2>
          {v && <div className="kv made-from">
            <span>prompt</span><span className="prompt" title={v.made_from.prompt}>{v.made_from.prompt || '—'}</span>
            <span>model</span><span>{v.made_from.model ?? '—'}{v.made_from.seed != null ? ` · seed ${v.made_from.seed}` : ''}</span>
          </div>}
          <div className="verbs">
            {i.cls === 'character' && <CommandButton id="story.idea.clay" text />}
            <CommandButton id="story.idea.keep" text label={`Keep ▶ as a new ${CLASS_LABEL[i.cls]}`} />
            <button type="button" className="quiet" disabled={!v} onClick={(e) => showMenu(e, ideaMenu(i).filter((m) => 'items' in m))} title="This variant as a new version of a Cast profile of its class">Keep as a new version ▾</button>
            <CommandButton id="story.idea.explore" text />
          </div>
          {kept.length > 0 && <div className="kept">kept as {kept.map(({ k, p }) => <button key={`${k.profile_id}${k.version_id}`} type="button" className="link" data-id={k.profile_id}
            onClick={() => { useIdeas.setState({ board: 'cast' }); useStory.getState().selectProfile(k.profile_id, k.version_id) }}>{p?.name ?? 'a deleted profile'} {k.version_id}</button>)}</div>}
        </div>
      </div>
      <section>
        <h3>Variants <Help text={"The pictures the idea gathered — copies, so their own pages keep them. A click puts one in focus; its right-click makes its clay, keeps it or removes it. Drop pictures here to add them."} /></h3>
        <div className="story-cands" role="list" aria-label="variants">{i.variants.map((x) => <Variant key={x.id} i={i} v={x} />)}</div>
      </section>
      <section>
        <h3>Clay <Help text={"Make the clay ▶ draws the variant in the A-pose, fits the body to it (about a minute), then makes its shell in the background (minutes). Keep ▶ takes the clay into Cast: the A-pose picture as the animation reference, the body, the shell."} /></h3>
        {v ? <Clay i={i} v={v} /> : <span className="hint">no variant yet</span>}
      </section>
      <section>
        <h3>Made for this idea <Help text={"What Image made while its For chip named this idea (Explore in Image), newest first. Nothing becomes a variant by itself: ＋ variant takes one."} /></h3>
        <MadeFor i={i} />
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Inspector
export function IdeaInspector() {
  const i = useIdeas((s) => s.ideas.find((x) => x.id === s.ideaId))
  if (!i) return <span className="hint">Nothing selected.</span>
  const v = focusOf(i)
  return (
    <div className="story-insp idea-insp">
      <h4>{i.name}</h4>
      <div className="kv">
        <span>name</span><input aria-label="idea name" defaultValue={i.name} key={`n${i.revision}`} maxLength={80} onBlur={(e) => { const n = e.target.value.trim(); if (n && n !== i.name) void ideas().patch(i.id, { name: n }) }} />
        <span>class</span><select aria-label="idea class" value={i.cls} onChange={(e) => void ideas().patch(i.id, { cls: e.target.value as ProfileClass })}>{(['character', 'prop', 'place'] as const).map((c) => <option key={c} value={c}>{c}</option>)}</select>
        <span>note</span><textarea aria-label="idea note" defaultValue={i.note} key={`t${i.revision}`} maxLength={1000} rows={3} onBlur={(e) => { if (e.target.value !== i.note) void ideas().patch(i.id, { note: e.target.value }) }} />
        {v && <><span>variant</span><input aria-label="variant note" placeholder="a note on this variant" defaultValue={v.note} key={`v${v.id}${i.revision}`} maxLength={400} onBlur={(e) => { if (e.target.value !== v.note) void ideas().patch(i.id, { variants: [{ id: v.id, note: e.target.value }] }) }} /></>}
        <span>kept</span><span>{i.kept.length ? `${i.kept.length}×` : 'not yet'}</span>
      </div>
      <div className="verbs"><CommandButton id="story.idea.rename" text /><CommandButton id="story.idea.delete" text /></div>
    </div>
  )
}
