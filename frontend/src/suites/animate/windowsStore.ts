// D165: Performance's Windows view — the shot's final at a frame, each character's window (D163) and head box (D118) as keyframed boxes the
// author moves, resizes, keys, removes or gives back to the automatic rule before the GPU time is spent. The server's boxes (GET
// /finals/{fid}/boxes) are what the run will use; an edit is sent at once (PUT …/layers/{lid}/boxes) and the server's answer replaces them.
import { create } from 'zustand'
import { http, unwrap, type ApiError } from '../../api/client'
import type { Final, FinalBoxes, LayerBoxes } from '../../api/types'
import { useSession } from '../../store/session'
import { boxAt, removeAt, upsert, type Box, type BoxKey, type BoxKind } from './boxKeys'

export type BoxMode = 'auto' | 'keys' | 'none'
export interface BoxSel { lid: string; kind: BoxKind }

interface WindowsState {
  fid: string | null
  data: FinalBoxes | null
  frame: number
  sel: BoxSel | null
  skeletons: boolean
  busy: boolean
  load: (fid: string) => Promise<void>
  setFrame: (frame: number) => void
  select: (sel: BoxSel | null) => void
  /** The box as drawn at the current frame set as a key there (the automatic offer becomes the author's keys first). */
  place: (sel: BoxSel, box: Box) => Promise<void>
  keyHere: () => Promise<void>
  deleteKey: () => Promise<void>
  setMode: (sel: BoxSel, mode: 'auto' | 'none') => Promise<void>
  /** A box added by hand to a layer that has none: the automatic track's keys, then the author's. */
  add: (sel: BoxSel) => Promise<void>
}

/** A layer's track of one kind. */
export const trackOf = (l: LayerBoxes, kind: BoxKind) => (kind === 'window' ? l.window : l.head)
export const keysOf = (l: LayerBoxes, kind: BoxKind): BoxKey[] => trackOf(l, kind).keys as unknown as BoxKey[]
/** The box a layer shows at a frame: the server's frame as it will run. */
export function shownBox(l: LayerBoxes, kind: BoxKind, frame: number): Box | null {
  const fr = trackOf(l, kind).frames[frame]
  if (!fr) return null
  return { cx: fr[0] + fr[2] / 2, cy: fr[1] + fr[3] / 2, size: fr[3] }
}

const body = (kind: BoxKind, mode: BoxMode, keys: BoxKey[] = []) =>
  (kind === 'window' ? { window: mode, window_keys: keys } : { head: mode, head_keys: keys }) as never

export const useWindows = create<WindowsState>((set, get) => {
  const layer = (lid: string) => get().data?.layers.find((l) => l.id === lid) ?? null
  const put = async (lid: string, payload: never, what: string) => {
    const fid = get().fid
    if (!fid) return
    set({ busy: true })
    try { set({ data: await unwrap(http.PUT('/finals/{fid}/layers/{lid}/boxes', { params: { path: { fid, lid } }, body: payload })) }) }
    catch (e) { useSession.getState().toast(`${what}: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
    finally { set({ busy: false }) }
  }
  return {
    fid: null, data: null, frame: 0, sel: null, skeletons: true, busy: false,
    load: async (fid) => {
      try {
        const data = await unwrap(http.GET('/finals/{fid}/boxes', { params: { path: { fid } } }))
        const same = get().fid === fid
        set({ fid, data, frame: same ? Math.min(get().frame, Math.max(0, data.frames - 1)) : 0, sel: same ? get().sel : data.layers[0] ? { lid: data.layers[0].id, kind: 'window' } : null })
      } catch (e) { set({ fid, data: null }); useSession.getState().toast(`Windows: ${(e as ApiError).detail ?? (e as Error).message ?? e}`, 'error') }
    },
    setFrame: (frame) => { const n = get().data?.frames ?? 1; set({ frame: Math.max(0, Math.min(n - 1, Math.round(frame))) }) },
    select: (sel) => set({ sel }),
    place: async (sel, box) => {
      const l = layer(sel.lid)
      if (!l) return
      const t = trackOf(l, sel.kind)
      const from = t.mode === 'keys' ? keysOf(l, sel.kind) : (t.offer as unknown as BoxKey[])
      await put(sel.lid, body(sel.kind, 'keys', upsert(from, sel.kind, get().frame, box)), sel.kind === 'window' ? `${l.name}'s window` : `${l.name}'s head box`)
    },
    keyHere: async () => {
      const { sel, frame } = get()
      const l = sel ? layer(sel.lid) : null
      if (!sel || !l) return
      const b = shownBox(l, sel.kind, frame) ?? boxAt(keysOf(l, sel.kind), sel.kind, frame)
      if (b) await get().place(sel, b)
    },
    deleteKey: async () => {
      const { sel, frame } = get()
      const l = sel ? layer(sel.lid) : null
      if (!sel || !l || trackOf(l, sel.kind).mode !== 'keys') return
      const keys = removeAt(keysOf(l, sel.kind), frame)
      if (!keys.length) { useSession.getState().toast('The last key: use Back to automatic, or remove the box', 'info'); return }
      await put(sel.lid, body(sel.kind, 'keys', keys), `${l.name}: delete the key`)
    },
    setMode: async (sel, mode) => {
      const l = layer(sel.lid)
      if (l) await put(sel.lid, body(sel.kind, mode), `${l.name}: ${mode === 'auto' ? 'back to automatic' : sel.kind === 'window' ? 'no window' : 'no face work'}`)
    },
    add: async (sel) => {
      const l = layer(sel.lid)
      const offer = l ? (trackOf(l, sel.kind).offer as unknown as BoxKey[]) : []
      if (l && offer.length) await put(sel.lid, body(sel.kind, 'keys', offer), `${l.name}: add a ${sel.kind === 'window' ? 'window' : 'head box'}`)
    },
  }
})

/** Whether the layer's box of this kind has a key at the frame. */
export const keyAt = (l: LayerBoxes, kind: BoxKind, frame: number): boolean => trackOf(l, kind).mode === 'keys' && keysOf(l, kind).some((k) => k.frame === frame)

/** The shot's newest final for the open shot version, else the stage's newest. */
export function finalFor(finals: Final[], shotId: string | null | undefined, version: string | null | undefined): Final | null {
  const by = (xs: Final[]) => [...xs].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0] ?? null
  return by(finals.filter((f) => shotId && f.shot_id === shotId && (!f.shot_version || f.shot_version === version))) ?? by(finals)
}
