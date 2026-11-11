/** Where the screen is, as the URL's hash, so a reload lands where it was and Back goes where it was before:
 * `#/` the quick start, `#/character/<id>` a saved character, `#/draft/<key>` a new one not saved yet,
 * `#/new-cast` a new cast's first page, `#/cast/<id>` a cast's board (`#/cast/new` one not saved yet), and `#/models`
 * the Models dialog over the quick start. */
export type Address =
  | { kind: 'start' }
  | { kind: 'character'; id: string }
  | { kind: 'draft'; key: string }
  | { kind: 'new-cast' }
  | { kind: 'cast'; key: string }
  | { kind: 'models' }

const PART = /^[A-Za-z0-9_-]{1,80}$/

export function addressText(address: Address): string {
  switch (address.kind) {
    case 'start': return '#/'
    case 'character': return `#/character/${address.id}`
    case 'draft': return `#/draft/${address.key}`
    case 'new-cast': return '#/new-cast'
    case 'cast': return `#/cast/${address.key}`
    case 'models': return '#/models'
  }
}

/** The address a hash names; anything else is the quick start. */
export function readAddress(hash: string): Address {
  const [kind, part, ...rest] = hash.replace(/^#\/?/, '').split('/')
  const named = part !== undefined && PART.test(part) && !rest.length
  if (kind === 'character' && named) return { kind: 'character', id: part }
  if (kind === 'draft' && named) return { kind: 'draft', key: part }
  if (kind === 'cast' && named) return { kind: 'cast', key: part }
  if (kind === 'new-cast' && part === undefined) return { kind: 'new-cast' }
  if (kind === 'models' && part === undefined) return { kind: 'models' }
  return { kind: 'start' }
}

/** A new character or cast that has just been saved takes its id's address in place of its unsaved one, so Back
 * does not go to an address that no longer names anything. */
export const replaces = (before: string, after: string) =>
  (before.startsWith('#/draft/') && after.startsWith('#/character/')) || (before === '#/cast/new' && after.startsWith('#/cast/'))
