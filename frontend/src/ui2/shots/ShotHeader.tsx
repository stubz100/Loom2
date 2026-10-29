// U4 (D157, proto01_UI2 04 §2.1): the shot header — the shot and its version, the description, the lines, the scene (its stage, the shot's
// camera, its range) and the cast standing on the stage, each cast member with what it still lacks for Clay (a click opens it in World).
import { lazy, Suspense, useState } from 'react'
import { CommandButton, MenuButton } from '../../frame/CommandButton'
import type { MenuItem } from '../../frame/commands'
import { Help } from '../../frame/Help'
import { navigate } from '../../frame/router'
import { useStory } from '../../suites/story/storyStore'
import { useWorld } from '../world/worldStore'
import { cameraUsers, castOf, rescene, setRange, useRouteRows, useShotStage, type CastMember } from './scene'
import { flushClay, useShots } from './shotsStore'

const LinesEditor = lazy(() => import('../../suites/story/StoryParts').then((m) => ({ default: m.LinesEditor })))

/** A cast member's World page (its class's rail, the entity and the version the stage wears). */
function openInWorld(m: CastMember): void {
  if (!m.profile) return
  navigate({ suite: 'generate' })                                          // World's Make; the layer follows
  useWorld.getState().pick(m.profile, m.version)
}

function RangeField({ start, end, fps, whole }: { start: number; end: number; fps: number; whole: boolean }) {
  const [a, setA] = useState<string | null>(null), [b, setB] = useState<string | null>(null)
  const commit = () => {
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

export function ShotHeader() {
  const s = useStory((st) => st.shot())
  const v = useStory((st) => st.shotVersion())
  const node = useStory((st) => { const sh = st.shot(); return sh?.owner_node ? st.flowNodes[sh.owner_node] : undefined })
  const shots = useStory((st) => st.shots)
  const profiles = useStory((st) => st.profiles)
  const route = useRouteRows()
  const stage = useShotStage(v?.stage_id ?? null)
  const level = useShots((x) => x.level)
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
  const range = v.range ?? stage?.range
  return (
    <div className="w-head" data-testid="shots-header">
      <div className="w-head-row"><MenuButton label={r ? `${r.n} · ${r.label}` : node?.title || s.name} items={shotMenu} text /><MenuButton label={`${v.id}${v.state === 'final' ? ' · final' : ''}`} items={versions} text /></div>
      {node && <label className="w-field"><span>description</span><textarea rows={2} value={node.text} aria-label="description" placeholder="what happens"
        onChange={(e) => void useStory.getState().patchNode(node.id, { text: e.target.value })} /></label>}
      {node && <div className="w-field stack"><span>lines</span><div className="s-lines"><Suspense fallback={null}><LinesEditor n={node} /></Suspense></div></div>}
      <div className="w-field"><span>scene</span>
        {v.stage_id ? <span className="s-scene" data-testid="shots-scene">
          <MenuButton label={stage?.name ?? 'the stage'} items={sceneMenu} text />
          <MenuButton label={cam?.name ?? 'no camera'} items={camMenu} text />
          {range && stage && <RangeField start={range.start} end={range.end} fps={stage.fps} whole={!v.range} />}
        </span> : <span className="w-val">no scene yet <MenuButton label="Give it a scene" items={sceneMenu} text /></span>}
      </div>
      {stage && <div className="w-field"><span>cast <Help text="What stands on the shot's stage, from World: add a figure or a prop in Clay's Scene section. A member that is not ready for Clay says what it lacks; a click opens it in World." /></span>
        <span className="s-cast" data-testid="shots-cast">{cast.length ? cast.map((m) => (
          <button key={m.id} className={`s-member${m.owed ? ' owed' : ''}`} disabled={!m.profile} title={m.profile ? `${m.line} — open in World` : m.line} onClick={() => openInWorld(m)}>
            {m.name}{m.owed ? <span className="s-owed"> · {m.line}</span> : m.profile ? null : <span className="s-owed"> · unbound</span>}
          </button>)) : <span className="w-val">nobody yet</span>}
          {open && level !== 'clay' && <CommandButton id="shots.level.clay" text label="Add in Clay ▸" />}
        </span>
      </div>}
    </div>
  )
}
