// CE2 (D126, proto01_animate 30 §12): a FilmCraft cut in the Episode — FilmCraft's frame at the playhead, the transport and the tools, and
// every track of the cut: one row each (video above, audio below), a clip as a block (its take's frames, a picture, a sound's waveform), the
// transitions shaded, the playhead. A drag asks FilmCraft for one edit when it ends (the tool decides which, cut.ts); a click with the
// razor cuts; a right-click opens the clip's or the track's verbs; a drop places a take, a picture or a sound where it falls. FilmCraft
// keeps the cut: what is drawn is the server's last reply.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { api, baseUrl, getBackend } from '../../../api/client'
import type { CutItem, CutTrack, CutTracks } from '../../../api/types'
import { CommandRow } from '../../../frame/CommandButton'
import { showMenu } from '../../../frame/ContextMenu'
import { useDropTarget, type DragPayload } from '../../../frame/drag'
import { useSession } from '../../../store/session'
import { useAnimate } from '../../animate/animateStore'
import { useStory } from '../storyStore'
import { storyKey } from '../storyKeys'
import { laneTake } from './bin'
import { laneChanges, type LaneChange } from './assemble'
import { runCommand } from '../../../frame/commands'
import { CUT_TOOLS, db, dragStep, gradeLabel, gripAt, itemLabel, razorStep, ROLE_NAMES, stripLabel, trackDrop, trackRef, type Grip } from './cut'
import { tc } from './lane'
import { cutClipMenu, cutLength, cutSpaceMenu, cutTrackMenu } from './sequenceCommands'
import { useSequence } from './sequenceStore'
import '../../animate/animate.css'
import './cut.css'

const HEAD = 104                                   // the track headers' column, px

/** FilmCraft's frame at the playhead: ½ size at rest, ¼ while playing; the latest asked wins, the frames seen are kept a while. */
function CutViewer({ tlId, revision, fps, w, h }: { tlId: string; revision: number; fps: number; w: number; h: number }) {
  const playhead = useSequence((s) => s.playhead)
  const playing = useSequence((s) => s.playing)
  const [src, setSrc] = useState<string | null>(null)
  const want = useRef<{ frame: number; side: number } | null>(null)
  const busy = useRef(false)
  const cache = useRef(new Map<string, string>())
  useEffect(() => () => { cache.current.forEach((u) => URL.revokeObjectURL(u)); cache.current.clear() }, [])
  useEffect(() => {
    want.current = { frame: playhead, side: playing ? Math.round(Math.max(w, h) / 4) : Math.round(Math.max(w, h) / 2) }
    const pump = async () => {
      if (busy.current) return
      busy.current = true
      try {
        while (want.current) {
          const job = want.current
          want.current = null
          const key = `${revision}:${job.frame}:${job.side}`
          let url = cache.current.get(key)
          if (!url) {
            const b = getBackend()
            if (!b) return
            const res = await fetch(`${baseUrl()}/timelines/${tlId}/frame?t=${(job.frame + 0.5) / fps}&side=${job.side}`, { headers: { 'X-Loom-Token': b.token } })
            if (!res.ok) continue
            url = URL.createObjectURL(await res.blob())
            cache.current.set(key, url)
            if (cache.current.size > 96) { const [k, u] = cache.current.entries().next().value as [string, string]; URL.revokeObjectURL(u); cache.current.delete(k) }
          }
          setSrc(url)
        }
      } catch { /* the next playhead asks again */ } finally { busy.current = false }
    }
    void pump()
  }, [playhead, playing, revision, tlId, fps, w, h])
  return <div className="cut-view" style={{ aspectRatio: `${w} / ${h}` }}>{src ? <img src={src} alt="" draggable={false} /> : null}</div>
}

/** CE3: the cut's sound as FilmCraft mixes it (`GET /timelines/{id}/mix`, a WAV at the movie's loudness), fetched again when the cut moves. */
function useCutMix(tlId: string, revision: number): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let gone = false, made: string | null = null
    const timer = window.setTimeout(() => {
      const b = getBackend()
      if (!b) return
      void fetch(`${baseUrl()}/timelines/${tlId}/mix`, { headers: { 'X-Loom-Token': b.token } }).then(async (res) => {
        if (gone) return
        if (!res.ok) {                                                     // AU4: a print that could not be made is said (the picture plays on)
          if (res.status === 422) useSession.getState().toast(`The cut's sound: ${((await res.json().catch(() => null)) as { detail?: string } | null)?.detail ?? res.status}`, 'error')
          return
        }
        made = URL.createObjectURL(await res.blob())
        if (gone) { URL.revokeObjectURL(made); return }
        setUrl(made)
        if (useSequence.getState().tracks?.audio.some((t) => t.printed === 'stale')) void useSequence.getState().loadTracks()   // AU4: the mix printed them
      }).catch(() => { /* the picture plays without it */ })
    }, 250)
    return () => { gone = true; window.clearTimeout(timer); if (made) URL.revokeObjectURL(made) }
  }, [tlId, revision])
  return url
}


interface Drag { id: number; grip: Grip; dx: number; toTrack: number }

function ClipBlock({ cut, track, item, ppf, drag, onDown, changed }: { cut: CutTracks; track: CutTrack; item: CutItem; ppf: number; drag: Drag | null; onDown: (e: ReactPointerEvent, item: CutItem) => void; changed?: LaneChange }) {
  const selected = useSequence((s) => s.selClip === item.id)
  const clips = useAnimate((s) => s.clips)
  const width = Math.max(2, item.duration * ppf)
  let left = item.start * ppf, w = width, moved = false
  if (drag?.id === item.id) {
    if (drag.grip === 'body') { left += drag.dx; moved = drag.toTrack !== track.id } else if (drag.grip === 'in') { left += drag.dx; w -= drag.dx } else w += drag.dx
  }
  const clip = item.clip_id ? clips.find((c) => c.id === item.clip_id) : undefined
  const shot = useStory((s) => (item.shot_id ? s.shots.find((x) => x.id === item.shot_id) : undefined))
  const node = useStory((s) => (item.kind === 'line' && item.node_id ? s.flowNodes[item.node_id] : undefined))
  const said = node && item.line !== null && item.line !== undefined ? node.lines[item.line]?.text : undefined
  const label = said ? `“${said.length > 40 ? `${said.slice(0, 38)}…` : said}”` : itemLabel(item, shot, clip)          // CE3: a line by its words
  const thumbs = () => {
    if (item.kind === 'take' && clip) {
      const tw = Math.max(40, Math.round((40 * clip.w) / Math.max(1, clip.h)))
      const n = Math.max(1, Math.min(60, Math.floor(width / tw)))
      return Array.from({ length: n }, (_, k) => {
        const local = Math.min(clip.frames - 1, Math.floor((item.source_in + ((k + 0.5) / n) * (item.duration / cut.fps) * item.speed) * clip.fps))
        return <img key={k} src={api.fileUrl(`/clips/${clip.id}/frames/${local}.png?size=96`)} alt="" draggable={false} loading="lazy" style={{ left: k * tw, width: tw }} />
      })
    }
    if (item.asset_id && (item.kind === 'picture' || item.kind === 'sound' || item.kind === 'line')) return <img className="fill" src={api.thumbUrl(item.asset_id)} alt="" draggable={false} loading="lazy" />
    return null
  }
  return (
    <div className={`cut-clip k-${item.kind}${selected ? ' selected' : ''}${moved ? ' moving' : ''}${item.enabled ? '' : ' off'}`} data-clip={item.id}
      style={{ left, width: Math.max(2, w) }} onPointerDown={(e) => onDown(e, item)}
      title={`${label} · ${item.kind}${item.shot_id ? ` · shot ${item.shot_id} ${item.shot_version ?? ''}` : ''} · ${tc(Math.round(item.start), cut.fps)} for ${Math.round(item.duration)} f${item.speed !== 1 ? ` · ${Math.round(item.speed * 100)} %` : ''}${item.hold ? ' · frame hold' : ''}`}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); useSequence.getState().selectClip(item.id); showMenu(e, cutClipMenu()) }}>
      <div className="cut-thumbs">{thumbs()}</div>
      {changed && <button type="button" className="seq-changed" title={`${changed.name} ${changed.version} is the approved take now — Update plays it in place, the edits around it stay`}
        onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); useSequence.getState().selectClip(item.id); runCommand('story.episode.update') }}>changed · Update</button>}
      <b>{label}{item.speed !== 1 ? ` · ${Math.round(item.speed * 100)} %` : ''}{item.hold ? ' · hold' : ''}{item.gain_db ? ` · ${db(item.gain_db)}` : ''}{item.ducked ? ' · ducked' : ''}{item.grade ? ` · ${gradeLabel(item.grade)}` : ''}</b>
    </div>
  )
}

function TrackRow({ cut, track, ppf, len, drag, onDown, frameAt, changed }: { cut: CutTracks; track: CutTrack; ppf: number; len: number; drag: Drag | null; onDown: (e: ReactPointerEvent, item: CutItem) => void; frameAt: (x: number) => number; changed: Map<number, LaneChange> }) {
  const video = cut.video.some((x) => x.id === track.id)
  const clips = useAnimate((s) => s.clips)
  const shots = useStory((s) => s.shots)
  const rule = (p: DragPayload) => trackDrop(p.items, video, clips)
  const { ref, over } = useDropTarget((p) => rule(p).verdict.ok, (p, info) => {
    const r = rule(p), sq = useSequence.getState(), at = Math.round(frameAt(info.x)), name = trackRef(cut, track)
    const stamped = new Map(laneTake(p, clips, shots).take.filter((x) => x.shot).map((x) => [x.clip.id, x.shot!]))   // from the Shots bin: the shot it stands for
    void (async () => {
      for (const c of r.clips) { const s = stamped.get(c.id); await sq.cutPlace({ clip_id: c.id, shot_id: s?.id, shot_version: s?.version, node_id: s?.node, track: name, frame: at }) }
      for (const a of r.assets) await sq.cutPlace({ asset_id: a, track: name, frame: at })
    })()
  }, (p) => { const v = rule(p).verdict; return v.ok ? { ...v, label: `${v.label} · ${trackRef(cut, track)}` } : v })
  const target = drag && drag.grip === 'body' && drag.toTrack === track.id
  const role = !video && track.role ? ROLE_NAMES[track.role] : null                     // D127: an audio track's role and its strip away from neutral
  const on = video ? 0 : track.chain.filter((e) => !e.bypass).length                   // AU4: the effects on
  const strip = video ? '' : [stripLabel(track), on ? `${on} fx${track.printed === 'stale' ? ' · to print' : ''}` : ''].filter(Boolean).join(' · ')
  const picked = useSequence((s) => s.selTrack === track.id)
  return (
    <div className={`cut-row${video ? ' v' : ' a'}${track.locked ? ' locked' : ''}${track.muted ? ' muted' : ''}${target ? ' target' : ''}`} data-track={track.id}>
      <div className={`cut-head${picked ? ' selected' : ''}`} title={`${trackRef(cut, track)} · ${track.name}${role ? ` (${role.toLowerCase()})` : ''}${strip ? ` · ${strip}` : ''} — click: ${video ? 'the track' : 'its settings'} in the Inspector · right-click: ${video ? 'rename, lock, mute, add a track' : 'gain, volume, pan, width, role, rename, lock, mute'}`}
        onClick={() => useSequence.getState().selectTrack(track.id)}
        onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); useSequence.getState().selectTrack(track.id); showMenu(e, cutTrackMenu()) }}>
        <span className="line">
          <span className="ref">{trackRef(cut, track)}</span><span className="name">{track.name}</span>
          {role && role !== track.name && <i title="the track's role">{role.toLowerCase()}</i>}{track.locked && <i title="locked">🔒</i>}{track.muted && <i title="muted">∅</i>}
        </span>
        {strip && <span className="cut-strip">{strip}</span>}
      </div>
      <div className="cut-lane" ref={ref} data-over={over || undefined} style={{ width: len * ppf }}>
        {track.transitions.map((x) => <i key={x.id} className={`cut-trans e-${x.effect}`} style={{ left: x.start * ppf, width: Math.max(2, x.duration * ppf) }} title={`${x.effect.replace(/_/g, ' ')} · ${Math.round(x.duration)} frames`} />)}
        {track.items.map((it) => <ClipBlock key={it.id} cut={cut} track={track} item={it} ppf={ppf} drag={drag} onDown={onDown} changed={changed.get(it.id)} />)}
      </div>
    </div>
  )
}

function CutTracksView({ cut }: { cut: CutTracks }) {
  const ppf = useSequence((s) => s.pxPerFrame)
  const playhead = useSequence((s) => s.playhead)
  const tool = useSequence((s) => s.tool)
  const lane = useSequence((s) => s.lane)
  const shots = useStory((s) => s.shots)
  const changed = new Map(lane ? laneChanges(lane, shots).map((x) => [Number(lane.clips[x.i].id), x]) : [])   // D125 (S13): a V1 take whose shot has a newer approved take
  const [drag, setDrag] = useState<Drag | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const len = Math.max(1, Math.ceil(cut.duration)) + Math.round(cut.fps * 4)            // room after the end to drop and drag into
  const frameAt = (clientX: number) => { const el = scroller.current!; const r = el.getBoundingClientRect(); return Math.max(0, (clientX - r.left - HEAD + el.scrollLeft) / ppf) }
  const scrub = (e: ReactPointerEvent) => {
    const sq = useSequence.getState()
    sq.togglePlay(false); sq.setPlayhead(Math.round(frameAt(e.clientX)))
    const move = (ev: PointerEvent) => sq.setPlayhead(Math.round(frameAt(ev.clientX)))
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const rows = [...[...cut.video].reverse(), ...cut.audio]                                // V2 above V1 above A1, as an editor stacks them
  const onDown = (e: ReactPointerEvent, item: CutItem) => {
    if (e.button !== 0) return
    e.stopPropagation()
    const sq = useSequence.getState()
    const track = rows.find((t) => t.items.some((i) => i.id === item.id))!
    sq.selectClip(item.id)
    if (tool === 'razor') { const st = razorStep(cut, track, Math.round(frameAt(e.clientX))); if (st) void sq.cutEdit([st]); return }
    const box = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const grip = gripAt(e.clientX - box.left, box.width)
    const x0 = e.clientX
    let cur: Drag = { id: item.id, grip, dx: 0, toTrack: track.id }
    const move = (ev: PointerEvent) => {
      const under = document.elementFromPoint(ev.clientX, ev.clientY)?.closest('[data-track]') as HTMLElement | null
      cur = { ...cur, dx: ev.clientX - x0, toTrack: under ? Number(under.dataset.track) : cur.toTrack }
      setDrag(cur)
    }
    const up = () => {
      window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up)
      setDrag(null)
      if (Math.abs(cur.dx) < 3 && cur.toTrack === track.id) { sq.togglePlay(false); sq.setPlayhead(Math.round(frameAt(x0))); return }     // a click: select and scrub
      const to = rows.find((t) => t.id === cur.toTrack) ?? track
      const st = dragStep(cut, sq.tool, track, item, grip, cur.dx / ppf, to)
      if (st) void sq.cutEdit([st])
    }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  const major = Math.max(1, Math.round(cut.fps * (ppf < 1 ? 5 : ppf < 3 ? 2 : 1)))
  const marks: number[] = []
  for (let f = 0; f <= len; f += major) marks.push(f)
  return (
    <div className={`cut-tracks tool-${tool}`} ref={scroller} onWheel={(e) => { if (e.ctrlKey) { e.preventDefault(); useSequence.getState().zoom(e.deltaY < 0 ? 1.25 : 0.8) } }}
      onContextMenu={(e) => { e.preventDefault(); showMenu(e, cutSpaceMenu()) }}
      onPointerDown={(e) => { if ((e.target as HTMLElement).classList.contains('cut-lane')) { useSequence.getState().selectClip(null); scrub(e) } }}>
      <div className="cut-ruler" style={{ width: HEAD + len * ppf }} onPointerDown={scrub}>
        {marks.map((f) => <div key={f} className="tick" style={{ left: HEAD + f * ppf }}><span>{tc(f, cut.fps)}</span></div>)}
      </div>
      {rows.map((t) => <TrackRow key={t.id} cut={cut} track={t} ppf={ppf} len={len} drag={drag} onDown={onDown} frameAt={frameAt} changed={changed} />)}
      <div className="cut-play" style={{ left: HEAD + playhead * ppf }} />
    </div>
  )
}

export function CutStage() {
  const current = useSequence((s) => s.current)
  const cut = useSequence((s) => s.tracks)
  const playhead = useSequence((s) => s.playhead)
  const playing = useSequence((s) => s.playing)
  const busy = useSequence((s) => s.cutBusy)
  const tool = useSequence((s) => s.tool)
  const mix = useCutMix(current?.id ?? '', current?.revision ?? 0)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const len = cut ? cutLength() : 0, fps = cut?.fps ?? 24
  // Playback at the cut's fps; stops at the end (the viewer asks FilmCraft for each frame it shows). CE3: with the mix loaded its clock
  // moves the playhead (the sound never drifts from the picture); without it, the frame clock.
  useEffect(() => {
    if (!playing || len <= 0) return
    let raf = 0, last = performance.now(), acc = 0
    const el = audioRef.current
    const sound = el && el.readyState >= 2 ? el : null
    if (sound) { sound.currentTime = useSequence.getState().playhead / fps; void sound.play().catch(() => undefined) }
    const step = (t: number) => {
      const s = useSequence.getState()
      if (sound && !sound.paused) {
        const f = Math.floor(sound.currentTime * fps)
        if (f >= len - 1 || sound.ended) { s.setPlayhead(len - 1); s.togglePlay(false); return }
        if (f !== s.playhead) s.setPlayhead(f)
      } else {
        acc += ((t - last) * fps) / 1000
        const n = Math.floor(acc)
        if (n > 0) {
          acc -= n
          if (s.playhead + n >= len - 1) { s.setPlayhead(len - 1); s.togglePlay(false); return }
          s.setPlayhead(s.playhead + n)
        }
      }
      last = t
      raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => { cancelAnimationFrame(raf); sound?.pause() }
  }, [playing, len, fps])
  if (!current || !cut) return <div className="anim-empty"><h2>Episode</h2>opening the cut…</div>
  return (
    <div className="anim-stage seq-stage cut-stage" tabIndex={0} onKeyDown={(e) => { storyKey('episode', e.nativeEvent) }}>
      <div className="anim-view"><CutViewer tlId={current.id} revision={current.revision} fps={cut.fps} w={cut.w} h={cut.h} /></div>
      {mix && <audio ref={audioRef} src={mix} preload="auto" data-testid="cut-mix" />}
      <div className="transport">
        <CommandRow ids={['story.episode.home', 'story.episode.back10', 'story.episode.stepBack', 'story.episode.play', 'story.episode.stepForward', 'story.episode.fwd10', 'story.episode.end']} labels={{ 'story.episode.play': playing ? 'Pause' : 'Play' }} />
        <span className="counter">{tc(playhead, cut.fps)} / {tc(Math.ceil(cut.duration), cut.fps)}{busy ? ' · …' : ''}</span>
        <span className="spacer" />
        <span className="cut-tools"><CommandRow ids={CUT_TOOLS.map((t) => `story.cut.tool.${t}`)} active={`story.cut.tool.${tool}`} /></span>
        <CommandRow ids={['story.episode.undo', 'story.episode.redo', 'gap', 'story.cut.addVideoTrack', 'story.cut.addAudioTrack', 'gap', 'story.episode.zoomOut', 'story.episode.zoomIn']} />
      </div>
      <CutTracksView cut={cut} />
    </div>
  )
}
