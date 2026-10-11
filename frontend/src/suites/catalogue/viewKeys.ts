// D72: the loupe's and the compare view's own actions (zoom to fit, 1:1, swap), published while they are mounted so their registry
// commands — the keys a user can remap, and the buttons in their bars — reach them. A leaf module (the views and the commands import it).
export const catView: { fit?: () => void; one?: () => void; swap?: () => void } = {}
