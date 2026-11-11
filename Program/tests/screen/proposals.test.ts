/** src/proposals.ts: a model's text stands in its field at once, Keep drops the mark, Put back restores the user's own. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { emptyCharacter, type Character } from '../../src/api'
import { pathOf, proposals, same, valueAt, withValue } from '../../src/proposals'

function openForm(key = 'form-1', start: Partial<Character> = {}) {
  let character: Character = { ...emptyCharacter(), name: 'Dana', about: 'Mine.', ...start }
  proposals.register({ key, get: () => character, set: (next) => { character = next } })
  return { now: () => character }
}

afterEach(() => { proposals.unregister('form-1'); proposals.forget('form-1'); vi.unstubAllGlobals() })

describe('where a field sits', () => {
  it('reads dotted keys, the psyche and Companion fields', () => {
    expect(pathOf('about')).toEqual(['about'])
    expect(pathOf('arc.lie')).toEqual(['arc', 'lie'])
    expect(pathOf('psyche.was')).toEqual(['psyche', 'was', 'text'])
    expect(pathOf('routine')).toEqual(['companion', 'routine'])
  })

  it('sets a psyche field on a character with no psyche yet', () => {
    const set = withValue(emptyCharacter(), pathOf('psyche.was'), 'The eldest.')
    expect(valueAt(set, ['psyche', 'was', 'text'])).toBe('The eldest.')
    expect(valueAt(set, ['psyche', 'expected', 'text'])).toBe('')
  })

  it('counts blank lines and edges as the same', () => {
    expect(same(['a', ' '], ['a'])).toBe(true)
    expect(same(' text ', 'text')).toBe(true)
    expect(same('', null)).toBe(true)
    expect(same('a', 'b')).toBe(false)
  })
})

describe('a proposal', () => {
  it('stands in its field, and Keep keeps it', () => {
    const form = openForm()
    const id = proposals.propose({ field: 'about', label: 'About', value: 'Written.', source: 'help', hits: [] })
    expect(form.now().about).toBe('Written.')
    expect(proposals.get().open.about.before).toBe('Mine.')
    expect(proposals.written()).toEqual(['about'])
    proposals.keep('about')
    expect(proposals.get().open).toEqual({})
    expect(proposals.outcome(id)).toBe('kept')
    expect(form.now().about).toBe('Written.')
  })

  it('a second one for the field keeps the first one\'s before, so Put back goes to the user\'s own text', () => {
    const form = openForm()
    const first = proposals.propose({ field: 'about', label: 'About', value: 'One.', source: 'help', hits: [] })
    proposals.propose({ field: 'about', label: 'About', value: 'Two.', source: 'assistant', hits: [] })
    expect(proposals.outcome(first)).toBe('replaced')
    proposals.putBack('about', false)
    expect(form.now().about).toBe('Mine.')
    expect(proposals.written()).toEqual([])
  })

  it('asks before putting back over the user\'s own edit of it', () => {
    const form = openForm()
    proposals.propose({ field: 'about', label: 'About', value: 'Written.', source: 'help', hits: [] })
    proposals.form()!.set({ ...form.now(), about: 'Written, then edited.' })
    const confirm = vi.fn(() => false)
    vi.stubGlobal('window', { confirm })
    proposals.putBack('about')
    expect(confirm).toHaveBeenCalledOnce()
    expect(form.now().about).toBe('Written, then edited.')
  })

  it('comes back with its own form after another character was open', () => {
    openForm()
    proposals.propose({ field: 'wants', label: 'Wants', value: 'Rest.', source: 'help', hits: [] })
    proposals.unregister('form-1')
    openForm('form-2')
    expect(proposals.get().open).toEqual({})
    proposals.unregister('form-2')
    openForm()
    expect(Object.keys(proposals.get().open)).toEqual(['wants'])
  })

  it('Keep all and Put back all settle every open one', () => {
    const form = openForm()
    proposals.propose({ field: 'about', label: 'About', value: 'A.', source: 'assistant', hits: [] })
    proposals.propose({ field: 'wants', label: 'Wants', value: 'B.', source: 'assistant', hits: [] })
    proposals.putBackAll()
    expect(form.now().about).toBe('Mine.')
    expect(form.now().wants).toBe('')
    proposals.propose({ field: 'fears', label: 'Fears', value: 'C.', source: 'assistant', hits: [] })
    expect(proposals.keepAll()).toBe(1)
  })
})
