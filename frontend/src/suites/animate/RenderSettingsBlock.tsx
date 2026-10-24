// AE5 (03 §AE5, proto01_animate 31 §4a): the finished shot's render settings and output modules in Animate › Final › Output.
import type { Final, RenderSettings } from '../../api/types'
import { Help } from '../../frame/Help'
import { useFinals } from '../stage/finalShot'

/** AE5 (03 §AE5): the render settings and the output modules of the finished shot — EffectCraft's render queue item and what is written
 *  beside the take's PNG master. The defaults are AE1's render (Best, Full, the composition's switches, 8-bit, no alpha, no ProRes). */
export function RenderSettingsBlock({ f }: { f: Final }) {
  const r = f.render
  const set = (patch: Partial<RenderSettings>) => void useFinals.getState().setRender(f.id, patch)
  return (
    <div className="render-settings" data-render-settings>
      <h4>Render settings <Help text="EffectCraft's render queue: quality and resolution of the composition, motion blur and frame blending (the composition's own switches, or off for every layer), the colour depth it works at. The PNG master is the take; its H.264 proxy is made beside it." /></h4>
      <div className="kv">
        <span>quality</span><select value={r.quality} aria-label="render quality" onChange={(e) => set({ quality: e.target.value as RenderSettings['quality'] })}><option value="best">Best</option><option value="draft">Draft</option></select>
        <span>resolution</span><select value={r.resolution} aria-label="render resolution" onChange={(e) => set({ resolution: e.target.value as RenderSettings['resolution'] })}>
          {(['full', 'half', 'third', 'quarter'] as const).map((x) => <option key={x} value={x}>{x[0].toUpperCase() + x.slice(1)}{x === 'full' ? ` · ${f.size.w}×${f.size.h}` : ''}</option>)}</select>
        <span>motion blur</span><select value={r.motion_blur} aria-label="render motion blur" onChange={(e) => set({ motion_blur: e.target.value as RenderSettings['motion_blur'] })}><option value="comp">as the layers ask</option><option value="off">off for all</option></select>
        <span>frame blending</span><select value={r.frame_blending} aria-label="render frame blending" onChange={(e) => set({ frame_blending: e.target.value as RenderSettings['frame_blending'] })}><option value="comp">as the layers ask</option><option value="off">off for all</option></select>
        <span>depth</span><select value={r.depth} aria-label="render depth" onChange={(e) => set({ depth: Number(e.target.value) as RenderSettings['depth'] })}><option value={8}>8 bits</option><option value={16}>16 bits</option><option value={32}>32 bits (float)</option></select>
      </div>
      <h4>Output <Help text="The PNG master is always written (the take). Keep its alpha where the layers leave the frame open (straight, conformed with it at F16); a ProRes 4444 (10-bit 4:4:4) beside it in the clip's folder for finishing elsewhere." /></h4>
      <label className="chk"><input type="checkbox" checked={r.alpha} aria-label="keep the alpha" onChange={(e) => set({ alpha: e.target.checked })} /> keep the alpha</label>
      <label className="chk"><input type="checkbox" checked={r.prores} aria-label="ProRes 4444 beside it" onChange={(e) => set({ prores: e.target.checked })} /> ProRes 4444 beside the master</label>
    </div>
  )
}
