import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Download, ImagePlus, Trash2, TriangleAlert } from 'lucide-react'
import { APPS, APP_NAMES, fileData, sendJson, type App, type Character, type Gender, type Looks, type Problems, type Relationship, type Saved } from './api'
import { Field, HelpMeWrite, ListArea, TextArea, TextInput, cleanList, useModelReady } from './Fields'
import { AppPicks } from './Start'
import { Schedule, scheduleProblems } from './Schedule'
import { Sliders } from './Sliders'

const LIFESPANS: [string, string][] = [['', 'As long as their kind does'], ['0', "Doesn't age"], ['80', 'About 80 years'],
  ['150', 'About 150 years'], ['300', 'About 300 years'], ['600', 'About 600 years'], ['1000', 'About 1,000 years']]
const LOOKS: [keyof Looks, string][] = [['build', 'Build'], ['skin', 'Skin'], ['face', 'Face'], ['jaw', 'Jaw'], ['nose', 'Nose'],
  ['eyes', 'Eyes'], ['eye_shape', 'Eye shape'], ['hair', 'Hair'], ['facial_hair', 'Facial hair'], ['feature', 'Something people notice']]
const STAGES = ['Just met', 'Getting to know each other', 'Friends', 'Close', 'Very close']

/** The form as the server takes it: lists without blank lines, numbers as numbers. */
export function cleaned(character: Character): Character {
  return {
    ...character, skills: cleanList(character.skills), flaws: cleanList(character.flaws), interests: cleanList(character.interests),
    companion: { ...character.companion, life_themes: cleanList(character.companion.life_themes) },
  }
}

interface Props {
  saved: Saved | null; start: Character; seed: string; filledIn?: string[]; note?: string
  onSaved: (saved: Saved) => void; onDeleted: () => void
}

/** One character, every field, for whichever apps they are made for. Nothing is saved until Save. */
export function Editor({ saved, start, seed, filledIn, note, onSaved, onDeleted }: Props) {
  const client = useQueryClient()
  const ready = useModelReady()
  const [character, setCharacter] = useState<Character>(start)
  const [problems, setProblems] = useState<Problems>(saved?.problems ?? {})
  const [checkError, setCheckError] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ tone: 'note' | 'error'; text: string } | null>(note ? { tone: 'note', text: note } : null)
  const [portraitAt, setPortraitAt] = useState(Date.now())
  const picture = useRef<HTMLInputElement>(null)
  const set = (change: Partial<Character>) => setCharacter((current) => ({ ...current, ...change }))
  const setLife = (change: Partial<Character['companion']>) => setCharacter((current) => ({ ...current, companion: { ...current.companion, ...change } }))
  const current = () => cleaned(character)
  const has = (app: App) => character.apps.includes(app)

  // What each app's own models make of the form, a moment after the last change.
  useEffect(() => {
    const timer = setTimeout(() => {
      sendJson<{ problems: Problems }>('/api/check', 'POST', { character: cleaned(character) })
        .then((found) => { setProblems(found.problems); setCheckError('') })
        .catch((failure: Error) => setCheckError(failure.message))
    }, 500)
    return () => clearTimeout(timer)
  }, [character])

  const help = <T,>(field: string, label: string, value: T, apply: (value: T) => void): ReactNode =>
    ready ? <HelpMeWrite field={field} label={label} character={current} current={value} apply={apply} /> : null

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    try {
      const body = { character: cleaned(character), seed }
      const next = saved ? await sendJson<Saved>(`/api/characters/${saved.id}`, 'PUT', body) : await sendJson<Saved>('/api/characters', 'POST', body)
      await client.invalidateQueries({ queryKey: ['characters'] })
      setResult({ tone: 'note', text: `Saved ${next.character.name || 'them'}.` })
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
  const setPortrait = async (file: File | undefined) => {
    if (!saved || !file) return
    try {
      const next = await sendJson<Saved>(`/api/characters/${saved.id}/portrait`, 'PUT', { filename: file.name, data: await fileData(file) })
      onSaved({ ...next, problems })
      setPortraitAt(Date.now())
      await client.invalidateQueries({ queryKey: ['characters'] })
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'That picture could not be used.' })
    } finally { if (picture.current) picture.current.value = '' }
  }

  const filled = new Set(filledIn ?? [])
  const mark = (field: string, label: string) => filled.has(field) ? `${label} (filled in)` : label
  const blocked = has('companion') && scheduleProblems(character.companion.schedule).length > 0
  return (
    <form className="editor" onSubmit={submit}>
      <div className="editor-head">
        <h2>{character.name || 'New character'}</h2>
        <div className="row">
          <button type="submit" className="primary" disabled={busy || blocked}>{busy ? 'Saving…' : saved ? 'Save' : 'Save to the library'}</button>
          {saved && <>
            <a className="button" href={`/api/characters/${saved.id}/card.png`} download><Download size={14} aria-hidden /> Card (PNG)</a>
            <a className="button" href={`/api/characters/${saved.id}/card.json`} download><Download size={14} aria-hidden /> Card (JSON)</a>
            <button type="button" className="icon danger" aria-label="Delete them" onClick={() => void remove()}><Trash2 size={15} /></button>
          </>}
        </div>
      </div>
      {result && <p className={result.tone} role="status">{result.text}</p>}
      {filled.size > 0 && <p className="note">Their text said nothing about {[...filled].join(', ')}, so the model filled those in. Check them.</p>}
      <WorksIn apps={character.apps} problems={problems} error={checkError} saved={!!saved} />

      <section>
        <h3>Who they are</h3>
        <div className="portrait-row">
          {saved && (
            <div className="portrait">
              {saved.portrait ? <img src={`/api/characters/${saved.id}/portrait.png?at=${portraitAt}`} alt={`${character.name}'s portrait`} /> : <div className="no-portrait" aria-hidden />}
              <input ref={picture} type="file" accept=".png,image/png" hidden onChange={(event) => void setPortrait(event.target.files?.[0])} />
              <button type="button" className="link" onClick={() => picture.current?.click()}><ImagePlus size={13} aria-hidden /> {saved.portrait ? 'Change portrait' : 'Add a portrait'}</button>
            </div>
          )}
          <div className="stack grow">
            <div className="grid three">
              <TextInput label="Name" value={character.name} onChange={(name) => set({ name })} maxLength={80} />
              <Field label="Gender">{(id) => (
                <select id={id} value={character.gender} onChange={(event) => set({ gender: event.target.value as Gender })}>
                  <option value="">Not said</option><option value="woman">Woman</option><option value="man">Man</option><option value="nonbinary">Nonbinary</option>
                </select>
              )}</Field>
              <Field label="Age" hint="18 or older.">{(id) => (
                <input id={id} type="number" min={18} max={5000} value={character.age ?? ''} onChange={(event) => set({ age: event.target.value ? Number(event.target.value) : null })} />
              )}</Field>
            </div>
            <TextInput label="Where and when" value={character.setting} onChange={(setting) => set({ setting })} maxLength={200} placeholder="Baltimore, today" />
            <AppPicks apps={character.apps} onChange={(apps) => set({ apps })} />
          </div>
        </div>
        <TextArea label={mark('about', 'About them')} value={character.about} onChange={(about) => set({ about })} maxLength={2000} rows={3}
          hint="Who they are, what they do, who they live or travel with. Companion reads it as who they are; Adventure and Dungeon as About you."
          help={help('about', 'About them', character.about, (about) => set({ about }))} />
        <TextArea label={mark('personality', 'Personality')} value={character.personality} onChange={(personality) => set({ personality })} maxLength={8000} rows={4}
          help={help('personality', 'their personality', character.personality, (personality) => set({ personality }))} />
        <div className="grid two">
          <TextArea label={mark('voice', 'How they talk')} value={character.voice} onChange={(voice) => set({ voice })} maxLength={600} rows={3}
            hint="Their words, rhythm, humour and what they avoid saying: instructions for writing them." help={help('voice', 'how they talk', character.voice, (voice) => set({ voice }))} />
          <TextArea label={mark('sound', 'How they sound')} value={character.sound} onChange={(sound) => set({ sound })} maxLength={300} rows={3}
            hint="The voice itself, for text to speech: age, pitch, pace, texture. Not personality or their name." help={help('sound', 'how they sound', character.sound, (sound) => set({ sound }))} />
        </div>
      </section>

      <section>
        <h3>Personality sliders</h3>
        <Sliders character={current} seed={seed} onChange={(personality_sliders) => set({ personality_sliders })} />
      </section>

      <section>
        <h3>Their story</h3>
        <TextArea label={mark('background', 'Background')} value={character.background} onChange={(background) => set({ background })} maxLength={12000} rows={5}
          help={help('background', 'their background', character.background, (background) => set({ background }))} />
        <div className="grid two">
          <TextArea label={mark('wants', 'What they want')} value={character.wants} onChange={(wants) => set({ wants })} maxLength={300} rows={2}
            help={help('wants', 'what they want', character.wants, (wants) => set({ wants }))} />
          <TextArea label={mark('fears', 'What they fear')} value={character.fears} onChange={(fears) => set({ fears })} maxLength={300} rows={2}
            help={help('fears', 'what they fear', character.fears, (fears) => set({ fears }))} />
        </div>
        <div className="grid three">
          <ListArea label={mark('skills', 'Skills')} value={character.skills} onChange={(skills) => set({ skills })} help={help('skills', 'skills', character.skills, (skills) => set({ skills }))} />
          <ListArea label={mark('flaws', 'Flaws')} value={character.flaws} onChange={(flaws) => set({ flaws })} help={help('flaws', 'flaws', character.flaws, (flaws) => set({ flaws }))} />
          <ListArea label={mark('interests', 'Interests')} value={character.interests} onChange={(interests) => set({ interests })} help={help('interests', 'interests', character.interests, (interests) => set({ interests }))} />
        </div>
      </section>

      <section>
        <h3>How they look</h3>
        <TextArea label={mark('appearance', 'Appearance')} value={character.appearance} onChange={(appearance) => set({ appearance })} maxLength={600} rows={2}
          help={help('appearance', 'their appearance', character.appearance, (appearance) => set({ appearance }))} />
        <details>
          <summary>Looks, field by field</summary>
          <p className="muted small">So every picture shows the same person. A field left empty is drawn for them by the app they go to.</p>
          <div className="grid three">
            <Field label="Height (cm)">{(id) => <input id={id} type="number" min={120} max={230} value={character.looks.height_cm ?? ''} onChange={(event) => set({ looks: { ...character.looks, height_cm: event.target.value ? Number(event.target.value) : null } })} />}</Field>
            <Field label="Weight (kg)">{(id) => <input id={id} type="number" min={35} max={250} value={character.looks.weight_kg ?? ''} onChange={(event) => set({ looks: { ...character.looks, weight_kg: event.target.value ? Number(event.target.value) : null } })} />}</Field>
            {LOOKS.map(([key, label]) => (
              <TextInput key={key} label={label} value={String(character.looks[key] ?? '')} maxLength={key === 'hair' || key === 'feature' ? 200 : 120}
                onChange={(value) => set({ looks: { ...character.looks, [key]: value } })} />
            ))}
          </div>
        </details>
      </section>

      <details className="section">
        <summary>More about them</summary>
        <TextArea label="How others see them" value={character.seen_as} onChange={(seen_as) => set({ seen_as })} maxLength={400} rows={2}
          hint="One line: how they come across; a habit people notice; what sets them off. Left empty, the app fills it in." />
        <TextArea label="How they see themselves" value={character.sees_self} onChange={(sees_self) => set({ sees_self })} maxLength={1200} rows={3}
          hint="Private, a few first-person lines. Left empty, the app fills it in." />
        <div className="grid three">
          <TextInput label="Kind" value={character.kind} onChange={(kind) => set({ kind: kind.toLowerCase().replace(/[^a-z0-9-]/g, '') })} maxLength={40}
            hint="Empty for an ordinary human, else a word such as elf." />
          <Field label="How long they live">{(id) => (
            <select id={id} value={character.lifespan ?? ''} onChange={(event) => set({ lifespan: event.target.value === '' ? null : Number(event.target.value) })}>
              {LIFESPANS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          )}</Field>
          <Field label="Birthday" hint="Month and day, MM-DD.">{(id) => (
            <input id={id} value={character.birthday} maxLength={5} placeholder="04-21" onChange={(event) => set({ birthday: event.target.value })} />
          )}</Field>
        </div>
      </details>

      {has('companion') && (
        <section className="app-section">
          <h3>For Companion</h3>
          <div className="grid two">
            <Field label="Relationship" hint="Romance starts only with your yes.">{(id) => (
              <select id={id} value={character.companion.relationship} onChange={(event) => setLife({ relationship: event.target.value as Relationship })}>
                <option value="friendship">Friendship</option><option value="romance">Romance</option><option value="mentor">Mentor</option><option value="family">Family</option><option value="other">Something else</option>
              </select>
            )}</Field>
            <Field label="How close you start">{(id) => (
              <select id={id} value={character.companion.starting_closeness} onChange={(event) => setLife({ starting_closeness: Number(event.target.value) })}>
                {STAGES.map((stage, index) => <option key={stage} value={index + 1}>{stage}</option>)}
              </select>
            )}</Field>
          </div>
          <TextArea label="How you know each other" value={character.companion.history_together} onChange={(history_together) => setLife({ history_together })} maxLength={2000} rows={2} />
          <TextArea label={mark('routine', 'Their routine, in their words')} value={character.companion.routine} onChange={(routine) => setLife({ routine })} maxLength={8000} rows={3}
            help={help('routine', 'their routine', character.companion.routine, (routine) => setLife({ routine }))} />
          <Field label="Their week" help={help('schedule', 'their week', character.companion.schedule, (schedule) => setLife({ schedule }))}>{() => (
            <Schedule blocks={character.companion.schedule} onChange={(schedule) => setLife({ schedule })} />
          )}</Field>
          <ListArea label={mark('life_themes', 'Life themes')} value={character.companion.life_themes} onChange={(life_themes) => setLife({ life_themes })} rows={3}
            hint="What their everyday life tends to involve. One per line." help={help('life_themes', 'life themes', character.companion.life_themes, (life_themes) => setLife({ life_themes }))} />
          <TextInput label="Time zone" value={character.companion.timezone} onChange={(timezone) => setLife({ timezone })} maxLength={64} hint="Where their clock is, such as America/New_York." />
          <fieldset className="ticks">
            <legend>How they text</legend>
            {([['bursts', 'In bursts of short texts'], ['lowercase', 'All lowercase'], ['typos', 'With typos'], ['quick', 'Quick to reply']] as const).map(([key, label]) => (
              <label key={key} className="check"><input type="checkbox" checked={character.companion.texting[key]} onChange={(event) => setLife({ texting: { ...character.companion.texting, [key]: event.target.checked } })} /> {label}</label>
            ))}
          </fieldset>
          <TextArea label="When you are away" value={character.companion.absence_reaction} onChange={(absence_reaction) => setLife({ absence_reaction })} maxLength={2000} rows={2}
            hint="Empty means they are fine with time apart. Jealousy or missing you are yours to add." />
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
