// 17 §3d (D85): play mode's walker — pure. From the Start it follows the edges: a Dialogue or Shot node stops and waits for *next*, a
// Choice waits for an option (whose `require` reads the variables and whose `set` writes them), a Condition takes *then* or *else*, an
// Action sets variables, a Hub passes through, a Jump goes to its target; no edge out = the end. No model is ever invoked (loom R143):
// authored content or nothing. The variables start at the World's defaults.
import type { FlowGraph, FlowNode, FlowOption, StoryVariable } from '../../../api/types'

export type Vars = Record<string, boolean | string>
export interface PlayState { node: string | null; vars: Vars; trail: string[]; ended: boolean; waiting: 'next' | 'choice' | null; steps: number }

const MAX_STEPS = 1000

export function defaultVars(variables: StoryVariable[]): Vars {
  const out: Vars = {}
  for (const v of variables) out[v.name] = v.default
  return out
}

export function edgeFrom(graph: FlowGraph, from: string, port: string): string | null {
  return graph.edges.find((e) => e.from === from && e.port === port)?.to ?? null
}

/** The options a Choice offers now: those whose requirement holds (an option without one always shows). */
export function optionsAvailable(node: FlowNode, vars: Vars): FlowOption[] {
  return node.options.filter((o) => !o.require || !o.require.var || String(vars[String(o.require.var)]) === String(o.require.value))
}

export function applySets(vars: Vars, sets: Record<string, unknown>[]): Vars {
  const out = { ...vars }
  for (const s of sets) if (typeof s.var === 'string' && s.var) out[s.var] = (typeof s.value === 'boolean' ? s.value : String(s.value ?? ''))
  return out
}

function holds(node: FlowNode, vars: Vars): boolean {
  const c = node.cond
  if (!c || !c.var) return false
  const eq = String(vars[c.var]) === String(c.value)
  return c.op === 'ne' ? !eq : eq
}

/** Walk from `at` until a node that waits (Dialogue, Shot, Choice) or the end; Comments and gone nodes end the walk. */
function settle(state: PlayState, graph: FlowGraph, nodes: Record<string, FlowNode>, at: string | null): PlayState {
  let cur = at
  let vars = state.vars
  const trail = [...state.trail]
  let steps = state.steps
  while (cur) {
    const n = nodes[cur]
    if (!n || steps++ > MAX_STEPS) return { node: null, vars, trail, ended: true, waiting: null, steps }
    trail.push(cur)
    if (n.type === 'dialogue' || n.type === 'shot') return { node: cur, vars, trail, ended: false, waiting: 'next', steps }
    if (n.type === 'choice') return { node: cur, vars, trail, ended: false, waiting: 'choice', steps }
    if (n.type === 'comment') return { node: null, vars, trail, ended: true, waiting: null, steps }
    if (n.type === 'jump') { cur = n.target && nodes[n.target] ? n.target : null; continue }
    if (n.type === 'condition') { cur = edgeFrom(graph, cur, holds(n, vars) ? 'then' : 'else'); continue }
    if (n.type === 'action') vars = applySets(vars, n.set)
    cur = edgeFrom(graph, cur, 'out')                               // start · hub · action
  }
  return { node: null, vars, trail, ended: true, waiting: null, steps }
}

export function startPlay(graph: FlowGraph, nodes: Record<string, FlowNode>, variables: StoryVariable[]): PlayState {
  const init: PlayState = { node: null, vars: defaultVars(variables), trail: [], ended: false, waiting: null, steps: 0 }
  if (!graph.start || !nodes[graph.start]) return { ...init, ended: true }
  return settle(init, graph, nodes, graph.start)
}

/** From a waiting node: *next* follows `out`; a Choice takes the option (its sets applied) and follows `opt:<id>`. */
export function stepPlay(state: PlayState, graph: FlowGraph, nodes: Record<string, FlowNode>, option?: string): PlayState {
  if (state.ended || !state.node) return state
  const n = nodes[state.node]
  if (!n) return { ...state, ended: true, node: null, waiting: null }
  if (n.type === 'choice') {
    const o = n.options.find((x) => x.id === option)
    if (!o || !optionsAvailable(n, state.vars).some((x) => x.id === o.id)) return state
    const vars = applySets(state.vars, o.set)
    return settle({ ...state, vars }, graph, nodes, edgeFrom(graph, n.id, `opt:${o.id}`))
  }
  return settle(state, graph, nodes, edgeFrom(graph, n.id, 'out'))
}
