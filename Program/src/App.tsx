import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Drama, Link2, Plus, Swords, Users } from 'lucide-react'
import { APP_NAMES, getJson, type Health, type Saved, type Summary } from './api'
import { CastBoard, linkSaved, type Board } from './cast/CastBoard'
import { CastStart } from './cast/CastStart'
import { castCalls, draftIdea, editCorner, findCorner, type Cast, type SavedCast } from './castApi'
import { Editor } from './Editor'
import { ModelSettings } from './ModelSettings'
import { Start, type Begun, type Picks } from './Start'

/** A corner waiting for a character: drafting from the Cast board carries it to the quick start and the form, and the
 * first save links the new character there. `castKey` is the cast's id, or `new` for one not saved yet. */
interface Pending { castKey: string; cornerId: string }

type View =
  | { kind: 'start'; initial?: Picks; pending?: Pending }
  | { kind: 'edit'; key: string; saved: Saved | null; begun: Begun; pending?: Pending }
  | { kind: 'new-cast' }
  | { kind: 'cast'; key: string }

const NEW = 'new'

function Library({ chosen, onOpen, onNew }: { chosen: string | null; onOpen: (id: string) => void; onNew: () => void }) {
  const listing = useQuery({ queryKey: ['characters'], queryFn: () => getJson<Summary[]>('/api/characters') })
  return (
    <>
      <h2><Users size={16} aria-hidden /> Characters</h2>
      <button type="button" className="primary wide" onClick={onNew}><Plus size={14} aria-hidden /> New character</button>
      {listing.isError && <p className="error small">{listing.error.message}</p>}
      {listing.data && !listing.data.length && <p className="muted small">Nobody yet. Characters you save live here, and each one exports as a card for the Prospero apps or any chat app.</p>}
      <ul className="choices">
        {listing.data?.map((item) => (
          <li key={item.id}>
            <button type="button" aria-pressed={chosen === item.id} onClick={() => onOpen(item.id)}>
              {item.portrait ? <img className="thumb" src={`/api/characters/${item.id}/portrait.png?at=${item.updated}`} alt="" /> : <span className="thumb" aria-hidden />}
              <span>
                <strong>{item.name}</strong>
                <span className="muted small">{item.apps.map((app) => APP_NAMES[app]).join(', ')}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

/** Casts, with any board still being edited: an unsaved new one first, and a mark on those with unsaved changes. */
function Casts({ chosen, boards, onOpen, onNew }: { chosen: string | null; boards: Record<string, Board>; onOpen: (key: string) => void; onNew: () => void }) {
  const listing = useQuery({ queryKey: ['casts'], queryFn: castCalls.list })
  const changed = (key: string) => !!boards[key]?.saved && JSON.stringify(boards[key].saved?.cast) !== JSON.stringify(boards[key].cast)
  const unsaved = boards[NEW]
  return (
    <>
      <h2 className="casts-title"><Swords size={16} aria-hidden /> Casts</h2>
      <button type="button" className="wide" onClick={onNew}><Plus size={14} aria-hidden /> New cast</button>
      {listing.isError && <p className="error small">{listing.error.message}</p>}
      <ul className="choices">
        {unsaved && (
          <li>
            <button type="button" aria-pressed={chosen === NEW} onClick={() => onOpen(NEW)}>
              <span><strong>{unsaved.cast.title || 'Untitled cast'}</strong><span className="muted small">Not saved yet</span></span>
            </button>
          </li>
        )}
        {listing.data?.map((item) => (
          <li key={item.id}>
            <button type="button" aria-pressed={chosen === item.id} onClick={() => onOpen(item.id)}>
              <span>
                <strong>{boards[item.id]?.cast.title || item.title || 'Untitled cast'}</strong>
                <span className="muted small">
                  {item.characters === 1 ? '1 character' : `${item.characters} characters`}{changed(item.id) ? ', unsaved changes' : ''}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

/** The libraries on the left; the quick start, a character's form or a cast's board in the middle. */
export function App() {
  const client = useQueryClient()
  const health = useQuery({ queryKey: ['health'], queryFn: () => getJson<Health>('/api/health') })
  const [view, setView] = useState<View>({ kind: 'start' })
  const [boards, setBoards] = useState<Record<string, Board>>({})
  const [linked, setLinked] = useState<{ castKey: string; text: string } | null>(null)
  const [error, setError] = useState('')
  const go = (next: View) => { setError(''); setLinked(null); setView(next) }

  const open = async (id: string) => {
    try {
      const saved = await getJson<Saved>(`/api/characters/${id}`)
      go({ kind: 'edit', key: `${id}-${saved.updated}`, saved, begun: { character: saved.character, seed: saved.seed } })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'They could not be opened.')
    }
  }
  const openCast = async (key: string) => {
    if (boards[key]) { go({ kind: 'cast', key }); return }
    try {
      const saved = await castCalls.get(key)
      setBoards((current) => ({ ...current, [key]: { saved, cast: saved.cast } }))
      go({ kind: 'cast', key })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The cast could not be opened.')
    }
  }
  const updateBoard = (key: string) => (change: (cast: Cast) => Cast) =>
    setBoards((current) => current[key] ? { ...current, [key]: { ...current[key], cast: change(current[key].cast) } } : current)
  const castSaved = (key: string, saved: SavedCast) => {
    setBoards((current) => {
      const { [key]: _, ...rest } = current
      return { ...rest, [saved.id]: { saved, cast: saved.cast, note: key === saved.id ? undefined : `Saved ${saved.cast.title || 'the cast'}.` } }
    })
    if (key !== saved.id) setView({ kind: 'cast', key: saved.id })
  }
  const castDeleted = (key: string) => {
    setBoards((current) => {
      const { [key]: _, ...rest } = current
      return rest
    })
    go({ kind: 'new-cast' })
  }

  /** The character just saved goes into the corner that asked for them: in the board as edited, and in the stored cast. */
  const link = async (pending: Pending, character: Saved) => {
    const { castKey, cornerId } = pending
    const put = (cast: Cast) => editCorner(cast, cornerId, (corner) => ({ ...corner, character_id: character.id }))
    setBoards((current) => current[castKey] ? { ...current, [castKey]: { ...current[castKey], cast: put(current[castKey].cast) } } : current)
    const board = boards[castKey]
    const where = `${(board && findCorner(board.cast, cornerId)?.corner.label) || 'their corner'} in ${board?.cast.title || 'the cast'}`
    try {
      if (castKey !== NEW) {
        const stored = await linkSaved(castKey, cornerId, character.id)
        if (stored) setBoards((current) => current[castKey] ? { ...current, [castKey]: { ...current[castKey], saved: stored } } : current)
        await client.invalidateQueries({ queryKey: ['casts'] })
      }
      setLinked({ castKey, text: `Linked ${character.character.name || 'them'} to ${where}.` })
    } catch (failure) {
      setLinked({ castKey, text: `${character.character.name || 'They'} could not be linked to ${where}.${failure instanceof Error ? ` ${failure.message}` : ''}` })
    }
  }

  const begin = (begun: Begun) => setView((current) => ({
    kind: 'edit', key: `new-${Date.now()}`, saved: null, begun, pending: current.kind === 'start' ? current.pending : undefined,
  }))
  const pending = view.kind === 'start' || view.kind === 'edit' ? view.pending : undefined
  const pendingBoard = pending && boards[pending.castKey]
  const chosen = view.kind === 'edit' ? view.saved?.id ?? null : null
  return (
    <div className="shell">
      <header className="top">
        <Drama size={18} aria-hidden />
        <h1>Prospero's Dramatis</h1>
        <span className="muted small">{health.data ? `v${health.data.version}` : health.isError ? 'server not reachable' : '…'}</span>
        <div className="top-model"><ModelSettings /></div>
      </header>
      <aside className="pane library" aria-label="Library">
        <Library chosen={chosen} onOpen={(id) => void open(id)} onNew={() => go({ kind: 'start' })} />
        <Casts chosen={view.kind === 'cast' ? view.key : null} boards={boards} onOpen={(key) => void openCast(key)} onNew={() => go({ kind: 'new-cast' })} />
        {error && <p className="error small">{error}</p>}
      </aside>
      <main className="pane work">
        {(pendingBoard || linked) && (
          <p className="note link-bar" role="status">
            <Link2 size={14} aria-hidden />
            {linked ? linked.text : `Saving them puts them in ${findCorner(pendingBoard!.cast, pending!.cornerId)?.corner.label || 'their corner'} in ${pendingBoard!.cast.title || 'the cast'}.`}
            <button type="button" className="link" onClick={() => void openCast(linked?.castKey ?? pending!.castKey)}>Back to the cast</button>
          </p>
        )}
        {view.kind === 'start' ? <Start key={pending ? `${pending.castKey}-${pending.cornerId}` : 'start'} initial={view.initial} onBegin={begin} />
          : view.kind === 'edit' ? (
            <Editor key={view.key} saved={view.saved} start={view.begun.character} seed={view.saved?.seed ?? view.begun.seed ?? 'dramatis'}
              filledIn={view.begun.filledIn} note={view.begun.note}
              onSaved={(saved) => {
                setView((current) => current.kind === 'edit' ? { ...current, saved, pending: undefined } : current)
                if (view.pending) void link(view.pending, saved)
              }}
              onDeleted={() => go({ kind: 'start' })} />
          ) : view.kind === 'new-cast' ? (
            <CastStart onBegin={(cast) => {
              setBoards((current) => ({ ...current, [NEW]: { saved: null, cast } }))
              go({ kind: 'cast', key: NEW })
            }} />
          ) : boards[view.key] ? (
            <CastBoard key={view.key} board={boards[view.key]} update={updateBoard(view.key)}
              onSaved={(saved) => castSaved(view.key, saved)} onDeleted={() => castDeleted(view.key)}
              onDraft={(cornerId) => go({ kind: 'start', initial: { idea: draftIdea(boards[view.key].cast, cornerId) }, pending: { castKey: view.key, cornerId } })}
              onOpenCharacter={(id) => void open(id)} />
          ) : null}
      </main>
    </div>
  )
}
