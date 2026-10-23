// D123 (SC3c-1): the lens a set from an image is made with — asked before the job. What the author types (degrees, or a focal length in
// mm on a 36 mm sensor) and what the picture already knows: a Stage still's camera, or the prompt's camera lens ("35mm", "a 50 mm portrait").
import { http, unwrap } from '../../api/client'
import type { Asset } from '../../api/types'

export const SENSOR_MM = 36
export const LENS_MIN = 20, LENS_MAX = 150

/** The horizontal field of view of a focal length on the 36 mm sensor, in degrees (one decimal). */
export function hfovOfMm(mm: number): number { return Math.round((2 * Math.atan(SENSOR_MM / 2 / mm) * 180) / Math.PI * 10) / 10 }

/** What the author typed: empty → null (MoGe reads the lens); "35 mm" / "35mm" → the focal's field of view; "70", "70°", "70 deg" →
 *  degrees. 'invalid' for anything else, or a lens outside 20–150°. */
export function parseLens(text: string): number | null | 'invalid' {
  const t = text.trim().toLowerCase()
  if (!t) return null
  const mm = /^(\d+(?:[.,]\d+)?)\s*mm$/.exec(t)
  const deg = /^(\d+(?:[.,]\d+)?)\s*(?:°|deg|degrees?)?$/.exec(t)
  const v = mm ? hfovOfMm(Number(mm[1].replace(',', '.'))) : deg ? Number(deg[1].replace(',', '.')) : NaN
  return Number.isFinite(v) && v >= LENS_MIN && v <= LENS_MAX ? Math.round(v * 10) / 10 : 'invalid'
}

/** A focal length named in a prompt's camera lens ("35mm", "a 50 mm portrait lens") — the first number before "mm". */
export function mmInText(text: string | null | undefined): number | null {
  const m = /(\d{2,3}(?:[.,]\d+)?)\s*mm\b/i.exec(text ?? '')
  return m ? Number(m[1].replace(',', '.')) : null
}

export interface LensGuess { mm: number; from: string }

/** What the picture knows of its lens: a Stage still (Image › From a stage) its camera's focal; a prompt its camera lens in mm. */
export async function lensGuess(asset: Asset): Promise<LensGuess | null> {
  const recipe = (asset.params as { recipe?: { kind?: string; stage_id?: string; camera_id?: string } } | null)?.recipe
  if (recipe?.kind === 'stage_shot' && recipe.stage_id && recipe.camera_id) {
    try {
      const st = await unwrap(http.GET('/stages/{st_id}', { params: { path: { st_id: recipe.stage_id } } }))
      const cam = st.cameras.find((c) => c.id === recipe.camera_id)
      if (cam) return { mm: cam.focal_mm, from: `the Stage camera ${cam.name}` }
    } catch { /* the stage is gone: no guess */ }
  }
  const camera = (asset.prompt_json as { camera?: { lens?: string } } | null)?.camera
  const mm = mmInText(camera?.lens) ?? mmInText(asset.prompt_text)
  return mm ? { mm, from: 'the prompt' } : null
}
