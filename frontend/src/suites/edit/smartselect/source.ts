// D59: the image the smart-select tools look at (PhotoCraft with_doc_sampler / pixel_layer): the active pixel layer placed in the
// document, or — with "sample all layers", or when the active layer has no pixels — the visible composite. The Worker keeps it until
// the key changes (the layer's pixel version and position, or the document revision for the composite).
import { findNode, useEditor } from '../editorStore'
import { ensureImage } from './client'

export async function ensureDocImage(sampleAll: boolean): Promise<boolean> {
  const st = useEditor.getState(), doc = st.doc
  if (!doc) return false
  const n = findNode(doc, st.activeId)
  const lp = n?.kind === 'raster' ? st.pixels.get(n.id) : undefined
  if (lp && n && !sampleAll) {
    const x = n.x ?? 0, y = n.y ?? 0
    await ensureImage(`layer:${n.id}:${lp.version}:${x},${y}:${doc.w}x${doc.h}`, () => {
      const c = document.createElement('canvas'); c.width = doc.w; c.height = doc.h
      const cx = c.getContext('2d', { willReadFrequently: true })!
      cx.drawImage(lp.canvas, x, y)
      return { data: cx.getImageData(0, 0, doc.w, doc.h).data, w: doc.w, h: doc.h }
    })
    return true
  }
  const c = st.extractor?.()
  if (!c) return false
  await ensureImage(`composite:${doc.id}:${st.revision}`, () => ({ data: c.getContext('2d', { willReadFrequently: true })!.getImageData(0, 0, c.width, c.height).data, w: c.width, h: c.height }))
  return true
}
