// Rail tab definitions per suite (07 §2). A leaf module: suites and the frame both import it, it imports neither.
import { Aperture, Bookmark, Boxes, Brush, Camera, Clapperboard, Clock, Cpu, Film, Files, GitBranch, Globe, Image as ImageIcon, Images, Lasso, ListTree, PersonStanding, Shapes, SlidersHorizontal, Sparkles, Users, Wand2 } from 'lucide-react'
import type { ReactNode } from 'react'

export interface RailTab { id: string; label: string; key?: string; icon: ReactNode }

export const DEFAULT_RAIL: Record<string, RailTab[]> = {
  catalogue: [{ id: 'places', label: 'Catalogue', icon: <Images size={18} /> }],   // D90: shown as Story's third workspace (STORY_RAIL)
  generate: [{ id: 'prompt', label: 'Prompt', icon: <Wand2 size={18} /> }, { id: 'params', label: 'Parameters', icon: <SlidersHorizontal size={18} /> }],
  // Edit and Animate load lazily (D69); their rails are here so the frame shows them (and ?suite=&tab= deep links resolve) before they load
  edit: [{ id: 'tools', label: 'Tool options', icon: <SlidersHorizontal size={18} /> }, { id: 'brushes', label: 'Brushes', icon: <Brush size={18} /> }, { id: 'selection', label: 'Selection', icon: <Lasso size={18} /> },
    { id: 'ai', label: 'AI', icon: <Sparkles size={18} /> }, { id: 'documents', label: 'Documents', icon: <Files size={18} /> }],
  animate: [{ id: 'inputs', label: 'Inputs', icon: <ImageIcon size={18} /> }, { id: 'model', label: 'Model', icon: <Boxes size={18} /> }, { id: 'length', label: 'Length & Size', icon: <Clock size={18} /> },
    { id: 'presets', label: 'Presets', icon: <Bookmark size={18} /> }, { id: 'clips', label: 'Clips', icon: <Film size={18} /> }],   // P17's Sequence tab moved to Story · Episode (17 SY4, D85)
  models: [{ id: 'roster', label: 'Roster', icon: <Boxes size={18} /> }, { id: 'engine', label: 'Engine', icon: <Cpu size={18} /> }],
  // P13 / ST1 (D81): the Stage suite loads lazily like Edit; Poses came with ST2, Shot with ST3
  stage: [{ id: 'library', label: 'Library', icon: <Shapes size={18} /> }, { id: 'outliner', label: 'Outliner', icon: <ListTree size={18} /> }, { id: 'cameras', label: 'Cameras', icon: <Camera size={18} /> },
    { id: 'poses', label: 'Poses', icon: <PersonStanding size={18} /> }, { id: 'shot', label: 'Shot', icon: <Aperture size={18} /> }],
  // 17 (D85): the Story suite loads lazily; World came with SY0, Cast with SY1, Shots with SY2, Flow with SY3; Episode comes with SY4
  story: [{ id: 'world', label: 'World', icon: <Globe size={18} /> }, { id: 'cast', label: 'Cast', icon: <Users size={18} /> }, { id: 'shots', label: 'Shots', icon: <Clapperboard size={18} /> },
    { id: 'flow', label: 'Flow', icon: <GitBranch size={18} /> }, { id: 'episode', label: 'Episode', icon: <Film size={18} /> }],   // SY4: the single-lane timeline (P17, D83) lives here now
}

/** D90 (02 §3): a top-bar tab and the suites it shows. Story holds the Catalogue as its third workspace; the Catalogue stays a suite of its
 *  own underneath (its scope, keys, deep links and wide strip are unchanged), so the tab group is purely a matter of placement. */
export interface TopTab { id: string; label: string; key: string; suites: string[] }
export const TOP_TABS: TopTab[] = [
  { id: 'story', label: 'Story', key: '1', suites: ['story', 'catalogue'] }, { id: 'generate', label: 'Generate', key: '2', suites: ['generate'] },
  { id: 'edit', label: 'Edit', key: '3', suites: ['edit'] }, { id: 'animate', label: 'Animate', key: '4', suites: ['animate'] },
  { id: 'stage', label: 'Stage', key: '5', suites: ['stage'] },
]
export const topTabOf = (suite: string): TopTab | undefined => TOP_TABS.find((t) => t.suites.includes(suite))

/** A rail button and the suite whose tab it opens (the Story tab's rail spans two suites). */
export interface GroupRailTab extends RailTab { suite: string }
const story = (id: string) => ({ ...DEFAULT_RAIL.story.find((t) => t.id === id)!, suite: 'story' })
/** D90 (02 §3, R5): World · Cast · Catalogue · Shots · Flow · Episode — the Catalogue after Cast, as the author asked. */
export const STORY_RAIL: GroupRailTab[] = [story('world'), story('cast'), { ...DEFAULT_RAIL.catalogue[0], suite: 'catalogue' }, story('shots'), story('flow'), story('episode')]
