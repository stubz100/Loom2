// D90 (02 §6, R3, R4): Generate's Panel as one continuous column — saved panels, prompt, references, look, camera, model, size, preview —
// instead of five rail tabs. The rail's buttons jump to a section and follow the scroll. Every preset is an icon tile (frame/PresetIcons):
// drawn glyphs for geometry, generated swatches for looks (swatches.ts); the words live in the tooltip, and a section's "Aa" shows them
// under the tiles. Fields a model cannot use are hidden, not disabled (B12). D92: the tiles are the project's Story · World library (a
// field's + adds an entry there; a tile's right-click edits it in World), a look without its picture yet shows its field's glyph — never
// letters — and a subject card picks a Cast character or prop by its hero image.
import { CaseSensitive, ImagePlus, Minus, Plus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, sep } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { onlyAssets, useDropTarget } from '../../frame/drag'
import { PresetIcons, type PresetIcon } from '../../frame/PresetIcons'
import { aspectGlyph, fieldGlyph, tierGlyph } from '../../frame/presetGlyphs'
import { setRailTab } from '../../frame/suiteRegistry'
import { byOrder } from '../../store/modelCaps'
import { askConfirm, useSession } from '../../store/session'
import { appendValue, FIELD_LABEL, REPLACE, type FieldKey } from './fieldPresets'
import { dropRefs, honoursNegative, refDropFor, runOnSubject, useGenerate, type ModelCap, type Panel as PanelState, type Subject } from './generateStore'
import { bindingLines, castOffer, nameOnly, needsLook, sentIndex, slotsOf } from './subjectCast'
import { CastButton, SubjectSlots, SubjectWarn } from './SubjectLink'
import { entriesOf, entryTile, useLibrary } from '../story/libraryStore'
import { profilesForMentions, sy, useStory } from '../story/storyStore'
import { LoraSlots } from './LoraSlots'
import { RefExtras, TextPrompt } from './RefExtras'
import { StylePicker } from './StylePicker'
import { ForChip } from '../story/ForChip'
import { needsPicture, swatchJob, useSwatches } from './swatches'
import { useMentions } from './useMentions'

const ASPECTS: [string, number, number][] = [['16:9', 16, 9], ['1:1', 1, 1], ['3:2', 3, 2], ['2:3', 2, 3], ['9:16', 9, 16], ['21:9', 21, 9]]
const snap16 = (n: number) => Math.max(64, Math.round(n / 16) * 16)
/** The column's sections in order; the rail's buttons carry the same ids (GenerateSuite.tsx). */
const SECTION_IDS = ['presets', 'prompt', 'refs', 'look', 'camera', 'model', 'size'] as const

// ------------------------------------------------------------------ presets as icons
/** The values a field's text already holds: one for a replace field (lens, f-number…), the comma-separated parts otherwise. */
const partsOf = (field: FieldKey, text: string) => (REPLACE.has(field) ? [text.trim()] : text.split(',').map((x) => x.trim())).filter(Boolean).map((x) => x.toLowerCase())

function PresetRow({ field, value, onChange, section }: { field: FieldKey; value: string; onChange: (v: string) => void; section: string }) {
  const lib = useLibrary((l) => l.library)
  const showText = useGenerate((g) => !!g.presetText[section])
  const swatchUrl = useSwatches((s) => s.url)
  useSwatches((s) => s.items)                                             // re-render when a swatch lands
  const jobs = useSession((s) => s.jobs)                                  // … and when its job starts or ends (the busy mark)
  const has = new Set(partsOf(field, value))
  const items = entriesOf(lib, field).map((e) => entryTile(e, swatchUrl, (f, v) => !!swatchJob(jobs, f, v)))   // D92: the World library's entries for this field
  const pic = items.some((i) => i.img || i.busy) || entriesOf(lib, field).some((e) => needsPicture(e.field, e.text))
  const toggle = (text: string) => {
    if (!has.has(text.toLowerCase())) { onChange(appendValue(value, text, field)); return }
    onChange(REPLACE.has(field) ? '' : value.split(',').map((x) => x.trim()).filter((x) => x && x.toLowerCase() !== text.toLowerCase()).join(', '))
  }
  if (!items.length) return null
  return (
    <PresetIcons label={`${FIELD_LABEL[field]} presets`} size={pic ? 44 : 38} showText={showText} items={items}
      selected={items.filter((i) => has.has(i.text.toLowerCase())).map((i) => i.id)}
      onPick={(id) => { const it = items.find((i) => i.id === id); if (it) toggle(it.text) }}
      onContext={(id, e) => {
        const it = items.find((i) => i.id === id)
        if (!it) return
        sy().select({ kind: 'entry', id })                               // D92: the entry is the item the World verbs act on
        showMenu(e, [
          { label: has.has(it.text.toLowerCase()) ? 'Remove from the field' : 'Add to the field', run: () => toggle(it.text) },
          { cmd: 'story.world.entryPicture' }, { cmd: 'story.world.editEntry' }, sep, { cmd: 'story.world.remove', label: 'Remove from the library' },
        ])
      }} />
  )
}

/** One prompt field: its input (with @ for the multiline ones), its preset icons and the + that adds the words to the World library. */
function Field({ label, field, value, onChange, multiline, placeholder, rows, section, id, after }: { label?: string; field: FieldKey; value: string; onChange: (v: string) => void; multiline?: boolean; placeholder?: string; rows?: number; section: string; id?: string; after?: React.ReactNode }) {
  const [naming, setNaming] = useState<string | null>(null)
  const mention = useMentions(value, onChange)
  const commit = () => { if (naming !== null) void useLibrary.getState().add(field, value, naming.trim()).then((e) => { if (e) useSession.getState().toast(`“${e.name}” is in the library (Story · World)`, 'info') }); setNaming(null) }
  return (
    <>
      <label>{label ?? FIELD_LABEL[field]}</label>
      <div className="field">
        <div className="row">
          {multiline
            ? <textarea id={id} value={value} rows={rows} onChange={(e) => onChange(e.target.value)} onKeyUp={mention.onKeyUp} placeholder={placeholder} />
            : <input id={id} type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />}
          {multiline && mention.button}
          <button type="button" className="preset-btn" disabled={!value.trim()} title={`Add the current ${FIELD_LABEL[field]} to the library (Story · World)`} aria-label={`add ${FIELD_LABEL[field]} to the library`} onClick={() => setNaming('')}><Plus size={13} /></button>
        </div>
        {naming !== null && (
          <div className="saver">
            <input type="text" autoFocus value={naming} aria-label={`name of the new ${FIELD_LABEL[field]} entry`} placeholder={`a name for it (blank: the words)`} onChange={(e) => setNaming(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setNaming(null) }} />
            <button className="primary" onClick={commit}>Add</button>
            <button className="quiet" onClick={() => setNaming(null)}>Cancel</button>
          </div>
        )}
        {after}
        <PresetRow field={field} value={value} onChange={onChange} section={section} />
      </div>
    </>
  )
}

/** A section of the column: its anchor for the rail, a title, and the words-under-icons toggle where it has presets. */
function Section({ id, title, words, tools, children }: { id: string; title: string; words?: boolean; tools?: React.ReactNode; children: React.ReactNode }) {
  const on = useGenerate((g) => !!g.presetText[id])
  const setText = useGenerate((g) => g.setPresetText)
  return (
    <section id={`gen-sec-${id}`} className="gen-sec">
      <h4 className="gen-sec-head"><span>{title}</span><span className="spacer" />{tools}
        {words && <button type="button" className={`quiet icon${on ? ' active' : ''}`} title={on ? 'Hide the words under the preset icons' : 'Show the words under the preset icons'} aria-pressed={on} onClick={() => setText(id, !on)}><CaseSensitive size={15} /></button>}
      </h4>
      {children}
    </section>
  )
}

// ------------------------------------------------------------------ prompt
const FREE = '__free'
/** D92: the Cast as picture tiles — characters first, then props (places could map to the scene or background later), each by its current
 *  version's hero; "free subject" unlinks. */
function CastPicker({ s, i }: { s: Subject; i: number }) {
  const profiles = useStory((x) => x.profiles)
  const loaded = useStory((x) => x.profilesLoaded)
  useEffect(() => { if (!loaded) profilesForMentions() }, [loaded])
  const g = useGenerate.getState()
  const cast = [...profiles.filter((p) => p.cls === 'character'), ...profiles.filter((p) => p.cls === 'prop')]
  const hero = (pid: string) => { const p = profiles.find((x) => x.id === pid); return p?.versions.find((v) => v.id === p.current)?.hero_asset_id ?? null }
  const items: PresetIcon[] = [
    ...cast.map((p): PresetIcon => { const h = hero(p.id); return { id: p.id, label: p.name, hint: `${p.cls} · ${p.current} — its reference set${p.versions.find((v) => v.id === p.current)?.lora ? ' and LoRA' : ''} follow`, icon: fieldGlyph(p.cls), img: h ? api.thumbUrl(h, 256) : null } }),
    { id: FREE, label: 'free subject', hint: 'described in words only, no Cast profile', icon: fieldGlyph('free') },
  ]
  return (
    <PresetIcons label={`subject ${i + 1} from the Cast`} size={44} items={items} selected={s.profile_id ?? FREE}
      onPick={(id) => { if (id === FREE) g.unlinkSubject(i); else { const p = profiles.find((x) => x.id === id); if (p) g.linkSubject(i, p) } }}
      onContext={(id, e) => { if (id === FREE) return; sy().selectProfile(id); showMenu(e, [{ cmd: 'story.cast.openInStory' }]) }} />
  )
}

function SubjectCard({ i, s }: { i: number; s: Subject }) {
  const g = useGenerate()
  const set = (patch: Partial<Subject>) => g.setSubject(i, patch)
  const linked = useStory((x) => (s.profile_id ? x.profiles.find((p) => p.id === s.profile_id) : undefined))
  const hero = linked?.versions.find((v) => v.id === linked.current)?.hero_asset_id
  // D93 (A1, A3, A9): the link's slots in the prompt, the casting run, and what the description still lacks
  const pm = s.profile_id ? g.preview?.mentions?.find((m) => m.profile_id === s.profile_id) : undefined
  const offer = s.profile_id ? castOffer(linked, pm?.asset_ids?.length ?? 0) : null
  const slots = s.profile_id && g.panel.prompt_mode === 'tree' ? slotsOf(g.preview?.bindings, sentIndex(g.panel.tree.subjects ?? [], i)) : null
  const name = linked?.name ?? ''
  markUsed('gen.subject.cast')
  return (
    <div className={`subject${s.profile_id ? ' linked' : ''}`}>
      <div className="head"><b>subject {i + 1}</b>
        {s.profile_id && <span className="linked-to" title="its reference set and LoRA follow through the profile mention">
          {hero ? <img src={api.thumbUrl(hero, 256)} alt="" /> : <span className="glyph">{fieldGlyph(linked?.cls ?? 'character')}</span>}{linked?.name ?? 'a Cast profile'}
          <button className="quiet" aria-label={`unlink subject ${i + 1}`} title="Unlink: a free subject again (the words stay)" onClick={() => g.unlinkSubject(i)}><X size={11} /> unlink</button></span>}
        <SubjectSlots slots={slots} />
        <span className="spacer" /><button className="quiet" title="Remove this subject" onClick={() => g.removeSubject(i)}><X size={12} /> remove</button></div>
      <CastPicker s={s} i={i} />
      {offer && <div className="subject-cast-row"><CastButton offer={offer} onCast={() => runOnSubject(i, 'gen.subject.cast')} /></div>}
      <Field section="prompt" label="description" field="subject.description" multiline rows={2} value={s.description} onChange={(v) => set({ description: v })} id={`gen-subject-desc-${i}`}
        placeholder={s.profile_id ? `describe ${name || 'the character'}'s look — e.g. a wiry courier in a long grey coat, red scarf` : 'who/what; literal text in quotes; bind colours here ("a #F2A93B brass compass")'}
        after={s.profile_id ? <SubjectWarn name={name} nameOnly={nameOnly(s.description, name)} ask={g.castAsk === i && needsLook(s.description, name)} refs={pm?.asset_ids?.length ?? 0} /> : null} />
      <Field section="prompt" label="position" field="subject.position" value={s.position ?? ''} onChange={(v) => set({ position: v })} placeholder="where in frame" />
      <Field section="prompt" label="action" field="subject.action" value={s.action ?? ''} onChange={(v) => set({ action: v })} />
      <Field section="prompt" label="pose" field="subject.pose" value={s.pose ?? ''} onChange={(v) => set({ pose: v })} />
      <label>colour match</label>
      <select value={s.color_match ?? 'exact'} onChange={(e) => set({ color_match: e.target.value })}><option value="exact">exact</option><option value="approximate">approximate</option><option value="">—</option></select>
    </div>
  )
}

/** The negative prompt where the model honours one (B12); the recipe sends none otherwise. */
const negativeField = (g: ReturnType<typeof useGenerate.getState>, cap: ModelCap | undefined) => (!cap || honoursNegative(cap)
  ? <div className="gen-form"><Field section="prompt" field="negative" value={g.panel.negative} onChange={(v) => g.set({ negative: v })} placeholder="what to keep out of the image" /></div>
  : null)

function PromptSection() {
  const g = useGenerate()
  const p = g.panel
  const t = p.tree
  const pv = g.preview
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const wc = pv?.word_count ?? 0
  const counterClass = wc === 0 ? '' : wc >= 30 && wc <= 80 ? 'ok' : wc > 120 ? 'warn' : ''
  return (
    <Section id="prompt" title="Prompt" words tools={<span className={`counter ${counterClass}`}>{wc} words · ≈{pv?.token_estimate ?? 0} tokens</span>}>
      <div className="segmented" style={{ marginBottom: 8 }}>
        {(['tree', 'text', 'json'] as const).map((m) => <button key={m} className={p.prompt_mode === m ? 'active' : ''} onClick={() => { if (m === 'json' && p.prompt_mode === 'tree') g.treeToJson(); else if (m === 'tree' && p.prompt_mode === 'json') { if (!g.jsonToTree()) return } else g.set({ prompt_mode: m }) }}>{m === 'tree' ? 'Tree' : m === 'json' ? 'JSON' : 'Text'}</button>)}
      </div>
      {p.prompt_mode === 'tree' && (
        <div className="gen-form gen-tree">
          <Field section="prompt" field="scene" multiline rows={2} value={t.scene ?? ''} onChange={(v) => g.setTree({ scene: v })} placeholder="the scene in a sentence" />
          {(t.subjects ?? []).map((s, i) => <SubjectCard key={i} i={i} s={s} />)}
          <div className="full"><button onClick={g.addSubject} title="Add a subject card: a Cast character or prop, or free words — where, doing what"><Plus size={12} /> subject</button></div>
          <Field section="prompt" label="lead text" field="text" value={p.text} onChange={(v) => g.set({ text: v })} placeholder="optional sentence before the tree — the same text as Text mode" />
        </div>
      )}
      {p.prompt_mode === 'json' && (
        <div>
          <textarea value={p.json_text} onChange={(e) => g.set({ json_text: e.target.value })} rows={14} style={{ width: '100%', font: 'var(--mono)' }} spellCheck={false} aria-label="prompt JSON" />
          <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
            <button onClick={() => { try { g.set({ json_text: JSON.stringify(JSON.parse(p.json_text || '{}'), null, 2) }) } catch { /* keep */ } }}>pretty</button>
            <button onClick={() => { try { g.set({ json_text: JSON.stringify(JSON.parse(p.json_text || '{}')) }) } catch { /* keep */ } }}>compact</button>
            <button onClick={() => void navigator.clipboard?.readText().then((x) => { try { JSON.parse(x); g.set({ json_text: x }) } catch { useSession.getState().toast('Clipboard is not JSON', 'error') } })}>import clipboard</button>
          </div>
          {g.previewError && <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 6 }}>{g.previewError}</div>}
        </div>
      )}
      {p.prompt_mode === 'text' && <TextPrompt />}
      <div style={{ marginTop: 8 }}>{negativeField(g, cap)}</div>
    </Section>
  )
}

// ------------------------------------------------------------------ references
function RefSlots() {
  const g = useGenerate()
  const p = g.panel
  const caps = useSession((s) => s.capabilities)
  const cap = caps?.models[p.model_id]
  const max = cap?.max_refs ?? 4
  const suggest = cap?.inputs.refs_suggest
  const suggestCap = suggest ? caps?.models[suggest.model] : undefined
  const slots = Array.from({ length: Math.min(10, Math.max(max, p.refs.length)) }, (_, i) => p.refs[i])
  const { ref: dropRef, over } = useDropTarget((d) => onlyAssets(d) && refDropFor(d).verdict.ok, dropRefs, (d) => refDropFor(d).verdict)
  return (
    <>
      <div ref={dropRef} className="ref-slots">
        {slots.map((r, i) => (
          <div key={i} className={`ref-slot${over ? ' over' : ''}`} title={r ? `reference image ${i + 1}` : `drop a Catalogue tile here, or select one and press R · reference ${i + 1}`}
            onContextMenu={(e) => { if (!r) return; showMenu(e, [
              { label: 'Remove reference', icon: X, run: () => g.removeRef(r.asset_id) },
              { label: 'Move first', disabled: i === 0, run: () => g.moveRef(i, 0) },
              { label: 'Move left', disabled: i === 0, run: () => g.moveRef(i, i - 1) },
              { label: 'Move right', disabled: i >= p.refs.length - 1, run: () => g.moveRef(i, i + 1) },
              sep, { cmd: 'gen.clearRefs' },
            ]) }}>
            {r ? <>
              <img src={api.thumbUrl(r.asset_id, 256)} alt="" />
              <span className="n">{i + 1}</span>
              <button className="quiet x" title="Remove" onClick={() => g.removeRef(r.asset_id)}>✕</button>
              {i > 0 && <button className="quiet mv" title="Move left" onClick={() => g.moveRef(i, i - 1)}>◀</button>}
            </> : <span className="empty">{i + 1}</span>}
          </div>
        ))}
      </div>
      <RefExtras />
      <div className="gen-form" style={{ marginTop: 6 }}>
        <label>downscale</label>
        <div><select value={p.ref_max_px} onChange={(e) => g.set({ ref_max_px: Number(e.target.value) })} title="a 1024² reference ≈ 4 096 tokens"><option value={512}>≤ 512²</option><option value={768}>≤ 768²</option><option value={1024}>≤ 1024² (default)</option><option value={0}>original size</option></select></div>
      </div>
      {suggest && p.refs.length >= suggest.at && <p className="disabled-why">{suggestCap?.label ?? suggest.model} is suggested for ≥ {suggest.at} references ({suggest.why}).</p>}
    </>
  )
}

function RefsSection() {
  const p = useGenerate((g) => g.panel)
  const cap = useSession((s) => s.capabilities?.models[p.model_id])
  const max = cap?.max_refs ?? 4
  return (
    <Section id="refs" title={`References · ${p.refs.length} of ${max}`}>
      {cap && !max
        ? <div className="disabled-why">{cap.label} takes no reference images{p.refs.length ? ` — the ${p.refs.length} in the slots are not sent ` : ''}{p.refs.length > 0 && <CommandButton id="gen.clearRefs" text />}</div>
        : <RefSlots />}
    </Section>
  )
}

// ------------------------------------------------------------------ look and camera (Tree-mode fields; the Story style in every mode)
const treeOnly = (mode: string) => mode !== 'tree' && <p className="disabled-why">These are fields of the Tree prompt — switch the prompt to Tree to use them.</p>

function LookSection() {
  const g = useGenerate()
  const t = g.panel.tree
  const tree = g.panel.prompt_mode === 'tree'
  const swatches = useSwatches()
  const lib = useLibrary((l) => l.library)
  const jobs = useSession((s) => s.jobs)
  useEffect(() => { if (!swatches.loaded) void swatches.load() }, [swatches.loaded]) // eslint-disable-line react-hooks/exhaustive-deps
  const missing = (lib?.entries ?? []).filter((e) => needsPicture(e.field, e.text) && !swatches.url(e.field, e.text) && !swatchJob(jobs, e.field, e.text))   // D92: the library's looks without a picture
    .map((e) => ({ field: e.field, value: e.text }))
  const makeAll = async () => {
    if (!(await askConfirm({ title: 'Make sample icons', okLabel: `Make ${missing.length}`, text: `${missing.length} small sample images (one per look in the library that has none yet), queued now on the sample model (Settings › Samples). They are kept with the app, not the project, and each can be remade from its right-click menu.` }))) return
    const n = await swatches.make(missing)
    if (n) useSession.getState().toast(`${n} sample icon${n === 1 ? '' : 's'} queued`, 'info')
  }
  return (
    <Section id="look" title="Look" words tools={missing.length > 0 && <button type="button" className="quiet" onClick={() => void makeAll()} title="Generate a small sample image for every look preset that has none yet"><ImagePlus size={14} /> {missing.length}</button>}>
      <StylePicker />
      {treeOnly(g.panel.prompt_mode)}
      {tree && (
        <div className="gen-form gen-tree">
          <Field section="look" field="lighting" value={t.lighting ?? ''} onChange={(v) => g.setTree({ lighting: v })} />
          <Field section="look" field="mood" value={t.mood ?? ''} onChange={(v) => g.setTree({ mood: v })} />
          <Field section="look" label="art style" field="style" value={t.style ?? ''} onChange={(v) => g.setTree({ style: v })} placeholder="words for the look — the Story style above is separate" />
          <Field section="look" field="background" value={t.background ?? ''} onChange={(v) => g.setTree({ background: v })} />
          <Field section="look" field="composition" value={t.composition ?? ''} onChange={(v) => g.setTree({ composition: v })} />
          <label>palette</label>
          <div className="swatches" title="bind colours to objects in the subject descriptions; the palette alone is weak">
            {(t.color_palette ?? []).map((c, i) => <span key={i} className="swatch" style={{ background: c }} title={c}><input type="color" aria-label={`colour ${i + 1}`} value={/^#[0-9a-f]{6}$/i.test(c) ? c : '#888888'} onChange={(e) => { const pal = [...(t.color_palette ?? [])]; pal[i] = e.target.value.toUpperCase(); g.setTree({ color_palette: pal }) }} /><button type="button" className="quiet x" aria-label={`remove colour ${i + 1}`} onClick={() => g.setTree({ color_palette: (t.color_palette ?? []).filter((_, j) => j !== i) })}>×</button></span>)}
            <button title="Add a colour" onClick={() => g.setTree({ color_palette: [...(t.color_palette ?? []), '#F2A93B'] })}>+</button>
          </div>
        </div>
      )}
    </Section>
  )
}

function CameraSection() {
  const g = useGenerate()
  const c = g.panel.tree.camera
  const cam = (patch: Partial<NonNullable<typeof c>>) => g.setCamera(patch)
  return (
    <Section id="camera" title="Camera" words>
      {treeOnly(g.panel.prompt_mode)}
      {g.panel.prompt_mode === 'tree' && (
        <div className="gen-form gen-tree">
          <Field section="camera" label="shot size" field="camera.distance" value={c?.distance ?? ''} onChange={(v) => cam({ distance: v })} />
          <Field section="camera" label="angle" field="camera.angle" value={c?.angle ?? ''} onChange={(v) => cam({ angle: v })} />
          <Field section="camera" label="lens" field="camera.lens" value={c?.lens ?? ''} onChange={(v) => cam({ lens: v })} />
          <Field section="camera" label="depth of field" field="camera.depth_of_field" value={c?.depth_of_field ?? ''} onChange={(v) => cam({ depth_of_field: v })} />
          <Field section="camera" label="aperture" field="camera.f-number" value={c?.['f-number'] ?? ''} onChange={(v) => cam({ 'f-number': v })} />
        </div>
      )}
    </Section>
  )
}

// ------------------------------------------------------------------ model
function ModelSection() {
  const g = useGenerate()
  const p = g.panel
  const caps = useSession((s) => s.capabilities)
  const models = useSession((s) => s.models)
  const pv = g.preview
  const cap = caps?.models[p.model_id]
  const teOpts = cap?.te_options ?? []                                    // D31: an encoder picker only where the model has an alternate
  const teEff = teOpts.find((o) => (p.te_id ? o.id === p.te_id : o.default))
  const teGguf = !!teEff?.gguf
  useEffect(() => {
    if (p.te_id && cap && !teOpts.some((o) => o.id === p.te_id)) g.set({ te_id: null })
    else if (teGguf && p.te_device) g.set({ te_device: null })
  }, [p.te_id, p.te_device, cap, teGguf]) // eslint-disable-line react-hooks/exhaustive-deps
  const shiftCustom = p.base_shift !== null || p.max_shift !== null
  const modelShift = cap?.model_shift ?? 2.02
  const nodeDefaults = caps?.advanced?.shift_node_defaults ?? { base: 0.5, max: 1.15 }
  const flux2 = caps?.advanced?.flux2_schedule ?? 'flux2'
  const sampling = p.steps !== null || p.guidance !== null || p.cfg !== null || !!p.sampler || !!p.scheduler || p.seed_mode !== 'random' || p.turbo
  return (
    <Section id="model" title="Model">
      <div className="model-grid compact">
        {byOrder(caps?.models).filter(([, c]) => c.recipes.t2i).map(([m, c]) => {   /* D89: Refine-only models (SD 3.5) are Edit's */
          const r = models.find((x) => x.id === m)
          const off = !c.wired
          return (
            <button key={m} className={`model-card${p.model_id === m ? ' active' : ''}${off ? ' off' : ''}`} onClick={() => !off && g.setModel(m)} disabled={off}
              title={[c.hint, r?.license, c.health, c.distilled ? 'distilled' : '', off ? 'not available in this build' : ''].filter(Boolean).join(' · ')}>
              <span>{c.label}</span><i className={`dot ${c.health === 'missing' ? 'warn' : 'ok'}`} />
            </button>
          )
        })}
      </div>
      {cap?.turbo && <label className="chk" style={{ marginTop: 6 }}><input type="checkbox" checked={p.turbo} onChange={(e) => g.set({ turbo: e.target.checked, steps: null })} /> 8-step Turbo LoRA{p.turbo && <> · strength <input type="number" step={0.05} min={0} max={2} value={p.turbo_strength} onChange={(e) => g.set({ turbo_strength: Number(e.target.value) })} style={{ width: 64 }} /></>}</label>}
      <details className="advanced" open={sampling}>
        <summary>Sampling</summary>
        <div className="gen-form">
          <label>steps</label>
          <div><input type="number" min={1} max={200} value={p.steps ?? pv?.steps ?? cap?.steps ?? 20} disabled={!!cap?.distilled} onChange={(e) => g.set({ steps: Number(e.target.value) })} style={{ width: 90 }} />
            {cap?.distilled ? <span className="disabled-why"> fixed at {cap.steps} (distilled)</span> : p.steps !== null && <button className="quiet" onClick={() => g.set({ steps: null })}>reset</button>}</div>
          {(!cap || cap.guidance_node) && <><label>guidance</label>
            <div><input type="number" step={0.1} min={0} max={10} value={p.guidance ?? pv?.guidance ?? cap?.guidance ?? 4} onChange={(e) => g.set({ guidance: Number(e.target.value) })} style={{ width: 90 }} />{p.guidance !== null && <button className="quiet" onClick={() => g.set({ guidance: null })}>reset</button>}</div></>}
          <label>CFG</label>
          <div><input type="number" step={0.1} min={1} max={10} value={p.cfg ?? pv?.cfg ?? cap?.cfg ?? 1} disabled={!!cap?.distilled || !!cap?.cfg_fixed} onChange={(e) => g.set({ cfg: Number(e.target.value) })} style={{ width: 90 }} />
            {cap?.distilled || cap?.cfg_fixed ? <span className="disabled-why"> {cap?.distilled ? 'fixed (distilled)' : cap?.cfg_note ?? ''}</span> : p.cfg !== null && <button className="quiet" onClick={() => g.set({ cfg: null })}>reset</button>}</div>
          <label>sampler</label>
          <select value={p.sampler ?? ''} onChange={(e) => g.set({ sampler: e.target.value || null })}><option value="">preset ({cap?.sampler ?? 'euler'})</option>{caps?.samplers.map((x) => <option key={x}>{x}</option>)}</select>
          <label>scheduler</label>
          <select value={p.scheduler ?? ''} onChange={(e) => g.set({ scheduler: e.target.value || null })}><option value="">preset ({cap?.scheduler ?? 'simple'})</option>{caps?.schedulers.filter((x) => x !== flux2 || cap?.flux_shift !== false).map((x) => <option key={x} value={x}>{x === flux2 ? `${x} · resolution-shifted sigmas` : x}</option>)}</select>
          <label>seed</label>
          <div><div className="segmented">{(['random', 'fixed', 'increment'] as const).map((m) => <button key={m} className={p.seed_mode === m ? 'active' : ''} onClick={() => g.set({ seed_mode: m })}>{m}</button>)}</div>
            {p.seed_mode !== 'random' && <input type="number" value={p.seed} aria-label="seed" onChange={(e) => g.set({ seed: Number(e.target.value) })} style={{ width: 120, marginLeft: 6 }} />}
            {p.seed_mode !== 'random' && <button className="quiet" title="A new random seed" onClick={() => g.set({ seed: Math.floor(Math.random() * 2 ** 31) })}>new</button>}</div>
        </div>
      </details>
      <details className="advanced" open={p.loras.length > 0}>
        <summary>LoRAs{p.loras.length ? ` · ${p.loras.length}` : ''}</summary>
        <LoraSlots />
      </details>
      <details className="advanced" open={shiftCustom || !!p.weight_dtype || !!p.te_device || !!p.te_id || p.tiled_vae}>
        <summary>Advanced</summary>
        <div className="gen-form">
          {(!cap || cap.flux_shift !== false) && <><label>shift</label>   {/* D90 (B12): only where the graph has ModelSamplingFlux */}
            <div>
              <div className="segmented"><button className={!shiftCustom ? 'active' : ''} onClick={() => g.set({ base_shift: null, max_shift: null })}>model ({modelShift})</button><button className={shiftCustom ? 'active' : ''} onClick={() => g.set({ base_shift: nodeDefaults.base, max_shift: nodeDefaults.max })}>custom</button></div>
              {shiftCustom && <span className="disabled-why"> base <input type="number" step={0.05} min={0} max={10} value={p.base_shift ?? nodeDefaults.base} onChange={(e) => g.set({ base_shift: Number(e.target.value) })} style={{ width: 64 }} /> max <input type="number" step={0.05} min={0} max={10} value={p.max_shift ?? nodeDefaults.max} onChange={(e) => g.set({ max_shift: Number(e.target.value) })} style={{ width: 64 }} /></span>}
            </div></>}
          <label>weights</label>
          <select value={p.weight_dtype ?? ''} onChange={(e) => g.set({ weight_dtype: e.target.value || null })}><option value="">preset ({pv?.weight_dtype ?? 'default'})</option>{caps?.weight_dtypes.map((x) => <option key={x}>{x}</option>)}</select>
          <label>text encoder</label>
          <div>{teOpts.length > 1 && <select value={p.te_id ?? ''} title="Which weights encode the prompt (D31)" onChange={(e) => g.set({ te_id: e.target.value || null })}>{teOpts.map((o) => <option key={o.id} value={o.default ? '' : o.id}>{o.default ? `preset · ${o.label}` : o.label}{o.health === 'missing' ? ' (not fetched)' : ''}</option>)}</select>}
            {teOpts.length > 1 && ' '}<select value={p.te_device ?? ''} disabled={teGguf} title={teGguf ? 'a GGUF encoder loads on the GPU' : 'where the encoder runs — the CPU saves VRAM and costs time per new prompt'} onChange={(e) => g.set({ te_device: e.target.value || null })}><option value="">{teGguf ? 'GPU' : 'preset (GPU)'}</option>{!teGguf && caps?.te_devices.filter((x) => x !== 'default').map((x) => <option key={x} value={x}>{x}</option>)}</select></div>
          <label>decode</label>
          <div><label className="chk"><input type="checkbox" checked={p.tiled_vae} onChange={(e) => g.set({ tiled_vae: e.target.checked })} /> tiled VAE</label>
            {p.tiled_vae && <span className="disabled-why"> · tile <input type="number" step={32} min={64} max={4096} value={p.tile_size} onChange={(e) => g.set({ tile_size: Number(e.target.value) })} style={{ width: 72 }} /> px</span>}</div>
        </div>
      </details>
    </Section>
  )
}

// ------------------------------------------------------------------ size and count
function SizeSection() {
  const g = useGenerate()
  const p = g.panel
  const caps = useSession((s) => s.capabilities)
  const fmt = useSession((s) => s.project?.format)
  const fam = caps?.models[p.model_id]?.family ?? ''
  const tiers = caps?.tiers ?? {}
  const projectAspect = fmt ? `${fmt.aspect[0]}:${fmt.aspect[1]}` : '16:9'
  const applyAspect = (aw: number, ah: number) => { const w = Math.sqrt(p.width * p.height * aw / ah); g.set({ width: snap16(w), height: snap16(w * ah / aw), tier: 'custom' }) }
  const pv = g.preview
  const tierItems: PresetIcon[] = (['thumb', 'draft', 'full'] as const).flatMap((t) => { const wh = tiers[t]?.[fam]; return wh ? [{ id: t, label: `${t} · ${wh[0]}×${wh[1]}`, icon: tierGlyph(t), hint: t === 'draft' ? 'the default (D18)' : undefined }] : [] })
  return (
    <Section id="size" title={`Size · ${p.width}×${p.height}`}>
      <div className="gen-form">
        <label>aspect</label>
        <PresetIcons label="aspect" size={36} items={ASPECTS.map(([n, aw, ah]) => ({ id: n, label: n, icon: aspectGlyph(aw, ah), hint: n === projectAspect ? 'the project format' : undefined, badge: n === projectAspect ? '★' : undefined }))}
          selected={ASPECTS.find(([, aw, ah]) => Math.abs(p.width / p.height - aw / ah) < 0.02)?.[0] ?? null} onPick={(id) => { const a = ASPECTS.find(([n]) => n === id); if (a) applyAspect(a[1], a[2]) }} />
        <label>size</label>
        <PresetIcons label="size tier" size={36} items={[...tierItems, { id: 'custom', label: 'custom size', icon: tierGlyph('custom') }]} selected={p.tier}
          onPick={(id) => { const wh = tiers[id]?.[fam]; g.set(id === 'custom' || !wh ? { tier: 'custom' } : { tier: id as PanelState['tier'], width: wh[0], height: wh[1] }) }} />
        {p.tier === 'custom' && <><label>pixels</label>
          <div><input type="number" step={16} min={64} max={2048} value={p.width} aria-label="width" onChange={(e) => g.set({ width: snap16(Number(e.target.value)), tier: 'custom' })} style={{ width: 80 }} /> × <input type="number" step={16} min={64} max={2048} value={p.height} aria-label="height" onChange={(e) => g.set({ height: snap16(Number(e.target.value)), tier: 'custom' })} style={{ width: 80 }} />
            <span className="disabled-why"> {Math.round(p.width * p.height / 1e4) / 100} MP</span></div></>}
        <label>count</label>
        <div className="stepper"><button onClick={() => g.set({ count: Math.max(1, p.count - 1) })} disabled={p.count <= 1} aria-label="fewer"><Minus size={12} /></button><b aria-label="count">{p.count}</b><button onClick={() => g.set({ count: Math.min(8, p.count + 1) })} disabled={p.count >= 8} aria-label="more"><Plus size={12} /></button><span className="disabled-why"> one seed each</span></div>
      </div>
      <div className="estimate"><span className={`dot ${pv?.estimate.vram_fit ?? 'ok'}`} />{pv?.estimate.seconds ? `≈ ${Math.round(pv.estimate.seconds)} s each · ${Math.round(pv.estimate.seconds * p.count)} s for ${p.count}` : '…'}{pv?.estimate.vram_gb ? ` · VRAM ≈ ${pv.estimate.vram_gb} of ${pv.estimate.vram_budget_gb ?? '?'} GB` : ''}</div>
    </Section>
  )
}

// ------------------------------------------------------------------ saved panels and the preview
function SavedSection() {
  const g = useGenerate()
  const caps = useSession((s) => s.capabilities)
  useEffect(() => { void g.loadPresets() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Section id="presets" title="Saved panels" tools={<CommandButton id="gen.savePreset" className="quiet" size={14} />}>
      {g.presets.length
        ? <PresetIcons label="saved panels" size={44} showText items={g.presets.map((pr) => ({ id: pr.name, label: pr.name, hint: caps?.models[pr.panel.model_id]?.label ?? pr.panel.model_id, icon: fieldGlyph('panel'), img: pr.thumb_asset_id ? api.thumbUrl(pr.thumb_asset_id, 256) : null }))} selected={g.lastPreset}
            onPick={(id) => g.applyPreset(id)} onContext={(id, e) => { sy().select({ kind: 'panel', id }); showMenu(e, [{ cmd: 'story.world.applyPanel', label: 'Apply' }, { cmd: 'story.world.renamePanel' }, { cmd: 'story.world.editEntry', label: 'Show in Story · World' }, sep, { cmd: 'story.world.remove', label: `Delete "${id}"…` }]) }} />
        : <p className="disabled-why">None yet — the bookmark above saves every field of the panel under a name.</p>}
    </Section>
  )
}

function PreviewSection() {
  const pv = useGenerate((g) => g.preview)
  const previewing = useGenerate((g) => g.previewing)
  return (
    <details id="gen-sec-preview" className="gen-sec preview-sec">
      <summary>Preview · the prompt as sent{pv ? ` (${pv.prompt_mode === 'json' ? 'JSON in the Mistral template' : pv.prompt_mode === 'prose' ? 'prose for Klein' : 'plain text'})` : ''}</summary>
      <div className="preview-box">{pv?.serialized_prompt || (previewing ? '…' : '(empty prompt)')}</div>
      {!!pv?.bindings?.length && <ul className="preview-bindings" aria-label="subjects and their reference images">{/* D93 (A3): what each linked subject got, what was left out */}
        {bindingLines(pv.bindings, pv.max_refs).map((t) => <li key={t}>{t}</li>)}
        {!pv.bind_refs && <li className="muted">this model reads the references by their notes — the subjects are not bound in its prompt</li>}</ul>}
    </details>
  )
}

/** Opens the Preview at the end of the column (the Foot's Preview button). */
function showPreview(): void {
  const d = document.getElementById('gen-sec-preview') as HTMLDetailsElement | null
  if (d) { d.open = true; d.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }
}

// ------------------------------------------------------------------ the column and its rail sync
export function GenerateColumn({ tab }: { tab: string }) {
  const host = useRef<HTMLDivElement>(null)
  const fromScroll = useRef(false)
  const active = useRef(tab)
  useEffect(() => {                                                       // a rail click (or a deep link) scrolls to its section
    active.current = tab
    if (fromScroll.current) { fromScroll.current = false; return }
    document.getElementById(`gen-sec-${tab}`)?.scrollIntoView({ block: 'start' })
  }, [tab])
  useEffect(() => {                                                       // … and scrolling moves the rail's highlight
    const body = host.current?.closest('.body') as HTMLElement | null
    if (!body) return
    const h = () => {
      const top = body.getBoundingClientRect().top + 24
      let cur: string = SECTION_IDS[0]
      for (const id of SECTION_IDS) { const el = document.getElementById(`gen-sec-${id}`); if (el && el.getBoundingClientRect().top <= top) cur = id }
      if (cur !== active.current) { active.current = cur; fromScroll.current = true; setRailTab('generate', cur) }
    }
    body.addEventListener('scroll', h, { passive: true })
    return () => body.removeEventListener('scroll', h)
  }, [])
  return (
    <div ref={host} className="gen-column">
      <ForChip maker="generate" />{/* D90 (02 §5): opened for a shot — the results come back as its takes */}
      <SavedSection />
      <PromptSection />
      <RefsSection />
      <LookSection />
      <CameraSection />
      <ModelSection />
      <SizeSection />
      <PreviewSection />
    </div>
  )
}

/** The Foot's Preview button. */
export function PreviewButton() {
  return <button onClick={showPreview} title="Show the prompt exactly as it is sent (style fragment and LoRA triggers included)">Preview</button>
}

