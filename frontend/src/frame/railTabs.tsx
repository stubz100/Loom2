// Rail tab definitions per suite (07 §2): the sections of each suite's column, which its parts and the router read (B2, D159: the old
// frame's rail is gone). A leaf module: it imports no suite.
import { Aperture, Boxes, Brush, Camera, Clapperboard, Cpu, Film, Files, GitBranch, Globe, Lasso, Layers, MonitorPlay, PersonStanding, Shapes, SlidersHorizontal, Sparkles, Users, Wand2 } from 'lucide-react'
import type { ReactNode } from 'react'

export interface RailTab { id: string; label: string; key?: string; icon: ReactNode }

// D121 (proto01_animate 26 §5): each level's column — Clay composes the scene and its motion, Performance makes the moving picture,
// Final finishes the composition; the Shot section heads all three
const shot: RailTab = { id: 'shot', label: 'Shot', icon: <Clapperboard size={18} /> }
const CLAY_RAIL: RailTab[] = [shot, { id: 'scene', label: 'Scene', icon: <Shapes size={18} /> },
  { id: 'motion', label: 'Motion', icon: <PersonStanding size={18} /> }, { id: 'camera', label: 'Camera', icon: <Camera size={18} /> }]
const PERFORMANCE_RAIL: RailTab[] = [shot, { id: 'performance', label: 'Performance', icon: <Aperture size={18} /> },
  { id: 'clips', label: 'Clips', icon: <Film size={18} /> }]   // AW3: a clip's details under its row, as a layer's at Final and a thing's at Clay
const FINAL_RAIL: RailTab[] = [shot, { id: 'layers', label: 'Layers', icon: <Layers size={18} /> },   // AE2–3: the selected layer's editor under its row (UX9 U1)
  { id: 'output', label: 'Output', icon: <MonitorPlay size={18} /> }]

export const DEFAULT_RAIL: Record<string, RailTab[]> = {
  generate: [{ id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'params', label: 'Parameters', icon: <SlidersHorizontal size={18} /> },
    { id: 'poses', label: 'Poses', icon: <PersonStanding size={18} /> }],   // D115: the poses Expand runs
  // Edit and Animate load lazily (D69); their rails are here so the frame shows them (and ?suite=&tab= deep links resolve) before they load
  edit: [{ id: 'tools', label: 'Tool options', icon: <SlidersHorizontal size={18} /> }, { id: 'brushes', label: 'Brushes', icon: <Brush size={18} /> }, { id: 'selection', label: 'Selection', icon: <Lasso size={18} /> },
    { id: 'ai', label: 'AI', icon: <Sparkles size={18} /> }, { id: 'documents', label: 'Documents', icon: <Files size={18} /> }],
  animate: PERFORMANCE_RAIL,                                                                               // D121: Animate's Performance level
  models: [{ id: 'roster', label: 'Roster', icon: <Boxes size={18} /> }, { id: 'engine', label: 'Engine', icon: <Cpu size={18} /> }],
  // P13 / ST1 (D81): the Stage suite loads lazily like Edit; Poses came with ST2, Shot with ST3
  stage: CLAY_RAIL,                                                                                        // D95 (AN1) → D121: Animate's Clay level
  final: FINAL_RAIL,                                                                                       // D121: Animate's Final level (the composition)
  // 17 (D85): the Story suite loads lazily. D125: its rail is the order of the work — World · Cast · Flow · Shots · Episode; Props are a
  // class of Cast (D110's own tab folded back), the Catalogue a top tab of its own
  story: [{ id: 'world', label: 'World', icon: <Globe size={18} /> }, { id: 'cast', label: 'Cast', icon: <Users size={18} /> }, { id: 'flow', label: 'Flow', icon: <GitBranch size={18} /> },
    { id: 'shots', label: 'Shots', icon: <Clapperboard size={18} /> }, { id: 'episode', label: 'Episode', icon: <Film size={18} /> }],   // SY4: the single-lane timeline (P17, D83) lives here
}
