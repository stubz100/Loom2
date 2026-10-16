// D90 (01 §11.2, 02 §8.3): Models & engine's actions are commands in the `models` scope — the sheet's buttons render them, the roster rows
// have a right-click with them, ⌘K / Help / Settings › Keyboard list them, and their keys work while the sheet has the focus
// (frame/ModelsSheet.tsx dispatches them: a modal owns its keys). Registered eagerly (the sheet's frame module imports this file) so the
// palette and Settings › Keyboard see them before the sheet's body has loaded; no heavy imports here.
import { Download, FolderSearch, HardDriveDownload, Play, RefreshCw, RotateCcw, ShieldCheck, Square, Zap } from 'lucide-react'
import { create } from 'zustand'
import type { ModelEntry } from '../../api/types'
import { registerCommands, sep, type MenuItem } from '../../frame/commands'
import { revealPath } from '../../shell/tauri'
import { useSession } from '../../store/session'

interface ModelsUi {
  family: string; showRetired: boolean; search: string; missingOnly: boolean
  /** The last Verify sha256 result, for the entry it was run on. */
  verify: { id: string; text: string } | null
  set: (p: Partial<ModelsUi>) => void
}
export const useModelsUi = create<ModelsUi>()((set) => ({ family: 'all', showRetired: false, search: '', missingOnly: false, verify: null, set: (p) => set(p) }))

const s = () => useSession.getState()
const FETCHING = ['queued', 'downloading', 'hashing']
/** A roster entry that a Fetch can bring: not on disk, with a source, not retired. */
export const fetchable = (m: ModelEntry): boolean => m.health !== 'present' && m.health !== 'verified' && !!m.repo && !m.retired
const fetching = (id: string) => FETCHING.includes(s().fetches[id]?.status ?? '')
const selected = (): ModelEntry | undefined => s().models.find((m) => m.id === s().selectedModel)
/** The entries Fetch all missing would start (the missing ones not already fetching). */
const missingToFetch = () => s().models.filter((m) => fetchable(m) && !fetching(m.id))
const engine = () => s().engine

registerCommands([
  { id: 'models.rescan', scope: 'models', label: 'Rescan disk', icon: RefreshCw, keys: 'R', placement: ['strip'], hint: 'the roster\'s health from the files on disk', run: () => void s().scanModels() },
  { id: 'models.fetchAll', scope: 'models', label: 'Fetch all missing', icon: HardDriveDownload, keys: 'Shift+F', placement: ['strip'], when: () => missingToFetch().length > 0,
    run: () => { for (const m of missingToFetch()) void s().fetchModel(m.id) } },
  { id: 'models.fetch', scope: 'models', label: 'Fetch', icon: Download, keys: 'F', placement: ['inspector', 'context'], hint: 'the selected roster entry', when: () => { const m = selected(); return !!m && fetchable(m) && !fetching(m.id) },
    run: () => { const m = selected(); if (m) void s().fetchModel(m.id) } },
  { id: 'models.verify', scope: 'models', label: 'Verify sha256', icon: ShieldCheck, keys: 'V', placement: ['inspector', 'context'], hint: 'hashes the selected file and compares it with the ledger', when: () => !!selected()?.path,
    run: () => { const m = selected(); if (!m) return
      void s().verifyModel(m.id).then((r) => useModelsUi.getState().set({ verify: { id: m.id, text: `${r.sha256.slice(0, 16)}… ${r.matches_ledger === null ? '(no ledger entry)' : r.matches_ledger ? 'matches the ledger' : 'DIFFERS from the ledger'}` } }),
        (e: unknown) => s().toast(`Verify failed: ${(e as { detail?: string }).detail ?? e}`, 'error')) } },
  { id: 'models.reveal', scope: 'models', label: 'Reveal in folder', icon: FolderSearch, keys: 'Ctrl+Shift+R', placement: ['inspector', 'context'], when: () => !!selected()?.path, run: () => { const m = selected(); if (m?.path) void revealPath(m.path) } },
  // the engine (the sheet's Engine tab)
  { id: 'models.engine.start', scope: 'models', label: 'Start the engine', icon: Play, placement: ['panel'], when: () => !engine()?.running, run: () => void s().engineAction('start') },
  { id: 'models.engine.stop', scope: 'models', label: 'Stop the engine', icon: Square, placement: ['panel'], when: () => !!engine()?.running, run: () => void s().engineAction('stop') },
  { id: 'models.engine.restart', scope: 'models', label: 'Restart the engine', icon: RotateCcw, placement: ['panel'], run: () => void s().engineAction('restart') },
  { id: 'models.engine.free', scope: 'models', label: 'Free VRAM', icon: Zap, placement: ['panel'], hint: 'unloads the models; the engine keeps running', when: () => !!engine()?.running, run: () => void s().engineAction('free') },
])

/** Right-click on a roster row (selected by the caller first). */
export const rowMenu = (): MenuItem[] => [{ cmd: 'models.fetch' }, { cmd: 'models.verify' }, { cmd: 'models.reveal' }, sep, { cmd: 'models.rescan' }, { cmd: 'models.fetchAll' }]
