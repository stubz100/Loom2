// D123 (SC3c-2): the things in a picture set's picture, picked by the author one at a time. The picture large; a click marks the thing
// (SAM 3's point prompt on the set's own document — the mask it finds drawn over the picture), a right-click or "Not it" marks what is
// not; "Keep as a thing" keeps the mask under a name. The things kept so far are tinted on the picture, and (D124) the shadows the clean
// will take with them tinted violet. Made into models by the set's row's "Make the things ▶" (SC3c-3).
import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { useStage } from './stageStore'
import { useThings } from './thingsStore'

const TINTS = [[79, 209, 197], [246, 173, 85], [159, 122, 234], [104, 211, 145], [99, 179, 237], [252, 129, 129]]
const NOW: [number, number, number] = [240, 166, 58]                                 // the accent: the mask the last click found
const SHADOW: [number, number, number] = [150, 110, 255]                             // D124: the shadows the clean takes with the things

/** A grey mask (w·h) as a tinted, half-clear layer at the picture's size. */
function tinted(grey: Uint8ClampedArray | Uint8Array, w: number, h: number, rgb: number[], stride: number): HTMLCanvasElement {
  const c = document.createElement('canvas'); c.width = w; c.height = h
  const g = c.getContext('2d')!
  const img = g.createImageData(w, h)
  for (let i = 0, j = 0; i < w * h; i++, j += stride) {
    const on = grey[j] > 127
    img.data[i * 4] = rgb[0]; img.data[i * 4 + 1] = rgb[1]; img.data[i * 4 + 2] = rgb[2]; img.data[i * 4 + 3] = on ? 115 : 0
  }
  g.putImageData(img, 0, 0)
  return c
}

export function ThingsSheet() {
  const setId = useThings((s) => s.setId)
  const size = useThings((s) => s.size)
  const points = useThings((s) => s.points)
  const mode = useThings((s) => s.mode)
  const job = useThings((s) => s.job)
  const mask = useThings((s) => s.mask)
  const shadows = useThings((s) => s.shadows)
  const o = useStage((s) => s.current?.objects.find((x) => x.id === setId))
  const [name, setName] = useState('')
  const [disp, setDisp] = useState<{ w: number; h: number } | null>(null)
  const [kept, setKept] = useState<Record<string, HTMLCanvasElement>>({})          // the kept things' tinted masks, by mask asset
  const canvas = useRef<HTMLCanvasElement>(null)
  const pic = useRef<HTMLImageElement>(null)
  const close = () => void useThings.getState().open(null)

  useEffect(() => {                                                                   // Escape closes (an open dialog keeps its own)
    if (!setId) return
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !useSession.getState().ask) { e.preventDefault(); e.stopImmediatePropagation(); void useThings.getState().open(null) } }
    window.addEventListener('keydown', h, { capture: true })
    return () => window.removeEventListener('keydown', h, { capture: true })
  }, [setId])
  useEffect(() => {                                                                   // the kept things' masks, loaded once each
    const things = o?.things ?? []
    for (const [k, t] of things.entries()) {
      if (kept[t.mask_asset_id]) continue
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight
        const g = c.getContext('2d')!; g.drawImage(img, 0, 0)
        const d = g.getImageData(0, 0, c.width, c.height).data
        setKept((m) => ({ ...m, [t.mask_asset_id]: tinted(d, c.width, c.height, TINTS[k % TINTS.length], 4) }))
      }
      img.src = api.assetUrl(t.mask_asset_id)
    }
  }, [o?.things, kept])
  useEffect(() => {                                                                   // the overlay: kept things, the mask found, the points
    const c = canvas.current
    if (!c || !disp || !size) return
    c.width = disp.w; c.height = disp.h
    const g = c.getContext('2d')!
    g.clearRect(0, 0, c.width, c.height)
    if (shadows && shadows.length === size.w * size.h) g.drawImage(tinted(shadows, size.w, size.h, SHADOW, 1), 0, 0, disp.w, disp.h)   // D124
    for (const t of o?.things ?? []) { const k = kept[t.mask_asset_id]; if (k) g.drawImage(k, 0, 0, disp.w, disp.h) }
    if (mask && mask.length === size.w * size.h) g.drawImage(tinted(mask, size.w, size.h, NOW, 1), 0, 0, disp.w, disp.h)
    for (const p of points) {
      const x = (p.x / size.w) * disp.w, y = (p.y / size.h) * disp.h
      g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2)
      g.fillStyle = p.label ? '#3fbf6b' : '#e05a5a'; g.fill()
      g.lineWidth = 2; g.strokeStyle = '#ffffff'; g.stroke()
      g.fillStyle = '#ffffff'; g.font = 'bold 12px sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(p.label ? '+' : '−', x, y + 0.5)
    }
  }, [mask, shadows, points, disp, size, o?.things, kept])

  if (!setId || !o?.plate_asset_id) return null
  const measure = () => { const im = pic.current; if (im) setDisp({ w: im.clientWidth, h: im.clientHeight }) }
  const mark = (e: React.MouseEvent<HTMLCanvasElement>, label: 0 | 1) => {
    if (!size || !disp) return
    const r = e.currentTarget.getBoundingClientRect()
    void useThings.getState().addPoint(((e.clientX - r.left) / disp.w) * size.w, ((e.clientY - r.top) / disp.h) * size.h, label)
  }
  const coverage = mask && size ? (mask.reduce((a, v) => a + (v > 127 ? 1 : 0), 0) / (size.w * size.h)) * 100 : 0
  const things = o.things ?? []
  const status = job ? 'finding…' : mask ? `found: ${coverage.toFixed(1)} % of the picture` : points.length ? 'mark the thing itself (+)' : 'click a thing'
  const keep = async () => { if (await useThings.getState().keep(name.trim())) setName('') }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal things-sheet" role="dialog" aria-label="Things in the picture" onClick={(e) => e.stopPropagation()}>
        <div className="head">Things in the picture · {o.name}
          <Help text="Pick each thing that stands in the place (a crate, a table, a chair): click it and SAM 3 finds it; a right-click — or Not it — marks a part that is not it. Keep it under a name. Make the things (the set's row) cleans the plate under them and under the shadows they cast (violet: found beside each thing, on the side away from the light), and makes each a 3D model standing where it stood." />
          <span className="spacer" /><button className="quiet" onClick={close} title="Close (Esc)" aria-label="Close"><X size={16} /></button></div>
        <div className="body">
          <div className="things-bar">
            <span className="segmented" role="group" aria-label="a click marks">
              <button type="button" className={mode === 1 ? 'active' : ''} aria-pressed={mode === 1} onClick={() => useThings.getState().setMode(1)} title="A click marks the thing">+ The thing</button>
              <button type="button" className={mode === 0 ? 'active' : ''} aria-pressed={mode === 0} onClick={() => useThings.getState().setMode(0)} title="A click marks what is not it (a right-click does too)">− Not it</button>
            </span>
            <button type="button" disabled={!points.length} onClick={() => useThings.getState().clear()}>Clear the points</button>
            <span className="things-status" data-state={job ? 'finding' : mask ? 'found' : 'idle'}>{status}</span>
          </div>
          <div className="things-pic">
            <img ref={pic} src={api.assetUrl(o.plate_asset_id)} alt="" draggable={false} onLoad={measure} />
            <canvas ref={canvas} aria-label="the picture: click a thing" onClick={(e) => mark(e, mode)} onContextMenu={(e) => { e.preventDefault(); mark(e, mode === 1 ? 0 : 1) }} />
          </div>
        </div>
        <div className="foot">
          <span className="things-kept" data-shadows={shadows ? 'shown' : 'none'} title={things.map((t) => t.name).join(', ')}>
            {things.length ? `${things.length} kept${shadows ? ' · their shadows violet' : ''}` : 'none kept yet'}</span>
          <span className="spacer" />
          <input type="text" aria-label="the thing's name" value={name} placeholder={`Thing ${things.length + 1}`} onChange={(e) => setName(e.target.value)} />
          <button type="button" className="primary" disabled={!mask || !!job} onClick={() => void keep()}>Keep as a thing</button>
          <button type="button" onClick={close}>Done</button>
        </div>
      </div>
    </div>
  )
}
