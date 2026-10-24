// P17 (D83): the Sequence rail tab's panel — the project's sequences and the clip bin (every clip of the project, dragged or added
// onto the lane) — and the Inspector when a sequence is open (sequence · clip · transition). D90 (B7): the bins are sources; the lane
// (SequenceStage) is the drop target. Y57: the Shots bin offers a shot's final version (episode/bin.ts).
import { Plus } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../../api/client'
import { CommandButton, CommandRow } from '../../../frame/CommandButton'
import { beginDrag } from '../../../frame/drag'
import { Help } from '../../../frame/Help'
import { useSession } from '../../../store/session'
import { useAnimate } from '../../animate/animateStore'
import { duration, ticks } from './lane'
import { lastMovie, useSequence } from './sequenceStore'
import { useStory } from '../storyStore'
import { binItem, laneBelowFormat, laneChecklist } from './sequenceCommands'
import { markUsed, runCommand } from '../../../frame/commands'
import { shotRows } from './bin'
import { assembleLane, laneChanges, routeLabel, routePicks, walkRoute } from './assemble'
import { assembleCut } from './sequenceCommands'
import { flowOrder } from '../board'

export function SequencePanel() {
  const project = useSession((s) => s.project)
  const timelines = useSequence((s) => s.timelines)
  const current = useSequence((s) => s.current)
  const clips = useAnimate((s) => s.clips)
  const shots = useStory((s) => s.shots)
  const flowNodes = useStory((s) => s.flowNodes)
  const flowGraph = useStory((s) => s.flowGraph)
  const load = useSequence((s) => s.load)
  useEffect(() => { if (project?.open) { void load(); void useAnimate.getState().loadClips(); void useStory.getState().loadShots(); void useStory.getState().loadFlow() } }, [project?.path, load]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  markUsed('story.episode.addShot'); markUsed('story.episode.addClip')    // the bins' + run them on their entry
  return (
    <div className="seq-panel">
      <AssembleSheet />
      <div className="seq-list">
        <div className="seq-list-head"><b>Cuts</b><CommandButton id="story.episode.assemble" /><CommandButton id="story.episode.new" /></div>
        {!timelines.length && <span className="hint">None yet.</span>}
        {timelines.map((t) => (
          <button key={t.id} className={`seq-row${current?.id === t.id ? ' active' : ''}`} onClick={() => void useSequence.getState().open(t.id)} title={`${t.fps} fps · ${t.w}×${t.h} · revision ${t.revision}`}>
            <span className="name">{t.name}</span><span className="meta">{t.clips.length} clip{t.clips.length === 1 ? '' : 's'}</span>
          </button>
        ))}
      </div>
      <div className="seq-bin shots-bin">
        <div className="seq-list-head"><b>Shots</b><span className="hint">{current ? 'in the Flow\'s order — drag onto the lane, or +' : 'open a cut first'}</span></div>
        {(() => {
          const order = flowOrder(flowGraph, flowNodes, shots).map((r) => r.shot.id)                  // D125 (S13): the Flow's order
          const rows = shotRows(shots, clips).sort((x, y) => order.indexOf(x.sh.id) - order.indexOf(y.sh.id)).map((r) => ({ ...r, node: r.sh.owner_node ? flowNodes[r.sh.owner_node] : undefined }))
          if (!rows.length) return <span className="hint">No shot has a clip yet — Story · Shots.</span>
          return rows.map(({ sh, v, c, node }) => (
            <div key={sh.id} className={`seq-clip-card shot${v.state === 'final' ? ' final' : ''}`} data-shot={sh.id} title={`${sh.name} ${v.id} · ${v.state}${node ? ` · node ${node.title || node.type}` : ' · unbound'} · ${c.frames} f @ ${c.fps} · ${c.w}×${c.h}`}
              onPointerDown={(e) => beginDrag(e, () => ({ items: [{ kind: 'asset', id: c.asset_id ?? c.id, media: 'video' }], from: 'shots-bin', thumb: c.asset_id ? api.thumbUrl(c.asset_id, 256) : undefined, label: sh.name }))}>
              {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" draggable={false} /> : <span className="ph" />}
              <span className="t">{sh.name} · {v.id}{v.state === 'final' ? '' : ' · open'}<br /><small>{node ? node.title || node.type : 'unbound'}</small></span>
              <button className="quiet" disabled={!current} title={current ? 'Add to the end of the cut (stamped with the shot)' : 'open a cut first'} aria-label={`add shot ${sh.name}`} onClick={() => { binItem.shot = { clip: c, ref: { id: sh.id, version: v.id, node: sh.owner_node ?? null } }; runCommand('story.episode.addShot'); binItem.shot = undefined }}><Plus size={14} /></button>
            </div>
          ))
        })()}
      </div>
      <div className="seq-bin">
        <div className="seq-list-head"><b>Clips</b><span className="hint">{current ? 'drag onto the lane, or +' : 'open a cut first'}</span></div>
        {!clips.length && <span className="hint">No clips in this project yet — Animate makes them.</span>}
        {clips.map((c) => (
          <div key={c.id} className="seq-clip-card" title={`${c.frames} frames @ ${c.fps} fps · ${c.w}×${c.h}`}
            onPointerDown={(e) => beginDrag(e, () => ({ items: [{ kind: 'asset', id: c.asset_id ?? c.id, media: 'video' }], from: 'sequence-bin', thumb: c.asset_id ? api.thumbUrl(c.asset_id, 256) : undefined, label: c.id }))}>
            {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" draggable={false} /> : <span className="ph" />}
            <span className="t">{c.model_id.split('-')[0]} · {c.frames}f @ {c.fps}</span>
            <button className="quiet" disabled={!current} title={current ? 'Add to the end of the cut' : 'open a cut first'} aria-label={`add clip ${c.id}`} onClick={() => { binItem.clip = c; runCommand('story.episode.addClip'); binItem.clip = undefined }}><Plus size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  )
}

/** D125 (S13): *Assemble from the Flow…* / *Assemble again…* — a pick at each Choice the route meets, what the cut will hold, its name (a new
 *  cut is named after its route). Opened by the commands (sq().assembleFor). */
function AssembleSheet() {
  const target = useSequence((s) => s.assembleFor)
  return target ? <AssembleBody key={target.tlId ?? 'new'} target={target} /> : null    // mounted fresh each time it opens
}
function AssembleBody({ target }: { target: { tlId: string | null } }) {
  const timelines = useSequence((s) => s.timelines)
  const flowGraph = useStory((s) => s.flowGraph)
  const flowNodes = useStory((s) => s.flowNodes)
  const world = useStory((s) => s.world)
  const shots = useStory((s) => s.shots)
  const clips = useAnimate((s) => s.clips)
  const cut = target.tlId ? timelines.find((t) => t.id === target.tlId) : undefined
  const [picks, setPicks] = useState<Record<string, string>>(() => cut?.route ?? {})
  const [name, setName] = useState<string | null>(null)
  const walk = useMemo(() => (flowGraph ? walkRoute(flowGraph, flowNodes, world?.variables ?? [], picks) : null), [flowGraph, flowNodes, world, picks])
  if (!walk) return null
  const label = routeLabel(walk.choices)
  const preview = assembleLane(walk.nodes, shots, new Map(clips.map((c) => [c.id, c])), cut?.fps ?? 24)
  const auto = `Episode ${timelines.length + 1}${label ? ` · ${label}` : ''}`
  const close = () => useSequence.getState().setAssembleFor(null)
  const go = () => { close(); void assembleCut(routePicks(walk.choices), cut ? null : (name ?? auto).trim() || auto) }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal assemble" role="dialog" aria-modal="true" aria-label="Assemble from the Flow" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === 'Escape') close() }}>
        <div className="head">{cut ? `Assemble ${cut.name} again` : 'Assemble from the Flow'}<Help text={"One route of the Flow from its Start: every Dialogue or Shot node's shot in order, at its approved take (its final version, else the current one), stamped. Assembled again, the trims and dissolves stay where the same shots follow each other."} /></div>
        <div className="body form">
          {walk.choices.map((c) => (
            <div key={c.node.id} className="row"><label htmlFor={`pick-${c.node.id}`}>{c.node.title || 'Choice'}</label>
              <select id={`pick-${c.node.id}`} value={c.pick} onChange={(e) => setPicks({ ...picks, [c.node.id]: e.target.value })}>
                {c.options.map((o) => <option key={o.id} value={o.id}>{o.label || o.id}</option>)}
              </select></div>
          ))}
          {!walk.choices.length && <span className="hint">The Flow has one route.</span>}
          {!cut && <div className="row"><label htmlFor="assemble-name">name</label><input id="assemble-name" type="text" value={name ?? auto} onChange={(e) => setName(e.target.value)} /></div>}
          <span className="what" data-testid="assemble-what">{preview.lane.clips.length} shot{preview.lane.clips.length === 1 ? '' : 's'}{preview.missing.length ? ` · ${preview.missing.length} without a clip yet (${preview.missing.slice(0, 4).join(', ')})` : ''}</span>
        </div>
        <div className="foot">
          <button onClick={close}>Cancel</button>
          <button className="primary" disabled={!preview.lane.clips.length} onClick={go}>{cut ? 'Assemble again' : 'Assemble'}</button>
        </div>
      </div>
    </div>
  )
}

export function SequenceInspector() {
  const current = useSequence((s) => s.current)
  const lane = useSequence((s) => s.lane)
  const selected = useSequence((s) => s.selected)
  const saving = useSequence((s) => s.saving)
  const lastExport = useSequence((s) => s.lastExport)
  const clips = useAnimate((s) => s.clips)
  const shots = useStory((s) => s.shots)
  const jobs = useSession((s) => s.jobs)
  if (!current || !lane) return <span className="hint">No cut open.</span>
  const movie = lastMovie(jobs, current.id)                                                       // RC3: the newest movie job of this cut
  const ch = laneChanges(lane, shots)                                                           // D125 (S13): a newer approved take
  const changes = ch.length
  const selChange = ch.find((x) => x.i === selected) ?? null
  const c = selected !== null ? lane.clips[selected] : null
  const clip = c ? clips.find((x) => x.id === c.source) : null
  return (
    <div className="seq-insp">
      <h4>{current.name} <span className="hint">{saving ? '· saving…' : `· revision ${current.revision}`}</span></h4>
      <div className="kv"><span>lane</span><span>{current.fps} fps · {current.w}×{current.h}</span></div>
      <div className="kv"><span>duration</span><span>{duration(lane)} ticks · {(duration(lane) / current.fps).toFixed(2)} s · {lane.clips.length} clip{lane.clips.length === 1 ? '' : 's'}</span></div>
      {current.route && <div className="kv"><span>route</span><span>{Object.keys(current.route).length ? 'from the Flow, its picks kept' : 'from the Flow'}</span></div>}
      <div className="verbs"><CommandRow ids={['story.episode.reassemble', 'story.episode.rename', 'story.episode.delete']} /></div>
      <h4>Checklist <span className="hint">advisory — the export asks</span></h4>
      <ul className="seq-check">{(() => { const issues = laneChecklist(); return issues.length ? issues.map((x) => <li key={x.i} className="warn">clip {x.i + 1}: {x.what}</li>) : <li className="ok">{lane.clips.length ? 'every clip is a final shot version' : 'the lane is empty'}</li> })()}
        {(() => { const b = laneBelowFormat(); return b.count ? <li className="note" data-testid="below-format">{b.count} clip{b.count === 1 ? '' : 's'} below the format ({b.sizes.join(', ')}) <Help text={"A delivery note, not a problem: no video route renders the project format yet; Resolve scales the clips when it conforms the cut (D125)."} /></li> : null })()}</ul>
      {changes > 0 && <div className="verbs"><CommandButton id="story.episode.updateAll" text label={`Update ${changes} changed clip${changes === 1 ? '' : 's'}`} /></div>}
      <h4>Export <Help text={"Export for Resolve writes the FCPXML (a chapter marker per shot — its node's title — and the lines' voices on an audio lane), the EDL, the SRT (the nodes' Dialogue lines) and markers.txt into one folder named after the cut; Resolve conforms each clip at its own rate. One file at a time is still there. The draft render is a CPU job: frames from the masters, dissolves blended, a clip at another rate mapped by nearest frame (not conformed). The movie is the finished file: the cut's size (each clip fitted, bars where its shape differs), a 16 fps clip conformed to 24 by RIFE when the tool is installed, the voiced lines mixed where the exports place them; an MP4 (H.264 + AAC) beside the Resolve export and a video in the Catalogue."} /></h4>
      <div className="verbs"><CommandButton id="story.episode.exportResolve" text /><CommandButton id="story.episode.renderMovie" text label="Render the movie" /><CommandButton id="story.episode.render" text label="Render draft" /></div>
      <div className="verbs one-file"><span className="hint">one file</span><CommandButton id="story.episode.exportEdl" text label="EDL" /><CommandButton id="story.episode.exportFcpxml" text label="FCPXML + markers" /><CommandButton id="story.episode.exportSrt" text label="SRT" /></div>
      {lastExport && <p className="hint">last: {lastExport.path}</p>}
      {movie && <div className="kv seq-movie" data-testid="seq-movie"><span>movie</span><span>{movie.status === 'running' ? `rendering ${Math.round(movie.progress * 100)}%`
        : movie.status === 'failed' ? 'failed — the Dock has the log'
        : <><span title={movie.path ?? ''}>{movie.path?.split('/').pop()}</span>{movie.revision !== null && movie.revision !== current.revision ? ' · the cut changed since' : ''} <CommandButton id="story.episode.revealMovie" /></>}</span></div>}
      {c && <>
        <h4>Clip {selected! + 1}</h4>
        <div className="kv"><span>source</span><span>{clip ? `${clip.model_id} · ${clip.frames}f @ ${clip.fps}` : `${c.source} (missing)`}</span></div>
        <div className="kv"><span>uses</span><span>frames {c.in}–{c.out} ({c.out - c.in}) · {ticks(lane, c)} ticks</span></div>
        <div className="kv"><span>shot</span><span>{c.shot ? `${c.shot.id} · ${c.shot.version}${c.shot.node ? ` · node ${c.shot.node}` : ''}` : 'none (a plain clip)'}</span></div>
        {selected! > 0 && <div className="kv"><span>dissolve in</span><span>{lane.overlaps[selected!]} ticks</span></div>}
        {selChange && <div className="kv changed"><span>changed</span><span>{selChange.name} {selChange.version} is the approved take now <CommandButton id="story.episode.update" text label="Update" /></span></div>}
        <div className="verbs"><CommandRow ids={['story.episode.dissolve', 'story.episode.moveLeft', 'story.episode.moveRight', 'story.episode.openClip', 'story.episode.removeClip']} /></div>
      </>}
    </div>
  )
}
