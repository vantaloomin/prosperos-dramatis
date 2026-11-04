import { useEffect, useRef } from 'react'
import type { Character } from '../api'
import { proposals } from '../proposals'
import { assistant } from './store'

let opened = 0

/** The editor's form, for proposals and the Sidebar Assistant to see and edit. `key` names it (a character's own
 * key keeps their proposals when they are opened again); without one, each form opened is a form of its own. */
export function useProposalForm(character: Character, setCharacter: (character: Character) => void, key?: string) {
  const latest = useRef(character)
  const name = useRef(key ?? '')
  if (!name.current) name.current = `form-${Date.now().toString(36)}-${(opened += 1)}`
  latest.current = character
  useEffect(() => {
    const form = { key: name.current, get: () => latest.current, set: (next: Character) => { latest.current = next; setCharacter(next) } }
    proposals.register(form)
    return () => proposals.unregister(form.key)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}

/** The field the user moves into, from the `data-field` of the form field around it. */
export function trackFocus(target: EventTarget) {
  const field = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-field]') : null
  const name = field?.dataset.field
  if (field && name) assistant.setFocus({ field: name, label: field.querySelector(':scope > .field-top > label, :scope > .field-top > .label')?.textContent ?? name })
}
