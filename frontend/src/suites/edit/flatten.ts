// D90 (UI6, owed until 2026-10-17): Edit › Flatten image, as Photoshop's — every layer of the document (groups, masks, blend modes,
// clipping, adjustment and filter layers; hidden layers are discarded) becomes one raster layer whose pixels are the server's exact
// flatten (`POST /documents/{id}/export` format "raw", the same `OpenDocument.flatten` Save to Catalogue and the PNG export write).
// Pure parts here (tested); the store's `flattenImage` fetches the pixels and records one undo step.
import type { DocumentStack, Node } from './editorStore'

/** Why Flatten would do nothing (null: it can run) — one plain full-canvas layer is already flat. */
export function flattenBlocker(doc: Pick<DocumentStack, 'w' | 'h' | 'layers'> | null): string | null {
  if (!doc) return 'no document'
  if (!doc.layers.length) return 'no layers'
  if (doc.layers.length > 1) return null
  const n = doc.layers[0]
  const plain = n.kind === 'raster' && n.visible && n.opacity === 1 && (n.fill ?? 1) === 1 && n.blend === 'normal' && !n.mask && !n.clip
    && (n.x ?? 0) === 0 && (n.y ?? 0) === 0 && n.w === doc.w && n.h === doc.h
  return plain ? 'the document is one layer already' : null
}

/** The flattened layer's name: the bottom layer's when it is a pixel layer (Photoshop says "Background"; a storyboard frame keeps the
 * name its source gave it), else "Background". */
export function flattenedName(doc: Pick<DocumentStack, 'layers'>): string {
  const bottom = doc.layers[doc.layers.length - 1]
  return bottom?.kind === 'raster' && bottom.name.trim() ? bottom.name : 'Background'
}

/** The stack after Flatten: the document as it was (name, size, background, revision, meta) with one full-canvas raster layer. The
 * bottom layer's lineage carries over (the frame the document was opened from). */
export function flattenedStack(doc: DocumentStack, id: string): DocumentStack {
  const bottom = doc.layers[doc.layers.length - 1]
  const node: Node = { kind: 'raster', id, name: flattenedName(doc), opacity: 1, fill: 1, blend: 'normal', visible: true, locked: false, clip: false, mask: null,
    x: 0, y: 0, w: doc.w, h: doc.h, lineage_asset_id: bottom?.kind === 'raster' ? bottom.lineage_asset_id ?? null : null }
  return { ...JSON.parse(JSON.stringify(doc)) as DocumentStack, layers: [node] }
}

/** How many layers a flatten folds in (every node, groups included) and how many hidden ones it discards — the toast says both. */
export function flattenCounts(doc: Pick<DocumentStack, 'layers'>): { layers: number; hidden: number } {
  let layers = 0, hidden = 0
  const rec = (ns: Node[], shown: boolean) => { for (const n of ns) { layers++; if (shown && !n.visible) hidden++; if (n.children) rec(n.children, shown && n.visible) } }
  rec(doc.layers, true)
  return { layers, hidden }
}
