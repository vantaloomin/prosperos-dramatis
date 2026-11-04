import { useEffect, useLayoutEffect, useState } from 'react'
import { Check, Users, X } from 'lucide-react'
import {
  LIMITS, RESONANCE_ROLES, findCorner, samePair, type Cast, type Computed, type Resonance, type ResonanceRole, type TagInfo,
} from '../castApi'
import { ResonanceActions } from './slots'

/** A link the board can show: a computed candidate, or a resonance the author confirmed. */
export interface Link { key: string; a: string; b: string; on: string; confirmed: boolean }

export const linkKey = (link: { a: string; b: string; on: string }) => [link.a, link.b].sort().join('~') + `~${link.on}`

/** Confirmed links, then the candidates the author has not answered yet, skipping any whose corners are gone. */
export function boardLinks(cast: Cast, computed: Computed | null): Link[] {
  const confirmed = cast.resonance.filter((link) => link.status === 'confirmed')
  const answered = (candidate: { a: string; b: string; on: string }) =>
    cast.resonance.some((link) => link.on === candidate.on && samePair(link, candidate))
  const all = [
    ...confirmed.map((link) => ({ key: linkKey(link), a: link.a, b: link.b, on: link.on, confirmed: true })),
    ...(computed?.candidates ?? []).filter((candidate) => !answered(candidate)).map((candidate) => ({ key: linkKey(candidate), ...candidate, confirmed: false })),
  ]
  return all.filter((link) => findCorner(cast, link.a) && findCorner(cast, link.b))
}

/** A line between two elements on the board. `from` and `to` are keys of registered elements (corner ids, or psyche impulses). */
export interface Line { key: string; from: string; to: string; kind: 'candidate' | 'confirmed' | 'psyche' }
interface Drawn { key: string; kind: Line['kind']; x1: number; y1: number; x2: number; y2: number }

/** Where the segment from a box's centre towards a point leaves the box. */
function edge(box: DOMRect, origin: DOMRect, toward: { x: number; y: number }) {
  const cx = box.left - origin.left + box.width / 2
  const cy = box.top - origin.top + box.height / 2
  const dx = toward.x - cx
  const dy = toward.y - cy
  const t = Math.min(1, dx ? box.width / 2 / Math.abs(dx) : Infinity, dy ? box.height / 2 / Math.abs(dy) : Infinity)
  return { x: cx + dx * t, y: cy + dy * t }
}

function centre(box: DOMRect, origin: DOMRect) {
  return { x: box.left - origin.left + box.width / 2, y: box.top - origin.top + box.height / 2 }
}

/** The SVG overlay: lines drawn edge to edge between the boxes they join, and a badge per link at each line's middle.
 * Measured after every layout change, so it follows the cards as they grow. Hidden below 720 px (the list takes over). */
export function ResonanceLines({ board, elements, lines, links, selected, tags, onPick }: {
  board: HTMLElement | null; elements: Map<string, HTMLElement>; lines: Line[]; links: Link[]; selected: string | null
  tags: TagInfo[]; onPick: (key: string) => void
}) {
  const [drawn, setDrawn] = useState<Drawn[]>([])
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!board) return
    const observer = new ResizeObserver(() => setTick((value) => value + 1))
    observer.observe(board)
    for (const element of elements.values()) observer.observe(element)
    return () => observer.disconnect()
  })
  useLayoutEffect(() => {
    if (!board) return
    const origin = board.getBoundingClientRect()
    const next: Drawn[] = []
    for (const line of lines) {
      const from = elements.get(line.from)?.getBoundingClientRect()
      const to = elements.get(line.to)?.getBoundingClientRect()
      if (!from || !to || !from.width || !to.width) continue
      const start = edge(from, origin, centre(to, origin))
      const end = edge(to, origin, centre(from, origin))
      next.push({ key: line.key, kind: line.kind, x1: start.x, y1: start.y, x2: end.x, y2: end.y })
    }
    const round = (items: Drawn[]) => JSON.stringify(items.map((item) => [item.key, Math.round(item.x1), Math.round(item.y1), Math.round(item.x2), Math.round(item.y2)]))
    if (round(next) !== round(drawn)) setDrawn(next)
  })
  void tick
  const pairs = new Map<string, Link[]>()
  for (const link of links) {
    const pair = [link.a, link.b].sort().join('~')
    pairs.set(pair, [...(pairs.get(pair) ?? []), link])
  }
  const label = (tag: string) => tags.find((item) => item.id === tag)?.label ?? tag
  return (
    <div className="lines" aria-hidden={!links.length}>
      <svg>
        {drawn.map((line) => <line key={line.key} className={line.kind} x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2} />)}
      </svg>
      {[...pairs.entries()].map(([pair, group]) => {
        const line = drawn.find((item) => item.key === pair)
        if (!line) return null
        return (
          <div key={pair} className="badges" style={{ left: (line.x1 + line.x2) / 2, top: (line.y1 + line.y2) / 2 }}>
            {group.map((link) => (
              <button key={link.key} type="button" className={`badge${link.confirmed ? ' confirmed' : ''}`} aria-pressed={selected === link.key} onClick={() => onPick(link.key)}
                aria-label={`${link.confirmed ? 'Confirmed link' : 'Possible link'} on ${label(link.on)}`}>
                {link.confirmed && <Check size={11} aria-hidden />}{label(link.on)}
              </button>
            ))}
          </div>
        )
      })}
    </div>
  )
}

/** The same links as a list, for narrow screens where lines would not fit. */
export function ResonanceList({ cast, links, selected, tags, onPick }: { cast: Cast; links: Link[]; selected: string | null; tags: TagInfo[]; onPick: (key: string) => void }) {
  if (!links.length) return null
  const name = (id: string) => findCorner(cast, id)?.corner.label || 'Unnamed'
  const label = (tag: string) => tags.find((item) => item.id === tag)?.label ?? tag
  return (
    <ul className="resonance-list">
      {links.map((link) => (
        <li key={link.key}>
          <button type="button" aria-pressed={selected === link.key} onClick={() => onPick(link.key)}>
            {link.confirmed ? <Check size={13} aria-hidden /> : <span className="dash" aria-hidden />}
            <span>{name(link.a)} and {name(link.b)}, by {label(link.on)}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

/** One link, opened: confirm it with a role and a note, or dismiss it. A confirmed link can offer the two characters'
 * relationship records, both directions, empty for the author to fill. */
export function ResonancePanel({ cast, link, tags, update, onClose }: {
  cast: Cast; link: Link; tags: TagInfo[]; update: (change: (cast: Cast) => Cast) => void; onClose: () => void
}) {
  const stored = cast.resonance.find((item) => item.on === link.on && samePair(item, link))
  const [role, setRole] = useState<ResonanceRole>(stored?.role ?? '')
  const [note, setNote] = useState(stored?.note ?? '')
  const a = findCorner(cast, link.a)?.corner
  const b = findCorner(cast, link.b)?.corner
  const label = tags.find((item) => item.id === link.on)?.label ?? link.on
  const answer = (status: Resonance['status']) => update((current) => ({
    ...current, resonance: [...current.resonance.filter((item) => !(item.on === link.on && samePair(item, link))), { a: link.a, b: link.b, on: link.on, role, status, note }],
  }))
  const edit = (part: Partial<Resonance>) => update((current) => ({
    ...current, resonance: current.resonance.map((item) => item.on === link.on && samePair(item, link) ? { ...item, ...part } : item),
  }))
  const people = [a?.character_id, b?.character_id]
  const [first, second] = people
  const missing = first && second && first !== second
    ? [[first, second], [second, first]].filter(([from, to]) => !cast.relationships.some((item) => item.from === from && item.to === to)) : []
  return (
    <div className="resonance-panel card" role="group" aria-label="Resonance link">
      <div className="row">
        <strong className="grow">{a?.label || 'Unnamed'} and {b?.label || 'Unnamed'} both work by {label}</strong>
        <button type="button" className="icon" aria-label="Close" onClick={onClose}><X size={15} /></button>
      </div>
      <div className="row" role="radiogroup" aria-label="Role">
        {RESONANCE_ROLES.map(([value, name]) => (
          <button key={value} type="button" role="radio" className="chip" aria-checked={role === value}
            onClick={() => { setRole(value); if (stored?.status === 'confirmed') edit({ role: value }) }}>{name}</button>
        ))}
      </div>
      <textarea aria-label="Note on this link" rows={2} maxLength={LIMITS.resonanceNote} value={note} placeholder="What passes between them"
        onChange={(event) => { setNote(event.target.value); if (stored?.status === 'confirmed') edit({ note: event.target.value }) }} />
      <div className="row">
        {link.confirmed ? <>
          <button type="button" onClick={() => { update((current) => ({ ...current, resonance: current.resonance.filter((item) => !(item.on === link.on && samePair(item, link))) })); onClose() }}>Undo the link</button>
          {missing.length > 0 && (
            <button type="button" onClick={() => update((current) => ({
              ...current, relationships: [...current.relationships, ...missing.map(([from, to]) => ({ from, to, dynamic: '', hidden_tension: '', trust: 5, notes: '' }))],
            }))}><Users size={14} aria-hidden /> Add their relationship</button>
          )}
          {stored && <ResonanceActions cast={cast} update={update} link={stored} />}
        </> : <>
          <button type="button" className="primary" onClick={() => answer('confirmed')}><Check size={14} aria-hidden /> Confirm</button>
          <button type="button" onClick={() => { answer('dismissed'); onClose() }}>Dismiss</button>
        </>}
      </div>
    </div>
  )
}

/** Links the author dismissed, so one can be brought back. */
export function Dismissed({ cast, tags, update }: { cast: Cast; tags: TagInfo[]; update: (change: (cast: Cast) => Cast) => void }) {
  const dismissed = cast.resonance.filter((link) => link.status === 'dismissed')
  if (!dismissed.length) return null
  const name = (id: string) => findCorner(cast, id)?.corner.label || 'Unnamed'
  const label = (tag: string) => tags.find((item) => item.id === tag)?.label ?? tag
  return (
    <details className="dismissed small">
      <summary>Dismissed links ({dismissed.length})</summary>
      <ul>
        {dismissed.map((link) => (
          <li key={linkKey(link)}>
            {name(link.a)} and {name(link.b)}, by {label(link.on)}{' '}
            <button type="button" className="link" onClick={() => update((current) => ({ ...current, resonance: current.resonance.filter((item) => item !== link) }))}>Bring back</button>
          </li>
        ))}
      </ul>
    </details>
  )
}
