// D73 (ArtCraft P12): the Text prompt with @mentions, and what goes in beside the reference slots — the mention chips with what each gave,
// the references they resolved to (from the preview), a note per reference, and the references the model leaves out.
import { X } from 'lucide-react'
import { api } from '../../api/client'
import { useSession } from '../../store/session'
import { mentionsInUse, useGenerate } from './generateStore'
import { useMentions } from './useMentions'

/** The Text mode's prompt, with @mentions. */
export function TextPrompt() {
  const text = useGenerate((g) => g.panel.text)
  const set = useGenerate((g) => g.set)
  const m = useMentions(text, (v) => set({ text: v }))
  return (
    <div className="text-prompt">
      <textarea value={text} onChange={(e) => set({ text: e.target.value })} onKeyUp={m.onKeyUp} rows={8} placeholder="plain prompt — type @ to mention a group (its images become references)" />
      {m.button}
    </div>
  )
}

/** D73: the mentions in the prompt (with what they gave), the references they resolved to, notes, and what the model leaves out. */
export function RefExtras() {
  const g = useGenerate()
  const p = g.panel
  const pv = g.preview
  const caps = useSession((s) => s.capabilities)
  const cap = caps?.models[p.model_id]
  const ms = mentionsInUse(p)
  const fromMentions = (pv?.ref_list ?? []).map((r, i) => ({ ...r, n: i + 1 })).filter((r) => r.mention && r.asset_id)
  const dropped = pv?.refs_dropped ?? 0
  return (
    <>
      {ms.length > 0 && (
        <div className="mention-chips">
          {ms.map((m) => {
            const got = pv?.mentions?.find((x) => x.group_id === m.group_id)?.asset_ids?.length
            return (
              <span key={m.group_id} className={`mchip${m.profile_id ? ' profile' : ''}`} title={m.profile_id ? "the profile's current version: its hero, then its reference set in order — as many as the model has room for; its stub rides on the note" : "the group's cover, then its page in order — as many as the model has room for"}>
                @{m.name}<span className="muted"> · {got === undefined ? '…' : `${got} image${got === 1 ? '' : 's'}`}</span>
                <button className="quiet" aria-label={`Stop mentioning ${m.name}`} title="Stop mentioning it (the name stays as plain text)" onClick={() => g.removeMention(m.group_id)}><X size={12} /></button>
              </span>
            )
          })}
        </div>
      )}
      {fromMentions.length > 0 && (
        <div className="ref-from-mentions" aria-label="references from mentions">
          {fromMentions.map((r) => (
            <div key={r.asset_id} className="ref-slot mentioned" title={`reference image ${r.n} · from @${r.note ?? ''}`}>
              <img src={api.thumbUrl(r.asset_id!, 256)} alt="" /><span className="n">{r.n}</span>
            </div>
          ))}
        </div>
      )}
      {p.refs.length > 0 && (
        <div className="ref-notes">
          {p.refs.map((r, i) => (
            <label key={r.asset_id}><span className="n">{i + 1}</span>
              <input type="text" value={r.note ?? ''} placeholder="what it shows (optional) — e.g. the hero, red coat" aria-label={`note for reference ${i + 1}`} onChange={(e) => g.setRefNote(r.asset_id, e.target.value)} />
            </label>
          ))}
        </div>
      )}
      {dropped > 0 && (
        <p className="ref-warn">{dropped} reference{dropped === 1 ? '' : 's'} over {cap?.label ?? p.model_id}'s limit of {pv?.max_refs ?? cap?.max_refs} {dropped === 1 ? 'is' : 'are'} left out — remove some or pick a model that takes more.</p>
      )}
    </>
  )
}

