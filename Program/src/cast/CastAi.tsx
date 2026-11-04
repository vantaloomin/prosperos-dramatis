/** AI help on the Cast board: Suggest corners, Check my square, Find the turn and Suggest a relationship. Each sends the
 * board as it stands to the user's model (dramatis/cast_ai.py). What it writes goes onto the board in place as a
 * proposal (boardProposals.tsx), marked, with Keep / Put back where it stands; only Save writes the cast. What the model
 * wrote comes with the AI-slop audit's hits, shown the way the character form shows them. Every call has a Stop. */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Check, Cpu, Info, RefreshCw, TriangleAlert, X } from 'lucide-react'
import type { AuditHit } from '../api'
import { Audit } from '../Editor'
import { Bolt, ModelButton } from '../Fields'
import { openModelSettings } from '../ModelSettings'
import { useModelCall } from '../modelCall'
import {
  aiCalls, editRelationship, findCorner, placeProposal, proposedOf, setLinkNote, targetSquare, unplaceProposal, words,
  type Cast, type CastCheck, type CornerProposal, type Resonance, type SuggestTarget, type TagInfo,
} from '../castApi'
import { BoardProposalBar, cornerKey, relationshipKey, turnKey, useBoardProposals } from './boardProposals'

type Update = (change: (cast: Cast) => Cast) => void

const hitsAt = (hits: AuditHit[], prefix: string) => hits.filter((hit) => hit.field === prefix || hit.field.startsWith(`${prefix}.`))

/** Where the AI buttons would be, when no model is set up: one link to the model settings. */
export function SetUpModel() {
  return <button type="button" className="link" onClick={openModelSettings}><Cpu size={13} aria-hidden /> Set up a text model</button>
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

interface Offered { proposal: CornerProposal; hits: AuditHit[]; placed?: string }

/** Suggest corners for the outer square (in the board header) or for one side's inner square (in its card). Use puts a
 * suggestion on the board, marked in its corner for Keep or Put back. */
export function SuggestCorners({ cast, update, target, tags, compact }: { cast: Cast; update: Update; target: SuggestTarget; tags: TagInfo[]; compact?: boolean }) {
  const call = useModelCall()
  const proposals = useBoardProposals()
  const [open, setOpen] = useState(false)
  const [offered, setOffered] = useState<Offered[]>([])
  const side = target === 'outer' ? null : findCorner(cast, target)?.corner
  const square = targetSquare(cast, target)
  const name = side ? side.label || 'this side' : 'the outer square'
  const fetch = () => void call.run((signal) => aiCalls.suggest(cast, target, signal), (found) => setOffered(found.proposals.map((proposal, index) => ({
    proposal, hits: hitsAt(found.audit, `proposals.${index}`),
  }))))
  const toggle = () => { setOpen(!open); if (!open && !offered.length) fetch() }
  const use = (index: number, into: string | null) => {
    const { proposal, hits } = offered[index]
    const placed = placeProposal(cast, target, proposal, into)
    if (!placed) return
    const corner = into ? findCorner(cast, into)?.corner : undefined
    const before = corner ? proposedOf(corner) : null
    update((current) => placeProposal(current, target, proposal, into)?.cast ?? current)
    proposals.propose(cornerKey(placed.id), { label: proposal.label, hits, restore: (current) => unplaceProposal(current, placed.id, before) })
    setOffered((items) => items.map((item, at) => at === index ? { ...item, placed: placed.id } : item))
  }
  if (!square) return null
  const tagName = (tag: string) => tags.find((item) => item.id === tag)?.label ?? tag
  const cornerName = (id: string) => findCorner(cast, id)?.corner.label || 'the unnamed corner'
  return (
    <div className="ai-pop">
      {compact
        ? <button type="button" className="icon bolt" aria-expanded={open} aria-label={`Suggest corners for ${name}`} title="Suggest corners" onClick={toggle}><Bolt size={15} /></button>
        : <button type="button" aria-expanded={open} onClick={toggle}><Bolt /> Suggest corners</button>}
      {open && <Panel label={`Suggestions for ${name}`} onClose={() => setOpen(false)}>
      {call.busy && <div className="row"><button type="button" onClick={call.stop}>Stop</button><span className="muted small" role="status">Asking your model…</span></div>}
      {call.error && <p className="error small" role="alert">{call.error}</p>}
      <ul className="proposals">
        {offered.map((item, index) => {
          const { proposal, placed } = item
          const into = proposal.corner_id && square.corners.some((corner) => corner.id === proposal.corner_id) ? proposal.corner_id : null
          const full = square.corners.length >= 4
          const standing = placed && findCorner(cast, placed)
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
                {standing ? <span className="ok small"><Check size={14} aria-hidden /> In {cornerName(placed)}{proposals.open[cornerKey(placed)] ? ', to keep or put back' : ''}</span>
                  : into || !full
                    ? <button type="button" onClick={() => use(index, into)}>{into ? `Use in ${cornerName(into)}` : 'Use as a new corner'}</button>
                    : (
                      <select aria-label={`Put ${proposal.label} in place of`} value="" onChange={(event) => event.target.value && use(index, event.target.value)}>
                        <option value="">Use in place of…</option>
                        {square.corners.map((corner) => <option key={corner.id} value={corner.id}>{corner.label || 'Unnamed corner'}</option>)}
                      </select>
                    )}
              </div>
            </li>
          )
        })}
      </ul>
      {!call.busy && (offered.length > 0 || call.error) && (
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
  const call = useModelCall()
  const [found, setFound] = useState<{ checks: CastCheck[]; hits: AuditHit[]; held: number; asked: string } | null>(null)
  const now = JSON.stringify(cast)
  // Nothing to judge until some corner says what it stands for.
  const stanced = cast.outer.corners.some((side) => side.stance.trim() || side.inner?.corners.some((corner) => corner.stance.trim()))
  const check = () => void call.run((signal) => aiCalls.check(cast, signal), (answer) => {
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
        <ModelButton busy={call.busy} onRun={check} onStop={call.stop} disabled={!stanced} busyText="Checking the square">
          {found && found.asked !== now ? 'Check again' : 'Check my square'}
        </ModelButton>
        {!stanced && <span className="muted small">Once a corner has a stance</span>}
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
      {call.error && <p className="error small" role="alert">{call.error}</p>}
    </div>
  )
}

// ---- Find the turn ------------------------------------------------------------------------------------------------

/** Find the turn on a confirmed link: who moves, when and what it costs, written into the link's note as a proposal. */
export function FindTurn({ cast, update, link }: { cast: Cast; update: Update; link: Resonance }) {
  const call = useModelCall()
  const proposals = useBoardProposals()
  const key = turnKey(link)
  const find = () => void call.run((signal) => aiCalls.turn(cast, link.a, link.b, signal), (answer) => {
    const before = link.note
    update((current) => setLinkNote(current, link, answer.turn))
    proposals.propose(key, { label: 'the turn', hits: answer.audit, restore: (current) => setLinkNote(current, link, before) })
  })
  if (proposals.open[key]) return <BoardProposalBar at={key} again={find} busy={call.busy} onStop={call.stop} />
  return <>
    <ModelButton busy={call.busy} onRun={find} onStop={call.stop} busyText="Finding the turn">Find the turn</ModelButton>
    {call.error && <p className="error small ai-result" role="alert">{call.error}</p>}
  </>
}

// ---- Suggest a relationship ---------------------------------------------------------------------------------------

/** Suggest a relationship row: how one sees the other, the hidden tension (their wants against the other's flaws) and
 * how far they trust them, written into the row as a proposal. Offered while the row is empty. */
export function SuggestRelationship({ cast, update, index }: { cast: Cast; update: Update; index: number }) {
  const call = useModelCall()
  const proposals = useBoardProposals()
  const row = cast.relationships[index]
  if (!row) return null
  const key = relationshipKey(row.from, row.to)
  const suggest = () => void call.run((signal) => aiCalls.relationship(cast, row.from, row.to, signal), (answer) => {
    const { from, to } = row
    const before = { dynamic: row.dynamic, hidden_tension: row.hidden_tension, trust: row.trust }
    update((current) => editRelationship(current, from, to, answer.proposal))
    proposals.propose(key, { label: 'this relationship', hits: answer.audit, restore: (current) => editRelationship(current, from, to, before) })
  })
  if (proposals.open[key]) return <BoardProposalBar at={key} again={suggest} busy={call.busy} onStop={call.stop} />
  if (row.dynamic || row.hidden_tension) return null
  return <>
    <div className="row"><ModelButton busy={call.busy} onRun={suggest} onStop={call.stop} busyText="Suggesting">Suggest</ModelButton></div>
    {call.error && <p className="error small" role="alert">{call.error}</p>}
  </>
}
