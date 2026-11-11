import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Copy, MessageSquareText, Trash2 } from 'lucide-react'
import { cleaned, savedOver, type AuditHit, getJson, sendJson, type App, type Character, type Gender, type Problems, type Saved } from './api'
import { assistant, useAssistantShown } from './assistant/store'
import { trackFocus, useProposalForm } from './assistant/useForm'
import { ComesAcross, Depth, ForCompanion, HowTheyLook, Story } from './editor/sections'
import { ExportCard, WorksIn } from './editor/status'
import { Field, TextArea, TextInput, useModelReady } from './Fields'
import { sampleLine } from './Interview'
import { isEmpty, pathOf, proposals, useOpenCount, useWritten, valueAt, withValue } from './proposals'
import { useNameRoll } from './rollName'
import { Portrait } from './Portrait'
import { AppPicks, listed, type Begun } from './Start'
import { FormAudit } from './Audit'
import { scheduleProblems } from './Schedule'
import { Sliders } from './Sliders'
import { draftStore } from './drafts'

const LIFESPANS: [string, string][] = [['', 'As long as their kind does'], ['0', "Doesn't age"], ['80', 'About 80 years'],
  ['150', 'About 150 years'], ['300', 'About 300 years'], ['600', 'About 600 years'], ['1000', 'About 1,000 years']]

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
  onSaved: (saved: Saved) => void; onDeleted: () => void; onDuplicated: (id: string) => void
  /** Drop the unsaved changes: back to what was saved, or the form goes for a new one. */
  onDiscard: () => void
}

const asSaved = (character: Character) => JSON.stringify(cleaned(character))
/** Whether a new form holds anything worth keeping as a draft. */
const begunOn = (character: Character) => !!(character.name.trim() || character.about.trim() || character.personality.trim() || character.background.trim())


/** One character, every field, for whichever apps they are made for. What a model writes goes into its field as a
 * proposal to keep or put back (src/proposals.ts); nothing is saved until Save. */
export function Editor({ saved, start, seed, filledIn, missing, shortened, note, portrait, brought, allowed, draftKey, begun, onSaved, onDeleted, onDuplicated, onDiscard }: Props) {
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
  const current = () => cleaned(character)
  const has = (app: App) => character.apps.includes(app)
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
  // What a model wrote: as saved with them, and what it has written on this form since.
  const writtenNow = useWritten()
  const written = [...new Set([...(character.written ?? []), ...writtenNow])]
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
  }, [character, writtenNow]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    try {
      // Saving keeps what the form shows, proposals included.
      const kept = proposals.keepAll()
      const form = proposals.form()?.get() ?? character
      const sent = { ...form, written: [...new Set([...(form.written ?? []), ...proposals.written()])] }
      const body = { character: cleaned(sent), seed }
      let next = saved
        ? await savedOver((revision) => sendJson<Saved>(`/api/characters/${saved.id}`, 'PUT', { ...body, revision }), saved.revision)
        : await sendJson<Saved>('/api/characters', 'POST', body)
      // They are in the library from here: the form knows their id before the portrait goes, so a portrait that fails
      // never makes the next Save post a second copy.
      baseline.current = asSaved(sent)
      setCharacter((current) => ({ ...current, written: sent.written }))
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
  const duplicate = async () => {
    if (!saved) return
    try {
      const copy = await sendJson<Saved>(`/api/library/characters/${saved.id}/duplicate`, 'POST')
      await client.invalidateQueries({ queryKey: ['characters'] })
      onDuplicated(copy.id)
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'They could not be duplicated.' })
    }
  }
  const remove = async () => {
    if (!saved) return
    // The casts that name them say so first: their corner there will show they are gone (dramatis/library_tools.py).
    const inCasts = await getJson<{ id: string; title: string }[]>(`/api/library/characters/${saved.id}/casts`).catch(() => [])
    const where = inCasts.length ? ` They are in ${listed(inCasts.map((cast) => cast.title))}, which will show their corner empty.` : ''
    if (!window.confirm(`Delete ${saved.character.name || 'this character'} from the library?${where} Cards you exported stay where they are.`)) return
    await sendJson(`/api/characters/${saved.id}`, 'DELETE')
    draftStore.drop(key)
    proposals.forget(key)
    await client.invalidateQueries({ queryKey: ['characters'] })
    onDeleted()
  }

  const said = sampleLine(character.interview, sample)
  const blocked = has('companion') && scheduleProblems(character.companion.schedule).length > 0
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
            <button type="button" className="icon" aria-label="Duplicate them" title={changed ? 'Save first to duplicate them' : 'Duplicate them'}
              disabled={changed || busy} onClick={() => void duplicate()}><Copy size={15} /></button>
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
              <TextInput field="name" value={character.name} onChange={(name) => set({ name })} roll={rollName} />
              <Field field="gender">{(id) => (
                <select id={id} value={character.gender} onChange={(event) => set({ gender: event.target.value as Gender })}>
                  <option value="">Not said</option><option value="woman">Woman</option><option value="man">Man</option><option value="nonbinary">Nonbinary</option>
                </select>
              )}</Field>
              <Field field="age">{(id) => (
                <input id={id} type="number" min={18} max={5000} value={character.age ?? ''} onChange={(event) => set({ age: event.target.value ? Number(event.target.value) : null })} />
              )}</Field>
            </div>
            <TextInput field="setting" value={character.setting} onChange={(setting) => set({ setting })} />
            <div className="grid three">
              <TextInput field="kind" value={character.kind} onChange={(kind) => set({ kind: kind.toLowerCase().replace(/[^a-z0-9-]/g, '') })} />
              <Field field="lifespan">{(id) => (
                <select id={id} value={character.lifespan ?? ''} onChange={(event) => set({ lifespan: event.target.value === '' ? null : Number(event.target.value) })}>
                  {LIFESPANS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              )}</Field>
              <Field field="birthday">{(id) => (
                <input id={id} value={character.birthday} maxLength={5} placeholder="MM-DD" onChange={(event) => set({ birthday: event.target.value })} />
              )}</Field>
            </div>
            <AppPicks apps={character.apps} onChange={(apps) => set({ apps })} />
          </div>
        </div>
        <TextArea field="about" value={character.about} onChange={(about) => set({ about })} rows={3} />
        <TextArea field="personality" value={character.personality} onChange={(personality) => set({ personality })} rows={4} />
        <div className="grid two">
          <div className="stack tight">
            <TextArea field="voice" value={character.voice} onChange={(voice) => set({ voice })} rows={3} />
            {said && <q className="sample">{said}</q>}
          </div>
          <TextArea field="sound" value={character.sound} onChange={(sound) => set({ sound })} rows={3} />
        </div>
      </section>

      <ComesAcross character={character} set={set} />

      <section>
        <h3>Personality</h3>
        <Sliders character={current} words={[character.about, character.personality, character.voice, ...character.flaws].join('\n')} seed={seed} still={brought} onChange={(personality_sliders) => {
          // An older character saved before sliders were kept settles them on opening: that is not a change.
          if (!settled.current && saved && !saved.character.personality_sliders && baseline.current === asSaved(saved.character)) {
            baseline.current = asSaved({ ...saved.character, personality_sliders })
          }
          settled.current = true
          set({ personality_sliders })
        }} />
      </section>

      <Story character={character} set={set} />

      <Depth character={character} set={set} ready={ready} selfId={saved?.id} onSample={setSample} />

      <HowTheyLook character={character} set={set} update={setCharacter} />

      {has('companion') && <ForCompanion character={character} update={setCharacter} />}
    </form>
  )
}

