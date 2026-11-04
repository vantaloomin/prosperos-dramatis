import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Sparkles, Trash2 } from 'lucide-react'
import { fileData, getJson, sendJson, type Character, type ImageConfig, type MadePortrait, type PortraitStyle, type Saved } from './api'
import { useModelReady } from './Fields'

interface Props {
  saved: Saved | null; name: string; character: () => Character
  /** A picture picked before they were saved, as base64 PNG; the editor saves it with them. */
  pending: string | null; onPending: (data: string | null) => void
  onSaved: (saved: Saved) => void
}

/** Their portrait: add or change one from a file, remove it, or make one from how they look. A made portrait shows
 * beside the current one and is saved only with Use this. */
export function Portrait({ saved, name, character, pending, onPending, onSaved }: Props) {
  const client = useQueryClient()
  const modelReady = useModelReady()
  const images = useQuery({ queryKey: ['images'], queryFn: () => getJson<ImageConfig>('/api/images') })
  const styles = useQuery({ queryKey: ['portrait-styles'], queryFn: () => getJson<PortraitStyle[]>('/api/portrait/styles'), staleTime: Infinity })
  const [style, setStyle] = useState('photo')
  const [made, setMade] = useState<MadePortrait | null>(null)
  const [making, setMaking] = useState(false)
  const [error, setError] = useState('')
  const [at, setAt] = useState(Date.now())
  const picker = useRef<HTMLInputElement>(null)
  const current = pending ? `data:image/png;base64,${pending}` : saved?.portrait ? `/api/characters/${saved.id}/portrait.png?at=${at}` : null
  const canMake = modelReady && !!images.data?.ready

  const attempt = async (work: () => Promise<void>, failed: string) => {
    setError('')
    try { await work() } catch (failure) { setError(failure instanceof Error ? failure.message : failed) }
  }
  const changed = async (next: Saved) => {
    onSaved(next)
    setAt(Date.now())
    await client.invalidateQueries({ queryKey: ['characters'] })
  }
  const keep = async (data: string, filename: string) => {
    if (!saved) return onPending(data)
    await changed(await sendJson<Saved>(`/api/characters/${saved.id}/portrait`, 'PUT', { filename, data }))
  }
  const upload = (file: File | undefined) => file && void attempt(async () => {
    try { await keep(await fileData(file), file.name) } finally { if (picker.current) picker.current.value = '' }
  }, 'That picture could not be used.')
  const remove = () => void attempt(async () => {
    if (!saved) return onPending(null)
    await changed(await sendJson<Saved>(`/api/characters/${saved.id}/portrait`, 'DELETE'))
  }, 'The portrait could not be removed.')
  // The form as it stands, saved or not, so a change to how they look shows in the next portrait.
  const make = () => void attempt(async () => {
    setMaking(true)
    try { setMade(await sendJson<MadePortrait>('/api/portrait/make', 'POST', { character: character(), style })) } finally { setMaking(false) }
  }, 'No portrait came back.')
  const use = () => made && void attempt(async () => { await keep(made.image, 'portrait.png'); setMade(null) }, 'That portrait could not be saved.')

  return (
    <div className="portrait">
      <div className="portrait-pair">
        {current ? <img src={current} alt={name ? `${name}'s portrait` : 'Their portrait'} /> : <div className="no-portrait" aria-hidden />}
        {made && <img className="made" src={`data:image/png;base64,${made.image}`} alt="The portrait just made" />}
      </div>
      <input ref={picker} type="file" accept=".png,image/png" hidden onChange={(event) => upload(event.target.files?.[0])} />
      {made ? (
        <>
          <div className="row">
            <button type="button" className="primary" disabled={making} onClick={use}>Use this</button>
            <button type="button" disabled={making} onClick={make}>{making ? 'Drawing…' : 'Try again'}</button>
            <button type="button" className="link" disabled={making} onClick={() => setMade(null)}>Discard</button>
          </div>
          <details className="small"><summary>Prompt</summary><p className="muted">{made.prompt}</p></details>
        </>
      ) : (
        <>
          <div className="row">
            <button type="button" className="link" onClick={() => picker.current?.click()}><ImagePlus size={13} aria-hidden /> {current ? 'Change portrait' : 'Add a portrait'}</button>
            {current && <button type="button" className="link danger" onClick={remove}><Trash2 size={13} aria-hidden /> Remove</button>}
          </div>
          {canMake && (
            <div className="row">
              <select aria-label="Style" value={style} onChange={(event) => setStyle(event.target.value)}>
                {styles.data?.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}
              </select>
              <button type="button" disabled={making} onClick={make}><Sparkles size={13} aria-hidden /> {making ? 'Drawing…' : 'Make a portrait'}</button>
            </div>
          )}
        </>
      )}
      {error && <p className="error small" role="alert">{error}</p>}
    </div>
  )
}
