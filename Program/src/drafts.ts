/** Character forms with unsaved changes, so leaving one for another character, a cast or a reload loses nothing. A
 * draft is kept by the saved character's id, or by NEW for one not saved yet (one at a time, like a new cast). The
 * form writes its draft as it changes; the library marks the ones with changes and opens them as they were left.
 * Drafts with changes are kept in this browser's storage too, one entry each, so a reload brings them back and a
 * second tab never writes over the first one's drafts (it hears them change instead); nothing here is saved to the
 * library until Save. */
import { useSyncExternalStore } from 'react'
import type { Character, Saved } from './api'
import type { Begun } from './Start'

export const NEW = 'new'
/** One storage entry per draft: PREFIX + its key. */
const PREFIX = 'dramatis:draft:'
/** Where every draft was kept together before (one entry for all of them), read once and moved. */
const OLD_STORE = 'dramatis:drafts'

/** `saved` is the character as last saved (none for a new one); `begun` is how the form opened, with `character`
 * as it stands now. `changed` says whether it differs from what was saved. */
export interface Draft { key: string; saved: Saved | null; begun: Begun; changed: boolean }

const parsed = (text: string | null): Draft | null => {
  try {
    const found = JSON.parse(text ?? 'null') as Draft | null
    return found && typeof found === 'object' && typeof found.key === 'string' ? found : null
  } catch { return null }
}

function read(): Record<string, Draft> {
  const found: Record<string, Draft> = {}
  try {
    const old = JSON.parse(localStorage.getItem(OLD_STORE) ?? '{}') as Record<string, Draft>
    for (const draft of Object.values(old && typeof old === 'object' ? old : {})) {
      if (draft?.key) localStorage.setItem(PREFIX + draft.key, JSON.stringify(draft))
    }
    localStorage.removeItem(OLD_STORE)
  } catch { /* storage refused: start from what is there */ }
  try {
    for (let index = 0; index < localStorage.length; index++) {
      const name = localStorage.key(index)
      const draft = name?.startsWith(PREFIX) ? parsed(localStorage.getItem(name)) : null
      if (draft) found[draft.key] = draft
    }
  } catch { /* nothing stored */ }
  return found
}

let drafts: Record<string, Draft> = read()
let kept = true
let timer: ReturnType<typeof setTimeout> | undefined
/** The drafts changed here since the last write to storage. */
const dirty = new Set<string>()
const listeners = new Set<() => void>()

/** Only drafts with changes are stored, each in its own entry, without a portrait waiting to be saved (too large for
 * storage). A draft without changes, or dropped, leaves storage. */
function store(key: string) {
  dirty.add(key)
  clearTimeout(timer)
  timer = setTimeout(() => {
    let ok = true
    for (const each of dirty) {
      const draft = drafts[each]
      try {
        if (draft?.changed) localStorage.setItem(PREFIX + each, JSON.stringify({ ...draft, begun: { ...draft.begun, portrait: undefined } }))
        else localStorage.removeItem(PREFIX + each)
      } catch { ok = false }
    }
    dirty.clear()
    kept = ok
  }, 400)
}

const notify = () => listeners.forEach((listener) => listener())
const emit = (key: string) => { store(key); notify() }

// Another tab wrote or dropped a draft: take it as it is there, without writing it back.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (!event.key?.startsWith(PREFIX)) return
    const key = event.key.slice(PREFIX.length)
    const draft = parsed(event.newValue)
    if (draft) drafts = { ...drafts, [key]: draft }
    else { const { [key]: _, ...rest } = drafts; drafts = rest }
    notify()
  })
}

export const draftStore = {
  get: (key: string): Draft | undefined => drafts[key],
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
  put(draft: Draft) {
    const before = drafts[draft.key]
    drafts = { ...drafts, [draft.key]: draft }
    // Typing changes the draft but not whether it has changes: the library re-renders only when that flips.
    if (before?.changed !== draft.changed || before?.begun.character.name !== draft.begun.character.name) emit(draft.key)
    else store(draft.key)
  },
  drop(key: string) {
    if (!(key in drafts)) return
    const { [key]: _, ...rest } = drafts
    drafts = rest
    emit(key)
  },
  /** Whether a reload or closing the tab would lose changes: only when the browser would not store them. */
  atRisk: () => !kept && Object.values(drafts).some((draft) => draft.changed),
}

/** Which drafts have changes, by key, with their names as typed: for the library. Re-renders as that list changes. */
let shown = ''
let shownList: { key: string; name: string }[] = []
function changedList() {
  const list = Object.values(drafts).filter((draft) => draft.changed).map((draft) => ({ key: draft.key, name: draft.begun.character.name }))
  const next = JSON.stringify(list)
  if (next !== shown) { shown = next; shownList = list }
  return shownList
}
export function useChangedDrafts(): { key: string; name: string }[] {
  return useSyncExternalStore(draftStore.subscribe, changedList, changedList)
}

/** Whether two forms say the same, for Save and the library's mark. */
export const sameCharacter = (one: Character, other: Character) => JSON.stringify(one) === JSON.stringify(other)

if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', (event) => {
    if (draftStore.atRisk()) event.preventDefault()
  })
}
