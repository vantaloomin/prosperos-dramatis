import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, Image as ImageIcon, X } from 'lucide-react'
import { getJson, sendJson, type ImageCheck, type ImageConfig } from './api'
import { ModelSettings as ModelProfiles, profileFor, useModels } from './models/ModelSettings'

const OPEN = 'dramatis:set-up-model'

/** Open Models from anywhere, such as the Cast board's Set up a text model. */
export const openModelSettings = () => window.dispatchEvent(new Event(OPEN))

/** One Models button in the top bar, with a dot that turns amber while no text model is set up (portraits are
 * optional, so they never turn it). It opens one dialog: Text (Companion's profiles and jobs, src/models) and
 * Portraits. */
export function ModelSettings() {
  const models = useModels()
  const images = useQuery({ queryKey: ['images'], queryFn: () => getJson<ImageConfig>('/api/images') })
  const dialog = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)
  const show = () => { setOpen(true); dialog.current?.showModal() }
  useEffect(() => {
    window.addEventListener(OPEN, show)
    return () => window.removeEventListener(OPEN, show)
  }, [])
  const writing = profileFor(models.data, 'writing')
  const missing = !!models.data && !writing
  const state = [writing ? `Text: ${writing.name}` : models.data ? 'No text model yet' : '',
    images.data ? (images.data.kind === 'off' ? 'Portraits off' : `Portraits: ${IMAGE_KINDS[images.data.kind]}`) : ''].filter(Boolean).join('. ')
  return (
    <>
      <button type="button" className="models-button" onClick={show} title={state} aria-label={`Models. ${state}`}>
        <Cpu size={15} aria-hidden /> Models <span className={missing ? 'dot amber' : 'dot'} aria-hidden />
      </button>
      <dialog ref={dialog} className="models-dialog" aria-labelledby="models-title" onClose={() => setOpen(false)}>
        <header><h2 id="models-title">Models</h2><button type="button" className="icon-button" aria-label="Close" onClick={() => dialog.current?.close()}><X size={18} aria-hidden /></button></header>
        {open && <>
          <section aria-labelledby="models-text"><h3 id="models-text" className="models-section"><Cpu size={16} aria-hidden /> Text</h3><ModelProfiles /></section>
          <section aria-labelledby="models-portraits"><h3 id="models-portraits" className="models-section"><ImageIcon size={16} aria-hidden /> Portraits</h3><ImageSettings /></section>
        </>}
      </dialog>
    </>
  )
}

const IMAGE_KINDS = { off: 'No image maker', comfyui: 'ComfyUI', codex: 'Codex (ChatGPT subscription)', hosted: 'An image API' }
const COMFYUI_ADDRESS = 'http://127.0.0.1:8188'

/** Which image maker draws portraits: Companion's own choices. Off until set up; Check asks the maker what it has
 * without drawing anything. */
function ImageSettings() {
  const client = useQueryClient()
  const current = useQuery({ queryKey: ['images'], queryFn: () => getJson<ImageConfig>('/api/images') })
  const [editing, setEditing] = useState<ImageConfig & { key: string } | null>(null)
  const save = useMutation({
    mutationFn: (form: ImageConfig & { key: string }) => sendJson<ImageConfig>('/api/images', 'PUT',
      { kind: form.kind, provider: form.provider, family: form.family, base_url: form.base_url, model: form.model, key: form.key ? form.key : null }),
    onSuccess: (next) => { client.setQueryData(['images'], next); setEditing(null); check.reset() },
  })
  const check = useMutation({ mutationFn: () => sendJson<ImageCheck>('/api/images/check', 'POST') })
  if (!current.data) return null
  const chosen = current.data
  if (!editing) {
    const what = chosen.kind === 'hosted' ? chosen.providers[chosen.provider]?.label : IMAGE_KINDS[chosen.kind]
    const detail = chosen.kind === 'comfyui' ? [chosen.families[chosen.family], chosen.model] : chosen.kind === 'hosted' ? [chosen.model] : []
    return (
      <div className="model-line">
        {chosen.kind === 'off' ? 'Off' : what}
        {detail.filter(Boolean).map((part) => <span key={part}> · <code>{part}</code></span>)}
        {chosen.kind !== 'off' && <button type="button" className="link" disabled={check.isPending} onClick={() => check.mutate()}>{check.isPending ? 'Checking…' : 'Check'}</button>}
        <button type="button" className="link" onClick={() => setEditing({ ...chosen, key: '' })}>{chosen.kind === 'off' ? 'Set up' : 'Change'}</button>
        {check.data && <details className={check.data.ok ? undefined : 'error'}><summary>{check.data.summary}</summary>
          {check.data.details.length > 0 && <ul>{check.data.details.map((line) => <li key={line}>{line}</li>)}</ul>}</details>}
        {check.isError && <span className="error">{check.error.message}</span>}
      </div>
    )
  }
  const providers = Object.entries(chosen.providers)
  // A suggested address follows the provider picked; one the user typed stays.
  const suggested = [COMFYUI_ADDRESS, ...providers.map(([, provider]) => provider.base_url)]
  const typed = editing.base_url && !suggested.includes(editing.base_url)
  const pick = (kind: ImageConfig['kind'], provider = editing.provider) => setEditing({
    ...editing, kind, provider,
    base_url: typed ? editing.base_url : kind === 'comfyui' ? COMFYUI_ADDRESS : kind === 'hosted' ? chosen.providers[provider]?.base_url ?? '' : '',
  })
  return (
    <form className="model-form form-grid" onSubmit={(event) => { event.preventDefault(); save.mutate(editing) }}>
      <select aria-label="Image maker" value={editing.kind} onChange={(event) => pick(event.target.value as ImageConfig['kind'])}>
        {Object.entries(IMAGE_KINDS).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
      </select>
      {editing.kind === 'hosted' && (
        <select aria-label="Image API" value={editing.provider} onChange={(event) => pick('hosted', event.target.value)}>
          {providers.map(([value, provider]) => <option key={value} value={value}>{provider.label}</option>)}
        </select>
      )}
      {editing.kind === 'comfyui' && (
        <select aria-label="Model family" value={editing.family} onChange={(event) => setEditing({ ...editing, family: event.target.value })}>
          {Object.entries(chosen.families).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      )}
      {(editing.kind === 'comfyui' || editing.kind === 'hosted') && <>
        <input aria-label="Address" placeholder={editing.kind === 'comfyui' ? COMFYUI_ADDRESS : 'https://…/v1'} value={editing.base_url}
          onChange={(event) => setEditing({ ...editing, base_url: event.target.value })} />
        <input aria-label={editing.kind === 'comfyui' ? 'Model file' : 'Image model'} value={editing.model}
          placeholder={editing.kind === 'comfyui' ? "Model file (empty: the family's own)" : 'Image model, like gpt-image-1'}
          onChange={(event) => setEditing({ ...editing, model: event.target.value })} />
      </>}
      {editing.kind === 'hosted' && (
        <input aria-label="Image API key" type="password" placeholder={chosen.has_key ? 'Key saved (leave blank to keep)' : 'API key'}
          value={editing.key} onChange={(event) => setEditing({ ...editing, key: event.target.value })} />
      )}
      <div className="row">
        <button type="submit" disabled={save.isPending}>Save</button>
        <button type="button" onClick={() => setEditing(null)}>Cancel</button>
      </div>
      {save.isError && <p className="error small">{save.error.message}</p>}
    </form>
  )
}
