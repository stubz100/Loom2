// Generate suite (09; D90 02 §6): one scrolling Panel column (GenerateColumn.tsx — saved panels, prompt, references, look, camera, model,
// size), the pinned Generate / Queue / Preview foot, results on the Catalogue grid filtered to this suite with interim tiles and live
// previews. New angle is a sheet on any image (AngleTab.tsx).
import { PersonStanding, ArrowDownFromLine, Boxes, Bookmark, Camera, Hand, HardDriveDownload, Images, Orbit, Palette, PenLine, RotateCcw, RotateCw, SlidersHorizontal, Sparkles, Wand2, X, ZoomIn, ZoomOut } from 'lucide-react'
import { lazy, Suspense, useEffect, useMemo } from 'react'
import type { Asset } from '../../api/types'
import { handleKeyFor, markUsed, registerCommands, runCommand } from '../../frame/commands'
import { type SuiteDef } from '../../frame/suiteRegistry'
import { GenerateColumn, PreviewButton } from './GenerateColumn'
import { byOrder, shortName } from '../../store/modelCaps'
import { askText, useSession } from '../../store/session'
import { CatalogueStoreCtx } from '../catalogue/catalogueContext'
import { useGenerateResults } from '../catalogue/catalogueStore'
import { Inspector as CatInspector, Stage as CatStage, Strip as CatStrip } from '../catalogue/CatalogueSuite'
import { expandCells, batchOf, modelPatch, subjectItem, submitBlock, useGenerate, withoutForeignLinks, type Panel as PanelState, type Subject } from './generateStore'
import { http, unwrap } from '../../api/client'
import { castOffer } from './subjectCast'
import { versionOf } from './sheet'
import { profilesForMentions, useStory } from '../story/storyStore'
import { useLibrary } from '../story/libraryStore'
import { ImageModeSwitch } from '../../frame/ImageModeSwitch'
import './generate.css'
import { registerKeyHost } from '../../frame/keyHosts'

/** D93: drop the panel's links to profiles / groups the open project lacks (it is remembered across projects), with a toast. */
async function pruneForeignLinks(): Promise<void> {
  try {
    const [profiles, tree] = await Promise.all([unwrap(http.GET('/story/profiles')), unwrap(http.GET('/groups/tree'))])
    const groups = new Set<string>()
    const walk = (n: { id: string; children: unknown[] }) => { groups.add(n.id); for (const c of n.children as { id: string; children: unknown[] }[]) walk(c) }
    walk(tree)
    const g = useGenerate.getState()
    const { patch, dropped } = withoutForeignLinks(g.panel, new Set(profiles.items.map((x) => x.id)), groups)
    if (!dropped) return
    g.set(patch)
    useSession.getState().toast(`${dropped} link${dropped === 1 ? '' : 's'} from another project removed from Image — the words stay`, 'info')
  } catch { /* no project or the server is busy: the preview says what is wrong */ }
}

function Panel({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  const caps = useSession((s) => s.capabilities)
  const refresh = useGenerate((g) => g.refreshPreview)
  useEffect(() => {
    if (!project?.open) return
    void refresh(); void useLibrary.getState().load(); void useStory.getState().load()
    void pruneForeignLinks()                                                // D93: links remembered from another project
  }, [project?.path, refresh])   // D92: the tiles are the World library's; D85: the Style picker needs the world
  // C3 (D26) / D65: no model yet, or a persisted one this build does not offer (dev under `open`) → the variant's t2i default, else the first listed
  useEffect(() => {
    const g = useGenerate.getState()
    if (!caps || caps.models[g.panel.model_id]?.recipes.t2i) return
    const next = (caps.models[caps.defaults.t2i] ? caps.defaults.t2i : '') || byOrder(caps.models).find(([, m]) => m.recipes.t2i)?.[0]
    if (next) g.set(modelPatch(g.panel, next))
  }, [caps])
  if (!project?.open) return <span style={{ color: 'var(--fg3)' }}>Open or create a project.</span>
  return <GenerateColumn tab={tab} />                                     // D90 (02 §6.1): one column; the rail jumps between its sections
}

/** The pinned primary action with its estimate and disabled reasons (09 §3 foot); New angle has its own sheet now (D90, AngleTab.tsx). */
// D95 (AN1, UX0 #5): From a stage's foot is the stage's (Render frame), loaded with its code
const FromStageFoot = lazy(() => import('../stage/FromStage').then((m) => ({ default: m.FromStageFoot })))
function PrimaryAction() {
  const source = useGenerate((g) => g.source)
  if (source === 'stage') return <Suspense fallback={null}><FromStageFoot /></Suspense>
  return <PromptFoot />
}

function PromptFoot() {
  const g = useGenerate()
  const s = useSession()
  markUsed('gen.generate'); markUsed('gen.stage'); markUsed('gen.savePreset'); markUsed('gen.fetchMissing')
  const pv = g.preview
  const missing = pv?.missing ?? []
  const cells = expandCells(g.poses, s.capabilities?.story?.coverage?.shots ?? [], s.capabilities?.story?.coverage?.angles ?? [], s.capabilities?.story?.coverage?.expressions ?? []).length
  const reason = submitBlock(g, !!s.project?.open) ?? (g.run === 'expand' && !cells ? 'pick at least one pose (the Poses section)' : null)   // D90 (B4): the same reason gates Ctrl+Enter and the palette
  markUsed('gen.run.generate'); markUsed('gen.run.expand')
  return (
    <div>
      <span className="segmented run-switch" role="group" aria-label="How to run">{/* D115: Generate as always, or Expand over the chosen poses */}
        <button type="button" className={g.run === 'generate' ? 'active' : ''} aria-pressed={g.run === 'generate'} onClick={() => runCommand('gen.run.generate')} title="Generate: the prompt as written">Generate</button>
        <button type="button" className={g.run === 'expand' ? 'active' : ''} aria-pressed={g.run === 'expand'} onClick={() => runCommand('gen.run.expand')} title="Expand: one image per pose chosen in the Poses section, the prompt's pose and action replaced">Expand</button>
      </span>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('gen.generate')} title={g.run === 'expand' ? 'Expand (Ctrl+Enter)' : 'Generate (Ctrl+Enter)'}>
        {g.run === 'expand' ? `Expand ${cells * g.panel.count} ▶` : `Generate ${g.panel.count} ▶`}</button>
      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <button disabled={!!reason} onClick={() => runCommand('gen.stage')} title="Queue: add to the queue and run it later — Run now in the Dock (Ctrl+Shift+Enter)">Queue</button>
        <PreviewButton />
        {missing.length > 0 && <button onClick={() => runCommand('gen.fetchMissing')} title="Fetch the missing weights: Models & engine, on the missing entries">Fetch {missing.reduce((a, m) => a + (m.approx_gb ?? 0), 0).toFixed(0)} GB</button>}
      </div>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />≈ {Math.round((pv?.estimate.seconds ?? 0) * g.panel.count)} s · {pv?.width}×{pv?.height} · {pv?.steps} st{pv?.turbo ? ' turbo' : ''}{pv?.scheduler === 'flux2' ? ' · flux2 schedule' : ''}</>}</div>
    </div>
  )
}

// ------------------------------------------------------------------ Strip / Stage / Inspector (results on the catalogue grid)
function Strip() {
  const g = useGenerate()
  const health = useSession((s) => s.health)
  const r = useGenerateResults()
  useEffect(() => {
    const patch = g.show === 'batch' ? { batch_id: g.lastBatch ?? undefined, session_id: undefined } : g.show === 'session' ? { batch_id: undefined, session_id: health?.session_id ?? undefined } : { batch_id: undefined, session_id: undefined }
    if (r.q.batch_id !== patch.batch_id || r.q.session_id !== patch.session_id) void r.setQuery(patch)
  }, [g.show, g.lastBatch, health?.session_id]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <span>show</span>
      <div className="segmented gen-strip-show">{(['batch', 'session', 'all'] as const).map((m) => <button key={m} className={g.show === m ? 'active' : ''} onClick={() => g.setShow(m)}>{m === 'batch' ? 'this batch' : m === 'session' ? 'session' : 'all'}</button>)}</div>
      <CatStrip />
    </>
  )
}

function Interim() {
  const jobs = useSession((s) => s.jobs)
  const previews = useSession((s) => s.previews)
  const caps = useSession((s) => s.capabilities)
  const cancel = useSession((s) => s.cancelJob)
  const release = useSession((s) => s.releaseJob)
  const lastBatch = useGenerate((g) => g.lastBatch)
  // D66: Generate's own jobs (origin suite 'generate'), plus the batch it is showing (a Catalogue re-run / variations lands here too);
  // jobs without an origin (queued before D66) keep showing
  const list = useMemo(() => Object.values(jobs).filter((j) => j.kind === 't2i' && ['running', 'queued', 'staged'].includes(j.status) && (!j.origin || j.origin.suite === 'generate' || batchOf(j) === lastBatch))
    .sort((a, b) => (a.status === 'running' ? -1 : b.status === 'running' ? 1 : a.created_at < b.created_at ? -1 : 1)), [jobs, lastBatch])
  if (!list.length) return null
  return (
    <div className="interim">
      {list.map((j) => (
        <div className="card" key={j.id}>
          <div className="img">{previews[j.id] ? <img src={previews[j.id]} alt="" /> : <span style={{ color: 'var(--fg3)' }}>{j.status === 'running' ? j.progress_text || 'starting' : j.status}</span>}</div>
          <div className="bar"><i style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }} /></div>
          <div className="t"><span>{shortName((j.recipe as { model_id?: string }).model_id, caps)} · {j.seed}</span>
            <span>{j.status === 'staged' ? <button className="quiet" title="Run now" onClick={() => void release(j.id)}>run now</button> : <button className="quiet" onClick={() => void cancel(j.id)}>✕</button>}</span></div>
        </div>
      ))}
    </div>
  )
}

function Stage() {
  const project = useSession((s) => s.project)
  const r = useGenerateResults()
  useEffect(() => { if (project?.open) { void r.load(); void r.refreshMeta() } }, [project?.path]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <div className="placeholder"><div><h2>Image</h2>open or create a project to begin</div></div>
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column' }}>
      <Interim />
      <div style={{ position: 'relative', flex: 1, minHeight: 0 }}><CatStage /></div>
    </div>
  )
}

const withResults = (C: React.ComponentType) => function Wrapped() { return <CatalogueStoreCtx.Provider value={useGenerateResults}><C /></CatalogueStoreCtx.Provider> }

const canSubmit = () => !submitBlock(useGenerate.getState(), !!useSession.getState().project?.open)   // D90 (B4): what disables the Foot's buttons
registerCommands([
  { id: 'gen.generate', scope: 'generate', label: 'Generate', icon: Wand2, keys: 'Ctrl+Enter', placement: ['panel'], when: () => useGenerate.getState().source === 'stage' || canSubmit(),
    run: () => { const g = useGenerate.getState(); if (g.source === 'stage') runCommand('stage.shot.generate'); else if (g.run === 'expand') void g.expand(false); else void g.generate(false) } },   // D95: From a stage → the stage's Render frame; D115: Expand over the poses
  { id: 'gen.stage', scope: 'generate', label: 'Queue', hint: 'add to the queue and run it later — Run now in the Dock', icon: Boxes, keys: 'Ctrl+Shift+Enter', placement: ['panel'], when: canSubmit,
    run: () => { const g = useGenerate.getState(); void (g.run === 'expand' ? g.expand(true) : g.generate(true)) } },
  // D115: the two ways to run
  { id: 'gen.run.generate', scope: 'generate', label: 'Run: Generate', hint: 'the prompt as written', icon: Wand2, placement: ['panel'], run: () => useGenerate.getState().setRun('generate') },
  { id: 'gen.run.expand', scope: 'generate', label: 'Run: Expand', hint: 'one image per pose chosen in the Poses section, the prompt\'s pose and action replaced', icon: Orbit, placement: ['panel'], run: () => useGenerate.getState().setRun('expand') },
  // P14 (D82): the Angle tab — the five moves are buttons on the pad; the verb has no key (Ctrl+Enter stays Generate's)
  { id: 'gen.angle.generate', scope: 'generate', label: 'New angle', icon: Orbit, placement: ['panel'], when: () => !!useGenerate.getState().angle.asset_id,
    run: () => void useGenerate.getState().generateAngle().then((jobs) => { if (jobs) useGenerate.setState({ angleOpen: false }) }) },   // D90: the sheet closes once queued
  { id: 'gen.angle.left45', scope: 'generate', label: 'Rotate left 45°', icon: RotateCcw, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'left45' }) },
  { id: 'gen.angle.right45', scope: 'generate', label: 'Rotate right 45°', icon: RotateCw, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'right45' }) },
  { id: 'gen.angle.topdown', scope: 'generate', label: 'Top-down', icon: ArrowDownFromLine, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'topdown' }) },
  { id: 'gen.angle.closeup', scope: 'generate', label: 'Close-up', icon: ZoomIn, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'closeup' }) },
  { id: 'gen.angle.wide', scope: 'generate', label: 'Wide', icon: ZoomOut, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'wide' }) },
  { id: 'gen.angle.clear', scope: 'generate', label: 'Remove the source', icon: X, placement: ['panel'], when: () => !!useGenerate.getState().angle.asset_id, run: () => useGenerate.getState().setAngle({ asset_id: null }) },
  { id: 'gen.savePreset', scope: 'generate', label: 'Save panel preset…', icon: Bookmark, keys: 'Ctrl+S', placement: ['panel'], run: () => { const g = useGenerate.getState(); void askText({ title: 'Save panel preset', text: 'Saves every field of the panel under this name; an existing preset of the same name is replaced.', initial: g.lastPreset ?? '', placeholder: 'preset name' }).then((n) => { if (n) void g.savePreset(n) }) } },
  // D90 (01 §11.2): the Foot's Fetch — Models & engine on the missing weights of the model picked
  { id: 'gen.fetchMissing', scope: 'generate', label: 'Fetch the missing weights…', icon: HardDriveDownload, placement: ['panel'], when: () => (useGenerate.getState().preview?.missing.length ?? 0) > 0, run: () => useSession.getState().openModels({ missing: true }) },
  // D93 (A1): a linked subject card's casting run — "Give <name> a look" / "More looks for <name>" (the card's button sets the card first)
  { id: 'gen.subject.cast', scope: 'generate', label: 'Give the character a look', icon: Sparkles, placement: ['panel'], hint: "the panel's images land as the linked character's candidates in Story · Cast",
    when: () => { const i = subjectItem.i, g = useGenerate.getState(); const pid = i !== undefined ? g.panel.tree.subjects?.[i]?.profile_id : undefined
      const o = pid ? castOffer(profilesForMentions().find((p) => p.id === pid), 0, g.panel.tree.subjects?.[i ?? -1]?.version) : null; return !!o && !o.disabled && g.panel.prompt_mode === 'tree' && !!useSession.getState().project?.open },
    run: () => { const i = subjectItem.i; if (i !== undefined) void useGenerate.getState().castLook(i) } },
  // D93 (B4): the sheet a linked card shows is Cast's — edited there (the card's "edit in Cast", the version chip's menu); every linked subject follows
  { id: 'gen.subject.editSheet', scope: 'generate', label: 'Edit the character sheet in Story · Cast', icon: PenLine, placement: ['panel', 'context'],
    hint: 'the appearance, outfit, bound colours and marks of the version this subject uses — every linked subject follows',
    when: () => { const i = subjectItem.i; return i !== undefined && !!useGenerate.getState().panel.tree.subjects?.[i]?.profile_id },
    run: () => { const i = subjectItem.i, s = i !== undefined ? useGenerate.getState().panel.tree.subjects?.[i] : undefined
      const p = s?.profile_id ? profilesForMentions().find((x) => x.id === s.profile_id) : undefined, v = versionOf(p, s?.version)
      if (!p || !v) return
      const focus = (n: number) => {                                         // the version page renders after Story loads: focus its appearance once it is there
        const el = document.getElementById('cast-appearance') as HTMLTextAreaElement | null
        if (el && document.querySelector('.cast-page h2')?.textContent?.includes(p.name)) el.focus()
        else if (n < 60) window.setTimeout(() => focus(n + 1), 50)
      }
      void import('../../store/origin').then((m) => { m.goToStory({ tab: 'cast', id: p.id, version: v.id }); focus(0) }) } },
  // D93 (C6): a held prop is put down (the holds ▸ menu, the chip's ✕); a linked place's sheet is Cast's (the scene's "edit in Cast", its chip's menu)
  { id: 'gen.subject.unhold', scope: 'generate', label: 'Put the prop down', icon: Hand, placement: ['panel', 'context'], hint: 'the subject holds nothing — its words and images leave the prompt',
    when: () => { const i = subjectItem.i; return i !== undefined && !!useGenerate.getState().panel.tree.subjects?.[i]?.holds },
    run: () => { const i = subjectItem.i; if (i !== undefined) useGenerate.getState().holdProp(i, null) } },
  { id: 'gen.scene.editSheet', scope: 'generate', label: 'Edit the place in Story · Cast', icon: PenLine, placement: ['panel', 'context'],
    hint: 'the look, colours and marks of the place the scene uses — the scene follows', when: () => !!useGenerate.getState().panel.tree.scene_link,
    run: () => { const l = useGenerate.getState().panel.tree.scene_link, p = l ? profilesForMentions().find((x) => x.id === l.profile_id) : undefined, v = versionOf(p, l?.version)
      if (p && v) void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: p.id, version: v.id })) } },
  { id: 'gen.clearRefs', scope: 'generate', label: 'Clear references', icon: Images, placement: ['context', 'panel'], when: () => useGenerate.getState().panel.refs.length > 0, run: () => { const g = useGenerate.getState(); [...g.panel.refs].forEach((r) => g.removeRef(r.asset_id)) } },
])

export function useGenerateKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'generate') return
      if ((e.target as HTMLElement | null)?.closest?.('.modal')) return     // D90: a modal (Models & engine) owns its keys
      handleKeyFor('generate', e)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}

// U1 (D157): the keys are the shell's (frame/keyHosts.tsx), not the Strip's
registerKeyHost('generate', function GenerateKeys() { useGenerateKeys(); return null })

export const GenerateSuite: SuiteDef = {
  id: 'generate',
  // D90 (02 §6.1): one column — the rail's buttons jump to its sections and follow the scroll (GenerateColumn)
  rail: [{ id: 'presets', label: 'Saved panels', icon: <Bookmark size={18} /> }, { id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'refs', label: 'References', icon: <Images size={18} /> },
    { id: 'look', label: 'Look', icon: <Palette size={18} /> }, { id: 'camera', label: 'Camera', icon: <Camera size={18} /> }, { id: 'model', label: 'Model', icon: <Boxes size={18} /> },
    { id: 'size', label: 'Size & count', icon: <SlidersHorizontal size={18} /> }, { id: 'poses', label: 'Poses', icon: <PersonStanding size={18} /> }],   // D115: the poses Expand runs
  Panel, Strip: withResults(Strip), Stage: withResults(Stage), Inspector: withResults(CatInspector),
  PrimaryAction, panelTitle: 'Image', PanelHead: ImageModeSwitch,   // D95 (IM1): Image's Make mode
}

export type { Asset, PanelState, Subject }
