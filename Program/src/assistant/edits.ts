/** The Sidebar Assistant's edits as data: where a field sits in the character, putting a value there, and whether two
 * values are the same as the form means them. Nothing here talks to the server. */
import { emptyPsyche, type AuditHit, type Character } from '../api'

/** `before` is what the field held when the edit went in; `waiting` is an edit to a field the user was changing while
 * the assistant answered, so it waits for Apply instead of landing on their typing. */
export type EditStatus = 'applied' | 'waiting' | 'undone'
export interface Edit { id: string; field: string; label: string; path: string[]; value: unknown; before: unknown; status: EditStatus }
export interface Turn { id: string; message: string; reply: string; edits: Edit[]; audit: AuditHit[] }
export interface HistoryTurn { role: 'user' | 'assistant'; content: string }

const HISTORY_TURNS = 5
const HISTORY_CHARS = 4000

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
const empty = (value: unknown) => value === null || value === undefined || value === '' || (Array.isArray(value) && !value.length)

/** The same as the form means it: blank list lines and the edges of text don't count (dramatis/assistant.py `same`). */
export function same(one: unknown, other: unknown): boolean {
  const [a, b] = [plain(one), plain(other)]
  return (empty(a) && empty(b)) || JSON.stringify(a) === JSON.stringify(b)
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** A value as text, for Compare. */
export function shown(value: unknown): string {
  if (empty(plain(value))) return '(empty)'
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value.map((item) => item && typeof item === 'object' && 'label' in item
      ? `${item.label}: ${(item.days as number[]).map((day) => DAYS[day]).join(' ')} ${item.start} to ${item.end}`
      : String(item)).join('\n')
  }
  return String(value)
}

/** What became of each edit, for the next message: the assistant knows which of its changes the user kept. */
function outcome(edit: Edit): string {
  if (edit.status === 'applied') return `changed ${edit.label}`
  if (edit.status === 'undone') return `changed ${edit.label}, which they undid`
  return `offered a change to ${edit.label}, not put in yet`
}

/** What the server is sent of the conversation so far: the latest turns, each cut to a readable length. */
export function history(turns: Turn[]): HistoryTurn[] {
  return turns.slice(-HISTORY_TURNS).flatMap((turn) => [
    { role: 'user' as const, content: turn.message.slice(0, HISTORY_CHARS) },
    { role: 'assistant' as const, content: `${turn.reply}${turn.edits.length ? ` (You ${turn.edits.map(outcome).join('; ')}.)` : ''}`.slice(0, HISTORY_CHARS) },
  ])
}
