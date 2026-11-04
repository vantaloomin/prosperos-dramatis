import { useEffect, useRef } from 'react'
import type { Character } from '../api'
import { assistant } from './store'

let opened = 0

/** The editor's form, for the Sidebar Assistant to see and edit. Each form opened is a conversation of its own. */
export function useAssistantForm(character: Character, setCharacter: (character: Character) => void, clean: (character: Character) => Character) {
  const latest = useRef(character)
  const key = useRef('')
  if (!key.current) key.current = `form-${Date.now().toString(36)}-${(opened += 1)}`
  useEffect(() => {
    const form = {
      key: key.current, get: () => latest.current, clean: () => clean(latest.current),
      set: (next: Character) => { latest.current = next; setCharacter(next) },
    }
    assistant.register(form)
    return () => assistant.unregister(form.key)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    latest.current = character
    assistant.sync(character)
  }, [character])
}

/** The field the user moves into, from the `data-field` of the form field around it. */
export function trackFocus(target: EventTarget) {
  const field = target instanceof HTMLElement ? target.closest<HTMLElement>('[data-field]') : null
  const name = field?.dataset.field
  if (field && name) assistant.setFocus({ field: name, label: field.querySelector(':scope > label')?.textContent ?? name })
}
