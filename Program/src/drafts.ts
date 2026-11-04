/** Character forms with unsaved changes, so leaving one for another character, a cast or a reload loses nothing. A
 * draft is kept by the saved character's id, or by NEW for one not saved yet (one at a time, like a new cast). The
 * form writes its draft as it changes; the library marks the ones with changes and opens them as they were left.
 * Drafts with changes are kept in this browser's storage too, so a reload brings them back; nothing here is saved to
 * the library until Save. */
import { useSyncExternalStore } from 'react'
import type { Character, Saved } from './api'
import type { Begun } from './Start'

export const NEW = 'new'
const STORE = 'dramatis:drafts'

/** `saved` is the character as last saved (none for a new one); `begun` is how the form opened, with `character`
 * as it stands now. `changed` says whether it differs from what was saved. */
export interface Draft { key: string; saved: Saved | null; begun: Begun; changed: boolean }

function read(): Record<string, Draft> {
  try {
    const found = JSON.parse(localStorage.getItem(STORE) ?? '{}') as Record<string, Draft>
    return found && typeof found === 'object' ? found : {}
  } catch { return {} }
}

let drafts: Record<string, Draft> = read()
let kept = true
let timer: ReturnType<typeof setTimeout> | undefined
const listeners = new Set<() => void>()

/** Only drafts with changes are stored, without a portrait waiting to be saved (too large for storage). */
function store() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    const changed = Object.fromEntries(Object.entries(drafts).filter(([, draft]) => draft.changed)
      .map(([key, draft]) => [key, { ...draft, begun: { ...draft.begun, portrait: undefined } }]))
    try { localStorage.setItem(STORE, JSON.stringify(changed)); kept = true } catch { kept = false }
  }, 400)
}

const emit = () => { store(); listeners.forEach((listener) => listener()) }

export const draftStore = {
  get: (key: string): Draft | undefined => drafts[key],
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener) } },
  put(draft: Draft) {
    const before = drafts[draft.key]
    drafts = { ...drafts, [draft.key]: draft }
    // Typing changes the draft but not whether it has changes: the library re-renders only when that flips.
    if (before?.changed !== draft.changed || before?.begun.character.name !== draft.begun.character.name) emit()
    else store()
  },
  drop(key: string) {
    if (!(key in drafts)) return
    const { [key]: _, ...rest } = drafts
    drafts = rest
    emit()
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
