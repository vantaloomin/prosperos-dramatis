/** The form's sections below Who they are and the sliders, one component each. Each gets the character as the form
 * has it and changes it through `set` (a few fields) or `update` (a change made from the latest form). */
import { EmotionalEdges } from '../EmotionalEdges'
import { Field, Fold, ListField, TextArea, TextInput } from '../Fields'
import { FromTheirCard } from '../FromTheirCard'
import { InnerLife, SecretSection } from '../InnerLife'
import { Interview } from '../Interview'
import { Psyche } from '../Psyche'
import { Schedule } from '../Schedule'
import { RELATIONSHIPS, type Character, type Looks, type Relationship } from '../api'

type Set = (change: Partial<Character>) => void
type Update = (change: (character: Character) => Character) => void

const LOOKS: [keyof Looks, string][] = [['build', 'Build'], ['skin', 'Skin'], ['face', 'Face'], ['jaw', 'Jaw'], ['nose', 'Nose'],
  ['eyes', 'Eyes'], ['eye_shape', 'Eye shape'], ['hair', 'Hair'], ['facial_hair', 'Facial hair'], ['feature', 'Something people notice']]
/** Where a draft's Details came from, as the sliders say it (src/Sliders.tsx). */
const LOOKS_FROM = { idea: 'From their words', rolled: 'Rolled' }
const STAGES = ['Just met', 'Getting to know each other', 'Friends', 'Close', 'Very close']
const ZONES: string[] = (() => { try { return Intl.supportedValuesOf('timeZone') } catch { return [] } })()

export function ComesAcross({ character, set }: { character: Character; set: Set }) {
  return (
    <section>
      <h3>How they come across</h3>
      <div className="grid two">
        <TextArea name="seen_as" label="How others see them" write="how others see them" value={character.seen_as} onChange={(seen_as) => set({ seen_as })} maxLength={400} rows={3} />
        <TextArea name="sees_self" label="How they see themselves" write="how they see themselves" value={character.sees_self} onChange={(sees_self) => set({ sees_self })} maxLength={1200} rows={3} />
      </div>
    </section>
  )
}

export function Story({ character, set }: { character: Character; set: Set }) {
  return (
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
  )
}

export function Depth({ character, set, ready, selfId, onSample }: { character: Character; set: Set; ready: boolean; selfId?: string; onSample: (sample: string) => void }) {
  return (
    <section>
      <h3>Depth</h3>
      <div className="folds">
        <Interview character={character} ready={ready} set={set} onSample={onSample} />
        <InnerLife arc={character.arc} onChange={(arc) => set({ arc })} />
        <Psyche psyche={character.psyche} selfId={selfId} onChange={(psyche) => set({ psyche })} />
        <SecretSection secret={character.secret} onChange={(secret) => set({ secret })} />
      </div>
    </section>
  )
}

export function HowTheyLook({ character, set, update }: { character: Character; set: Set; update: Update }) {
  // Setting a Details field makes it the user's own: its Rolled or From their words mark goes.
  const setLook = <K extends keyof Looks>(key: K, value: Looks[K]) => update((current) => {
    const { [key]: _gone, ...from } = current.looks_from ?? {}
    return { ...current, looks: { ...current.looks, [key]: value }, looks_from: from }
  })
  const lookFrom = (key: keyof Looks) => { const from = character.looks_from?.[key]; return from && LOOKS_FROM[from] }
  return (
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
  )
}

/** Companion's everyday life with the user; a user persona has none, only the relationship. */
export function ForCompanion({ character, update }: { character: Character; update: Update }) {
  const setLife = (change: Partial<Character['companion']>) => update((current) => ({ ...current, companion: { ...current.companion, ...change } }))
  const persona = character.companion.relationship === 'persona'
  const zones = ZONES.includes(character.companion.timezone) || !character.companion.timezone ? ZONES : [character.companion.timezone, ...ZONES]
  return (
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
  )
}
