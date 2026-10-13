// P13 / ST1 (D81): the Stage suite's registration — three.js on its own WebGL2 canvas, kept alive while hidden (D69); the parts live in
// StageParts.tsx. Loaded lazily by frame/suiteRegistry.tsx.
import { DEFAULT_RAIL } from '../../frame/railTabs'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { Inspector, Panel, PrimaryAction, Stage, Strip } from './StageParts'

export const StageSuite: SuiteDef = {
  id: 'stage',
  rail: DEFAULT_RAIL.stage,
  Panel, Strip, Stage, Inspector, PrimaryAction, keepAlive: true,
}
