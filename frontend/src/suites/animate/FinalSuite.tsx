// D121 (proto01_animate 26 §5.4): Animate's Final level as a mode of its own — its column (Shot · Layers · Output), its strip, the viewer
// (FinalViewer: the composition's frames, its transport and lanes) and its foot (Render the finished shot ▶). ArtCraft's Record mode is the
// model: the picture, the lanes and one verb. The Shot section opens a final of the stage; Layers is AE2–AE4's editor; Output says what was
// rendered and from which revision. Keys: Final's reach (animateCommands.ts) — its own commands, the mode keys, the Shot head's and the one
// transport (the composition's here); Performance's player keys stay off.
import { useEffect } from 'react'
import { AnimateLevels, GraphPill } from '../../frame/AnimateLevels'
import { handleKeysAt, markUsed, runCommand } from '../../frame/commands'
import { inField } from '../../frame/fieldKeys'
import { Help } from '../../frame/Help'
import { DEFAULT_RAIL } from '../../frame/railTabs'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { useSession } from '../../store/session'
import { rendering, useFinals, useFinalsPoll } from '../stage/finalShot'
import { RenderSettingsBlock } from './RenderSettingsBlock'
import { ShotHead } from '../stage/ShotStepper'
import { st, useStage } from '../stage/stageStore'
import { AnimColumn, Sec } from './column'
import { useComposition } from './compositionStore'
import { LayersSection } from './FinalEditor'
import { FinalViewer } from './FinalViewer'
import './animate.css'
import { registerKeyHost } from '../../frame/keyHosts'

const FINAL_SECTIONS = ['shot', 'layers', 'output'] as const

/** The stage's finals, one to open — under the Shot head's stage and steps (Performance › Final shot makes them). */
function FinalPicker() {
  const current = useStage((s) => s.current)
  const finals = useFinals((s) => s.finals)
  const comps = useFinals((s) => s.compositions)
  const open = useComposition((s) => s.finalId)
  useFinalsPoll(current?.id)                                                       // a render's clip lands (one poll for every view of the finals)
  return (
    <div className="final-picker">
      {current && !finals.length && <span className="hint">No final shot on this stage. <Help text="Performance › Final shot makes one: the scene split into layers, performed, matted and assembled; Make the composition, then Open it here." /></span>}
      {finals.map((f) => {
        const c = comps[f.id] ?? null
        const on = open === f.id
        return (
          <div key={f.id} className={`final-pick${on ? ' active' : ''}`} data-pick={f.id}>
            <span className="name">{f.name}</span>
            <span className="meta">{f.frames} f @ {f.rate} · {c ? `revision ${c.revision}${c.stale ? ' · stale' : ''}` : f.assembled_at ? 'no composition yet' : 'not assembled'}</span>
            {c ? <button type="button" className={on ? 'quiet' : ''} disabled={on} onClick={() => useFinals.getState().openFinal(f.id)} title={on ? 'Open here' : `${f.name}'s composition in the viewer`}>{on ? 'open' : 'Open'}</button>
              : f.assembled_at ? <button type="button" onClick={() => void useFinals.getState().compose(f.id)} title="An EffectCraft composition beside the final: the shot to finish here">Make the composition</button> : null}
          </div>
        )
      })}
    </div>
  )
}

/** What the open final renders to, and from which revision; Play and Make the composition again. */
function OutputSection() {
  const fid = useComposition((s) => s.finalId)
  const final = useComposition((s) => s.final)
  const own = useComposition((s) => s.comp)
  const polled = useFinals((s) => (fid ? s.compositions[fid] ?? null : null))          // the poll sees the render's clip land
  const f = useFinals((s) => s.finals.find((x) => x.id === fid))
  useSession((s) => s.jobs)                                                            // re-render as the render job moves
  if (!fid || !final) return <span className="hint">No final open.</span>
  const comp = polled ?? own
  const busy = rendering(fid)
  return (
    <div className="final-output" data-output={fid}>
      <div className="kv"><span>shot</span><span>{final.frames} frames at {final.rate} fps · {final.size.w}×{final.size.h}</span></div>
      <div className="kv"><span>composition</span><span>{comp ? `revision ${comp.revision}${comp.stale ? ' · stale: the final changed' : ''}` : 'none'}</span></div>
      <div className="kv"><span>render</span><span data-render-state>{busy ? 'rendering…' : comp?.clip_id ? `rendered at revision ${comp.rendered_revision}` : 'not rendered yet'}
        <Help text="effectcraft-cli renders the composition on the CPU with the settings below (RIFE to 24 fps at F16); the clip becomes the final's and a take on its shot." /></span></div>
      {f && <RenderSettingsBlock f={f} />}
      <div className="verbs">
        {f?.clip_id && <button type="button" className="quiet" data-play onClick={() => useFinals.getState().play(fid)} title="The final's clip in the Performance player">Play ▶</button>}
        {f?.assembled_at && <button type="button" className="quiet" onClick={() => void useFinals.getState().compose(fid)} title="Write the composition afresh from the layers and the assembly (the edits are dropped)">Make the composition again</button>}
      </div>
    </div>
  )
}

function FinalColumn({ tab }: { tab: string }) {
  const project = useSession((s) => s.project)
  useEffect(() => { if (project?.open) void st().load() }, [project?.open, project?.path])   // the stages for the Shot head's picker
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  return (
    <AnimColumn suite="final" sections={FINAL_SECTIONS} tab={tab}>
      <Sec id="shot" title="Shot"><ShotHead /><FinalPicker /></Sec>
      <Sec id="layers" title="Layers"><LayersSection /></Sec>
      <Sec id="output" title="Output"><OutputSection /></Sec>
    </AnimColumn>
  )
}

/** The Final level's keys: its reach (animateCommands.ts) — its own commands (anim.final.*), the mode keys, the Shot head's and the one
 *  transport (it runs the composition's here, AW2). */
function useFinalKeys(): void {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'final') return
      if (document.querySelector('.ctx-menu')) return                     // an open menu owns the arrows, Space and Enter
      if (inField(e)) return
      if (handleKeysAt('final', e)) e.stopImmediatePropagation()
    }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [])
}

// U1 (D157): the keys are the shell's (frame/keyHosts.tsx), not the Strip's
registerKeyHost('final', function FinalKeys() { useFinalKeys(); return null })

function FinalStrip() {
  const final = useComposition((s) => s.final)
  return (
    <>
      <AnimateLevels /><GraphPill />
      <span className="spacer" />
      {final && <span className="hint" data-final-name>{final.name} · {final.size.w}×{final.size.h} @ {final.rate} fps</span>}
    </>
  )
}

/** The foot: Render the finished shot ▶ (Ctrl+Enter), with why it cannot run. */
function FinalFoot() {
  const fid = useComposition((s) => s.finalId)
  const comp = useComposition((s) => s.comp)
  const polled = useFinals((s) => (fid ? s.compositions[fid] ?? null : null))
  useSession((s) => s.jobs)
  markUsed('anim.final.render')
  const busy = fid ? rendering(fid) : false
  const c = polled ?? comp
  const reason = !fid ? 'open a final in the Shot section' : !comp ? 'no composition yet' : busy ? 'rendering…' : null
  return (
    <div>
      <button className="primary" disabled={!!reason} onClick={() => runCommand('anim.final.render')} title="effectcraft-cli renders the composition on the CPU with the Output section's settings; the clip becomes the final's and a take on its shot (Ctrl+Enter)">
        {busy ? 'Rendering…' : c?.clip_id ? 'Render again ▶' : 'Render the finished shot ▶'}</button>
      <div className="estimate">{reason ? <span style={{ color: 'var(--fg3)' }}>{reason}</span> : <span>{c?.clip_id ? `rendered at revision ${c.rendered_revision} · now at ${c.revision}` : `revision ${c?.revision ?? 0} · on the CPU`}</span>}</div>
    </div>
  )
}

export const FinalSuite: SuiteDef = {
  id: 'final',
  rail: DEFAULT_RAIL.final,
  Panel: FinalColumn, Strip: FinalStrip, Stage: FinalViewer, Inspector: () => null, PrimaryAction: FinalFoot, noInspector: true, panelTitle: 'Animate',
}
