/** src/drafts.ts: a form with unsaved changes is kept in this browser's storage, one entry per draft. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { emptyCharacter } from '../../src/api'

class Memory {
  items = new Map<string, string>()
  get length() { return this.items.size }
  key(index: number) { return [...this.items.keys()][index] ?? null }
  getItem(name: string) { return this.items.get(name) ?? null }
  setItem(name: string, value: string) { this.items.set(name, value) }
  removeItem(name: string) { this.items.delete(name) }
}

const draft = (key: string, name: string, changed = true) =>
  ({ key, saved: null, begun: { character: { ...emptyCharacter(), name }, portrait: 'data:image/png;base64,AAAA' }, changed })

let storage: Memory
beforeEach(() => { storage = new Memory(); vi.stubGlobal('localStorage', storage); vi.useFakeTimers(); vi.resetModules() })
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('drafts', () => {
  it('moves the old all-in-one entry into one entry per draft', async () => {
    storage.setItem('dramatis:drafts', JSON.stringify({ abc: draft('abc', 'Dana') }))
    const { draftStore } = await import('../../src/drafts')
    expect(draftStore.get('abc')?.begun.character.name).toBe('Dana')
    expect(storage.getItem('dramatis:drafts')).toBeNull()
    expect(storage.getItem('dramatis:draft:abc')).not.toBeNull()
  })

  it('stores a changed draft without its portrait, and drops one without changes', async () => {
    const { draftStore } = await import('../../src/drafts')
    draftStore.put(draft('new', 'Ruth'))
    expect(storage.getItem('dramatis:draft:new')).toBeNull()  // written a moment later, not on every key
    vi.advanceTimersByTime(500)
    const stored = JSON.parse(storage.getItem('dramatis:draft:new')!)
    expect(stored.begun.character.name).toBe('Ruth')
    expect(stored.begun.portrait).toBeUndefined()
    draftStore.put(draft('new', 'Ruth', false))
    vi.advanceTimersByTime(500)
    expect(storage.getItem('dramatis:draft:new')).toBeNull()
    expect(draftStore.atRisk()).toBe(false)
  })

  it('skips an unreadable entry', async () => {
    storage.setItem('dramatis:draft:bad', '{not json')
    storage.setItem('dramatis:draft:ok', JSON.stringify(draft('ok', 'Ida')))
    const { draftStore } = await import('../../src/drafts')
    expect(draftStore.get('bad')).toBeUndefined()
    expect(draftStore.get('ok')?.begun.character.name).toBe('Ida')
  })
})
