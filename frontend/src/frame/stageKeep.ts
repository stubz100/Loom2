// D69 (ArtCraft P5): whether the stage a component lives in is the one on screen. The old frame kept heavy stages mounted while hidden and
// said so through this context; B2 (D159): the shell's layers unmount what they do not show, so it is always true unless a host says
// otherwise (the editor's canvas and the player read it before resizing).
import { createContext, useContext } from 'react'

/** Whether the Stage this component lives in is the one on screen. */
export const StageActive = createContext(true)
export const useStageActive = () => useContext(StageActive)
