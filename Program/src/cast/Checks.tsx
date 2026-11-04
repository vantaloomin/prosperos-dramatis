import { CheckCircle2, Info, TriangleAlert } from 'lucide-react'
import type { Cast, CastCheck } from '../castApi'
import { ChecksActions } from './slots'

/** What the server's checks make of the board as it stands, live before Save. Every one is a warning with a fix; none
 * stops a save. Picking one lights the corners it names. */
export function Checks({ cast, checks, error, lit, onLight, update }: {
  cast: Cast; checks: CastCheck[] | null; error: string; lit: CastCheck | null; onLight: (check: CastCheck | null) => void
  update: (change: (cast: Cast) => Cast) => void
}) {
  const warnings = (checks ?? []).filter((check) => check.severity === 'warn')
  const reminders = (checks ?? []).filter((check) => check.severity !== 'warn')
  const item = (check: CastCheck, index: number) => (
    <li key={`${check.code}-${index}`}>
      <button type="button" aria-pressed={lit === check} disabled={!check.corners.length} onClick={() => onLight(lit === check ? null : check)}>
        {check.severity === 'warn' ? <TriangleAlert size={14} aria-hidden /> : <Info size={14} aria-hidden />}
        <span><span>{check.message}</span> <span className="muted">{check.fix}</span></span>
      </button>
    </li>
  )
  return (
    <section className="checks" aria-label="Checks" aria-live="polite">
      {error ? <p className="error small" role="alert"><TriangleAlert size={14} aria-hidden /> {error}</p>
        : checks && !warnings.length ? <p className="ok small"><CheckCircle2 size={14} aria-hidden /> Nothing to warn about</p> : null}
      {warnings.length > 0 && <ul>{warnings.map(item)}</ul>}
      {reminders.length > 0 && (
        <details className="small">
          <summary>Reminders ({reminders.length})</summary>
          <ul>{reminders.map(item)}</ul>
        </details>
      )}
      <ChecksActions cast={cast} update={update} lit={lit} onLight={onLight} />
    </section>
  )
}
