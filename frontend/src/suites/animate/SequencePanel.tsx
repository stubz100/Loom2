// P17 (D83): the Sequence rail tab's panel — the project's sequences and the clip bin (every clip of the project, dragged or added
// onto the lane) — and the Inspector when a sequence is open (sequence · clip · transition).
import { Plus } from 'lucide-react'
import { useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton, CommandRow } from '../../frame/CommandButton'
import { beginDrag, onlyAssets, useDropTarget } from '../../frame/drag'
import { laneDrop } from '../../frame/dropRules'
import { useSession } from '../../store/session'
import { useAnimate } from './animateStore'
import { duration, ticks } from './lane'
import { useSequence } from './sequenceStore'

export function SequencePanel() {
  const project = useSession((s) => s.project)
  const timelines = useSequence((s) => s.timelines)
  const current = useSequence((s) => s.current)
  const clips = useAnimate((s) => s.clips)
  const load = useSequence((s) => s.load)
  useEffect(() => { if (project?.open) { void load(); void useAnimate.getState().loadClips() } }, [project?.path, load]) // eslint-disable-line react-hooks/exhaustive-deps
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && laneDrop(d, clips).verdict.ok, (d) => laneDrop(d, clips).take.forEach((c) => useSequence.getState().addClip(c)), (d) => laneDrop(d, clips).verdict)
  if (!project?.open) return <span className="hint">Open or create a project to begin.</span>
  return (
    <div className="seq-panel">
      <div className="seq-list">
        <div className="seq-list-head"><b>Sequences</b><CommandButton id="anim.seq.new" /></div>
        {!timelines.length && <span className="hint">None yet.</span>}
        {timelines.map((t) => (
          <button key={t.id} className={`seq-row${current?.id === t.id ? ' active' : ''}`} onClick={() => void useSequence.getState().open(t.id)} title={`${t.fps} fps · ${t.w}×${t.h} · revision ${t.revision}`}>
            <span className="name">{t.name}</span><span className="meta">{t.clips.length} clip{t.clips.length === 1 ? '' : 's'}</span>
          </button>
        ))}
      </div>
      <div className="seq-bin" ref={dropRef} data-over={over || undefined}>
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
      <div className="verbs"><CommandRow ids={['anim.seq.rename', 'anim.seq.delete']} /></div>
      <h4>Export</h4>
      <div className="verbs"><CommandButton id="anim.seq.exportEdl" text label="EDL" /><CommandButton id="anim.seq.exportFcpxml" text label="FCPXML" /></div>
      {lastExport && <p className="hint">last: {lastExport.path}</p>}
      <p className="hint">Resolve conforms each clip at its own rate; a draft render (frames mapped, not conformed — D27) comes with the next slice.</p>
      {c && <>
        <h4>Clip {selected! + 1}</h4>
        <div className="kv"><span>source</span><span>{clip ? `${clip.model_id} · ${clip.frames}f @ ${clip.fps}` : `${c.source} (missing)`}</span></div>
        <div className="kv"><span>uses</span><span>frames {c.in}–{c.out} ({c.out - c.in}) · {ticks(lane, c)} ticks</span></div>
        {selected! > 0 && <div className="kv"><span>dissolve in</span><span>{lane.overlaps[selected!]} ticks</span></div>}
        <div className="verbs"><CommandRow ids={['anim.seq.dissolve', 'anim.seq.moveLeft', 'anim.seq.moveRight', 'anim.seq.openClip', 'anim.seq.removeClip']} /></div>
      </>}
    </div>
  )
}
