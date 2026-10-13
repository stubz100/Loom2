// 17 (D85): the Story suite's parts (StorySuite.ts registers them) — SY0: the World tab. Panel: the sections with their counts and the
// adders; Stage: the editor over story/world.json (logline, synopsis, styles, the spine, variables); Inspector: the project format (the
// finalize gate), counts, the default style, the selected item's fields. SY1: the Cast tab — Panel: the profiles by class; Strip: the
// version selector and the bootstrap strip; Stage: the version page (hero, stub, the coverage grid, the candidates with keep / reject);
// Inspector: the profile and the version. Mouse-first (D32): every verb is a button or a menu entry.
import { Lock, Star } from 'lucide-react'
import { useEffect, useRef, type MouseEvent as ReactMouseEvent } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, runCommand, sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { DEV_HOOKS } from '../../devHooks'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import type { Asset, Profile, StoryBeat, StoryVariable, WorldStyle } from '../../api/types'
import { coverageGrid, rowsCovered } from './coverage'
import { askExpand, rowMenu } from './storyCommands'
import { CLASS_LABEL, SECTIONS, sy, useStory, type ProfileClass, type Section } from './storyStore'
import './story.css'

/** Dev hook (`window.__loom2Story`, DEV_HOOKS only): the smoke test and scripts/sy_acceptance.py drive the suite through the store. */
function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Story?: Record<string, unknown> }
  w.__loom2Story ??= { state: () => ({ world: sy().world, selected: sy().selected, section: sy().section, profileId: sy().profileId, versionId: sy().versionId, refPage: sy().refPage, candPage: sy().candPage }),
    load: () => sy().load(), flush: () => sy().flush(),
    addStyle: (name?: string) => sy().addStyle(name), setStyle: (id: string, patch: Partial<WorldStyle>) => sy().setStyle(id, patch), edit: (patch: Record<string, unknown>) => sy().edit(patch as never),
    // SY1
    loadProfiles: () => sy().loadProfiles(), selectProfile: (id: string | null, v?: string | null) => sy().selectProfile(id, v), loadPages: () => sy().loadPages(),
    createProfile: (name: string, cls: ProfileClass, hero?: string | null, stub?: string) => sy().createProfile(name, cls, hero, stub),
    expand: (preset: string, seeds = 1, tier: 'draft' | 'full' = 'draft') => sy().expand(preset, seeds, tier), curate: (ids: string[], verdict: 'keep' | 'reject') => sy().curate(ids, verdict),
    lock: () => sy().lockVersion(), newVersion: () => sy().newVersion(), setStub: (s: string) => sy().setStub(s) }
  return w.__loom2Story
}
if (DEV_HOOKS) devHook()

const menu = (kind: 'style' | 'beat' | 'variable', id: string): MenuItem[] => rowMenu(kind, id).map((m) => (m === 'sep' ? sep : m))

// ------------------------------------------------------------------ Panel · World
function WorldTab() {
  const world = useStory((s) => s.world)
  const section = useStory((s) => s.section)
  const counts: Record<Section, number | null> = {
    logline: null, synopsis: null, styles: world?.styles.length ?? 0, spine: world?.spine.length ?? 0, variables: world?.variables.length ?? 0,
  }
  return (
    <div className="story-panel">
      <div className="story-list" role="list">
        {SECTIONS.map((s) => (
          <button key={s.id} className={`story-row${section === s.id ? ' active' : ''}`} role="listitem" onClick={() => sy().setSection(s.id)} title={`Show the ${s.label} section`}>
            <span>{s.label}</span>{counts[s.id] !== null && <span className="n">{counts[s.id]}</span>}
          </button>
        ))}
      </div>
      <h4>Add</h4>
      <div className="verbs"><CommandButton id="story.world.addStyle" text /><CommandButton id="story.world.addBeat" text /><CommandButton id="story.world.addVariable" text /></div>
      <span className="hint">The styles reach Generate's Style picker; a beat becomes a Flow node by hand (SY3); the variables drive the Flow's conditions.</span>
    </div>
  )
}

// ------------------------------------------------------------------ Panel · Cast
function CastTab() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const filter = useStory((s) => s.castFilter)
  const search = useStory((s) => s.castSearch)
  const q = search.trim().toLowerCase()
  const shown = profiles.filter((p) => (filter === 'all' || p.cls === filter) && (!q || p.name.toLowerCase().includes(q)))
  return (
    <div className="story-panel cast-panel">
      <div className="segmented" aria-label="class">
        {(['all', 'character', 'place', 'prop'] as const).map((c) => <button key={c} className={filter === c ? 'active' : ''} onClick={() => sy().setCastFilter(c)}>{c === 'all' ? 'all' : `${CLASS_LABEL[c]}s`}</button>)}
      </div>
      <input type="search" value={search} aria-label="search profiles" placeholder="search" onChange={(e) => sy().setCastSearch(e.target.value)} />
      <div className="story-list" role="list">
        {shown.map((p) => {
          const v = p.versions.find((x) => x.id === p.current)
          return (
            <button key={p.id} className={`story-row profile-row${profileId === p.id ? ' active' : ''}`} role="listitem" data-id={p.id} onClick={() => sy().selectProfile(p.id)}
              onContextMenu={(e) => { sy().selectProfile(p.id); showMenu(e, [{ cmd: 'story.cast.expand' }, { cmd: 'story.cast.newVersion' }, { cmd: 'story.cast.lock' }, sep, { cmd: 'story.cast.openGroup' }, { cmd: 'story.cast.openCandidates' }, sep, { cmd: 'story.cast.delete' }]) }}>
              {v?.hero_asset_id ? <img className="pthumb" src={api.thumbUrl(v.hero_asset_id, 256)} alt="" /> : <span className="pthumb empty" />}
              <span className="pname">{p.name}<span className="muted"> · {CLASS_LABEL[p.cls]}</span></span>
              <span className="n">{p.current} <i className={`dot ${v?.state === 'final' ? 'tight' : 'ok'}`} title={v?.state === 'final' ? 'locked' : 'open'} /></span>
            </button>
          )
        })}
        {!shown.length && <div className="empty hint">{profiles.length ? 'No profile matches.' : 'No profiles yet — "Make a character…" on a Catalogue tile, or New profile…'}</div>}
      </div>
      <div className="verbs"><CommandButton id="story.cast.new" text /><CommandButton id="story.cast.newPlace" text /><CommandButton id="story.cast.newProp" text /></div>
    </div>
  )
}

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) { void sy().load(); void sy().loadProfiles() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  if (tab === 'cast') return <CastTab />
  return <WorldTab />
}

export function PrimaryAction() {
  const saving = useStory((s) => s.saving)
  const world = useStory((s) => s.world)
  const profileId = useStory((s) => s.profileId)
  const profiles = useStory((s) => s.profiles)
  const versionId = useStory((s) => s.versionId)
  const expanding = useStory((s) => s.expanding)
  const caps = useSession((s) => s.capabilities?.story)
  const { active: tab } = useSuiteRail()
  markUsed('story.cast.expand')
  if (tab === 'cast') {
    const p = profiles.find((x) => x.id === profileId); const v = p?.versions.find((x) => x.id === (versionId ?? p.current))
    const reason = !p ? 'pick a profile' : !v ? 'no version' : v.state !== 'open' ? `${v.id} is locked — expand a new version` : !v.hero_asset_id ? 'no hero image yet' : !caps?.model_id ? 'no model in this build' : expanding ? 'queuing…' : caps.missing.length ? `weights missing: ${caps.missing.join(', ')}` : ''
    const secs = (caps?.seconds ?? 0) * (caps?.presets.full?.cells ?? 0)
    return (
      <div>
        <button className="primary" disabled={!!reason} onClick={() => runCommand('story.cast.expand')} title="Queue one job per coverage cell (Full coverage; the dialog says the cost) — Ctrl+Enter">Expand ▶</button>
        <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className="dot ok" />{caps?.presets.full?.cells ?? '?'} cells · ≈ {Math.max(1, Math.round(secs / 60))} min warm · {caps?.short}</>}</div>
      </div>
    )
  }
  if (!world) return null
  return <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${world.revision}`}</div>
}

// ------------------------------------------------------------------ Strip
function Bootstrap({ p }: { p: Profile }) {
  const refPage = useStory((s) => s.refPage)
  const candPage = useStory((s) => s.candPage)
  const versionId = useStory((s) => s.versionId)
  const caps = useSession((s) => s.capabilities?.story)
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  const grid = coverageGrid(Object.values(refPage?.assets ?? {}), caps?.coverage.shots ?? [], caps?.coverage.angles ?? [])
  const curated = (caps?.coverage.shots?.length ?? 0) > 0 && rowsCovered(grid).length === (caps?.coverage.shots?.length ?? 0)
  const steps: { id: string; label: string; done: boolean; hint: string; run?: string }[] = [
    { id: 'cast', label: 'Cast', done: !!v?.hero_asset_id, hint: v?.hero_asset_id ? 'the hero is set' : 'make an image the hero ("Make a character…" on a tile, or pick a candidate)' },
    { id: 'expand', label: 'Expand', done: Object.keys(candPage?.assets ?? {}).length > 0, hint: 'one job per coverage cell with the hero as the reference', run: 'story.cast.expand' },
    { id: 'curate', label: 'Curate', done: curated, hint: curated ? 'every shot-size row has a reference' : 'keep candidates until every shot-size row has one (advisory)' },
    { id: 'train', label: 'Train', done: !!v?.lora, hint: 'LoRA training comes with the next wave (03 §5)' },
    { id: 'lock', label: 'Lock', done: v?.state === 'final', hint: 'the version becomes read-only; a retake is a new version', run: 'story.cast.lock' },
  ]
  return (
    <span className="bootstrap" aria-label="bootstrap">
      {steps.map((s, i) => (
        <span key={s.id} className={`bs-step${s.done ? ' done' : ''}${s.id === 'train' ? ' off' : ''}`} title={s.hint}>
          {s.run ? <button className="quiet" onClick={() => runCommand(s.run!)}>{s.label}{s.done ? ' ✓' : ''}</button> : <span>{s.label}{s.done ? ' ✓' : ''}</span>}
          {i < steps.length - 1 && <span className="sep">›</span>}
        </span>
      ))}
    </span>
  )
}

export function Strip() {
  const world = useStory((s) => s.world)
  const project = useSession((s) => s.project)
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const { active: tab } = useSuiteRail()
  markUsed('story.cast.lock'); markUsed('story.cast.newVersion')
  if (tab === 'cast') {
    const p = profiles.find((x) => x.id === profileId)
    if (!p) return <div className="story-strip"><span>Cast</span><span className="spacer" /><span className="hint">pick a profile, or make one from a Catalogue tile</span></div>
    const v = p.versions.find((x) => x.id === (versionId ?? p.current))
    return (
      <div className="story-strip">
        <b>{p.name}</b>
        <select aria-label="version" value={v?.id ?? p.current} onChange={(e) => sy().selectProfile(p.id, e.target.value)} title="The version shown (mentions use the current one unless pinned)">
          {p.versions.map((x) => <option key={x.id} value={x.id}>{x.id}{x.id === p.current ? ' · current' : ''}{x.state === 'final' ? ' · locked' : ''}</option>)}
        </select>
        <CommandButton id="story.cast.newVersion" />
        {v?.state === 'final' ? <span className="lock-badge" title={`locked ${v.locked_at ?? ''}`}><Lock size={12} /> locked</span> : <CommandButton id="story.cast.lock" />}
        <span className="spacer" />
        <Bootstrap p={p} />
      </div>
    )
  }
  return (
    <div className="story-strip">
      <span>World</span>
      <span className="spacer" />
      {world && project?.open && project.format && <span className="hint">{project.name} · {project.format.width}×{project.format.height} · {project.format.fps} fps</span>}
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the World editor
function StyleRow({ s, active, isDefault }: { s: WorldStyle; active: boolean; isDefault: boolean }) {
  return (
    <div className={`row-item style-row${active ? ' active' : ''}`} data-id={s.id} onClick={() => sy().select({ kind: 'style', id: s.id })} onContextMenu={(e) => showMenu(e, menu('style', s.id))}>
      <button className="quiet" title={isDefault ? 'The default style (Generate preselects it)' : 'Make it the default style'} aria-label={isDefault ? `${s.name} is the default style` : `make ${s.name} the default style`}
        onClick={(e) => { e.stopPropagation(); sy().setDefaultStyle(isDefault ? null : s.id) }}><Star size={12} fill={isDefault ? 'currentColor' : 'none'} /></button>
      <input type="text" value={s.name} aria-label="style name" placeholder="name" onChange={(e) => sy().setStyle(s.id, { name: e.target.value })} />
      <input type="text" value={s.fragment} aria-label="style fragment" placeholder="the fragment appended after the prompt — e.g. painterly storyboard, ink and wash" onChange={(e) => sy().setStyle(s.id, { fragment: e.target.value })} />
      <span className="tools"><button className="quiet" title="Remove this style" aria-label={`remove style ${s.name}`} onClick={(e) => { e.stopPropagation(); sy().removeStyle(s.id) }}>✕</button></span>
    </div>
  )
}

function BeatRow({ b, i, active }: { b: StoryBeat; i: number; active: boolean }) {
  return (
    <div className={`row-item beat-row${active ? ' active' : ''}`} data-id={b.id} onClick={() => sy().select({ kind: 'beat', id: b.id })} onContextMenu={(e) => showMenu(e, menu('beat', b.id))}>
      <span className="k">{i + 1}</span>
      <input type="text" value={b.title} aria-label="beat title" placeholder="title" onChange={(e) => sy().setBeat(b.id, { title: e.target.value })} />
      <input type="text" value={b.line} aria-label="beat line" placeholder="one line: what happens" onChange={(e) => sy().setBeat(b.id, { line: e.target.value })} />
      <span className="tools">
        <button className="quiet" title="Move earlier" aria-label={`move beat ${i + 1} earlier`} disabled={i === 0} onClick={(e) => { e.stopPropagation(); sy().moveBeat(b.id, -1) }}>▲</button>
        <button className="quiet" title="Move later" aria-label={`move beat ${i + 1} later`} onClick={(e) => { e.stopPropagation(); sy().moveBeat(b.id, 1) }}>▼</button>
        <button className="quiet" title="Remove this beat" aria-label={`remove beat ${i + 1}`} onClick={(e) => { e.stopPropagation(); sy().removeBeat(b.id) }}>✕</button>
      </span>
    </div>
  )
}

function VarRow({ v, active }: { v: StoryVariable; active: boolean }) {
  return (
    <div className={`row-item var-row${active ? ' active' : ''}`} data-id={v.name} onClick={() => sy().select({ kind: 'variable', id: v.name })} onContextMenu={(e) => showMenu(e, menu('variable', v.name))}>
      <input type="text" value={v.name} aria-label="variable name" placeholder="name" onChange={(e) => sy().setVariable(v.name, { name: e.target.value.replace(/[^A-Za-z0-9_]/g, '_') })} />
      <select value={v.type} aria-label="variable type" onChange={(e) => sy().setVariable(v.name, { type: e.target.value as StoryVariable['type'] })}><option value="bool">bool</option><option value="enum">enum</option></select>
      {v.type === 'enum'
        ? <input type="text" value={v.values.join(', ')} aria-label="enum values" placeholder="values, comma-separated" onChange={(e) => sy().setVariable(v.name, { values: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) })} />
        : <span className="k">true / false</span>}
      {v.type === 'enum'
        ? <select value={String(v.default)} aria-label="default value" onChange={(e) => sy().setVariable(v.name, { default: e.target.value })}>{v.values.map((x) => <option key={x} value={x}>{x}</option>)}</select>
        : <select value={v.default ? 'true' : 'false'} aria-label="default value" onChange={(e) => sy().setVariable(v.name, { default: e.target.value === 'true' })}><option value="false">false</option><option value="true">true</option></select>}
      <span className="tools"><button className="quiet" title="Remove this variable" aria-label={`remove variable ${v.name}`} onClick={(e) => { e.stopPropagation(); sy().removeVariable(v.name) }}>✕</button></span>
    </div>
  )
}

function WorldEditor() {
  const world = useStory((s) => s.world)
  const loading = useStory((s) => s.loading)
  const section = useStory((s) => s.section)
  const selected = useStory((s) => s.selected)
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => { host.current?.querySelector<HTMLElement>(`#story-sec-${section}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [section])
  if (!world) return <div className="story-empty"><div>{loading ? 'Loading the world…' : 'The world could not be read.'}</div></div>
  return (
    <div ref={host} className="world-editor" tabIndex={0} onKeyDown={(e) => { if ((e.target as HTMLElement).tagName !== 'INPUT' && (e.target as HTMLElement).tagName !== 'TEXTAREA' && handleKeyFor('story', e.nativeEvent)) e.preventDefault() }}>
      <section id="story-sec-logline">
        <h3>Logline<span className="hint">one sentence</span></h3>
        <textarea rows={2} value={world.logline} aria-label="logline" placeholder="Who wants what, and what stands in the way." onChange={(e) => sy().edit({ logline: e.target.value })} />
      </section>
      <section id="story-sec-synopsis">
        <h3>Synopsis</h3>
        <textarea rows={8} value={world.synopsis} aria-label="synopsis" placeholder="The story in a page." onChange={(e) => sy().edit({ synopsis: e.target.value })} />
      </section>
      <section id="story-sec-styles">
        <h3>Styles<span className="hint">one per generation, appended after the prompt; ★ marks the default Generate preselects</span></h3>
        <div className="rows">
          {world.styles.map((s) => <StyleRow key={s.id} s={s} active={selected?.kind === 'style' && selected.id === s.id} isDefault={world.default_style === s.id} />)}
          {!world.styles.length && <div className="empty">No styles yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addStyle" text /></div>
      </section>
      <section id="story-sec-spine">
        <h3>Spine<span className="hint">the beats in order; a Flow node is made from a beat by hand (SY3)</span></h3>
        <div className="rows">
          {world.spine.map((b, i) => <BeatRow key={b.id} b={b} i={i} active={selected?.kind === 'beat' && selected.id === b.id} />)}
          {!world.spine.length && <div className="empty">No beats yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addBeat" text /></div>
      </section>
      <section id="story-sec-variables">
        <h3>Variables<span className="hint">bool or enum flags the Flow's conditions read (SY3)</span></h3>
        <div className="rows">
          {world.variables.map((v) => <VarRow key={v.name} v={v} active={selected?.kind === 'variable' && selected.id === v.name} />)}
          {!world.variables.length && <div className="empty">No variables yet.</div>}
        </div>
        <div className="adder"><CommandButton id="story.world.addVariable" text /></div>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the Cast version page
function candidateMenu(id: string): MenuItem[] {
  const s = sy()
  if (!s.picked.includes(id)) s.pick(id)
  return [{ cmd: 'story.cast.keep' }, { cmd: 'story.cast.reject' }, { cmd: 'story.cast.setHero' }, sep, { cmd: 'story.cast.openCandidates' }]
}

function Candidate({ a, picked }: { a: Asset; picked: boolean }) {
  const cell = (a.params as { coverage_cell?: { shot?: string; angle?: string; expression?: string } } | null)?.coverage_cell
  const title = cell ? `${cell.shot ?? ''} · ${cell.angle ?? ''} · ${cell.expression ?? ''}` : a.prompt_text ?? ''
  return (
    <div className={`cand-card${picked ? ' picked' : ''}${a.state === 'reject' ? ' reject' : ''}${a.state === 'keep' ? ' keep' : ''}`} data-id={a.id} title={title}
      onClick={(e: ReactMouseEvent) => sy().pick(a.id, e.ctrlKey || e.shiftKey)} onContextMenu={(e) => showMenu(e, candidateMenu(a.id))}>
      <img src={api.thumbUrl(a.id, 256)} alt="" />
      {cell && <span className="cell">{cell.shot} · {cell.angle}</span>}
      <span className="tools">
        <button className="quiet" title="Keep: into the reference set" aria-label="keep" onClick={(e) => { e.stopPropagation(); void sy().curate([a.id], 'keep') }}>✓</button>
        <button className="quiet" title="Reject" aria-label="reject" onClick={(e) => { e.stopPropagation(); void sy().curate([a.id], 'reject') }}>✕</button>
      </span>
    </div>
  )
}

function CastPage() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const refPage = useStory((s) => s.refPage)
  const candPage = useStory((s) => s.candPage)
  const picked = useStory((s) => s.picked)
  const caps = useSession((s) => s.capabilities?.story)
  markUsed('story.cast.keep'); markUsed('story.cast.reject'); markUsed('story.cast.setHero'); markUsed('story.cast.openCandidates'); markUsed('story.cast.openGroup'); markUsed('story.cast.delete')
  const p = profiles.find((x) => x.id === profileId)
  if (!p) return <div className="story-empty"><div>Pick a profile on the left, or make one: <b>Make a character…</b> on a Catalogue tile puts the image in as the hero.<div className="quick-cards"><CommandButton id="story.cast.new" text /></div></div></div>
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  if (!v) return null
  const refs = Object.values(refPage?.assets ?? {})
  const grid = coverageGrid(refs, caps?.coverage.shots ?? [], caps?.coverage.angles ?? [])
  const cands = Object.values(candPage?.assets ?? {}).sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const open = v.state === 'open'
  return (
    <div className="cast-page" tabIndex={0} onKeyDown={(e) => { if ((e.target as HTMLElement).tagName !== 'INPUT' && (e.target as HTMLElement).tagName !== 'TEXTAREA' && handleKeyFor('story', e.nativeEvent)) e.preventDefault() }}>
      <div className="cast-head">
        <div className="hero-card">{v.hero_asset_id ? <img src={api.thumbUrl(v.hero_asset_id, 512)} alt="" /> : <span className="hint">no hero yet</span>}</div>
        <div className="cast-fields">
          <h2>{p.name} <span className="muted">— {CLASS_LABEL[p.cls]} — {v.id} ({open ? 'open' : 'locked'})</span></h2>
          <label className="stub"><span>prompt stub</span>
            <textarea rows={2} value={v.stub} aria-label="prompt stub" readOnly={!open} placeholder="the clause a @mention carries into a prompt — e.g. Mara, a wiry courier in a grey coat" onChange={(e) => sy().setStub(e.target.value)} />
          </label>
          <div className="counts"><span>reference set · <b>{refs.length}</b></span><span>candidates · <b>{cands.length}</b></span>{v.candidates_group_id === null && <span className="hint">(none expanded yet)</span>}</div>
        </div>
      </div>
      <section>
        <h3>Coverage <span className="hint">kept references per shot size × angle; thin cells are tinted (advisory)</span></h3>
        <table className="cov-grid" aria-label="coverage">
          <thead><tr><th /> {grid.angles.map((a) => <th key={a}>{a}</th>)}</tr></thead>
          <tbody>
            {grid.shots.map((s) => <tr key={s}><th>{s}</th>{grid.angles.map((a) => { const n = grid.counts[s]?.[a] ?? 0; return <td key={a} className={n ? (n >= 2 ? 'full' : 'one') : 'thin'}>{n || '–'}</td> })}</tr>)}
          </tbody>
        </table>
        {grid.uncelled > 0 && <span className="hint">{grid.uncelled} reference{grid.uncelled === 1 ? '' : 's'} without a cell (the hero, imports).</span>}
      </section>
      <section>
        <h3>Candidates <span className="hint">newest first · ✓ keeps into the reference set, ✕ rejects · click to select, Ctrl-click for several</span></h3>
        {!cands.length && <div className="empty">{open ? <>No candidates yet — <button className="link" onClick={() => void askExpand('full', 1, 'draft')} disabled={!v.hero_asset_id}>Expand ▶</button> makes one image per coverage cell.</> : 'This version is locked.'}</div>}
        <div className="cand-strip" role="list">
          {cands.map((a) => <Candidate key={a.id} a={a} picked={picked.includes(a.id)} />)}
        </div>
      </section>
    </div>
  )
}

export function Stage() {
  const project = useSession((s) => s.project)
  const { active: tab } = useSuiteRail()
  markUsed('story.world.addStyle'); markUsed('story.world.addBeat'); markUsed('story.world.addVariable'); markUsed('story.world.remove'); markUsed('story.cast.new'); markUsed('story.cast.newPlace'); markUsed('story.cast.newProp')
  if (!project?.open) return <div className="story-empty"><div>Open or create a project to begin.</div></div>
  if (tab === 'cast') return <CastPage />
  return <WorldEditor />
}

// ------------------------------------------------------------------ Inspector
function CastInspector() {
  const profiles = useStory((s) => s.profiles)
  const profileId = useStory((s) => s.profileId)
  const versionId = useStory((s) => s.versionId)
  const picked = useStory((s) => s.picked)
  const p = profiles.find((x) => x.id === profileId)
  if (!p) return <span className="hint">Nothing selected.</span>
  const v = p.versions.find((x) => x.id === (versionId ?? p.current))
  return (
    <div className="story-insp">
      <h4>{p.name}</h4>
      <div className="kv">
        <span>name</span><input type="text" value={p.name} aria-label="profile name" onChange={(e) => void sy().patchProfile({ name: e.target.value })} />
        <span>class</span>
        <select value={p.cls} aria-label="profile class" onChange={(e) => void sy().patchProfile({ cls: e.target.value as ProfileClass })}>{(Object.keys(CLASS_LABEL) as ProfileClass[]).map((c) => <option key={c} value={c}>{CLASS_LABEL[c]}</option>)}</select>
        <span>current</span>
        <select value={p.current} aria-label="current version" onChange={(e) => void sy().patchProfile({ current: e.target.value })}>{p.versions.map((x) => <option key={x.id} value={x.id}>{x.id}</option>)}</select>
        <span>versions</span><span>{p.versions.length}</span>
        <span>mention</span><span className="mono">@{p.name}</span>
      </div>
      {v && <>
        <h4>Version {v.id} · {v.state}</h4>
        <div className="kv">
          <span>hero</span><span>{v.hero_asset_id ? <img className="insp-thumb small" src={api.thumbUrl(v.hero_asset_id, 256)} alt="" /> : '—'}</span>
          <span>reference set</span><span className="mono">{v.group_id}</span>
          <span>candidates</span><span className="mono">{v.candidates_group_id ?? '—'}</span>
          <span>trigger</span><span>{v.trigger ?? '— (LoRA wave)'}</span>
          <span>LoRA</span><span>{v.lora ?? '— (LoRA wave)'}</span>
          <span>from</span><span>{v.derived_from ?? '—'}</span>
          <span>created</span><span>{v.created_at.slice(0, 16).replace('T', ' ')}</span>
        </div>
        <div className="verbs"><CommandButton id="story.cast.expand" text /><CommandButton id="story.cast.lock" text /><CommandButton id="story.cast.newVersion" text /></div>
        <div className="verbs"><CommandButton id="story.cast.openGroup" text /><CommandButton id="story.cast.openCandidates" text /></div>
        {picked.length > 0 && <><h4>{picked.length} candidate{picked.length === 1 ? '' : 's'} selected</h4><div className="verbs"><CommandButton id="story.cast.keep" text /><CommandButton id="story.cast.reject" text /><CommandButton id="story.cast.setHero" text /></div></>}
      </>}
      <div className="verbs"><CommandButton id="story.cast.delete" text /></div>
    </div>
  )
}

export function Inspector() {
  const world = useStory((s) => s.world)
  const selected = useStory((s) => s.selected)
  const project = useSession((s) => s.project)
  const { active: tab } = useSuiteRail()
  if (!project?.open) return <span className="hint">Nothing selected.</span>
  if (tab === 'cast') return <CastInspector />
  if (!world) return <span className="hint">Nothing selected.</span>
  const fmt = project.format
  const style = selected?.kind === 'style' ? world.styles.find((s) => s.id === selected.id) : undefined
  const beat = selected?.kind === 'beat' ? world.spine.find((b) => b.id === selected.id) : undefined
  const variable = selected?.kind === 'variable' ? world.variables.find((v) => v.name === selected.id) : undefined
  return (
    <div className="story-insp">
      <h4>World</h4>
      <div className="kv">
        <span>format</span><span title="Fixed at the project's creation (R45); the finalize gate of a shot's clip (17 §3c)">{fmt ? `${fmt.aspect[0]}:${fmt.aspect[1]} · ${fmt.width}×${fmt.height} · ${fmt.fps} fps` : '—'}</span>
        <span>styles</span><span>{world.styles.length}</span>
        <span>beats</span><span>{world.spine.length}</span>
        <span>variables</span><span>{world.variables.length}</span>
        <span>default style</span>
        <select value={world.default_style ?? ''} aria-label="default style" onChange={(e) => sy().setDefaultStyle(e.target.value || null)}>
          <option value="">none</option>{world.styles.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <span>revision</span><span>{world.revision}</span>
      </div>
      {style && <>
        <h4>Style · {style.name}</h4>
        <div className="kv">
          <span>name</span><input type="text" value={style.name} aria-label="selected style name" onChange={(e) => sy().setStyle(style.id, { name: e.target.value })} />
          <span>fragment</span><textarea rows={3} value={style.fragment} aria-label="selected style fragment" onChange={(e) => sy().setStyle(style.id, { fragment: e.target.value })} />
          <span>default</span><span>{world.default_style === style.id ? 'yes' : 'no'}</span>
        </div>
        <div className="verbs"><CommandButton id="story.world.defaultStyle" text /><CommandButton id="story.world.remove" text /></div>
      </>}
      {beat && <>
        <h4>Beat {world.spine.indexOf(beat) + 1}</h4>
        <div className="kv">
          <span>title</span><input type="text" value={beat.title} aria-label="selected beat title" onChange={(e) => sy().setBeat(beat.id, { title: e.target.value })} />
          <span>line</span><textarea rows={3} value={beat.line} aria-label="selected beat line" onChange={(e) => sy().setBeat(beat.id, { line: e.target.value })} />
        </div>
        <div className="verbs"><CommandButton id="story.world.beatUp" text /><CommandButton id="story.world.beatDown" text /><CommandButton id="story.world.remove" text /></div>
      </>}
      {variable && <>
        <h4>Variable · {variable.name}</h4>
        <div className="kv">
          <span>type</span><span>{variable.type}</span>
          <span>values</span><span>{variable.type === 'enum' ? variable.values.join(', ') : 'true / false'}</span>
          <span>default</span><span>{String(variable.default)}</span>
        </div>
        <div className="verbs"><CommandButton id="story.world.remove" text /></div>
      </>}
    </div>
  )
}
