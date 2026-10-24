// RC1 (D96, proto01_animate 28; UX0 W6, C4): a shot version's recipe as a graph on @xyflow/react — one card per thing the shot is made of
// (its picture, its state, a short line), the edges where a step reads another, in columns from the characters to the take. The server
// builds it from the records (GET /story/shots/{sid}/graph); a story.changed for the shot (recipeTick) or a job starting or ending
// fetches it again, ↻ after edits elsewhere (a stage, a Cast sheet). A click picks a node — the caller opens it where it is made.
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api, http, unwrap, type ApiError } from '../../../api/client'
import { useSession } from '../../../store/session'
import { useRecipeTick } from '../recipeTick'
import { layout, NODE_H, NODE_W, STATE_LABEL, type GraphNode, type ShotGraph } from './graph'
import './recipe.css'

type CardT = Node<{ n: GraphNode; picked: boolean }, 'recipe'>

function Card({ data }: NodeProps<CardT>) {
  const n = data.n
  return (
    <div className={`recipe-node ${n.state}${data.picked ? ' picked' : ''}`} data-id={n.id} data-kind={n.kind} style={{ width: NODE_W, height: NODE_H }}
      title={[`${n.label}${n.sub ? ` · ${n.sub}` : ''}`, ...n.reasons].join('\n')}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="head"><span className="lbl">{n.label}</span><span className={`badge ${n.state}`}>{STATE_LABEL[n.state]}</span></div>
      <div className="pic">{n.thumb ? <img src={api.thumbUrl(n.thumb, 256)} alt="" draggable={false} /> : <span className="ph">{n.kind.replace('_', ' ')}</span>}</div>
      <div className="sub">{n.reasons[0] ?? n.sub ?? ''}</div>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
}
const nodeTypes = { recipe: Card }

/** The graph of a shot version; `onLoad` hands the record to the caller (its strip shows the counts). */
export function RecipeGraph({ shotId, version, picked, onPick, onLoad }: { shotId: string; version: string; picked?: string | null; onPick?: (n: GraphNode, g: ShotGraph) => void; onLoad?: (g: ShotGraph | null) => void }) {
  const tick = useRecipeTick((s) => s.tick[shotId] ?? 0)
  const active = useSession((s) => Object.values(s.jobs).filter((j) => j.status === 'queued' || j.status === 'running').map((j) => j.id).sort().join(','))
  const [g, setG] = useState<ShotGraph | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [again, setAgain] = useState(0)
  useEffect(() => {
    let live = true
    void unwrap(http.GET('/story/shots/{sid}/graph', { params: { path: { sid: shotId }, query: { version } } }))
      .then((x) => { if (live) { setG(x); setErr(null); onLoad?.(x) } })
      .catch((e) => { if (live) { setG(null); setErr((e as ApiError).detail ?? String(e)); onLoad?.(null) } })
    return () => { live = false }
  }, [shotId, version, tick, active, again])   // eslint-disable-line react-hooks/exhaustive-deps
  const { nodes, edges } = useMemo(() => {
    if (!g) return { nodes: [] as CardT[], edges: [] as Edge[] }
    const at = layout(g)
    const state = Object.fromEntries(g.nodes.map((n) => [n.id, n.state]))
    return {
      nodes: g.nodes.map((n) => ({ id: n.id, type: 'recipe' as const, position: { x: at[n.id].x, y: at[n.id].y }, data: { n, picked: picked === n.id }, draggable: false, connectable: false })),
      edges: g.edges.map((e) => ({ id: `${e.from}>${e.to}`, source: e.from, target: e.to, type: 'smoothstep', className: state[e.to] === 'stale' && state[e.from] === 'stale' ? 'stale' : '', animated: state[e.to] === 'running' })),
    }
  }, [g, picked])
  if (err) return <div className="recipe-graph empty"><span className="hint">The recipe could not be read: {err}</span></div>
  if (!g) return <div className="recipe-graph empty"><span className="hint">Reading the recipe…</span></div>
  return (
    <div className="recipe-graph" data-testid="recipe-graph">
      <ReactFlow<CardT, Edge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.15} maxZoom={1.6} nodesDraggable={false} nodesConnectable={false}
        deleteKeyCode={null} proOptions={{ hideAttribution: true }} onNodeClick={(_e, x) => onPick?.(x.data.n, g)}>
        <Background gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
      <button type="button" className="quiet recipe-again" title="Read the recipe again (after an edit elsewhere: a stage, a Cast sheet)" aria-label="read the recipe again" onClick={() => setAgain((k) => k + 1)}><RefreshCw size={14} /></button>
    </div>
  )
}
