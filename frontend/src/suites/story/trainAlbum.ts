// D122: which album the "Train a LoRA on this album…" sheet is open for (a leaf module: the Catalogue's page menus open it, the frame
// renders TrainAlbumSheet).
import { create } from 'zustand'

interface TrainAlbumState {
  album: { id: string; name: string } | null
  open: (id: string, name: string) => void
  close: () => void
}

export const useTrainAlbum = create<TrainAlbumState>()((set) => ({
  album: null,
  open: (id, name) => set({ album: { id, name } }),
  close: () => set({ album: null }),
}))
