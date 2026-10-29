// D90 (B10): what the loupe and compare show for an asset — an image with zoom / pan; a clip as a <video> with its thumbnail as the poster
// (an Animate clip also offers "Play in Animate"); a spoken line as an <audio> under its thumbnail; a 3D prop as its rendered thumbnail.
import { api } from '../../api/client'
import type { Asset } from '../../api/types'

export type LoupeMedia =
  | { kind: 'image'; src: string; zoom: true }
  | { kind: 'video'; src: string; poster: string; clipId: string | null; zoom: false }
  | { kind: 'audio'; src: string; poster: string; zoom: false }

export function loupeMedia(a: Pick<Asset, 'id' | 'kind' | 'params'>): LoupeMedia {
  if (a.kind === 'video') return { kind: 'video', src: api.assetUrl(a.id), poster: api.thumbUrl(a.id, 1024), clipId: (a.params as { clip_id?: string } | null)?.clip_id ?? null, zoom: false }
  if (a.kind === 'audio') return { kind: 'audio', src: api.assetUrl(a.id), poster: api.thumbUrl(a.id, 1024), zoom: false }
  return { kind: 'image', src: a.kind === 'mesh' ? api.thumbUrl(a.id, 1024) : api.assetUrl(a.id), zoom: true }
}
