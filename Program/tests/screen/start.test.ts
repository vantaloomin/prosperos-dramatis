/** src/Start.tsx: which apps a new character is made for, remembered between visits. */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { rememberedApps } from '../../src/Start'

const storage = (value: string | null) => ({ getItem: () => value, setItem: () => {}, removeItem: () => {} })
afterEach(() => vi.unstubAllGlobals())

describe('rememberedApps', () => {
  it('is all three until the user picks', () => {
    vi.stubGlobal('localStorage', storage(null))
    expect(rememberedApps()).toEqual(['companion', 'adventure', 'dungeon'])
  })

  it('keeps the apps picked, in the usual order, and ignores anything else', () => {
    vi.stubGlobal('localStorage', storage(JSON.stringify(['dungeon', 'nonsense', 'companion'])))
    expect(rememberedApps()).toEqual(['companion', 'dungeon'])
    vi.stubGlobal('localStorage', storage(JSON.stringify([])))
    expect(rememberedApps()).toEqual(['companion', 'adventure', 'dungeon'])
    vi.stubGlobal('localStorage', storage('{broken'))
    expect(rememberedApps()).toEqual(['companion', 'adventure', 'dungeon'])
  })
})
