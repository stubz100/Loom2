// D90 (02 §4.1): the style picker every maker uses (Generate's Style section, Cast's Expand, Stage's Shot) — a strip of sample tiles:
// "default" (the world's ★ style, followed as it changes), "none", then every style with ★ on the default. A style is only *picked* here;
// its name and fragment show as the tooltip and the accessible label, and it is written in Story · World alone. Value semantics as
// Generate's `panel.style_id`: undefined = the world's default, null = none, a string = that style.
import { Ban } from 'lucide-react'
import { useEffect } from 'react'
import { api } from '../../api/client'
import { CommandButton } from '../../frame/CommandButton'
import { showMenu } from '../../frame/ContextMenu'
import { PresetIcons } from '../../frame/PresetIcons'
import { useSession } from '../../store/session'
import { useAlbum } from '../../store/album'
import './storyCommands'
import { sy, useStory } from './storyStore'
import { DEFAULT_ID, NONE_ID, pickerId, pickerItems, pickerValue, styleFace } from './styleSamples'
import './story.css'

export function StyleTiles({ value, onChange, size = 48, showText = false }: { value: string | null | undefined; onChange: (v: string | null | undefined) => void; size?: number; showText?: boolean }) {
  const world = useStory((s) => s.world)
  const tree = useAlbum((a) => a.tree)
  const open = useSession((s) => !!s.project?.open)
  useEffect(() => { if (open && !sy().world && !sy().loading) void sy().load(); if (open && !useAlbum.getState().tree) void useAlbum.getState().load() }, [open])   // once per project open
  const styles = world?.styles ?? []
  if (!styles.length) return (
    <div className="style-tiles-empty"><span>Styles are made in World's Look</span><CommandButton id="story.world.open" text /></div>
  )
  const items = pickerItems(styles, world?.default_style, (s) => styleFace(s, tree), (id) => api.thumbUrl(id, 256), <Ban size={Math.round(size * 0.45)} />)
  return (
    <div className="style-tiles">
      <PresetIcons items={items} selected={pickerId(value)} size={size} showText={showText} label="style" onPick={(id) => onChange(pickerValue(id))}
        onContext={(id, e) => {                                                  // edit the style where it is written (Story · World)
          const sid = id === DEFAULT_ID ? world?.default_style : id === NONE_ID ? null : id
          if (sid) sy().select({ kind: 'style', id: sid })
          showMenu(e, [{ cmd: 'story.world.open' }])
        }} />
    </div>
  )
}
