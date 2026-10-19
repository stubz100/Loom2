// CA0 (D94, proto01_animate 01 §9): the body on a Cast character's sheet — height, build, proportions and rigid attachments. It shapes
// the Stage dummy of every figure bound to this version (stageStore.syncBodies copies it), so the clay, depth and pose passes have the
// character's build. None = the default 1.75 m adult. The silhouette is drawn from the numbers the dummy is built with (stage/body.ts),
// the default adult behind it for scale. Saved like the rest of the sheet (setSheet); read-only on a final version.
import { Plus, X } from 'lucide-react'
import type { Profile, ProfileVersion } from '../../api/types'
import { BUILD_WIDTH, DEFAULT_BODY, bodyDims, type Body } from '../stage/body'
import { CommandButton } from '../../frame/CommandButton'
import { useStory } from './storyStore'

const PROPORTIONS: [keyof Pick<Body, 'head' | 'neck' | 'torso' | 'shoulders' | 'arms' | 'legs' | 'hands' | 'feet'>, string, number, number][] = [
  ['head', 'head size', 0.5, 2.5], ['neck', 'neck length', 0.5, 3.0], ['torso', 'torso length', 0.6, 1.6], ['shoulders', 'shoulder width', 0.6, 1.8],
  ['arms', 'arm length', 0.6, 1.6], ['legs', 'leg length', 0.5, 1.6], ['hands', 'hand size', 0.5, 1.6], ['feet', 'foot size', 0.5, 1.6]]
const BUILDS: Body['build'][] = ['slim', 'average', 'broad', 'heavy']
const KINDS: Body['attachments'][number]['kind'][] = ['tail', 'horns', 'ears', 'wings', 'antennae', 'hat', 'backpack', 'other']
const JOINT_LABEL: Record<string, string> = { head: 'head', spine: 'back', root: 'hips', r_shoulder: 'right shoulder', l_shoulder: 'left shoulder', r_elbow: 'right forearm', l_elbow: 'left forearm' }
const MAX_ATTACHMENTS = 6

export function CastBody({ p, v }: { p: Profile; v: ProfileVersion }) {
  const setSheet = useStory((s) => s.setSheet)
  if (p.cls !== 'character') return null
  const open = v.state === 'open'
  const b = (v.body ?? null) as Body | null
  const set = (patch: Partial<Body>) => b && setSheet({ body: { ...b, ...patch } as never })
  if (!b) return (
    <>
      <label>body</label>
      <div className="cast-body empty">
        <span className="hint">The default dummy (a 1.75 m adult). A body shapes {p.name}'s figure on the stage — height, build, proportions, a tail or horns.</span>
        {open && <button type="button" className="quiet" onClick={() => setSheet({ body: DEFAULT_BODY as never })} title="Give this version a body of its own (starts as the default adult)"><Plus size={12} /> body</button>}
        {open && v.anim_ref_asset_id && <CommandButton id="story.cast.fitBody" text size={12} />}
      </div>
    </>
  )
  const atts = b.attachments
  const setAtt = (k: number, patch: Partial<Body['attachments'][number]>) => set({ attachments: atts.map((a, j) => (j === k ? { ...a, ...patch } : a)) })
  return (
    <>
      <label>body</label>
      <div className="cast-body" role="group" aria-label={`${p.name}'s body`}>
        <div className="body-fields">
          <div className="body-row">
            <span>height</span>
            <input type="number" aria-label="height in metres" min={0.3} max={4} step={0.01} value={b.height_m} disabled={!open}
              onChange={(e) => { const x = Number(e.target.value); if (x >= 0.3 && x <= 4) set({ height_m: x }) }} /> m
          </div>
          <div className="body-row">
            <span>build</span>
            <span className="segmented" role="group" aria-label="build">
              {BUILDS.map((k) => <button key={k} type="button" disabled={!open} className={b.build === k ? 'active' : ''} aria-pressed={b.build === k} onClick={() => set({ build: k })}>{k}</button>)}
            </span>
          </div>
          {PROPORTIONS.map(([k, label, lo, hi]) => (
            <div key={k} className="body-row">
              <span>{label}</span>
              <input type="range" aria-label={label} min={lo} max={hi} step={0.05} value={b[k]} disabled={!open} onChange={(e) => set({ [k]: Number(e.target.value) } as Partial<Body>)} />
              <span className="mono">×{b[k].toFixed(2)}</span>
            </div>
          ))}
          <div className="body-row attachments">
            <span>attachments</span>
            <div>
              {atts.map((a, k) => (
                <div key={k} className="body-att">
                  <select aria-label={`attachment ${k + 1}`} value={a.kind} disabled={!open} onChange={(e) => setAtt(k, { kind: e.target.value as typeof a.kind })}>{KINDS.map((x) => <option key={x} value={x}>{x}</option>)}</select>
                  <select aria-label={`attachment ${k + 1}: where`} value={a.joint ?? ''} disabled={!open} onChange={(e) => setAtt(k, { joint: e.target.value || null })}>
                    <option value="">its place</option>{Object.entries(JOINT_LABEL).map(([j, l]) => <option key={j} value={j}>{l}</option>)}
                  </select>
                  <input type="range" aria-label={`attachment ${k + 1}: size`} min={0.2} max={3} step={0.1} value={a.size} disabled={!open} onChange={(e) => setAtt(k, { size: Number(e.target.value) })} title={`size ×${a.size.toFixed(1)}`} />
                  <input type="text" aria-label={`attachment ${k + 1}: note`} maxLength={80} value={a.note} readOnly={!open} placeholder="a note" onChange={(e) => setAtt(k, { note: e.target.value })} />
                  {open && <button type="button" className="quiet x" aria-label={`remove attachment ${k + 1}`} title="Remove this attachment" onClick={() => set({ attachments: atts.filter((_, j) => j !== k) })}><X size={11} /></button>}
                </div>
              ))}
              {open && atts.length < MAX_ATTACHMENTS && <button type="button" className="quiet" title="A rigid part that follows the figure — on the stage dummy and in its clay and depth passes, not in the pose pass"
                onClick={() => set({ attachments: [...atts, { kind: 'tail', joint: null, size: 1, note: '' }] })}><Plus size={12} /> attachment</button>}
            </div>
          </div>
          {v.body_fit_from && <div className="body-row"><span /><span className="hint">{v.body_fit_from === v.anim_ref_asset_id ? 'Proportions fitted to the animation reference' : 'Proportions fitted to an earlier animation reference'}</span></div>}
          {open && <div className="body-row">
            <span />
            <span>
              {v.anim_ref_asset_id && <CommandButton id="story.cast.fitBody" text size={12} />}
              <button type="button" className="quiet" title="Proportions and build back to the default adult (the height and attachments stay)" onClick={() => set({ build: 'average', head: 1, neck: 1, torso: 1, shoulders: 1, arms: 1, legs: 1, hands: 1, feet: 1 })}>Reset proportions</button>
              <button type="button" className="quiet" title="No body of its own: the default 1.75 m dummy" onClick={() => setSheet({ body: null as never })}>Remove the body</button>
            </span>
          </div>}
        </div>
        <Silhouette b={b} />
      </div>
    </>
  )
}

/** A front view drawn from the dummy's own dimensions (body.ts), the default adult as a ghost behind it, a line per metre. */
function Silhouette({ b }: { b: Body }) {
  const H = 2.2, px = 70                                                    // metres shown, pixels per metre
  const fig = (body: Body | null) => {
    const x = body ?? DEFAULT_BODY
    const d = bodyDims(body ?? DEFAULT_BODY)
    const s = (body ?? DEFAULT_BODY).height_m / d.top
    const w = BUILD_WIDTH[x.build] ?? 1
    const y = (m: number) => (H - m * s) * px                               // metres in dummy units → svg y
    const cx = 60, hw = (m: number) => m * s * px
    const neck = d.hip + 0.06 + 0.44 * x.torso, shoulderY = d.hip + 0.06 + 0.4 * x.torso
    const sx = 0.21 * x.shoulders * (body ? 0.5 + 0.5 * w : 1)
    const armLen = d.limbs.upper_arm + d.limbs.forearm, legLen = d.limbs.thigh + d.limbs.shin
    return (
      <>
        <circle cx={cx} cy={y(neck + 0.06 * (x.neck ?? 1) + 0.1 * x.head)} r={hw(0.11 * x.head)} />
        <rect x={cx - hw(0.19 * w * x.shoulders)} y={y(neck)} width={hw(0.38 * w * x.shoulders)} height={hw(0.42 * x.torso + 0.06)} rx={2} />
        {[-1, 1].map((side) => <line key={`a${side}`} x1={cx + side * hw(sx)} y1={y(shoulderY)} x2={cx + side * hw(sx + 0.05)} y2={y(shoulderY - armLen)} strokeWidth={hw(0.1 * w)} />)}
        {[-1, 1].map((side) => <line key={`l${side}`} x1={cx + side * hw(0.1 * w)} y1={y(d.hip - 0.04)} x2={cx + side * hw(0.11 * w)} y2={y(d.hip - 0.04 - legLen)} strokeWidth={hw(0.13 * w)} />)}
      </>
    )
  }
  return (
    <svg className="body-silhouette" viewBox={`0 0 120 ${H * px}`} width={120} height={H * px} aria-label={`silhouette, ${b.height_m.toFixed(2)} m`}>
      {[1, 2].map((m) => <g key={m}><line x1={0} x2={120} y1={(H - m) * px} y2={(H - m) * px} className="metre" /><text x={2} y={(H - m) * px - 2}>{m} m</text></g>)}
      <g className="ghost">{fig(null)}</g>
      <g className="figure">{fig(b)}</g>
      <text x={60} y={H * px - 2} textAnchor="middle">{b.height_m.toFixed(2)} m · {b.build}{b.attachments.length ? ` · ${b.attachments.map((a) => a.kind).join(', ')}` : ''}</text>
    </svg>
  )
}
