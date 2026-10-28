// CE4 (D126, proto01_animate 30 §5, O6): a video clip's colour in the Inspector — a take's own grade or a scene's (its adjustment layer):
// FilmCraft's presets and looks (listed by the engine), a LUT file, the basic values as sliders (FilmCraft takes a value when the slider is
// let go), a match to another shot, and the scene's grade from a V1 shot.
import { useState } from 'react'
import type { CutItem, CutTrack, CutTracks } from '../../../api/types'
import { CommandRow } from '../../../frame/CommandButton'
import { Help } from '../../../frame/Help'
import { askText } from '../../../store/session'
import { useClips } from '../../../store/clips'
import { useStory } from '../storyStore'
import { GRADE_SLIDERS, gradeLabel, itemLabel } from './cut'
import { useSequence } from './sequenceStore'
import { enqueue } from './queue'

const show = (key: string, v: number): string => (key === 'exposure' ? `${v > 0 ? '+' : ''}${v.toFixed(2)}` : `${v > 0 && key !== 'saturation' && key !== 'look_intensity' ? '+' : ''}${Math.round(v)}${key === 'saturation' || key === 'look_intensity' ? ' %' : ''}`)

export function GradeControls({ cut, track, item }: { cut: CutTracks; track: CutTrack; item: CutItem }) {
  const looks = useSequence((s) => s.looks)
  const busy = useSequence((s) => s.cutBusy)
  const shots = useStory((s) => s.shots)
  const clips = useClips()
  const [moving, setMoving] = useState<Record<string, number | undefined>>({})
  const g = item.grade
  const value = (k: string, neutral: number): number => moving[k] ?? g?.values[k] ?? neutral
  const sq = () => useSequence.getState()
  const send = (k: string, v: number | undefined) => {
    if (v === undefined || v === g?.values[k]) { setMoving((m) => ({ ...m, [k]: undefined })); return }
    void enqueue(() => sq().cutGrade(item.id, { values: { [k]: v } })).finally(() => setMoving((m) => (m[k] === v ? { ...m, [k]: undefined } : m)))
  }
  const takes = cut.video[0]?.items.filter((i) => i.id !== item.id && i.kind === 'take') ?? []
  const folders = [...new Set((looks?.presets ?? []).map((p) => p.folder))]
  const onLook = (v: string) => {
    if (v !== '@file') { void sq().cutGrade(item.id, { look: v }); return }
    void askText({ title: 'A look from a LUT file', text: 'The path of a .cube or .3dl file; it is kept in the cut.', placeholder: 'D:\\LUTs\\look.cube' })
      .then((path) => { if (path?.trim()) void sq().cutGrade(item.id, { look_file: path.trim() }) })
  }
  return (
    <div className="grade-insp" data-testid="grade-inspector">
      <div className="kv"><span>colour <Help text={"FilmCraft's Lumetri on this clip: a preset sets several values at once (it replaces the clip's grade), a look is a LUT (built in, or a .cube / .3dl file of yours), the sliders are the basic correction. A scene's grade is an adjustment layer on the Grade track over its shots; a shot's own grade sits under it. Match to… solves this shot's colour wheels toward another shot's middle frame"} /></span>
        <span>{g ? gradeLabel(g) : 'as shot'}{track.name === 'Grade' ? ' · the scene\'s grade' : ''}</span></div>
      <div className="kv"><span>preset</span><span>
        <select aria-label="apply a preset" value="" disabled={busy || !looks} onChange={(e) => { if (e.target.value) void sq().cutGrade(item.id, { preset: e.target.value }) }}>
          <option value="">{looks ? 'Apply a preset…' : 'FilmCraft lists them…'}</option>
          {folders.map((f) => <optgroup key={f} label={f}>{looks!.presets.filter((p) => p.folder === f).map((p) => <option key={p.name} value={p.name} title={p.description}>{p.name}</option>)}</optgroup>)}
        </select></span></div>
      <div className="kv"><span>look</span><span>
        <select aria-label="the look" value={g?.look ?? ''} disabled={busy} onChange={(e) => onLook(e.target.value)}>
          <option value="">none</option>
          {(looks?.looks ?? []).map((l) => <option key={l.ref} value={l.ref}>{l.name}</option>)}
          {g?.look?.startsWith('lib:') && <option value={g.look}>a LUT file</option>}
          <option value="@file">A LUT file…</option>
        </select></span></div>
      {GRADE_SLIDERS.filter((s) => s.key !== 'look_intensity' || !!g?.look).map(({ key, label, range, neutral, step }) => (
        <div className="kv strip-ctl" key={key}><span>{label}</span><span>
          <input type="range" min={range[0]} max={range[1]} step={step} aria-label={`${label}`} value={value(key, neutral)}
            title={`${label}: drag and let go; double-click: ${show(key, neutral)}`}
            onChange={(e) => { const v = Number(e.target.value); setMoving((m) => ({ ...m, [key]: v })) }}
            onPointerUp={() => send(key, moving[key])} onKeyUp={() => send(key, moving[key])} onDoubleClick={() => send(key, neutral)} />
          <span className="strip-val">{show(key, value(key, neutral))}</span>
        </span></div>
      ))}
      {track.id === cut.video[0]?.id && takes.length > 0 && <div className="kv"><span>match</span><span>
        <select aria-label="match its colour to" value="" disabled={busy} onChange={(e) => { if (e.target.value) void sq().cutGrade(item.id, { match: Number(e.target.value) }) }}>
          <option value="">Match its colour to…</option>
          {takes.map((i) => <option key={i.id} value={i.id}>{itemLabel(i, shots.find((x) => x.id === i.shot_id), clips.find((c) => c.id === i.clip_id))}</option>)}
        </select></span></div>}
      <div className="verbs"><CommandRow ids={['story.cut.grade.scene', 'story.cut.grade.own', 'story.cut.grade.reset']} /></div>
    </div>
  )
}
