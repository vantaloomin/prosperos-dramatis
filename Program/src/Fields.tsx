import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ChevronRight, Square, TriangleAlert, X, Zap } from 'lucide-react'
import { cleaned, sendJson, type AuditHit } from './api'
import { useModelCall } from './modelCall'
import { profileFor, useModels } from './models/ModelSettings'
import { proposals, useProposal, type Proposal } from './proposals'

/** Whether a finished model profile does `job` (its own, or the writing profile): dramatis/profiles.py. */
export function useModelReady(job: 'writing' | 'assistant' | 'cast' = 'writing'): boolean {
  return !!profileFor(useModels().data, job)
}

/** Shows a field on the form: opens the folded section it is in, scrolls to it and puts the cursor there. */
export function reveal(field: string) {
  const found = document.querySelector<HTMLElement>(`.editor [data-field="${CSS.escape(field)}"]`)
  if (!found) return
  for (let fold = found.closest('details'); fold; fold = fold.parentElement?.closest('details') ?? null) fold.open = true
  found.scrollIntoView({ block: 'center', behavior: 'smooth' })
  found.querySelector<HTMLElement>('input, textarea, select')?.focus({ preventScroll: true })
}

/** The one mark for "your model does this", on every model action in the app. */
export const Bolt = ({ size = 14 }: { size?: number }) => <Zap size={size} aria-hidden />

/** A model action's button: the bolt and its name, and Stop while it runs. */
export function ModelButton({ busy, onRun, onStop, children, primary, disabled, busyText }: {
  busy: boolean; onRun: () => void; onStop: () => void; children: ReactNode; primary?: boolean; disabled?: boolean; busyText?: string
}) {
  return busy
    ? <button type="button" onClick={onStop} aria-label={`Stop${busyText ? `: ${busyText}` : ''}`}><Square size={12} aria-hidden /> Stop</button>
    : <button type="button" className={primary ? 'primary' : undefined} disabled={disabled} onClick={onRun}><Bolt /> {children}</button>
}

/** A folded part of the form: a chevron and its name, open from the start when it holds something. */
export function Fold({ title, filled, children, className }: { title: string; filled?: boolean; children: ReactNode; className?: string }) {
  const [open] = useState(!!filled)
  return (
    <details className={`fold${className ? ` ${className}` : ''}`} open={open}>
      <summary><ChevronRight size={16} aria-hidden /> {title}</summary>
      <div className="fold-body">{children}</div>
    </details>
  )
}

const hardOf = (hits: AuditHit[]) => [...new Set(hits.filter((hit) => hit.severity === 'hard').map((hit) => hit.match.trim() || hit.rule))]

/** Keep or Put back, under a field a model proposed something for. Help me write can try again with the same ask. */
function ProposalBar({ proposal, write }: { proposal: Proposal; write?: string }) {
  const call = useModelCall()
  const hard = hardOf(proposal.hits)
  const again = () => {
    const form = proposals.form()
    if (!form) return
    void call.run((signal) => ask(form.get(), proposal.field, proposal.request ?? '', signal), (found) => proposals.propose({
      field: proposal.field, label: proposal.label, value: found.value, source: 'help', hits: found.audit, request: proposal.request,
    }))
  }
  return (
    <div className="proposal-bar" role="group" aria-label={`Proposed ${proposal.label}`}>
      <button type="button" className="primary" onClick={() => proposals.keep(proposal.field)}>Keep</button>
      <button type="button" className="quiet" onClick={() => proposals.putBack(proposal.field)}>Put back</button>
      {proposal.source === 'help' && write && (call.busy
        ? <button type="button" className="quiet" onClick={call.stop}><Square size={11} aria-hidden /> Stop</button>
        : <button type="button" className="quiet" onClick={again}><Bolt size={13} /> Try again</button>)}
      {proposal.reason && <span className="muted small">{proposal.reason}</span>}
      {hard.length > 0 && <span className="error small"><TriangleAlert size={13} aria-hidden /> Reads as model-written: {hard.join(', ')}</span>}
      {call.error && <span className="error small" role="alert">{call.error}</span>}
    </div>
  )
}

const ask = (character: Parameters<typeof cleaned>[0], field: string, request: string, signal: AbortSignal) =>
  sendJson<{ value: unknown; audit: AuditHit[] }>('/api/draft/field', 'POST', { character: cleaned(character), field, request }, signal)

/** Help me write: what should change (optional), then the model's text goes into the field as a proposal. */
function Ask({ field, label, write, onDone }: { field: string; label: string; write: string; onDone: () => void }) {
  const call = useModelCall()
  const [request, setRequest] = useState('')
  const go = () => {
    const form = proposals.form()
    if (!form || call.busy) return
    void call.run((signal) => ask(form.get(), field, request, signal), (found) => {
      proposals.propose({ field, label, value: found.value, source: 'help', hits: found.audit, request })
      onDone()
    }, 'That could not be written.')
  }
  return (
    <div className="help-ask">
      <input autoFocus aria-label={`What should change about ${write}`} placeholder="What should change? (optional)" value={request} maxLength={500}
        onChange={(event) => setRequest(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') { event.preventDefault(); go() }
          if (event.key === 'Escape') { event.preventDefault(); onDone() }
        }} />
      {call.busy
        ? <button type="button" onClick={call.stop}><Square size={11} aria-hidden /> Stop</button>
        : <button type="button" className="primary" onClick={go}>Write</button>}
      <button type="button" className="icon" aria-label="Close" onClick={() => { call.stop(); onDone() }}><X size={15} /></button>
      {call.error && <p className="error small" role="alert">{call.error}</p>}
    </div>
  )
}

/** `name` is the field's key in the character (dotted for their depth, as Help me write and the Sidebar Assistant use
 * it): the assistant knows which field the user is in by it, and proposals stand in the field it names. `write` gives
 * the field its Help me write bolt ("Help me write <write>"), inside the box while it is empty (`filled` false) and
 * beside the label once it has something. `group` labels a set of controls rather than one. */
interface FieldProps { label: string; name?: string; write?: string; filled?: boolean; group?: boolean; children: (id: string) => ReactNode }

export function Field({ label, name, write, filled = true, group, children }: FieldProps) {
  const id = useId()
  const proposal = useProposal(name)
  const ready = useModelReady()
  const [asking, setAsking] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  // A proposal in a folded section (Inner life, Secret) opens it, so the change is never out of sight.
  useEffect(() => {
    for (let fold = proposal ? box.current?.closest('details') : null; fold; fold = fold.parentElement?.closest('details') ?? null) fold.open = true
  }, [proposal])
  const bolt = !!(write && name && ready)
  const button = bolt && (
    <button type="button" className="bolt" aria-label={`Help me write ${write}`} aria-expanded={asking} title="Help me write"
      onClick={() => setAsking(!asking)}><Bolt size={16} /></button>
  )
  return (
    <div className={proposal ? 'field proposed' : 'field'} data-field={name} ref={box}>
      <div className="field-top">
        {group ? <span className="label" id={`${id}-label`}>{label}</span> : <label htmlFor={id}>{label}</label>}
        {filled && button}
      </div>
      <div className={bolt && !filled ? 'field-box has-bolt' : 'field-box'}>
        {children(id)}
        {!filled && button}
      </div>
      {asking && name && write && <Ask field={name} label={label} write={write} onDone={() => setAsking(false)} />}
      {proposal && <ProposalBar proposal={proposal} write={write} />}
    </div>
  )
}

interface TextProps { label: string; value: string; onChange: (value: string) => void; maxLength: number; placeholder?: string; name?: string; write?: string }

export function TextInput({ label, value, onChange, maxLength, placeholder, name, write }: TextProps) {
  return <Field label={label} name={name} write={write} filled={!!value.trim()}>{(id) => (
    <input id={id} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
  )}</Field>
}

export function TextArea({ label, value, onChange, maxLength, placeholder, name, write, rows = 3 }: TextProps & { rows?: number }) {
  return <Field label={label} name={name} write={write} filled={!!value.trim()}>{(id) => (
    <textarea id={id} value={value} maxLength={maxLength} rows={rows} style={{ '--rows': rows } as CSSProperties} placeholder={placeholder}
      onChange={(event) => onChange(event.target.value)} />
  )}</Field>
}

/** A list item is one line however it is typed or pasted. */
const oneLine = (text: string) => text.replace(/\s*\n\s*/g, ' ')

/** A list, one row per item, each wrapping when it is long: Enter in the last box adds one, each has a remove button,
 * and an emptied row goes when the form is saved (`cleanList`). */
export function ListField({ label, value, onChange, add, name, write, itemLength = 120 }: {
  label: string; value: string[]; onChange: (value: string[]) => void; add: string; name?: string; write?: string; itemLength?: number
}) {
  const [draft, setDraft] = useState('')
  const adder = useRef<HTMLTextAreaElement>(null)
  const put = () => {
    const text = draft.trim()
    if (text) onChange([...value.filter((item) => item.trim()), text])
    setDraft('')
  }
  const items = value
  return <Field label={label} name={name} write={write} filled={items.some((item) => item.trim())} group>{(id) => (
    <div className="list" role="group" aria-labelledby={`${id}-label`}>
      {items.map((item, index) => (
        <div key={index} className="item">
          <textarea rows={1} aria-label={`${label}, ${index + 1}`} value={item} maxLength={itemLength}
            onChange={(event) => onChange(items.map((each, at) => at === index ? oneLine(event.target.value) : each))}
            onKeyDown={(event) => {
              if (event.key === 'Enter') { event.preventDefault(); adder.current?.focus() }
              if (event.key === 'Backspace' && !item) { event.preventDefault(); onChange(items.filter((_, at) => at !== index)); adder.current?.focus() }
            }} />
          <button type="button" className="icon" aria-label={`Remove ${item.trim() || 'this one'}`} onClick={() => onChange(items.filter((_, at) => at !== index))}><X size={14} /></button>
        </div>
      ))}
      <textarea ref={adder} rows={1} id={id} className="add" aria-label={add} placeholder={add} value={draft} maxLength={itemLength}
        onChange={(event) => setDraft(oneLine(event.target.value))} onBlur={put}
        onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); put() } }} />
    </div>
  )}</Field>
}
