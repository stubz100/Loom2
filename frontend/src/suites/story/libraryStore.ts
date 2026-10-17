// D92 (wave UI7): the project's Story · World library — every preset of Generate's prompt fields is an entry (`story/library.json`:
// {id, field, name, text}, seeded per project by the server from the built-in vocabulary and the app-wide presets). World writes an
// entry (its Inspector is the only place the name and the words are edited); Generate's tiles read the library and its field's + adds to
// it. Every change carries the revision the client holds and runs one after another (409 → reload, said); a typed name or words show at
// once and save after a pause. A look entry gets its picture by itself (swatches.ts `autoPicture`) when it is added or re-worded.
import { create } from 'zustand'
import { type ApiError, http, unwrap } from '../../api/client'
import type { Library, LibraryEntry } from '../../api/types'
import type { PresetIcon } from '../../frame/PresetIcons'
import { fieldGlyph, glyphFor } from '../../frame/presetGlyphs'
import { useSession } from '../../store/session'
import { needsPicture, useSwatches } from '../generate/swatches'

type Entry = Pick<LibraryEntry, 'id' | 'field' | 'name' | 'text'>

/** One entry as a tile: its own drawing (geometry, a built-in negative), else its picture (a look), else its field's glyph — with a busy
 *  mark while the picture is being made. Never letters (D92). The name is the label; the words are the hint when they differ. */
export function entryTile(e: Entry, url: (field: string, value: string) => string | null, busy: (field: string, value: string) => boolean): PresetIcon & { text: string } {
  const own = glyphFor(e.field, e.text)
  const pic = !own && needsPicture(e.field, e.text)
  const img = pic ? url(e.field, e.text) : null
  return { id: e.id, label: e.name, text: e.text, icon: own ?? fieldGlyph(e.field), img, busy: pic && !img && busy(e.field, e.text), hint: e.name.trim() !== e.text.trim() ? e.text : undefined }
}

/** A field's entries in the library's order. */
export const entriesOf = (lib: Pick<Library, 'entries'> | null | undefined, field: string): LibraryEntry[] => (lib?.entries ?? []).filter((e) => e.field === field)

/** The whole list's ids after moving one entry earlier (-1) or later (+1) among its field's entries; null at an end. */
export function moveWithinField(entries: Entry[], id: string, delta: -1 | 1): string[] | null {
  const e = entries.find((x) => x.id === id)
  if (!e) return null
  const same = entries.flatMap((x, i) => (x.field === e.field ? [i] : []))
  const k = same.findIndex((i) => entries[i].id === id), j = k + delta
  if (j < 0 || j >= same.length) return null
  const ids = entries.map((x) => x.id)
  ;[ids[same[k]], ids[same[j]]] = [ids[same[j]], ids[same[k]]]
  return ids
}

/** D92 (owed): the whole list's ids after dragging one entry before / after another of its field (World › Library's drag); null when the
 *  target is in another field, is the entry itself, or the order would not change. The other fields' entries keep their places. */
export function moveToInField(entries: Entry[], id: string, targetId: string, where: 'before' | 'after'): string[] | null {
  const e = entries.find((x) => x.id === id), t = entries.find((x) => x.id === targetId)
  if (!e || !t || e.field !== t.field || id === targetId) return null
  const slots = entries.flatMap((x, i) => (x.field === e.field ? [i] : []))       // the field's places in the whole list, kept
  const order = slots.map((i) => entries[i].id).filter((x) => x !== id)
  order.splice(order.indexOf(targetId) + (where === 'after' ? 1 : 0), 0, id)
  const ids = entries.map((x) => x.id)
  slots.forEach((i, k) => { ids[i] = order[k] })
  return ids.every((x, i) => x === entries[i].id) ? null : ids
}

interface LibraryState {
  library: Library | null
  loading: boolean
  load: () => Promise<void>
  /** A new entry at the end of its field (the name is the words when empty); its picture is queued when it is a look. */
  add: (field: string, text: string, name?: string) => Promise<LibraryEntry | null>
  /** The name and / or words as typed: shown at once, saved after a pause (blank values are not sent). */
  edit: (id: string, patch: { name?: string; text?: string }) => void
  flush: () => Promise<void>
  /** Out of the library; the toast's Undo puts it back with its id and place. */
  remove: (id: string) => Promise<void>
  move: (id: string, delta: -1 | 1) => Promise<void>
  /** D92 (owed): a drag within the field's row — before / after another entry (`PUT /story/library/order`, the same as Move earlier / later). */
  moveTo: (id: string, targetId: string, where: 'before' | 'after') => Promise<void>
  /** `story.changed` {kind: library}: another writer moved it — reload when nothing of ours is pending. */
  onChanged: (revision?: number) => void
}

const toast = (text: string, kind: 'error' | 'info' = 'error', action?: () => void) => useSession.getState().toast(text, kind, action)
const detail = (e: unknown) => (e as ApiError).detail ?? String(e)
let chain: Promise<unknown> = Promise.resolve()
let pending: Record<string, { name?: string; text?: string }> = {}
let timer: number | null = null
let inflight = 0

export const useLibrary = create<LibraryState>()((set, get) => {
  /** What the server returned, with the names / words typed since still showing (they save next). */
  const overlay = (lib: Library): Library => ({ ...lib, entries: lib.entries.map((e) => (pending[e.id] ? { ...e, ...pending[e.id] } : e)) })
  /** One change at a time, each with the revision the last one returned; a 409 reloads and says so. */
  const run = <T>(what: string, fn: (rev: number) => Promise<T>): Promise<T | null> => {
    const p = chain.then(async () => {
      inflight += 1
      try { return await fn(get().library?.revision ?? 0) } catch (e) {
        if ((e as ApiError).status === 409) { toast('The library changed elsewhere — reloaded; your last change was not saved'); await get().load() }
        else toast(`${what}: ${detail(e)}`)
        return null
      } finally { inflight -= 1 }
    })
    chain = p.catch(() => null)
    return p
  }
  const savePending = () => {
    const todo = pending
    pending = {}
    for (const [id, body] of Object.entries(todo)) {
      const send = Object.fromEntries(Object.entries(body).filter(([, v]) => typeof v === 'string' && v.trim()))
      if (!Object.keys(send).length) continue
      void run('Library entry not saved', async (revision) => {
        const r = await unwrap(http.PATCH('/story/library/entries/{eid}', { params: { path: { eid: id } }, body: { revision, ...send } as never }))
        set({ library: overlay(r.library) })
        if (send.text) void useSwatches.getState().autoPicture(r.entry.field, r.entry.text)   // new words: their picture, when a look
      })
    }
  }
  return {
    library: null, loading: false,
    load: async () => {
      set({ loading: true })
      try { set({ library: overlay(await unwrap(http.GET('/story/library'))) }) }
      catch (e) { if ((e as ApiError).status !== 409) toast(`Library: ${detail(e)}`); set({ library: null }) }
      finally { set({ loading: false }) }
    },
    add: async (field, text, name = '') => {
      const send = (revision: number) => unwrap(http.POST('/story/library/entries', { body: { field, text: text.trim(), name: name.trim(), revision } }))
      const r = await run('Not added to the library', send)
      if (!r) return null
      set({ library: overlay(r.library) })
      void useSwatches.getState().autoPicture(r.entry.field, r.entry.text)
      return r.entry
    },
    edit: (id, patch) => {
      const lib = get().library
      if (!lib) return
      set({ library: { ...lib, entries: lib.entries.map((e) => (e.id === id ? { ...e, ...patch } : e)) } })
      pending[id] = { ...pending[id], ...patch }
      if (timer) window.clearTimeout(timer)
      timer = window.setTimeout(() => { timer = null; savePending() }, 400)
    },
    flush: async () => { if (timer) { window.clearTimeout(timer); timer = null; savePending() } await chain },
    remove: async (id) => {
      await get().flush()
      const r = await run('Not removed', (revision) => unwrap(http.DELETE('/story/library/entries/{eid}', { params: { path: { eid: id }, query: { revision } } })))
      if (!r) return
      set({ library: overlay(r.library) })
      const e = r.entry
      toast(`Removed “${e.name}” from the library`, 'info', () => void run('Not put back', async (revision) => {
        const back = await unwrap(http.POST('/story/library/entries', { body: { field: e.field, text: e.text, name: e.name, id: e.id, at: r.index, revision } }))
        set({ library: overlay(back.library) })
      }))
    },
    move: async (id, delta) => {
      await get().flush()
      const ids = moveWithinField(get().library?.entries ?? [], id, delta)
      if (!ids) return
      const r = await run('Not moved', (revision) => unwrap(http.PUT('/story/library/order', { body: { ids, revision } })))
      if (r) set({ library: overlay(r) })
    },
    moveTo: async (id, targetId, where) => {
      await get().flush()
      const ids = moveToInField(get().library?.entries ?? [], id, targetId, where)
      if (!ids) return
      const lib = get().library!
      const byId = new Map(lib.entries.map((e) => [e.id, e]))
      set({ library: { ...lib, entries: ids.map((x) => byId.get(x)!) } })            // the row shows the new order at once
      const r = await run('Not moved', (revision) => unwrap(http.PUT('/story/library/order', { body: { ids, revision } })))
      if (r) set({ library: overlay(r) }); else void get().load()
    },
    onChanged: (revision) => {
      const lib = get().library
      if (!lib || timer !== null || inflight > 0 || Object.keys(pending).length) return
      if (revision !== undefined && revision <= lib.revision) return
      void get().load()
    },
  }
})
