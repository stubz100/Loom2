// 17 §3b (D85): the coverage grid of a profile version — shot size × angle, the kept references' count per cell read from each asset's
// `params.coverage_cell` (an Expand job stamps it; an imported or generated hero has none). Pure, so the Cast tab and its tests share it.
export interface CoverageCell { shot: string; angle: string; expression?: string; take?: number }
export interface CoverageGrid { shots: string[]; angles: string[]; counts: Record<string, Record<string, number>>; total: number; uncelled: number }

export const cellOf = (a: { params?: Record<string, unknown> | null }): CoverageCell | null => {
  const c = a.params?.coverage_cell
  if (!c || typeof c !== 'object') return null
  const { shot, angle } = c as Record<string, unknown>
  return typeof shot === 'string' && typeof angle === 'string' ? (c as CoverageCell) : null
}

/** The grid over `assets` with the vocabulary's rows and columns (from /capabilities.story; cells outside it are added as rows / columns). */
export function coverageGrid(assets: { params?: Record<string, unknown> | null }[], shots: string[], angles: string[]): CoverageGrid {
  const counts: Record<string, Record<string, number>> = {}
  const rows = [...shots], cols = [...angles]
  let uncelled = 0
  for (const a of assets) {
    const c = cellOf(a)
    if (!c) { uncelled += 1; continue }
    if (!rows.includes(c.shot)) rows.push(c.shot)
    if (!cols.includes(c.angle)) cols.push(c.angle)
    counts[c.shot] ??= {}
    counts[c.shot][c.angle] = (counts[c.shot][c.angle] ?? 0) + 1
  }
  return { shots: rows, angles: cols, counts, total: assets.length, uncelled }
}

/** The shot-size rows with at least one reference — the bootstrap strip's "Curate" is done when every row has one (17 §3b). */
export function rowsCovered(g: CoverageGrid): string[] {
  return g.shots.filter((s) => Object.values(g.counts[s] ?? {}).some((n) => n > 0))
}

export interface Readiness { score: number; summary: string; lines: string[]; refs: number; rows: number; anglesCovered: number; expressions: number; celled: number }

/** 18 §3d (LT2): how ready a version's reference set is for a LoRA — advisory (D10): a 0–100 score with its sentences, never a gate.
 *  References (24 = full marks), the shot-size rows covered, the angles (3), the expressions (2), a hero, and how many carry a cell (their captions). */
export function readiness(assets: { params?: Record<string, unknown> | null }[], shots: string[], angles: string[], hero: boolean): Readiness {
  const g = coverageGrid(assets, shots, angles)
  const refs = assets.length
  const rows = rowsCovered(g).length
  const anglesCovered = g.angles.filter((a) => g.shots.some((s) => (g.counts[s]?.[a] ?? 0) > 0)).length
  const expressions = new Set(assets.map((a) => (cellOf(a)?.expression ?? '')).filter(Boolean)).size
  const celled = refs - g.uncelled
  let score = Math.min(40, (refs * 40) / 24)
  score += shots.length ? (rows * 20) / shots.length : 0
  score += Math.min(15, anglesCovered * 5)
  score += Math.min(10, expressions * 5)
  score += hero ? 5 : 0
  score += refs ? Math.min(10, (celled / refs) * 10) : 0
  score = Math.round(score)
  const summary = refs < 4 ? 'too few references' : score >= 80 ? 'strong' : score >= 55 ? 'good' : 'thin'
  const lines = [
    `${refs} reference${refs === 1 ? '' : 's'} (12 good, 24 strong)`,
    `${rows} of ${shots.length || '?'} shot-size rows covered`,
    `${anglesCovered} angle${anglesCovered === 1 ? '' : 's'} (3 good)`,
    `${expressions} expression${expressions === 1 ? '' : 's'} (2 good)`,
    hero ? 'the hero is set' : 'no hero',
    `${celled} of ${refs} carry a coverage cell (their captions)`,
  ]
  return { score, summary, lines, refs, rows, anglesCovered, expressions, celled }
}

/** Thin cells: the vocabulary's cells with no reference (what to re-roll — advisory, 02 §7). */
export function thinCells(g: CoverageGrid): CoverageCell[] {
  const out: CoverageCell[] = []
  for (const s of g.shots) for (const a of g.angles) if (!(g.counts[s]?.[a] ?? 0)) out.push({ shot: s, angle: a })
  return out
}
