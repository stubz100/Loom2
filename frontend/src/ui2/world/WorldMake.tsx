// U3b (D157, proto01_UI2 03 §3): Make, scoped to the entity in the header. The Generate panel is this entity version's own (`makeContext`,
// U1): first seeded with the entity linked — a character or prop as the subject card, a place as the scene — and kept for it, so a return
// finds what was set. The entity is always the subject, its words the Sheet's: the Prompt's Tree mode is this picture's words and a
// framing per class; Text and JSON (FLUX.2's JSON prompt) are Image's own. The author, 2026-10-29: the column's settings stay — the
// references, the Look, the camera, the model with its sampling, LoRAs and encoder, the size and count, the prompt as sent. The foot runs
// the casting run: the pictures land as the version's candidates in its bin.
import { useEffect } from 'react'
import { castOrigin } from '../../suites/generate/subjectCast'
import { useGenerate } from '../../suites/generate/generateStore'
import { CameraSection, LookSection, ModelSection, PreviewSection, PromptSection, RefsSection, SizeSection } from '../../suites/generate/GenerateColumn'
import { Help } from '../../frame/Help'
import { useStory } from '../../suites/story/storyStore'
import { CastSheet } from '../../suites/story/CastSheet'
import { enterMake, FRAMINGS, linkEntity } from './make'
import '../../suites/generate/generate.css'
import '../../suites/story/story.css'

export function WorldMake() {
  const p = useStory((s) => s.profiles.find((x) => x.id === s.profileId))
  const vid = useStory((s) => s.versionId)
  const panel = useGenerate((s) => s.panel)
  const pv = useGenerate((s) => s.preview)
  useEffect(() => { if (p && vid) enterMake(p.cls, p.id, vid) }, [p?.id, p?.cls, vid])        // eslint-disable-line react-hooks/exhaustive-deps
  const linked = p?.cls === 'place' ? !!panel.tree.scene_link : (panel.tree.subjects ?? []).some((s) => s.profile_id === p?.id)
  useEffect(() => { if (p && vid && panel.prompt_mode === 'tree' && !linked) linkEntity(p.cls, p.id, vid) }, [panel.prompt_mode, linked])   // eslint-disable-line react-hooks/exhaustive-deps -- back from JSON
  if (!p || !vid) return null
  const v = p.versions.find((x) => x.id === vid)
  const g = useGenerate.getState()
  const i = (panel.tree.subjects ?? []).findIndex((s) => s.profile_id === p.id)
  const note = p.cls === 'place' ? panel.tree.scene_link?.note ?? '' : i >= 0 ? panel.tree.subjects![i].shot_note ?? '' : ''
  const setNote = (t: string) => (p.cls === 'place' ? g.setSceneLink({ note: t }) : i >= 0 && g.setSubject(i, { shot_note: t }))
  const open = v?.state === 'open'
  const run = async () => {
    if (p.cls !== 'place' && i >= 0 && panel.prompt_mode === 'tree') { await g.castLook(i); return }   // the casting run renders the sheet
    const gid = await useStory.getState().ensureCandidates(p.id, vid)                                  // a place, or Text / JSON as written
    if (gid) await g.generate(false, castOrigin(p.id, vid, gid), { text: ` — they land as ${p.name}'s candidates` })
  }
  const secs = pv?.estimate.seconds ? Math.round(pv.estimate.seconds * panel.count) : null
  const tree = (
    <div className="w-make-tree">
      <label className="w-field"><span>this picture <Help text="Words for this run only, after the sheet above (soaked, hood up)." /></span>
        <textarea rows={2} value={note} aria-label="this picture only" placeholder="soaked, hood up" onChange={(e) => setNote(e.target.value)} /></label>
      <div className="w-field"><span>framing <Help text="Frames the next Give ‹entity› a look ▶ — nothing is queued here. The animation reference and a place's set picture are made in Build." /></span><div className="w-chips left">
        {FRAMINGS[p.cls].map((f) => <button key={f.id} onClick={() => g.setTree({ ...f.tree, camera: { ...panel.tree.camera, ...(f.tree.camera ?? {}) } })}>{f.label}</button>)}
      </div></div>
    </div>
  )
  return (
    <div className="w-make" data-testid="world-make">
      <div className="w-make-body gen-column">
        {v && <section className="gen-sec w-make-sheet" id="gen-sec-sheet" data-testid="world-sheet"><h4 className="gen-sec-head"><span>Sheet</span><span className="spacer" /><Help text="The words every picture of it carries — a @mention and every linked subject carry them too. The body, the animation reference and the rest are Build's." /></h4>
          <CastSheet p={p} v={v} /></section>}{/* D161: the words and the pictures made from them, one tab */}
        <PromptSection tree={tree} />
        <RefsSection />
        <LookSection />
        <CameraSection />
        <ModelSection />
        <SizeSection />
        <PreviewSection />
      </div>
      <div className="w-foot">
        <button className="primary" disabled={!open} onClick={() => void run()} title={open ? `${panel.count} pictures of ${p.name}; they land as its candidates` : `${p.name} ${vid} is final — make a new version`}>
          Give {p.name} a look ▶{secs ? ` ≈ ${secs < 90 ? `${secs} s` : `${Math.round(secs / 60)} min`}` : ''}</button>
        {pv?.estimate.refs_fit === 'spill' && <span className="spill" title="the references do not fit beside the model and run from shared memory">refs spill VRAM</span>}
      </div>
    </div>
  )
}
