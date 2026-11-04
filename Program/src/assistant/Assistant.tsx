import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, MessageSquareText, RotateCcw, Square, TriangleAlert, X } from 'lucide-react'
import { cleaned } from '../api'
import { reveal, useModelReady } from '../Fields'
import { proposals, useOutcomes, type Outcome } from '../proposals'
import { shown, type Edit, type Turn } from './edits'
import { assistant, useAssistant } from './store'

/** The Sidebar Assistant, after Prospero's Adventure's: a chat beside the character form that sees it as you type.
 * The changes it proposes go straight into their fields as proposals, kept or put back there or here
 * (dramatis/assistant.py, src/proposals.ts). */
export function Assistant() {
  const chat = useAssistant()
  const ready = useModelReady('assistant')
  const name = proposals.form()?.get().name || 'them'
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
  const outcomes = useOutcomes()
  useEffect(() => { box.current?.scrollTo({ top: box.current.scrollHeight }) }, [turns.length, busy])
  return (
    <div className="assistant-transcript" ref={box} aria-live="polite">
      {turns.length === 0 && (
        <div className="muted small">
          <p>Ask about {name}, or for a change: &ldquo;does their fear fit their background?&rdquo;, &ldquo;make this shorter&rdquo;, &ldquo;give them a sister they don&rsquo;t talk to&rdquo;.</p>
          <p>It reads the form as you type. A change it proposes shows in its field, for you to keep or put back.</p>
        </div>
      )}
      {turns.map((turn) => (
        <article key={turn.id} className="assistant-turn">
          <p className="assistant-message">{turn.message.length > 600 ? `${turn.message.slice(0, 600)}…` : turn.message}</p>
          <p className="assistant-reply">{turn.reply}</p>
          {turn.edits.map((edit) => <EditCard key={edit.id} edit={edit} outcome={outcomes[edit.id] ?? 'proposed'} hard={turn.audit.filter((hit) => hit.field === edit.field && hit.severity === 'hard').map((hit) => hit.match.trim() || hit.rule)} />)}
          {turn.edits.filter((edit) => outcomes[edit.id] === 'proposed').length > 1 && (
            <div className="row">
              <button type="button" className="primary" onClick={() => proposals.keepAll(turn.edits.map((edit) => edit.id))}>Keep all</button>
              <button type="button" className="quiet" onClick={() => proposals.putBackAll(turn.edits.map((edit) => edit.id))}>Put all back</button>
            </div>
          )}
        </article>
      ))}
      {busy && <p className="muted small" role="status">Thinking it over…</p>}
    </div>
  )
}

const SAID: Record<Outcome, string> = { proposed: 'On the form', kept: 'Kept', 'put back': 'Put back', replaced: 'Replaced by a later one' }

function EditCard({ edit, outcome, hard }: { edit: Edit; outcome: Outcome; hard: string[] }) {
  return (
    <section className={`assistant-edit ${outcome === 'proposed' ? 'pending' : outcome === 'kept' ? 'applied' : 'dismissed'}`} aria-label={edit.label}>
      <div className="row">
        <button type="button" className="link" onClick={() => reveal(edit.field)}>{edit.label}</button>
        {outcome === 'proposed' ? <span className="row">
          <button type="button" className="primary" onClick={() => proposals.keep(edit.field)}>Keep</button>
          <button type="button" className="quiet" onClick={() => proposals.putBack(edit.field)}>Put back</button>
        </span> : <span className="muted small">{SAID[outcome]}</span>}
      </div>
      {hard.length > 0 && <p className="error small"><TriangleAlert size={13} aria-hidden /> Reads as model-written: {hard.join(', ')}</p>}
      <details>
        <summary className="small">Compare</summary>
        <p className="muted small">Before</p><p className="assistant-value">{shown(edit.before)}</p>
        <p className="muted small">Proposed</p><p className="assistant-value">{shown(edit.value)}</p>
      </details>
    </section>
  )
}

function Composer({ ready }: { ready: boolean }) {
  const { busy, error, focus } = useAssistant()
  const form = proposals.form()
  const [message, setMessage] = useState('')
  const send = async (event?: FormEvent) => {
    event?.preventDefault()
    const text = message.trim()
    if (text && await assistant.send(text, cleaned)) setMessage('')
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
        {busy
          ? <button type="button" className="send" aria-label="Stop" onClick={() => assistant.stop()}><Square size={13} /></button>
          : <button type="submit" className="primary send" aria-label="Send to the Sidebar Assistant" disabled={!ready || !message.trim()}><ArrowUp size={15} /></button>}
      </div>
    </form>
  )
}
