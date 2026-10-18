// D95 (IM1): whether Edit has a document open, for the frame (the Image tab's drop verb) without importing the lazy editor (D69).
// A leaf module: the editor store writes it on every document change, the frame reads it.
export const editPresence = { hasDoc: false }
