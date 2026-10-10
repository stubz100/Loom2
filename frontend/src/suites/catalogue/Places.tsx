// Places (D34, proto01_design/01 §6a): Unprocessed, Library, the Album's group tree and Trash. Places are where you go;
// conditions live in the strip's filter chips. Every row takes dropped tiles; group rows take cards too.
import { BookOpen, ChevronDown, ChevronRight, Columns2, Copy, FolderPlus, Inbox, Library, Pencil, Trash2, Ungroup, X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { askConfirm, askText, useSession } from '../../store/session'
import { assetIds, onlyAssets, useDropTarget, type DragPayload } from '../../frame/drag'
import { showMenu } from '../../frame/ContextMenu'
import { sep, type MenuItem } from '../../frame/commands'
import { ALBUM_ID, useAlbum, type AlbumNode } from './albumStore'
import { useCat } from './catalogueContext'
import type { CatalogueState } from './catalogueStore'
import { openInOtherPane, openPlace } from './split'

export { openPlace }

function Row({ icon, label, count, active, depth = 0, chevron, drop, onOpen, onMenu, title }: {
  icon?: ReactNode; label: string; count?: number | string; active?: boolean; depth?: number; chevron?: ReactNode
  drop?: { accept: (p: DragPayload) => boolean; run: (p: DragPayload) => void }; onOpen: () => void; onMenu?: (e: React.MouseEvent) => void; title?: string
}) {
  const { ref, over } = useDropTarget((p) => !!drop && drop.accept(p), (p) => drop?.run(p))
  return (
    <div ref={ref} className={`place-row${active ? ' active' : ''}${over ? ' drop-over' : ''}`} style={{ paddingLeft: 6 + depth * 14 }} title={title}
      onContextMenu={(e) => { if (onMenu) { e.preventDefault(); onMenu(e) } }}>
      {chevron ?? <span className="chev" />}
      <button className="place-open" onClick={onOpen}>{icon}<span className="lbl">{label}</span>{count !== undefined && <span className="n">{count}</span>}</button>
    </div>
  )
}

export function groupMenu(node: AlbumNode, c: CatalogueState): MenuItem[] {
  const al = useAlbum.getState()
  return [
    { label: 'Open', icon: BookOpen, run: () => openPlace(c, { group: node.id }) },
    { label: 'Open in other pane', icon: Columns2, run: () => openInOtherPane({ group: node.id }) },
    { label: 'New group inside…', icon: FolderPlus, run: () => void askText({ title: `New group in "${node.name}"`, placeholder: 'group name' }).then((n) => { if (n?.trim()) void al.create(n.trim(), node.id) }) },
    sep,
    { label: 'Rename…', icon: Pencil, run: () => void askText({ title: 'Rename group', initial: node.name }).then((n) => { if (n?.trim() && n !== node.name) void al.rename(node.id, n.trim()) }) },
    { label: 'Duplicate', icon: Copy, run: () => void al.duplicate(node.id) },
    { label: 'Ungroup', icon: Ungroup, run: () => void al.ungroup(node.id).then(() => { if (c.q.group_id === node.id) openPlace(c, 'unprocessed') }) },
    sep,
    { label: 'Delete group…', icon: X, danger: true, run: () => void askConfirm({ title: `Delete "${node.name}"?`, text: `Its ${node.total} photo${node.total === 1 ? '' : 's'} go back to Unprocessed; nothing is trashed. The arrangement of the page is lost.`, okLabel: 'Delete group', danger: true })
      .then((ok) => { if (ok) void al.remove(node.id).then(() => { if (c.q.group_id === node.id) openPlace(c, 'unprocessed') }) }) },
  ]
}

/** Assets and groups dropped on a group row move onto that page (the server refuses a group into itself). */
const takesItems = (target: string) => (p: DragPayload) => p.items.length > 0 && !p.items.some((i) => i.kind === 'group' && i.id === target)

function TreeRows({ nodes, depth }: { nodes: AlbumNode[]; depth: number }) {
  const c = useCat()
  const expanded = useAlbum((s) => s.expanded)
  const toggle = useAlbum((s) => s.toggle)
  return (
    <>
      {nodes.map((n) => {
        const open = !!expanded[n.id]
        const chevron = n.children.length
          ? <button className="chev" aria-label={open ? `Collapse ${n.name}` : `Expand ${n.name}`} onClick={() => toggle(n.id)}>{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button>
          : undefined
        return (
          <div key={n.id}>
            <Row label={n.name} count={n.total} depth={depth} chevron={chevron} active={c.q.group_id === n.id}
              drop={{ accept: takesItems(n.id), run: (p) => void useAlbum.getState().move(p.items, n.id) }}
              onOpen={() => openPlace(c, { group: n.id })} onMenu={(e) => showMenu(e, groupMenu(n, c))} title="drop photos or groups here to move them onto this page" />
            {open && n.children.length > 0 && <TreeRows nodes={n.children} depth={depth + 1} />}
          </div>
        )
      })}
    </>
  )
}

export function Places() {
  const c = useCat()
  const s = useSession()
  const tree = useAlbum((st) => st.tree)
  const load = useAlbum((st) => st.load)
  useEffect(() => { if (s.project?.open) void load() }, [s.project?.path, load])
  useEffect(() => {                                               // the open group and its ancestors stay expanded: the tree shows where you are and what is inside
    const gid = c.q.group_id
    if (!gid || !tree) return
    const al = useAlbum.getState()
    for (const p of al.pathOf(gid)) if (!al.expanded[p.id] && al.find(p.id)?.children.length) al.toggle(p.id, true)
  }, [c.q.group_id, tree]) // eslint-disable-line react-hooks/exhaustive-deps
  if (!s.project?.open) return <span style={{ color: 'var(--fg3)' }}>Open or create a project.</span>
  const q = c.q
  const newGroup = () => void askText({ title: 'New group', text: 'A page on the Album; drag photos onto it.', placeholder: 'group name' }).then((n) => { if (n?.trim()) void useAlbum.getState().create(n.trim()) })
  return (
    <div className="places">
      <Row icon={<Inbox size={16} />} label="Unprocessed" count={c.counts.unprocessed ?? ''} active={q.folder === 'unprocessed' && !q.group_id}
        drop={{ accept: onlyAssets, run: (p) => void useAlbum.getState().move(p.items, null) }} onOpen={() => openPlace(c, 'unprocessed')}
        onMenu={(e) => showMenu(e, [{ label: 'Open', icon: Inbox, run: () => openPlace(c, 'unprocessed') }, { label: 'Open in other pane', icon: Columns2, run: () => openInOtherPane('unprocessed') }])}
        title="every new generation, render, clip and import lands here until you place it on a page" />
      <Row icon={<Library size={16} />} label="Library" count={c.counts.all ?? ''} active={q.folder === 'all' && !q.group_id} onOpen={() => openPlace(c, 'library')} title="every asset in the project, wherever it lives"
        onMenu={(e) => showMenu(e, [{ label: 'Open', icon: Library, run: () => openPlace(c, 'library') }, { label: 'Open in other pane', icon: Columns2, run: () => openInOtherPane('library') }])} />
      <AlbumHead active={q.group_id === ALBUM_ID} onOpen={() => openPlace(c, { group: ALBUM_ID })} onNew={newGroup} />
      {tree && <TreeRows nodes={tree.children} depth={0} />}
      {tree && !tree.children.length && <p className="hint">No groups yet. Make one with <FolderPlus size={12} style={{ verticalAlign: '-2px' }} />, then drag photos onto it.</p>}
      <div className="spacer" />
      <Row icon={<Trash2 size={16} />} label="Trash" count={c.counts.trash ?? ''} active={q.folder === 'trash'}
        drop={{ accept: onlyAssets, run: (p) => { const ids = assetIds(p); void c.trash(ids) } }} onOpen={() => openPlace(c, 'trash')}
        onMenu={(e) => showMenu(e, [{ cmd: 'cat.emptyTrash' }])} title="drop photos here to move them to Trash" />
    </div>
  )
}

/** The Album heading opens the root page and takes drops: items moved onto the Album page itself. */
function AlbumHead({ active, onOpen, onNew }: { active: boolean; onOpen: () => void; onNew: () => void }) {
  const { ref, over } = useDropTarget(takesItems(ALBUM_ID), (p) => void useAlbum.getState().move(p.items, ALBUM_ID))
  return (
    <div ref={ref} className={`places-head${active ? ' active' : ''}${over ? ' drop-over' : ''}`}>
      <button className="place-open album" onClick={onOpen} onContextMenu={(e) => showMenu(e, [{ label: 'New group…', icon: FolderPlus, run: onNew }])} title="the Album page: drop photos or groups here">
        <BookOpen size={14} /><span>Album</span>
      </button>
      <button className="quiet" title="New group" aria-label="New group" onClick={onNew}><FolderPlus size={14} /></button>
    </div>
  )
}

