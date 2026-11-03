// D182 (C2b, propo02 04 §4.3): the Library's Animations — every animation as a tile: the author's library and the project's (a thumbnail
// of its first frame on the mannequin, its length, where it is kept), then the downloaded files' clips (CC0 starter, the local folder),
// each file opened to its clips. A tile opens the animation on the animation bench; its right-click has the verbs (open, rename,
// duplicate, to my library, remove; a clip: open, make it mine).
import { Film } from 'lucide-react'
import { useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import type { AnimRef } from '../../suites/stage/animationBench'
import { useTemplates } from '../../suites/stage/blockEdit'
import type { AnimationTemplate } from '../../suites/stage/blocks'
import { singleClip, useMotion } from '../../suites/stage/motion/motionStore'
import type { MotionClip, MotionFile } from '../../suites/stage/motion/library'
import { useClay } from './clayStore'

const secs = (frames: number, fps: number) => `${(frames / Math.max(1, fps)).toFixed(1)} s`

function Tile({ t, where }: { t: AnimationTemplate; where: 'project' | 'library' }) {
  const ref: AnimRef = { kind: 'template', id: t.id }
  const sel = useClay((s) => s.animSel?.kind === 'template' && s.animSel.id === t.id)
  const src = t.source?.clip ? `from ${t.source.clip}${t.source.licence ? ` · ${t.source.licence}` : ''}` : where === 'library' ? 'my library' : 'this project'
  return (
    <button className={`c-tile anim${sel ? ' selected' : ''}`} data-anim={t.id} title={`${t.name} — ${secs(t.frames, t.fps)} · ${src}; a click opens it on the bench`}
      onClick={() => void useClay.getState().openAnimation(ref)}
      onContextMenu={(e) => { useClay.getState().selectAnimation(ref); showMenu(e, [{ cmd: 'clay.anim.open' }, { sep: true }, { cmd: 'clay.anim.rename' }, { cmd: 'clay.anim.duplicate' }, { cmd: 'clay.anim.toLibrary' }, { sep: true }, { cmd: 'clay.anim.remove' }]) }}>
      <span className="c-thumb">{t.thumb_asset_id ? <img src={api.thumbUrl(t.thumb_asset_id, 256)} alt="" draggable={false} /> : <Film className="glyph" size={28} />}</span>
      <span className="c-name">{t.name}</span>
      <span className="c-meta">{secs(t.frames, t.fps)} · {src}</span>
    </button>
  )
}

function ClipTile({ f, c }: { f: MotionFile; c: MotionClip }) {
  const ref: AnimRef = { kind: 'clip', file: f.id, clip: c.name }
  const sel = useClay((s) => s.animSel?.kind === 'clip' && s.animSel.file === f.id && s.animSel.clip === c.name)
  return (
    <button className={`c-tile anim clip${sel ? ' selected' : ''}`} data-clip={`${f.id}:${c.name}`} title={`${c.name} — ${f.name} · ${f.licence}; a click opens it on the bench, Make it mine keeps an edited copy`}
      onClick={() => void useClay.getState().openAnimation(ref)}
      onContextMenu={(e) => { useClay.getState().selectAnimation(ref); showMenu(e, [{ cmd: 'clay.anim.open' }, { cmd: 'clay.anim.mine' }]) }}>
      <span className="c-thumb"><Film className="glyph" size={28} /></span>
      <span className="c-name">{c.name}</span>
      <span className="c-meta">{c.duration ? `${c.duration.toFixed(1)} s` : 'a clip'}{c.rootMotion ? ' · moves' : ''} · {f.licence}</span>
    </button>
  )
}

function FileClips({ f }: { f: MotionFile }) {
  const open = useMotion((s) => !!s.open[f.id])
  const clips = useMotion((s) => s.clips[f.id])
  if (f.ext === 'fbx') return <div className="c-tiles"><ClipTile f={f} c={singleClip(f)} /></div>
  return (
    <div className="c-anim-file" data-file={f.id}>
      <button type="button" className="quiet" aria-expanded={open} onClick={() => useMotion.getState().toggle(f)} title={`${f.rel} · ${f.licence}`}>{open ? '▾' : '▸'} {f.name} <small>{f.source === 'starter' ? 'CC0' : 'local'} · {(f.bytes / 2 ** 20).toFixed(1)} MB</small></button>
      {open && (clips === 'loading' || !clips ? <span className="hint">loading…</span>
        : 'error' in (clips as object) ? <span className="hint error">{(clips as { error: string }).error}</span>
        : (clips as MotionClip[]).length === 0 ? <span className="hint">no clips in this file</span>
        : <div className="c-tiles">{(clips as MotionClip[]).map((c) => <ClipTile key={c.name} f={f} c={c} />)}</div>)}
    </div>
  )
}

export function AnimationsGrid() {
  const t = useTemplates()
  const m = useMotion()
  const project = useSession((s) => s.project)
  useEffect(() => { if (!t.loaded) void t.load() }, [t.loaded])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (project?.open && !m.loaded) void m.refresh() }, [project?.path, m.loaded])   // eslint-disable-line react-hooks/exhaustive-deps
  const inLib = new Set(t.library.map((x) => x.id))
  const mine = t.items.filter((x) => !inLib.has(x.id))
  return (
    <div className="c-anim-sections" data-testid="clay-animations">
      <h4>Mine <small>· this project</small><Help text="Animations of your own, kept with the project: made on the bench from scratch, from a downloaded clip (Make it mine) or from a figure's track (Save as animation…). A click opens one on the bench; right-click for its verbs." /><span className="spacer" /><CommandButton id="clay.anim.new" text /></h4>
      {mine.length ? <div className="c-tiles">{mine.map((x) => <Tile key={x.id} t={x} where="project" />)}</div> : <span className="hint">None yet — New animation…, or open a downloaded clip and Make it mine.</span>}
      <h4>My library <small>· every project</small><Help text="Animations you put in your library (To my library): they are offered in every project." /></h4>
      {t.library.length ? <div className="c-tiles">{t.library.map((x) => <Tile key={x.id} t={x} where="library" />)}</div> : <span className="hint">None yet — To my library on one of the project's.</span>}
      <h4>Downloaded <small>· {m.files.length} file{m.files.length === 1 ? '' : 's'}</small><Help text="The starter set (CC0) and your local motion folder (Settings › Motion): their clips as they are. Open one on the bench to see it; Make it mine keeps an edited copy as your own." /></h4>
      {m.error && <span className="hint error">{m.error}</span>}
      {m.loaded && !m.files.length ? <span className="hint">No motion files found — the starter set lives in the models root's motion folder; your own clips go in Settings › Motion.</span>
        : m.files.map((f) => <FileClips key={f.id} f={f} />)}
    </div>
  )
}
