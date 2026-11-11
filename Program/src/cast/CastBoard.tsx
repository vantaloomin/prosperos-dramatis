import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { getJson, savedOver, type Summary } from '../api'
import { CARD_TARGETS } from '../editor/status'
import { LIMITS, castCalls, editCorner, findCorner, linkedCharacters, type Cast, type CastCheck, type Computed, type SavedCast } from '../castApi'
import { ProposalsProvider, useBoardProposalState } from './boardProposals'
import { Checks } from './Checks'
import type { CornerContext } from './CornerCard'
import { PsycheSquare, pressLines, useFocus } from './PsycheSquare'
import { Relationships } from './Relationships'
import { Dismissed, ResonanceLines, ResonanceList, ResonancePanel, boardLinks, type Line } from './ResonanceLines'
import { HeaderActions } from './slots'
import { SquareView } from './SquareView'

/** A cast as the board holds it: the saved record (none until the first Save) and the cast as edited. */
export interface Board { saved: SavedCast | null; cast: Cast; note?: string }

interface Props {
  board: Board
  update: (change: (cast: Cast) => Cast) => void
  onSaved: (saved: SavedCast) => void
  onDeleted: () => void
  /** Draft a character for a corner through the quick start; saving them links them here. */
  onDraft: (cornerId: string) => void
  onOpenCharacter: (id: string) => void
}

/** One cast: the outer square and any inner squares, resonance between sides, the checks, the relationships, and the
 * focused character's inner square. Edits stay in the app until Save; the checks run on the unsaved board. */
export function CastBoard({ board, update, onSaved, onDeleted, onDraft, onOpenCharacter }: Props) {
  const client = useQueryClient()
  const { cast, saved } = board
  const templates = useQuery({ queryKey: ['cast-templates'], queryFn: castCalls.templates, staleTime: Infinity })
  const characters = useQuery({ queryKey: ['characters'], queryFn: () => getJson<Summary[]>('/api/characters') })
  const [computed, setComputed] = useState<Computed | null>(saved?.computed ?? null)
  const [checkError, setCheckError] = useState('')
  const [lit, setLit] = useState<CastCheck | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ tone: 'note' | 'error'; text: string } | null>(board.note ? { tone: 'note', text: board.note } : null)
  const [boardElement, setBoardElement] = useState<HTMLDivElement | null>(null)
  const proposals = useBoardProposalState(update)
  // A new board shows its checks from the first edit on, not while it is still blank.
  const [touched, setTouched] = useState(!!saved)
  const opened = useRef(cast)
  useEffect(() => { if (cast !== opened.current) setTouched(true) }, [cast])
  const elements = useRef(new Map<string, HTMLElement>())
  const register = useCallback((key: string, element: HTMLElement | null) => {
    if (element) elements.current.set(key, element)
    else elements.current.delete(key)
  }, [])

  // The server's checks and resonance candidates for the board as it stands, 400 ms after the last change.
  const asked = useRef(0)
  useEffect(() => {
    const ask = ++asked.current
    const timer = setTimeout(() => {
      castCalls.check(cast)
        .then((found) => { if (ask === asked.current) { setComputed(found.computed); setCheckError('') } })
        .catch((failure: Error) => { if (ask === asked.current) setCheckError(failure.message) })
    }, 400)
    return () => clearTimeout(timer)
  }, [cast])

  const genre = templates.data?.genres.find((item) => item.id === cast.genre)
  const group = templates.data?.groups.find((item) => item.id === cast.group)
  const tags = templates.data?.tags ?? []
  const names = computed?.names ?? {}
  const links = boardLinks(cast, computed)
  const link = links.find((item) => item.key === selected)
  const focus = useFocus(cast.focus_id)

  const pairs = new Map<string, Line>()
  for (const item of links) {
    const key = [item.a, item.b].sort().join('~')
    if (!pairs.has(key) || item.confirmed) pairs.set(key, { key, from: item.a, to: item.b, kind: item.confirmed ? 'confirmed' : 'candidate' })
  }
  const lines = [...pairs.values(), ...pressLines(cast, cast.focus_id ? focus.psyche : null)]
  const highlighted = new Set([...(lit?.corners ?? []), ...(link ? [link.a, link.b] : [])])

  const context: CornerContext = {
    tags, characters: characters.data ?? [], names, focusId: cast.focus_id, highlighted, register, onDraft, onOpenCharacter,
    onFocus: (id) => update((current) => ({ ...current, focus_id: id })),
  }
  const dirty = !saved || JSON.stringify(saved.cast) !== JSON.stringify(cast)

  const light = (check: CastCheck | null) => {
    setLit(check)
    const first = check?.corners.find((id) => elements.current.has(id))
    if (first) elements.current.get(first)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }
  const save = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setResult(null)
    try {
      proposals.keepAll()
      const next = await savedOver((revision) => castCalls.save(cast, saved?.id ?? null, revision), saved?.revision)
      await client.invalidateQueries({ queryKey: ['casts'] })
      setComputed(next.computed)
      setResult({ tone: 'note', text: `Saved ${next.cast.title || 'the cast'}.` })
      onSaved(next)
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'The cast could not be saved.' })
    } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!saved || !window.confirm(`Delete ${cast.title || 'this cast'}? Its characters stay in the library.`)) return
    try {
      await castCalls.remove(saved.id)
      await client.invalidateQueries({ queryKey: ['casts'] })
      onDeleted()
    } catch (failure) {
      setResult({ tone: 'error', text: failure instanceof Error ? failure.message : 'The cast could not be deleted.' })
    }
  }

  return (
    <ProposalsProvider value={proposals}>
    <form className="cast-board" onSubmit={save}>
      <div className="editor-head">
        <input className="cast-title" aria-label="Title" value={cast.title} maxLength={LIMITS.title} placeholder="Untitled cast"
          onChange={(event) => update((current) => ({ ...current, title: event.target.value }))} />
        <div className="row">
          <HeaderActions cast={cast} update={update} tags={tags} />
          <button type="submit" className="primary" disabled={busy || !dirty}>{busy ? 'Saving…' : saved ? 'Save' : 'Save the cast'}</button>
          {saved && <ExportCast saved={saved} />}
          {saved && <button type="button" className="icon danger" aria-label="Delete this cast" onClick={() => void remove()}><Trash2 size={15} /></button>}
        </div>
      </div>
      <input className="cast-theme" aria-label="The question your story asks" value={cast.theme} maxLength={LIMITS.theme} placeholder="The question your story asks"
        onChange={(event) => update((current) => ({ ...current, theme: event.target.value }))} />
      {result && <p className={result.tone} role="status">{result.text}</p>}

      <div className="board" ref={setBoardElement}>
        <SquareView cast={cast} axes={templates.data?.axes ?? []} genre={genre} group={group} context={context} update={update} />
        {cast.focus_id && (
          <PsycheSquare id={cast.focus_id} focus={focus} register={register} onOpen={onOpenCharacter}
            onClose={() => update((current) => ({ ...current, focus_id: null }))} />
        )}
        <ResonanceLines board={boardElement} elements={elements.current} lines={lines} links={links} selected={selected} tags={tags} onPick={setSelected} />
      </div>
      <ResonanceList cast={cast} links={links} selected={selected} tags={tags} onPick={setSelected} />
      {link && <ResonancePanel key={link.key} cast={cast} link={link} tags={tags} update={update} onClose={() => setSelected(null)} />}
      <Dismissed cast={cast} tags={tags} update={update} />

      <Checks cast={cast} checks={touched ? computed?.checks ?? null : null} error={checkError} lit={lit} onLight={light} update={update} />
      <Relationships cast={cast} characters={characters.data ?? []} names={names} update={update} />
    </form>
    </ProposalsProvider>
  )
}

/** Export: the cast file, or a card for each of its characters, for the Prospero apps or for chat apps. */
function ExportCast({ saved }: { saved: SavedCast }) {
  const id = saved.id
  const named = linkedCharacters(saved.cast).length > 0 || saved.cast.relationships.length > 0 || !!saved.cast.focus_id
  const menu = useRef<HTMLDetailsElement>(null)
  const close = () => { if (menu.current) menu.current.open = false }
  return (
    <details className="export" ref={menu}>
      <summary className="button"><Download size={14} aria-hidden /> Export</summary>
      <ul>
        <li>
          <span>The cast</span>
          <span className="muted small">Its squares, links and relationships, with every character in it.</span>
          <span className="row"><a className="button" href={castCalls.exportUrl(id)} download onClick={close} aria-label="The cast as JSON">JSON</a></span>
        </li>
        {named && CARD_TARGETS.map(({ target, name, leaves }) => (
          <li key={target}>
            <span>A card for each character, for {name}</span>
            {leaves && <span className="muted small">{leaves}</span>}
            <span className="row">
              {(['png', 'json'] as const).map((kind) => (
                <a key={kind} className="button" href={castCalls.cardsUrl(id, target, kind)} download onClick={close}
                  aria-label={`Cards as ${kind.toUpperCase()} for ${name}`}>{kind.toUpperCase()}</a>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

/** Link a saved character to a corner of a saved cast: the stored cast is read fresh, so unsaved edits stay unsaved. */
export async function linkSaved(castId: string, cornerId: string, characterId: string): Promise<SavedCast | null> {
  const stored = await castCalls.get(castId)
  if (!findCorner(stored.cast, cornerId)) return null
  return castCalls.save(editCorner(stored.cast, cornerId, (corner) => ({ ...corner, character_id: characterId })), castId, stored.revision)
}
