// D57: Photoshop's curve as PhotoCraft samples it (crates/compose/src/adjust.rs curve_lut @ b37bff98, Copyright (c) 2026 ArtCraft Team
// and the PhotoCraft contributors, MIT OR Apache-2.0) — a natural cubic spline through the points (it may overshoot between them, as
// Photoshop's does), flat outside the first / last point, clamped to 0..1, sampled into 4096 entries and read back by linear
// interpolation. compose.py spline_lut / lut_lookup are the same code; the Curves editor draws with it and the adjustment shader's
// 256-entry table is filled from it.
export const CURVE_LUT_N = 4096
export type CurvePoints = [number, number][]          // [input, output] in 0..255

export function splineLut(points: CurvePoints): Float32Array {
  const pts = points.map(([a, b]) => [Number(a) / 255, Number(b) / 255] as [number, number]).sort((p, q) => p[0] - q[0])
  const dd: [number, number][] = []
  for (const q of pts) if (!dd.length || Math.abs(q[0] - dd[dd.length - 1][0]) >= 1e-6) dd.push(q)
  const out = new Float32Array(CURVE_LUT_N)
  if (dd.length < 2) { for (let k = 0; k < CURVE_LUT_N; k++) out[k] = k / (CURVE_LUT_N - 1); return out }
  const n = dd.length, x = dd.map((q) => q[0]), y = dd.map((q) => q[1])
  const m2 = new Float64Array(n)
  if (n > 2) {                                          // second derivatives of the natural spline (tridiagonal solve)
    const c = new Float64Array(n), d = new Float64Array(n)
    for (let i = 1; i < n - 1; i++) {
      const h0 = x[i] - x[i - 1], h1 = x[i + 1] - x[i]
      const a = h0 / 6, b = (h0 + h1) / 3, cc = h1 / 6
      const r = (y[i + 1] - y[i]) / h1 - (y[i] - y[i - 1]) / h0
      const denom = b - a * c[i - 1]
      c[i] = cc / denom; d[i] = (r - a * d[i - 1]) / denom
    }
    for (let i = n - 2; i >= 1; i--) m2[i] = d[i] - c[i] * m2[i + 1]
  }
  let i = 0
  for (let k = 0; k < CURVE_LUT_N; k++) {
    const xv = Math.fround(k / (CURVE_LUT_N - 1))      // PhotoCraft samples at f32 positions
    if (xv <= x[0]) { out[k] = Math.min(1, Math.max(0, y[0])); continue }
    if (xv >= x[n - 1]) { out[k] = Math.min(1, Math.max(0, y[n - 1])); continue }
    while (i < n - 2 && xv > x[i + 1]) i++
    const h = x[i + 1] - x[i], a = (x[i + 1] - xv) / h, b = (xv - x[i]) / h
    const v = a * y[i] + b * y[i + 1] + ((a * a * a - a) * m2[i] + (b * b * b - b) * m2[i + 1]) * h * h / 6
    out[k] = Math.min(1, Math.max(0, v))
  }
  return out
}

/** Linear interpolation between LUT entries (PhotoCraft `lut`). */
export function lutAt(t: Float32Array, v: number): number {
  const xi = Math.min(1, Math.max(0, v)) * (t.length - 1)
  const i = Math.floor(xi), j = Math.min(i + 1, t.length - 1), f = xi - i
  return t[i] * (1 - f) + t[j] * f
}

const cache = new Map<string, Float32Array>()
/** The LUT of a point list, cached by its JSON (the editor redraws and the shader refills often). */
export function cachedLut(points: CurvePoints): Float32Array {
  const key = JSON.stringify(points)
  let t = cache.get(key)
  if (!t) { t = splineLut(points); if (cache.size > 64) cache.clear(); cache.set(key, t) }
  return t
}
