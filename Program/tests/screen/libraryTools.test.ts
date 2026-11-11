/** src/LibraryTools.tsx: what a backup brought back, in a sentence. */
import { describe, expect, it } from 'vitest'
import { restoredLine } from '../../src/LibraryTools'

describe('restoredLine', () => {
  it('says what came back, what was left and what could not be read', () => {
    expect(restoredLine({ characters: 3, casts: 1, kept: 2, skipped: 0 })).toBe('Brought back 3 characters and 1 cast. 2 already here were left as they are.')
    expect(restoredLine({ characters: 1, casts: 0, kept: 1, skipped: 1 })).toBe("Brought back 1 character. 1 already here was left as it is. 1 file couldn't be read.")
    expect(restoredLine({ characters: 0, casts: 0, kept: 4, skipped: 0 })).toBe('Nothing to bring back. 4 already here were left as they are.')
  })
})
