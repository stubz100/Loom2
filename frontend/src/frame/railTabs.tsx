// Rail tab definitions per suite (07 §2). A leaf module: suites and the frame both import it, it imports neither.
import { Boxes, Cpu, Filter, FolderTree, Library, SlidersHorizontal, Upload, Wand2 } from 'lucide-react'
import type { ReactNode } from 'react'

export interface RailTab { id: string; label: string; key?: string; icon: ReactNode }

export const DEFAULT_RAIL: Record<string, RailTab[]> = {
  catalogue: [{ id: 'library', label: 'Library', icon: <Library size={18} /> }, { id: 'filters', label: 'Filters', icon: <Filter size={18} /> }, { id: 'collections', label: 'Collections', icon: <FolderTree size={18} /> }, { id: 'import', label: 'Import', icon: <Upload size={18} /> }],
  generate: [{ id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'params', label: 'Parameters', icon: <SlidersHorizontal size={18} /> }],
  edit: [{ id: 'tools', label: 'Tools', icon: <Wand2 size={18} /> }],
  animate: [{ id: 'inputs', label: 'Inputs', icon: <Boxes size={18} /> }],
  models: [{ id: 'roster', label: 'Roster', icon: <Boxes size={18} /> }, { id: 'engine', label: 'Engine', icon: <Cpu size={18} /> }],
}
