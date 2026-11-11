/** What a model proposes for the character form, in one place: Help me write, the Sidebar Assistant and the interview
 * all put their text into the field it would change, marked as a proposal, and the user keeps it or puts back what was
 * there. Nothing here talks to the server, and nothing is saved until Save.
 *
 * A proposal stands in the form at once (so the field shows what the model wrote, and the user can edit it), with
 * `before` holding what the field had. Keep drops the mark; Put back restores `before`. A second proposal for the same
 * field replaces the first and keeps the first one's `before`, so Put back always goes back to the user's own text.
 * Every proposal has an `id`, and what became of it stays in `outcomes` for whoever asked for it (the assistant tells
 * its model which of its changes were kept). */
import { useSyncExternalStore } from 'react'
import { emptyPsyche, type AuditHit, type Character } from './api'

/** The open character form: `get` is it as typed, `set` takes effect for `get` at once, so proposals one after
 * another each build on the last. `key` names the form; another key is another character. */
export interface Form { key: string; get: () => Character; set: (character: Character) => void }

export type Source = 'help' | 'assistant' | 'interview' | 'split' | 'fix'
export interface Proposal {
  id: string; field: string; label: string; path: string[]; value: unknown; before: unknown; source: Source
  /** The AI-slop audit's hits on what the model wrote, and the model's reason, when it gave one. */
  hits: AuditHit[]; reason?: string
  /** What the user asked Help me write for, so Try again asks the same. */
  request?: string
}
export type Outcome = 'proposed' | 'kept' | 'put back' | 'replaced'

/** `written` is every field a model has put text into on this form and the user hasn't put back: the fields the
 * AI-slop audit reads (text the user typed or brought is theirs). */
interface State { form: Form | null; open: Record<string, Proposal>; outcomes: Record<string, Outcome>; written: string[] }

// Fields under `companion` in the character, as Help me write and the assistant name them.
const LIFE = new Set(['routine', 'life_themes', 'schedule', 'history_together', 'absence_reaction', 'timezone', 'emotional_traits'])

/** Where a field sits in the character, from its key: arc.lie under arc, psyche.was in its text, routine under
 * companion (dramatis/assistant.py `path`). */
export function pathOf(field: string): string[] {
  if (field.startsWith('psyche.')) return ['psyche', field.slice(7), 'text']
  if (field.includes('.')) return field.split('.')
  return LIFE.has(field) ? ['companion', field] : [field]
}

export function valueAt(character: Character, path: string[]): unknown {
  let value: unknown = character
  for (const key of path) value = value && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined
  return value
}

/** The character with one field set; an inner square still empty starts from its four empty pulls. */
export function withValue(character: Character, path: string[], value: unknown): Character {
  const start = path[0] === 'psyche' && !character.psyche ? { ...character, psyche: emptyPsyche() } : character
  const put = (source: unknown, keys: string[]): unknown => {
    if (!keys.length) return value
    const found = (source && typeof source === 'object' ? source : {}) as Record<string, unknown>
    return { ...found, [keys[0]]: put(found[keys[0]], keys.slice(1)) }
  }
  return put(start, path) as Character
}

const plain = (value: unknown): unknown => Array.isArray(value)
  ? value.filter((item) => !(typeof item === 'string' && !item.trim())).map((item) => typeof item === 'string' ? item.trim() : item)
  : typeof value === 'string' ? value.trim() : value
export const isEmpty = (value: unknown) => value === null || value === undefined || value === '' || (Array.isArray(value) && !(plain(value) as unknown[]).length)

/** The same as the form means it: blank list lines and the edges of text don't count (dramatis/assistant.py `same`). */
export function same(one: unknown, other: unknown): boolean {
  const [a, b] = [plain(one), plain(other)]
  return (isEmpty(a) && isEmpty(b)) || JSON.stringify(a) === JSON.stringify(b)
}

let made = 0
export const newId = (kind = 'proposal') => `${kind}-${Date.now().toString(36)}-${(made += 1)}`

// Each form's open proposals, by form key, so a character opened again finds its own still waiting.
const byForm = new Map<string, Record<string, Proposal>>()
const writtenBy = new Map<string, string[]>()
let state: State = { form: null, open: {}, outcomes: {}, written: [] }
const listeners = new Set<() => void>()
const set = (change: Partial<State>) => {
  state = { ...state, ...change }
  if (state.form) { byForm.set(state.form.key, state.open); writtenBy.set(state.form.key, state.written) }
  listeners.forEach((listener) => listener())
}
const without = (field: string) => Object.fromEntries(Object.entries(state.open).filter(([key]) => key !== field))
const settle = (ids: string[], outcome: Outcome) => ({ ...state.outcomes, ...Object.fromEntries(ids.map((id) => [id, outcome])) })

export const proposals = {
  get: () => state,
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
  form: () => state.form,

  /** The editor registers its form; its own proposals come back with it. */
  register(form: Form) { set({ form, open: byForm.get(form.key) ?? {}, written: writtenBy.get(form.key) ?? [] }) },
  unregister(key: string) { if (state.form?.key === key) set({ form: null, open: {}, written: [] }) },
  /** A form gone for good (saved as another key, or deleted) takes its proposals with it. */
  forget(key: string) { byForm.delete(key); writtenBy.delete(key) },
  /** The fields a model has written on the open form (and not put back), for Save to keep with them. */
  written: () => state.written,

  /** Puts a model's value into its field as a proposal. Returns its id, or '' when no form is open. */
  propose(found: Omit<Proposal, 'id' | 'before' | 'path'> & { path?: string[]; id?: string }): string {
    const form = state.form
    if (!form) return ''
    const path = found.path ?? pathOf(found.field)
    const now = form.get()
    const earlier = state.open[found.field]
    const id = found.id ?? newId()
    form.set(withValue(now, path, found.value))
    set({
      open: { ...state.open, [found.field]: { ...found, id, path, before: earlier ? earlier.before : valueAt(now, path) } },
      outcomes: { ...(earlier ? settle([earlier.id], 'replaced') : state.outcomes), [id]: 'proposed' },
      written: state.written.includes(found.field) ? state.written : [...state.written, found.field],
    })
    return id
  },
  keep(field: string) {
    const found = state.open[field]
    if (found) set({ open: without(field), outcomes: settle([found.id], 'kept') })
  },
  /** Puts back what the field held before, asking first when the user has changed the proposal since. */
  putBack(field: string, ask = true) {
    const found = state.open[field]
    const form = state.form
    if (!found || !form) return
    const now = form.get()
    if (ask && !same(valueAt(now, found.path), found.value) &&
      !window.confirm(`${found.label} has changed since it was proposed. Put back what was there before, and lose that?`)) return
    form.set(withValue(now, found.path, found.before))
    set({ open: without(field), outcomes: settle([found.id], 'put back'), written: state.written.filter((each) => each !== field) })
  },
  /** Keep every open proposal, or those with these ids. Returns how many were kept. */
  keepAll(ids?: string[]): number {
    const kept = Object.values(state.open).filter((item) => !ids || ids.includes(item.id))
    if (kept.length) set({ open: Object.fromEntries(Object.entries(state.open).filter(([, item]) => !kept.includes(item))), outcomes: settle(kept.map((item) => item.id), 'kept') })
    return kept.length
  },
  putBackAll(ids?: string[]) {
    for (const item of Object.values(state.open)) if (!ids || ids.includes(item.id)) proposals.putBack(item.field, false)
  },
  outcome: (id: string): Outcome | undefined => state.outcomes[id],
}

/** The proposal standing in this field, if any. */
export function useProposal(field?: string): Proposal | undefined {
  const found = () => field ? state.open[field] : undefined
  return useSyncExternalStore(proposals.subscribe, found, found)
}

/** How many proposals wait on the open form. */
export function useOpenCount(): number {
  const count = () => Object.keys(state.open).length
  return useSyncExternalStore(proposals.subscribe, count, count)
}

/** The fields a model wrote on the open form (see State). */
export function useWritten(): string[] {
  return useSyncExternalStore(proposals.subscribe, () => state.written, () => state.written)
}

/** What became of these proposals, for the assistant's chat: re-renders as they are kept or put back. */
export function useOutcomes(): Record<string, Outcome> {
  return useSyncExternalStore(proposals.subscribe, () => state.outcomes, () => state.outcomes)
}
