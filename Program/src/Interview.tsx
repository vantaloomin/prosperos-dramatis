import { useState } from 'react'
import { cleaned, sendJson, type AuditHit, type Character, type Interviewed, type Suggestion } from './api'
import { Fold, ModelButton, TextArea, reveal } from './Fields'
import { FIELDS } from './generated/fields'
import { useModelCall } from './modelCall'
import { proposals } from './proposals'

// A line of quoted speech short enough to show under How they talk (the server's interview.QUOTE).
const QUOTE = /["“]([^"“”\n]{8,120})["”]/

/** One line of their speech: the sample the last run picked while it is still in the transcript, else the first
 * quoted line short enough. */
export function sampleLine(transcript: string, picked: string): string {
  if (picked && transcript.includes(picked)) return picked
  return QUOTE.exec(transcript)?.[1].trim() ?? ''
}

const words = (text: string) => text.split(/\s+/).filter(Boolean).length

interface Props { character: Character; ready: boolean; set: (change: Partial<Character>) => void; onSample: (sample: string) => void }

/** The in-voice interview, and what it suggests for their fields. A run's transcript, and each field it suggests,
 * goes onto the form as a proposal to keep or put back, like Help me write's. */
export function Interview({ character, ready, set, onSample }: Props) {
  const hear = useModelCall()
  const use = useModelCall()
  const [placed, setPlaced] = useState<string[] | null>(null)
  if (!ready && !character.interview) return null
  const body = () => ({ character: cleaned(proposals.form()?.get() ?? character) })
  const listen = () => void hear.run((signal) => sendJson<Interviewed>('/api/draft/interview', 'POST', body(), signal), (found) => {
    proposals.propose({ field: 'interview', label: 'Their interview', value: found.interview, source: 'interview', hits: found.audit })
    onSample(found.sample)
    setPlaced(null)
  })
  const read = () => void use.run((signal) => sendJson<{ proposals: Suggestion[]; audit: AuditHit[] }>('/api/draft/from-interview', 'POST', body(), signal), (found) => {
    for (const item of found.proposals) {
      proposals.propose({ field: item.field, label: FIELDS[item.field].label, value: item.value, source: 'interview', reason: item.reason,
        hits: found.audit.filter((hit) => hit.field === item.field) })
    }
    setPlaced(found.proposals.map((item) => item.field))
  })
  return (
    <Fold title="Interview" filled={!!character.interview}>
      {ready && (
        <div className="row">
          <ModelButton busy={hear.busy} onRun={listen} onStop={hear.stop} disabled={use.busy}>{character.interview ? 'Run again' : 'Hear them talk'}</ModelButton>
          {character.interview && <ModelButton busy={use.busy} onRun={read} onStop={use.stop} disabled={hear.busy}>Use what they said</ModelButton>}
        </div>
      )}
      {[hear.error, use.error].filter(Boolean).map((error) => <p key={error} className="error small" role="alert">{error}</p>)}
      {placed && (placed.length
        ? <p className="small">On the form: {placed.map((field, index) => <span key={field}>{index ? ', ' : ''}<button type="button" className="link" onClick={() => reveal(field)}>{FIELDS[field as Suggestion['field']].label}</button></span>)}</p>
        : <p className="muted small">The interview adds nothing their fields don&rsquo;t already say.</p>)}
      {character.interview && (
        <TextArea field="interview" label={`Their interview, ${words(character.interview).toLocaleString()} words`} value={character.interview}
          onChange={(interview) => set({ interview })} rows={14} />
      )}
    </Fold>
  )
}
