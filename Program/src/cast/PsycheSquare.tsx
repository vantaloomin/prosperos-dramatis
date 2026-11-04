import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import { getJson, type Saved } from '../api'
import { IMPULSES, corners, type Cast, type Psyche } from '../castApi'

/** The focused character, read from the library: their name and their psyche, when they have one. */
export function useFocus(id: string | null) {
  const found = useQuery({ queryKey: ['character', id], enabled: !!id, queryFn: () => getJson<Saved>(`/api/characters/${id}`) })
  const psyche = (found.data?.character as { psyche?: Psyche | null } | undefined)?.psyche ?? null
  return { name: found.data?.character.name || 'They', psyche, loading: found.isLoading, error: found.error?.message ?? '' }
}

/** Which board corners press on each impulse: the corners whose character the impulse names in `pressed_by`. */
export function pressLines(cast: Cast, psyche: Psyche | null) {
  if (!psyche) return []
  return IMPULSES.flatMap(([key]) => corners(cast)
    .filter(({ corner }) => corner.character_id && psyche[key]?.pressed_by.includes(corner.character_id))
    .map(({ corner }) => ({ key: `psyche:${key}~${corner.id}`, from: `psyche:${key}`, to: corner.id, kind: 'psyche' as const })))
}

/** A small fifth square: the focused character's four impulses, read-only. Their form is where they change. */
export function PsycheSquare({ id, focus, register, onOpen, onClose }: {
  id: string; focus: ReturnType<typeof useFocus>; register: (key: string, element: HTMLElement | null) => void
  onOpen: (id: string) => void; onClose: () => void
}) {
  const filled = focus.psyche && IMPULSES.some(([key]) => focus.psyche?.[key]?.text)
  return (
    <section className="psyche-square" aria-label={`${focus.name}'s inner square`}>
      <div className="row">
        <strong className="grow">{focus.loading ? 'Loading…' : focus.name}</strong>
        <button type="button" className="icon" aria-label="Open their form" title="Open their form" onClick={() => onOpen(id)}><ExternalLink size={14} /></button>
        <button type="button" className="icon" aria-label="Stop focusing" title="Stop focusing" onClick={onClose}><X size={14} /></button>
      </div>
      {focus.error ? <p className="error small">{focus.error}</p> : !focus.loading && !filled ? (
        <p className="muted small">No inner square yet. <button type="button" className="link" onClick={() => onOpen(id)}>Write it on their form</button></p>
      ) : (
        <div className="impulses">
          {IMPULSES.map(([key, label]) => (
            <div key={key} className="impulse" ref={(element) => register(`psyche:${key}`, element)}>
              <span className="hint">{label}</span>
              <span>{focus.psyche?.[key]?.text || '…'}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
