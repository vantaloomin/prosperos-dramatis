import { useRef, useState, type FormEvent } from 'react'
import { ClipboardPaste, FileUp, Sparkles } from 'lucide-react'
import { APPS, APP_NAMES, emptyCharacter, fileData, sendJson, type App, type Character, type Drafted, type Gender, type Opened, type OpenedText, type Relationship } from './api'
import { Field, TextArea, TextInput, useModelReady } from './Fields'

export interface Begun { character: Character; seed?: string; filledIn?: string[]; note?: string }
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

/** A character the user already has: pasted, or read from a card file into the box first, then split by the model.
 * A card Dramatis made opens whole, with nothing sent to a model. */
function PasteCharacter({ onBegin }: { onBegin: (begun: Begun) => void }) {
  const ready = useModelReady()
  const input = useRef<HTMLInputElement>(null)
  const [text, setText] = useState('')
  const [apps, setApps] = useState<App[]>(APPS)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const open = async (file: File | undefined) => {
    if (!file) return
    setBusy('Reading…')
    setError('')
    try {
      const found = await sendJson<Opened | OpenedText>('/api/cards/open', 'POST', { filename: file.name, data: await fileData(file) })
      if (found.kind === 'character') {
        onBegin({ character: found.character, note: `${found.character.name || 'They'} came back whole from a card Dramatis made. Save to keep them here.` })
        return
      }
      setText(found.text)
      setNote(found.truncated ? 'The card was long, so only its first 40,000 characters are in the box.' : `Read ${found.name || 'the card'}. Check the text, then split it into fields.`)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That file could not be read.')
    } finally {
      setBusy('')
      if (input.current) input.current.value = ''
    }
  }
  const split = async () => {
    setBusy('Splitting…')
    setError('')
    try {
      const found = await sendJson<Drafted>('/api/draft/split', 'POST', { text, apps, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? '' })
      const told = found.instructions?.length
        ? ` Your text had lines that talk to the app or the model rather than describe them (“${found.instructions.join('”, “')}”). The model was told to ignore them; check the fields before you save.`
        : ''
      onBegin({ character: found.character, seed: found.seed, filledIn: found.filled_in, note: `Your character, split into the fields.${told}` })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The character could not be split.')
    } finally { setBusy('') }
  }
  return (
    <section className="card" aria-labelledby="paste-title">
      <h2 id="paste-title"><ClipboardPaste size={16} aria-hidden /> Or bring a character you already have</h2>
      <p className="muted">Notes, a bio, a scene, or a character card from SillyTavern, Chub or another app. You see exactly what will be sent before anything is. Nothing in a card runs, and no picture is fetched.</p>
      <input ref={input} type="file" accept=".png,.json,.txt,.md" hidden onChange={(event) => {
        const file = event.target.files?.[0]
        if (file && /\.(txt|md)$/i.test(file.name)) { void file.text().then((value) => setText(value.slice(0, 40000))); return }
        void open(file)
      }} />
      <div className="stack">
        <TextArea label="Their character" value={text} onChange={setText} maxLength={40000} rows={8} />
        <AppPicks apps={apps} onChange={setApps} />
        {note && <p className="note">{note}</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <div className="row">
          <button type="button" disabled={!!busy} onClick={() => input.current?.click()}><FileUp size={14} aria-hidden /> Open a card or text file</button>
          <button type="button" className="primary" disabled={!ready || !text.trim() || !!busy} onClick={() => void split()}>{busy === 'Splitting…' ? busy : 'Split into fields'}</button>
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
