import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { ClipboardPaste, FileUp, Square, UserPlus } from 'lucide-react'
import { APPS, APP_NAMES, RELATIONSHIPS, emptyCharacter, fileData, sendJson, type App, type Character, type Drafted, type Gender, type Opened, type OpenedFile, type Relationship } from './api'
import { Bolt, Field, Fold, TextArea, TextInput, useModelReady } from './Fields'
import { useModelCall } from './modelCall'
import { useNameRoll } from './rollName'
import { profileFor, useModels } from './models/ModelSettings'

/** How the form opens: the character, and a portrait (base64 PNG) to save with them, such as an imported file's picture. */
/** `filledIn` are the fields a split wrote that the user's text said nothing about; `missing` the ones a draft left
 * empty; `brought` says no model wrote any of it (a file used as written), and `allowed` is the user's own text it came
 * from, for the AI-slop audit. */
export interface Begun {
  character: Character; seed?: string; filledIn?: string[]; missing?: string[]; shortened?: string[]; note?: string; portrait?: string; brought?: boolean; allowed?: string
}
/** Picks the quick start opens with, such as the idea the Cast board writes for a corner. */
export interface Picks { idea?: string; setting?: string }

const AGES = [['', 'Any age'], ['24', 'Mid-twenties'], ['32', 'Early thirties'], ['38', 'Late thirties'], ['45', 'Mid-forties'],
  ['55', 'Mid-fifties'], ['65', 'Sixties'], ['75', 'Seventies']] as const
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

/** While a model works: what it is doing (the server's step when it has said one), with which model, and how long it
 * has been at it. */
export function Waiting({ job = 'writing', doing, step }: { job?: 'writing' | 'cast'; doing: string; step?: string }) {
  const model = profileFor(useModels().data, job)?.config.model
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const begun = Date.now()
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - begun) / 1000)), 1000)
    return () => clearInterval(timer)
  }, [])
  return <span className="muted small" role="status">{[step || doing, model, `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`].filter(Boolean).join(' · ')}</span>
}

/** The quick start: a few picks, and the user's model writes the rest for review. Nothing is saved before the form. */
function QuickStart({ initial, onBegin }: { initial?: Picks; onBegin: (begun: Begun) => void }) {
  const ready = useModelReady()
  const call = useModelCall()
  const [picks, setPicks] = useState({ name: '', gender: '' as Gender, age: '', setting: '', idea: '', vibe: '', relationship: 'friendship' as Relationship, emotional_edges: false, ...initial })
  const set = (change: Partial<typeof picks>) => setPicks((current) => ({ ...current, ...change }))
  const rollName = useNameRoll(picks.name, (name) => set({ name }), () => ({
    gender: picks.gender, age: picks.age ? Number(picks.age) : null, setting: picks.setting, about: `${picks.idea} ${picks.vibe}`,
  }))
  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    void call.run((signal) => sendJson<Drafted>('/api/draft', 'POST', {
      ...picks, age: picks.age ? Number(picks.age) : null, apps: APPS, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? '',
    }, signal), (found) => onBegin({ character: found.character, seed: found.seed, missing: found.missing, shortened: found.shortened, note: 'Your model drafted them. Read it through, change anything, then save.' }),
    'The draft could not be written.')
  }
  const vibes = picks.vibe.split(',').map((item) => item.trim().toLowerCase()).filter(Boolean)
  const toggleVibe = (vibe: string) => set({
    vibe: vibes.includes(vibe.toLowerCase()) ? picks.vibe.split(',').map((item) => item.trim()).filter((item) => item && item.toLowerCase() !== vibe.toLowerCase()).join(', ')
      : [picks.vibe.trim(), vibe].filter(Boolean).join(', '),
  })
  return (
    <section className="card" aria-labelledby="quick-title">
      <h2 id="quick-title"><UserPlus size={16} aria-hidden /> A new character</h2>
      {!ready && <p className="note">Set up a model at the top to draft with it, or fill in the form yourself.</p>}
      <form className="stack" onSubmit={submit}>
        <div className="grid three">
          <TextInput label="Name" value={picks.name} onChange={(name) => set({ name })} maxLength={80} roll={rollName} />
          <Field label="Gender">{(id) => (
            <select id={id} value={picks.gender} onChange={(event) => set({ gender: event.target.value as Gender })}>
              <option value="">Any</option><option value="woman">Woman</option><option value="man">Man</option><option value="nonbinary">Nonbinary</option>
            </select>
          )}</Field>
          <Field label="Age">{(id) => (
            <select id={id} value={picks.age} onChange={(event) => set({ age: event.target.value })}>
              {AGES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
            </select>
          )}</Field>
        </div>
        <TextInput label="Where and when" value={picks.setting} onChange={(setting) => set({ setting })} maxLength={200} />
        <Fold title="More options" filled={!!initial?.idea}>
          <TextArea label="Who are they?" value={picks.idea} onChange={(idea) => set({ idea })} maxLength={2000} rows={2} />
          <div className="vibes">
            <TextInput label="Vibe" value={picks.vibe} onChange={(vibe) => set({ vibe })} maxLength={300} />
            <div className="row" role="group" aria-label="Vibe suggestions">
              {VIBES.map((vibe) => <button key={vibe} type="button" className="chip" aria-pressed={vibes.includes(vibe.toLowerCase())} onClick={() => toggleVibe(vibe)}>{vibe}</button>)}
            </div>
          </div>
          <Field label="Relationship in Companion">{(id) => (
            <select id={id} value={picks.relationship} onChange={(event) => set({ relationship: event.target.value as Relationship })}>
              {RELATIONSHIPS.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
            </select>
          )}</Field>
          {picks.relationship !== 'persona' && <label className="check"><input type="checkbox" checked={picks.emotional_edges} onChange={(event) => set({ emotional_edges: event.target.checked })} /> Emotional edges in Companion, such as jealousy or missing you</label>}
        </Fold>
        {call.error && <p className="error" role="alert">{call.error}</p>}
        <div className="row">
          {call.busy
            ? <><button type="button" onClick={call.stop}><Square size={12} aria-hidden /> Stop</button><Waiting doing="Writing them" step={call.step} /></>
            : <button type="submit" className="primary" disabled={!ready}><Bolt /> Write them</button>}
          <button type="button" className="quiet" onClick={() => onBegin({ character: emptyCharacter(APPS) })}>Fill in the form myself</button>
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
 * file opens in the form as written, with no model, or the model sorts it into the fields; either way, its greetings,
 * lorebook and picture stay with them. A card Dramatis made opens whole. */
function PasteCharacter({ onBegin }: { onBegin: (begun: Begun) => void }) {
  const ready = useModelReady()
  const call = useModelCall()
  const input = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [file, setFile] = useState<OpenedFile | null>(null)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const [over, setOver] = useState(false)
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone ?? ''
  const write = (value: string) => {
    setText(value)
    if (!value.trim()) setFile(null)
  }
  const open = async (picked: File | undefined) => {
    if (!picked) return
    setError('')
    if (/\.(txt|md)$/i.test(picked.name)) {
      setFile(null)
      setText((await picked.text()).slice(0, 40000))
      return
    }
    setReading(true)
    try {
      const found = await sendJson<Opened | OpenedFile>('/api/cards/open', 'POST', { filename: picked.name, data: await fileData(picked) })
      if (found.kind === 'character') {
        onBegin({ character: found.character, brought: !!found.character.card?.source, note: `${found.character.name || 'They'} came back whole from a card Dramatis made. Save to keep them here.` })
        return
      }
      setText(found.text)
      setFile(found)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That file could not be read.')
    } finally {
      setReading(false)
      if (input.current) input.current.value = ''
    }
  }
  const drop = (event: DragEvent) => {
    event.preventDefault()
    setOver(false)
    void open(event.dataTransfer.files[0])
  }
  // What came with the file stays with them whichever way the form is filled.
  const withFile = (character: Character): Character => ({ ...character, card: file?.card ?? character.card ?? null })
  const asRead = file?.character && text === file.text ? file.character : null
  const openAsRead = () => asRead && onBegin({
    character: withFile({ ...asRead, apps: APPS, companion: { ...asRead.companion, timezone: asRead.companion.timezone || timezone } }),
    portrait: file?.portrait ?? undefined, brought: true,
    note: `${asRead.name || 'They'} opened as the file has them. Read the fields through, fill in the rest, then save.${instructionsNote(file?.instructions)}`,
  })
  const split = () => void call.run((signal) => sendJson<Drafted>('/api/draft/split', 'POST', { text, apps: APPS, timezone }, signal), (found) => onBegin({
    character: withFile(found.character), seed: found.seed, filledIn: found.filled_in, portrait: file?.portrait ?? undefined, allowed: text,
    note: `Your character, sorted into the fields.${found.filled_in?.length ? ' What your text didn’t say is marked for you to keep or put back.' : ''}${instructionsNote(found.instructions)}`,
  }), 'The character could not be sorted into the fields.')
  return (
    <section className="card" aria-labelledby="paste-title">
      <h2 id="paste-title"><ClipboardPaste size={16} aria-hidden /> Bring a character you already have</h2>
      <input ref={input} type="file" accept=".png,.json,.charx,.byaf,.txt,.md" aria-label="Character file: a card (PNG or JSON), CHARX, BYAF, JSON or text" hidden
        onChange={(event) => void open(event.target.files?.[0])} />
      <div className="stack">
        <div className={over ? 'drop over' : 'drop'} onDragOver={(event) => { event.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={drop}>
          <TextArea label="Their character" value={text} onChange={write} maxLength={40000} rows={8} placeholder="Paste notes, a bio or a scene, or drop a character file here" />
        </div>
        {file && (
          <div className="receipt small">
            {file.kept.length > 0 && <p>Kept from the card: {listed(file.kept)}.</p>}
            {[...(file.truncated ? ['Only the first 40,000 characters are in the box.'] : []), ...file.notes].map((note) => <p key={note} className="muted">{note}</p>)}
            {file.instructions.length > 0 && <p className="error">Lines in it talk to the app or the model rather than describe them (“{file.instructions.join('”, “')}”).</p>}
          </div>
        )}
        {file?.refused && <p className="error" role="alert">{file.refused}</p>}
        {(error || call.error) && <p className="error" role="alert">{error || call.error}</p>}
        <div className="row">
          <button type="button" disabled={reading || call.busy} onClick={() => input.current?.click()}><FileUp size={14} aria-hidden /> {reading ? 'Reading…' : 'Open a character file'}</button>
          {asRead && <button type="button" className="primary" disabled={call.busy} onClick={openAsRead}>Use as written</button>}
          {call.busy
            ? <><button type="button" onClick={call.stop}><Square size={12} aria-hidden /> Stop</button><Waiting doing="Sorting them" step={call.step} /></>
            : <button type="button" className={asRead ? undefined : 'primary'} disabled={!ready || !text.trim() || reading} onClick={split}><Bolt /> Sort into fields with my model</button>}
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
