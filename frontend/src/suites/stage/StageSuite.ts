// P13 / ST1 (D81): the Stage suite's registration — three.js on its own WebGL2 canvas, kept alive while hidden (D69); the parts live in
// StageParts.tsx. Loaded lazily by frame/suiteRegistry.tsx.
// D95 (AN1): Stage is Animate's Clay level — it shares Animate's column, foot and rail (frame/railTabs.sharedKeyOf); its own parts are the
// strip and the viewport.
import { DEFAULT_RAIL } from '../../frame/railTabs'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { AnimateColumn, AnimateFoot } from '../animate/AnimateSuite'
import { Stage, Strip } from './StageParts'

export const StageSuite: SuiteDef = {
  id: 'stage',
  rail: DEFAULT_RAIL.stage,
  Panel: AnimateColumn, Strip, Stage, Inspector: () => null, PrimaryAction: AnimateFoot, keepAlive: true, noInspector: true, panelTitle: 'Animate',
}
