import { useState } from 'react'
import { Check, MessageCircle, Undo2, Wand2, X } from 'lucide-react'
import { sendJson, type Character, type Interviewed, type Proposal, type ProposedField } from './api'

const LABELS: Record<ProposedField, string> = {
  voice: 'How they talk', appearance: 'Appearance', seen_as: 'Outward appearance', sees_self: 'How they see themselves',
  flaws: 'Flaws', interests: 'Interests',
}
// A line of quoted speech short enough to show under How they talk (the server's interview.QUOTE).
const QUOTE = /["“]([^"“”\n]{8,120})["”]/

/** One line of their speech: the sample the last run picked while it is still in the transcript, else the first
 * quoted line short enough. */
export function sampleLine(transcript: string, picked: string): string {
  if (picked && transcript.includes(picked)) return picked
  return QUOTE.exec(transcript)?.[1].trim() ?? ''
}

type Card = { proposal: Proposal; before?: Character[ProposedField] }
const words = (text: string) => text.split(/\s+/).filter(Boolean).length

interface Props {
  character: Character; ready: boolean; current: () => Character
  set: (change: Partial<Character>) => void; onSample: (sample: string) => void
}

/** The in-voice interview, and what it suggests for their fields. A new run waits beside the old transcript until the
 * user takes it, and a proposal changes nothing until Apply. */
export function Interview({ character, ready, current, set, onSample }: Props) {
  const [pending, setPending] = useState<Interviewed | null>(null)
  const [cards, setCards] = useState<Card[] | null>(null)
  const [busy, setBusy] = useState<'hear' | 'use' | null>(null)
  const [error, setError] = useState('')
  if (!ready && !character.interview) return null

  const run = async <T,>(kind: 'hear' | 'use', path: string, then: (found: T) => void) => {
    setBusy(kind)
    setError('')
    try {
      then(await sendJson<T>(path, 'POST', { character: current() }))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The model could not do that.')
    } finally { setBusy(null) }
  }
  const take = (found: Interviewed) => {
    set({ interview: found.interview })
    onSample(found.sample)
    setPending(null)
    setCards(null)
  }
  const hear = () => run<Interviewed>('hear', '/api/draft/interview', (found) => character.interview ? setPending(found) : take(found))
  const use = () => run<{ proposals: Proposal[] }>('use', '/api/draft/from-interview', (found) => setCards(found.proposals.map((proposal) => ({ proposal }))))
  const apply = (index: number) => {
    if (!cards) return
    const { proposal } = cards[index]
    set({ [proposal.field]: proposal.value })
    setCards(cards.map((card, at) => at === index ? { proposal, before: character[proposal.field] } : card))
  }
  const undo = (index: number) => {
    const card = cards?.[index]
    if (!cards || !card || card.before === undefined) return
    set({ [card.proposal.field]: card.before })
    setCards(cards.map((each, at) => at === index ? { proposal: card.proposal } : each))
  }
  const dismiss = (index: number) => setCards(cards && cards.filter((_, at) => at !== index))

  return (
    <section>
      <h3>Interview</h3>
      {ready && (
        <div className="row">
          <button type="button" disabled={!!busy} onClick={() => void hear()}><MessageCircle size={14} aria-hidden /> {busy === 'hear' ? 'Listening…' : character.interview ? 'Run again' : 'Hear them talk'}</button>
          {character.interview && <button type="button" disabled={!!busy} onClick={() => void use()}><Wand2 size={14} aria-hidden /> {busy === 'use' ? 'Reading…' : 'Use what they said'}</button>}
        </div>
      )}
      {error && <p className="error small" role="alert">{error}</p>}
      {pending && (
        <div className="card proposal">
          <details open><summary>The new interview ({words(pending.interview).toLocaleString()} words)</summary><div className="transcript">{pending.interview}</div></details>
          <div className="row">
            <button type="button" className="primary" onClick={() => take(pending)}><Check size={14} aria-hidden /> Use this one</button>
            <button type="button" onClick={() => setPending(null)}>Keep the old one</button>
          </div>
        </div>
      )}
      {character.interview && (
        <details>
          <summary>Their interview ({words(character.interview).toLocaleString()} words)</summary>
          <textarea aria-label="Their interview" value={character.interview} maxLength={16000} rows={16} onChange={(event) => set({ interview: event.target.value })} />
        </details>
      )}
      {cards && !cards.length && <p className="muted small">The interview adds nothing their fields don't already say.</p>}
      {cards?.map((card, index) => (
        <div key={card.proposal.field} className="card proposal">
          <strong>{LABELS[card.proposal.field]}</strong>
          {Array.isArray(card.proposal.value) ? <ul>{card.proposal.value.map((item) => <li key={item}>{item}</li>)}</ul> : <p className="transcript">{card.proposal.value}</p>}
          {card.proposal.reason && <p className="muted small">{card.proposal.reason}</p>}
          <div className="row">
            {card.before === undefined
              ? <><button type="button" className="primary" onClick={() => apply(index)}><Check size={14} aria-hidden /> Apply</button>
                <button type="button" onClick={() => dismiss(index)}><X size={14} aria-hidden /> Dismiss</button></>
              : <><span className="ok small"><Check size={14} aria-hidden /> Applied</span>
                <button type="button" className="link" onClick={() => undo(index)}><Undo2 size={13} aria-hidden /> Undo</button></>}
          </div>
        </div>
      ))}
    </section>
  )
}
