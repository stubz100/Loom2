// AE3 (proto01_animate 20 §2, D114): the Effects section at the Final level — the curated effects as icon tiles (one click adds the
// effect to the selected layer: `effect.apply`), the layer's effects with their dials (a few of the engine's parameters each, by type:
// number with its range, choice, switch, colour, point, a layer; the rest keep the engine's defaults), enabled / reset / remove. The
// definitions — names, parameters, ranges, options — come from the engine (`GET …/composition/effects`), never a copy here (T8).
import { Aperture, BarChart3, Box, Circle, Contrast, Droplet, Eraser, Feather, Grip, Layers, Maximize2, Minimize2, Moon, MoveHorizontal, Palette, Scale, Spline, Sun, SunDim, SunMedium, Triangle, type LucideIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NumField } from './FinalEditor'
import { useComposition, type EffectDef, type EffectInfo, type EffectParam } from './compositionStore'

type Group = 'colour' | 'soften' | 'edges' | 'mood'
interface Curated { name: string; group: Group; icon: LucideIcon; dials: string[]; hint: string }
const GROUPS: Record<Group, string> = { colour: 'Colour', soften: 'Soften and match', edges: 'Edges and mattes', mood: 'Mood' }
/** The curated effects and the dials shown for each (the engine's parameter ids). */
const CURATED: Curated[] = [
  { name: 'Lumetri Color', group: 'colour', icon: SunMedium, hint: 'exposure, contrast, highlights and shadows, white balance, saturation',
    dials: ['basicCorrection/tone/exposure', 'basicCorrection/tone/contrast', 'basicCorrection/tone/highlights', 'basicCorrection/tone/shadows', 'basicCorrection/tone/whites', 'basicCorrection/tone/blacks', 'basicCorrection/whiteBalance/temperature', 'basicCorrection/whiteBalance/tint', 'basicCorrection/saturation'] },
  { name: 'Curves', group: 'colour', icon: Spline, hint: 'the RGB curve as points "x,y x,y …" from 0,0 to 1,1', dials: ['rgb'] },
  { name: 'Levels', group: 'colour', icon: BarChart3, hint: 'input and output black and white, gamma', dials: ['inBlack', 'inWhite', 'gamma', 'outBlack', 'outWhite'] },
  { name: 'Hue/Saturation', group: 'colour', icon: Palette, hint: 'hue, saturation, lightness', dials: ['hue', 'saturation', 'lightness'] },
  { name: 'Tint', group: 'colour', icon: Droplet, hint: 'black and white mapped to two colours', dials: ['black', 'white', 'amount'] },
  { name: 'Color Balance', group: 'colour', icon: Scale, hint: 'red, green, blue in the shadows, midtones and highlights', dials: ['shadowRed', 'shadowGreen', 'shadowBlue', 'midRed', 'midGreen', 'midBlue', 'hiRed', 'hiGreen', 'hiBlue'] },
  { name: 'Gaussian Blur', group: 'soften', icon: Aperture, hint: 'a soft blur', dials: ['blurriness', 'dimensions'] },
  { name: 'Fast Box Blur', group: 'soften', icon: Box, hint: 'a quick blur', dials: ['radius', 'iterations'] },
  { name: 'Directional Blur', group: 'soften', icon: MoveHorizontal, hint: 'a blur along a direction (motion)', dials: ['direction', 'length'] },
  { name: 'Sharpen', group: 'soften', icon: Triangle, hint: 'sharpen', dials: ['amount'] },
  { name: 'Add Grain', group: 'soften', icon: Grip, hint: 'film grain', dials: ['tweaking/intensity', 'tweaking/size', 'tweaking/softness'] },
  { name: 'Match Grain', group: 'soften', icon: Layers, hint: 'the grain of another layer (the plate) on this one', dials: ['noiseSourceLayer', 'compensateForExistingNoise', 'tweaking/intensity'] },
  { name: 'Remove Grain', group: 'soften', icon: Eraser, hint: 'noise reduction', dials: ['noiseReductionSettings/noiseReduction', 'noiseReductionSettings/passes'] },
  { name: 'Simple Choker', group: 'edges', icon: Minimize2, hint: 'the matte choked or spread', dials: ['chokeMatte'] },
  { name: 'Matte Choker', group: 'edges', icon: Maximize2, hint: 'the matte choked with softness', dials: ['choke1', 'geometricSoftness1', 'grayLevelSoftness1'] },
  { name: 'Refine Soft Matte', group: 'edges', icon: Feather, hint: 'the matte edge refined', dials: ['radius', 'feather', 'contrast', 'shiftEdge', 'smooth'] },
  { name: 'Drop Shadow', group: 'edges', icon: Moon, hint: 'a shadow behind the layer', dials: ['color', 'opacity', 'direction', 'distance', 'softness'] },
  { name: 'Glow', group: 'mood', icon: Sun, hint: 'a glow on the bright parts', dials: ['threshold', 'radius', 'intensity'] },
  { name: 'CC Vignette', group: 'mood', icon: Circle, hint: 'darkened corners', dials: ['amount', 'angleOfView', 'pinHighlights'] },
  { name: 'Exposure', group: 'mood', icon: SunDim, hint: 'exposure, offset, gamma', dials: ['master/exposure', 'master/offset', 'master/gamma'] },
  { name: 'Black & White', group: 'mood', icon: Contrast, hint: 'black and white by colour, a tint', dials: ['reds', 'yellows', 'greens', 'cyans', 'blues', 'magentas', 'tint', 'tintColor'] },
]
const CURATED_NAMES = CURATED.map((c) => c.name)
const cp = () => useComposition.getState()
const short = (id: string) => id.split('/').pop()!.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()

const hex = (c: unknown): string => { const v = Array.isArray(c) ? (c as number[]) : [0, 0, 0]; return '#' + v.slice(0, 3).map((x) => Math.round(Math.max(0, Math.min(1, x)) * 255).toString(16).padStart(2, '0')).join('') }
const rgba = (h: string, old: unknown): number[] => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255, Array.isArray(old) && typeof old[3] === 'number' ? old[3] : 1]

/** A text typed, committed on Enter or blur (the Curves points, a file name). */
function TextField({ value, onCommit, label }: { value: string; onCommit: (v: string) => void; label: string }) {
  const [draft, setDraft] = useState(value)
  const commit = () => { if (draft !== value) onCommit(draft) }
  return <input type="text" value={draft} aria-label={label} onChange={(e) => setDraft(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit() } }} />
}

/** One dial: the field its type asks for, its value the engine's. */
function Dial({ path, param, value }: { path: string; param: EffectParam; value: unknown }) {
  const busy = useComposition((s) => s.busy)
  const layers = useComposition((s) => s.layers)
  const selected = useComposition((s) => s.selected)
  const set = (v: unknown) => void cp().setProp(path, v)
  const label = param.name || short(param.id)
  let field: React.ReactNode
  if (param.type === 'enum' && param.options) {
    field = <select value={String(value ?? param.default ?? 0)} disabled={busy} aria-label={label} onChange={(e) => set(Number(e.target.value))}>{param.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
  } else if (param.type === 'bool') {
    field = <input type="checkbox" checked={!!value} disabled={busy} aria-label={label} onChange={(e) => set(e.target.checked)} />
  } else if (param.type === 'color') {
    field = <input type="color" value={hex(value ?? param.default)} disabled={busy} aria-label={label} onChange={(e) => set(rgba(e.target.value, value ?? param.default))} />
  } else if (param.type === 'vec2' || param.type === 'vec3') {
    const v = Array.isArray(value) ? (value as number[]) : [0, 0, 0]
    field = <>{[0, 1].map((i) => <NumField key={`${i}:${v[i]}`} value={Number(v[i] ?? 0)} step={0.01} onCommit={(n) => { const next = [...v]; next[i] = n; set(next) }} label={`${label} ${'xy'[i]}`} />)}</>
  } else if (param.type === 'layer') {
    field = <select value={value === null || value === undefined ? '' : String(value)} disabled={busy} aria-label={label} onChange={(e) => set(e.target.value ? Number(e.target.value) : null)}>
      <option value="">none</option>{layers.filter((l) => l.id !== selected).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
  } else if (param.type === 'string') {
    field = <TextField key={String(value)} value={String(value ?? param.default ?? '')} onCommit={set} label={label} />
  } else {
    const range = param.max !== undefined && param.min !== undefined ? param.max - param.min : 100
    const step = param.decimals ? Math.pow(10, -param.decimals) : range <= 20 ? 0.1 : 1
    const clamp = (n: number) => Math.max(param.min ?? -Infinity, Math.min(param.max ?? Infinity, n))
    field = <NumField key={`v:${String(value)}`} value={Number(value ?? param.default ?? 0)} step={step} onCommit={(n) => set(clamp(n))} label={label} />
  }
  return <label className="dial" data-param={path} title={param.min !== undefined ? `${label}: ${param.min} to ${param.max}` : label}><span>{short(param.id)}</span>{field}</label>
}

function EffectRow({ e, def, dials }: { e: EffectInfo; def: EffectDef | undefined; dials: string[] }) {
  const busy = useComposition((s) => s.busy)
  const values = useComposition((s) => s.fxValues)
  const params = def ? dials.map((d) => def.params.find((p) => p.id === d)).filter((p): p is EffectParam => !!p) : []
  const rest = def ? def.params.length - params.length : 0
  return (
    <li className={`comp-effect${e.enabled ? '' : ' off'}`} data-effect={e.uid} data-name={e.name}>
      <div className="head">
        <input type="checkbox" checked={e.enabled} disabled={busy} aria-label={`${e.name} on`} title="On / off" onChange={(ev) => void cp().toggleEffect(e.uid, ev.target.checked)} />
        <span className="name">{e.name}</span>
        <span className="spacer" />
        <button type="button" className="quiet" title="Reset this effect to its defaults" disabled={busy} onClick={() => void cp().resetEffect(e.uid)}>reset</button>
        <button type="button" className="quiet danger" title="Remove this effect" disabled={busy} onClick={() => void cp().removeEffect(e.uid)}>×</button>
      </div>
      <div className="dials">
        {params.map((p) => <Dial key={p.id} path={`${e.path}/${p.id}`} param={p} value={values[`${e.path}/${p.id}`]} />)}
        {!def && <span className="hint">not one of the curated effects — its parameters stay as they are</span>}
        {rest > 0 && <span className="hint">{rest} more parameter{rest === 1 ? '' : 's'} at the engine's defaults</span>}
      </div>
    </li>
  )
}

/** The Effects part of the selected layer's editor (under its row in Layers, UX9 U1). */
export function EffectsBody() {
  const comp = useComposition((s) => s.comp)
  const finalId = useComposition((s) => s.finalId)
  const selected = useComposition((s) => s.selected)
  const effects = useComposition((s) => s.effects)
  const catalog = useComposition((s) => s.catalog)
  const busy = useComposition((s) => s.busy)
  useEffect(() => { if (finalId && comp && !Object.keys(catalog).length) void cp().loadCatalog(CURATED_NAMES) }, [finalId, comp?.final_id]) // eslint-disable-line react-hooks/exhaustive-deps
  const groups = (Object.keys(GROUPS) as Group[]).map((g) => ({ g, items: CURATED.filter((c) => c.group === g) }))
  return (
    <div className="comp-effects" data-layer={selected ?? undefined}>
      {groups.map(({ g, items }) => (
        <div key={g} className="fx-group"><span className="fx-group-name">{GROUPS[g]}</span>
          <div className="fx-tiles">{items.map((c) => { const known = !!catalog[c.name]; const Icon = c.icon
            return <button key={c.name} type="button" className="fx-tile" data-effect={c.name} disabled={busy || (Object.keys(catalog).length > 0 && !known)}
              title={`${c.name}: ${c.hint}${Object.keys(catalog).length > 0 && !known ? ' — not in this engine' : ''}`} onClick={() => void cp().addEffect(c.name)}><Icon size={16} /><span>{c.name}</span></button> })}</div>
        </div>))}
      {effects.length ? <ul className="comp-effect-list">{effects.map((e) => { const c = CURATED.find((x) => x.name === e.name.replace(/ \d+$/, '')); return <EffectRow key={e.uid} e={e} def={c ? catalog[c.name] : undefined} dials={c?.dials ?? []} /> })}</ul>
        : <span className="hint">No effect on this layer. Compare with <b>Before</b> under the viewer once there is one.</span>}
    </div>
  )
}
