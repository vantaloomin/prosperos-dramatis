/** The AI-slop audit on screen (dramatis/slop.py): hard hits (stock names, dashes, the assistant's voice) to fix, and
 * flags worth a look. Nothing here stops a save: a name the user chose is theirs.
 *
 * `Audit` lists them. `FormAudit` is the character form's: each hit has a box, and Fix selected / Fix all send the
 * hits to POST /api/draft/fix (dramatis/fixes.py), which rewrites only those words; each changed field comes back as a
 * proposal in it (src/proposals.ts). Ignore keeps the words on this character (`ignored_flags`, saved with them), and
 * the audit leaves them out from then on; Ignored lists them to take back. */
import { useEffect, useState, type ReactNode } from 'react'
import { TriangleAlert, X } from 'lucide-react'
import { cleaned, sendJson, type AuditHit } from './api'
import { ModelButton, useModelReady } from './Fields'
import { useModelCall } from './modelCall'
import { proposals } from './proposals'

interface FixedField { field: string; label: string; value: unknown; audit: AuditHit[] }

const keyOf = (hit: AuditHit) => [hit.field, hit.rule, hit.match, hit.context].join('\u0000')
const words = (hit: AuditHit) => hit.match.trim() || hit.match
const HARD_NOTE = "Stock names, dashes and the assistant's voice. Change them unless you chose them."
const FLAG_NOTE = 'Words and phrases models lean on. One means little; keep them where they fit.'

function Line({ hit }: { hit: AuditHit }) {
  return <><strong>{hit.label}:</strong> “{words(hit)}” <span className="muted">({hit.rule}) …{hit.context}…</span></>
}

function Group({ summary, note, open, error, children }: { summary: ReactNode; note: string; open?: boolean; error?: boolean; children: ReactNode }) {
  return <details open={open} className={error ? 'error small' : 'small'}><summary>{summary}</summary><p className="muted">{note}</p>{children}</details>
}

const hardSummary = (count: number) => <><TriangleAlert size={14} aria-hidden /> {count} {count === 1 ? 'thing reads' : 'things read'} as model-written</>

/** The audit's hits, to read: the cast board's suggestions use it. */
export function Audit({ hits }: { hits: AuditHit[] }) {
  if (!hits.length) return null
  const hard = hits.filter((hit) => hit.severity === 'hard')
  const flags = hits.filter((hit) => hit.severity === 'flag')
  const list = (found: AuditHit[]) => <ul>{found.map((hit, index) => <li key={index}><Line hit={hit} /></li>)}</ul>
  return (
    <div className="audit">
      {hard.length > 0 && <Group open error summary={hardSummary(hard.length)} note={HARD_NOTE}>{list(hard)}</Group>}
      {flags.length > 0 && <Group summary={`Worth a look (${flags.length})`} note={FLAG_NOTE}>{list(flags)}</Group>}
    </div>
  )
}

/** One kind of hit with its boxes and actions. */
function Pickable({ hits, picked, onPick, onFix, onStop, onIgnore, busy, ready }: {
  hits: AuditHit[]; picked: Set<string>; onPick: (key: string, on: boolean) => void
  onFix: (hits: AuditHit[]) => void; onStop: () => void; onIgnore: (hits: AuditHit[]) => void; busy: boolean; ready: boolean
}) {
  const chosen = hits.filter((hit) => picked.has(keyOf(hit)))
  return <>
    <ul className="picks">
      {hits.map((hit, index) => (
        <li key={index}><label><input type="checkbox" checked={picked.has(keyOf(hit))} onChange={(event) => onPick(keyOf(hit), event.target.checked)} /> <span><Line hit={hit} /></span></label></li>
      ))}
    </ul>
    <div className="row">
      {ready && (busy
        ? <ModelButton busy onRun={() => undefined} onStop={onStop} busyText="fixing">Fix</ModelButton>
        : <>
          <ModelButton busy={false} disabled={!chosen.length} onRun={() => onFix(chosen)} onStop={onStop}>Fix selected</ModelButton>
          <ModelButton busy={false} onRun={() => onFix(hits)} onStop={onStop}>Fix all</ModelButton>
        </>)}
      <button type="button" className="quiet" disabled={!chosen.length} onClick={() => onIgnore(chosen)}>Ignore</button>
    </div>
  </>
}

/** The character form's audit: pick hits, then fix them with the model or keep them on this character. */
export function FormAudit({ hits, ignored, allowed, onIgnored }: {
  hits: AuditHit[]; ignored: string[]; allowed: string; onIgnored: (ignored: string[]) => void
}) {
  const call = useModelCall()
  const ready = useModelReady()
  const [picked, setPicked] = useState<Set<string>>(new Set())
  // A box stays ticked only while its hit is still on the form.
  useEffect(() => {
    const now = new Set(hits.map(keyOf))
    setPicked((current) => [...current].every((key) => now.has(key)) ? current : new Set([...current].filter((key) => now.has(key))))
  }, [hits])
  if (!hits.length && !ignored.length) return null
  const hard = hits.filter((hit) => hit.severity === 'hard')
  const flags = hits.filter((hit) => hit.severity === 'flag')
  const pick = (key: string, on: boolean) => setPicked((current) => {
    const next = new Set(current)
    if (on) next.add(key); else next.delete(key)
    return next
  })
  const fix = (chosen: AuditHit[]) => {
    const form = proposals.form()
    if (!chosen.length || !form) return
    void call.run((signal) => sendJson<{ fields: FixedField[] }>('/api/draft/fix', 'POST', { character: cleaned(form.get()), hits: chosen, allowed }, signal), (found) => {
      for (const item of found.fields) proposals.propose({ field: item.field, label: item.label, value: item.value, source: 'fix', hits: item.audit })
      setPicked(new Set())
    }, 'Those could not be fixed.')
  }
  const ignore = (chosen: AuditHit[]) => {
    onIgnored([...new Set([...ignored, ...chosen.map(words)])])
    setPicked(new Set())
  }
  const shared = { picked, onPick: pick, onFix: fix, onStop: call.stop, onIgnore: ignore, busy: call.busy, ready }
  return (
    <div className="audit">
      {hard.length > 0 && <Group open error summary={hardSummary(hard.length)} note={HARD_NOTE}><Pickable hits={hard} {...shared} /></Group>}
      {flags.length > 0 && <Group summary={`Worth a look (${flags.length})`} note={FLAG_NOTE}><Pickable hits={flags} {...shared} /></Group>}
      {call.error && <p className="error small" role="alert">{call.error}</p>}
      {ignored.length > 0 && <details className="small"><summary>Ignored ({ignored.length})</summary>
        <div className="row">{ignored.map((item) => (
          <button key={item} type="button" className="chip" aria-label={`Stop ignoring ${item}`} onClick={() => onIgnored(ignored.filter((other) => other !== item))}>{item} <X size={11} aria-hidden /></button>
        ))}</div>
      </details>}
    </div>
  )
}
