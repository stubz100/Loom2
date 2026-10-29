// The Generate column's commands (09; D90 02 §6): a subject card's and the scene's verbs, the references, the saved panels, New angle's
// sheet (AngleTab.tsx). B2 (D159): moved out of the old Image suite with the frame; World's Make and Sketches have their own feet.
import { ArrowDownFromLine, Bookmark, Hand, Images, Orbit, PenLine, RotateCcw, RotateCw, Sparkles, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useEffect } from 'react'
import { handleKeyFor, registerCommands } from '../../frame/commands'
import { registerKeyHost } from '../../frame/keyHosts'
import { askText, useSession } from '../../store/session'
import { profilesForMentions } from '../story/storyStore'
import { useGenerate, subjectItem } from './generateStore'
import { castOffer } from './subjectCast'
import { versionOf } from './sheet'

registerCommands([
  // P14 (D82): the Angle tab — the five moves are buttons on the pad; the verb has no key (Ctrl+Enter stays Generate's)
  { id: 'gen.angle.generate', scope: 'generate', label: 'New angle', icon: Orbit, placement: ['panel'], when: () => !!useGenerate.getState().angle.asset_id,
    run: () => void useGenerate.getState().generateAngle().then((jobs) => { if (jobs) useGenerate.setState({ angleOpen: false }) }) },   // D90: the sheet closes once queued
  { id: 'gen.angle.left45', scope: 'generate', label: 'Rotate left 45°', icon: RotateCcw, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'left45' }) },
  { id: 'gen.angle.right45', scope: 'generate', label: 'Rotate right 45°', icon: RotateCw, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'right45' }) },
  { id: 'gen.angle.topdown', scope: 'generate', label: 'Top-down', icon: ArrowDownFromLine, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'topdown' }) },
  { id: 'gen.angle.closeup', scope: 'generate', label: 'Close-up', icon: ZoomIn, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'closeup' }) },
  { id: 'gen.angle.wide', scope: 'generate', label: 'Wide', icon: ZoomOut, placement: ['panel'], run: () => useGenerate.getState().setAngle({ move: 'wide' }) },
  { id: 'gen.angle.clear', scope: 'generate', label: 'Remove the source', icon: X, placement: ['panel'], when: () => !!useGenerate.getState().angle.asset_id, run: () => useGenerate.getState().setAngle({ asset_id: null }) },
  { id: 'gen.savePreset', scope: 'generate', label: 'Save panel preset…', icon: Bookmark, keys: 'Ctrl+S', placement: ['panel'], run: () => { const g = useGenerate.getState(); void askText({ title: 'Save panel preset', text: 'Saves every field of the panel under this name; an existing preset of the same name is replaced.', initial: g.lastPreset ?? '', placeholder: 'preset name' }).then((n) => { if (n) void g.savePreset(n) }) } },
  // D93 (A1): a linked subject card's casting run — "Give <name> a look" / "More looks for <name>" (the card's button sets the card first)
  { id: 'gen.subject.cast', scope: 'generate', label: 'Give the character a look', icon: Sparkles, placement: ['panel'], hint: "the panel's images land as the linked character's candidates in World",
    when: () => { const i = subjectItem.i, g = useGenerate.getState(); const pid = i !== undefined ? g.panel.tree.subjects?.[i]?.profile_id : undefined
      const o = pid ? castOffer(profilesForMentions().find((p) => p.id === pid), 0, g.panel.tree.subjects?.[i ?? -1]?.version) : null; return !!o && !o.disabled && g.panel.prompt_mode === 'tree' && !!useSession.getState().project?.open },
    run: () => { const i = subjectItem.i; if (i !== undefined) void useGenerate.getState().castLook(i) } },
  // D93 (B4): the sheet a linked card shows is Cast's — edited there (the card's "edit in Cast", the version chip's menu); every linked subject follows
  { id: 'gen.subject.editSheet', scope: 'generate', label: 'Edit the character sheet in World', icon: PenLine, placement: ['panel', 'context'],
    hint: 'the appearance, outfit, bound colours and marks of the version this subject uses — every linked subject follows',
    when: () => { const i = subjectItem.i; return i !== undefined && !!useGenerate.getState().panel.tree.subjects?.[i]?.profile_id },
    run: () => { const i = subjectItem.i, s = i !== undefined ? useGenerate.getState().panel.tree.subjects?.[i] : undefined
      const p = s?.profile_id ? profilesForMentions().find((x) => x.id === s.profile_id) : undefined, v = versionOf(p, s?.version)
      if (!p || !v) return
      const focus = (n: number) => {                                         // the version page renders after Story loads: focus its appearance once it is there
        const el = document.getElementById('cast-appearance') as HTMLTextAreaElement | null
        if (el && document.querySelector('.cast-page h2')?.textContent?.includes(p.name)) el.focus()
        else if (n < 60) window.setTimeout(() => focus(n + 1), 50)
      }
      void import('../../store/origin').then((m) => { m.goToStory({ tab: 'cast', id: p.id, version: v.id }); focus(0) }) } },
  // D93 (C6): a held prop is put down (the holds ▸ menu, the chip's ✕); a linked place's sheet is Cast's (the scene's "edit in Cast", its chip's menu)
  { id: 'gen.subject.unhold', scope: 'generate', label: 'Put the prop down', icon: Hand, placement: ['panel', 'context'], hint: 'the subject holds nothing — its words and images leave the prompt',
    when: () => { const i = subjectItem.i; return i !== undefined && !!useGenerate.getState().panel.tree.subjects?.[i]?.holds },
    run: () => { const i = subjectItem.i; if (i !== undefined) useGenerate.getState().holdProp(i, null) } },
  { id: 'gen.scene.editSheet', scope: 'generate', label: 'Edit the place in World', icon: PenLine, placement: ['panel', 'context'],
    hint: 'the look, colours and marks of the place the scene uses — the scene follows', when: () => !!useGenerate.getState().panel.tree.scene_link,
    run: () => { const l = useGenerate.getState().panel.tree.scene_link, p = l ? profilesForMentions().find((x) => x.id === l.profile_id) : undefined, v = versionOf(p, l?.version)
      if (p && v) void import('../../store/origin').then((m) => m.goToStory({ tab: 'cast', id: p.id, version: v.id })) } },
  { id: 'gen.clearRefs', scope: 'generate', label: 'Clear references', icon: Images, placement: ['context', 'panel'], when: () => useGenerate.getState().panel.refs.length > 0, run: () => { const g = useGenerate.getState(); [...g.panel.refs].forEach((r) => g.removeRef(r.asset_id)) } },
])

export function useGenerateKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (useSession.getState().ui.suite !== 'generate') return
      if ((e.target as HTMLElement | null)?.closest?.('.modal')) return     // D90: a modal (Models & engine) owns its keys
      handleKeyFor('generate', e)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])
}

// U1 (D157): the keys are the shell's (frame/keyHosts.tsx), not the Strip's
registerKeyHost('generate', function GenerateKeys() { useGenerateKeys(); return null })

