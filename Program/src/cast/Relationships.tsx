import { useId, type ReactNode } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import type { Summary } from '../api'
import { LIMITS, linkedCharacters, type Cast, type CastRelationship } from '../castApi'
import { RelationshipActions } from './slots'

/** How each character sees another: one directed row per ordered pair, never from someone to themself. */
export function Relationships({ cast, characters, names, update }: {
  cast: Cast; characters: Summary[]; names: Record<string, string>; update: (change: (cast: Cast) => Cast) => void
}) {
  const linked = linkedCharacters(cast)
  // The cast's own characters first, then the rest of the library, then any end that is no longer in it.
  const ids = [...new Set([...linked, ...characters.map((item) => item.id), ...cast.relationships.flatMap((row) => [row.from, row.to])])]
  const name = (id: string) => characters.find((item) => item.id === id)?.name ?? names[id] ?? 'No longer in the library'
  const taken = (from: string, to: string, except: number) => cast.relationships.some((row, index) => index !== except && row.from === from && row.to === to)
  const pool = linked.length >= 2 ? linked : ids
  const open = pool.flatMap((from) => pool.filter((to) => to !== from && !taken(from, to, -1)).map((to) => [from, to] as const))[0]
  const setRow = (index: number, part: Partial<CastRelationship>) => update((current) => ({
    ...current, relationships: current.relationships.map((row, at) => at === index ? { ...row, ...part } : row),
  }))
  return (
    <section className="relationships" aria-labelledby="relationships-title">
      <h3 id="relationships-title">Relationships</h3>
      {cast.relationships.map((row, index) => (
        <RelationshipRow key={index} row={row} ids={ids} name={name} taken={(from, to) => taken(from, to, index)} onChange={(part) => setRow(index, part)}
          onRemove={() => update((current) => ({ ...current, relationships: current.relationships.filter((_, at) => at !== index) }))}>
          {!row.dynamic && !row.hidden_tension && <RelationshipActions cast={cast} update={update} index={index} />}
        </RelationshipRow>
      ))}
      <button type="button" className="link" disabled={!open || cast.relationships.length >= 120} title={open ? undefined : 'Link two characters first'}
        onClick={() => open && update((current) => ({
          ...current, relationships: [...current.relationships, { from: open[0], to: open[1], dynamic: '', hidden_tension: '', trust: 5, notes: '' }],
        }))}><Plus size={13} aria-hidden /> Add a relationship</button>
    </section>
  )
}

function RelationshipRow({ row, ids, name, taken, onChange, onRemove, children }: {
  row: CastRelationship; ids: string[]; name: (id: string) => string; taken: (from: string, to: string) => boolean
  onChange: (part: Partial<CastRelationship>) => void; onRemove: () => void; children?: ReactNode
}) {
  const id = useId()
  return (
    <div className="relationship card">
      <div className="pair">
        <select aria-label="Who" value={row.from} onChange={(event) => onChange({ from: event.target.value })}>
          {ids.map((item) => <option key={item} value={item} disabled={item === row.to || taken(item, row.to)}>{name(item)}</option>)}
        </select>
        <span className="muted">sees</span>
        <select aria-label="Whom" value={row.to} onChange={(event) => onChange({ to: event.target.value })}>
          {ids.map((item) => <option key={item} value={item} disabled={item === row.from || taken(row.from, item)}>{name(item)}</option>)}
        </select>
        <button type="button" className="icon danger" aria-label={`Remove how ${name(row.from)} sees ${name(row.to)}`} onClick={onRemove}><Trash2 size={14} /></button>
      </div>
      <div className="grid two">
        <div className="field"><label htmlFor={`${id}-dynamic`}>Dynamic</label>
          <input id={`${id}-dynamic`} value={row.dynamic} maxLength={LIMITS.dynamic} onChange={(event) => onChange({ dynamic: event.target.value })} /></div>
        <div className="field"><label htmlFor={`${id}-tension`}>Hidden tension</label>
          <input id={`${id}-tension`} value={row.hidden_tension} maxLength={LIMITS.dynamic} onChange={(event) => onChange({ hidden_tension: event.target.value })} /></div>
      </div>
      <div className="trust field">
        <label htmlFor={`${id}-trust`}>Trust <strong>{row.trust}</strong> of 10</label>
        <input id={`${id}-trust`} type="range" min={1} max={10} value={row.trust} onChange={(event) => onChange({ trust: Number(event.target.value) })} />
      </div>
      <details open={!!row.notes || undefined}>
        <summary>Notes</summary>
        <textarea aria-label="Notes" rows={2} value={row.notes} maxLength={LIMITS.notes} onChange={(event) => onChange({ notes: event.target.value })} />
      </details>
      {children}
    </div>
  )
}
