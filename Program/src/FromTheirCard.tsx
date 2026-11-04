import { Trash2 } from 'lucide-react'
import { type CardParts } from './api'
import { ListArea, TextArea } from './Fields'

const LIMIT = 40000
type CardText = 'mes_example' | 'scenario' | 'creator_notes' | 'system_prompt' | 'post_history_instructions'
const TEXTS: [CardText, string, string?][] = [
  ['mes_example', 'Example messages'],
  ['scenario', 'Scenario', 'Their cards use How you know each other instead when it has words in it.'],
  ['creator_notes', "Creator's notes"], ['system_prompt', 'System prompt'], ['post_history_instructions', 'Instructions after the chat'],
]

const entries = (count: number) => count === 1 ? '1 entry' : `${count} entries`

/** What the card they were imported from had that Dramatis doesn't make: greetings, examples, prompts, tags, a lorebook
 * and other apps' settings, kept as they came ({{char}} and {{user}} included) for the cards they export. No model sees
 * them. Each can be changed here, or left out. */
export function FromTheirCard({ card, onChange }: { card: CardParts | null; onChange: (card: CardParts | null) => void }) {
  if (!card) return null
  const set = (change: Partial<CardParts>) => onChange({ ...card, ...change })
  const greetings = card.alternate_greetings
  const settings = Object.keys(card.extensions)
  return (
    <details className="section">
      <summary>From their card</summary>
      <div className="stack">
        <TextArea label="First message" value={card.first_mes} onChange={(first_mes) => set({ first_mes })} maxLength={LIMIT} rows={4} />
        {greetings.map((text, index) => (
          <TextArea key={index} label={`Greeting ${index + 2}`} value={text} maxLength={LIMIT} rows={3}
            onChange={(value) => set({ alternate_greetings: greetings.map((item, at) => at === index ? value : item) })} />
        ))}
        {TEXTS.map(([key, label, hint]) => (
          <TextArea key={key} label={label} hint={hint} value={card[key]} onChange={(value) => set({ [key]: value })} maxLength={LIMIT} rows={3} />
        ))}
        <ListArea label="Tags" value={card.tags} onChange={(tags) => set({ tags })} rows={2} />
        {card.character_book && (
          <p className="row small">Lorebook, {entries(card.character_book.entries?.length ?? 0)}
            <button type="button" className="link danger" onClick={() => set({ character_book: null })}><Trash2 size={13} aria-hidden /> Leave it out</button></p>
        )}
        {settings.length > 0 && (
          <p className="row small">Settings for other apps: {settings.join(', ')}
            <button type="button" className="link danger" onClick={() => set({ extensions: {} })}><Trash2 size={13} aria-hidden /> Leave them out</button></p>
        )}
        <button type="button" className="link danger" onClick={() => onChange(null)}><Trash2 size={13} aria-hidden /> Leave all of it out</button>
      </div>
    </details>
  )
}
