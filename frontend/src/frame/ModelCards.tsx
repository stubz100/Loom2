// D186: the one model card — the Make column's cards (the label, the health dot, the hint · licence · health · time in the tooltip),
// wherever a picture is generated: World's Make, Clay's Still and its plate, Edit's AI tab, the Library's set, the Angle sheet, Settings.
// The candidates come from /capabilities (D65: no model id in code; modelCardItems.ts builds them); the surface lists the models that run
// its job, the measured default first, and keeps the pick as its own state. T8: what the card says is what the job runs.
import type { ModelCardItem } from './modelCardItems'
import './modelCards.css'

export function ModelCards({ items, value, onPick, label = 'model', testId, time }: { items: ModelCardItem[]; value: string | null | undefined; onPick: (id: string) => void; label?: string; testId?: string; time?: boolean }) {
  if (!items.length) return <span className="hint">No model for this in this build.</span>
  return (
    <div className="model-grid compact" role="group" aria-label={label} data-testid={testId}>
      {items.map((m) => {
        const active = m.id === value
        const secs = m.seconds != null ? `≈ ${Math.round(m.seconds)} s${m.measured === false ? ' (unmeasured)' : ''}` : ''
        return (
          <button key={m.id} type="button" className={`model-card${active ? ' active' : ''}${m.off ? ' off' : ''}`} disabled={!!m.off} aria-pressed={active} data-model={m.id}
            onClick={() => !m.off && onPick(m.id)}
            title={[m.hint, m.license, m.health, secs, m.distilled ? 'distilled' : '', m.off ? m.offWhy ?? 'not available in this build' : ''].filter(Boolean).join(' · ')}>
            <span>{m.label}</span><i className={`dot ${m.health === 'missing' ? 'warn' : 'ok'}`} />
            {time && secs ? <small className="secs">{secs}</small> : null}
          </button>
        )
      })}
    </div>
  )
}
