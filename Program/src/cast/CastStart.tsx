import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Swords } from 'lucide-react'
import { Field, TextInput } from '../Fields'
import { LIMITS, castCalls, newCast, type Cast } from '../castApi'

/** A new cast: the question the story asks, and a genre and group type to start from, or a blank board. */
export function CastStart({ onBegin }: { onBegin: (cast: Cast) => void }) {
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
        <TextInput label="The question your story asks" value={theme} onChange={setTheme} maxLength={LIMITS.theme}
          placeholder="Is order worth what it costs?" />
        {templates.isError && <p className="error small">{templates.error.message} You can still start a blank board.</p>}
        <div className="grid two">
          <Field label="Genre" hint={genre?.help}>{(id) => (
            <select id={id} value={genreId} onChange={(event) => setGenreId(event.target.value)} disabled={!templates.data}>
              <option value="">None</option>
              {templates.data?.genres.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          )}</Field>
          <Field label="Group type" hint={group?.shares}>{(id) => (
            <select id={id} value={groupId ?? genre?.group ?? ''} onChange={(event) => setGroupId(event.target.value)} disabled={!templates.data}>
              <option value="">None</option>
              {templates.data?.groups.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          )}</Field>
        </div>
        {genre && (
          <ul className="genre-sides">
            {genre.outer.map((side, index) => <li key={index}><strong>{side.label}</strong>{side.stance_hint && <span className="muted"> {side.stance_hint}</span>}</li>)}
          </ul>
        )}
        <div className="row">
          <button type="submit" className="primary" disabled={!genre && !group}>Start the board</button>
          <button type="button" onClick={() => onBegin(newCast(theme.trim(), undefined, undefined))}>Blank board</button>
        </div>
      </form>
    </section>
  )
}
