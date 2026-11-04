import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Download, MessageSquareText, Trash2, TriangleAlert } from 'lucide-react'
import { APPS, APP_NAMES, cleaned, type AuditHit, sendJson, type App, type Character, type Gender, type Looks, type Problems, type Relationship, type Saved } from './api'
import { assistant, useAssistantShown } from './assistant/store'
import { trackFocus, useProposalForm } from './assistant/useForm'
import { Field, Fold, ListField, TextArea, TextInput, useModelReady } from './Fields'
import { FromTheirCard } from './FromTheirCard'
import { InnerLife, SecretSection } from './InnerLife'
import { Interview, sampleLine } from './Interview'
import { proposals, useOpenCount } from './proposals'
import { Psyche } from './Psyche'
import { Portrait } from './Portrait'
import { AppPicks } from './Start'
import { Schedule, scheduleProblems } from './Schedule'
import { Sliders } from './Sliders'

const LIFESPANS: [string, string][] = [['', 'As long as their kind does'], ['0', "Doesn't age"], ['80', 'About 80 years'],
  ['150', 'About 150 years'], ['300', 'About 300 years'], ['600', 'About 600 years'], ['1000', 'About 1,000 years']]
const LOOKS: [keyof Looks, string][] = [['build', 'Build'], ['skin', 'Skin'], ['face', 'Face'], ['jaw', 'Jaw'], ['nose', 'Nose'],
  ['eyes', 'Eyes'], ['eye_shape', 'Eye shape'], ['hair', 'Hair'], ['facial_hair', 'Facial hair'], ['feature', 'Something people notice']]
const STAGES = ['Just met', 'Getting to know each other', 'Friends', 'Close', 'Very close']

/** Where a card can go: `prospero` keeps everything for Companion, Adventure and Dungeon; `chat` is the card for other
 * chat apps, without what only the Prospero apps use (dramatis/cards.py). */
export const CARD_TARGETS: { target: 'prospero' | 'chat'; name: string; leaves?: string }[] = [
  { target: 'prospero', name: 'Prospero apps' },
  { target: 'chat', name: 'SillyTavern, Marinara, Front Porch and other chat apps', leaves: 'Leaves out what only the Prospero apps use, like the schedule and sliders.' },
]

function ExportCard({ id }: { id: string }) {
  const menu = useRef<HTMLDetailsElement>(null)
  const close = () => { if (menu.current) menu.current.open = false }
  return (
    <details className="export" ref={menu}>
      <summary className="button"><Download size={14} aria-hidden /> Export card</summary>
      <ul>
        {CARD_TARGETS.map(({ target, name, leaves }) => (
          <li key={target}>
            <span>{name}</span>
            {leaves && <span className="muted small">{leaves}</span>}
            <span className="row">
              {(['png', 'json'] as const).map((kind) => (
                <a key={kind} className="button" href={`/api/characters/${id}/card.${kind}?for=${target}`} download onClick={close}
                  aria-label={`${kind.toUpperCase()} for ${name}`}>{kind.toUpperCase()}</a>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

interface Props {
  saved: Saved | null; start: Character; seed: string; filledIn?: string[]; note?: string
  /** A picture to save with them, as base64 PNG: an imported file's own. */
  portrait?: string
  onSaved: (saved: Saved) => void; onDeleted: () => void
}

const ZONES: string[] = (() => { try { return Intl.supportedValuesOf('timeZone') } catch { return [] } })()

/** One character, every field, for whichever apps they are made for. What a model writes goes into its field as a
 * proposal to keep or put back (src/proposals.ts); nothing is saved until Save. */
export function Editor({ saved, start, seed, filledIn, note, portrait, onSaved, onDeleted }: Props) {
  const client = useQueryClient()
  const ready = useModelReady()
  const [character, setCharacter] = useState<Character>(start)
  const [problems, setProblems] = useState<Problems>(saved?.problems ?? {})
  const [checkError, setCheckError] = useState('')
  const [audit, setAudit] = useState<AuditHit[]>([])
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ tone: 'note' | 'error'; text: string } | null>(note ? { tone: 'note', text: note } : null)
  const [pendingPortrait, setPendingPortrait] = useState<string | null>(portrait ?? null)
  const [sample, setSample] = useState('')
  const set = (change: Partial<Character>) => setCharacter((current) => ({ ...current, ...change }))
  const setLife = (change: Partial<Character['companion']>) => setCharacter((current) => ({ ...current, companion: { ...current.companion, ...change } }))
  const current = () => cleaned(character)
  const has = (app: App) => character.apps.includes(app)
  const assisting = useAssistantShown()
  const waiting = useOpenCount()
  useProposalForm(character, setCharacter)

  // What each app's own models make of the form, a moment after the last change.
  useEffect(() => {
    const timer = setTimeout(() => {
      sendJson<{ problems: Problems; audit: AuditHit[] }>('/api/check', 'POST', { character: cleaned(character) })
        .then((found) => { setProblems(found.problems); setAudit(found.audit); setCheckError('') })
        .catch((failure: Error) => setCheckError(failure.message))
    }, 500)
    return () => clearTimeout(timer)
  }, [character])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    try {
      // Saving keeps what the form shows, proposals included.
      const kept = proposals.keepAll()
      const body = { character: cleaned(proposals.form()?.get() ?? character), seed }
      let next = saved ? await sendJson<Saved>(`/api/characters/${saved.id}`, 'PUT', body) : await sendJson<Saved>('/api/characters', 'POST', body)
      if (pendingPortrait) {
        const pictured = await sendJson<Saved>(`/api/characters/${next.id}/portrait`, 'PUT', { filename: 'portrait.png', data: pendingPortrait })
        next = { ...pictured, problems: next.problems }
        setPendingPortrait(null)
      }
      await client.invalidateQueries({ queryKey: ['characters'] })
      const proposed = kept === 1 ? ', with the proposal that was waiting' : kept ? `, with the ${kept} proposals that were waiting` : ''
      setResult({ tone: 'note', text: `Saved ${next.character.name || 'them'}${proposed}.` })
      onSaved(next)
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'They could not be saved.' })
    } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!saved || !window.confirm(`Delete ${saved.character.name || 'this character'} from the library? Cards you exported stay where they are.`)) return
    await sendJson(`/api/characters/${saved.id}`, 'DELETE')
    await client.invalidateQueries({ queryKey: ['characters'] })
    onDeleted()
  }

  const said = sampleLine(character.interview, sample)
  const filled = new Set(filledIn ?? [])
  const mark = (field: string, label: string) => filled.has(field) ? `${label} (filled in)` : label
  const blocked = has('companion') && scheduleProblems(character.companion.schedule).length > 0
  const zones = ZONES.includes(character.companion.timezone) || !character.companion.timezone ? ZONES : [character.companion.timezone, ...ZONES]
  return (
    <form className="editor" onSubmit={submit} onFocus={(event) => trackFocus(event.target)}>
      <div className="editor-head">
        <h2>{character.name || 'New character'}</h2>
        <div className="row">
          {waiting > 0 && <span className="muted small">{waiting === 1 ? '1 proposal waiting' : `${waiting} proposals waiting`}</span>}
          <button type="button" aria-pressed={assisting} onClick={() => assistant.toggle()}><MessageSquareText size={14} aria-hidden /> Assistant</button>
          <button type="submit" className="primary" disabled={busy || blocked}>{busy ? 'Saving…' : saved ? 'Save' : 'Save to the library'}</button>
          {saved && <>
            <ExportCard id={saved.id} />
            <button type="button" className="icon danger" aria-label="Delete them" onClick={() => void remove()}><Trash2 size={15} /></button>
          </>}
        </div>
      </div>
      {result && <p className={result.tone} role="status">{result.text}</p>}
      {filled.size > 0 && <p className="note">Their text said nothing about {[...filled].join(', ')}, so the model filled those in. Check them.</p>}
      <WorksIn apps={character.apps} problems={problems} error={checkError} saved={!!saved} />
      <Audit hits={audit} />

      <section>
        <h3>Who they are</h3>
        <div className="portrait-row">
          <Portrait saved={saved} name={character.name} character={current} pending={pendingPortrait} onPending={setPendingPortrait}
            onSaved={(next) => onSaved({ ...next, problems })} />
          <div className="stack grow">
            <div className="grid three">
              <TextInput name="name" label="Name" value={character.name} onChange={(name) => set({ name })} maxLength={80} />
              <Field name="gender" label="Gender">{(id) => (
                <select id={id} value={character.gender} onChange={(event) => set({ gender: event.target.value as Gender })}>
                  <option value="">Not said</option><option value="woman">Woman</option><option value="man">Man</option><option value="nonbinary">Nonbinary</option>
                </select>
              )}</Field>
              <Field name="age" label="Age">{(id) => (
                <input id={id} type="number" min={18} max={5000} value={character.age ?? ''} onChange={(event) => set({ age: event.target.value ? Number(event.target.value) : null })} />
              )}</Field>
            </div>
            <TextInput name="setting" label="Where and when" value={character.setting} onChange={(setting) => set({ setting })} maxLength={200} />
            <div className="grid three">
              <TextInput name="kind" label="Kind, if not human" value={character.kind} onChange={(kind) => set({ kind: kind.toLowerCase().replace(/[^a-z0-9-]/g, '') })} maxLength={40} />
              <Field label="How long they live">{(id) => (
                <select id={id} value={character.lifespan ?? ''} onChange={(event) => set({ lifespan: event.target.value === '' ? null : Number(event.target.value) })}>
                  {LIFESPANS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              )}</Field>
              <Field label="Birthday">{(id) => (
                <input id={id} value={character.birthday} maxLength={5} placeholder="MM-DD" onChange={(event) => set({ birthday: event.target.value })} />
              )}</Field>
            </div>
            <AppPicks apps={character.apps} onChange={(apps) => set({ apps })} />
          </div>
        </div>
        <TextArea name="about" label={mark('about', 'About them')} write="about them" value={character.about} onChange={(about) => set({ about })} maxLength={2000} rows={3} />
        <TextArea name="personality" label={mark('personality', 'Personality')} write="their personality" value={character.personality} onChange={(personality) => set({ personality })} maxLength={8000} rows={4} />
        <div className="grid two">
          <div className="stack tight">
            <TextArea name="voice" label={mark('voice', 'How they talk')} write="how they talk" value={character.voice} onChange={(voice) => set({ voice })} maxLength={600} rows={3} />
            {said && <q className="sample">{said}</q>}
          </div>
          <TextArea name="sound" label={mark('sound', 'How they sound aloud')} write="how they sound aloud" value={character.sound} onChange={(sound) => set({ sound })} maxLength={300} rows={3} />
        </div>
      </section>

      <section>
        <h3>How they come across</h3>
        <div className="grid two">
          <TextArea name="seen_as" label={mark('seen_as', 'How others see them')} write="how others see them" value={character.seen_as} onChange={(seen_as) => set({ seen_as })} maxLength={400} rows={3} />
          <TextArea name="sees_self" label={mark('sees_self', 'How they see themselves')} write="how they see themselves" value={character.sees_self} onChange={(sees_self) => set({ sees_self })} maxLength={1200} rows={3} />
        </div>
      </section>

      <section>
        <h3>Personality</h3>
        <Sliders character={current} seed={seed} onChange={(personality_sliders) => set({ personality_sliders })} />
      </section>

      <section>
        <h3>Their story</h3>
        <TextArea name="background" label={mark('background', 'Background')} write="their background" value={character.background} onChange={(background) => set({ background })} maxLength={12000} rows={5} />
        <div className="grid two">
          <TextArea name="wants" label={mark('wants', 'What they want')} write="what they want" value={character.wants} onChange={(wants) => set({ wants })} maxLength={300} rows={2} />
          <TextArea name="fears" label={mark('fears', 'What they fear')} write="what they fear" value={character.fears} onChange={(fears) => set({ fears })} maxLength={300} rows={2} />
        </div>
        <div className="grid three">
          <ListField name="skills" label={mark('skills', 'Skills')} write="skills" add="Add a skill" value={character.skills} onChange={(skills) => set({ skills })} />
          <ListField name="flaws" label={mark('flaws', 'Flaws')} write="flaws" add="Add a flaw" value={character.flaws} onChange={(flaws) => set({ flaws })} />
          <ListField name="interests" label={mark('interests', 'Interests')} write="interests" add="Add an interest" value={character.interests} onChange={(interests) => set({ interests })} />
        </div>
      </section>

      <section>
        <h3>Depth</h3>
        <div className="folds">
          <Interview character={character} ready={ready} set={set} onSample={setSample} />
          <InnerLife arc={character.arc} onChange={(arc) => set({ arc })} />
          <Psyche psyche={character.psyche} selfId={saved?.id} onChange={(psyche) => set({ psyche })} />
          <SecretSection secret={character.secret} onChange={(secret) => set({ secret })} />
        </div>
      </section>

      <section>
        <h3>How they look</h3>
        <TextArea name="appearance" label={mark('appearance', 'Appearance')} write="their appearance" value={character.appearance} onChange={(appearance) => set({ appearance })} maxLength={600} rows={2} />
        <div className="folds">
          <Fold title="Details" filled={Object.values(character.looks).some((value) => value !== null && value !== '')}>
            <div className="grid three">
              <Field label="Height (cm)">{(id) => <input id={id} type="number" min={120} max={230} value={character.looks.height_cm ?? ''} onChange={(event) => set({ looks: { ...character.looks, height_cm: event.target.value ? Number(event.target.value) : null } })} />}</Field>
              <Field label="Weight (kg)">{(id) => <input id={id} type="number" min={35} max={250} value={character.looks.weight_kg ?? ''} onChange={(event) => set({ looks: { ...character.looks, weight_kg: event.target.value ? Number(event.target.value) : null } })} />}</Field>
              {LOOKS.map(([key, label]) => (
                <TextInput key={key} label={label} value={String(character.looks[key] ?? '')} maxLength={key === 'hair' || key === 'feature' ? 200 : 120}
                  onChange={(value) => set({ looks: { ...character.looks, [key]: value } })} />
              ))}
            </div>
          </Fold>
          <FromTheirCard card={character.card} onChange={(card) => set({ card })} />
        </div>
      </section>

      {has('companion') && (
        <section className="app-section">
          <h3>For Companion</h3>
          <div className="grid two">
            <Field label="Relationship">{(id) => (
              <select id={id} value={character.companion.relationship} onChange={(event) => setLife({ relationship: event.target.value as Relationship })}>
                <option value="friendship">Friendship</option><option value="romance">Romance, only with your yes</option><option value="mentor">Mentor</option><option value="family">Family</option><option value="other">Something else</option>
              </select>
            )}</Field>
            <Field label="How close you start">{(id) => (
              <select id={id} value={character.companion.starting_closeness} onChange={(event) => setLife({ starting_closeness: Number(event.target.value) })}>
                {STAGES.map((stage, index) => <option key={stage} value={index + 1}>{stage}</option>)}
              </select>
            )}</Field>
          </div>
          <TextArea name="history_together" label="How you know each other" value={character.companion.history_together} onChange={(history_together) => setLife({ history_together })} maxLength={2000} rows={2} />
          <TextArea name="routine" label={mark('routine', 'Their routine, in their words')} write="their routine" value={character.companion.routine} onChange={(routine) => setLife({ routine })} maxLength={8000} rows={3} />
          <Field name="schedule" label="Their week" write="their week" filled={character.companion.schedule.length > 0} group>{() => (
            <Schedule blocks={character.companion.schedule} onChange={(schedule) => setLife({ schedule })} />
          )}</Field>
          <ListField name="life_themes" label={mark('life_themes', 'Life themes')} write="life themes" add="Add a life theme" value={character.companion.life_themes} onChange={(life_themes) => setLife({ life_themes })} />
          <div className="grid two">
            <Field label="Time zone">{(id) => (
              <select id={id} value={character.companion.timezone} onChange={(event) => setLife({ timezone: event.target.value })}>
                <option value="">Not set</option>
                {zones.map((zone) => <option key={zone} value={zone}>{zone.replace(/_/g, ' ')}</option>)}
              </select>
            )}</Field>
          </div>
          <fieldset className="ticks">
            <legend>How they text</legend>
            {([['bursts', 'In bursts of short texts'], ['lowercase', 'All lowercase'], ['typos', 'With typos'], ['quick', 'Quick to reply']] as const).map(([key, label]) => (
              <label key={key} className="check"><input type="checkbox" checked={character.companion.texting[key]} onChange={(event) => setLife({ texting: { ...character.companion.texting, [key]: event.target.checked } })} /> {label}</label>
            ))}
          </fieldset>
          <TextArea label="When you are away" value={character.companion.absence_reaction} onChange={(absence_reaction) => setLife({ absence_reaction })} maxLength={2000} rows={2} />
        </section>
      )}
    </form>
  )
}

/** The AI-slop audit of the form as it stands: hard hits (stock names, dashes, the assistant's voice) to fix, and flags
 * worth a look. Nothing here stops a save: a name the user chose is theirs. */
export function Audit({ hits }: { hits: AuditHit[] }) {
  if (!hits.length) return null
  const hard = hits.filter((hit) => hit.severity === 'hard')
  const flags = hits.filter((hit) => hit.severity === 'flag')
  const line = (hit: AuditHit, index: number) => <li key={index}><strong>{hit.label}:</strong> “{hit.match.trim() || hit.match}” <span className="muted">({hit.rule}) …{hit.context}…</span></li>
  return (
    <div className="audit">
      {hard.length > 0 && <details open className="error small"><summary><TriangleAlert size={14} aria-hidden /> {hard.length} {hard.length === 1 ? 'thing reads' : 'things read'} as model-written</summary>
        <p className="muted">Stock names, dashes and the assistant's voice. Change them unless you chose them.</p><ul>{hard.map(line)}</ul></details>}
      {flags.length > 0 && <details className="small"><summary>Worth a look ({flags.length})</summary>
        <p className="muted">Words and phrases models lean on. One means little; keep them where they fit.</p><ul>{flags.map(line)}</ul></details>}
    </div>
  )
}

function WorksIn({ apps, problems, error, saved }: { apps: App[]; problems: Problems; error: string; saved: boolean }) {
  return (
    <div className="works-in" aria-live="polite">
      {error ? <p className="error small"><TriangleAlert size={14} aria-hidden /> {error}</p> : APPS.filter((app) => apps.includes(app)).map((app) => {
        const found = problems[app]
        return found?.length
          ? <details key={app} className="error small"><summary><TriangleAlert size={14} aria-hidden /> {APP_NAMES[app]} would refuse this</summary><ul>{found.map((problem) => <li key={problem}>{problem}</li>)}</ul></details>
          : <span key={app} className="ok small"><CheckCircle2 size={14} aria-hidden /> Works in {APP_NAMES[app]}</span>
      })}
      {!saved && <span className="muted small">Save them to export a card.</span>}
    </div>
  )
}
