/** src/castApi.ts: the board's pure edits, which every button and the Cast AI's Keep and Put back go through. */
import { describe, expect, it } from 'vitest'
import {
  addInnerCorner, corners, draftIdea, dropCorner, editCorner, mergeSide, newCast, placeProposal, setLinkNote, splitSide,
  tagOf, unplaceProposal, type Cast,
} from '../../src/castApi'

const blank = (): Cast => newCast('Is order worth what it costs?', undefined, undefined)

describe('the board', () => {
  it('starts as four blank sides, a to d', () => {
    expect(blank().outer.corners.map((side) => side.id)).toEqual(['a', 'b', 'c', 'd'])
  })

  it('splits a side into roles, adds a fourth, and merges it back with its links', () => {
    let cast = splitSide(blank(), 'a', 'means', 'How?', ['zealot', 'pragmatist', ''])
    const side = cast.outer.corners[0]
    expect(side.depth).toBe('full')
    expect(side.inner!.corners.map((corner) => [corner.id, corner.label, corner.role])).toEqual(
      [['a1', 'Zealot', 'zealot'], ['a2', 'Pragmatist', 'pragmatist'], ['a3', '', '']])
    cast = addInnerCorner(cast, 'a')
    expect(cast.outer.corners[0].inner!.corners).toHaveLength(4)
    expect(addInnerCorner(cast, 'a').outer.corners[0].inner!.corners).toHaveLength(4)  // four is the most
    cast = { ...cast, resonance: [{ a: 'a1', b: 'b', on: 'force', role: '', status: 'confirmed', note: '' }] }
    cast = mergeSide(cast, 'a')
    expect(cast.outer.corners[0].inner).toBeNull()
    expect(cast.resonance).toEqual([])
  })

  it('dropping an inner corner leaves a partial split and takes its links', () => {
    let cast = splitSide(blank(), 'b', 'means', '', ['', '', ''])
    cast = { ...cast, resonance: [{ a: 'b3', b: 'c', on: 'law', role: '', status: 'dismissed', note: '' }] }
    cast = dropCorner(cast, 'b3')
    expect(cast.outer.corners[1].depth).toBe('partial')
    expect(cast.resonance).toEqual([])
  })

  it('writes a corner\'s idea for the quick start from its side, its how and the theme', () => {
    let cast = splitSide(blank(), 'a', 'means', '', ['', ''])
    cast = editCorner(cast, 'a', (side) => ({ ...side, label: 'The Order', stance: 'stability' }))
    cast = editCorner(cast, 'a1', (corner) => ({ ...corner, label: 'Zealot', stance: 'by purity' }))
    expect(draftIdea(cast, 'a1')).toBe('Zealot. Belongs to The Order, who want stability. Pursues it by purity. ' +
      'The story asks: Is order worth what it costs?')
  })

  it('tags are lowercase words joined by hyphens', () => {
    expect(tagOf('  Quiet Deals! ')).toBe('quiet-deals')
  })
})

describe('Cast AI proposals', () => {
  const proposal = { corner_id: null, label: 'The Free', stance: 'liberty', tags: ['force'], role: '' }

  it('a suggestion goes over a corner, and Put back restores its texts', () => {
    const cast = blank()
    const placed = placeProposal(cast, 'outer', proposal, 'b')!
    expect(placed.id).toBe('b')
    expect(corners(placed.cast)[1].corner.label).toBe('The Free')
    const back = unplaceProposal(placed.cast, 'b', { label: '', stance: '', tags: [], role: '', fields: {} })
    expect(corners(back)[1].corner.label).toBe('')
  })

  it('a new corner needs room, and Put back takes it away again', () => {
    const three = dropCorner(blank(), 'd')
    const placed = placeProposal(three, 'outer', proposal, null)!
    expect(placed.cast.outer.corners).toHaveLength(4)
    expect(placeProposal(placed.cast, 'outer', proposal, null)).toBeNull()
    expect(unplaceProposal(placed.cast, placed.id, null).outer.corners).toHaveLength(3)
  })

  it('a turn is written into the link, whichever way round it is named', () => {
    const cast = { ...blank(), resonance: [{ a: 'a', b: 'b', on: 'law', role: '' as const, status: 'confirmed' as const, note: '' }] }
    expect(setLinkNote(cast, { a: 'b', b: 'a', on: 'law' }, 'She crosses at the trial.').resonance[0].note)
      .toBe('She crosses at the trial.')
  })
})
