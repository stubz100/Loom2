// The Cast sheet's own sections, shared by Story's Cast page and World's Sheet (B2a, D159; proto01_UI2 11 §7): a prop's 3D model and its
// height (D110 PS2, CW4), a version's animation reference — front, back, and its test animation (CA0).
import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { api, http, unwrap } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { latestModelJob, modelSource, modelStale, sy } from './storyStore'

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
    : v.model_asset_id && !v.model_from ? 'imported · Animate places it as it is'
    : !mc?.model_id ? (v.model_asset_id ? 'Animate places it in the scene' : 'import its model as a GLB — no image → 3D in this build')
    : !source ? 'give the prop an image first (its animation reference or a hero), or import a GLB'
    : modelStale(v) ? 'made from an older image — remake it from the current reference'
    : v.model_asset_id ? 'stood upright · Animate places it in the scene' : 'none yet'
  return (
    <section className="prop-model">
      <h3>3D model <Help text={`Every prop has a 3D model (D128): made once from ${v.anim_ref_asset_id ? 'the animation reference' : 'the hero'}, or imported as a GLB — Animate places it in the scene.`} /></h3>
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
              <Help text={"An image → 3D model comes out at no particular size: Animate scales it to this height (its bench and the line-up show a 1.75 m figure beside it). Prefilled from the prop's name and look — a cup 0.1 m, a door 2.1 m — else 1 m."} /></span></div>
        </div>
      </div>
    </section>
  )
}

/** CA0 → D161: the version's animation reference slots, the makes (runs: their pictures are candidates, `children` lists them to pick from)
 *  and a filled slot's ✕ (the picture stays a candidate). */
export function AnimRef({ p, v, children }: { p: Profile; v: Profile['versions'][number]; children?: ReactNode }) {
  const slot = (side: 'front' | 'back', id: string | null | undefined, label: string) => (
    <div className={`anim-ref-slot${id ? '' : ' empty'}`} data-side={side}
      onContextMenu={(e) => showMenu(e, side === 'back' ? [{ cmd: 'story.cast.makeAnimRefBack' }, { cmd: 'story.cast.clearAnimRefBack' }] : [{ cmd: 'story.cast.makeAnimRef' }, { cmd: 'story.cast.fitBody' }, { cmd: 'story.cast.clearAnimRef' }])}>
      {id ? <img src={api.thumbUrl(id, 512)} alt={label} /> : <span className="hint">{label}: none yet</span>}
      <span className="cell">{label}</span>
      {id && <span className="slot-clear"><CommandButton id={side === 'back' ? 'story.cast.clearAnimRefBack' : 'story.cast.clearAnimRef'} className="quiet" size={12} /></span>}
      {side === 'front' && id && v.anim_ref_note === 'arms_close' && <button type="button" className="link ref-note" data-note="arms_close"
        title="The body is fitted and the shell made only on an A-pose — the arms clear of the body, the fingers straight and spread (D139, D140): draw the reference again, then fit the body"
        onClick={(e) => { e.stopPropagation(); runCommand('story.cast.makeAnimRef') }}>The arms touch the body — draw it again?</button>}   {/* proto01_UIcast S8 */}
    </div>
  )
  return (
    <section className="anim-ref">
      <h3>Animation reference <Help text={p.cls === 'prop' ? 'The prop alone, a three-quarter view, 16:9.' : 'Full body, A-pose, 16:9, plain ground — what Wan Animate is given.'} /></h3>
      <div className="anim-ref-row">
        {slot('front', v.anim_ref_asset_id, p.cls === 'prop' ? 'reference' : 'front')}
        {p.cls === 'character' && slot('back', v.anim_ref_back_asset_id, 'back (optional)')}
        {p.cls === 'character' && <AnimTestSlot clipId={v.anim_test_clip_id ?? null} />}
        <div className="verbs">
          <CommandButton id="story.cast.makeAnimRef" text />
          {p.cls === 'character' && <CommandButton id="story.cast.makeAnimRefBack" text />}
          {p.cls === 'character' && <CommandButton id="story.cast.testAnimRef" text />}
        </div>
      </div>
      {children}
    </section>
  )
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
