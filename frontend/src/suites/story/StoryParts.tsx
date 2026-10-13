// 17 (D85): the Story suite's parts (StorySuite.ts registers them) — SY0: the World tab. Panel: the sections with their counts and the
// adders; Stage: the editor over story/world.json (logline, synopsis, styles, the spine, variables); Inspector: the project format (the
// finalize gate), counts, the default style, the selected item's fields. Mouse-first (D32): every verb is a button or a menu entry.
import { Star } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { CommandButton } from '../../frame/CommandButton'
import { handleKeyFor, markUsed, sep, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { DEV_HOOKS } from '../../devHooks'
import { useSuiteRail } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import type { StoryBeat, StoryVariable, WorldStyle } from '../../api/types'
import { rowMenu } from './storyCommands'
import { SECTIONS, sy, useStory, type Section } from './storyStore'
import './story.css'

/** Dev hook (`window.__loom2Story`, DEV_HOOKS only): the smoke test drives the suite through the store. */
function devHook(): Record<string, unknown> {
  const w = window as unknown as { __loom2Story?: Record<string, unknown> }
  w.__loom2Story ??= { state: () => ({ world: sy().world, selected: sy().selected, section: sy().section }), load: () => sy().load(), flush: () => sy().flush(),
    addStyle: (name?: string) => sy().addStyle(name), setStyle: (id: string, patch: Partial<WorldStyle>) => sy().setStyle(id, patch), edit: (patch: Record<string, unknown>) => sy().edit(patch as never) }
  return w.__loom2Story
}
if (DEV_HOOKS) devHook()

const menu = (kind: 'style' | 'beat' | 'variable', id: string): MenuItem[] => rowMenu(kind, id).map((m) => (m === 'sep' ? sep : m))

// ------------------------------------------------------------------ Panel
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

export function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) void sy().load() }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  void tab                                                                                          // SY0: the World tab; Cast, Shots, Flow and Episode come with SY1–SY4
  return <WorldTab />
}

export function PrimaryAction() {
  const saving = useStory((s) => s.saving)
  const world = useStory((s) => s.world)
  const { active: tab } = useSuiteRail()
  void tab
  if (!world) return null
  return <div className="estimate"><span className={`dot ${saving ? 'tight' : 'ok'}`} />{saving ? 'saving…' : `saved · revision ${world.revision}`}</div>
}

// ------------------------------------------------------------------ Strip
export function Strip() {
  const world = useStory((s) => s.world)
  const project = useSession((s) => s.project)
  return (
    <div className="story-strip">
      <span>World</span>
      <span className="spacer" />
      {world && project?.open && project.format && <span className="hint">{project.name} · {project.format.width}×{project.format.height} · {project.format.fps} fps</span>}
    </div>
  )
}

// ------------------------------------------------------------------ Stage: the editor
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

export function Stage() {
  const world = useStory((s) => s.world)
  const loading = useStory((s) => s.loading)
  const section = useStory((s) => s.section)
  const selected = useStory((s) => s.selected)
  const project = useSession((s) => s.project)
  const host = useRef<HTMLDivElement>(null)
  markUsed('story.world.addStyle'); markUsed('story.world.addBeat'); markUsed('story.world.addVariable'); markUsed('story.world.remove')
  useEffect(() => { host.current?.querySelector<HTMLElement>(`#story-sec-${section}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' }) }, [section])
  if (!project?.open) return <div className="story-empty"><div>Open or create a project to begin.</div></div>
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

// ------------------------------------------------------------------ Inspector
export function Inspector() {
  const world = useStory((s) => s.world)
  const selected = useStory((s) => s.selected)
  const project = useSession((s) => s.project)
  if (!project?.open || !world) return <span className="hint">Nothing selected.</span>
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
        <h4>StoryBeat {world.spine.indexOf(beat) + 1}</h4>
        <div className="kv">
          <span>title</span><input type="text" value={beat.title} aria-label="selected beat title" onChange={(e) => sy().setBeat(beat.id, { title: e.target.value })} />
          <span>line</span><textarea rows={3} value={beat.line} aria-label="selected beat line" onChange={(e) => sy().setBeat(beat.id, { line: e.target.value })} />
        </div>
        <div className="verbs"><CommandButton id="story.world.beatUp" text /><CommandButton id="story.world.beatDown" text /><CommandButton id="story.world.remove" text /></div>
      </>}
      {variable && <>
        <h4>StoryVariable · {variable.name}</h4>
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
