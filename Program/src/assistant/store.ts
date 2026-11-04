/** The Sidebar Assistant's state, with no React in it: whether it is open, its conversation about the open form, and
 * the field the user is in (dramatis/assistant.py). Its edits go onto the form as proposals (src/proposals.ts) the user
 * keeps or puts back there. The conversation belongs to one form: another character coming into the editor starts it
 * over. Nothing here is saved. */
import { useSyncExternalStore } from 'react'
import { sendJson, stopped, type AuditHit, type Character } from '../api'
import { newId, proposals, valueAt } from '../proposals'
import { history, type Edit, type Turn } from './edits'

interface Reply { reply: string; edits: Omit<Edit, 'id' | 'before'>[]; audit: AuditHit[] }
/** The field the user was last in, by its key and the label the form shows. */
export interface Focus { field: string; label: string }
/** `seen` is the form as the last answer left it, so the next message says what the user changed since. `focus` is
 * the field the user was last in. `about` is the key of the form the conversation is about. */
export interface AssistantState {
  open: boolean; about: string | null; turns: Turn[]; seen: Character | null; focus: Focus | null; busy: boolean; error: string
}

const OPEN_KEY = 'dramatis:assistant'
const NARROW = '(max-width: 800px)'

/** Whether it was left open: remembered on wide screens only, where it sits beside the form rather than over it. */
function readOpen(): boolean {
  try { return !window.matchMedia(NARROW).matches && localStorage.getItem(OPEN_KEY) === 'open' } catch { return false }
}

let state: AssistantState = { open: readOpen(), about: null, turns: [], seen: null, focus: null, busy: false, error: '' }
let out: AbortController | null = null
const listeners = new Set<() => void>()
const set = (change: Partial<AssistantState>) => {
  state = { ...state, ...change }
  listeners.forEach((listener) => listener())
}

// A different form than the conversation is about starts it over.
proposals.subscribe(() => {
  const key = proposals.form()?.key ?? null
  if (key && key !== state.about) {
    out?.abort()
    set({ about: key, turns: [], seen: null, focus: null, error: '', busy: false })
  }
})

export const assistant = {
  get: () => state,
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
  setOpen(open: boolean) {
    set({ open })
    try { localStorage.setItem(OPEN_KEY, open ? 'open' : 'closed') } catch { /* A blocked store only forgets the choice. */ }
  },
  toggle() { assistant.setOpen(!state.open) },
  setFocus(focus: Focus | null) { if (focus?.field !== state.focus?.field || focus?.label !== state.focus?.label) set({ focus }) },
  setError(error: string) { set({ error }) },
  clear() { set({ turns: [], seen: null, error: '' }) },
  stop() { out?.abort(); out = null; set({ busy: false }) },

  /** One message: the reply, and its edits put onto the form as proposals. Resolves true once answered, so the
   * composer can clear. */
  async send(message: string, clean: (character: Character) => Character): Promise<boolean> {
    const form = proposals.form()
    if (!form || state.busy) return false
    const sent = clean(form.get())
    const control = new AbortController()
    out = control
    set({ busy: true, error: '' })
    try {
      const reply = await sendJson<Reply>('/api/assistant', 'POST', {
        message, character: sent, seen: state.seen, focus: state.focus?.field ?? null, history: history(state.turns, proposals.outcome),
      }, control.signal)
      if (proposals.form()?.key !== form.key) return true
      const edits: Edit[] = reply.edits.map((edit) => ({ ...edit, id: newId('edit'), before: valueAt(form.get(), edit.path) }))
      for (const edit of edits) {
        proposals.propose({ id: edit.id, field: edit.field, label: edit.label, path: edit.path, value: edit.value, source: 'assistant',
          hits: reply.audit.filter((hit) => hit.field === edit.field) })
      }
      // What the answer left on the form is what the next message compares the user's own changes against.
      set({ turns: [...state.turns, { id: newId('turn'), message, reply: reply.reply, edits, audit: reply.audit }], seen: clean(form.get()) })
      return true
    } catch (failure) {
      if (!stopped(failure)) set({ error: failure instanceof Error ? failure.message : 'The assistant could not answer.' })
      return false
    } finally { if (out === control) { out = null; set({ busy: false }) } }
  },
}

export function useAssistant(): AssistantState {
  return useSyncExternalStore(assistant.subscribe, assistant.get, assistant.get)
}

const shown = () => state.open && !!proposals.form()
const subscribeBoth = (listener: () => void) => {
  const one = assistant.subscribe(listener)
  const two = proposals.subscribe(listener)
  return () => { one(); two() }
}

/** Whether the panel shows, for the app shell, which must not re-render as the form changes. */
export function useAssistantShown(): boolean {
  return useSyncExternalStore(subscribeBoth, shown, shown)
}
