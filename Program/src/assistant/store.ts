/** The Sidebar Assistant's state, with no React in it: whether it is open, the character form it sees and edits, its
 * conversation, and the fields its edits still stand in (dramatis/assistant.py). The conversation belongs to one open
 * form: another character coming into the editor starts it over. Nothing here is saved. */
import { useSyncExternalStore } from 'react'
import { sendJson, type AuditHit, type Character } from '../api'
import { history, same, valueAt, withValue, type Edit, type Turn } from './edits'

/** The open character form: `get` is it as typed, `clean` as the server takes it. `set` takes effect for `get` at once,
 * so edits one after another each build on the last. */
export interface Form { key: string; get: () => Character; clean: () => Character; set: (character: Character) => void }
interface Reply { reply: string; edits: Omit<Edit, 'id' | 'before' | 'status'>[]; audit: AuditHit[] }
/** The field the user was last in, by its key and the label the form shows. */
export interface Focus { field: string; label: string }
/** `seen` is the form as the last answer left it, so the next message says what the user changed since. `focus` is
 * the field the user was last in. `marks` holds, by field, the applied edit still standing in it. */
export interface AssistantState {
  open: boolean; form: Form | null; about: string | null; turns: Turn[]; seen: Character | null; focus: Focus | null
  busy: boolean; error: string; marks: Record<string, string>
}

const OPEN_KEY = 'dramatis:assistant'
let made = 0
const newId = () => `edit-${Date.now().toString(36)}-${(made += 1)}`

function readOpen(): boolean {
  try { return localStorage.getItem(OPEN_KEY) === 'open' } catch { return false }
}

let state: AssistantState = { open: readOpen(), form: null, about: null, turns: [], seen: null, focus: null, busy: false, error: '', marks: {} }
const listeners = new Set<() => void>()
const set = (change: Partial<AssistantState>) => {
  state = { ...state, ...change }
  listeners.forEach((listener) => listener())
}

const found = (id: string): Edit | undefined => state.turns.flatMap((turn) => turn.edits).find((edit) => edit.id === id)
const updated = (id: string, change: Partial<Edit>): Turn[] =>
  state.turns.map((turn) => ({ ...turn, edits: turn.edits.map((edit) => edit.id === id ? { ...edit, ...change } : edit) }))
const without = (field: string) => Object.fromEntries(Object.entries(state.marks).filter(([key]) => key !== field))

export const assistant = {
  get: () => state,
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
  setOpen(open: boolean) {
    set({ open })
    try { localStorage.setItem(OPEN_KEY, open ? 'open' : 'closed') } catch { /* A blocked store only forgets the choice. */ }
  },
  toggle() { assistant.setOpen(!state.open) },

  /** The editor registers its form; a different character than the conversation is about starts it over. */
  register(form: Form) {
    const fresh = form.key !== state.about
    set({ form, about: form.key, ...(fresh ? { turns: [], seen: null, focus: null, marks: {}, error: '' } : {}) })
  },
  unregister(key: string) { if (state.form?.key === key) set({ form: null }) },
  /** After every change on the form: a field the user has typed over is theirs again, so its mark goes. */
  sync(character: Character) {
    const kept = Object.fromEntries(Object.entries(state.marks).filter(([, id]) => {
      const edit = found(id)
      return edit && same(valueAt(character, edit.path), edit.value)
    }))
    if (Object.keys(kept).length !== Object.keys(state.marks).length) set({ marks: kept })
  },
  setFocus(focus: Focus | null) { if (focus?.field !== state.focus?.field || focus?.label !== state.focus?.label) set({ focus }) },
  setError(error: string) { set({ error }) },
  clear() { set({ turns: [], seen: null, marks: {}, error: '' }) },

  /** One message: the reply, with its edits put straight into the form. An edit to a field the user changed while it
   * answered waits for Apply. Resolves true once answered, so the composer can clear. */
  async send(message: string): Promise<boolean> {
    const form = state.form
    if (!form || state.busy) return false
    const sent = form.clean()
    set({ busy: true, error: '' })
    try {
      const reply = await sendJson<Reply>('/api/assistant', 'POST', { message, character: sent, seen: state.seen, focus: state.focus?.field ?? null, history: history(state.turns) })
      if (state.form?.key !== form.key) return true
      let next = form.get()
      const edits: Edit[] = reply.edits.map((edit) => {
        const before = valueAt(next, edit.path)
        if (!same(valueAt(sent, edit.path), before)) return { ...edit, id: newId(), before, status: 'waiting' }
        next = withValue(next, edit.path, edit.value)
        return { ...edit, id: newId(), before, status: 'applied' }
      })
      form.set(next)
      const marks = { ...state.marks, ...Object.fromEntries(edits.filter((edit) => edit.status === 'applied').map((edit) => [edit.field, edit.id])) }
      set({ turns: [...state.turns, { id: newId(), message, reply: reply.reply, edits, audit: reply.audit }], seen: next, marks })
      return true
    } catch (failure) {
      set({ error: failure instanceof Error ? failure.message : 'The assistant could not answer.' })
      return false
    } finally { set({ busy: false }) }
  },

  /** Puts an edit in: one that waited, or one undone. */
  apply(id: string) {
    const edit = found(id)
    const form = state.form
    if (!edit || !form) return
    const now = form.get()
    form.set(withValue(now, edit.path, edit.value))
    set({ turns: updated(id, { status: 'applied', before: valueAt(now, edit.path) }), marks: { ...state.marks, [edit.field]: id } })
  },
  /** Puts back what the field held before the edit, asking first if the user has changed it since. */
  undo(id: string) {
    const edit = found(id)
    const form = state.form
    if (!edit || !form || edit.status !== 'applied') return
    const now = form.get()
    if (!same(valueAt(now, edit.path), edit.value) &&
      !window.confirm(`${edit.label} has changed since the assistant wrote it. Put back what was there before, and lose that?`)) return
    form.set(withValue(now, edit.path, edit.before))
    set({ turns: updated(id, { status: 'undone' }), marks: without(edit.field) })
  },
  /** Undo for the mark on the form itself. */
  undoField(field: string) { const id = state.marks[field]; if (id) assistant.undo(id) },
  /** Undo for every edit of one answer still in the form. */
  undoTurn(turn: Turn) { for (const edit of turn.edits) if (edit.status === 'applied') assistant.undo(edit.id) },
}

export function useAssistant(): AssistantState {
  return useSyncExternalStore(assistant.subscribe, assistant.get, assistant.get)
}

/** Whether the panel shows, for the app shell, which must not re-render as the form changes. */
export function useAssistantShown(): boolean {
  const shown = () => state.open && !!state.form
  return useSyncExternalStore(assistant.subscribe, shown, shown)
}

/** Whether an edit of the assistant's still stands in this field, for its mark on the form. */
export function useMarked(field?: string): boolean {
  const marked = () => !!field && field in state.marks
  return useSyncExternalStore(assistant.subscribe, marked, marked)
}
