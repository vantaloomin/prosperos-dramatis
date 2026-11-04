/** The Sidebar Assistant's turns as data: what it proposed, how a value reads in Compare, and what the server is told
 * of the conversation so far. Its edits are proposals on the form (src/proposals.ts). */
import type { AuditHit } from '../api'
import { isEmpty, type Outcome } from '../proposals'

/** One field the assistant proposed: `before` is what the field held when its proposal went into the form. */
export interface Edit { id: string; field: string; label: string; path: string[]; value: unknown; before: unknown }
export interface Turn { id: string; message: string; reply: string; edits: Edit[]; audit: AuditHit[] }
export interface HistoryTurn { role: 'user' | 'assistant'; content: string }

const HISTORY_TURNS = 5
const HISTORY_CHARS = 4000
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** A value as text, for Compare. */
export function shown(value: unknown): string {
  if (isEmpty(typeof value === 'string' ? value.trim() : value)) return '(empty)'
  if (typeof value === 'string') return value
  if (Array.isArray(value)) {
    return value.map((item) => item && typeof item === 'object' && 'label' in item
      ? `${item.label}: ${(item.days as number[]).map((day) => DAYS[day]).join(' ')} ${item.start} to ${item.end}`
      : String(item)).join('\n')
  }
  return String(value)
}

const SAID: Record<Outcome, string> = {
  kept: 'which they kept', 'put back': 'which they put back', replaced: 'which a later proposal replaced',
  proposed: 'still waiting on the form for them to keep or put back',
}

/** What the server is sent of the conversation so far: the latest turns, each cut to a readable length, with what
 * became of each edit, so the assistant knows which of its changes the user kept. */
export function history(turns: Turn[], outcome: (id: string) => Outcome | undefined): HistoryTurn[] {
  return turns.slice(-HISTORY_TURNS).flatMap((turn) => {
    const edits = turn.edits.map((edit) => `proposed a change to ${edit.label}, ${SAID[outcome(edit.id) ?? 'proposed']}`)
    return [
      { role: 'user' as const, content: turn.message.slice(0, HISTORY_CHARS) },
      { role: 'assistant' as const, content: `${turn.reply}${edits.length ? ` (You ${edits.join('; ')}.)` : ''}`.slice(0, HISTORY_CHARS) },
    ]
  })
}
