// The few pieces of Prospero's Companion's screen that its Settings > Models form is built from (components/Fields,
// Rows, Feedback, InfoTip, numberBounds, returnFocus, paths and api at c641bca), so the files beside this one stay
// as close to Companion's as they can.
import { createContext, useContext, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { AlertCircle, ChevronDown, CircleHelp, Info } from 'lucide-react'

/** Companion's `api`: a GET, or a POST when there is a body, under /api. Errors carry the server's own message. */
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(data?.detail) ? data.detail.map((item: { msg?: string }) => item.msg?.replace(/^Value error, /, '')).filter(Boolean).join(' ') : data?.detail
    throw new Error(data?.error ?? (detail || `The server answered ${response.status}.`))
  }
  return data as T
}

/** A path as shown on screen, with the user's home folder written as ~ so screenshots don't carry their name. */
export function shownPath(path: string): string {
  return path.replace(/^(?:[A-Za-z]:)?([\\/])(?:Users|home)\1[^\\/]+(?=[\\/]|$)/i, '~')
}

/** Keeps a typed number inside its range; while typing only the top is enforced, leaving enforces the bottom too. */
export function bounded(value: string, min?: number, max?: number, leaving = false): string {
  const number = Number(value)
  if (value.trim() === '' || !Number.isFinite(number)) return value
  if (max !== undefined && number > max) return String(max)
  if (leaving && min !== undefined && number < min) return String(min)
  return value
}

/** Focus goes back to the button that opened something once it closes. */
export function useReturnFocus<T extends HTMLElement>(open: boolean) {
  const opener = useRef<T>(null)
  const wasOpen = useRef(open)
  useEffect(() => {
    if (wasOpen.current && !open && document.activeElement === document.body) opener.current?.focus()
    wasOpen.current = open
  }, [open])
  return opener
}

/** A "?" beside a label: the text stays in the page for screen readers and shows on hover, focus or a click. */
export function InfoTip({ id, label, text }: { id: string; label: string; text: string }) {
  const [open, setOpen] = useState(false)
  return <span className="info-tip" onPointerEnter={(event) => { if (event.pointerType === 'mouse') setOpen(true) }} onPointerLeave={(event) => { if (event.pointerType === 'mouse') setOpen(false) }}>
    <button type="button" className="info-tip-button" aria-label={`More about ${label}`} aria-describedby={id} aria-expanded={open}
      onClick={() => setOpen(!open)} onBlur={() => setOpen(false)} onKeyDown={(event) => { if (event.key === 'Escape') setOpen(false) }}><CircleHelp size={14} aria-hidden /></button>
    <span id={id} role="tooltip" className="info-tip-text" hidden={!open}>{text}</span>
  </span>
}

interface Help { hint?: ReactNode; tip?: string }
const joinIds = (...ids: (string | false | undefined)[]) => ids.filter(Boolean).join(' ') || undefined

/** A labelled control with an optional hint under it and a tip behind a "?" by its label, both read out with it. */
export function Field({ label, hint, tip, children }: Help & { label: string; children: (id: string, describedBy?: string) => ReactNode }) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const tipId = tip ? `${id}-tip` : undefined
  return <div className="field">
    <span className="label-row"><label htmlFor={id}>{label}</label>{tip && tipId && <InfoTip id={tipId} label={label} text={tip} />}</span>
    {children(id, joinIds(hintId, tipId))}
    {hint && <small id={hintId} className="hint">{hint}</small>}
  </div>
}

interface TextInputProps extends Help { label: string; value: string; onChange: (value: string) => void; maxLength?: number; type?: string; placeholder?: string; min?: number; max?: number }

export function TextInput({ label, hint, tip, value, onChange, maxLength, type = 'text', placeholder, min, max }: TextInputProps) {
  const leave = () => { const fixed = bounded(value, min, max, true); if (fixed !== value) onChange(fixed) }
  return <Field label={label} hint={hint} tip={tip}>{(id, describedBy) => <input id={id} type={type} value={value} maxLength={maxLength} placeholder={placeholder}
    autoComplete={type === 'password' ? undefined : 'off'} min={min} max={max} aria-describedby={describedBy} onChange={(event) => onChange(bounded(event.target.value, min, max))} onBlur={leave} />}</Field>
}

/** Errors are announced assertively; other notices politely. */
export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error'; children: ReactNode }) {
  const Icon = tone === 'error' ? AlertCircle : Info
  return <div className={`notice notice-${tone}`} role={tone === 'error' ? 'alert' : 'status'}><Icon size={16} aria-hidden /><span>{children}</span></div>
}

/** Rows in one bordered list. */
export function RowGroup({ children }: { children: ReactNode }) {
  return <section className="row-group"><div className="row-list">{children}</div></section>
}

const ParentOff = createContext(false)

/** One setting: its label on the left, its control on the right. */
export function SettingRow({ label, tip, children }: { label: string; tip?: string; children: (id: string, disabled: boolean) => ReactNode }) {
  const id = useId()
  const disabled = useContext(ParentOff)
  return <div className={disabled ? 'setting-row disabled' : 'setting-row'}>
    <span className="setting-row-label"><label htmlFor={id}>{label}</label>{tip && <InfoTip id={`${id}-tip`} label={label} text={tip} />}</span>
    {children(id, disabled)}
  </div>
}

export function SwitchRow({ label, tip, checked, onChange }: { label: string; tip?: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return <SettingRow label={label} tip={tip}>{(id, disabled) => <button id={id} type="button" role="switch" className="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)} />}</SettingRow>
}

/** A summary line that opens to its detail. Closed until asked, unless `open` says otherwise. */
export function FoldRow({ summary, value, open, onToggle, nested, children }: { summary: ReactNode; value?: ReactNode; open?: boolean; onToggle?: (open: boolean) => void; nested?: boolean; children: ReactNode }) {
  const id = useId()
  const [own, setOwn] = useState(false)
  const shown = open ?? own
  const toggle = () => { setOwn(!shown); onToggle?.(!shown) }
  return <div className={['fold-row', shown && 'open', nested && 'nested'].filter(Boolean).join(' ')}>
    <button type="button" className="fold-summary" aria-expanded={shown} aria-controls={id} onClick={toggle}>
      <span className="fold-text">{summary}</span>
      {value && <span className="row-value">{value}</span>}
      <ChevronDown size={16} className="fold-chevron" aria-hidden />
    </button>
    <div id={id} className="fold-body" hidden={!shown}>{children}</div>
  </div>
}
