import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, MessageSquareText, RotateCcw, TriangleAlert, Undo2, X } from 'lucide-react'
import { useModelReady } from '../Fields'
import { shown, type Edit, type Turn } from './edits'
import { assistant, useAssistant } from './store'

/** Shows a field on the form: opens the folded section it is in, scrolls to it and puts the cursor there. */
export function reveal(field: string) {
  const found = document.querySelector<HTMLElement>(`.editor [data-field="${CSS.escape(field)}"]`)
  if (!found) return
  for (let fold = found.closest('details'); fold; fold = fold.parentElement?.closest('details') ?? null) fold.open = true
  found.scrollIntoView({ block: 'center', behavior: 'smooth' })
  found.querySelector<HTMLElement>('input, textarea, select')?.focus({ preventScroll: true })
}

/** The Sidebar Assistant, after Prospero's Adventure's: a chat beside the character form that sees it as you type
 * and proposes edits you apply one by one, each marked on the form with Undo once applied (dramatis/assistant.py). */
export function Assistant() {
  const chat = useAssistant()
  const ready = useModelReady('assistant')
  const name = chat.form?.get().name || 'them'
  return (
    <aside className="pane assistant" aria-labelledby="assistant-title">
      <header>
        <h2 id="assistant-title"><MessageSquareText size={16} aria-hidden /> Sidebar Assistant</h2>
        {chat.turns.length > 0 && <button type="button" className="icon" aria-label="Start a new conversation" title="Start over" onClick={() => assistant.clear()}><RotateCcw size={15} /></button>}
        <button type="button" className="icon" aria-label="Close the Sidebar Assistant" onClick={() => assistant.setOpen(false)}><X size={16} /></button>
      </header>
      <Transcript turns={chat.turns} busy={chat.busy} name={name} />
      <Composer ready={ready} />
    </aside>
  )
}

function Transcript({ turns, busy, name }: { turns: Turn[]; busy: boolean; name: string }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }) }, [turns.length, busy])
  return (
    <div className="assistant-transcript" ref={box} aria-live="polite">
      {turns.length === 0 && (
        <div className="muted small">
          <p>Ask about {name}, or for a change: &ldquo;does their fear fit their background?&rdquo;, &ldquo;make this shorter&rdquo;, &ldquo;give them a sister they don&rsquo;t talk to&rdquo;.</p>
          <p>It reads the form as you type. You apply each change it proposes, and nothing is kept until you save.</p>
        </div>
      )}
      {turns.map((turn) => (
        <article key={turn.id} className="assistant-turn">
          <p className="assistant-message">{turn.message.length > 600 ? `${turn.message.slice(0, 600)}…` : turn.message}</p>
          <p className="assistant-reply">{turn.reply}</p>
          {turn.edits.map((edit) => <EditCard key={edit.id} edit={edit} hard={turn.audit.filter((hit) => hit.field === edit.field && hit.severity === 'hard').map((hit) => hit.match.trim() || hit.rule)} />)}
          {turn.edits.filter((edit) => edit.status === 'pending').length > 1 && <button type="button" onClick={() => assistant.applyTurn(turn)}>Apply all</button>}
        </article>
      ))}
      {busy && <p className="muted small" role="status">Thinking it over. A local model can take a minute or two.</p>}
    </div>
  )
}

function EditCard({ edit, hard }: { edit: Edit; hard: string[] }) {
  return (
    <section className={`assistant-edit ${edit.status}`} aria-label={edit.label}>
      <div className="row">
        <button type="button" className="link" onClick={() => reveal(edit.field)}>{edit.label}</button>
        {edit.status === 'applied' && <button type="button" onClick={() => assistant.undo(edit.id)}><Undo2 size={13} aria-hidden /> Undo</button>}
        {edit.status === 'pending' && <span className="row">
          <button type="button" className="primary" onClick={() => assistant.apply(edit.id)}>Apply</button>
          <button type="button" className="link" onClick={() => assistant.dismiss(edit.id)}>Dismiss</button>
        </span>}
        {edit.status === 'dismissed' && <span className="muted small">Dismissed</span>}
      </div>
      {hard.length > 0 && <p className="error small"><TriangleAlert size={13} aria-hidden /> Reads as model-written: {hard.join(', ')}</p>}
      <details>
        <summary className="small">Compare</summary>
        <p className="muted small">Before</p><p className="assistant-value">{shown(edit.before)}</p>
        <p className="muted small">After</p><p className="assistant-value">{shown(edit.value)}</p>
      </details>
    </section>
  )
}

function Composer({ ready }: { ready: boolean }) {
  const { busy, error, focus, form } = useAssistant()
  const [message, setMessage] = useState('')
  const send = async (event?: FormEvent) => {
    event?.preventDefault()
    const text = message.trim()
    if (text && await assistant.send(text)) setMessage('')
  }
  const keyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void send() }
  }
  return (
    <form className="assistant-composer" onSubmit={(event) => void send(event)}>
      {focus && form && (
        <p className="assistant-focus small">
          About <button type="button" className="link" onClick={() => reveal(focus.field)}>{focus.label}</button>
          <button type="button" className="icon" aria-label={`Stop pointing it at ${focus.label}`} onClick={() => assistant.setFocus(null)}><X size={13} /></button>
        </p>
      )}
      {error && <p className="error small" role="alert">{error}</p>}
      {!ready && <p className="note small">Set up a model at the top to talk to the assistant.</p>}
      <textarea aria-label="Message to the Sidebar Assistant" placeholder="Ask, or ask for a change" rows={3} maxLength={8000}
        value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={keyDown} />
      <div className="row">
        <span className="muted small">Ctrl+Enter sends</span>
        <button type="submit" className="primary send" aria-label="Send to the Sidebar Assistant" disabled={busy || !ready || !message.trim()}><ArrowUp size={15} /></button>
      </div>
    </form>
  )
}
