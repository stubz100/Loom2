// D115: the Poses section of Image's column — the coverage cells as icon tiles (the shot sizes by the angles), the expressions as chips
// that apply to the chosen tiles, the presets as quick picks; what Expand ▶ runs, one image per cell, the prompt's pose and action
// replaced by the cell's. With a Cast character linked in the prompt the images land as its candidates (D93 A1), each with its cell.
import { Fragment } from 'react'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { useStory } from '../story/storyStore'
import { expandCells, useGenerate, type PoseCell } from './generateStore'

const ANGLE_SHORT: Record<string, string> = { front: 'front', 'three-quarter left': '¾ L', 'three-quarter right': '¾ R', 'profile left': 'prof. L', 'profile right': 'prof. R', back: 'back' }
const ANGLE_X: Record<string, number | null> = { front: 0, 'three-quarter left': -0.45, 'three-quarter right': 0.45, 'profile left': -0.9, 'profile right': 0.9, back: null }

/** A framing box with the figure's head (and shoulders, torso, legs by the shot size); the nose mark says the angle, a hollow head the back. */
export function PoseGlyph({ shot, angle }: { shot: string; angle: string }) {
  const x = ANGLE_X[angle] ?? 0
  const back = ANGLE_X[angle] === null
  const head = shot === 'close-up' ? { cy: 14, r: 9 } : shot === 'portrait' ? { cy: 10, r: 5.5 } : shot === 'waist-up' ? { cy: 7.5, r: 3.6 } : { cy: 5.5, r: 2.6 }
  const bottom = head.cy + head.r
  const body = shot === 'portrait' ? `M4 26 Q14 ${bottom + 2} 24 26` : shot === 'waist-up' ? `M8 26 L9 ${bottom + 1.5} Q14 ${bottom} 19 ${bottom + 1.5} L20 26`
    : shot === 'full-body' ? `M11 26 L11.5 ${bottom + 1} Q14 ${bottom} 16.5 ${bottom + 1} L17 26 M11.5 17.5 L16.5 17.5` : ''
  return (
    <svg viewBox="0 0 28 28" width={28} height={28} aria-hidden>
      <rect x="1" y="1" width="26" height="26" rx="3" fill="none" stroke="currentColor" opacity=".3" />
      <circle cx="14" cy={head.cy} r={head.r} fill={back ? 'none' : 'currentColor'} stroke="currentColor" strokeWidth="1.2" strokeDasharray={back ? '2 1.5' : undefined} opacity=".9" />
      {!back && <circle cx={14 + x * head.r * 0.75} cy={head.cy + head.r * 0.08} r={Math.max(0.9, head.r * 0.24)} fill="var(--bg)" />}
      {body && <path d={body} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity=".8" />}
    </svg>
  )
}

const unique = <T,>(xs: T[]): T[] => Array.from(new Set(xs))

export function PosesSection() {
  const run = useGenerate((g) => g.run)
  const poses = useGenerate((g) => g.poses)
  const count = useGenerate((g) => g.panel.count)
  const linked = useGenerate((g) => (g.panel.prompt_mode === 'tree' ? (g.panel.tree.subjects ?? []).find((s) => !!s.profile_id)?.profile_id : undefined))
  const name = useStory((x) => x.profiles.find((p) => p.id === linked)?.name)
  const st = useSession((s) => s.capabilities?.story)
  const shots: string[] = st?.coverage?.shots ?? []
  const angles: string[] = st?.coverage?.angles ?? []
  const exprs: string[] = st?.coverage?.expressions ?? []
  const presets = (st?.presets ?? {}) as Record<string, { label: string; hint: string; cells: number; plan?: PoseCell[] }>
  const cells = expandCells(poses, shots, angles, exprs)
  const g = () => useGenerate.getState()
  const tileOn = (shot: string, angle: string) => poses.cells.some((c) => c.shot === shot && c.angle === angle)
  const tileExprs = (shot: string, angle: string) => unique(poses.cells.filter((c) => c.shot === shot && c.angle === angle).map((c) => c.expression))
  return (
    <section id="gen-sec-poses" className="gen-sec poses-sec" data-run={run}>
      <h4 className="gen-sec-head"><span>Poses{run === 'expand' ? ` · ${cells.length} cell${cells.length === 1 ? '' : 's'}` : ''}</span><span className="spacer" />
        {run === 'expand' && <button type="button" className="quiet" disabled={!poses.cells.length} title="No poses" onClick={() => g().setPoses({ ...poses, cells: [] })}>clear</button>}</h4>
      {run !== 'expand' ? <span className="hint">Expand is off. <Help text={"Expand (the switch under the prompt) runs one image per pose chosen here, with the prompt's pose and action replaced by the pose's."} /></span> : <>
        <div className="pose-presets" aria-label="coverage presets">
          {Object.entries(presets).map(([k, v]) => <button key={k} type="button" className="quiet" data-preset={k} title={`${v.hint} — ${v.cells} cells`}
            onClick={() => g().setPoses({ cells: (v.plan ?? []).map((c) => ({ shot: c.shot, angle: c.angle, expression: c.expression })), expressions: unique((v.plan ?? []).map((c) => c.expression)) })}>{v.label}</button>)}
        </div>
        <div className="pose-grid" role="group" aria-label="poses" style={{ gridTemplateColumns: `auto repeat(${Math.max(1, angles.length)}, 1fr)` }}>
          <span />{angles.map((a) => <span key={a} className="pose-col">{ANGLE_SHORT[a] ?? a}</span>)}
          {shots.map((s) => <Fragment key={s}>
            <span className="pose-row">{s}</span>
            {angles.map((a) => {
              const on = tileOn(s, a)
              const ex = tileExprs(s, a)
              return <button key={a} type="button" className={`pose-tile${on ? ' on' : ''}`} aria-pressed={on} data-shot={s} data-angle={a}
                title={`${s} · ${a}${on ? ` · ${ex.join(', ')}` : ''}`} onClick={() => g().toggleTile(s, a)}>
                <PoseGlyph shot={s} angle={a} />{ex.length > 1 && <span className="badge">{ex.length}</span>}
              </button>
            })}
          </Fragment>)}
        </div>
        <div className="pose-chips" role="group" aria-label="expressions">
          {exprs.map((x) => { const on = poses.expressions.includes(x); return <button key={x} type="button" className={`chip${on ? ' on' : ''}`} aria-pressed={on} data-expression={x}
            title={on ? `Drop ${x} from the chosen poses` : `Add ${x} to the chosen poses`} onClick={() => g().toggleExpression(x)}>{x}</button> })}
        </div>
        <span className="hint" data-lands>{!cells.length ? 'No pose picked.'
          : name ? `${cells.length * count} image${cells.length * count === 1 ? '' : 's'} land as ${name}'s candidates in Cast, each with its pose recorded.`
            : 'No Cast character is linked in the prompt: the images land in the Bin as a batch (link one in the Prompt section to grow its reference set).'}</span>{!cells.length && <Help text={"A tile is a shot size and an angle; the chips add expressions to the chosen tiles."} />}
      </>}
    </section>
  )
}
