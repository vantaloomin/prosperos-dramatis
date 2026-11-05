import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Drama, Link2, Plus, Swords, Users, X } from 'lucide-react'
import { APPS, APP_NAMES, getJson, type Health, type Saved, type Summary } from './api'
import { CastBoard, linkSaved, type Board } from './cast/CastBoard'
import { CastStart } from './cast/CastStart'
import { castCalls, draftIdea, editCorner, findCorner, type Cast, type SavedCast } from './castApi'
import { Assistant } from './assistant/Assistant'
import { useAssistantShown } from './assistant/store'
import { draftStore, NEW, useChangedDrafts } from './drafts'
import { Editor } from './Editor'
import { ModelSettings } from './ModelSettings'
import { Start, type Begun, type Picks } from './Start'

/** A corner waiting for a character: drafting from the Cast board carries it to the quick start and the form, and the
 * first save links the new character there. `castKey` is the cast's id, or `new` for one not saved yet. */
interface Pending { castKey: string; cornerId: string }

type View =
  | { kind: 'start'; initial?: Picks; pending?: Pending }
  | { kind: 'edit'; key: string; draft: string; saved: Saved | null; begun: Begun; pending?: Pending }
  | { kind: 'new-cast' }
  | { kind: 'cast'; key: string }


const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0].toUpperCase()).join('')

/** Saved characters, with new ones not saved yet first. A row says which apps only when not all three, the start of
 * About them when two share a name, and when it has changes not saved. */
function Library({ chosen, onOpen, onOpenDraft, onNew }: {
  chosen: string | null; onOpen: (id: string) => void; onOpenDraft: (key: string) => void; onNew: () => void
}) {
  const listing = useQuery({ queryKey: ['characters'], queryFn: () => getJson<Summary[]>('/api/characters') })
  const drafts = useChangedDrafts()
  const changed = new Set(drafts.map((draft) => draft.key))
  const unsaved = drafts.filter((draft) => draft.key.startsWith(NEW))
  const names = new Map<string, number>()
  for (const item of listing.data ?? []) names.set(item.name, (names.get(item.name) ?? 0) + 1)
  const line = (item: Summary) => [
    item.apps.length < APPS.length ? item.apps.map((app) => APP_NAMES[app]).join(', ') : '',
    (names.get(item.name) ?? 0) > 1 ? (item.about.length > 60 ? `${item.about.slice(0, 60).trimEnd()}…` : item.about) : '',
    changed.has(item.id) ? 'Unsaved changes' : '',
  ].filter(Boolean).join(' · ')
  return (
    <>
      <h2><Users size={16} aria-hidden /> Characters</h2>
      <button type="button" className="wide" onClick={onNew}><Plus size={14} aria-hidden /> New character</button>
      {listing.isError && <p className="error small">{listing.error.message}</p>}
      {listing.data && !listing.data.length && !unsaved.length && <p className="muted small">Nobody yet.</p>}
      <ul className="choices">
        {unsaved.map((draft) => (
          <li key={draft.key}>
            <button type="button" aria-pressed={chosen === draft.key} onClick={() => onOpenDraft(draft.key)}>
              <span className="thumb" aria-hidden>{initials(draft.name)}</span>
              <span><strong>{draft.name || 'New character'}</strong><span className="muted small">Not saved yet</span></span>
            </button>
          </li>
        ))}
        {listing.data?.map((item) => {
          const name = drafts.find((draft) => draft.key === item.id)?.name || item.name
          return (
          <li key={item.id}>
            <button type="button" aria-pressed={chosen === item.id} onClick={() => onOpen(item.id)}>
              {item.portrait ? <img className="thumb" src={`/api/characters/${item.id}/portrait.png?at=${item.updated}`} alt="" /> : <span className="thumb" aria-hidden>{initials(name)}</span>}
              <span>
                <strong>{name}</strong>
                {line(item) && <span className="muted small">{line(item)}</span>}
              </span>
            </button>
          </li>
          )
        })}
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
  const assisting = useAssistantShown()
  // On a phone the library is a drawer over the page, opened from the top bar.
  const [drawer, setDrawer] = useState(false)
  const go = (next: View) => { setError(''); setLinked(null); setDrawer(false); setView(next) }

  /** A saved character, as their unsaved changes left them if they have any. */
  const open = async (id: string) => {
    try {
      const saved = await getJson<Saved>(`/api/characters/${id}`)
      const draft = draftStore.get(id)
      const begun = draft?.changed ? draft.begun : { character: saved.character, seed: saved.seed }
      go({ kind: 'edit', key: `${id}-${Date.now()}`, draft: id, saved, begun })
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

  const openDraft = (key: string) => {
    const draft = draftStore.get(key)
    if (draft) go({ kind: 'edit', key: `${key}-${Date.now()}`, draft: key, saved: null, begun: draft.begun })
  }
  const begin = (begun: Begun) => setView((current) => {
    const key = `${NEW}-${Date.now()}`
    return { kind: 'edit', key, draft: key, saved: null, begun, pending: current.kind === 'start' ? current.pending : undefined }
  })
  const pending = view.kind === 'start' || view.kind === 'edit' ? view.pending : undefined
  const pendingBoard = pending && boards[pending.castKey]
  const chosen = view.kind === 'edit' ? view.saved?.id ?? view.draft : null
  return (
    <div className={assisting ? 'shell assisting' : 'shell'}>
      <a className="skip" href="#work">Skip to the {view.kind === 'edit' ? 'form' : view.kind === 'cast' ? 'board' : 'page'}</a>
      <header className="top">
        <button type="button" className="drawer-toggle" aria-expanded={drawer} aria-controls="library" onClick={() => setDrawer(!drawer)}>
          <Users size={15} aria-hidden /> Characters
        </button>
        <Drama size={18} aria-hidden />
        <h1>Prospero's Dramatis</h1>
        <span className="muted small">{health.data ? `v${health.data.version}` : health.isError ? 'server not reachable' : '…'}</span>
        <div className="top-model"><ModelSettings /></div>
      </header>
      {drawer && <div className="drawer-scrim" onClick={() => setDrawer(false)} aria-hidden />}
      <aside id="library" className={drawer ? 'pane library open' : 'pane library'} aria-label="Library"
        onKeyDown={(event) => { if (event.key === 'Escape') setDrawer(false) }}>
        <button type="button" className="icon drawer-close" aria-label="Close the library" onClick={() => setDrawer(false)}><X size={16} /></button>
        <Library chosen={chosen} onOpen={(id) => void open(id)} onOpenDraft={openDraft} onNew={() => go({ kind: 'start' })} />
        <Casts chosen={view.kind === 'cast' ? view.key : null} boards={boards} onOpen={(key) => void openCast(key)} onNew={() => go({ kind: 'new-cast' })} />
        {error && <p className="error small">{error}</p>}
      </aside>
      <main id="work" className="pane work" tabIndex={-1}>
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
              filledIn={view.begun.filledIn} missing={view.begun.missing} note={view.begun.note} portrait={view.begun.portrait}
              brought={view.begun.brought ?? !!view.saved?.character.card?.source} allowed={view.begun.allowed}
              draftKey={view.draft} begun={view.begun}
              onSaved={(saved) => {
                setView((current) => current.kind === 'edit' ? { ...current, saved, draft: saved.id, pending: undefined } : current)
                if (view.pending) void link(view.pending, saved)
              }}
              onDeleted={() => go({ kind: 'start' })}
              onDiscard={() => view.saved ? void open(view.saved.id) : go({ kind: 'start' })} />
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
      {assisting && <Assistant />}
    </div>
  )
}
