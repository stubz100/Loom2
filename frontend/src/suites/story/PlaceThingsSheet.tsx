// D180 (W60): the parts of a built set that move, picked on the place's set picture (as SC3's ThingsSheet picks a picture set's things):
// a click marks the thing (SAM 3 finds it — the mask drawn over the picture), a right-click or "Not it" marks what is not; "Keep as a thing"
// keeps it under a name, cut out and standing where the picture shows it. The things kept so far are tinted on the picture. Below the
// set, each thing's row makes its 3D model (ThingRows); Clay places the card or the model as an object of its own.
import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import type { PlaceSet } from './setBuilder'
import { containedRect, pointIn, setPicture, usePlaceThings } from './placeThingsStore'
import { useStory } from './storyStore'
import '../stage/stage.css'                                                // RS1: the sheet's own styles — it opens in World's Clay before any bench has loaded the stage's

const TINTS = [[79, 209, 197], [246, 173, 85], [159, 122, 234], [104, 211, 145], [99, 179, 237], [252, 129, 129]]
const NOW: [number, number, number] = [240, 166, 58]                                 // the accent: the mask the last click found
const NO_THINGS: PlaceSet['things'] = []                                              // one empty list, so the effects do not run on every render

/** A grey mask (w·h) as a tinted, half-clear layer at the picture's size. */
function tinted(grey: Uint8ClampedArray | Uint8Array, w: number, h: number, rgb: number[], stride: number): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = w; c.height = h
  const g = c.getContext('2d')!
  const img = g.createImageData(w, h)
  for (let i = 0, j = 0; i < w * h; i++, j += stride) {
    img.data[i * 4] = rgb[0]; img.data[i * 4 + 1] = rgb[1]; img.data[i * 4 + 2] = rgb[2]; img.data[i * 4 + 3] = grey[j] > 127 ? 115 : 0
  }
  g.putImageData(img, 0, 0)
  return c
}

export function PlaceThingsSheet() {
  const target = usePlaceThings((s) => s.target)
  const size = usePlaceThings((s) => s.size)
  const points = usePlaceThings((s) => s.points)
  const mode = usePlaceThings((s) => s.mode)
  const job = usePlaceThings((s) => s.job)
  const mask = usePlaceThings((s) => s.mask)
  const things = useStory((s) => (target ? s.profiles.find((p) => p.id === target.pid)?.versions.find((v) => v.id === target.vid)?.place_set?.things : undefined)) ?? NO_THINGS
  const pic = target ? setPicture(target.pid, target.vid) : null
  const [name, setName] = useState('')
  const [disp, setDisp] = useState<{ x: number; y: number; w: number; h: number } | null>(null)   // K82: the drawn picture inside the img box
  const [kept, setKept] = useState<Record<string, HTMLCanvasElement>>({})
  const asked = useRef(new Set<string>())                                               // K96: each kept mask asked for once (not once per mask landing)
  const canvas = useRef<HTMLCanvasElement>(null)
  const img = useRef<HTMLImageElement>(null)
  const close = () => void usePlaceThings.getState().open(null)

  useEffect(() => {                                                                   // Escape closes (an open dialog keeps its own)
    if (!target) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !useSession.getState().ask) { e.preventDefault(); e.stopImmediatePropagation(); void usePlaceThings.getState().open(null) } }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [target])
  useEffect(() => {                                                                   // the kept things' masks, loaded once each
    for (const [k, t] of things.entries()) {
      if (asked.current.has(t.mask_asset_id)) continue
      asked.current.add(t.mask_asset_id)
      const im = new Image()
      im.crossOrigin = 'anonymous'
      im.onload = () => {
        const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight
        const g = c.getContext('2d')!; g.drawImage(im, 0, 0)
        setKept((m) => ({ ...m, [t.mask_asset_id]: tinted(g.getImageData(0, 0, c.width, c.height).data, c.width, c.height, TINTS[k % TINTS.length], 4) }))
      }
      im.src = api.assetUrl(t.mask_asset_id)
    }
  }, [things])
  useEffect(() => {                                                                   // K82: the window resized — the picture is drawn elsewhere
    const im = img.current
    if (!target || !im || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => setDisp(im.naturalWidth ? containedRect(im.clientWidth, im.clientHeight, im.naturalWidth, im.naturalHeight) : null))
    ro.observe(im)
    return () => ro.disconnect()
  }, [target])
  useEffect(() => {                                                                   // the overlay: kept things, the mask found, the points
    const c = canvas.current
    if (!c || !disp || !size) return
    c.width = Math.round(disp.w); c.height = Math.round(disp.h)
    const g = c.getContext('2d')!
    g.clearRect(0, 0, c.width, c.height)
    for (const t of things) { const k = kept[t.mask_asset_id]; if (k) g.drawImage(k, 0, 0, disp.w, disp.h) }
    if (mask && mask.length === size.w * size.h) g.drawImage(tinted(mask, size.w, size.h, NOW, 1), 0, 0, disp.w, disp.h)
    for (const p of points) {
      const x = (p.x / size.w) * disp.w, y = (p.y / size.h) * disp.h
      g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2)
      g.fillStyle = p.label ? '#3fbf6b' : '#e05a5a'; g.fill()
      g.lineWidth = 2; g.strokeStyle = '#ffffff'; g.stroke()
    }
  }, [mask, points, disp, size, things, kept])

  if (!target || !pic) return null
  const measure = () => { const im = img.current; if (im) setDisp(containedRect(im.clientWidth, im.clientHeight, im.naturalWidth, im.naturalHeight)) }
  const mark = (e: React.MouseEvent<HTMLCanvasElement>, label: 0 | 1) => {
    if (!size || !disp) return
    const p = pointIn(e.clientX, e.clientY, e.currentTarget.getBoundingClientRect(), size)    // K82: the overlay lies over the drawn picture only
    void usePlaceThings.getState().addPoint(p.x, p.y, label)
  }
  const status = job ? 'finding…' : mask ? 'found — keep it under a name' : points.length ? 'mark the thing itself (+)' : 'click a thing that moves'
  const keep = async () => { if (await usePlaceThings.getState().keep(name.trim())) setName('') }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal things-sheet" role="dialog" aria-label="Things that move" onClick={(e) => e.stopPropagation()}>
        <div className="head">Things that move
          <Help text="A part of the set that should move — the ferry, a cart, a door: click it and SAM 3 finds it; a right-click — or Not it — marks a part that is not it. Kept, it is cut out and stands where the picture shows it; its row below the set makes its 3D model, and Clay places the card or the model as an object you can key." />
          <span className="spacer" /><button className="quiet" onClick={close} title="Close (Esc)" aria-label="Close"><X size={16} /></button></div>
        <div className="body">
          <div className="things-bar">
            <span className="segmented" role="group" aria-label="a click marks">
              <button type="button" className={mode === 1 ? 'active' : ''} aria-pressed={mode === 1} onClick={() => usePlaceThings.getState().setMode(1)} title="A click marks the thing">+ The thing</button>
              <button type="button" className={mode === 0 ? 'active' : ''} aria-pressed={mode === 0} onClick={() => usePlaceThings.getState().setMode(0)} title="A click marks what is not it (a right-click does too)">− Not it</button>
            </span>
            <button type="button" disabled={!points.length} onClick={() => usePlaceThings.getState().clear()}>Clear the points</button>
            <span className="things-status" data-state={job ? 'finding' : mask ? 'found' : 'idle'}>{status}</span>
          </div>
          <div className="things-pic">
            <img ref={img} src={api.assetUrl(pic)} alt="" draggable={false} onLoad={measure} />
            <canvas ref={canvas} aria-label="the set picture: click a thing" style={disp ? { left: disp.x, top: disp.y, width: disp.w, height: disp.h } : undefined} onClick={(e) => mark(e, mode)} onContextMenu={(e) => { e.preventDefault(); mark(e, mode === 1 ? 0 : 1) }} />
          </div>
        </div>
        <div className="foot">
          <span className="things-kept" title={things.map((t) => t.name).join(', ')}>{things.length ? `${things.length} kept` : 'none kept yet'}</span>
          <span className="spacer" />
          <input type="text" aria-label="the thing's name" value={name} placeholder={`Thing ${things.length + 1}`} onChange={(e) => setName(e.target.value)} />
          <button type="button" className="primary" disabled={!mask || !!job} onClick={() => void keep()}>Keep as a thing</button>
          <button type="button" onClick={close}>Done</button>
        </div>
      </div>
    </div>
  )
}

/** D180: the set's things below it — each its card, its size where it stands, its 3D model (made, being made, or Make ▶), ✕. */
export function ThingRows({ pid, vid, ps }: { pid: string; vid: string; ps: PlaceSet }) {
  const jobs = useSession((s) => s.jobs)
  const mesh = useSession((s) => s.capabilities?.mesh)
  return (
    <div className="place-things" data-testid="place-things">
      <h4>Things that move <Help text="Parts of the set picked to move on their own (the ferry, a cart). Clay places each as an object you can key: its 3D model when it has one, else its card (the cut-out, facing the picture's camera)." /></h4>
      {ps.things.map((t) => {
        const making = !!t.mesh_job_id && ['queued', 'running'].includes(jobs[t.mesh_job_id]?.status ?? 'queued')
        return (
          <div key={t.id} className="place-thing" data-thing={t.id}>
            <img src={api.thumbUrl(t.card_asset_id, 256)} alt="" />
            <span className="name">{t.name}<small> · {t.width_m.toFixed(1)} × {t.height_m.toFixed(1)} m{t.cleaned ? ' · gone from the picture' : ''}</small></span>
            {t.mesh_asset_id ? <span className="hint">3D model ✓</span>
              : making ? <span className="hint">3D model: making…</span>
                : mesh?.model_id ? <button type="button" className="quiet" title={`Its cut-out made a 3D model (${mesh.label ?? mesh.model_id}, about ${Math.round((mesh.seconds ?? 300) / 60)} min) — else Clay places its card`}
                  onClick={() => void usePlaceThings.getState().model(pid, vid, t.id)}>Make a 3D model ▶</button> : null}
            <button type="button" className="quiet" aria-label={`remove ${t.name}`} title="Remove it from the set's things (what was made of it stays in the Bin)" onClick={() => void usePlaceThings.getState().remove(pid, vid, t.id)}>✕</button>
          </div>
        )
      })}
      <div className="verbs"><CommandButton id="cast.place.things" text />{ps.things.some((t) => !t.cleaned) ? <CommandButton id="cast.place.things.clean" text /> : ps.things.length > 0 && <CommandButton id="cast.place.things.cleanAgain" text />}</div>
    </div>
  )
}
