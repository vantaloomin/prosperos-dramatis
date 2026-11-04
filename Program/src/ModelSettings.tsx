import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, Image as ImageIcon } from 'lucide-react'
import { getJson, sendJson, type ImageConfig, type ModelConfig } from './api'

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

const IMAGE_NAMES = { off: 'No image maker', openai: 'OpenAI-compatible images API', comfyui: 'ComfyUI on this computer' }
const IMAGE_ADDRESSES = { off: '', openai: 'https://api.openai.com/v1', comfyui: 'http://127.0.0.1:8188' }

/** Which image maker draws portraits, beside the model line and edited the same way. Off until set up. */
export function ImageSettings() {
  const client = useQueryClient()
  const current = useQuery({ queryKey: ['images'], queryFn: () => getJson<ImageConfig>('/api/images') })
  const [editing, setEditing] = useState<ImageConfig & { key: string } | null>(null)
  const save = useMutation({
    mutationFn: (form: ImageConfig & { key: string }) => sendJson<ImageConfig>('/api/images', 'PUT',
      { provider: form.provider, base_url: form.base_url, model: form.model, size: form.size, key: form.key ? form.key : null }),
    onSuccess: (next) => { client.setQueryData(['images'], next); setEditing(null) },
  })
  if (!current.data) return null
  if (!editing) {
    const chosen = current.data
    return (
      <p className="model-line small">
        <ImageIcon size={14} aria-hidden /> {chosen.provider === 'off' ? 'Portraits off' : <>Portraits: {IMAGE_NAMES[chosen.provider]}</>}
        {chosen.provider !== 'off' && chosen.model && <> · <code>{chosen.model}</code></>}
        <button type="button" className="link" onClick={() => setEditing({ ...chosen, key: '' })}>{chosen.provider === 'off' ? 'Set up' : 'Change'}</button>
      </p>
    )
  }
  // A suggested address follows the maker picked; one the user typed stays.
  const typed = editing.base_url && !Object.values(IMAGE_ADDRESSES).includes(editing.base_url)
  const pick = (provider: ImageConfig['provider']) => setEditing({ ...editing, provider, base_url: typed ? editing.base_url : IMAGE_ADDRESSES[provider] })
  return (
    <form className="model-form" onSubmit={(event) => { event.preventDefault(); save.mutate(editing) }}>
      <select aria-label="Image maker" value={editing.provider} onChange={(event) => pick(event.target.value as ImageConfig['provider'])}>
        {Object.entries(IMAGE_NAMES).map(([value, name]) => <option key={value} value={value}>{name}</option>)}
      </select>
      {editing.provider !== 'off' && <>
        <input aria-label="Image maker address" placeholder={IMAGE_ADDRESSES[editing.provider]} value={editing.base_url}
          onChange={(event) => setEditing({ ...editing, base_url: event.target.value })} />
        <input aria-label={editing.provider === 'comfyui' ? 'Checkpoint' : 'Image model'} value={editing.model}
          placeholder={editing.provider === 'comfyui' ? 'Checkpoint, like sd_xl_base_1.0.safetensors' : 'Image model, like gpt-image-1'}
          onChange={(event) => setEditing({ ...editing, model: event.target.value })} />
      </>}
      {editing.provider === 'openai' && <>
        <input aria-label="Picture size" className="size" placeholder="1024x1536" value={editing.size}
          onChange={(event) => setEditing({ ...editing, size: event.target.value })} />
        <input aria-label="Image API key" type="password" placeholder={current.data.has_key ? 'Key saved (leave blank to keep)' : 'API key'}
          value={editing.key} onChange={(event) => setEditing({ ...editing, key: event.target.value })} />
      </>}
      <div className="row">
        <button type="submit" disabled={save.isPending}>Save</button>
        <button type="button" onClick={() => setEditing(null)}>Cancel</button>
      </div>
      {save.isError && <p className="error small">{save.error.message}</p>}
    </form>
  )
}
