// Rail tab definitions per suite (07 §2). A leaf module: suites and the frame both import it, it imports neither.
import { Aperture, Boxes, Brush, Camera, Clapperboard, Cpu, Film, Files, GitBranch, Globe, Images, Lasso, Layers, MonitorPlay, Package, PersonStanding, Shapes, SlidersHorizontal, Sparkles, Users, Wand2 } from 'lucide-react'
import type { ReactNode } from 'react'

export interface RailTab { id: string; label: string; key?: string; icon: ReactNode }

/** D121: the Animate tab's three levels — Clay (stage), Performance (animate), Final (final) — are modes, each with its own rail and
 *  column; they keep one panel width between them (the width is the tab's, not the level's). */
export const ANIMATE_LEVELS = ['stage', 'animate', 'final'] as const
export const widthKeyOf = (suite: string): string => ((ANIMATE_LEVELS as readonly string[]).includes(suite) ? 'animate' : suite)

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
  catalogue: [{ id: 'places', label: 'Catalogue', icon: <Images size={18} /> }],   // D90: shown as Story's third workspace (STORY_RAIL)
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
  // 17 (D85): the Story suite loads lazily; World came with SY0, Cast with SY1, Shots with SY2, Flow with SY3; Episode comes with SY4
  story: [{ id: 'world', label: 'World', icon: <Globe size={18} /> }, { id: 'cast', label: 'Cast', icon: <Users size={18} /> }, { id: 'props', label: 'Props', icon: <Package size={18} /> }, { id: 'shots', label: 'Shots', icon: <Clapperboard size={18} /> },
    { id: 'flow', label: 'Flow', icon: <GitBranch size={18} /> }, { id: 'episode', label: 'Episode', icon: <Film size={18} /> }],   // SY4: the single-lane timeline (P17, D83) lives here now
}

/** D90 (02 §3): a top-bar tab and the suites it shows. Story holds the Catalogue as its third workspace; the Catalogue stays a suite of its
 *  own underneath (its scope, keys, deep links and wide strip are unchanged), so the tab group is purely a matter of placement.
 *  D95 (IM1): Image holds Generate and Edit the same way, as its two modes Make and Edit (proto01_animate 03 §3); (AN1) Animate holds the
 *  animate and stage suites as its viewer levels, Performance and Clay (03 §4.1), and (D121) the final suite as its Final level. */
export interface TopTab { id: string; label: string; key: string; suites: string[] }
export const TOP_TABS: TopTab[] = [
  { id: 'story', label: 'Story', key: '1', suites: ['story', 'catalogue'] }, { id: 'image', label: 'Image', key: '2', suites: ['generate', 'edit'] },
  { id: 'animate', label: 'Animate', key: '3', suites: ['animate', 'stage', 'final'] },   // D121: Performance, Clay, Final
]
export const topTabOf = (suite: string): TopTab | undefined => TOP_TABS.find((t) => t.suites.includes(suite))

/** A rail button and the suite whose tab it opens (the Story tab's rail spans two suites). */
export interface GroupRailTab extends RailTab { suite: string }
const story = (id: string) => ({ ...DEFAULT_RAIL.story.find((t) => t.id === id)!, suite: 'story' })
/** D90 (02 §3, R5): World · Cast · Props · Catalogue · Shots · Flow · Episode — the Catalogue after Cast, as the author asked; D110 (PS1):
 *  Props beside Cast, a prop made like a character (images first, then its 3D model). */
export const STORY_RAIL: GroupRailTab[] = [story('world'), story('cast'), story('props'), { ...DEFAULT_RAIL.catalogue[0], suite: 'catalogue' }, story('shots'), story('flow'), story('episode')]
