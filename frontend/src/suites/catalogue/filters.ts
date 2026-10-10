// Query-bar filters (D34, proto01_design/01 §6b): each filter is a chip when active (click = its editor, ✕ = remove) and an
// entry in the "+ Filter" menu. Batch and lineage chips are set from a tile's menu, not from "+ Filter".
import { CalendarDays, Cpu, FileType, GitBranch, Layers, Ratio, Star, Tag, ToggleLeft, Workflow } from 'lucide-react'
import type { MenuItem } from '../../frame/commands'
import { askText, useSession } from '../../store/session'
import type { CatalogueState, Query } from './catalogueStore'

type IconType = typeof Star
export interface FilterDef {
  id: string; label: string; icon: IconType; inMenu: boolean
  active: (q: Query) => boolean
  chip: (q: Query) => string
  options: (c: CatalogueState) => MenuItem[]
  clear: Partial<Query>
}

const opt = (c: CatalogueState, label: string, checked: boolean, patch: Partial<Query>): MenuItem => ({ label, checked, run: () => void c.setQuery(patch) })
const SOURCES: [string, string][] = [['generate', 'Generate'], ['inpaint', 'Inpaint'], ['refine', 'Refine'], ['upscale', 'Upscale'], ['animate', 'Animate'], ['extract', 'Frame extract'], ['import', 'Imported']]
const DATES: [string, string][] = [['today', 'Today'], ['last_session', 'Last session'], ['7d', 'Last 7 days'], ['30d', 'Last 30 days']]
const day = (iso?: string) => iso?.slice(0, 10) ?? '…'

export const FILTERS: FilterDef[] = [
  { id: 'state', label: 'State', icon: ToggleLeft, inMenu: true, clear: { state: 'all' },
    active: (q) => q.state !== 'all', chip: (q) => `State: ${q.state === 'none' ? 'unjudged' : q.state}`,
    options: (c) => (['keep', 'reject', 'none'] as const).map((s) => opt(c, s === 'none' ? 'Unjudged' : s === 'keep' ? 'Kept' : 'Rejected', c.q.state === s, { state: s })) },
  { id: 'type', label: 'Type', icon: FileType, inMenu: true, clear: { kind: undefined, has_document: undefined },
    active: (q) => !!q.kind || q.has_document !== undefined, chip: (q) => `Type: ${q.kind === 'video' ? 'clips' : q.kind === 'image' ? 'images' : 'documents'}`,
    options: (c) => [opt(c, 'Images', c.q.kind === 'image', { kind: 'image', has_document: undefined }), opt(c, 'Clips', c.q.kind === 'video', { kind: 'video', has_document: undefined }),
      opt(c, 'Has a document', c.q.has_document === true, { kind: undefined, has_document: true })] },
  { id: 'source', label: 'Source', icon: Workflow, inMenu: true, clear: { suite: undefined },
    active: (q) => !!q.suite, chip: (q) => `Source: ${SOURCES.find(([k]) => k === q.suite)?.[1] ?? q.suite}`,
    options: (c) => SOURCES.map(([k, l]) => opt(c, l, c.q.suite === k, { suite: k })) },
  { id: 'model', label: 'Model', icon: Cpu, inMenu: true, clear: { model_id: undefined },
    active: (q) => !!q.model_id, chip: (q) => `Model: ${q.model_id}`,
    options: (c) => Object.keys(useSession.getState().capabilities?.models ?? {}).map((m) => opt(c, m, c.q.model_id === m, { model_id: m })) },
  { id: 'rating', label: 'Rating', icon: Star, inMenu: true, clear: { rating_min: 0 },
    active: (q) => q.rating_min > 0, chip: (q) => `Rating ≥ ${'★'.repeat(q.rating_min)}`,
    options: (c) => [5, 4, 3, 2, 1].map((n) => opt(c, `${'★'.repeat(n)} or more`, c.q.rating_min === n, { rating_min: n })) },
  { id: 'date', label: 'Date', icon: CalendarDays, inMenu: true, clear: { date_preset: undefined, created_from: undefined, created_to: undefined },
    active: (q) => !!q.date_preset || !!q.created_from || !!q.created_to,
    chip: (q) => q.date_preset ? `Date: ${DATES.find(([k]) => k === q.date_preset)?.[1].toLowerCase()}` : `Date: ${day(q.created_from)} → ${day(q.created_to)}`,
    options: (c) => [...DATES.map(([k, l]) => opt(c, l, c.q.date_preset === k, { date_preset: k as Query['date_preset'], created_from: undefined, created_to: undefined })),
      { sep: true }, { label: 'Range…', run: () => void askText({ title: 'Date range', text: 'From and to, as YYYY-MM-DD (either may be left out).', placeholder: '2026-10-01 2026-10-07',
        initial: [c.q.created_from?.slice(0, 10), c.q.created_to?.slice(0, 10)].filter(Boolean).join(' ') }).then((v) => {
        if (v === null) return
        const [a, b] = (v.match(/\d{4}-\d{2}-\d{2}/g) ?? []) as string[]
        void c.setQuery({ date_preset: undefined, created_from: a ? `${a}T00:00:00` : undefined, created_to: b ? `${b}T23:59:59` : undefined })
      }) }] },
  { id: 'tags', label: 'Tags', icon: Tag, inMenu: true, clear: { tags_any: [] },
    active: (q) => q.tags_any.length > 0, chip: (q) => `Tags: ${q.tags_any.join(', ')}`,
    options: (c) => [...c.tagCloud.slice(0, 20).map((t) => ({ label: `${t.tag}  (${t.count})`, checked: c.q.tags_any.includes(t.tag),
      run: () => void c.setQuery({ tags_any: c.q.tags_any.includes(t.tag) ? c.q.tags_any.filter((x) => x !== t.tag) : [...c.q.tags_any, t.tag] }) })),
      ...(c.tagCloud.length ? [{ sep: true } as MenuItem] : []),
      { label: 'Another tag…', run: () => void askText({ title: 'Filter by tag', placeholder: 'tag' }).then((t) => { if (t?.trim() && !c.q.tags_any.includes(t.trim())) void c.setQuery({ tags_any: [...c.q.tags_any, t.trim()] }) }) }] },
  { id: 'aspect', label: 'Aspect', icon: Ratio, inMenu: false, clear: { aspect: undefined },
    active: (q) => !!q.aspect, chip: (q) => `Aspect: ${q.aspect}`,
    options: (c) => (['landscape', 'portrait', 'square'] as const).map((a) => opt(c, a[0].toUpperCase() + a.slice(1), c.q.aspect === a, { aspect: a })) },
  { id: 'derived', label: 'Derivations', icon: GitBranch, inMenu: false, clear: { has_children: undefined },
    active: (q) => q.has_children !== undefined, chip: (q) => (q.has_children ? 'Has derivations' : 'No derivations'),
    options: (c) => [opt(c, 'Has derivations', c.q.has_children === true, { has_children: true }), opt(c, 'No derivations', c.q.has_children === false, { has_children: false })] },
  { id: 'batch', label: 'Batch', icon: Layers, inMenu: false, clear: { batch_id: undefined, batch_label: undefined },
    active: (q) => !!q.batch_id, chip: (q) => `Batch${q.batch_label ? ` · ${q.batch_label}` : ''}`, options: () => [] },
  { id: 'lineage', label: 'Lineage', icon: GitBranch, inMenu: false, clear: { root_id: undefined, root_label: undefined },
    active: (q) => !!q.root_id, chip: (q) => `Lineage${q.root_label ? ` · ${q.root_label}` : ''}`, options: () => [] },
]

/** Every filter cleared (the query bar's ✕ and the empty-grid "Clear filters"). */
export const CLEAR_ALL: Partial<Query> = Object.assign({ search: '' }, ...FILTERS.map((f) => f.clear))

/** The "+ Filter" menu: one submenu per filter, the rarer ones under More. */
export function addFilterMenu(c: CatalogueState): MenuItem[] {
  const sub = (f: FilterDef): MenuItem => ({ label: f.label, icon: f.icon, items: f.options(c) })
  return [...FILTERS.filter((f) => f.inMenu).map(sub), { sep: true }, { label: 'More', items: FILTERS.filter((f) => !f.inMenu && f.options(c).length).map(sub) }]
}
