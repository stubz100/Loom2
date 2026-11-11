// RS2 (D197 G2, proto02 01 §9.1; Q13): the run form — what every ▶ that queues a job shows above it, inline: the model tiles (one tile
// when one model can do it, so the model is still named), every parameter the recipe takes with the default the worker runs (T8) and its
// measured reason behind the ? (rule 11), and the cost. The surface owns the values (kept on the thing the job makes, Q16) and the
// command that runs; this part only shows and edits them.
import { useState, type ReactNode } from 'react'
import { Help } from './Help'
import { ModelCards } from './ModelCards'
import type { ModelCardItem } from './modelCardItems'
import './runForm.css'

export interface RunChoice { value: number | string; label: string; hint?: string }
export interface RunField {
  key: string; label: string; help?: string
  kind: 'choice' | 'number'
  options?: RunChoice[]                                                    // a choice's values
  min?: number; max?: number; step?: number                                // a number's range
  fixed?: string                                                           // shown, not editable — with why (a model that takes no other value)
}

/** A number committed on Enter or blur, clamped to its range; what is typed stays until then (keyed by its value: a new value starts clean). */
function Num({ f, value, onCommit }: { f: RunField; value: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState<string | null>(null)
  const commit = () => {
    if (text === null) return
    const n = Number(text)
    setText(null)
    if (!text.trim() || !Number.isFinite(n)) return
    const c = Math.min(f.max ?? Infinity, Math.max(f.min ?? -Infinity, f.step && Number.isInteger(f.step) ? Math.round(n) : n))
    if (c !== value) onCommit(c)
  }
  return <input type="number" aria-label={f.label} value={text ?? String(value)} min={f.min} max={f.max} step={f.step} disabled={!!f.fixed}
    onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
}

export function RunForm({ testId, models, model, onModel, fields, values, onChange, cost, children }: {
  testId?: string
  models: ModelCardItem[]; model: string | null; onModel: (id: string) => void
  fields: RunField[]; values: Record<string, number | string>; onChange: (key: string, value: number | string) => void
  cost?: string                                                            // "≈ 4 min · 14 GB", said before the click
  children?: ReactNode                                                     // the run's own verbs (the command buttons)
}) {
  return (
    <div className="run-form" data-testid={testId}>
      <div className="run-row"><span>model</span><ModelCards items={models} value={model} onPick={onModel} label="the model that runs" time /></div>
      {fields.map((f) => (
        <div className="run-row" key={f.key} data-field={f.key}>
          <span>{f.label}{f.help ? <> <Help text={f.help} /></> : null}</span>
          {f.kind === 'choice'
            ? <span className="segmented" role="group" aria-label={f.label}>{(f.options ?? []).map((o) => (
              <button key={String(o.value)} type="button" className={values[f.key] === o.value ? 'active' : ''} aria-pressed={values[f.key] === o.value} disabled={!!f.fixed} title={o.hint}
                onClick={() => onChange(f.key, o.value)}>{o.label}</button>))}</span>
            : <Num key={String(values[f.key])} f={f} value={Number(values[f.key])} onCommit={(v) => onChange(f.key, v)} />}
          {f.fixed ? <small className="run-fixed">{f.fixed}</small> : null}
        </div>
      ))}
      <div className="run-foot">{children}{cost ? <span className="run-cost">{cost}</span> : null}</div>
    </div>
  )
}
