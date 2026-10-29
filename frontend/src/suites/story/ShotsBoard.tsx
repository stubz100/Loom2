// D125 (proto01_UIcomp 04 §3.1; SP3): the Shots board — every shot in the Flow's order against its steps (board.ts reads their states from
// the records), a Choice's branches as group rows. A cell is its verb: a click runs the step for that shot (storyCommands.runStep), a
// right-click gives the shot's menu. The selected row's shot page sits under the board (StoryParts' ShotBoard).
import { Fragment, useEffect, useMemo, useState } from 'react'
import { api, http, unwrap } from '../../api/client'
import { runCommand } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { STEPS, SORT_LABEL, arrange, cellsOf, flowOrder, lengthLine, madeFinal, routeOf, ROUTE_LABEL, staleFrom, type BoardSort, type Cell, type Step } from './board'
import type { ShotCard } from '../../api/types'
import { runStep, shotMenu, STEP_VERB } from './storyCommands'
import { linesToVoice } from './episodeVerbs'
import { CommandButton } from '../../frame/CommandButton'
import { sy, useStory, type BoardFilter } from './storyStore'

const GLYPH: Record<Cell['state'], string> = { done: '✓', owed: '○', running: '◐', stale: '!', na: '–' }
const ACTIVE = ['staged', 'queued', 'running']
const FRAME_KINDS = ['t2i', 'i2i', 'inpaint', 'reangle', 'upscale', 'stage_shot']

/** The steps a queued or running job of each shot is making (its for-shot origin, a line's voice, a final's work). */
function useBusy(): (shotId: string) => Set<Step> {
  const jobs = useSession((s) => s.jobs)
  const flowNodes = useStory((s) => s.flowNodes)
  return useMemo(() => {
    const by = new Map<string, Set<Step>>()
    const add = (sid: string | undefined | null, step: Step) => { if (!sid) return; const s = by.get(sid) ?? new Set<Step>(); s.add(step); by.set(sid, s) }
    for (const j of Object.values(jobs)) {
      if (!ACTIVE.includes(j.status)) continue
      const o = j.origin, kind = (j as { kind?: string }).kind ?? ''
      const payload = (o?.payload ?? {}) as { shot_id?: string }
      if (o?.surface === 'for_shot') add(payload.shot_id, FRAME_KINDS.includes(kind) ? 'frame' : 'clip')
      else if (o?.surface === 'lipsync') add(o.ref, 'lipsync')
      else if (o?.surface === 'voice' && o.ref) add(flowNodes[o.ref]?.shot_id, 'voice')
      else if (['assemble_final', 'comp_render', 'layer_pass', 'matte_sequence'].includes(kind) || (o?.surface ?? '').startsWith('final')) {
        const sid = (payload as { shot_id?: string }).shot_id
        add(sid, 'final')
      }
    }
    return (sid: string) => by.get(sid) ?? new Set<Step>()
  }, [jobs, flowNodes])
}

export function ShotsBoard() {
  const shots = useStory((s) => s.shots)
  const flowNodes = useStory((s) => s.flowNodes)
  const flowGraph = useStory((s) => s.flowGraph)
  const shotId = useStory((s) => s.shotId)
  const clipsById = useStory((s) => s.clipsById)
  const finals = useStory((s) => s.boardFinals)
  const cuts = useStory((s) => s.boardCuts)
  const filter = useStory((s) => s.boardFilter)
  const search = useStory((s) => s.boardSearch)                                               // RC2d: the list's search and order
  const sort = useStory((s) => s.boardSort)
  const scenes = useStory((s) => s.scenes)
  const cards = useStory((s) => s.cards)
  const guide = useStory((s) => s.cardGuide)
  const busy = useBusy()
  useEffect(() => { void sy().loadBoard() }, [shots])
  const rows = useMemo(() => flowOrder(flowGraph, flowNodes, shots).map((r) => {
    const v = r.shot.versions.find((x) => x.id === r.shot.current) ?? r.shot.versions[0]
    return { ...r, v, cells: cellsOf(r.shot, v, r.node, { clipAudio: (id) => (clipsById[id] ? !!clipsById[id].audio_asset_id : undefined), finals, cuts, busy, stale: staleFrom(cards) }) }
  }), [flowGraph, flowNodes, shots, clipsById, finals, cuts, busy, cards])
  const shown = arrange(rows.filter((r) => keep(filter, r.cells)), search, sort, scenes, cards)
  return (
    <div className="shots-board" data-testid="shots-board">
      <table className="board">
        <thead><tr><th className="name">Shot</th>{STEPS.map((s) => <th key={s.id}>{s.label}</th>)}</tr></thead>
        <tbody>
          {shown.map((r, i) => {
            const head = r.group && r.group !== shown[i - 1]?.group ? <tr className="grp"><td colSpan={STEPS.length + 1}>{r.group}</td></tr> : null
            const thumb = r.v.frame_asset_id ?? (r.v.clip_id ? clipsById[r.v.clip_id]?.asset_id : null) ?? null
            return (
              <Fragment key={r.shot.id}>
                {head}
                <tr className={`row${shotId === r.shot.id ? ' sel' : ''}`} data-id={r.shot.id} onClick={() => sy().selectShot(r.shot.id)}
                  onContextMenu={(e) => { sy().selectShot(r.shot.id); showMenu(e, shotMenu()) }}>
                  <td className="name">
                    {thumb ? <img src={api.thumbUrl(thumb, 256)} alt="" /> : <span className="ph" />}
                    <span><b>{r.shot.name}</b><span className="route" title="its route — the recipe template (the Inspector changes it)">{ROUTE_LABEL[routeOf(r.v, madeFinal(r.shot.id, finals))] ?? routeOf(r.v, madeFinal(r.shot.id, finals))}
                      <RowFacts card={cards[r.shot.id]} guide={guide} scene={sort !== 'scene' && r.node?.scene_id ? scenes.find((s) => s.id === r.node!.scene_id)?.name : undefined} /></span></span>
                  </td>
                  {STEPS.map((s) => {
                    const c = r.cells[s.id]
                    const verb = STEP_VERB[s.id](r.v, c)
                    return (
                      <td key={s.id}>
                        <button type="button" className={`cell ${c.state}`} data-step={s.id}
                          disabled={(c.state === 'na' && !verb.always) || (r.v.state !== 'open' && ['frame', 'clip', 'final', 'lipsync'].includes(s.id))}   // V74: a final version makes nothing more
                          title={`${s.label}: ${r.v.state !== 'open' && ['frame', 'clip', 'final', 'lipsync'].includes(s.id) ? 'the version is final — make a new version' : verb.label}`} aria-label={`${r.shot.name} · ${s.label}: ${verb.label}`}
                          onClick={(e) => { e.stopPropagation(); sy().selectShot(r.shot.id); void sy().loadShotDetails().then(() => runStep(s.id)) }}>
                          <span className="g">{GLYPH[c.state]}</span>{c.text && <span className="t">{c.text}</span>}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              </Fragment>
            )
          })}
          {!shown.length && <tr className="empty"><td colSpan={STEPS.length + 1}>{rows.length ? 'No shot matches the filter.' : 'No shots yet — every Shot node in Flow has one.'}</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

function keep(f: BoardFilter, cells: Record<Step, Cell>): boolean {
  if (f === 'owes') return Object.values(cells).some((c) => c.state === 'owed' || c.state === 'stale')
  if (f === 'stale') return Object.values(cells).some((c) => c.state === 'stale')
  if (f === 'open') return cells.approved.state !== 'done'
  return true
}

/** RC2b / RC2d: a row's length (a warning past the guide), its stale count and its scene, after its route. */
function RowFacts({ card, guide, scene }: { card?: ShotCard; guide: number; scene?: string }) {
  const len = lengthLine(card, guide)
  return <>{len && <span className={`len${len.over ? ' over' : ''}`} title={len.title} data-length> · {len.text}</span>}
    {card && card.stale > 0 && <span className="stale" data-stale> · {card.stale} stale</span>}{scene && <span className="scene" title="its scene group"> · {scene}</span>}</>
}

/** The Shots panel (04 §3.1): the filters, the search and the order (RC2d), the legend, the shot verbs. */
export function BoardPanel() {
  const filter = useStory((s) => s.boardFilter)
  const search = useStory((s) => s.boardSearch)
  const sort = useStory((s) => s.boardSort)
  const F: [BoardFilter, string][] = [['all', 'all'], ['owes', 'owes a step'], ['stale', 'stale'], ['open', 'not approved']]
  return (
    <div className="story-panel board-panel">
      <div className="segmented" aria-label="filter">{F.map(([id, label]) => <button key={id} className={filter === id ? 'active' : ''} onClick={() => sy().setBoardFilter(id)}>{label}</button>)}</div>
      <input type="search" value={search} aria-label="search shots" placeholder="search — a name, a line, a scene" onChange={(e) => sy().setBoardSearch(e.target.value)} />
      <div className="kv"><span>order</span><select value={sort} aria-label="shot order" onChange={(e) => sy().setBoardSort(e.target.value as BoardSort)}>{(Object.keys(SORT_LABEL) as BoardSort[]).map((s) => <option key={s} value={s}>{SORT_LABEL[s]}</option>)}</select></div>
      <div className="verbs"><VoiceAllButton /></div>
      <h4>Legend <Help text={"A cell is its step's verb: a click does it for that shot (the maker opens on the shot). A right-click on a row is the shot's menu."} /></h4>
      <div className="board-legend">
        <span><b className="cell done">✓</b> done</span><span><b className="cell owed">○</b> owed — a click does it</span><span><b className="cell running">◐</b> running or queued</span>
        <span><b className="cell stale">!</b> its input changed</span><span><b className="cell na">–</b> not on this shot's route</span>
      </div>
    </div>
  )
}

/** D125 (S8): *Voice all lines (N)* — N counts the episode's lines (its Shots', U2) not voiced yet or changed since (the Flow strip, the Shots panel). */
export function VoiceAllButton() {
  const nodes = useStory((s) => s.flowNodes)
  useStory((s) => s.play)
  const n = linesToVoice(Object.values(nodes))
  return <CommandButton id="story.flow.voiceEpisode" text label={n ? `Voice all lines (${n})` : 'Voice all lines'} />
}

/** D125 (S11): *Link a stage camera…* — a stage and one of its cameras for the shot's open version (its stills and clips then come back by
 *  the camera); *A new stage for it* is *Block it on a stage…*. A sheet over Story, opened by the command (sy().linkFor). */
export function LinkStageSheet() {
  const linkFor = useStory((s) => s.linkFor)
  const shots = useStory((s) => s.shots)
  const [stages, setStages] = useState<{ id: string; name: string; cameras: { id: string; name: string; focal_mm: number }[] }[] | null>(null)
  const [pick, setPick] = useState<{ stage: string; camera: string } | null>(null)
  useEffect(() => {
    if (!linkFor) return
    let live = true
    void unwrap(http.GET('/stages')).then((r) => {
      if (!live) return
      const items = r.items.map((x) => ({ id: x.id, name: x.name, cameras: x.cameras.map((c) => ({ id: c.id, name: c.name, focal_mm: c.focal_mm })) }))
      setStages(items)
      const first = items.find((x) => x.cameras.length)
      setPick(first ? { stage: first.id, camera: first.cameras[0].id } : null)
    }).catch(() => { if (live) setStages([]) })
    return () => { live = false }
  }, [linkFor])
  if (!linkFor) return null
  const s = shots.find((x) => x.id === linkFor.shotId)
  const close = () => { sy().setLinkFor(null); setStages(null) }
  const stage = stages?.find((x) => x.id === pick?.stage)
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal link-stage" role="dialog" aria-modal="true" aria-label="Link a stage camera" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === 'Escape') close() }}>
        <div className="head">Link a stage camera to {s?.name ?? 'the shot'} {linkFor.version}<Help text={"The version takes the stage camera as its source: Image's From a stage and Animate's stage clip and final shot make its frame and clip there, and they come back to it. No second shot is made."} /></div>
        <div className="body form">
          {stages === null ? <span className="hint">Loading the stages…</span> : !stages.length ? <span className="hint">No stage yet — make one for the shot.</span> : <>
            <label htmlFor="link-stage">stage</label>
            <select id="link-stage" value={pick?.stage ?? ''} onChange={(e) => { const st = stages.find((x) => x.id === e.target.value); setPick(st ? { stage: st.id, camera: st.cameras[0]?.id ?? '' } : null) }}>
              {stages.map((x) => <option key={x.id} value={x.id}>{x.name} · {x.cameras.length} camera{x.cameras.length === 1 ? '' : 's'}</option>)}
            </select>
            <label htmlFor="link-camera">camera</label>
            <select id="link-camera" value={pick?.camera ?? ''} onChange={(e) => setPick(pick ? { ...pick, camera: e.target.value } : null)}>
              {(stage?.cameras ?? []).map((c) => <option key={c.id} value={c.id}>{c.name} · {c.focal_mm} mm</option>)}
            </select>
          </>}
        </div>
        <div className="foot">
          <button onClick={close}>Cancel</button>
          <button onClick={() => { close(); runCommand('story.shot.blockOnStage') }} title="A new stage named after the shot, its camera linked">A new stage for it…</button>
          <button className="primary" disabled={!pick?.camera} onClick={() => { if (pick) void sy().linkStage(linkFor.shotId, linkFor.version, pick.stage, pick.camera).then((ok) => { if (ok) { close(); useSession.getState().toast(`${s?.name ?? 'The shot'} takes ${stage?.name ?? 'the stage'}'s camera`, 'success') } }) }}>Link</button>
        </div>
      </div>
    </div>
  )
}
