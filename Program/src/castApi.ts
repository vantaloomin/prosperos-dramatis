/** Casts: the shapes and calls of the cast routes (the Shared contract of the Cast-layer spec), and the pure edits the
 * board makes to a cast. Kept out of api.ts so the character side and the cast side change without touching each other. */
import { getJson, sendJson } from './api'

export type AxisKind = 'value' | 'means' | 'cost' | 'purity' | 'leadership' | 'secret' | 'goal-definition' | 'dilemma'
export type Depth = 'single' | 'partial' | 'full'
export type ResonanceRole = 'defector' | 'double-agent' | 'bridge' | 'mirror' | ''

export interface Axis { kind: AxisKind; label: string }
export interface Corner {
  id: string; label: string; stance: string; tags: string[]; role: string; fields: Record<string, string>
  character_id: string | null; note: string; depth: Depth; inner: Square | null
}
export interface Square { axis: Axis; question: string; corners: Corner[] }
export interface Resonance { a: string; b: string; on: string; role: ResonanceRole; status: 'confirmed' | 'dismissed'; note: string }
export interface CastRelationship { from: string; to: string; dynamic: string; hidden_tension: string; trust: number; notes: string }
export interface Cast {
  title: string; theme: string; genre: string; group: string; outer: Square; resonance: Resonance[]
  relationships: CastRelationship[]; focus_id: string | null
}

export interface Candidate { a: string; b: string; on: string }
export interface CastCheck { code: string; severity: 'warn' | 'info'; corners: string[]; message: string; fix: string }
export interface Computed { candidates: Candidate[]; checks: CastCheck[]; names: Record<string, string> }
export interface SavedCast { id: string; created: string; updated: string; cast: Cast; computed: Computed }
export interface CastSummary { id: string; title: string; theme: string; updated: string; characters: number }

/** `outer_only` marks a kind an inner square may not use (the dilemma). */
export interface AxisInfo { kind: AxisKind; label: string; help: string; outer_only?: boolean }
export interface GenreCorner { label: string; stance_hint?: string; role?: string; fields?: string[] }
/** `outer_axis` is the outer square's kind; `axis` the kind a split side takes; `split` the side worth splitting first. */
export interface Genre {
  id: string; name: string; outer_axis: AxisKind; axis: AxisKind; split: number | null; group: string; help: string; outer: GenreCorner[]; checks: string[]
}
export interface Group { id: string; name: string; shares: string; axis: AxisKind; roles: string[] }
export interface TagInfo { id: string; label: string }
export interface Templates { axes: AxisInfo[]; genres: Genre[]; groups: Group[]; tags: TagInfo[] }

export const AXIS_KINDS: AxisKind[] = ['value', 'means', 'cost', 'purity', 'leadership', 'secret', 'goal-definition', 'dilemma']
export const RESONANCE_ROLES: [ResonanceRole, string][] = [['', 'No role yet'], ['defector', 'Defector'], ['double-agent', 'Double agent'],
  ['bridge', 'Bridge'], ['mirror', 'Mirror']]
export const LIMITS = { title: 120, theme: 300, axis: 120, question: 300, label: 80, stance: 200, tags: 6, tag: 30, note: 600, field: 300,
  resonanceNote: 400, dynamic: 300, notes: 600 } as const

export const castCalls = {
  list: () => getJson<CastSummary[]>('/api/casts'),
  get: (id: string) => getJson<SavedCast>(`/api/casts/${id}`),
  save: (cast: Cast, id: string | null) => id ? sendJson<SavedCast>(`/api/casts/${id}`, 'PUT', { cast }) : sendJson<SavedCast>('/api/casts', 'POST', { cast }),
  remove: (id: string) => sendJson<{ ok: true }>(`/api/casts/${id}`, 'DELETE'),
  check: (cast: Cast) => sendJson<{ computed: Computed }>('/api/casts/check', 'POST', { cast }),
  templates: () => getJson<Templates>('/api/cast-templates'),
  exportUrl: (id: string) => `/api/casts/${id}/cast.json`,
  /** One card per character the cast names that is still in the library, zipped; 404 when none are. */
  cardsUrl: (id: string, target: 'prospero' | 'chat', kind: 'png' | 'json') => `/api/casts/${id}/cards.zip?for=${target}&kind=${kind}`,
}

/** A tag as the contract takes it: lowercase letters, digits and dashes, at most 30. */
export const tagOf = (text: string) => text.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, LIMITS.tag)
export const words = (key: string) => key.charAt(0).toUpperCase() + key.slice(1).replace(/[_-]+/g, ' ')

export function emptyCorner(id: string, label = '', extra: Partial<Corner> = {}): Corner {
  return { id, label, stance: '', tags: [], role: '', fields: {}, character_id: null, note: '', depth: 'single', inner: null, ...extra }
}

/** Every corner on the board, each with the outer corner (side) it sits under. An outer corner is its own side. */
export function corners(cast: Cast): { corner: Corner; side: Corner; inner: boolean }[] {
  return cast.outer.corners.flatMap((side) => [
    { corner: side, side, inner: false },
    ...(side.inner?.corners ?? []).map((corner) => ({ corner, side, inner: true })),
  ])
}

export const findCorner = (cast: Cast, id: string) => corners(cast).find((item) => item.corner.id === id)

/** A corner id no other corner uses: an outer side is a letter (a, b, ...), an inner corner its side's letter and a number. */
function nextFree(used: Set<string>, side?: string): string {
  if (!side) {
    for (const letter of 'abcdefghijklmnopqrstuvwxyz') if (!used.has(letter)) return letter
  }
  for (let n = 1; ; n++) if (!used.has(`${side ?? 'x'}${n}`)) return `${side ?? 'x'}${n}`
}

export const freshId = (cast: Cast, side?: string) => nextFree(new Set(corners(cast).map((item) => item.corner.id)), side)

/** A new cast from the start picks: a genre fills the outer square, else a blank board of four sides. */
export function newCast(theme: string, genre: Genre | undefined, group: Group | undefined): Cast {
  const cast: Cast = {
    title: '', theme, genre: genre?.id ?? '', group: group?.id ?? genre?.group ?? '',
    outer: { axis: { kind: genre?.outer_axis ?? 'value', label: '' }, question: '', corners: [] }, resonance: [], relationships: [], focus_id: null,
  }
  const outer = genre?.outer.length ? genre.outer.slice(0, 4) : [{ label: '' }, { label: '' }, { label: '' }, { label: '' }]
  for (const pick of outer) {
    cast.outer.corners.push(emptyCorner(freshId(cast), pick.label, {
      role: pick.role ?? '', fields: Object.fromEntries((pick.fields ?? []).map((key) => [key, ''])),
    }))
  }
  return cast
}

/** Change one corner, wherever it sits. */
export function editCorner(cast: Cast, id: string, change: (corner: Corner) => Corner): Cast {
  return {
    ...cast, outer: {
      ...cast.outer, corners: cast.outer.corners.map((side) => side.id === id ? change(side) : side.inner
        ? { ...side, inner: { ...side.inner, corners: side.inner.corners.map((corner) => corner.id === id ? change(corner) : corner) } } : side),
    },
  }
}

/** The depth an inner square of this many corners has: two is a partial split, three or four a full one. */
export const depthOf = (inner: Square | null): Depth => !inner ? 'single' : inner.corners.length <= 2 ? 'partial' : 'full'

/** Drop a corner (and, for a side, everything under it) with the resonance that names it. Squares keep at least two. */
export function dropCorner(cast: Cast, id: string): Cast {
  const gone = new Set([id, ...(cast.outer.corners.find((side) => side.id === id)?.inner?.corners.map((corner) => corner.id) ?? [])])
  const sides = cast.outer.corners.filter((side) => side.id !== id).map((side) => {
    if (!side.inner?.corners.some((corner) => corner.id === id)) return side
    const inner = { ...side.inner, corners: side.inner.corners.filter((corner) => corner.id !== id) }
    return { ...side, inner, depth: depthOf(inner) }
  })
  return { ...cast, outer: { ...cast.outer, corners: sides }, resonance: cast.resonance.filter((link) => !gone.has(link.a) && !gone.has(link.b)) }
}

/** Split a side: an inner square on its own axis, with two corners (Split in two) or three or four (Split this side). */
/** Split a side: an inner square on its own axis, with a corner per role (a group type's roles, or blanks). */
export function splitSide(cast: Cast, sideId: string, kind: AxisKind, question: string, roles: string[]): Cast {
  const used = new Set(corners(cast).map((item) => item.corner.id))
  const inner: Square = {
    axis: { kind, label: '' }, question, corners: roles.map((role) => {
      const id = nextFree(used, sideId)
      used.add(id)
      return emptyCorner(id, role ? words(role) : '', { role: tagOf(role) })
    }),
  }
  return editCorner(cast, sideId, (side) => ({ ...side, inner, depth: depthOf(inner) }))
}

export function mergeSide(cast: Cast, sideId: string): Cast {
  const side = cast.outer.corners.find((item) => item.id === sideId)
  const gone = new Set(side?.inner?.corners.map((corner) => corner.id) ?? [])
  const next = editCorner(cast, sideId, (corner) => ({ ...corner, inner: null, depth: 'single' }))
  return { ...next, resonance: next.resonance.filter((link) => !gone.has(link.a) && !gone.has(link.b)) }
}

export function addInnerCorner(cast: Cast, sideId: string): Cast {
  return editCorner(cast, sideId, (side) => {
    if (!side.inner || side.inner.corners.length >= 4) return side
    const inner = { ...side.inner, corners: [...side.inner.corners, emptyCorner(freshId(cast, sideId))] }
    return { ...side, inner, depth: depthOf(inner) }
  })
}

/** The same unordered pair, whichever way round it is written. */
export const samePair = (one: { a: string; b: string }, other: { a: string; b: string }) =>
  (one.a === other.a && one.b === other.b) || (one.a === other.b && one.b === other.a)

/** The idea the quick start opens with when the board drafts the character for a corner. */
export function draftIdea(cast: Cast, cornerId: string): string {
  const found = findCorner(cast, cornerId)
  if (!found) return ''
  const { corner, side, inner } = found
  const parts = [corner.label.trim() ? `${corner.label.trim()}.` : '']
  if (inner) {
    parts.push(`Belongs to ${side.label.trim() || 'one side'}${side.stance.trim() ? `, who want ${side.stance.trim()}` : ''}.`)
    if (corner.stance.trim()) parts.push(`Pursues it ${corner.stance.trim()}.`)
  } else if (corner.stance.trim()) parts.push(`Wants ${corner.stance.trim()}.`)
  if (cast.theme.trim()) parts.push(`The story asks: ${cast.theme.trim()}`)
  return parts.filter(Boolean).join(' ').slice(0, 2000)
}

/** Every character the cast links, in board order, without repeats. */
export const linkedCharacters = (cast: Cast) => [...new Set(corners(cast).map((item) => item.corner.character_id).filter((id): id is string => !!id))]
