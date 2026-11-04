import { useState } from 'react'
import { Trash2, Undo2 } from 'lucide-react'
import { type CardParts } from './api'
import { Fold, ListField, TextArea } from './Fields'

const LIMIT = 40000
type CardText = 'mes_example' | 'scenario' | 'creator_notes' | 'system_prompt' | 'post_history_instructions'
const TEXTS: [CardText, string][] = [
  ['mes_example', 'Example messages'], ['scenario', 'Scenario'],
  ['creator_notes', "Creator's notes"], ['system_prompt', 'System prompt'], ['post_history_instructions', 'Instructions after the chat'],
]

const entries = (count: number) => count === 1 ? '1 entry' : `${count} entries`

/** What the card they were imported from had that Dramatis doesn't make: greetings, examples, prompts, tags, a lorebook
 * and other apps' settings, kept as they came ({{char}} and {{user}} included) for the cards they export. No model sees
 * them. Each can be changed here, or left out. */
export function FromTheirCard({ card, onChange }: { card: CardParts | null; onChange: (card: CardParts | null) => void }) {
  // What was just left out, so it can be put back.
  const [left, setLeft] = useState<{ what: string; card: CardParts } | null>(null)
  const undo = left && (
    <p className="row small" role="status">{left.what} left out.
      <button type="button" className="link" onClick={() => { onChange(left.card); setLeft(null) }}><Undo2 size={13} aria-hidden /> Undo</button></p>
  )
  if (!card) return undo ? <div className="fold-undo">{undo}</div> : null
  const set = (change: Partial<CardParts>) => onChange({ ...card, ...change })
  const leave = (what: string, next: CardParts | null) => { setLeft({ what, card }); onChange(next) }
  const greetings = card.alternate_greetings
  const settings = Object.keys(card.extensions)
  return (
    <Fold title="From their card">
      <div className="stack">
        <TextArea label="First message" value={card.first_mes} onChange={(first_mes) => set({ first_mes })} maxLength={LIMIT} rows={4} />
        {greetings.map((text, index) => (
          <TextArea key={index} label={`Greeting ${index + 2}`} value={text} maxLength={LIMIT} rows={3}
            onChange={(value) => set({ alternate_greetings: greetings.map((item, at) => at === index ? value : item) })} />
        ))}
        {TEXTS.map(([key, label]) => (
          <TextArea key={key} label={label} value={card[key]} onChange={(value) => set({ [key]: value })} maxLength={LIMIT} rows={3} />
        ))}
        <ListField label="Tags" add="Add a tag" value={card.tags} onChange={(tags) => set({ tags })} itemLength={100} />
        {card.character_book && (
          <p className="row small">Lorebook, {entries(card.character_book.entries?.length ?? 0)}
            <button type="button" className="link danger" onClick={() => leave('Their lorebook', { ...card, character_book: null })}><Trash2 size={13} aria-hidden /> Leave it out</button></p>
        )}
        {settings.length > 0 && (
          <p className="row small">Settings for other apps: {settings.join(', ')}
            <button type="button" className="link danger" onClick={() => leave('Their settings for other apps', { ...card, extensions: {} })}><Trash2 size={13} aria-hidden /> Leave them out</button></p>
        )}
        {undo}
        <button type="button" className="link danger" onClick={() => leave('Everything from their card', null)}><Trash2 size={13} aria-hidden /> Leave all of it out</button>
      </div>
    </Fold>
  )
}
