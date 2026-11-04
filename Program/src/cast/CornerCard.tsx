import { useId, useState, type ReactNode } from 'react'
import { Crosshair, ExternalLink, Sparkles, Trash2, Unlink, X } from 'lucide-react'
import type { Summary } from '../api'
import { LIMITS, tagOf, words, type Corner, type TagInfo } from '../castApi'

export interface CornerContext {
  tags: TagInfo[]
  characters: Summary[]
  names: Record<string, string>
  focusId: string | null
  highlighted: Set<string>
  register: (id: string, element: HTMLElement | null) => void
  onDraft: (cornerId: string) => void
  onOpenCharacter: (id: string) => void
  onFocus: (id: string | null) => void
}

interface Props {
  corner: Corner
  /** An outer corner holds a why; an inner one, a how. */
  outer: boolean
  context: CornerContext
  stanceHint?: string
  /** Role-specific texts a template asks for (the four-corner web), by key. */
  fieldKeys?: string[]
  onChange: (change: Partial<Corner>) => void
  onRemove?: () => void
  /** Actions shown in the card's head, after its name. */
  actions?: ReactNode
  children?: ReactNode
}

/** One corner of a square: its name, its stance, its how-tags, a note and the character who stands there. */
export function CornerCard({ corner, outer, context, stanceHint, fieldKeys = [], onChange, onRemove, actions, children }: Props) {
  const id = useId()
  const lit = context.highlighted.has(corner.id)
  return (
    <article className={`corner${outer ? ' side' : ''}${lit ? ' lit' : ''}`} ref={(element) => context.register(corner.id, element)} aria-label={corner.label || (outer ? 'Unnamed side' : 'Unnamed corner')}>
      <div className="corner-head">
        <input className="corner-name" aria-label={outer ? 'Name of this side' : 'Name of this corner'} value={corner.label} maxLength={LIMITS.label}
          placeholder={outer ? 'Name this side' : 'Name this corner'} onChange={(event) => onChange({ label: event.target.value })} />
        {actions}
        {onRemove && <button type="button" className="icon danger" aria-label={`Remove ${corner.label || 'this corner'}`} onClick={onRemove}><Trash2 size={14} /></button>}
      </div>
      <label className="sr-only" htmlFor={`${id}-stance`}>{outer ? 'Why' : 'How'}</label>
      <textarea id={`${id}-stance`} className="stance" rows={2} value={corner.stance} maxLength={LIMITS.stance}
        placeholder={stanceHint || (outer ? 'Why: what this side wants' : 'How: the way this corner goes after it')} onChange={(event) => onChange({ stance: event.target.value })} />
      {fieldKeys.map((key) => (
        <div className="field" key={key}>
          <label htmlFor={`${id}-${key}`}>{words(key)}</label>
          <textarea id={`${id}-${key}`} rows={2} value={corner.fields[key] ?? ''} maxLength={LIMITS.field}
            onChange={(event) => onChange({ fields: { ...corner.fields, [key]: event.target.value } })} />
        </div>
      ))}
      <TagPicker tags={corner.tags} bank={context.tags} onChange={(tags) => onChange({ tags })} />
      <details className="corner-note" open={!!corner.note || undefined}>
        <summary>Note</summary>
        <textarea aria-label="Note" rows={2} value={corner.note} maxLength={LIMITS.note} onChange={(event) => onChange({ note: event.target.value })} />
      </details>
      <CharacterSlot corner={corner} context={context} onChange={onChange} />
      {children}
    </article>
  )
}

/** How a corner fights, as tags: picked from the bank or typed new. Shared tags across sides are what resonance finds. */
function TagPicker({ tags, bank, onChange }: { tags: string[]; bank: TagInfo[]; onChange: (tags: string[]) => void }) {
  const list = useId()
  const [text, setText] = useState('')
  const label = (tag: string) => bank.find((item) => item.id === tag)?.label ?? tag
  const add = (raw: string) => {
    const typed = raw.trim()
    const tag = bank.find((item) => item.label.toLowerCase() === typed.toLowerCase())?.id ?? tagOf(typed)
    if (tag && !tags.includes(tag) && tags.length < LIMITS.tags) onChange([...tags, tag])
    setText('')
  }
  return (
    <div className="tags">
      {tags.map((tag) => (
        <span key={tag} className="tag">{label(tag)}<button type="button" className="icon" aria-label={`Remove the tag ${label(tag)}`} onClick={() => onChange(tags.filter((item) => item !== tag))}><X size={12} /></button></span>
      ))}
      {tags.length < LIMITS.tags && (
        <input className="tag-input" list={list} value={text} aria-label="Add a how-tag" placeholder={tags.length ? 'Another tag' : 'How-tags: force, charm…'}
          onChange={(event) => {
            const value = event.target.value
            if (bank.some((item) => item.id === value)) add(value)
            else setText(value)
          }}
          onKeyDown={(event) => {
            // Enter adds the tag; it never submits the board.
            if (event.key === 'Enter' || (event.key === ',' && text.trim())) { event.preventDefault(); if (text.trim()) add(text) }
            if (event.key === 'Backspace' && !text && tags.length) onChange(tags.slice(0, -1))
          }}
          onBlur={() => { if (text.trim()) add(text) }} />
      )}
      <datalist id={list}>{bank.filter((item) => !tags.includes(item.id)).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</datalist>
    </div>
  )
}

/** Who stands in this corner: a character from the library, or one drafted for it through the quick start. */
function CharacterSlot({ corner, context, onChange }: { corner: Corner; context: CornerContext; onChange: (change: Partial<Corner>) => void }) {
  const id = useId()
  const linked = corner.character_id
  if (linked) {
    const found = context.characters.find((item) => item.id === linked)
    const name = found?.name ?? context.names[linked]
    const missing = !found && context.characters.length > 0 && !context.names[linked]
    const focused = context.focusId === linked
    return (
      <div className="slot linked">
        {found?.portrait ? <img className="thumb small-thumb" src={`/api/characters/${linked}/portrait.png?at=${found.updated}`} alt="" /> : <span className="thumb small-thumb" aria-hidden />}
        <strong className={`grow${missing ? ' error' : ''}`}>{missing ? 'No longer in the library' : name || 'Loading…'}</strong>
        {!missing && <button type="button" className="icon" aria-label={`Open ${name}`} title="Open their form" onClick={() => context.onOpenCharacter(linked)}><ExternalLink size={14} /></button>}
        {!missing && <button type="button" className="icon" aria-pressed={focused} aria-label={focused ? `Stop showing ${name}'s inner square` : `Show ${name}'s inner square`} title="Focus"
          onClick={() => context.onFocus(focused ? null : linked)}><Crosshair size={14} /></button>}
        <button type="button" className="icon" aria-label="Unlink them" title="Unlink" onClick={() => onChange({ character_id: null })}><Unlink size={14} /></button>
      </div>
    )
  }
  return (
    <div className="slot">
      <label className="sr-only" htmlFor={id}>Link a character</label>
      <select id={id} value="" onChange={(event) => event.target.value && onChange({ character_id: event.target.value })}>
        <option value="">Link a character…</option>
        {context.characters.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
      <button type="button" onClick={() => context.onDraft(corner.id)}><Sparkles size={14} aria-hidden /> Draft this character</button>
    </div>
  )
}
