// D127 (proto01_animate 30 §16, AU2): a cut's track in the Inspector — an audio track's channel strip as sliders (FilmCraft takes the value
// when the slider is let go; its number asks for a typed one; a double-click puts back the role's setting), its role, and the track's verbs.
import { useState } from 'react'
import type { CutTrack, CutTracks, TrackRole, TrackStrip } from '../../../api/types'
import { CommandRow } from '../../../frame/CommandButton'
import { Help } from '../../../frame/Help'
import { runCommand } from '../../../frame/commands'
import { useSession } from '../../../store/session'
import { detent, faderDb, faderPos, isVideo, panLabel, ROLE_NAMES, STRIP, TRACK_ROLES, trackRef, volumeLabel, widthLabel } from './cut'
import { useSequence } from './sequenceStore'
import './cut.css'

type Key = keyof TrackStrip
const ROWS: { key: Key; label: string; cmd: string; show: (v: number) => string; help: string }[] = [
  { key: 'gain_db', label: 'gain', cmd: 'story.cut.track.gain', show: volumeLabel, help: 'Before the track\'s effects: −36 … +36 dB' },
  { key: 'volume_db', label: 'volume', cmd: 'story.cut.track.volume', show: volumeLabel, help: 'The fader: −∞ … +18 dB' },
  { key: 'pan', label: 'pan', cmd: 'story.cut.track.pan', show: panLabel, help: '100 % left … 50 / 50 … 100 % right' },
  { key: 'width', label: 'width', cmd: 'story.cut.track.width', show: widthLabel,
    help: '0 % mono … 100 % as recorded … 200 % wider: past 100 % the sides are raised and the centre lowered (3 dB at 200 %), so a mono sound gets quieter, not wider' },
]

/** The strip's changes in the order the author made them: one waits for the one before (a slider stays live while FilmCraft takes a value —
 *  disabling it dropped the keys pressed meanwhile). */
let queue: Promise<unknown> = Promise.resolve()
function enqueue(change: () => Promise<unknown>): Promise<unknown> {
  queue = queue.then(change)
  return queue
}

/** A slider's travel for a setting (0…1000) and back: the volume on a fader taper, the rest straight with their detents. */
const toPos = (k: Key, v: number): number => Math.round(k === 'volume_db' ? faderPos(v) * 1000 : (v - STRIP[k][0]) / (STRIP[k][1] - STRIP[k][0]) * 1000)
function fromPos(k: Key, pos: number): number {
  if (k === 'volume_db') return faderDb(pos / 1000)
  const [lo, hi] = STRIP[k]
  const v = lo + (pos / 1000) * (hi - lo)
  return detent(k, k === 'gain_db' ? Math.round(v * 2) / 2 : Math.round(v))
}

export function TrackInspector({ cut, track }: { cut: CutTracks; track: CutTrack }) {
  const [moving, setMoving] = useState<Partial<Record<Key, number>>>({})
  const busy = useSequence((s) => s.cutBusy)
  const audio = useSession((s) => s.settings?.audio)
  const video = isVideo(cut, track)
  const value = (k: Key): number => moving[k] ?? track[k]
  const roleStrip = (r: TrackRole | null | undefined): TrackStrip => (r && audio ? audio[r] : { gain_db: 0, volume_db: 0, pan: 0, width: 100 })
  const send = (k: Key, v: number | undefined) => {
    if (v === undefined || v === track[k]) { setMoving((m) => ({ ...m, [k]: undefined })); return }
    void enqueue(() => useSequence.getState().cutStrip(track.id, { [k]: v })).finally(() => setMoving((m) => (m[k] === v ? { ...m, [k]: undefined } : m)))
  }
  return (
    <div className="track-insp" data-testid="track-inspector">
      <h4>{track.name} <span className="hint">{trackRef(cut, track)} · {video ? 'video' : track.role ? `${track.role} track` : 'audio track'}</span></h4>
      {!video && <>
        <div className="kv"><span>role</span><span>
          <select aria-label="the track's role" value={track.role ?? ''} disabled={busy} onChange={(e) => void useSequence.getState().cutRole(track.id, (e.target.value || null) as TrackRole | null)}>
            {TRACK_ROLES.map((r) => <option key={r} value={r}>{ROLE_NAMES[r]}</option>)}<option value="">No role</option>
          </select> <Help text={"A role names the track and sets its four settings to the role's in Settings › Audio; No role keeps them. A sound on a dialogue track counts as dialogue when the music ducks"} /></span></div>
        {ROWS.map(({ key, label, cmd, show, help }) => (
          <div className="kv strip-ctl" key={key}><span title={help}>{label}</span><span>
            <input type="range" min={0} max={1000} step={1} aria-label={`${track.name} ${label}`} value={toPos(key, value(key))}
              title={`${help} — drag and let go; double-click: the ${track.role ? `${track.role} role's` : 'neutral'} setting`}
              onChange={(e) => { const v = fromPos(key, Number(e.target.value)); setMoving((m) => ({ ...m, [key]: v })) }}
              onPointerUp={() => send(key, moving[key])} onKeyUp={() => send(key, moving[key])}
              onDoubleClick={() => send(key, roleStrip(track.role)[key])} />
            <button className="link strip-val" title={`Type the ${label}`} disabled={busy} onClick={() => runCommand(cmd)}>{show(value(key))}</button>
          </span></div>
        ))}
      </>}
      <div className="verbs"><CommandRow ids={video ? ['story.cut.track.rename', 'story.cut.track.lock', 'story.cut.track.mute']
        : ['story.cut.track.resetRole', 'story.cut.track.duck', 'story.cut.track.rename', 'story.cut.track.lock', 'story.cut.track.mute']} /></div>
    </div>
  )
}
