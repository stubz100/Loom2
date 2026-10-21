// D88 XL (19 §7, experimental): the shot version's lip-sync — a voiced Flow line (the owner node's first), the preset with E18's time, the
// caveat in plain sight, the verb as a command (D32). The talking clip lands as a take on the version (never its clip until picked).
// D90 (B6): a line longer than the window (its audio's duration against `seconds_max`) is listed but cannot be picked.
import { useEffect } from 'react'
import { Help } from '../../frame/Help'
import type { ShotVersion } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import { sy, useStory, voicedLines } from './storyStore'

export function LipsyncBlock({ v, ownerNode }: { v: ShotVersion; ownerNode: string | null }) {
  const caps = useSession((s) => s.capabilities?.experimental?.lipsync)
  const flowNodes = useStory((s) => s.flowNodes)
  const opts = useStory((s) => s.lipsyncOpts)
  const audioSecs = useStory((s) => s.audioSecs)
  const audioIds = Object.values(flowNodes).flatMap((n) => n.lines.map((l) => l.audio_asset_id ?? '')).filter(Boolean).sort().join(',')
  useEffect(() => { if (audioIds) void sy().loadAudioSecs(audioIds.split(',')) }, [audioIds])
  if (!caps) return null
  const lines = voicedLines(flowNodes, ownerNode, audioSecs, caps.seconds_max)
  const first = lines.find((l) => !l.too_long)
  const key = opts.node_id !== null && opts.index !== null ? `${opts.node_id}:${opts.index}` : (first ? `${first.node_id}:${first.index}` : '')
  const preset = caps.presets?.[opts.preset] as { label?: string; seconds?: number | null } | undefined
  return (
    <div className="lipsync" aria-label="lip-sync">
      <h4>Lip-sync <span className="badge experimental" title={caps.caveat}>experimental</span><Help text={caps.caveat} /></h4>
      {!caps.available ? <span className="hint">{caps.why}</span> : (
        <div className="kv">
          <span>line</span>
          <select aria-label="lip-sync line" value={key} onChange={(e) => { const [n, i] = e.target.value.split(':'); sy().setLipsyncOpts({ node_id: n || null, index: i ? Number(i) : null }) }}>
            {!first && <option value="">{lines.length ? `every voiced line runs over ${caps.seconds_max} s — shorten one` : 'no voiced line yet — voice one in the Flow (🎙)'}</option>}
            {lines.map((l) => <option key={`${l.node_id}:${l.index}`} value={`${l.node_id}:${l.index}`} disabled={l.too_long}>{l.label}{l.seconds !== null ? ` · ${l.seconds} s` : ''}{l.too_long ? ` (over ${caps.seconds_max} s)` : ''}</option>)}
          </select>
          <span>preset</span>
          <select aria-label="lip-sync preset" value={opts.preset} onChange={(e) => sy().setLipsyncOpts({ preset: e.target.value as 'draft' | 'fast' })}>
            {Object.entries(caps.presets ?? {}).map(([k, p]) => <option key={k} value={k}>{(p as { label?: string }).label ?? k}</option>)}
          </select>
          <span>face</span><span>{v.frame_asset_id ? 'the version\'s frame' : '— the version needs a frame'}</span>
          <span>estimate</span><span>{preset?.seconds ? `≈ ${Math.round(preset.seconds / 60)} min · queued for later (Run now in the Dock when the rig is free)` : '—'}</span>
        </div>
      )}
      <div className="verbs"><CommandButton id="story.shot.lipsync" text /></div>
    </div>
  )
}
