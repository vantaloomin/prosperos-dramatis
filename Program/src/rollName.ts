import { useState } from 'react'
import { sendJson } from './api'

/** What a name is rolled from: what the form says of them so far. */
export interface NameFrom { gender: string; age: number | null; setting: string; about: string }

/** Roll a name (dramatis/names.py, Companion's name banks, no model) for a Name field: offered while the field is empty
 * or still holds the name it rolled, so a name the user typed is never rolled over. */
export function useNameRoll(name: string, onName: (name: string) => void, from: () => NameFrom) {
  const [rolled, setRolled] = useState('')
  const [busy, setBusy] = useState(false)
  const run = async () => {
    if (busy) return
    setBusy(true)
    try {
      const found = await sendJson<{ name: string }>('/api/names/roll', 'POST', from())
      setRolled(found.name)
      onName(found.name)
    } catch {
      // Nothing to say: the field stays as it was, and the button is still there to try again.
    } finally {
      setBusy(false)
    }
  }
  return !name.trim() || name === rolled ? run : undefined
}
