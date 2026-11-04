/** What the board's AI help proposes, in place, as on the character form (src/proposals.ts): a suggested corner, a
 * link's turn or a relationship goes onto the board at once, marked, with Keep / Put back where it stands. Put back
 * restores what was there; a second proposal in the same place keeps the first one's restore, so Put back always goes
 * back to the author's own. Save keeps whatever is still open. Keys: `corner:<id>`, `link:<a>~<b>~<on>`,
 * `relationship:<from>~<to>`. */
import { createContext, useContext, useState, type ReactNode } from 'react'
import { Square, TriangleAlert } from 'lucide-react'
import type { AuditHit } from '../api'
import type { Cast } from '../castApi'
import { Bolt } from '../Fields'

export interface BoardProposal { label: string; restore: (cast: Cast) => Cast; hits: AuditHit[] }
export interface BoardProposals {
  open: Record<string, BoardProposal>
  propose: (key: string, proposal: BoardProposal) => void
  keep: (key: string) => void
  putBack: (key: string) => void
  keepAll: () => void
}

const Proposals = createContext<BoardProposals | null>(null)
export const ProposalsProvider = Proposals.Provider

export function useBoardProposalState(update: (change: (cast: Cast) => Cast) => void): BoardProposals {
  const [open, setOpen] = useState<Record<string, BoardProposal>>({})
  const without = (key: string) => setOpen((current) => Object.fromEntries(Object.entries(current).filter(([at]) => at !== key)))
  return {
    open,
    propose: (key, proposal) => setOpen((current) => ({ ...current, [key]: current[key] ? { ...proposal, restore: current[key].restore } : proposal })),
    keep: without,
    putBack: (key) => {
      const found = open[key]
      if (found) update(found.restore)
      without(key)
    },
    keepAll: () => setOpen({}),
  }
}

export function useBoardProposals(): BoardProposals {
  const found = useContext(Proposals)
  if (!found) throw new Error('Board proposals are used outside a board.')
  return found
}

export const cornerKey = (id: string) => `corner:${id}`
export const turnKey = (link: { a: string; b: string; on: string }) => `link:${[link.a, link.b].sort().join('~')}~${link.on}`
export const relationshipKey = (from: string, to: string) => `relationship:${from}~${to}`

const hardOf = (hits: AuditHit[]) => [...new Set(hits.filter((hit) => hit.severity === 'hard').map((hit) => hit.match.trim() || hit.rule))]

/** Keep / Put back under what a model put on the board, and Try again where asking again makes sense. */
export function BoardProposalBar({ at, again, busy, onStop }: { at: string; again?: () => void; busy?: boolean; onStop?: () => void }): ReactNode {
  const proposals = useBoardProposals()
  const found = proposals.open[at]
  if (!found) return null
  const hard = hardOf(found.hits)
  return (
    <div className="proposal-bar" role="group" aria-label={`Proposed ${found.label}`}>
      <button type="button" className="primary" onClick={() => proposals.keep(at)}>Keep</button>
      <button type="button" className="quiet" onClick={() => proposals.putBack(at)}>Put back</button>
      {again && (busy
        ? <button type="button" className="quiet" onClick={onStop}><Square size={11} aria-hidden /> Stop</button>
        : <button type="button" className="quiet" onClick={again}><Bolt size={13} /> Try again</button>)}
      {hard.length > 0 && <span className="error small"><TriangleAlert size={13} aria-hidden /> Reads as model-written: {hard.join(', ')}</span>}
    </div>
  )
}
