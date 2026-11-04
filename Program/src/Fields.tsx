import { useId, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sparkles, Undo2 } from 'lucide-react'
import { getJson, sendJson, type Character, type ModelConfig } from './api'

/** Whether a model is set up to draft: Claude through the API needs a key; a local server or the CLI may not. */
export function useModelReady(): boolean {
  const models = useQuery({ queryKey: ['models'], queryFn: () => getJson<ModelConfig>('/api/models') })
  return !!models.data && (models.data.provider !== 'anthropic' || models.data.has_key)
}

interface FieldProps { label: string; hint?: string; children: (id: string) => ReactNode; help?: ReactNode }

export function Field({ label, hint, children, help }: FieldProps) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <span className="hint">{hint}</span>}
      {help}
    </div>
  )
}

interface TextProps { label: string; value: string; onChange: (value: string) => void; maxLength: number; hint?: string; placeholder?: string; help?: ReactNode }

export function TextInput({ label, value, onChange, maxLength, hint, placeholder, help }: TextProps) {
  return <Field label={label} hint={hint} help={help}>{(id) => (
    <input id={id} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
  )}</Field>
}

export function TextArea({ label, value, onChange, maxLength, hint, placeholder, help, rows = 3 }: TextProps & { rows?: number }) {
  return <Field label={label} hint={hint} help={help}>{(id) => (
    <textarea id={id} value={value} maxLength={maxLength} rows={rows} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
  )}</Field>
}

/** A list edited one item per line; blank lines are dropped when the form is saved (`cleanList`). */
export function ListArea({ label, value, onChange, hint, help, rows = 4 }: { label: string; value: string[]; onChange: (value: string[]) => void; hint?: string; help?: ReactNode; rows?: number }) {
  return <Field label={label} hint={hint ?? 'One per line.'} help={help}>{(id) => (
    <textarea id={id} value={value.join('\n')} rows={rows} onChange={(event) => onChange(event.target.value.split('\n'))} />
  )}</Field>
}

export const cleanList = (items: string[]) => [...new Set(items.map((item) => item.trim()).filter(Boolean))]

/** Help me write: the model rewrites one field to fit the rest of the character, and the old text can be put back. */
export function HelpMeWrite<T>({ field, label, character, current, apply }: { field: string; label: string; character: () => Character; current: T; apply: (value: T) => void }) {
  const [open, setOpen] = useState(false)
  const [ask, setAsk] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [before, setBefore] = useState<{ value: T } | null>(null)
  const write = async () => {
    setBusy(true)
    setError('')
    try {
      const found = await sendJson<{ value: T }>('/api/draft/field', 'POST', { character: character(), field, request: ask })
      setBefore({ value: current })
      apply(found.value)
      setOpen(false)
      setAsk('')
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That could not be written.')
    } finally { setBusy(false) }
  }
  return (
    <div className="help">
      {!open && <button type="button" className="link" onClick={() => setOpen(true)}><Sparkles size={13} aria-hidden /> Help me write {label}</button>}
      {before && !open && <button type="button" className="link" onClick={() => { apply(before.value); setBefore(null) }}><Undo2 size={13} aria-hidden /> Put back what was there</button>}
      {open && (
        <div className="help-ask">
          <input aria-label={`What should change about ${label}`} placeholder="What should change? (optional)" value={ask} maxLength={500}
            onChange={(event) => setAsk(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void write() } }} />
          <button type="button" disabled={busy} onClick={() => void write()}>{busy ? 'Writing…' : 'Write it'}</button>
          <button type="button" onClick={() => setOpen(false)}>Cancel</button>
        </div>
      )}
      {error && <p className="error small" role="alert">{error}</p>}
    </div>
  )
}
