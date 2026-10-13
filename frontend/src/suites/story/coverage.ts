// 17 §3b (D85): the coverage grid of a profile version — shot size × angle, the kept references' count per cell read from each asset's
// `params.coverage_cell` (an Expand job stamps it; an imported or generated hero has none). Pure, so the Cast tab and its tests share it.
export interface CoverageCell { shot: string; angle: string; expression?: string; take?: number }
export interface CoverageGrid { shots: string[]; angles: string[]; counts: Record<string, Record<string, number>>; total: number; uncelled: number }

const cellOf = (a: { params?: Record<string, unknown> | null }): CoverageCell | null => {
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

/** Thin cells: the vocabulary's cells with no reference (what to re-roll — advisory, 02 §7). */
export function thinCells(g: CoverageGrid): CoverageCell[] {
  const out: CoverageCell[] = []
  for (const s of g.shots) for (const a of g.angles) if (!(g.counts[s]?.[a] ?? 0)) out.push({ shot: s, angle: a })
  return out
}
