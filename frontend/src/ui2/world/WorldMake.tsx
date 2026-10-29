// U3b (D157, proto01_UI2 03 §3): Make, scoped to the entity in the header. The Generate panel is this entity version's own (`makeContext`,
// U1): first seeded with the entity linked — a character or prop as the subject card, a place as the scene — and kept for it, so a return
// finds what was set. The entity is always the subject; what stays of Image's column: words for this picture only, a framing per class,
// the Look, the model and the count. The foot runs the casting run: the pictures land as the version's candidates in its bin.
import { useEffect } from 'react'
import { byOrder } from '../../store/modelCaps'
import { useSession } from '../../store/session'
import { castOrigin } from '../../suites/generate/subjectCast'
import { useGenerate } from '../../suites/generate/generateStore'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useStory } from '../../suites/story/storyStore'
import { enterMake, FRAMINGS } from './make'

export function WorldMake() {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  const stylesRaw = useStory((s) => s.world?.styles)                    // a selector must not return a fresh array (it would loop)
  const styles = stylesRaw ?? []
  const defaultStyle = useStory((s) => s.world?.default_style ?? null)
  const panel = useGenerate((s) => s.panel)
  const pv = useGenerate((s) => s.preview)
  const caps = useSession((s) => s.capabilities)
  useEffect(() => { if (p && vid) enterMake(p.cls, p.id, vid) }, [p?.id, p?.cls, vid])        // eslint-disable-line react-hooks/exhaustive-deps
  if (!p || !vid) return null
  const v = p.versions.find((x) => x.id === vid)
  const g = useGenerate.getState()
  const i = (panel.tree.subjects ?? []).findIndex((s) => s.profile_id === p.id)
  const note = p.cls === 'place' ? panel.tree.scene_link?.note ?? '' : i >= 0 ? panel.tree.subjects![i].shot_note ?? '' : ''
  const setNote = (t: string) => (p.cls === 'place' ? g.setSceneLink({ note: t }) : i >= 0 && g.setSubject(i, { shot_note: t }))
  const models = byOrder(caps?.models).filter(([, m]) => (m as { recipes?: { t2i?: unknown } }).recipes?.t2i)
  const style = panel.style_id === undefined ? defaultStyle : panel.style_id
  const open = v?.state === 'open'
  const run = async () => {
    if (p.cls !== 'place' && i >= 0) { await g.castLook(i); return }
    const gid = await useStory.getState().ensureCandidates(p.id, vid)
    if (gid) await g.generate(false, castOrigin(p.id, vid, gid), { text: ` — they land as ${p.name}'s candidates` })
  }
  const secs = pv?.estimate.seconds ? Math.round(pv.estimate.seconds * panel.count) : null
  return (
    <div className="w-make" data-testid="world-make">
      <label className="w-field"><span>this picture <Help text="Words for this run only, after the sheet (soaked, hood up). The sheet itself is the header's." /></span>
        <textarea rows={2} value={note} aria-label="this picture only" placeholder="soaked, hood up" onChange={(e) => setNote(e.target.value)} /></label>
      <div className="w-field"><span>framing</span><div className="w-chips left">
        {FRAMINGS[p.cls].map((f) => <button key={f.id} onClick={() => g.setTree({ ...f.tree, camera: { ...panel.tree.camera, ...(f.tree.camera ?? {}) } })}>{f.label}</button>)}
        {p.cls === 'character' && <><CommandButton id="story.cast.makeAnimRef" text label="A-pose front" /><CommandButton id="story.cast.makeAnimRefBack" text label="A-pose back" /></>}
        {p.cls === 'place' && <CommandButton id="cast.place.picture" text label="the set picture" />}
      </div></div>
      <div className="w-field"><span>look</span><div className="w-chips left">
        <button className={!style ? 'active' : ''} onClick={() => g.set({ style_id: null })}>none</button>
        {styles.map((s) => <button key={s.id} className={style === s.id ? 'active' : ''} onClick={() => g.set({ style_id: s.id })}>{s.name}{s.id === defaultStyle ? ' ★' : ''}</button>)}
      </div></div>
      <label className="w-field"><span>model</span>
        <select value={panel.model_id} aria-label="model" onChange={(e) => g.set({ model_id: e.target.value })}>{models.map(([id, m]) => <option key={id} value={id}>{(m as { label?: string }).label ?? id}</option>)}</select></label>
      <div className="w-field"><span>count</span><span className="w-val"><button onClick={() => g.set({ count: Math.max(1, panel.count - 1) })} aria-label="fewer">−</button> <b>{panel.count}</b> <button onClick={() => g.set({ count: Math.min(8, panel.count + 1) })} aria-label="more">+</button></span></div>
      <div className="w-foot">
        <button className="primary" disabled={!open} onClick={() => void run()} title={open ? `${panel.count} pictures of ${p.name}; they land as its candidates` : `${p.name} ${vid} is final — make a new version`}>
          Give {p.name} a look ▶{secs ? ` ≈ ${secs < 90 ? `${secs} s` : `${Math.round(secs / 60)} min`}` : ''}</button>
        {pv?.estimate.refs_fit === 'spill' && <span className="spill" title="the references do not fit beside the model and run from shared memory">refs spill VRAM</span>}
      </div>
    </div>
  )
}
