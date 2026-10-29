// B2 (D159): the parts a suite's code gives the shell's layers — its column, strip, viewer, inspector and foot. The old frame's SuiteDef
// without its rail and flags: the layers place the parts themselves (ui2/shots/ShotsLayer.tsx, ui2/world/WorldEdit.tsx).
import type { ComponentType } from 'react'

export interface SuiteParts {
  Panel: ComponentType<{ tab: string }>
  Strip: ComponentType
  Stage: ComponentType
  Inspector: ComponentType
  PrimaryAction?: ComponentType
}
