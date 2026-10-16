// P17 (D83): the Sequence rail tab's panel — the project's sequences and the clip bin (every clip of the project, dragged or added
// onto the lane) — and the Inspector when a sequence is open (sequence · clip · transition). D90 (B7): the bins are sources; the lane
// (SequenceStage) is the drop target. Y57: the Shots bin offers a shot's final version (episode/bin.ts).
import { Plus } from 'lucide-react'
import { useEffect } from 'react'
import { api } from '../../../api/client'
import { CommandButton, CommandRow } from '../../../frame/CommandButton'
import { beginDrag } from '../../../frame/drag'
import { useSession } from '../../../store/session'
import { useAnimate } from '../../animate/animateStore'
import { duration, ticks } from './lane'
import { useSequence } from './sequenceStore'
import { useStory } from '../storyStore'
import { laneChecklist } from './sequenceCommands'
import { shotRows } from './bin'

export function SequencePanel() {
  const project = useSession((s) => s.project)
  const timelines = useSequence((s) => s.timelines)
  const current = useSequence((s) => s.current)
  const clips = useAnimate((s) => s.clips)
  const shots = useStory((s) => s.shots)
  const flowNodes = useStory((s) => s.flowNodes)
  const load = useSequence((s) => s.load)
  useEffect(() => { if (project?.open) { void load(); void useAnimate.getState().loadClips(); void useStory.getState().loadShots(); void useStory.getState().loadFlow() } }, [project?.path, load]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  return (
    <div className="seq-panel">
      <div className="seq-list">
        <div className="seq-list-head"><b>Sequences</b><CommandButton id="story.episode.new" /></div>
        {!timelines.length && <span className="hint">None yet.</span>}
        {timelines.map((t) => (
          <button key={t.id} className={`seq-row${current?.id === t.id ? ' active' : ''}`} onClick={() => void useSequence.getState().open(t.id)} title={`${t.fps} fps · ${t.w}×${t.h} · revision ${t.revision}`}>
            <span className="name">{t.name}</span><span className="meta">{t.clips.length} clip{t.clips.length === 1 ? '' : 's'}</span>
          </button>
        ))}
      </div>
      <div className="seq-bin shots-bin">
        <div className="seq-list-head"><b>Shots</b><span className="hint">{current ? 'a shot\'s final version (else its current one), stamped — drag onto the lane, or +' : 'open a sequence first'}</span></div>
        {(() => {
          const rows = shotRows(shots, clips).map((r) => ({ ...r, node: r.sh.owner_node ? flowNodes[r.sh.owner_node] : undefined }))
          if (!rows.length) return <span className="hint">No shot has a clip yet — Story · Shots.</span>
          return rows.map(({ sh, v, c, node }) => (
            <div key={sh.id} className={`seq-clip-card shot${v.state === 'final' ? ' final' : ''}`} data-shot={sh.id} title={`${sh.name} ${v.id} · ${v.state}${node ? ` · node ${node.title || node.type}` : ' · unbound'} · ${c.frames} f @ ${c.fps} · ${c.w}×${c.h}`}
              onPointerDown={(e) => beginDrag(e, () => ({ items: [{ kind: 'asset', id: c.asset_id ?? c.id, media: 'video' }], from: 'shots-bin', thumb: c.asset_id ? api.thumbUrl(c.asset_id, 256) : undefined, label: sh.name }))}>
              {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" draggable={false} /> : <span className="ph" />}
              <span className="t">{sh.name} · {v.id}{v.state === 'final' ? '' : ' · open'}<br /><small>{node ? node.title || node.type : 'unbound'}</small></span>
              <button className="quiet" disabled={!current} title={current ? 'Add to the end of the episode (stamped with the shot)' : 'open a sequence first'} aria-label={`add shot ${sh.name}`} onClick={() => useSequence.getState().addShot(c, { id: sh.id, version: v.id, node: sh.owner_node ?? null })}><Plus size={14} /></button>
            </div>
          ))
        })()}
      </div>
      <div className="seq-bin">
        <div className="seq-list-head"><b>Clips</b><span className="hint">{current ? 'drag onto the lane, or +' : 'open a sequence first'}</span></div>
        {!clips.length && <span className="hint">No clips in this project yet — Animate makes them.</span>}
        {clips.map((c) => (
          <div key={c.id} className="seq-clip-card" title={`${c.frames} frames @ ${c.fps} fps · ${c.w}×${c.h}`}
            onPointerDown={(e) => beginDrag(e, () => ({ items: [{ kind: 'asset', id: c.asset_id ?? c.id, media: 'video' }], from: 'sequence-bin', thumb: c.asset_id ? api.thumbUrl(c.asset_id, 256) : undefined, label: c.id }))}>
            {c.asset_id ? <img src={api.thumbUrl(c.asset_id, 256)} alt="" draggable={false} /> : <span className="ph" />}
            <span className="t">{c.model_id.split('-')[0]} · {c.frames}f @ {c.fps}</span>
            <button className="quiet" disabled={!current} title={current ? 'Add to the end of the sequence' : 'open a sequence first'} onClick={() => useSequence.getState().addClip(c)}><Plus size={14} /></button>
          </div>
        ))}
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
  if (!current || !lane) return <span className="hint">No sequence open.</span>
  const c = selected !== null ? lane.clips[selected] : null
  const clip = c ? clips.find((x) => x.id === c.source) : null
  return (
    <div className="seq-insp">
      <h4>{current.name} <span className="hint">{saving ? '· saving…' : `· revision ${current.revision}`}</span></h4>
      <div className="kv"><span>lane</span><span>{current.fps} fps · {current.w}×{current.h}</span></div>
      <div className="kv"><span>duration</span><span>{duration(lane)} ticks · {(duration(lane) / current.fps).toFixed(2)} s · {lane.clips.length} clip{lane.clips.length === 1 ? '' : 's'}</span></div>
      <div className="verbs"><CommandRow ids={['story.episode.rename', 'story.episode.delete']} /></div>
      <h4>Checklist <span className="hint">advisory — the export asks</span></h4>
      <ul className="seq-check">{(() => { const issues = laneChecklist(); return issues.length ? issues.map((x) => <li key={x.i} className="warn">clip {x.i + 1}: {x.what}</li>) : <li className="ok">{lane.clips.length ? 'every clip is a final shot version' : 'the lane is empty'}</li> })()}</ul>
      <h4>Export</h4>
      <div className="verbs"><CommandButton id="story.episode.exportEdl" text label="EDL" /><CommandButton id="story.episode.exportFcpxml" text label="FCPXML + markers" /><CommandButton id="story.episode.exportSrt" text label="SRT" /><CommandButton id="story.episode.render" text label="Render draft" /></div>
      {lastExport && <p className="hint">last: {lastExport.path}</p>}
      <p className="hint">Resolve conforms each clip at its own rate; the FCPXML carries a chapter marker per shot (its node's title) and `markers.txt` lists them; the SRT takes the nodes' Dialogue lines; the FCPXML and the EDL carry the lines' voices on an audio lane at the lines' ticks (CN2). The draft render is a CPU job: frames from the masters, dissolves blended, a clip at another rate mapped by nearest frame (not conformed — D27).</p>
      {c && <>
        <h4>Clip {selected! + 1}</h4>
        <div className="kv"><span>source</span><span>{clip ? `${clip.model_id} · ${clip.frames}f @ ${clip.fps}` : `${c.source} (missing)`}</span></div>
        <div className="kv"><span>uses</span><span>frames {c.in}–{c.out} ({c.out - c.in}) · {ticks(lane, c)} ticks</span></div>
        <div className="kv"><span>shot</span><span>{c.shot ? `${c.shot.id} · ${c.shot.version}${c.shot.node ? ` · node ${c.shot.node}` : ''}` : 'none (a plain clip)'}</span></div>
        {selected! > 0 && <div className="kv"><span>dissolve in</span><span>{lane.overlaps[selected!]} ticks</span></div>}
        <div className="verbs"><CommandRow ids={['story.episode.dissolve', 'story.episode.moveLeft', 'story.episode.moveRight', 'story.episode.openClip', 'story.episode.removeClip']} /></div>
      </>}
    </div>
  )
}
