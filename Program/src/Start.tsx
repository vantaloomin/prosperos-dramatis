import { useRef, useState, type FormEvent } from 'react'
import { ClipboardPaste, FileUp, Sparkles } from 'lucide-react'
import { APPS, APP_NAMES, emptyCharacter, fileData, sendJson, type App, type Character, type Drafted, type Gender, type Opened, type OpenedFile, type Relationship } from './api'
import { Field, TextArea, TextInput, useModelReady } from './Fields'

/** How the form opens: the character, and a portrait (base64 PNG) to save with them, such as an imported file's picture. */
export interface Begun { character: Character; seed?: string; filledIn?: string[]; note?: string; portrait?: string }
/** Picks the quick start opens with, such as the idea the Cast board writes for a corner. */
export interface Picks { idea?: string; setting?: string }

const AGES = [['', 'Any age'], ['24', 'Mid-twenties'], ['32', 'Early thirties'], ['38', 'Late thirties'], ['45', 'Mid-forties'],
  ['55', 'Mid-fifties'], ['65', 'Sixties'], ['75', 'Seventies']] as const
const RELATIONSHIPS: [Relationship, string][] = [['friendship', 'Friendship'], ['romance', 'Romance'], ['mentor', 'Mentor'],
  ['family', 'Family'], ['other', 'Something else']]
const VIBES = ['Dry humour', 'Warm', 'Blunt', 'Shy', 'Chatty', 'Restless', 'Old-fashioned', 'Night owl', 'Outdoorsy', 'Bookish']

export function AppPicks({ apps, onChange }: { apps: App[]; onChange: (apps: App[]) => void }) {
  const toggle = (app: App) => {
    const next = apps.includes(app) ? apps.filter((item) => item !== app) : APPS.filter((item) => item === app || apps.includes(item))
    if (next.length) onChange(next)
  }
  return (
    <fieldset className="apps">
      <legend>Made for</legend>
      {APPS.map((app) => (
        <label key={app} className="check"><input type="checkbox" checked={apps.includes(app)} onChange={() => toggle(app)} /> {APP_NAMES[app]}</label>
      ))}
    </fieldset>
  )
}

/** The quick start: a few picks, and the user's model writes the rest for review. Nothing is saved before the form. */
function QuickStart({ initial, onBegin }: { initial?: Picks; onBegin: (begun: Begun) => void }) {
  const ready = useModelReady()
  const [picks, setPicks] = useState({ name: '', gender: '' as Gender, age: '', setting: '', idea: '', vibe: '', relationship: 'friendship' as Relationship, emotional_edges: false, ...initial })
  const [apps, setApps] = useState<App[]>(APPS)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (change: Partial<typeof picks>) => setPicks((current) => ({ ...current, ...change }))
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const found = await sendJson<Drafted>('/api/draft', 'POST', {
        ...picks, age: picks.age ? Number(picks.age) : null, apps, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? '',
      })
      onBegin({ character: found.character, seed: found.seed, note: 'Your model drafted them. Read it through, change anything, then save.' })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The draft could not be written.')
    } finally { setBusy(false) }
  }
  const vibes = picks.vibe.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean)
  const toggleVibe = (vibe: string) => set({
    vibe: vibes.includes(vibe.toLowerCase()) ? picks.vibe.split(',').map((item) => item.trim()).filter((item) => item && item.toLowerCase() !== vibe.toLowerCase()).join(', ')
      : [picks.vibe.trim(), vibe].filter(Boolean).join(', '),
  })
  return (
    <section className="card" aria-labelledby="quick-title">
      <h2 id="quick-title"><Sparkles size={16} aria-hidden /> A few things to start</h2>
      <p className="muted">Your model writes the rest: who they are, their voice, skills, flaws, what they want and fear, and, for Companion, their week. You see the whole character before anything is saved.</p>
      {!ready && <p className="note">Drafting uses your model, and none is set up yet. Set one up above, or fill in the form yourself.</p>}
      <form className="stack" onSubmit={submit}>
        <div className="grid three">
          <TextInput label="Name" value={picks.name} onChange={(name) => set({ name })} maxLength={80} hint="Optional. Left empty, they get one that fits." />
          <Field label="Gender">{(id) => (
            <select id={id} value={picks.gender} onChange={(event) => set({ gender: event.target.value as Gender })}>
              <option value="">Any</option><option value="woman">Woman</option><option value="man">Man</option><option value="nonbinary">Nonbinary</option>
            </select>
          )}</Field>
          <Field label="Age" hint="Characters are always adults.">{(id) => (
            <select id={id} value={picks.age} onChange={(event) => set({ age: event.target.value })}>
              {AGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
            </select>
          )}</Field>
        </div>
        <TextInput label="Where and when" value={picks.setting} onChange={(setting) => set({ setting })} maxLength={200}
          placeholder="Baltimore, today · a frontier town in 1870 · a generation ship" hint="Optional. Each app can still move them into its own world." />
        <AppPicks apps={apps} onChange={setApps} />
        <details className="more" open={!!initial?.idea || undefined}>
          <summary>More options</summary>
          <div className="stack">
            <TextArea label="Who are they?" value={picks.idea} onChange={(idea) => set({ idea })} maxLength={2000} rows={2}
              placeholder="A night-shift nurse who is trying to get back into running" hint="Leave it empty to be surprised." />
            <div className="vibes">
              <TextInput label="Vibe" value={picks.vibe} onChange={(vibe) => set({ vibe })} maxLength={300} hint="Pick a few or write your own, separated by commas." />
              <div className="row" role="group" aria-label="Vibe suggestions">
                {VIBES.map((vibe) => <button key={vibe} type="button" className="chip" aria-pressed={vibes.includes(vibe.toLowerCase())} onClick={() => toggleVibe(vibe)}>{vibe}</button>)}
              </div>
            </div>
            {apps.includes('companion') && <>
              <Field label="Relationship in Companion" hint="Someone you haven't met yet starts as a friendship. Romance starts only with your yes.">{(id) => (
                <select id={id} value={picks.relationship} onChange={(event) => set({ relationship: event.target.value as Relationship })}>
                  {RELATIONSHIPS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
                </select>
              )}</Field>
              <label className="check"><input type="checkbox" checked={picks.emotional_edges} onChange={(event) => set({ emotional_edges: event.target.checked })} /> Give them emotional edges, such as jealousy or missing you when you are away</label>
            </>}
          </div>
        </details>
        {busy && <p className="note">Writing them. A local model can take a minute or two.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button type="submit" className="primary" disabled={!ready || busy}>{busy ? 'Writing…' : 'Write them'}</button>
          <button type="button" className="link" onClick={() => onBegin({ character: emptyCharacter(apps) })}>Fill in the form myself</button>
        </div>
      </form>
    </section>
  )
}

/** "a, b and c" */
export const listed = (items: string[]) => items.length < 2 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`

const instructionsNote = (lines?: string[]) => lines?.length
  ? ` Their text had lines that talk to the app or the model rather than describe them (“${lines.join('”, “')}”). The model was told to ignore them; check the fields before you save.`
  : ''

/** A character the user already has: pasted, or a character file from another app (Companion's importer reads it). A
 * file opens in the form as it has them, with no model, or goes into the box to split into the fields with the model;
 * either way, its greetings, lorebook and picture stay with them. A card Dramatis made opens whole. */
function PasteCharacter({ onBegin }: { onBegin: (begun: Begun) => void }) {
  const ready = useModelReady()
  const input = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [file, setFile] = useState<OpenedFile | null>(null)
  const [apps, setApps] = useState<App[]>(APPS)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? ''
  const write = (value: string) => {
    setText(value)
    if (!value.trim()) setFile(null)
  }
  const open = async (picked: File | undefined) => {
    if (!picked) return
    setBusy('Reading…')
    setError('')
    try {
      const found = await sendJson<Opened | OpenedFile>('/api/cards/open', 'POST', { filename: picked.name, data: await fileData(picked) })
      if (found.kind === 'character') {
        onBegin({ character: found.character, note: `${found.character.name || 'They'} came back whole from a card Dramatis made. Save to keep them here.` })
        return
      }
      setText(found.text)
      setFile(found)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That file could not be read.')
    } finally {
      setBusy('')
      if (input.current) input.current.value = ''
    }
  }
  // What came with the file stays with them whichever way the form is filled.
  const withFile = (character: Character): Character => ({ ...character, card: file?.card ?? character.card ?? null })
  const asRead = file?.character && text === file.text ? file.character : null
  const openAsRead = () => asRead && onBegin({
    character: withFile({ ...asRead, apps, companion: { ...asRead.companion, timezone: asRead.companion.timezone || timezone } }),
    portrait: file?.portrait ?? undefined,
    note: `${asRead.name || 'They'} opened as the file has them. Read the fields through, fill in the rest, then save.${instructionsNote(file?.instructions)}`,
  })
  const split = async () => {
    setBusy('Splitting…')
    setError('')
    try {
      const found = await sendJson<Drafted>('/api/draft/split', 'POST', { text, apps, timezone })
      onBegin({ character: withFile(found.character), seed: found.seed, filledIn: found.filled_in, portrait: file?.portrait ?? undefined,
        note: `Your character, split into the fields.${instructionsNote(found.instructions)}` })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The character could not be split.')
    } finally { setBusy('') }
  }
  const kept = file?.kept.length ? ` Their ${listed(file.kept)} stay with them for the cards you export.` : ''
  return (
    <section className="card" aria-labelledby="paste-title">
      <h2 id="paste-title"><ClipboardPaste size={16} aria-hidden /> Or bring a character you already have</h2>
      <p className="muted">Notes, a bio, a scene, or a character file from SillyTavern, Chub, Backyard, Marinara or another app: a card (PNG or JSON), CHARX, BYAF or plain JSON. Nothing in a file runs, no picture is fetched, and you see exactly what goes to your model before anything does.</p>
      <input ref={input} type="file" accept=".png,.json,.charx,.byaf,.txt,.md" hidden onChange={(event) => {
        const picked = event.target.files?.[0]
        if (picked && /\.(txt|md)$/i.test(picked.name)) {
          setFile(null)
          void picked.text().then((value) => setText(value.slice(0, 40000)))
          return
        }
        void open(picked)
      }} />
      <div className="stack">
        <TextArea label="Their character" value={text} onChange={write} maxLength={40000} rows={8} />
        <AppPicks apps={apps} onChange={setApps} />
        {file && (
          <p className="note">
            Read {file.name || 'them'} from {file.format === 'JSON' ? 'a JSON file' : `a ${file.format} file`}.{kept}
            {file.truncated && ' The text was long, so only its first 40,000 characters are in the box.'}
            {file.notes.map((note) => ` ${note}`).join('')}
            {file.instructions.length > 0 && ` Lines in it talk to the app or the model rather than describe them (“${file.instructions.join('”, “')}”).`}
          </p>
        )}
        {file?.refused && <p className="error" role="alert">{file.refused}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button type="button" disabled={!!busy} onClick={() => input.current?.click()}><FileUp size={14} aria-hidden /> Open a character file</button>
          {asRead && <button type="button" className="primary" disabled={!!busy} onClick={openAsRead}>Open in the form</button>}
          <button type="button" className={asRead ? undefined : 'primary'} disabled={!ready || !text.trim() || !!busy} onClick={() => void split()}>{busy === 'Splitting…' ? busy : 'Split into fields'}</button>
        </div>
      </div>
    </section>
  )
}

export function Start({ initial, onBegin }: { initial?: Picks; onBegin: (begun: Begun) => void }) {
  return (
    <div className="start">
      <QuickStart initial={initial} onBegin={onBegin} />
      <PasteCharacter onBegin={onBegin} />
    </div>
  )
}
