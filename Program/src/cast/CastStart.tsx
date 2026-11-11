import { useRef, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileUp, Swords } from 'lucide-react'
import { fileData, sendJson } from '../api'
import { Field, TextInput } from '../Fields'
import { LIMITS, castCalls, newCast, type Cast, type SavedCast } from '../castApi'

/** A new cast: the question the story asks, and a genre and group type to start from; with neither, a blank board.
 * Or a cast file another Dramatis exported, opened as a new cast with the characters it brings
 * (dramatis/library_tools.py). */
export function CastStart({ onBegin, onOpened }: { onBegin: (cast: Cast) => void; onOpened: (saved: SavedCast, note: string) => void }) {
  const picker = useRef<HTMLInputElement>(null)
  const [opening, setOpening] = useState(false)
  const [error, setError] = useState('')
  const open = async (file: File | undefined) => {
    if (!file) return
    setOpening(true)
    setError('')
    try {
      const found = await sendJson<{ cast: SavedCast; added: number }>('/api/library/casts/import', 'POST', { filename: file.name, data: await fileData(file) })
      const title = found.cast.cast.title || 'the cast'
      onOpened(found.cast, found.added ? `Opened ${title}, with ${found.added === 1 ? '1 character' : `${found.added} characters`} new to this library.` : `Opened ${title}.`)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That cast file could not be opened.')
    } finally {
      setOpening(false)
      if (picker.current) picker.current.value = ''
    }
  }
  const templates = useQuery({ queryKey: ['cast-templates'], queryFn: castCalls.templates, staleTime: Infinity })
  const [theme, setTheme] = useState('')
  const [genreId, setGenreId] = useState('')
  const [groupId, setGroupId] = useState<string | null>(null)  // null follows the genre's own group type
  const genre = templates.data?.genres.find((item) => item.id === genreId)
  const group = templates.data?.groups.find((item) => item.id === (groupId ?? genre?.group))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onBegin(newCast(theme.trim(), genre, group))
  }
  return (
    <section className="card cast-start" aria-labelledby="cast-start-title">
      <h2 id="cast-start-title"><Swords size={16} aria-hidden /> A new cast</h2>
      <form className="stack" onSubmit={submit}>
        <TextInput label="The question your story asks" value={theme} onChange={setTheme} maxLength={LIMITS.theme} />
        {templates.isError && <p className="error small">{templates.error.message} You can still start a blank board.</p>}
        <div className="grid two">
          <Field label="Genre">{(id) => (
            <select id={id} value={genreId} onChange={(event) => setGenreId(event.target.value)} disabled={!templates.data}>
              <option value="">None</option>
              {templates.data?.genres.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          )}</Field>
          <Field label="Group type">{(id) => (
            <select id={id} value={groupId ?? genre?.group ?? ''} onChange={(event) => setGroupId(event.target.value)} disabled={!templates.data}>
              <option value="">None</option>
              {templates.data?.groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          )}</Field>
        </div>
        {genre?.help && <p className="muted small">{genre.help}</p>}
        {genre && (
          <ul className="genre-sides">
            {genre.outer.map((side, index) => <li key={index}><strong>{side.label}</strong>{side.stance_hint && <span className="muted"> {side.stance_hint}</span>}</li>)}
          </ul>
        )}
        <div className="row">
          <button type="submit" className="primary">{genre || group ? 'Start the board' : 'Start a blank board'}</button>
          <button type="button" className="quiet" disabled={opening} onClick={() => picker.current?.click()}><FileUp size={14} aria-hidden /> {opening ? 'Opening…' : 'Open a cast file'}</button>
          <input ref={picker} type="file" accept=".json" hidden aria-label="Cast file" onChange={(event) => void open(event.target.files?.[0])} />
        </div>
        {error && <p className="error small" role="alert">{error}</p>}
      </form>
    </section>
  )
}
