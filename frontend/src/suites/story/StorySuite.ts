// 17 (D85): the Story suite's registration — the parts live in StoryParts.tsx; loaded lazily by frame/suiteRegistry.tsx (D69). No GPU
// stage, so nothing is kept alive while hidden.
import { DEFAULT_RAIL } from '../../frame/railTabs'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { Inspector, Panel, PrimaryAction, Stage, Strip } from './StoryParts'
import './episode/sequenceCommands'                     // SY4: the lane's verbs register with the Story suite

export const StorySuite: SuiteDef = {
  id: 'story',
  rail: DEFAULT_RAIL.story,
  Panel, Strip, Stage, Inspector, PrimaryAction,
}
