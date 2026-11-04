import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Drama, Plus, Users } from 'lucide-react'
import { APP_NAMES, getJson, type Health, type Saved, type Summary } from './api'
import { Editor } from './Editor'
import { ModelSettings } from './ModelSettings'
import { Start, type Begun } from './Start'

type View = { kind: 'start' } | { kind: 'edit'; key: string; saved: Saved | null; begun: Begun }

function Library({ chosen, onOpen, onNew }: { chosen: string | null; onOpen: (id: string) => void; onNew: () => void }) {
  const listing = useQuery({ queryKey: ['characters'], queryFn: () => getJson<Summary[]>('/api/characters') })
  return (
    <>
      <h2><Users size={16} aria-hidden /> Characters</h2>
      <button type="button" className="primary wide" onClick={onNew}><Plus size={14} aria-hidden /> New character</button>
      {listing.isError && <p className="error small">{listing.error.message}</p>}
      {listing.data && !listing.data.length && <p className="muted small">Nobody yet. Characters you save live here, and each one exports as a card for any Prospero app.</p>}
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

/** The library on the left; the quick start or a character's form in the middle. */
export function App() {
  const health = useQuery({ queryKey: ['health'], queryFn: () => getJson<Health>('/api/health') })
  const [view, setView] = useState<View>({ kind: 'start' })
  const [error, setError] = useState('')
  const open = async (id: string) => {
    setError('')
    try {
      const saved = await getJson<Saved>(`/api/characters/${id}`)
      setView({ kind: 'edit', key: `${id}-${saved.updated}`, saved, begun: { character: saved.character, seed: saved.seed } })
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'They could not be opened.')
    }
  }
  const begin = (begun: Begun) => setView({ kind: 'edit', key: `new-${Date.now()}`, saved: null, begun })
  const chosen = view.kind === 'edit' ? view.saved?.id ?? null : null
  return (
    <div className="shell">
      <header className="top">
        <Drama size={18} aria-hidden />
        <h1>Prospero's Dramatis</h1>
        <span className="muted small">{health.data ? `v${health.data.version}` : health.isError ? 'server not reachable' : '…'}</span>
        <div className="top-model"><ModelSettings /></div>
      </header>
      <aside className="pane library" aria-label="Characters">
        <Library chosen={chosen} onOpen={(id) => void open(id)} onNew={() => setView({ kind: 'start' })} />
        {error && <p className="error small">{error}</p>}
      </aside>
      <main className="pane work">
        {view.kind === 'start' ? <Start onBegin={begin} /> : (
          <Editor key={view.key} saved={view.saved} start={view.begun.character} seed={view.saved?.seed ?? view.begun.seed ?? 'dramatis'}
            filledIn={view.begun.filledIn} note={view.begun.note}
            onSaved={(saved) => setView((current) => current.kind === 'edit' ? { ...current, saved } : current)}
            onDeleted={() => setView({ kind: 'start' })} />
        )}
      </main>
    </div>
  )
}
