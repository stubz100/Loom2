// 17 §3d (D85): the Flow canvas on @xyflow/react (React Flow 12, MIT) — nodes from the story store's node files, their places and edges
// from the index; a drag moves (saved on drop), a handle-to-handle drag connects (one edge per out-port), a right-click on the pane adds
// a node there, on a node opens its verbs. The node card shows the type, the title, the speaker and first line, and the bound shot.
// D90: an edge is selected by a click and goes by its right-click menu or Delete (B3); the canvas takes the Flow tab's keys (B2); "Add a
// node here" maps the pointer through the viewport (B11); a Shot node shows its text — a beat's line (B19).
import { Background, Controls, Handle, MiniMap, Position, ReactFlow, applyNodeChanges, useReactFlow, type Connection, type Edge, type Node, type NodeChange, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../../api/client'
import type { FlowNode } from '../../../api/types'
import { sep, type MenuItem } from '../../../frame/commands'
import { showMenu, useMenu } from '../../../frame/ContextMenu'
import { CLASS_LABEL, sy, useStory } from '../storyStore'
import { edgeMenu, flowView, nodeMenu } from '../storyCommands'
import { storyKey } from '../storyKeys'
import { NODE_LABEL } from './types'

const NODE_W = 220

interface StoryData extends Record<string, unknown> { node: FlowNode; thumb: string | null; speaker: string | null; problem: string | null; shotState: string | null }
type StoryNodeT = Node<StoryData, 'story'>

function StoryNode({ id, data, selected }: NodeProps<StoryNodeT>) {
  const n = data.node
  const ports = n.type === 'choice' ? n.options.map((o) => ({ id: `opt:${o.id}`, label: o.label || '…' })) : n.type === 'condition' ? [{ id: 'then', label: 'then' }, { id: 'else', label: 'else' }] : n.type === 'jump' || n.type === 'comment' ? [] : [{ id: 'out', label: '' }]
  return (
    <div className={`flow-node t-${n.type}${selected ? ' selected' : ''}${data.problem ? ' problem' : ''}`} data-id={id} style={{ width: NODE_W }} title={data.problem ?? undefined}>
      {n.type !== 'start' && <Handle type="target" position={Position.Left} />}
      <div className="head"><span className="type">{NODE_LABEL[n.type]}</span><span className="title">{n.title || (n.type === 'dialogue' ? n.lines[0]?.text?.slice(0, 24) : '')}</span></div>
      {n.type === 'dialogue' && n.lines.length > 0 && <div className="line">{data.speaker && <b>{data.speaker}: </b>}{n.lines[0].text}</div>}
      {(n.type === 'comment' || n.type === 'shot') && n.text && <div className="line">{n.text}</div>}
      {n.type === 'jump' && <div className="line">→ {n.target ?? '…'}</div>}
      {n.type === 'condition' && n.cond && <div className="line">{n.cond.var || '?'} {n.cond.op === 'ne' ? '≠' : '='} {String(n.cond.value)}</div>}
      {n.type === 'action' && <div className="line">{n.set.map((s) => `${String(s.var)} = ${String(s.value)}`).join(', ') || 'sets nothing'}</div>}
      {(n.type === 'dialogue' || n.type === 'shot') && (
        <div className={`shot${n.shot_id ? '' : ' none'}`}>{data.thumb ? <img src={api.thumbUrl(data.thumb, 256)} alt="" /> : <span>{n.shot_id ? 'shot' : 'no shot'}</span>}{data.shotState && <i className={`dot ${data.shotState === 'final' ? 'ok' : 'tight'}`} title={data.shotState} />}</div>
      )}
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

export function FlowCanvas() {
  const flowNodes = useStory((s) => s.flowNodes)
  const graph = useStory((s) => s.flowGraph)
  const nodeId = useStory((s) => s.nodeId)
  const shots = useStory((s) => s.shots)
  const clipsById = useStory((s) => s.clipsById)
  const profiles = useStory((s) => s.profiles)
  const problems = useStory((s) => s.problems)
  const edgeSel = useStory((s) => s.edge)
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
      return { id: p.id, type: 'story' as const, position: { x: p.x, y: p.y }, selected: p.id === nodeId, data: { node: n, thumb, speaker: sp ? `${sp.name} (${CLASS_LABEL[sp.cls]})` : null, problem: byProblem.get(p.id) ?? null, shotState: v?.state ?? null } }
    })
  }, [graph, flowNodes, nodeId, shots, clipsById, profiles, problems])
  if (from !== built) { setFrom(built); setNodes(built) }                                      // derived state, synced in render (not an effect)
  const edges = useMemo<Edge[]>(() => (graph?.edges ?? []).filter((e) => flowNodes[e.from] && flowNodes[e.to]).map((e) => {
    const n = flowNodes[e.from]
    const label = e.port.startsWith('opt:') ? n.options.find((o) => `opt:${o.id}` === e.port)?.label : e.port === 'then' || e.port === 'else' ? e.port : undefined
    return { id: `${e.from}:${e.port}`, source: e.from, sourceHandle: e.port, target: e.to, label, deletable: true, selected: edgeSel?.from === e.from && edgeSel.port === e.port }
  }), [graph, flowNodes, edgeSel])
  const onNodesChange = (changes: NodeChange<StoryNodeT>[]) => {
    setNodes((ns) => applyNodeChanges(changes, ns))
    for (const c of changes) if (c.type === 'select' && c.selected) sy().selectNode(c.id)
  }
  return (
    <div className="flow-host" data-testid="flow-canvas" tabIndex={0} onKeyDown={(e) => { storyKey('flow', e.nativeEvent) }}>
      <ReactFlow<StoryNodeT, Edge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2} maxZoom={2} deleteKeyCode={null} proOptions={{ hideAttribution: true }}
        onNodesChange={onNodesChange}
        onNodeDragStop={(_e, _n, dragged) => sy().moveNodes(dragged.map((d) => ({ id: d.id, x: Math.round(d.position.x), y: Math.round(d.position.y) })))}
        onConnect={(c: Connection) => { if (c.source && c.target) void sy().connect(c.source, c.sourceHandle ?? 'out', c.target) }}
        onEdgesDelete={(es) => { for (const e of es) void sy().disconnect(e.source, e.sourceHandle ?? 'out') }}
        onNodeClick={(_e, n) => sy().selectNode(n.id)}
        onPaneClick={() => { sy().selectNode(null); sy().selectEdge(null) }}
        onEdgeClick={(_e, ed) => sy().selectEdge({ from: ed.source, port: ed.sourceHandle ?? 'out' })}
        onEdgeContextMenu={(e, ed) => { e.preventDefault(); sy().selectEdge({ from: ed.source, port: ed.sourceHandle ?? 'out' }); showMenu(e, edgeMenu()) }}
        onNodeContextMenu={(e, n) => { e.preventDefault(); sy().selectNode(n.id); showMenu(e, nodeMenu() as MenuItem[]) }}
        onPaneContextMenu={(e) => { e.preventDefault(); sy().setAddAt(flowView.toFlow?.(e.clientX, e.clientY) ?? null)
          showMenu(e, [{ heading: 'Add a node here' }, ...(['start', 'hub', 'dialogue', 'choice', 'condition', 'action', 'shot', 'jump', 'comment'] as const).map((t) => ({ cmd: `story.flow.add.${t}` })), sep, { cmd: 'story.flow.validate' }, { cmd: 'story.flow.play' }, { cmd: 'story.flow.fit' }]) }}>
        <Background gap={24} />
        <MiniMap pannable zoomable />
        <Controls showInteractive={false} />
        <FitBridge />
      </ReactFlow>
    </div>
  )
}
