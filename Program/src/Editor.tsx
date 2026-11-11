import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Download, MessageSquareText, Trash2, TriangleAlert } from 'lucide-react'
import { APPS, APP_NAMES, RELATIONSHIPS, cleaned, type AuditHit, sendJson, type App, type Character, type Gender, type Looks, type Problems, type Relationship, type Saved } from './api'
import { assistant, useAssistantShown } from './assistant/store'
import { trackFocus, useProposalForm } from './assistant/useForm'
import { EmotionalEdges } from './EmotionalEdges'
import { Field, Fold, ListField, TextArea, TextInput, useModelReady } from './Fields'
import { FromTheirCard } from './FromTheirCard'
import { InnerLife, SecretSection } from './InnerLife'
import { Interview, sampleLine } from './Interview'
import { isEmpty, pathOf, proposals, useOpenCount, useWritten, valueAt, withValue } from './proposals'
import { Psyche } from './Psyche'
import { useNameRoll } from './rollName'
import { Portrait } from './Portrait'
import { AppPicks, listed, type Begun } from './Start'
import { FormAudit } from './Audit'
import { Schedule, scheduleProblems } from './Schedule'
import { Sliders } from './Sliders'
import { draftStore } from './drafts'

const LIFESPANS: [string, string][] = [['', 'As long as their kind does'], ['0', "Doesn't age"], ['80', 'About 80 years'],
  ['150', 'About 150 years'], ['300', 'About 300 years'], ['600', 'About 600 years'], ['1000', 'About 1,000 years']]
const LOOKS: [keyof Looks, string][] = [['build', 'Build'], ['skin', 'Skin'], ['face', 'Face'], ['jaw', 'Jaw'], ['nose', 'Nose'],
  ['eyes', 'Eyes'], ['eye_shape', 'Eye shape'], ['hair', 'Hair'], ['facial_hair', 'Facial hair'], ['feature', 'Something people notice']]
/** Where a draft's Details came from, as the sliders say it (src/Sliders.tsx). */
const LOOKS_FROM = { idea: 'From their words', rolled: 'Rolled' }
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
  /** Fields the model's draft left empty, said at the top so a blank section is never a quiet failure. */
  missing?: string[]
  /** Fields the model wrote past their limit, which end at the last sentence that fit (dramatis/drafting.py `cut`). */
  shortened?: string[]
  /** No model wrote them (brought from another app as written): the audit reads only what a model writes from here,
   * and their sliders stay In between where their words don't say. `allowed` is the user's own text they came from. */
  brought?: boolean; allowed?: string
  /** A picture to save with them, as base64 PNG: an imported file's own. */
  portrait?: string
  /** Where the form keeps its unsaved changes (src/drafts.ts): their id, or a new form's own key; `begun` is how it
   * opened, kept with the draft. */
  draftKey: string; begun: Begun
  onSaved: (saved: Saved) => void; onDeleted: () => void
  /** Drop the unsaved changes: back to what was saved, or the form goes for a new one. */
  onDiscard: () => void
}

const asSaved = (character: Character) => JSON.stringify(cleaned(character))
/** Whether a new form holds anything worth keeping as a draft. */
const begunOn = (character: Character) => !!(character.name.trim() || character.about.trim() || character.personality.trim() || character.background.trim())

const ZONES: string[] = (() => { try { return Intl.supportedValuesOf('timeZone') } catch { return [] } })()

/** One character, every field, for whichever apps they are made for. What a model writes goes into its field as a
 * proposal to keep or put back (src/proposals.ts); nothing is saved until Save. */
export function Editor({ saved, start, seed, filledIn, missing, shortened, note, portrait, brought, allowed, draftKey, begun, onSaved, onDeleted, onDiscard }: Props) {
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
  const rollName = useNameRoll(character.name, (name) => set({ name }), () => ({
    gender: character.gender, age: character.age, setting: character.setting, about: character.about,
  }))
  // Setting a Details field makes it the user's own: its Rolled or From their words mark goes.
  const setLook = <K extends keyof Looks>(key: K, value: Looks[K]) => setCharacter((current) => {
    const { [key]: _gone, ...from } = current.looks_from ?? {}
    return { ...current, looks: { ...current.looks, [key]: value }, looks_from: from }
  })
  const lookFrom = (key: keyof Looks) => { const from = character.looks_from?.[key]; return from && LOOKS_FROM[from] }
  const setLife = (change: Partial<Character['companion']>) => setCharacter((current) => ({ ...current, companion: { ...current.companion, ...change } }))
  const current = () => cleaned(character)
  const has = (app: App) => character.apps.includes(app)
  const persona = character.companion.relationship === 'persona'
  const assisting = useAssistantShown()
  const waiting = useOpenCount()
  useProposalForm(character, setCharacter, draftKey)
  // What Save would change: the form against the character as last saved (or saved from here).
  const baseline = useRef(saved ? asSaved(saved.character) : null)
  const settled = useRef(false)
  const [key, setKey] = useState(draftKey)
  const changed = baseline.current === null ? begunOn(character) : asSaved(character) !== baseline.current
  useEffect(() => {
    draftStore.put({ key, saved, begun: { ...begun, character, filledIn: undefined, missing: undefined, shortened: undefined, note: undefined }, changed })
  }, [character, saved, key, changed]) // eslint-disable-line react-hooks/exhaustive-deps
  const written = useWritten()
  // A split's fields that the user's text said nothing about go onto the form as proposals, from empty.
  useEffect(() => {
    const form = proposals.form()
    if (!form || !filledIn?.length) return
    for (const field of filledIn) {
      const path = pathOf(field)
      const value = valueAt(form.get(), path)
      if (isEmpty(value)) continue
      form.set(withValue(form.get(), path, Array.isArray(value) ? [] : typeof value === 'string' ? '' : null))
      const label = document.querySelector(`.editor [data-field="${CSS.escape(field)}"] .field-top > :is(label, .label)`)?.textContent ?? field
      proposals.propose({ field, label, value, source: 'split', hits: [] })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  // What a draft left empty or wrote too long for, by the form's own words: a whole section by its title, else each
  // field's label.
  useEffect(() => {
    const labelOf = (field: string) => document.querySelector(`.editor [data-field="${CSS.escape(field)}"] .field-top > :is(label, .label)`)?.textContent ?? field
    const named = (missing ?? []).map((field) => {
      const fold = document.querySelector(`.editor [data-field="${CSS.escape(field)}"]`)?.closest('details.fold')
      const all = [...fold?.querySelectorAll('[data-field]') ?? []].map((item) => item.getAttribute('data-field') ?? '')
      if (fold && all.every((item) => missing!.includes(item))) return fold.querySelector('summary')?.textContent?.trim() ?? field
      return labelOf(field)
    })
    const said = [
      named.length ? `Your model left ${listed([...new Set(named)])} empty.` : '',
      shortened?.length ? `${named.length ? 'It' : 'Your model'} wrote more than ${listed(shortened.map(labelOf))} ${shortened.length === 1 ? 'holds' : 'hold'}, so ${shortened.length === 1 ? 'it ends' : 'each ends'} at the last sentence that fit.` : '',
    ].filter(Boolean)
    if (said.length) setResult(named.length ? { tone: 'error', text: said.join(' ') } : { tone: 'note', text: [note, ...said].filter(Boolean).join(' ') })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // What each app's own models make of the form, a moment after the last change.
  useEffect(() => {
    const timer = setTimeout(() => {
      sendJson<{ problems: Problems; audit: AuditHit[] }>('/api/check', 'POST', { character: cleaned(character), fields: brought ? written : null, allowed: allowed ?? '' })
        .then((found) => { setProblems(found.problems); setAudit(found.audit); setCheckError('') })
        .catch((failure: Error) => setCheckError(failure.message))
    }, 500)
    return () => clearTimeout(timer)
  }, [character, written]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    try {
      // Saving keeps what the form shows, proposals included.
      const kept = proposals.keepAll()
      const sent = proposals.form()?.get() ?? character
      const body = { character: cleaned(sent), seed }
      let next = saved ? await sendJson<Saved>(`/api/characters/${saved.id}`, 'PUT', body) : await sendJson<Saved>('/api/characters', 'POST', body)
      // They are in the library from here: the form knows their id before the portrait goes, so a portrait that fails
      // never makes the next Save post a second copy.
      baseline.current = asSaved(sent)
      if (key !== next.id) { draftStore.drop(key); setKey(next.id) }
      let unpictured = ''
      if (pendingPortrait) {
        try {
          const pictured = await sendJson<Saved>(`/api/characters/${next.id}/portrait`, 'PUT', { filename: 'portrait.png', data: pendingPortrait })
          next = { ...pictured, problems: next.problems }
          setPendingPortrait(null)
        } catch (failure) {
          unpictured = failure instanceof Error ? failure.message : 'The portrait could not be saved.'
        }
      }
      onSaved(next)
      await client.invalidateQueries({ queryKey: ['characters'] })
      const name = next.character.name || 'them'
      const proposed = kept === 1 ? ', with the proposal that was waiting' : kept ? `, with the ${kept} proposals that were waiting` : ''
      setResult(unpictured
        ? { tone: 'error', text: `Saved ${name}, but not their portrait: ${unpictured.replace(/\.$/, '')}. Save again to try it again.` }
        : { tone: 'note', text: `Saved ${name}${proposed}.` })
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'They could not be saved.' })
    } finally { setBusy(false) }
  }
  const discard = () => {
    const what = saved ? `Put ${saved.character.name || 'them'} back as last saved, and lose the changes since?` : `Discard ${character.name || 'this new character'}? They were never saved.`
    if (!window.confirm(what)) return
    proposals.putBackAll()
    draftStore.drop(key)
    onDiscard()
  }
  const remove = async () => {
    if (!saved || !window.confirm(`Delete ${saved.character.name || 'this character'} from the library? Cards you exported stay where they are.`)) return
    await sendJson(`/api/characters/${saved.id}`, 'DELETE')
    draftStore.drop(key)
    proposals.forget(key)
    await client.invalidateQueries({ queryKey: ['characters'] })
    onDeleted()
  }

  const said = sampleLine(character.interview, sample)
  const blocked = has('companion') && scheduleProblems(character.companion.schedule).length > 0
  const zones = ZONES.includes(character.companion.timezone) || !character.companion.timezone ? ZONES : [character.companion.timezone, ...ZONES]
  return (
    <form className="editor" onSubmit={submit} onFocus={(event) => trackFocus(event.target)}>
      <div className="editor-head">
        <h2>{character.name || 'New character'}</h2>
        <div className="row">
          {waiting > 0 && <span className="muted small">{waiting === 1 ? '1 proposal waiting' : `${waiting} proposals waiting`}</span>}
          <button type="button" aria-pressed={assisting} onClick={() => assistant.toggle()}><MessageSquareText size={14} aria-hidden /> Assistant</button>
          {changed && <button type="button" className="quiet" onClick={discard}>{saved ? 'Discard changes' : 'Discard'}</button>}
          <button type="submit" className="primary" disabled={busy || blocked || (!!saved && !changed && !waiting && !pendingPortrait)}>{busy ? 'Saving…' : saved ? 'Save' : 'Save to the library'}</button>
          {saved && <>
            <ExportCard id={saved.id} />
            <button type="button" className="icon danger" aria-label="Delete them" onClick={() => void remove()}><Trash2 size={15} /></button>
          </>}
        </div>
      </div>
      {result && <p className={result.tone} role="status">{result.text}</p>}
      <WorksIn apps={character.apps} problems={problems} error={checkError} saved={!!saved} />
      <FormAudit hits={audit} ignored={character.ignored_flags ?? []} allowed={allowed ?? ''} onIgnored={(ignored_flags) => set({ ignored_flags })} />

      <section>
        <h3>Who they are</h3>
        <div className="portrait-row">
          <Portrait saved={saved} name={character.name} character={current} pending={pendingPortrait} onPending={setPendingPortrait}
            onSaved={(next) => onSaved({ ...next, problems })} />
          <div className="stack grow">
            <div className="grid three">
              <TextInput name="name" label="Name" value={character.name} onChange={(name) => set({ name })} maxLength={80} roll={rollName} />
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
        <TextArea name="about" label="About them" write="about them" value={character.about} onChange={(about) => set({ about })} maxLength={2000} rows={3} />
        <TextArea name="personality" label="Personality" write="their personality" value={character.personality} onChange={(personality) => set({ personality })} maxLength={8000} rows={4} />
        <div className="grid two">
          <div className="stack tight">
            <TextArea name="voice" label="How they talk" write="how they talk" value={character.voice} onChange={(voice) => set({ voice })} maxLength={600} rows={3} />
            {said && <q className="sample">{said}</q>}
          </div>
          <TextArea name="sound" label="How they sound aloud" write="how they sound aloud" value={character.sound} onChange={(sound) => set({ sound })} maxLength={300} rows={3} />
        </div>
      </section>

      <section>
        <h3>How they come across</h3>
        <div className="grid two">
          <TextArea name="seen_as" label="How others see them" write="how others see them" value={character.seen_as} onChange={(seen_as) => set({ seen_as })} maxLength={400} rows={3} />
          <TextArea name="sees_self" label="How they see themselves" write="how they see themselves" value={character.sees_self} onChange={(sees_self) => set({ sees_self })} maxLength={1200} rows={3} />
        </div>
      </section>

      <section>
        <h3>Personality</h3>
        <Sliders character={current} seed={seed} still={brought} onChange={(personality_sliders) => {
          // An older character saved before sliders were kept settles them on opening: that is not a change.
          if (!settled.current && saved && !saved.character.personality_sliders && baseline.current === asSaved(saved.character)) {
            baseline.current = asSaved({ ...saved.character, personality_sliders })
          }
          settled.current = true
          set({ personality_sliders })
        }} />
      </section>

      <section>
        <h3>Their story</h3>
        <TextArea name="background" label="Background" write="their background" value={character.background} onChange={(background) => set({ background })} maxLength={12000} rows={5} />
        <div className="grid two">
          <TextArea name="wants" label="What they want" write="what they want" value={character.wants} onChange={(wants) => set({ wants })} maxLength={300} rows={2} />
          <TextArea name="fears" label="What they fear" write="what they fear" value={character.fears} onChange={(fears) => set({ fears })} maxLength={300} rows={2} />
        </div>
        <div className="grid three">
          <ListField name="skills" label="Skills" write="skills" add="Add a skill" itemLength={300} value={character.skills} onChange={(skills) => set({ skills })} />
          <ListField name="flaws" label="Flaws" write="flaws" add="Add a flaw" itemLength={300} value={character.flaws} onChange={(flaws) => set({ flaws })} />
          <ListField name="interests" label="Interests" write="interests" add="Add an interest" value={character.interests} onChange={(interests) => set({ interests })} />
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
        <TextArea name="appearance" label="Appearance" write="their appearance" value={character.appearance} onChange={(appearance) => set({ appearance })} maxLength={600} rows={2} />
        <div className="folds">
          <Fold title="Details" filled={Object.values(character.looks).some((value) => value !== null && value !== '')}>
            <div className="grid three">
              <Field label="Height (cm)" from={lookFrom('height_cm')}>{(id) => <input id={id} type="number" min={120} max={230} value={character.looks.height_cm ?? ''} onChange={(event) => setLook('height_cm', event.target.value ? Number(event.target.value) : null)} />}</Field>
              <Field label="Weight (kg)" from={lookFrom('weight_kg')}>{(id) => <input id={id} type="number" min={35} max={250} value={character.looks.weight_kg ?? ''} onChange={(event) => setLook('weight_kg', event.target.value ? Number(event.target.value) : null)} />}</Field>
              {LOOKS.map(([key, label]) => (
                <TextInput key={key} label={label} value={String(character.looks[key] ?? '')} maxLength={key === 'hair' || key === 'feature' ? 200 : 120}
                  from={lookFrom(key)} onChange={(value) => setLook(key, value)} />
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
                {RELATIONSHIPS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
              </select>
            )}</Field>
            {!persona && <Field label="How close you start">{(id) => (
              <select id={id} value={character.companion.starting_closeness} onChange={(event) => setLife({ starting_closeness: Number(event.target.value) })}>
                {STAGES.map((stage, index) => <option key={stage} value={index + 1}>{stage}</option>)}
              </select>
            )}</Field>}
          </div>
          {!persona && <>
            <TextArea name="history_together" label="How you know each other" value={character.companion.history_together} onChange={(history_together) => setLife({ history_together })} maxLength={2000} rows={2} />
            <TextArea name="routine" label="Their routine" write="their routine" value={character.companion.routine} onChange={(routine) => setLife({ routine })} maxLength={8000} rows={3} />
            <Field name="schedule" label="Their week" write="their week" filled={character.companion.schedule.length > 0} group>{() => (
              <Schedule blocks={character.companion.schedule} onChange={(schedule) => setLife({ schedule })} />
            )}</Field>
            <ListField name="life_themes" label="Life themes" write="life themes" add="Add a life theme" value={character.companion.life_themes} onChange={(life_themes) => setLife({ life_themes })} />
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
            <Field name="emotional_traits" label="Emotional edges" filled={character.companion.emotional_traits.length > 0} group>{() => (
              <EmotionalEdges edges={character.companion.emotional_traits} onChange={(emotional_traits) => setLife({ emotional_traits })} />
            )}</Field>
            <TextArea name="absence_reaction" label="When you are away" value={character.companion.absence_reaction} onChange={(absence_reaction) => setLife({ absence_reaction })} maxLength={2000} rows={2} />
          </>}
        </section>
      )}
    </form>
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
