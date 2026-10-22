// P13 / ST1 (D81): the Stage suite's registration — three.js on its own WebGL2 canvas, kept alive while hidden (D69); the parts live in
// StageParts.tsx. Loaded lazily by frame/suiteRegistry.tsx.
// D95 (AN1) → D121: Stage is Animate's Clay level, a mode of its own — its column (Shot · Scene · Motion · Camera), its strip, the viewport
// and its foot (Render passes ▶); Performance and Final are the animate and final suites beside it under the Animate tab.
import { DEFAULT_RAIL } from '../../frame/railTabs'
import type { SuiteDef } from '../../frame/suiteRegistry'
import { ClayColumn, ClayFoot, Stage, Strip } from './StageParts'

export const StageSuite: SuiteDef = {
  id: 'stage',
  rail: DEFAULT_RAIL.stage,
  Panel: ClayColumn, Strip, Stage, Inspector: () => null, PrimaryAction: ClayFoot, keepAlive: true, noInspector: true, panelTitle: 'Animate',
}
