// The engine size of an Edit AI job (10 §8), shown by the AI panel before it runs: the same rule as the orchestrator's
// edit_ai._engine_size. Pure, so the unit suite (D68) checks it against the orchestrator's numbers.

/** Mirrors edit_ai._engine_size: ≥ min on the longer side, ≤ max, ≤ 1 MP, multiples of 16. */
export function planSize(w: number, h: number, minSize: number, maxSize: number, maxPixels = 1048576): { w: number; h: number; scale: number } {
  const longer = Math.max(w, h)
  let s = 1
  if (minSize && longer < minSize) s = minSize / longer
  if (maxSize && longer * s > maxSize) s = maxSize / longer
  if (maxPixels && w * h * s * s > maxPixels) s = Math.sqrt(maxPixels / (w * h))
  const r16 = (n: number) => Math.max(16, Math.ceil(n / 16) * 16)
  let ew = r16(w * s), eh = r16(h * s)
  // the 16-rounding may overshoot the cap: step down as the orchestrator does (before D68 the panel showed the overshooting size,
  // e.g. 1376 × 768 for a 1920 × 1080 region the engine runs at 1360 × 768)
  while (maxPixels && ew * eh > maxPixels && s > 0.05) { s *= 0.99; ew = r16(w * s); eh = r16(h * s) }
  return { w: ew, h: eh, scale: s }
}
