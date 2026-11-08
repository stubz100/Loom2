// U4 (D157, proto01_UI2 04 §2.1): the shot header — the shot and its version, the description, the lines, the scene (its stage, the shot's
// camera, its range) and the cast standing on the stage, each cast member with what it still lacks for Clay (a click opens it in World).
import { lazy, Suspense, useEffect, useState } from 'react'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import type { MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { navigate } from '../../frame/router'
import { useStory } from '../../suites/story/storyStore'
import { lineSpans, linesOutlast } from '../../suites/stage/tracks'
import { useWorld } from '../world/worldStore'
import { api } from '../../api/client'
import { animaticState, cameraUsers, castOf, extendRange, rescene, setRange, useRouteRows, useShotStage, type CastMember } from './scene'
import { flushClay, METHOD_LABEL, METHODS, newestFinal, recordInClay, setShotMethod, useShots } from './shotsStore'
import { ShotWords } from './ShotWords'
import type { Shot, ShotVersion } from '../../api/types'

const LinesEditor = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.LinesEditor })))

/** A cast member's World page (its class's rail, the entity and the version the stage wears). */
function openInWorld(m: CastMember): void {
  if (!m.profile) return
  navigate({ suite: 'generate' })                                          // World's Make; the layer follows
  useWorld.getState().pick(m.profile, m.version)
}

export function RangeField({ start, end, fps, whole }: { start: number; end: number; fps: number; whole: boolean }) {
  const [a, setA] = useState<string | null>(null), [b, setB] = useState<string | null>(null)
  const commit = () => {
    if (a === null && b === null) return                                  // review K95: a blur without typing pinned the stage's range on the shot
    const s = Number(a ?? start), e = Number(b ?? end)
    setA(null); setB(null)
    if (Number.isFinite(s) && Number.isFinite(e) && 0 <= s && s <= e && (s !== start || e !== end || whole)) void setRange({ start: Math.round(s), end: Math.round(e) })
  }
  const key = (ev: React.KeyboardEvent) => { if (ev.key === 'Enter') (ev.target as HTMLInputElement).blur() }
  return (
    <span className="s-range" data-testid="shots-range">
      <input type="number" min={0} aria-label="range start" value={a ?? start} onChange={(e) => setA(e.target.value)} onBlur={commit} onKeyDown={key} />–
      <input type="number" min={0} aria-label="range end" value={b ?? end} onChange={(e) => setB(e.target.value)} onBlur={commit} onKeyDown={key} />
      <span className="w-val">{((end - start) / fps).toFixed(1)} s{whole ? ' · the stage\'s range' : ''}</span>
      {!whole && <button className="link" title="Back to the stage's whole range" onClick={() => void setRange(null)}>whole</button>}
    </span>
  )
}

/** C3 (D181, 04 §4.3–4.4; Q6): the animatic row — ▶ plays it here, its frames, when it was recorded, current or stale since the scene
 *  changed; Record ▸ (again) opens the scene in Clay's Record mode. */
function AnimaticRow({ a, stage, open }: { a: NonNullable<ShotVersion['animatic']> | null; stage: { id: string; revision: number } | null; open: boolean }) {
  const [playing, setPlaying] = useState(false)
  const state = animaticState(a, stage)
  const when = a ? new Date(a.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''
  return (
    <span className="s-animatic" data-testid="shots-animatic" data-state={state}>
      {a ? <>
        <button className="link" disabled={!a.asset_id} title={playing ? 'Stop' : 'Play the animatic here'} onClick={() => setPlaying(!playing)}>{playing ? '■' : '▶'} {a.frames} frames</button>
        <span className="w-val">· recorded {when} · </span><span className={state === 'stale' ? 's-stale' : 'w-val'}>{state === 'stale' ? 'stale since the scene changed' : 'current'}</span>
      </> : <span className="w-val">none yet</span>}
      {open && <button className="link" onClick={() => void recordInClay()} title="Clay's Record mode on the shot's scene: Record ▶ writes the animatic">{a ? 'Record again ▸' : 'Record ▸'}</button>}
      {playing && a?.asset_id && <video className="s-animatic-player" src={api.assetUrl(a.asset_id)} controls autoPlay loop />}
    </span>
  )
}

/** C4 (D181, 04 §4.4; Q8): the ledger's *performance* row — the method (▾ sets it), the take in use with its identity, what the final owes;
 *  Perform ▶ with its minutes, takes ▸ (the Performance level, its editor beneath). */
function PerformanceRow({ v, open }: { v: ShotVersion; open: boolean }) {
  const clip = useStory((st) => (v.clip_id ? st.clipsById[v.clip_id] : undefined))
  const owed = useShots((x) => x.owed)
  const method = (v.method ?? 'layered') as keyof typeof METHOD_LABEL
  const ident = clip?.identity && typeof (clip.identity as { mean?: unknown }).mean === 'number' ? ` · identity ${((clip.identity as { mean: number }).mean).toFixed(2)}` : ''
  const take = clip ? `${clip.model_id === 'composition' ? 'the render' : 'take'} · ${clip.frames} f at ${clip.fps} fps${ident}` : v.clip_id ? 'a take' : 'no take yet'
  const items = (): MenuItem[] => METHODS.map((m) => ({ label: METHOD_LABEL[m], checked: method === m, disabled: !open, run: () => void setShotMethod(m) }))
  return (
    <span className="s-ledger" data-testid="shots-row-performance" data-method={method}>
      <MenuButton label={METHOD_LABEL[method]} items={items} text />
      <span className="w-val">· {take}{owed?.queued ? ` · ${owed.queued} owed` : ''}</span>
      {owed?.queued ? <CommandButton id="shots.performOwed" text label={`Perform ▶ · ≈ ${owed.minutes} min`} /> : null}
      <button className="link" onClick={() => useShots.getState().setLevel('performance')} title="The Performance level: the takes, the method's card, the clips">takes ▸</button>
    </span>
  )
}

/** C4 (04 §4.4): the ledger's *final* row — the newest final made for the version (its layers, its assembly), the render as the shot's clip,
 *  marked or not; Render ▶ and open the composition ▸ at the Final level, Mark final ✓. */
function FinalRow({ s, v, open }: { s: Shot; v: ShotVersion; open: boolean }) {
  const finals = useStory((st) => st.boardFinals)
  const clip = useStory((st) => (v.clip_id ? st.clipsById[v.clip_id] : undefined))
  const f = newestFinal(finals as { id: string; shot_id?: string | null; shot_version?: string | null; created_at: string; revision?: number; layers: { status: string }[]; clip_id: string | null; assembled_at?: string | null }[], s.id, v.id)
  const rendered = clip && clip.model_id === 'composition' ? `rendered ${new Date(clip.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · ${clip.w}×${clip.h}` : null
  const fact = rendered ?? (f ? (f.clip_id ? 'assembled, not rendered' : `${f.layers.filter((l) => l.status === 'done').length} / ${f.layers.length} layers`) : 'no final yet')
  const marked = v.state === 'final'
  return (
    <span className="s-ledger" data-testid="shots-row-final" data-state={marked ? 'marked' : rendered ? 'rendered' : f ? 'made' : 'none'}>
      <span className="w-val">{fact} · {marked ? 'marked final ✓' : 'not marked'}</span>
      <button className="link" onClick={() => useShots.getState().setLevel('final')} title={f ? "The Final level: the composition's layers, blends and mattes; Render the finished shot ▶" : 'The Final level — Performance makes the final shot first'}>{f ? 'open the composition ▸' : 'Final ▸'}</button>
      {open && v.clip_id && !marked && <CommandButton id="story.shot.finalize" text label="Mark final ✓" />}
    </span>
  )
}

export function ShotHeader() {
  const s = useStory((st) => st.shot())
  const v = useStory((st) => st.shotVersion())
  const node = useStory((st) => { const sh = st.shot(); return sh?.owner_node ? st.flowNodes[sh.owner_node] : undefined })
  const shots = useStory((st) => st.shots)
  const profiles = useStory((st) => st.profiles)
  const route = useRouteRows()
  const stage = useShotStage(v?.stage_id ?? null)
  const scene = useStory((st) => (node?.scene_id ? st.scenes.find((x) => x.id === node.scene_id) : undefined))   // W26: the Flow's scene, the one the Inspector names
  const level = useShots((x) => x.level)
  const secs = useStory((st) => st.audioSecs)
  useEffect(() => { const ids = (node?.lines ?? []).map((l) => l.audio_asset_id).filter((x): x is string => !!x); if (ids.length) void useStory.getState().loadAudioSecs(ids) }, [node])
  if (!s || !v) return <div className="w-head"><span className="w-empty">Pick a shot on the storyboard, or make one</span></div>
  const at = route.findIndex((x) => x.shot.id === s.id)
  const r = at >= 0 ? route[at] : undefined
  const before = at > 0 ? route[at - 1] : undefined
  const open = v.state === 'open'
  const shotMenu = (): MenuItem[] => route.map((x) => ({ label: `${x.n} · ${x.label}`, checked: x.shot.id === s.id, run: () => useShots.getState().open(x.shot.id) }))
  const versions = (): MenuItem[] => [...s.versions.map((x) => ({ label: `${x.id}${x.state === 'final' ? ' · final' : ''}`, checked: x.id === v.id, run: () => useStory.getState().selectShot(s.id, x.id) })),
    { sep: true }, { cmd: 'story.shot.newVersion' }, { cmd: 'story.shot.finalize' }]
  const places = profiles.filter((p) => p.cls === 'place')
  const sceneMenu = (): MenuItem[] => [
    { cmd: 'shots.scene.new' },
    { label: before ? `Same scene as ${before.n} · ${before.label}` : 'Same scene as the shot before', disabled: !open || !before?.v.stage_id, run: () => void rescene('same', { like: before?.node?.id }).then(() => useShots.getState().reopen()) },
    ...(places.length ? [{ label: 'A new scene at a World place', items: places.map((p): MenuItem => ({ label: p.name, disabled: !open, run: () => void rescene('new', { place_id: p.id }).then(() => useShots.getState().reopen()) })) }] : []),
  ]
  const users = stage ? cameraUsers(stage.id, shots) : {}
  const camMenu = (): MenuItem[] => (stage?.cameras ?? []).map((c) => ({
    label: `${c.name}${users[c.id] && users[c.id] !== s.name ? ` · ${users[c.id]}'s (a copy is made)` : ''}`, checked: c.id === v.camera_id, disabled: !open,
    run: () => void flushClay().then(() => useStory.getState().linkStage(s.id, v.id, stage!.id, c.id)).then(() => useShots.getState().reopen()) }))
  const cam = stage?.cameras.find((c) => c.id === v.camera_id)
  const cast = stage ? castOf(stage, profiles) : []
  const range = (v.range ?? stage?.range) as { start: number; end: number } | undefined
  // F39 (U5d): the lines outlast the shot — say so, and extend the range to them only when asked (the range never moves by itself)
  const fps = stage?.fps ?? 24
  const need = range && node ? linesOutlast(lineSpans(node.lines, secs, range.start, fps), range) : null
  return (
    <div className="w-head" data-testid="shots-header">
      <div className="w-head-row"><MenuButton label={r ? `${r.n} · ${r.label}` : node?.title || s.name} items={shotMenu} text /><MenuButton label={`${v.id}${v.state === 'final' ? ' · final' : ''}`} items={versions} text /></div>
      {node && <label className="w-field"><span>description</span><textarea rows={2} value={node.text} aria-label="description" placeholder="what happens"
        onChange={(e) => void useStory.getState().patchNode(node.id, { text: e.target.value })} /></label>}
      {node && <div className="w-field stack"><span>lines</span><div className="s-lines"><Suspense fallback={null}><LinesEditor n={node} /></Suspense></div></div>}
      <div className="w-field"><span>scene</span>
        {v.stage_id ? <span className="s-scene" data-testid="shots-scene">
          <span title={scene && stage && scene.name !== stage.name ? `the scene ${scene.name}, on the stage ${stage.name}` : undefined}><MenuButton label={scene?.name ?? stage?.name ?? 'the stage'} items={sceneMenu} text /></span>
          <MenuButton label={cam?.name ?? 'no camera'} items={camMenu} text />
          {range && stage && <RangeField start={range.start} end={range.end} fps={stage.fps} whole={!v.range} />}
          {need !== null && range && <span className="s-outlast" data-testid="shots-outlast">the lines run {((need - range.start + 1) / fps).toFixed(1)} s, the shot {((range.end - range.start + 1) / fps).toFixed(1)} s
            {open && <button className="link" title="The shot's range to the lines' end — the scene lengthened first when they run past it (C3)" onClick={() => void extendRange({ start: range.start, end: need }, stage)}>Extend to the lines</button>}</span>}
        </span> : <span className="w-val">{scene ? `${scene.name} — no stage yet` : 'no scene yet'} <MenuButton label={scene ? 'Give it a stage' : 'Give it a scene'} items={sceneMenu} text /></span>}
      </div>
      {stage && <div className="w-field"><span>cast <Help text="What stands on the shot's stage, from World: add a figure or a prop in Clay's Scene section. A member that is not ready for Clay says what it lacks; a click opens it in World." /></span>
        <span className="s-cast" data-testid="shots-cast">{cast.length ? cast.map((m) => (
          <button key={m.id} className={`s-member${m.owed ? ' owed' : ''}`} disabled={!m.profile} title={m.profile ? `${m.line} — open in World` : m.line} onClick={() => openInWorld(m)}>
            {m.name}{m.owed ? <span className="s-owed"> · {m.line}</span> : m.profile ? null : <span className="s-owed"> · unbound</span>}
          </button>)) : <span className="w-val">nobody yet</span>}
          {open && level !== 'clay' && <CommandButton id="shots.level.clay" text label="Add in Clay ▸" />}
        </span>
      </div>}
      {v.stage_id && <div className="w-field"><span>performance <Help text="How the moving picture is made — Layered (the scene split into layers, each character performed and matted), One pass (the stage's sequence animated from a still), From the start still — the take in use and what the final still owes. ▾ sets the method; takes ▸ opens the Performance level." /></span>
        <PerformanceRow v={v} open={open} /></div>}{/* C4 (04 §4.4): the ledger */}
      {v.stage_id && <div className="w-field"><span>final <Help text="The newest final made for this version — its layers, its assembly, the render as the shot's clip — and whether the shot is marked final (the Flow and the Episode bind that clip)." /></span>
        <FinalRow s={s} v={v} open={open} /></div>}
      {v.stage_id && <div className="w-field"><span>animatic <Help text="Record ▶ in Clay's Record mode writes the scene's lit clay through the shot's camera over its range as a clip, on the CPU: the storyboard plays it and Episode cuts it until a performance replaces it. Stale: the scene changed since it was recorded." /></span>
        <AnimaticRow a={v.animatic ?? null} stage={stage ? { id: stage.id, revision: stage.revision } : null} open={open} /></div>}{/* C3 (D181) */}
      <ShotWords stageRev={stage?.revision} />
    </div>
  )
}
