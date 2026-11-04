import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, Image as ImageIcon } from 'lucide-react'
import { getJson, sendJson, type ImageCheck, type ImageConfig, type ModelConfig } from './api'

const PROVIDER_NAMES = { anthropic: 'Claude (Anthropic API)', openai: 'OpenAI-compatible server', 'claude-cli': 'claude command line' }

/** Which model drafts: shown in one line, edited in place. Keys go to the system keyring, never the settings file. */
export function ModelSettings() {
  const client = useQueryClient()
  const current = useQuery({ queryKey: ['models'], queryFn: () => getJson<ModelConfig>('/api/models') })
  const [editing, setEditing] = useState<ModelConfig & { key: string } | null>(null)
  const save = useMutation({
    mutationFn: (form: ModelConfig & { key: string }) => sendJson<ModelConfig>('/api/models', 'PUT',
      { provider: form.provider, model: form.model, base_url: form.base_url, key: form.key ? form.key : null }),
    onSuccess: (next) => { client.setQueryData(['models'], next); setEditing(null) },
  })
  if (!current.data) return null
  if (!editing) {
    return (
      <p className="model-line small">
        <Cpu size={14} aria-hidden /> {PROVIDER_NAMES[current.data.provider]}{current.data.model && <> · <code>{current.data.model}</code></>}
        <button type="button" className="link" onClick={() => setEditing({ ...current.data, key: '' })}>Change</button>
      </p>
    )
  }
  return (
    <form className="model-form" onSubmit={(event) => { event.preventDefault(); save.mutate(editing) }}>
      <select aria-label="Provider" value={editing.provider} onChange={(event) => setEditing({ ...editing, provider: event.target.value as ModelConfig['provider'] })}>
        {Object.entries(PROVIDER_NAMES).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
      </select>
      <input aria-label="Model" placeholder={editing.provider === 'anthropic' ? 'claude-opus-5-5' : 'Model name'} value={editing.model}
        onChange={(event) => setEditing({ ...editing, model: event.target.value })} />
      {editing.provider === 'openai' && (
        <input aria-label="Server address" placeholder="http://127.0.0.1:1234/v1" value={editing.base_url}
          onChange={(event) => setEditing({ ...editing, base_url: event.target.value })} />
      )}
      {editing.provider !== 'claude-cli' && (
        <input aria-label="API key" type="password" placeholder={current.data.has_key ? 'Key saved (leave blank to keep)' : 'API key (optional for local servers)'}
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

const IMAGE_KINDS = { off: 'No image maker', comfyui: 'ComfyUI', codex: 'Codex (ChatGPT subscription)', hosted: 'An image API' }
const COMFYUI_ADDRESS = 'http://127.0.0.1:8188'

/** Which image maker draws portraits, beside the model line and edited the same way: Companion's own choices. Off until
 * set up; Check asks the maker what it has without drawing anything. */
export function ImageSettings() {
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
      <div className="model-line small">
        <ImageIcon size={14} aria-hidden /> {chosen.kind === 'off' ? 'Portraits off' : <>Portraits: {what}</>}
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
    <form className="model-form" onSubmit={(event) => { event.preventDefault(); save.mutate(editing) }}>
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
