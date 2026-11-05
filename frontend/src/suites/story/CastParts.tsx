// The Cast sheet's own sections, shared by Story's Cast page and World's Sheet (B2a, D159; proto01_UI2 11 §7): a prop's 3D model and its
// height (D110 PS2, CW4), a version's animation reference — front, back, and its test animation (CA0).
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { api, http, unwrap } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { command, markUsed, runCommand, type MenuItem } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { partRead } from './partRead'
import { partModel } from '../generate/generateStore'
import { latestModelJob, modelSource, modelStale, NOT_WHOLE, SEVERAL, sy } from './storyStore'

const ModelView = lazy(() => import('../stage/ModelView'))

/** D110 (PS2): a prop's 3D model — made from its animation reference (else its hero), stood upright, shown turning; Animate places it. */
export function PropModel({ p, v }: { p: Profile; v: Profile['versions'][number] }) {
  const jobs = useSession((s) => s.jobs)
  const mc = useSession((s) => s.capabilities?.mesh)
  const job = latestModelJob(jobs, p.id, v.id)
  const busy = !!job && !['done', 'failed', 'cancelled'].includes(job.status)
  const source = modelSource(v)
  const status = busy ? `making the model… ${Math.round((job!.progress ?? 0) * 100)} %${job!.progress_text ? ` · ${job!.progress_text}` : ''}`
    : job?.status === 'failed' && !v.model_asset_id ? `the last make failed: ${job.error ?? 'see the job'}`
    : v.model_asset_id && !v.model_from ? 'imported · Clay places it as it is'
    : !mc?.model_id ? (v.model_asset_id ? 'Clay places it in the scene' : 'import its model as a GLB — no image → 3D in this build')
    : !source ? 'give the prop an image first (its animation reference or a hero), or import a GLB'
    : modelStale(v) ? 'made from an older image — remake it from the current reference'
    : v.model_asset_id ? 'stood upright · Clay places it in the scene' : 'none yet'
  return (
    <section className="prop-model">
      <h3>3D model <Help text={`Every prop has a 3D model (D128): made once from ${v.anim_ref_asset_id ? 'the animation reference' : 'the hero'}, or imported as a GLB — Clay places it in the scene.`} /></h3>
      <div className="prop-model-row" onContextMenu={(e) => showMenu(e, [{ cmd: 'story.cast.makeModel' }, { cmd: 'story.cast.importModel' }, { cmd: 'story.cast.clearModel' }])}>
        {v.model_asset_id
          ? <Suspense fallback={<div className="model-view" />}><ModelView key={v.model_asset_id} assetId={v.model_asset_id} /></Suspense>
          : <div className="model-view empty"><span className="hint">{busy ? 'making…' : 'no model yet'}</span></div>}
        <div className="prop-model-side">
          <span className={`hint${modelStale(v) ? ' warn' : ''}`} data-status>{status}</span>
          <div className="verbs"><CommandButton id="story.cast.makeModel" text /><CommandButton id="story.cast.importModel" text /><CommandButton id="story.cast.clearModel" text /><CommandButton id="story.cast.bench" text /></div>
          <div className="kv prop-height"><span>height</span>{/* CW4 (03 §4): the model scaled to it in Animate */}
            <span><input type="number" key={`h${v.id}${v.height_m ?? ''}`} defaultValue={v.height_m ?? ''} min={0.01} max={100} step={0.05} disabled={v.state !== 'open'} aria-label="the prop's height in metres" placeholder="1.0"
              onBlur={(e) => { const t = e.target.value.trim(), h = t ? Number(t) : null; if (h !== (v.height_m ?? null) && (h === null || h > 0)) sy().setSheet({ height_m: h }) }}
              onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} /> m
              <Help text={"An image → 3D model comes out at no particular size: Clay scales it to this height (its bench and the line-up show a 1.75 m figure beside it); a flat thing — a letter, a rug, a map — to this length along its longest side. Prefilled from the prop's name and look — a cup 0.1 m, a door 2.1 m — else 1 m."} /></span></div>
        </div>
      </div>
    </section>
  )
}

type RefSlot = 'front' | 'back' | 'side' | 'hand' | 'feet'
const SLOT_MENU: Record<RefSlot, MenuItem[]> = {
  front: [{ cmd: 'story.cast.makeAnimRef' }, { cmd: 'story.cast.fitBody' }, { cmd: 'story.cast.clearAnimRef' }],
  back: [{ cmd: 'story.cast.makeAnimRefBack' }, { cmd: 'story.cast.clearAnimRefBack' }],
  side: [{ cmd: 'story.cast.makeAnimRefSide' }, { cmd: 'story.cast.sideAsFeet' }, { cmd: 'story.cast.clearAnimRefSide' }],
  hand: [{ cmd: 'story.cast.makeHandRef' }, { cmd: 'story.cast.readHand' }, { cmd: 'story.cast.clearHandRef' }],          // RG1
  feet: [{ cmd: 'story.cast.makeFeetRef' }, { cmd: 'story.cast.readFeet' }, { cmd: 'story.cast.clearFeetRef' }],
}
const SLOT_CLEAR: Record<RefSlot, string> = { front: 'story.cast.clearAnimRef', back: 'story.cast.clearAnimRefBack', side: 'story.cast.clearAnimRefSide',
  hand: 'story.cast.clearHandRef', feet: 'story.cast.clearFeetRef' }

/** CA0 → D161: the version's animation reference slots, the makes (runs: their pictures are candidates, `children` lists them to pick from)
 *  and a filled slot's ✕ (the picture stays a candidate). */
export function AnimRef({ p, v, children }: { p: Profile; v: Profile['versions'][number]; children?: ReactNode }) {
  const jobs = useSession((s) => s.jobs)
  const slot = (side: RefSlot, id: string | null | undefined, label: string) => {
    const read = side === 'hand' || side === 'feet' ? partRead(v, side, jobs, p.id) : null      // RG1: what the read of the picture says, in a few words
    return (
    <div className={`anim-ref-slot${id ? '' : ' empty'}`} data-side={side} data-read={read?.state}
      onContextMenu={(e) => showMenu(e, SLOT_MENU[side])}>
      {id ? <img src={api.thumbUrl(id, 512)} alt={label} /> : <span className="hint">{label}: none yet</span>}
      <span className="cell">{read && id ? `${label} · ${read.text}` : label}</span>
      {id && read?.state === 'failed' && <button type="button" className="link ref-note" data-note="part" title={read.note ?? ''}
        onClick={(e) => { e.stopPropagation(); runCommand(side === 'hand' ? 'story.cast.makeHandRef' : 'story.cast.makeFeetRef') }}>Not read — make candidates?</button>}
      {id && <span className="slot-clear"><CommandButton id={SLOT_CLEAR[side]} className="quiet" size={12} /></span>}
      {side === 'front' && id && v.anim_ref_note === 'arms_close' && <button type="button" className="link ref-note" data-note="arms_close"
        title="The body is fitted and the shell made only on an A-pose — the arms clear of the body, the fingers straight and spread (D139, D140): draw the reference again, then fit the body"
        onClick={(e) => { e.stopPropagation(); runCommand('story.cast.makeAnimRef') }}>The arms touch the body — draw it again?</button>}   {/* proto01_UIcast S8 */}
      {side === 'front' && id && v.anim_ref_note === 'not_whole' && <button type="button" className="link ref-note" data-note="not_whole" title={NOT_WHOLE}
        onClick={(e) => { e.stopPropagation(); runCommand('story.cast.makeAnimRef') }}>Not the whole figure — make candidates?</button>}   {/* W9 */}
      {side === 'front' && id && v.anim_ref_note === 'several' && <button type="button" className="link ref-note" data-note="several" title={SEVERAL}
        onClick={(e) => { e.stopPropagation(); runCommand('story.cast.makeAnimRef') }}>More than one figure — make candidates?</button>}   {/* W11 */}
      {side === 'front' && id && v.anim_ref_note === 't_pose' && <button type="button" className="link ref-note" data-note="t_pose"
        title="The arms are held level (a T-pose); the A-pose holds them about 30° out — the fit took it, but the shell and Wan Animate follow the arms as drawn"
        onClick={(e) => { e.stopPropagation(); runCommand('story.cast.makeAnimRef') }}>Arms level (a T-pose) — make candidates?</button>}   {/* W11 */}
    </div>
  ) }
  return (
    <section className="anim-ref">
      <h3>Animation reference <Help text={p.cls === 'prop' ? 'The prop alone, a three-quarter view, 16:9.' : 'Full body, A-pose, 16:9, plain ground — what Wan Animate is given.'} /></h3>
      <div className="anim-ref-row">
        {slot('front', v.anim_ref_asset_id, p.cls === 'prop' ? 'reference' : 'front')}
        {p.cls === 'character' && slot('back', v.anim_ref_back_asset_id, 'back (optional)')}
        {p.cls === 'character' && slot('side', v.anim_ref_side_asset_id, 'side (optional)')}
        {p.cls === 'character' && slot('hand', v.hand_ref_asset_id, 'hand')}{/* RG1 (D187, D188) */}
        {p.cls === 'character' && slot('feet', v.feet_ref_asset_id, 'feet')}
        {p.cls === 'character' && <AnimTestSlot clipId={v.anim_test_clip_id ?? null} />}
        <div className="verbs">
          <CommandButton id="story.cast.makeAnimRef" text label={withRun('story.cast.makeAnimRef', 2)} />
          {p.cls === 'character' && <CommandButton id="story.cast.makeAnimRefBack" text label={withRun('story.cast.makeAnimRefBack', 2)} />}
          {p.cls === 'character' && <CommandButton id="story.cast.makeAnimRefSide" text label={withRun('story.cast.makeAnimRefSide', 2)} />}
          {p.cls === 'character' && <CommandButton id="story.cast.makeHandRef" text label={withRun('story.cast.makeHandRef', 2)} />}
          {p.cls === 'character' && <CommandButton id="story.cast.makeFeetRef" text label={withRun('story.cast.makeFeetRef', 2)} />}
          {p.cls === 'character' && <CommandButton id="story.cast.testAnimRef" text />}
        </div>
      </div>
      {children}
    </section>
  )
}

/** W10: a run button says what it queues before it does — the model, how many, the time with the model warm. D190: a hand or feet picture
 *  runs on World's Make column card (any text-to-image model), named here; the time is said for the measured model only. */
function withRun(id: string, n: number): string | undefined {
  const caps = useSession.getState().capabilities, label = command(id)?.label, st = caps?.story
  if (!label || !st?.model_id) return undefined
  const part = id === 'story.cast.makeHandRef' || id === 'story.cast.makeFeetRef' ? partModel() : null
  if (part && part !== st.model_id) return `${label} · ${caps?.models[part]?.label ?? part} · ${n}`
  const s = (st.seconds ?? 0) * n
  return `${label} · ${st.short ?? st.label ?? st.model_id} · ${n} · ${s ? `≈ ${s < 90 ? `${Math.round(s)} s` : `${Math.round(s / 60)} min`}` : 'time unknown'}`
}

/** CA0: the version's latest test animation (a turn on the spot) — its first frame, played in Animate. */
function AnimTestSlot({ clipId }: { clipId: string | null }) {
  const [got, setGot] = useState<{ clip: string; asset: string | null } | null>(null)   // the clip's first-frame asset, keyed by the clip it belongs to
  useEffect(() => {
    let live = true
    if (clipId) void unwrap(http.GET('/clips/{clip_id}', { params: { path: { clip_id: clipId } } })).then((c) => { if (live) setGot({ clip: clipId, asset: c.asset_id ?? null }) }).catch(() => undefined)
    return () => { live = false }
  }, [clipId])
  const thumb = got && got.clip === clipId ? got.asset : null
  markUsed('story.cast.playAnimTest')
  return (
    <div className={`anim-ref-slot${clipId ? '' : ' empty'}`} data-side="test" onDoubleClick={() => runCommand('story.cast.playAnimTest')}
      onContextMenu={(e) => showMenu(e, [{ cmd: 'story.cast.playAnimTest' }, { cmd: 'story.cast.testAnimRef' }])}>
      {thumb ? <img src={api.thumbUrl(thumb, 512)} alt="the test animation" /> : <span className="hint">{clipId ? 'the test clip' : 'test: none yet'}</span>}
      <span className="cell">test · a turn{clipId ? ' — right-click to play' : ''}</span>
    </div>
  )
}
