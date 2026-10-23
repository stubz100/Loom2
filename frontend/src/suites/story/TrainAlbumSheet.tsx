// D122: a LoRA trained on an album — the sheet "Train a LoRA on this album…" opens (an album page's right-click, a group card's). The
// album's images that are not in the Trash are the set; on a Cast version's reference album the adapter goes to that version, on any
// other it is the album's own (the registry, Generate's LoRA slots). The options are the Cast block's (TrainOptions, the last choice).
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import { Help } from '../../frame/Help'
import { useSession } from '../../store/session'
import { sy } from './storyStore'
import { useTrainAlbum } from './trainAlbum'
import { TrainOptions } from './TrainingBlock'

export function TrainAlbumSheet() {
  const album = useTrainAlbum((s) => s.album)
  const close = useTrainAlbum((s) => s.close)
  const caps = useSession((s) => s.capabilities?.train)
  const [counted, setCounted] = useState<{ id: string; n: number } | null>(null)   // the count of the album it was read for
  const [busy, setBusy] = useState(false)
  const count = album && counted?.id === album.id ? counted.n : null
  useEffect(() => {
    if (!album) return
    let live = true
    unwrap(http.GET('/groups/{gid}', { params: { path: { gid: album.id } } }))
      .then((pg) => { if (live) setCounted({ id: album.id, n: Object.values(pg.assets).filter((a) => a.kind === 'image' && !a.trashed_at).length }) })
      .catch(() => { if (live) setCounted({ id: album.id, n: 0 }) })
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape' && !useSession.getState().ask) { e.preventDefault(); e.stopImmediatePropagation(); close() } }
    window.addEventListener('keydown', h, { capture: true })
    return () => { live = false; window.removeEventListener('keydown', h, { capture: true }) }
  }, [album, close])
  if (!album) return null
  const min = caps?.min_refs ?? 4
  const run = async () => {
    setBusy(true)
    const r = await sy().trainAlbum(album.id, album.name)
    setBusy(false)
    if (r) close()
  }
  return (
    <div className="modal-backdrop" onClick={close}>
      <div className="modal train-album" role="dialog" aria-label="Train a LoRA on this album" onClick={(e) => e.stopPropagation()}>
        <div className="head">Train a LoRA on {album.name}
          <Help text="Every image on this album that is not in the Trash is the training set. On a Cast version's reference album the LoRA goes to that version (its trigger, the mention's slot); on any other it is the album's own, offered in Generate's LoRA slots." />
          <span className="spacer" /><button className="quiet" onClick={close} title="Close (Esc)" aria-label="Close"><X size={16} /></button></div>
        <div className="body"><TrainOptions count={count ?? 0} noun="images" namePlaceholder={album.name} /></div>
        <div className="foot">
          <span className="estimate">{count === null ? '…' : `${count} image${count === 1 ? '' : 's'} on the album`}</span>
          <span className="spacer" />
          <button className="primary" disabled={busy || !caps?.available || count === null || count < min} onClick={() => void run()}>Train ▶</button>
        </div>
      </div>
    </div>
  )
}
