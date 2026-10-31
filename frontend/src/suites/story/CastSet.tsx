// proto01_UIcast CW6 (04 §3–6; D143): a place's set builder on its Cast page — the set picture (the empty place), the set fitted to it and
// drawn over it from the picture's camera (a wall's foot or top dragged fits it, the guessed ones dashed), its kind in one click, its sizes,
// parts and the camera's height as fields, its faces baked (with what the picture saw) and filled, each with its material named.
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { api } from '../../api/client'
import type { Profile } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { markUsed, sep } from '../../frame/commands'
import { showMenu } from '../../frame/ContextMenu'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { SET_KIND_PARTS, SET_KIND_SIZES, type PlaceSetDoc, type SetKind } from '../stage/placeSet'
import { changeKind, dragTo, handles, outlines, rescale, type Handle, type SourceCam } from '../stage/setOverlay'
import { autoBake, faceNoun, saveSet, setCamera, setPicture, setStatus, useSetBuilder, type PlaceSet } from './setBuilder'
import { onStoryItem } from './storyCommands'

type Version = Profile['versions'][number]
const KINDS: [SetKind, string][] = [['room', 'Room'], ['corridor', 'Corridor'], ['street', 'Street'], ['ground', 'Open ground']]
const SIZE_LABEL: Record<string, string> = { width: 'width', depth: 'depth', height: 'height', length: 'length', pavement: 'pavement', height_l: 'left fronts', height_r: 'right fronts',
  size: 'floor', backdrop: 'backdrop at' }
const PART_LABEL: Record<string, string> = { floor: 'floor', ceiling: 'ceiling', wall_back: 'back wall', wall_left: 'left wall', wall_right: 'right wall', wall_front: 'front wall', road: 'road',
  pavement_left: 'left pavement', pavement_right: 'right pavement', facade_left: 'left fronts', facade_right: 'right fronts', end: 'far end', backdrop: 'backdrop' }
const HANDLE_TIP: Record<string, string> = { back: 'the back wall: drag its foot along the floor', left: 'the left wall: drag its foot', right: 'the right wall: drag its foot',
  top_back: 'the height: drag the top edge', top_left: 'the height: drag the top edge', top_right: 'the height: drag the top edge' }

/** The set with its picture's camera moved (a drag, the height). */
const withCamera = (ps: PlaceSet, cam: SourceCam): PlaceSet => ({ ...ps, sources: ps.sources.map((s, i) => (i === 0 ? { ...s, camera: { ...s.camera, ...cam } } : s)) })

export function PlaceSetSection({ p, v }: { p: Profile; v: Version }) {
  const jobs = useSession((s) => s.jobs)
  const baking = useSetBuilder((s) => s.baking)
  const ps = v.place_set ?? null
  const cam = setCamera(ps)
  const pic = ps?.sources[0]?.asset_id ?? setPicture(v)
  const status = setStatus(v, jobs, p.id, baking)
  useEffect(() => { if (ps) autoBake(p.id, v.id, ps) }, [ps, p.id, v.id])
  markUsed('cast.place.fillFace')
  const edit = (next: PlaceSet) => void saveSet(next)
  const s = ps ? { ...SET_KIND_SIZES[ps.kind], ...ps.sizes } : {}
  const parts = ps ? { ...SET_KIND_PARTS[ps.kind], ...(ps.parts ?? {}) } : {}
  return (
    <section className="place-set">
      <h3>The set <Help text={"A room, a corridor, a street or open ground fitted to the set picture (the place empty, from eye level): MoGe reads the picture's depth, the set's walls and the camera come from it, scaled by the camera's height. Drag a wall's foot or its top on the picture to fit it (the dashed ones were guessed). The picture is then baked onto the faces; Fill paints what it never saw, face by face, with each face's material."} /></h3>
      <div className="place-set-row">
        {pic ? <SetOverlay key={pic} pic={pic} ps={ps} cam={cam} assumed={ps?.sources[0]?.assumed ?? []} onEdit={edit} />
          : <div className="set-view empty" onContextMenu={(e) => showMenu(e, [{ cmd: 'cast.place.picture' }])}><span className="hint">set picture: none yet</span></div>}
        <div className="place-set-side">
          <span className={`hint${status.warn ? ' warn' : ''}`} data-status>{status.text}</span>
          {ps && cam && <>
            <div className="segmented set-kind" role="group" aria-label="the set's kind">
              {KINDS.map(([k, label]) => <button key={k} type="button" className={ps.kind === k ? 'active' : ''} aria-pressed={ps.kind === k}
                onClick={() => { const r = changeKind(ps as PlaceSetDoc, cam, k); edit(withCamera(r.set as PlaceSet, r.camera)) }}>{label}</button>)}
            </div>
            <div className="kv set-sizes">
              {Object.keys(SET_KIND_SIZES[ps.kind]).map((k) => <Field key={`${k}${s[k]}`} label={SIZE_LABEL[k] ?? k} value={s[k]} min={0.5} onSet={(x) => edit({ ...ps, sizes: { ...ps.sizes, [k]: x } })} />)}
              <Field key={`cam${cam.pos[1]}`} label="camera height" value={cam.pos[1]} min={0.2} title="The picture's camera above the floor: the whole fit scales with it (eye level is 1.6 m)"
                onSet={(x) => { const r = rescale(ps as PlaceSetDoc, cam, x); edit(withCamera(r.set as PlaceSet, r.camera)) }} />
            </div>
            <div className="set-parts">
              {Object.keys(SET_KIND_PARTS[ps.kind]).map((k) => <label key={k} className="chip-toggle"><input type="checkbox" checked={parts[k] !== false}
                onChange={(e) => edit({ ...ps, parts: { ...ps.parts, [k]: e.target.checked } })} /> {PART_LABEL[k] ?? k}</label>)}
            </div>
          </>}
          <div className="verbs">
            {!ps && <CommandButton id="cast.place.picture" text />}
            <CommandButton id="cast.place.build" text />
            <CommandButton id="cast.place.bake" text />
            <CommandButton id="cast.place.fill" text />
            <CommandButton id="story.cast.bench" text />
            {ps && <CommandButton id="cast.place.clear" text />}
          </div>
        </div>
      </div>
      {ps && ps.faces.some((f) => f.baked_asset_id) && <FaceRows ps={ps} onEdit={edit} />}
    </section>
  )
}

function Field({ label, value, min, title, onSet }: { label: string; value: number; min: number; title?: string; onSet: (v: number) => void }) {
  return (
    <><span title={title}>{label}</span>
      <span><input type="number" defaultValue={+value.toFixed(2)} min={min} max={200} step={0.05} aria-label={label} title={title}
        onBlur={(e) => { const x = Number(e.target.value); if (Number.isFinite(x) && x >= min && Math.abs(x - value) > 1e-3) onSet(x) }}
        onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} /> m</span></>
  )
}

/** The picture with the set drawn over it from its camera; a handle dragged previews the set and saves it on release. */
function SetOverlay({ pic, ps, cam, assumed, onEdit }: { pic: string; ps: PlaceSet | null; cam: SourceCam | null; assumed: string[]; onEdit: (ps: PlaceSet) => void }) {
  const [size, setSize] = useState<[number, number] | null>(null)
  const [drag, setDrag] = useState<{ h: Handle; set: PlaceSetDoc; camera: SourceCam } | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const shown = drag ?? (ps && cam ? { set: ps as PlaceSetDoc, camera: cam } : null)
  const lines = size && shown ? outlines(shown.set, shown.camera, size[0], size[1]) : []
  const hs = size && ps && cam ? handles(ps as PlaceSetDoc, cam, size[0], size[1], assumed) : []
  const at = (e: ReactPointerEvent): [number, number] => { const r = svg.current!.getBoundingClientRect(); return [((e.clientX - r.left) / r.width) * size![0], ((e.clientY - r.top) / r.height) * size![1]] }
  const shownHandles = drag && size ? handles(drag.set, drag.camera, size[0], size[1], assumed) : hs
  return (
    <div className="set-view" style={size ? { aspectRatio: `${size[0]} / ${size[1]}` } : undefined} data-set={ps?.kind ?? 'none'}
      onContextMenu={(e) => showMenu(e, [{ cmd: 'cast.place.build' }, { cmd: 'cast.place.picture' }, { cmd: 'cast.place.bake' }, { cmd: 'cast.place.fill' }, sep, { cmd: 'cast.place.clear' }])}>
      <img src={api.thumbUrl(pic, 1024)} alt="the set picture" draggable={false} onLoad={(e) => setSize([e.currentTarget.naturalWidth, e.currentTarget.naturalHeight])} />
      {size && <svg ref={svg} className="set-overlay" viewBox={`0 0 ${size[0]} ${size[1]}`} preserveAspectRatio="none">
        {lines.filter((o) => o.points.length > 2).map((o) => <polygon key={o.id} className="face" data-face={o.id} points={o.points.map((q) => q.join(',')).join(' ')} />)}
        {shownHandles.map((h) => {
          const live = hs.find((x) => x.id === h.id) ?? h
          return (
            <g key={h.id} className={`handle${h.assumed ? ' assumed' : ''}${drag?.h.id === h.id ? ' on' : ''}`} data-handle={h.id}
              onPointerDown={(e) => { if (e.button !== 0 || !ps || !cam) return; e.currentTarget.setPointerCapture(e.pointerId); setDrag({ h: live, set: ps as PlaceSetDoc, camera: cam }) }}
              onPointerMove={(e) => { if (!drag || drag.h.id !== h.id || !ps || !cam) return; const r = dragTo(ps as PlaceSetDoc, cam, size[0], size[1], drag.h, at(e)); if (r) setDrag({ h: drag.h, ...r }) }}
              onPointerUp={() => { if (drag && ps) onEdit(withCamera(drag.set as PlaceSet, drag.camera)); setDrag(null) }}
              onPointerCancel={() => setDrag(null)}>
              <title>{(HANDLE_TIP[h.id] ?? h.id) + (h.assumed ? ' (guessed — the picture does not show it)' : '')}</title>
              <line className="hit" x1={h.a[0]} y1={h.a[1]} x2={h.b[0]} y2={h.b[1]} />
              <line className="edge" x1={h.a[0]} y1={h.a[1]} x2={h.b[0]} y2={h.b[1]} />
            </g>
          )
        })}
      </svg>}
    </div>
  )
}

/** The baked faces: what the picture saw of each, filled or to fill, and the material each Fill names (D143). D170: a facade is filled as a
 *  flat elevation of its material; unnamed, the place's words paint a view down the street (E46c), so it is marked until named. */
function FaceRows({ ps, onEdit }: { ps: PlaceSet; onEdit: (ps: PlaceSet) => void }) {
  const order = [...ps.faces].sort((a, b) => (a.bad ?? 0) - (b.bad ?? 0))
  return (
    <div className="set-faces" role="list" aria-label="the set's faces">
      {order.map((f) => { const facade = f.id.split('_')[0] === 'facade'; return (
        <div key={f.id} role="listitem" className={`set-face${f.filled ? ' filled' : ''}`} data-face={f.id}
          onContextMenu={(e) => showMenu(e, [{ cmd: 'cast.place.fillFace', on: onStoryItem({ face: f.id }) }, { cmd: 'cast.place.fill' }, { cmd: 'cast.place.bake' }])}>
          {f.texture_asset_id ? <img src={api.thumbUrl(f.texture_asset_id, 256)} alt="" /> : <span className="thumb" />}
          <span className="name">{PART_LABEL[f.id.replace(/_\d+$/, '')] ?? f.id}</span>
          <span className="muted">{f.fill_job_id ? 'filling…' : f.filled ? 'filled' : (f.bad ?? 0) >= 0.002 ? `${Math.round((f.bad ?? 0) * 100)} % to fill` : 'seen'}</span>
          <input type="text" defaultValue={f.material} key={`${f.id}${f.material}`} maxLength={200} aria-label={`${f.id}: its material for the Fill`}
            className={facade && !f.material.trim() ? 'want' : undefined}
            placeholder={facade ? 'what stands along it: shop fronts, doors below, windows above' : faceNoun(f.id)}
            title={facade ? "Filled as a flat elevation of what you name here, seen square on. Unnamed, the place's words paint a view down the street"
              : "The face's material, named for its Fill (pale ochre plaster, worn terracotta tiles)"}
            onBlur={(e) => { const m = e.target.value.trim(); if (m !== f.material) onEdit({ ...ps, faces: ps.faces.map((x) => (x.id === f.id ? { ...x, material: m } : x)) }) }}
            onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
        </div>
      ) })}
    </div>
  )
}
