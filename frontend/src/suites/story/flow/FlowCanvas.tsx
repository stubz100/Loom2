// 17 §3d (D85): the Flow canvas on @xyflow/react (React Flow 12, MIT) — nodes from the story store's node files, their places and edges
// from the index; a drag moves (saved on drop), a handle-to-handle drag connects (one edge per out-port), a right-click on the pane adds
// a node there, on a node opens its verbs. The node card shows the type, the title, the speaker and first line, and the bound shot.
// D90: an edge is selected by a click and goes by its right-click menu or Delete (B3); the canvas takes the Flow tab's keys (B2); "Add a
// node here" maps the pointer through the viewport (B11); a Shot node shows its text — a beat's line (B19). UI4 (02 §4.2): a node's board
// (an album group) shows as its cover, name and count; a group card dropped on a node becomes its board (makeFor.boardDrop).
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, ViewportPortal, applyNodeChanges, useReactFlow, useViewport, type Connection, type Edge, type Node, type NodeChange, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../../../api/client'
import type { FlowNode } from '../../../api/types'
import { sep, type MenuItem } from '../../../frame/commands'
import { useDropTarget } from '../../../frame/drag'
import { useAlbum } from '../../catalogue/albumStore'
import { boardDrop } from '../makeFor'
import { findNode } from '../styleSamples'
import { showMenu, useMenu } from '../../../frame/ContextMenu'
import { CLASS_LABEL, sy, useStory } from '../storyStore'
import { edgeMenu, flowView, nodeMenu, sceneMenu, templateItems } from '../storyCommands'
import { storyKey } from '../storyKeys'
import { NODE_LABEL } from './types'
import { cellsOf, lengthLine, owes, routeOf, staleFrom, STEPS, type CellState, type Step } from '../board'
import { TriangleAlert } from 'lucide-react'

const NODE_W = 220

interface StoryData extends Record<string, unknown> { node: FlowNode; thumb: string | null; speaker: string | null; problem: string | null; shotState: string | null; pills: { step: Step; label: string; state: CellState }[] | null
  length: { text: string; over: boolean; title: string } | null; stale: number
  board: { name: string; cover: string | null; total: number } | null; place: string | null }
type StoryNodeT = Node<StoryData, 'story'>
/** RC2c: the scene groups' frames — drawn in the flow's coordinates behind the edges and nodes (a ViewportPortal: not nodes React Flow
 *  measures, so their size never feeds back into its ResizeObserver), around their nodes as they stand. The name tab is the frame's
 *  handle: a click picks the scene, a right-click shows its menu, a drag moves its nodes; the body lets clicks through to the canvas. */
interface Frame { id: string; name: string; count: number; x: number; y: number; w: number; h: number }
const FRAME_PAD = 20, FRAME_HEAD = 26

function SceneFrames({ frames, picked, onMove, onDrop }: { frames: Frame[]; picked: string | null; onMove: (sceneId: string, dx: number, dy: number) => void; onDrop: () => void }) {
  const { zoom } = useViewport()
  const drag = useRef<{ id: string; x: number; y: number; moved: boolean } | null>(null)
  return (
    <ViewportPortal>
      {frames.map((f) => (
        <div key={f.id} className={`scene-frame${picked === f.id ? ' picked' : ''}`} data-scene={f.name} style={{ transform: `translate(${f.x}px, ${f.y}px)`, width: f.w, height: f.h }}>
          <span className="scene-name nodrag nopan" title={`${f.name} — a scene of ${f.count} node${f.count === 1 ? '' : 's'}: drag its name to move them together, right-click to rename or dissolve it`}
            onPointerDown={(e) => { if (e.button !== 0) return; e.stopPropagation(); e.currentTarget.setPointerCapture(e.pointerId); drag.current = { id: f.id, x: e.clientX, y: e.clientY, moved: false } }}
            onPointerMove={(e) => { const d = drag.current; if (!d || d.id !== f.id) return; const dx = (e.clientX - d.x) / zoom, dy = (e.clientY - d.y) / zoom
              if (Math.abs(dx) + Math.abs(dy) > 2) d.moved = true
              if (d.moved) onMove(f.id, dx, dy) }}
            onPointerUp={() => { const d = drag.current; drag.current = null; if (!d) return; if (d.moved) onDrop(); else { sy().selectNode(null); sy().selectScene(f.id) } }}
            onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); sy().selectNode(null); sy().selectScene(f.id); showMenu(e, sceneMenu()) }}>{f.name}</span>
        </div>
      ))}
    </ViewportPortal>
  )
}

/** What a node's handles depend on: its type and a Choice's options. */
const handlesOf = (n: FlowNode): string => `${n.type}|${n.options.map((o) => o.id).join(',')}`

function StoryNode({ id, data, selected }: NodeProps<StoryNodeT>) {
  const n = data.node
  const name = n.title || NODE_LABEL[n.type]
  const { ref, over } = useDropTarget((p) => boardDrop(p, name).verdict.ok, (p) => { const g = boardDrop(p, name).group; if (g) void sy().patchNode(n.id, { board_group_id: g }) }, (p) => boardDrop(p, name).verdict)
  const ports = n.type === 'choice' ? n.options.map((o) => ({ id: `opt:${o.id}`, label: o.label || '…' })) : n.type === 'condition' ? [{ id: 'then', label: 'then' }, { id: 'else', label: 'else' }] : n.type === 'jump' || n.type === 'comment' ? [] : [{ id: 'out', label: '' }]
  return (
    <div ref={ref} className={`flow-node t-${n.type}${selected ? ' selected' : ''}${data.problem ? ' problem' : ''}${over ? ' drop-over' : ''}`} data-id={id} style={{ width: NODE_W }} title={data.problem ?? undefined}>
      {n.type !== 'start' && <Handle type="target" position={Position.Left} />}
      <div className="head"><span className="type">{NODE_LABEL[n.type]}</span><span className="title">{n.title || (n.type === 'shot' ? n.lines[0]?.text?.slice(0, 24) ?? '' : '')}</span></div>
      {n.type === 'shot' && n.lines.length > 0 && <div className="line">{data.speaker && <b>{data.speaker}: </b>}{n.lines[0].text}</div>}
      {(n.type === 'comment' || n.type === 'shot') && n.text && <div className="line">{n.text}</div>}
      {n.type === 'jump' && <div className="line">→ {n.target ?? '…'}</div>}
      {n.type === 'condition' && n.cond && <div className="line">{n.cond.var || '?'} {n.cond.op === 'ne' ? '≠' : '='} {String(n.cond.value)}</div>}
      {n.type === 'action' && <div className="line">{n.set.map((s) => `${String(s.var)} = ${String(s.value)}`).join(', ') || 'sets nothing'}</div>}
      {n.type === 'shot' && (
        <div className={`shot${n.shot_id ? '' : ' none'}`}>{data.thumb ? <img src={api.thumbUrl(data.thumb, 256)} alt="" /> : <span>{n.shot_id ? 'shot' : 'no shot'}</span>}{data.shotState && <i className={`dot ${data.shotState === 'final' ? 'ok' : 'tight'}`} title={data.shotState} />}
          {(data.length || data.stale > 0) && <span className="facts">{/* RC2b (D96): the length (a warning past the guide) and the stale count */}
            {data.length && <span className={`len${data.length.over ? ' over' : ''}`} title={data.length.title} data-length>{data.length.over && <TriangleAlert size={11} aria-hidden />}{data.length.text}</span>}
            {data.stale > 0 && <span className="stale" title={`${data.stale} part${data.stale === 1 ? '' : 's'} of its recipe changed since made — Run stale on the shot`} data-stale>{data.stale} stale</span>}</span>}</div>
      )}
      {data.pills && <div className="pills" aria-label="the shot's steps">{data.pills.map((p) => <span key={p.step} className={`pill ${p.state}`} title={`${p.label}: ${p.state}`}>{p.label.toLowerCase()}</span>)}</div>}{/* D125 (SP3): the shot's steps, as on the board */}
      {data.place && <div className="place" title="where — a Cast place; Make frame links Generate's scene to it">@ {data.place}</div>}{/* D93 (C7) */}
      {n.board_group_id && <div className="board" title={data.board ? `board: ${data.board.name} — its images seed Make frame's references` : 'its board group was deleted'}>
        {data.board?.cover ? <img src={api.thumbUrl(data.board.cover, 256)} alt="" /> : <span className="empty" />}<span>{data.board ? `${data.board.name} · ${data.board.total}` : 'board gone'}</span></div>}
      {ports.map((p, i) => (
        <div key={p.id} className="port" style={{ top: ports.length === 1 ? '50%' : `${40 + i * 18}px` }}>
          {ports.length > 1 && <span className="plabel">{p.label}</span>}
          <Handle type="source" position={Position.Right} id={p.id} style={{ top: ports.length === 1 ? '50%' : `${40 + i * 18}px` }} />
        </div>
      ))}
    </div>
  )
}

const nodeTypes = { story: StoryNode }

/** Inside the canvas: the Fit command reaches the viewport through `flowView` (the canvas is not a store). */
function FitBridge() {
  const rf = useReactFlow()
  useEffect(() => {
    flowView.fit = () => void rf.fitView({ padding: 0.2 })
    flowView.centre = () => { const el = document.querySelector('.flow-host'); if (!el) return null; const r = el.getBoundingClientRect(); const p = rf.screenToFlowPosition({ x: r.left + r.width / 2, y: r.top + r.height / 2 }); return { x: Math.round(p.x), y: Math.round(p.y) } }
    flowView.toFlow = (x, y) => { const p = rf.screenToFlowPosition({ x, y }); return { x: Math.round(p.x), y: Math.round(p.y) } }
    return () => { flowView.fit = undefined; flowView.centre = undefined; flowView.toFlow = undefined }
  }, [rf])
  return null
}

/** U4 (D157 04 §7), the new shell's: `onOpen` — a Shot node's double-click opens its shot (Clay); `paneItems` — the canvas menu's own
 *  entries first (*New shot*). The old shell passes neither. */
export function FlowCanvas({ onOpen, paneItems }: { onOpen?: (shotId: string) => void; paneItems?: MenuItem[] } = {}) {
  const flowNodes = useStory((s) => s.flowNodes)
  const graph = useStory((s) => s.flowGraph)
  const nodeId = useStory((s) => s.nodeId)
  const shots = useStory((s) => s.shots)
  const clipsById = useStory((s) => s.clipsById)
  const boardFinals = useStory((s) => s.boardFinals)                                          // D125 (SP3): the pills read the board's records
  const boardCuts = useStory((s) => s.boardCuts)
  const cards = useStory((s) => s.cards)                                                      // RC2b: length and stale count
  const scenes = useStory((s) => s.scenes)                                                    // RC2c: the frames
  const sceneId = useStory((s) => s.sceneId)
  const cardGuide = useStory((s) => s.cardGuide)
  useEffect(() => { void sy().loadBoard() }, [shots])
  const profiles = useStory((s) => s.profiles)
  const problems = useStory((s) => s.problems)
  const edgeSel = useStory((s) => s.edge)
  const tree = useAlbum((a) => a.tree)
  useEffect(() => { if (!useAlbum.getState().tree) void useAlbum.getState().load() }, [])   // the boards' covers
  // B11: a pane menu dismissed without adding leaves no stale point for the next Strip add (an add reads it before the menu closes)
  useEffect(() => useMenu.subscribe((m, prev) => { if (prev.open && !m.open && sy().addAt) sy().setAddAt(null) }), [])
  const [nodes, setNodes] = useState<StoryNodeT[]>([])
  const [from, setFrom] = useState<StoryNodeT[]>([])
  const built = useMemo<StoryNodeT[]>(() => {
    if (!graph) return []
    const byProblem = new Map<string, string>()
    for (const p of problems ?? []) if (p.node_id && !byProblem.has(p.node_id)) byProblem.set(p.node_id, p.message)
    return graph.nodes.filter((p) => flowNodes[p.id]).map((p) => {
      const n = flowNodes[p.id]
      const sh = n.shot_id ? shots.find((s) => s.id === n.shot_id) : undefined
      const v = sh?.versions.find((x) => x.id === (n.shot_version ?? sh.current))
      const thumb = v?.frame_asset_id ?? (v?.clip_id ? clipsById[v.clip_id]?.asset_id ?? null : null)
      const sp = n.lines[0]?.speaker ? profiles.find((x) => x.id === n.lines[0].speaker) : undefined
      const g = findNode(tree, n.board_group_id)
      const cells = sh && v ? cellsOf(sh, v, n, { clipAudio: (id) => (clipsById[id] ? !!clipsById[id].audio_asset_id : undefined), finals: boardFinals, cuts: boardCuts, busy: () => new Set(), stale: staleFrom(cards) }) : null
      const pills = cells && v ? STEPS.filter((s) => s.id !== 'lines' && s.id !== 'cut' && owes(routeOf(v), n, s.id)).map((s) => ({ step: s.id, label: s.label, state: cells[s.id].state })) : null
      const card = sh ? cards[sh.id] : undefined
      return { id: p.id, type: 'story' as const, position: { x: p.x, y: p.y }, selected: p.id === nodeId, data: { node: n, thumb, speaker: sp ? `${sp.name} (${CLASS_LABEL[sp.cls]})` : null, problem: byProblem.get(p.id) ?? null, shotState: v?.state ?? null, pills,
        length: lengthLine(card, cardGuide), stale: card?.stale ?? 0,
        board: g ? { name: g.name, cover: g.cover_ids[0] ?? null, total: g.total } : null, place: n.place_id ? profiles.find((x) => x.id === n.place_id)?.name ?? 'a deleted place' : null } }
    })
  }, [graph, flowNodes, nodeId, shots, clipsById, profiles, problems, tree, boardFinals, boardCuts, cards, cardGuide])
  if (from !== built) {                                                                       // derived state, synced in render (not an effect)
    setFrom(built)
    // U4: the sizes measured so far carried over — a node without them is hidden until measured, so a selection made it blink (and the
    // second click of a double-click fell through to the pane). Not when its handles changed (a Choice's options): it is measured again.
    setNodes((prev) => {
      const was = new Map(prev.map((p) => [p.id, p]))
      return built.map((b) => { const p = was.get(b.id); return p?.measured && handlesOf(p.data.node) === handlesOf(b.data.node) ? { ...b, measured: p.measured } : b })
    })
  }
  const edges = useMemo<Edge[]>(() => (graph?.edges ?? []).filter((e) => flowNodes[e.from] && flowNodes[e.to]).map((e) => {
    const n = flowNodes[e.from]
    const label = e.port.startsWith('opt:') ? n.options.find((o) => `opt:${o.id}` === e.port)?.label : e.port === 'then' || e.port === 'else' ? e.port : undefined
    return { id: `${e.from}:${e.port}`, source: e.from, sourceHandle: e.port, target: e.to, label, deletable: true, selected: edgeSel?.from === e.from && edgeSel.port === e.port }
  }), [graph, flowNodes, edgeSel])
  // RC2c: each scene's frame around its nodes as they stand now (their measured sizes once drawn)
  const frames = useMemo<Frame[]>(() => scenes.flatMap((s) => {
    const ms = nodes.filter((x) => s.node_ids.includes(x.id))
    if (!ms.length) return []
    const x0 = Math.min(...ms.map((m) => m.position.x)) - FRAME_PAD, y0 = Math.min(...ms.map((m) => m.position.y)) - FRAME_PAD - FRAME_HEAD
    const x1 = Math.max(...ms.map((m) => m.position.x + (m.measured?.width ?? NODE_W))) + FRAME_PAD
    const y1 = Math.max(...ms.map((m) => m.position.y + (m.measured?.height ?? 120))) + FRAME_PAD
    return [{ id: s.id, name: s.name, count: ms.length, x: x0, y: y0, w: x1 - x0, h: y1 - y0 }]
  }), [scenes, nodes])
  const dragFrom = useRef<Record<string, { x: number; y: number }> | null>(null)
  const onFrameMove = (sid: string, dx: number, dy: number) => {
    const s = scenes.find((x) => x.id === sid); if (!s) return
    if (!dragFrom.current) dragFrom.current = Object.fromEntries(nodes.filter((m) => s.node_ids.includes(m.id)).map((m) => [m.id, { ...m.position }]))
    const from = dragFrom.current
    setNodes((ns) => ns.map((m) => (from[m.id] ? { ...m, position: { x: from[m.id].x + dx, y: from[m.id].y + dy } } : m)))
  }
  const onFrameDrop = () => {
    const from = dragFrom.current; dragFrom.current = null; if (!from) return
    sy().moveNodes(nodes.filter((m) => from[m.id]).map((m) => ({ id: m.id, x: Math.round(m.position.x), y: Math.round(m.position.y) })))
  }
  const onNodesChange = (changes: NodeChange<StoryNodeT>[]) => {
    setNodes((ns) => applyNodeChanges(changes, ns))
    for (const c of changes) if (c.type === 'select' && c.selected) sy().selectNode(c.id)
  }
  return (
    <div className="flow-host" data-testid="flow-canvas" tabIndex={0} onKeyDown={(e) => { storyKey('flow', e.nativeEvent) }}>
      <ReactFlow<StoryNodeT, Edge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2} maxZoom={2} deleteKeyCode={null} proOptions={{ hideAttribution: true }}
        onNodesChange={onNodesChange}
        onSelectionChange={({ nodes: sel }) => sy().setFlowSel(sel.map((x) => x.id))}
        onNodeDragStop={(_e, _n, dragged) => sy().moveNodes(dragged.map((d) => ({ id: d.id, x: Math.round(d.position.x), y: Math.round(d.position.y) })))}
        onConnect={(c: Connection) => { if (c.source && c.target) void sy().connect(c.source, c.sourceHandle ?? 'out', c.target) }}
        onEdgesDelete={(es) => { for (const e of es) void sy().disconnect(e.source, e.sourceHandle ?? 'out') }}
        onNodeClick={(_e, n) => { sy().selectScene(null); sy().selectNode(n.id) }}
        onNodeDoubleClick={onOpen ? (_e, n) => { const id = flowNodes[n.id]?.shot_id; if (id) onOpen(id) } : undefined}
        onPaneClick={() => { sy().selectNode(null); sy().selectEdge(null); sy().selectScene(null) }}
        onEdgeClick={(_e, ed) => sy().selectEdge({ from: ed.source, port: ed.sourceHandle ?? 'out' })}
        onEdgeContextMenu={(e, ed) => { e.preventDefault(); sy().selectEdge({ from: ed.source, port: ed.sourceHandle ?? 'out' }); showMenu(e, edgeMenu()) }}
        onNodeContextMenu={(e, n) => { e.preventDefault(); sy().selectScene(null); sy().selectNode(n.id); showMenu(e, nodeMenu() as MenuItem[]) }}
        onPaneContextMenu={(e) => { e.preventDefault(); sy().setAddAt(flowView.toFlow?.(e.clientX, e.clientY) ?? null)
          showMenu(e, [...(paneItems ?? []), { heading: 'Add a node here' }, ...(['start', 'hub', 'choice', 'condition', 'action', 'shot', 'jump', 'comment'] as const).map((t) => ({ cmd: `story.flow.add.${t}` })),
            ...templateItems(null, flowView.toFlow?.(e.clientX, e.clientY) ?? null), sep, { cmd: 'story.flow.voiceEpisode' }, { cmd: 'story.flow.validate' }, { cmd: 'story.flow.play' }, { cmd: 'story.flow.fit' }]) }}>
        <Background gap={24} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
        <FitBridge />
        <SceneFrames frames={frames} picked={sceneId} onMove={onFrameMove} onDrop={onFrameDrop} />
      </ReactFlow>
    </div>
  )
}
