// D110 (PS4): a light of the 3D scene in the Inspector — its strength, colour, the softness of its shadow, whether it casts one, and where it
// aims (a point, or an object picked from the list: a figure's chest, another object's top); with three looks to start from. The stage's
// ambient level (the sky) sits with the stage's own fields.
import type { StageObject } from '../../api/types'
import { Help } from '../../frame/Help'
import { st, useStage } from './stageStore'

type Light = NonNullable<StageObject['light']>
/** A light object without settings shines as E23c's key (stages.py LightSpec). */
const E23C_KEY: Light = { intensity: 2.3, colour: '#ffffff', softness: 0, shadows: true, target: [0, 1, 0] }
/** Three looks to start from — set the strength, colour and softness together (the aim stays). */
const LOOKS: { id: string; label: string; hint: string; s: Pick<Light, 'intensity' | 'colour' | 'softness'> }[] = [
  { id: 'window', label: 'Window', hint: 'a soft, slightly warm daylight', s: { intensity: 2.0, colour: '#fff1dc', softness: 0.7 } },
  { id: 'sun', label: 'Sun', hint: 'strong, white, hard-edged shadows', s: { intensity: 3.5, colour: '#ffffff', softness: 0.1 } },
  { id: 'lamp', label: 'Lamp', hint: 'a warm, dimmer light', s: { intensity: 1.4, colour: '#ffc98a', softness: 0.5 } },
]

/** Where a light aims at an object: a figure's chest, else a little above the object's foot. */
function aimPoint(o: StageObject): number[] {
  const p = o.transform.pos
  return [p[0], p[1] + (o.kind === 'mannequin' ? 1.2 : 0.4), p[2]]
}
const num = (x: number) => Math.round(x * 100) / 100

export function LightControls({ o }: { o: StageObject }) {
  const objects = useStage((s) => s.current?.objects ?? [])
  const s = o.light ?? E23C_KEY
  const set = (patch: Partial<Light>) => st().updateObject(o.id, { light: { ...s, ...patch } })
  const targets = objects.filter((x) => x.id !== o.id && x.kind !== 'light')
  return (
    <div className="light-controls">
      <div className="kv"><span>look</span><span className="looks">{LOOKS.map((l) => <button key={l.id} className="quiet" title={l.hint} onClick={() => set(l.s)}>{l.label}</button>)}</span></div>
      <div className="kv"><span>intensity</span><span className="range-row"><input type="range" min={0} max={10} step={0.1} value={s.intensity} aria-label="light intensity" onChange={(e) => set({ intensity: Number(e.target.value) })} /><span className="n">{s.intensity.toFixed(1)}</span></span></div>
      <div className="kv"><span>colour</span><input type="color" value={s.colour} aria-label="light colour" onChange={(e) => set({ colour: e.target.value })} /></div>
      <div className="kv"><span>softness</span><span className="range-row"><input type="range" min={0} max={1} step={0.05} value={s.softness} aria-label="shadow softness" onChange={(e) => set({ softness: Number(e.target.value) })} /><span className="n">{s.softness.toFixed(2)}</span></span></div>
      <div className="kv"><span>shadows</span><input type="checkbox" checked={s.shadows} aria-label="casts shadows" onChange={(e) => set({ shadows: e.target.checked })} /></div>
      <div className="kv"><span>aims at</span><span className="vec">{s.target.map((x, i) => <input key={i} type="number" step={0.1} value={num(x)} aria-label={`aim ${'xyz'[i]}`}
        onChange={(e) => { const t = [...s.target]; t[i] = Number(e.target.value) || 0; set({ target: t }) }} />)}</span></div>
      {targets.length > 0 && <div className="kv"><span>aim at</span><select value="" aria-label="aim the light at an object" onChange={(e) => { const t = targets.find((x) => x.id === e.target.value); if (t) set({ target: aimPoint(t) }) }}>
        <option value="">an object…</option>{targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>}
      {!o.light && <p className="hint">As the key light <Help text="Shining as the first key light did (hard shadows); any change gives it settings of its own." /></p>}
    </div>
  )
}

/** The stage's ambient level — the sky's fill under the lights (0.85 by default, 1.1 with no light). */
export function AmbientControl() {
  const doc = useStage((s) => s.current)
  if (!doc) return null
  const lit = doc.objects.some((o) => o.kind === 'light' && o.visible)
  const v = doc.ambient ?? (lit ? 0.85 : 1.1)
  return (
    <div className="kv"><span>ambient</span><span className="range-row"><input type="range" min={0} max={2} step={0.05} value={v} aria-label="ambient light" onChange={(e) => st().setAmbient(Number(e.target.value))} />
      <span className="n">{v.toFixed(2)}</span>{doc.ambient != null && <button className="quiet" title="Back to the default for the lights on the stage" onClick={() => st().setAmbient(null)}>default</button>}</span></div>
  )
}

