/** src/address.ts: the view in the URL's hash. */
import { describe, expect, it } from 'vitest'
import { addressText, readAddress, replaces, type Address } from '../../src/address'

describe('address', () => {
  it('reads back every address it writes', () => {
    const all: Address[] = [{ kind: 'start' }, { kind: 'character', id: '06c0befa15ff' }, { kind: 'draft', key: 'new-1794' },
      { kind: 'new-cast' }, { kind: 'cast', key: 'new' }, { kind: 'cast', key: 'abc123' }, { kind: 'models' }]
    for (const address of all) expect(readAddress(addressText(address))).toEqual(address)
  })

  it('takes anything it does not know as the quick start', () => {
    for (const hash of ['', '#', '#/nowhere', '#/character/', '#/character/a/b', '#/cast/<script>', '#/models/x']) {
      expect(readAddress(hash)).toEqual({ kind: 'start' })
    }
  })

  it('lets a first save replace the unsaved address, and nothing else', () => {
    expect(replaces('#/draft/new-1', '#/character/abc')).toBe(true)
    expect(replaces('#/cast/new', '#/cast/abc')).toBe(true)
    expect(replaces('#/character/abc', '#/character/def')).toBe(false)
    expect(replaces('#/', '#/draft/new-1')).toBe(false)
  })
})
