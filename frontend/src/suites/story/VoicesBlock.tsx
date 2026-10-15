// CN2 (19 §3b / §6 item 6, D87): the Cast Inspector's voices block — the character's voice (the Flow's lines of this speaker take it),
// its tier and measured pace, the form for a new voice of the project: the draft tier's fixed Kokoro voice (the CPU, beside a running
// engine) or the cloning tier's reference clip — an audio asset of 3–10 s: a recording imported as a WAV, or a draft line — with its
// transcript, whose voice it is and that they consented; the verbs as commands (D32).
import { useEffect, useState } from 'react'
import { http, unwrap } from '../../api/client'
import type { Asset, Profile, VoiceCaps } from '../../api/types'
import { CommandButton } from '../../frame/CommandButton'
import { useSession } from '../../store/session'
import { sy, useStory, voiceLabel, type VoiceBody } from './storyStore'

const TIER_LABEL: Record<string, string> = { draft: 'draft · Kokoro on the CPU', cloning: 'cloning · Qwen3-TTS on the GPU' }

export function VoicesBlock({ p }: { p: Profile }) {
  const caps = useSession((s) => s.capabilities?.voice)
  const voices = useStory((s) => s.voices)
  const form = useStory((s) => s.voiceForm)
  const mine = voices.find((v) => v.id === p.voice_id)
  return (
    <div className="voices" aria-label="voices">
      <h4>Voice</h4>
      <div className="kv">
        <span>speaks with</span>
        <select aria-label="profile voice" value={p.voice_id ?? ''} onChange={(e) => void sy().patchProfile({ voice_id: e.target.value || null })}>
          <option value="">(no voice)</option>{voices.map((v) => <option key={v.id} value={v.id}>{voiceLabel(v)}</option>)}
        </select>
        {mine && <><span>tier</span><span>{TIER_LABEL[mine.tier] ?? mine.tier}{mine.tier === 'draft' ? ` · ${mine.voice ?? ''}` : mine.speaker ? ` · ${mine.speaker}` : ''}</span></>}
        {mine?.measured?.rtf != null && <><span>measured</span>
          <span>{String(mine.measured.rtf)} s per second of speech · load {String(mine.measured.load_s ?? '?')} s{mine.measured.peak_vram_gb ? ` · peak ${String(mine.measured.peak_vram_gb)} GB` : ''}</span></>}
      </div>
      {caps && !caps.available && <span className="hint">{caps.why ?? 'the voice tools are not available in this build'}</span>}
      <div className="verbs"><CommandButton id="story.cast.newVoice" text /><CommandButton id="story.cast.deleteVoice" text /></div>
      {form && caps && <NewVoiceForm caps={caps} />}
    </div>
  )
}

function NewVoiceForm({ caps }: { caps: VoiceCaps }) {
  const [b, setB] = useState<VoiceBody>({ name: '', tier: 'draft', voice: caps.draft.voices?.[0]?.id ?? 'af_heart', language: 'English', reference_asset_id: null, reference_text: '', speaker: '', consent: '' })
  const [refs, setRefs] = useState<Asset[]>([])
  useEffect(() => {
    if (b.tier !== 'cloning') return
    void unwrap(http.GET('/assets', { params: { query: { kind: 'audio', limit: 100 } } })).then((r) => setRefs(r.items)).catch(() => setRefs([]))
  }, [b.tier])
  const set = (patch: Partial<VoiceBody>) => setB({ ...b, ...patch })
  const tier = b.tier === 'draft' ? caps.draft : caps.cloning
  const [lo, hi] = caps.cloning.reference_s ?? [3, 10]
  const fits = (a: Asset) => a.duration_s != null && a.duration_s >= lo && a.duration_s <= hi + 0.5
  return (
    <div className="kv voice-form" aria-label="new voice">
      <span>name</span><input type="text" aria-label="voice name" value={b.name} placeholder="Narrator" onChange={(e) => set({ name: e.target.value })} />
      <span>tier</span>
      <select aria-label="voice tier" value={b.tier} onChange={(e) => set({ tier: e.target.value as VoiceBody['tier'], language: 'English' })}>
        <option value="draft">draft — Kokoro on the CPU{caps.draft.cached ? '' : ' (0.3 GB fetched on first use)'}</option>
        <option value="cloning">cloning — Qwen3-TTS on the GPU, {caps.cloning.vram_gb} GB{caps.cloning.cached ? '' : ' (2.3 GB fetched on first use)'}</option>
      </select>
      {b.tier === 'draft' ? <>
        <span>voice</span>
        <select aria-label="kokoro voice" value={b.voice ?? ''} onChange={(e) => set({ voice: e.target.value })}>{(caps.draft.voices ?? []).map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}</select>
      </> : <>
        <span>reference</span>
        <select aria-label="reference clip" value={b.reference_asset_id ?? ''} onChange={(e) => set({ reference_asset_id: e.target.value || null })}>
          <option value="">an audio asset of {lo}–{hi} s…</option>
          {refs.map((a) => <option key={a.id} value={a.id} disabled={!fits(a)}>{(a.prompt_text ?? a.id).slice(0, 48)} · {a.duration_s ?? '?'} s{fits(a) ? '' : ` (not ${lo}–${hi} s)`}</option>)}
        </select>
        <span>transcript</span><textarea rows={2} aria-label="reference transcript" value={b.reference_text} placeholder="the words spoken in the reference clip" onChange={(e) => set({ reference_text: e.target.value })} />
        <span>speaker</span><input type="text" aria-label="voice speaker" value={b.speaker} placeholder="whose voice" onChange={(e) => set({ speaker: e.target.value })} />
        <span>consent</span><input type="text" aria-label="voice consent" value={b.consent} placeholder="e.g. my own voice, recorded 2026-10-14" onChange={(e) => set({ consent: e.target.value })} />
      </>}
      <span>language</span>
      <select aria-label="voice language" value={b.language} onChange={(e) => set({ language: e.target.value })}>{tier.languages.map((l) => <option key={l} value={l}>{l}</option>)}</select>
      <span>estimate</span><span>≈ {tier.rtf} s per second of speech + {tier.load_s} s to load{b.tier === 'cloning' ? ' · the engine stops for it' : ' · beside a running engine'}</span>
      <span />
      <div className="verbs">
        <button className="primary" aria-label="create voice" disabled={!b.name.trim()} onClick={() => void sy().createVoice(b).then((r) => { if (r) sy().setVoiceForm(false) })}>Create</button>
        <button onClick={() => sy().setVoiceForm(false)}>Cancel</button>
      </div>
    </div>
  )
}
