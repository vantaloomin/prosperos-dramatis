/** AI help on the Cast board: Suggest corners, Check my square, Find the turn and Suggest a relationship. Each sends the
 * board as it stands to the user's model (dramatis/cast_ai.py) and shows what comes back as proposals. Apply changes the
 * board, Undo puts it back and Dismiss drops the proposal; only Save writes the cast. What the model wrote comes with
 * the AI-slop audit's hits, shown the way the character form shows them. */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Info, RefreshCw, Sparkles, TriangleAlert, Undo2, X } from 'lucide-react'
import type { AuditHit } from '../api'
import { Audit } from '../Editor'
import { openModelSettings } from '../ModelSettings'
import {
  aiCalls, editRelationship, findCorner, placeProposal, proposedOf, setLinkNote, targetSquare, unplaceProposal, words,
  type Cast, type CastCheck, type CornerProposal, type Proposed, type RelationshipProposal, type Resonance, type SuggestTarget, type TagInfo,
} from '../castApi'

type Update = (change: (cast: Cast) => Cast) => void

/** One call to the model at a time: whether it is out, and the error it came back with. */
function useAsk() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async <T,>(call: () => Promise<T>, done: (found: T) => void) => {
    setBusy(true)
    setError('')
    try { done(await call()) } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Your model could not be asked.')
    } finally { setBusy(false) }
  }
  return { busy, error, run }
}

const hitsAt = (hits: AuditHit[], prefix: string) => hits.filter((hit) => hit.field === prefix || hit.field.startsWith(`${prefix}.`))

/** Where the AI buttons would be, when no model is set up: one link to the model settings. */
export function SetUpModel() {
  return <button type="button" className="link" onClick={openModelSettings}><Sparkles size={13} aria-hidden /> Set up a text model</button>
}

/** The panel a button opens under itself, closed again by its X or Escape. */
function Panel({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => { panel.current?.focus() }, [])
  return (
    <div className="ai-panel card" role="dialog" aria-label={label} tabIndex={-1} ref={panel}
      onKeyDown={(event) => { if (event.key === 'Escape') { event.stopPropagation(); onClose() } }}>
      <div className="row">
        <strong className="grow">{label}</strong>
        <button type="button" className="icon" aria-label="Close" onClick={onClose}><X size={15} /></button>
      </div>
      {children}
    </div>
  )
}

// ---- Suggest corners ----------------------------------------------------------------------------------------------

interface Offered { proposal: CornerProposal; hits: AuditHit[]; applied?: { id: string; before: Proposed | null } }

/** Suggest corners for the outer square (in the board header) or for one side's inner square (in its card). */
export function SuggestCorners({ cast, update, target, tags, compact }: { cast: Cast; update: Update; target: SuggestTarget; tags: TagInfo[]; compact?: boolean }) {
  const ask = useAsk()
  const [open, setOpen] = useState(false)
  const [offered, setOffered] = useState<Offered[]>([])
  const side = target === 'outer' ? null : findCorner(cast, target)?.corner
  const square = targetSquare(cast, target)
  const name = side ? side.label || 'this side' : 'the outer square'
  const fetch = () => void ask.run(() => aiCalls.suggest(cast, target), (found) => setOffered(found.proposals.map((proposal, index) => ({
    proposal, hits: hitsAt(found.audit, `proposals.${index}`),
  }))))
  const toggle = () => { setOpen(!open); if (!open && !offered.length) fetch() }
  const apply = (index: number, into: string | null) => {
    const { proposal } = offered[index]
    const placed = placeProposal(cast, target, proposal, into)
    if (!placed) return
    const before = into ? findCorner(cast, into)?.corner : undefined
    setOffered((items) => items.map((item, at) => at === index ? { ...item, applied: { id: placed.id, before: before ? proposedOf(before) : null } } : item))
    update((current) => placeProposal(current, target, proposal, into)?.cast ?? current)
  }
  const undo = (index: number) => {
    const { applied } = offered[index]
    if (!applied) return
    update((current) => unplaceProposal(current, applied.id, applied.before))
    setOffered((items) => items.map((item, at) => at === index ? { ...item, applied: undefined } : item))
  }
  if (!square) return null
  const tagName = (tag: string) => tags.find((item) => item.id === tag)?.label ?? tag
  const cornerName = (id: string) => findCorner(cast, id)?.corner.label || 'the unnamed corner'
  return (
    <div className="ai-pop">
      {compact
        ? <button type="button" className="icon" aria-expanded={open} aria-label={`Suggest corners for ${name}`} title="Suggest corners" onClick={toggle}><Sparkles size={14} /></button>
        : <button type="button" aria-expanded={open} onClick={toggle}><Sparkles size={14} aria-hidden /> Suggest corners</button>}
      {open && <Panel label={`Suggestions for ${name}`} onClose={() => setOpen(false)}>
      {ask.busy && <p className="muted small" role="status">Asking your model…</p>}
      {ask.error && <p className="error small" role="alert">{ask.error}</p>}
      <ul className="proposals">
        {offered.map((item, index) => {
          const { proposal, applied } = item
          const into = proposal.corner_id && square.corners.some((corner) => corner.id === proposal.corner_id) ? proposal.corner_id : null
          const full = square.corners.length >= 4
          return (
            <li key={index} className="proposal">
              <strong>{proposal.label}</strong>
              <span>{proposal.stance}</span>
              {(proposal.tags.length > 0 || proposal.role) && (
                <span className="tags">
                  {proposal.role && <span className="muted small">{words(proposal.role)}</span>}
                  {proposal.tags.map((tag) => <span key={tag} className="tag">{tagName(tag)}</span>)}
                </span>
              )}
              {Object.entries(proposal.fields ?? {}).filter(([, text]) => text).map(([key, text]) => (
                <span key={key} className="small"><span className="muted">{words(key)}:</span> {text}</span>
              ))}
              <Audit hits={item.hits} />
              <div className="row">
                {applied ? <>
                  <span className="ok small"><Check size={14} aria-hidden /> In {cornerName(applied.id)}</span>
                  <button type="button" className="link" onClick={() => undo(index)}><Undo2 size={13} aria-hidden /> Undo</button>
                </> : <>
                  {into || !full
                    ? <button type="button" className="primary" onClick={() => apply(index, into)}>{into ? `Apply to ${cornerName(into)}` : 'Apply as a new corner'}</button>
                    : (
                      <select aria-label={`Put ${proposal.label} in place of`} value="" onChange={(event) => event.target.value && apply(index, event.target.value)}>
                        <option value="">Apply in place of…</option>
                        {square.corners.map((corner) => <option key={corner.id} value={corner.id}>{corner.label || 'Unnamed corner'}</option>)}
                      </select>
                    )}
                  <button type="button" onClick={() => setOffered((items) => items.filter((_, at) => at !== index))}>Dismiss</button>
                </>}
              </div>
            </li>
          )
        })}
      </ul>
      {!ask.busy && (offered.length > 0 || ask.error) && (
        <button type="button" className="link" onClick={fetch}><RefreshCw size={13} aria-hidden /> {offered.length ? 'Suggest others' : 'Try again'}</button>
      )}
      </Panel>}
    </div>
  )
}

// ---- Check my square ----------------------------------------------------------------------------------------------

/** Check my square: where a stance reads as the wrong kind, and the four-corner web's judgement calls, as soft
 * warnings beside the computed checks. Picking one lights its corner, as the computed ones do. */
export function CheckSquare({ cast, lit, onLight }: { cast: Cast; lit: CastCheck | null; onLight: (check: CastCheck | null) => void }) {
  const ask = useAsk()
  const [found, setFound] = useState<{ checks: CastCheck[]; hits: AuditHit[]; held: number; asked: string } | null>(null)
  const now = JSON.stringify(cast)
  const check = () => void ask.run(() => aiCalls.check(cast), (answer) => {
    const checks: CastCheck[] = [
      ...answer.flags.map((flag) => ({ code: `reads-as-${flag.reads_as}`, severity: 'warn' as const, corners: [flag.corner_id], message: flag.message, fix: '' })),
      ...answer.judgements.filter((item) => !item.holds).map((item) => ({ code: item.code, severity: 'info' as const, corners: [item.corner_id], message: item.message, fix: '' })),
    ]
    setFound({ checks, hits: answer.audit, held: answer.judgements.filter((item) => item.holds).length, asked: now })
    if (lit && !checks.includes(lit) && lit.code.startsWith('reads-as-')) onLight(null)
  })
  const dismiss = (check: CastCheck) => {
    if (lit === check) onLight(null)
    setFound((current) => current && { ...current, checks: current.checks.filter((item) => item !== check) })
  }
  return (
    <div className="ai-check">
      <div className="row">
        <button type="button" disabled={ask.busy} onClick={check}>
          <Sparkles size={14} aria-hidden /> {ask.busy ? 'Checking…' : found && found.asked !== now ? 'Check again' : 'Check my square'}
        </button>
      </div>
      {found && (found.checks.length ? (
        <ul>
          {found.checks.map((item, index) => (
            <li key={`${item.code}-${index}`} className="row">
              <button type="button" className="grow" aria-pressed={lit === item} onClick={() => onLight(lit === item ? null : item)}>
                {item.severity === 'warn' ? <TriangleAlert size={14} aria-hidden /> : <Info size={14} aria-hidden />}
                <span><span>{item.message}</span> {item.fix && <span className="muted">{item.fix}</span>}</span>
              </button>
              <button type="button" className="icon" aria-label="Dismiss" onClick={() => dismiss(item)}><X size={14} /></button>
            </li>
          ))}
        </ul>
      ) : <p className="ok small"><Check size={14} aria-hidden /> Your model found nothing to flag{found.held ? ', and the template\'s judgement calls hold' : ''}</p>)}
      {found && <Audit hits={found.hits} />}
      {ask.error && <p className="error small" role="alert">{ask.error}</p>}
    </div>
  )
}

// ---- Find the turn ------------------------------------------------------------------------------------------------

/** Find the turn on a confirmed link: who moves, when and what it costs, for the link's note. */
export function FindTurn({ cast, update, link }: { cast: Cast; update: Update; link: Resonance }) {
  const ask = useAsk()
  const [found, setFound] = useState<{ turn: string; hits: AuditHit[]; before?: string } | null>(null)
  const find = () => void ask.run(() => aiCalls.turn(cast, link.a, link.b), (answer) => setFound({ turn: answer.turn, hits: answer.audit }))
  const apply = () => {
    if (!found) return
    setFound({ ...found, before: link.note })
    update((current) => setLinkNote(current, link, found.turn))
  }
  const undo = () => {
    if (found?.before === undefined) return
    update((current) => setLinkNote(current, link, found.before!))
    setFound({ ...found, before: undefined })
  }
  return <>
    {!found && <button type="button" disabled={ask.busy} onClick={find}><Sparkles size={14} aria-hidden /> {ask.busy ? 'Finding it…' : 'Find the turn'}</button>}
    {ask.error && <p className="error small ai-result" role="alert">{ask.error}</p>}
    {found && (
      <div className="ai-result proposal">
        {found.before === undefined && <><span>{found.turn}</span><Audit hits={found.hits} /></>}
        <div className="row">
          {found.before !== undefined ? <>
            <span className="ok small"><Check size={14} aria-hidden /> In the note</span>
            <button type="button" className="link" onClick={undo}><Undo2 size={13} aria-hidden /> Undo</button>
          </> : <>
            <button type="button" className="primary" onClick={apply}>Apply</button>
            <button type="button" onClick={() => setFound(null)}>Dismiss</button>
            <button type="button" className="link" disabled={ask.busy} onClick={find}><RefreshCw size={13} aria-hidden /> Another</button>
          </>}
        </div>
      </div>
    )}
  </>
}

// ---- Suggest a relationship ---------------------------------------------------------------------------------------

/** Suggest a relationship row: how one sees the other, the hidden tension (their wants against the other's flaws) and
 * how far they trust them. Offered while the row is empty; Undo stays until the row is changed by hand. */
export function SuggestRelationship({ cast, update, index }: { cast: Cast; update: Update; index: number }) {
  const ask = useAsk()
  const row = cast.relationships[index]
  const [found, setFound] = useState<{ from: string; to: string; proposal: RelationshipProposal; hits: AuditHit[]; before?: RelationshipProposal } | null>(null)
  // A proposal is for the pair it was asked about; picking someone else in the row drops it.
  const mine = found && row && found.from === row.from && found.to === row.to ? found : null
  if (!row) return null
  const suggest = () => void ask.run(() => aiCalls.relationship(cast, row.from, row.to), (answer) => setFound({ from: row.from, to: row.to, proposal: answer.proposal, hits: answer.audit }))
  const apply = () => {
    if (!mine) return
    setFound({ ...mine, before: { dynamic: row.dynamic, hidden_tension: row.hidden_tension, trust: row.trust } })
    update((current) => editRelationship(current, mine.from, mine.to, mine.proposal))
  }
  const undo = () => {
    if (!mine?.before) return
    update((current) => editRelationship(current, mine.from, mine.to, mine.before!))
    setFound(null)
  }
  const empty = !row.dynamic && !row.hidden_tension
  if (mine?.before) {
    const untouched = row.dynamic === mine.proposal.dynamic && row.hidden_tension === mine.proposal.hidden_tension && row.trust === mine.proposal.trust
    return untouched ? <div className="row"><button type="button" className="link" onClick={undo}><Undo2 size={13} aria-hidden /> Undo the suggestion</button></div> : null
  }
  if (mine) {
    const { proposal } = mine
    return (
      <div className="proposal">
        {proposal.dynamic && <span><span className="muted">Dynamic:</span> {proposal.dynamic}</span>}
        {proposal.hidden_tension && <span><span className="muted">Hidden tension:</span> {proposal.hidden_tension}</span>}
        <span><span className="muted">Trust:</span> {proposal.trust} of 10</span>
        <Audit hits={mine.hits} />
        <div className="row">
          <button type="button" className="primary" onClick={apply}>Apply</button>
          <button type="button" onClick={() => setFound(null)}>Dismiss</button>
        </div>
      </div>
    )
  }
  if (!empty) return null
  return <>
    <div className="row"><button type="button" disabled={ask.busy} onClick={suggest}><Sparkles size={14} aria-hidden /> {ask.busy ? 'Suggesting…' : 'Suggest'}</button></div>
    {ask.error && <p className="error small" role="alert">{ask.error}</p>}
  </>
}
