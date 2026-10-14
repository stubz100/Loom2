// LT1 (18 §3e, D25): the four LoRA slots of Generate's Model tab. The picker lists what GET /loras offers for the model — the project's
// trained LoRAs first (LT2), the roster's free LoRAs, the files under the loras folder — with a strength per slot; the ones that do not
// fit stay visible but disabled with the sentence. The recipe carries loras[], the preview names the files, the manifest records them.
import { useEffect } from 'react'
import { useGenerate } from './generateStore'

const SLOTS = [0, 1, 2, 3]

export function LoraSlots() {
  const g = useGenerate()
  const p = g.panel
  const opts = g.lorasAvailable
  const modelId = p.model_id
  useEffect(() => { void g.loadLoras(modelId) }, [modelId]) // eslint-disable-line react-hooks/exhaustive-deps
  const fitting = opts.filter((o) => o.fits)
  const others = opts.filter((o) => !o.fits)
  const setSlot = (i: number, id: string) => {
    const next = p.loras.slice(0, 4)
    if (!id) { next.splice(i, 1) } else {
      const strength = next[i]?.strength ?? fitting.find((o) => o.id === id)?.strength ?? 1
      if (i < next.length) next[i] = { model_id: id, strength }
      else next.push({ model_id: id, strength })
    }
    g.set({ loras: next })
  }
  const setStrength = (i: number, v: number) => {
    const next = p.loras.map((l, j) => (j === i ? { ...l, strength: Math.max(0, Math.min(2, Number.isFinite(v) ? v : 1)) } : l))
    g.set({ loras: next })
  }
  const used = p.loras.length
  return (
    <div className="lora-slots">
      <h4 style={{ margin: '12px 0 6px', color: 'var(--fg3)', fontSize: 11 }}>LORA SLOTS</h4>
      <div className="gen-form" style={{ gridTemplateColumns: '84px 1fr' }}>
        {SLOTS.map((i) => {
          const cur = p.loras[i]
          const disabled = i > used                                              // the next free slot follows the last used one
          return (
            <div key={`slot-${i}`} style={{ display: 'contents' }}>
              <label>slot {i + 1}</label>
              <div>
                <select aria-label={`LoRA slot ${i + 1}`} value={cur?.model_id ?? ''} disabled={disabled} style={{ width: 220 }} onChange={(e) => setSlot(i, e.target.value)}
                  title={cur ? (opts.find((o) => o.id === cur.model_id)?.why ?? opts.find((o) => o.id === cur.model_id)?.label ?? cur.model_id) : 'a LoRA to load after the model (D25)'}>
                  <option value="">— none —</option>
                  {fitting.map((o) => <option key={o.id} value={o.id} title={o.why ?? ''}>{o.label}</option>)}
                  {others.length > 0 && <optgroup label="does not fit this model">{others.map((o) => <option key={o.id} value={o.id} disabled title={o.why ?? ''}>{o.label} — {o.why}</option>)}</optgroup>}
                </select>
                {cur && <> <input type="number" aria-label={`LoRA strength ${i + 1}`} step={0.05} min={0} max={2} value={cur.strength} style={{ width: 64 }} onChange={(e) => setStrength(i, Number(e.target.value))} title="strength_model of the LoraLoaderModelOnly node (0–2)" /></>}
              </div>
            </div>
          )
        })}
        <span className="hint">
          {opts.length === 0
            ? 'no LoRA on disk for this model — train one in Story · Cast (the LT wave) or put a .safetensors under the loras folder'
            : `${fitting.length} available${others.length ? `, ${others.length} for other models` : ''}; a file LoRA declares no family — the job log names keys the engine cannot load`}
        </span>
      </div>
    </div>
  )
}
