// Models, from Prospero's Companion src/features/settings/models/ModelSettings.tsx at c641bca: the profiles and which
// does each job. Companion's recall profiles, Mix, per-world jobs, built-in model and local program launcher are its
// own and stay there.
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Pencil, PlugZap, Trash2 } from 'lucide-react'
import { CliLookRow } from './CliAccountPicker'
import { ModelUsage } from './ModelUsage'
import { ProfileEditor } from './ProfileEditor'
import { api, Notice, useReturnFocus } from './ui'
import { useModelUsage } from './usage'
import type { ModelJob, ModelProfile, ModelsOverview } from './types'

export const MODELS_KEY = ['models']
const WRITING = 'writing'
type Result = { tone: 'info' | 'error'; text: string } | null
const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

export const useModels = () => useQuery({ queryKey: MODELS_KEY, queryFn: () => api<ModelsOverview>('/models') })

/** The profile a job's calls go to: its own, else the writing profile's; undefined while none is finished. */
export function profileFor(overview: ModelsOverview | undefined, job: string): ModelProfile | undefined {
  const id = overview?.routes[job] ?? overview?.routes[WRITING]
  return overview?.profiles.find(profile => profile.id === id && profile.ready)
}

type Editing = string | 'new' | null

export function ModelSettings() {
  const client = useQueryClient()
  const query = useModels()
  const [editing, setEditing] = useState<Editing>(null)
  const [result, setResult] = useState<Result>(null)
  const addButton = useReturnFocus<HTMLButtonElement>(editing === 'new')
  if (!query.data) return query.isError ? <Notice tone="error">{failure(query.error, 'Models could not be read.')}</Notice> : null
  const overview = query.data
  const refresh = (data?: ModelsOverview) => {
    if (data) client.setQueryData(MODELS_KEY, data)
    void client.invalidateQueries({ queryKey: MODELS_KEY })
  }
  const done = (saved?: ModelProfile) => { setEditing(null); if (saved) { setResult({ tone: 'info', text: `${saved.name} saved. New requests use it.` }); refresh() } }
  const profiles = overview.profiles
  return <section className="form-stack models">
    {profiles.length === 0 && editing !== 'new' && <p className="subtle">No text model yet.</p>}
    {profiles.length > 0 && <ul className="model-profiles">
      {profiles.map(profile => editing === profile.id
        ? <li key={profile.id}><ProfileEditor profile={profile} others={profiles} onDone={done} /></li>
        : <ProfileCard key={profile.id} profile={profile} jobs={overview.jobs.filter(job => overview.routes[job.key] === profile.id)} onEdit={() => setEditing(profile.id)} onCopied={setEditing} onChanged={refresh} setResult={setResult} />)}
    </ul>}
    {editing === 'new' ? <ProfileEditor others={profiles} onDone={done} />
      : <div className="form-actions"><button ref={addButton} type="button" className={profiles.length ? 'button' : 'button primary'} onClick={() => { setResult(null); setEditing('new') }}>Add a model profile</button></div>}
    <CliLookRow overview={overview} />
    {profiles.some(profile => profile.ready) && <JobAssignments overview={overview} onChanged={refresh} setResult={setResult} />}
    {result && <Notice tone={result.tone}>{result.text}</Notice>}
  </section>
}

function keyLine(profile: ModelProfile) {
  if (!profile.has_saved_key) return ''
  return profile.key_shared_with?.length ? ` · key shared with ${profile.key_shared_with.join(', ')}` : ' · key saved'
}

function ProfileCard({ profile, jobs, onEdit, onCopied, onChanged, setResult }: { profile: ModelProfile; jobs: ModelJob[]; onEdit: () => void; onCopied: (id: string) => void; onChanged: (data?: ModelsOverview) => void; setResult: (result: Result) => void }) {
  const [busy, setBusy] = useState(false)
  const [check, setCheck] = useState<{ count: number; note?: string } | null>(null)
  const { usage, refresh } = useModelUsage(profile)
  const run = async (work: () => Promise<void>) => { setBusy(true); try { await work() } catch (error) { setResult({ tone: 'error', text: failure(error, 'That did not work.') }) } finally { setBusy(false) } }
  const verify = () => run(async () => { setCheck(null); const found = await api<{ models: string[]; note?: string }>(`/models/profiles/${profile.id}/check`, {}); setCheck({ count: found.models.length, note: found.note }); void refresh() })
  // Another model on the same service: a copy with the same key and settings, open for its model to be changed.
  const copy = () => run(async () => { const made = await api<ModelProfile>(`/models/profiles/${profile.id}/duplicate`, {}); onChanged(); setResult(null); onCopied(made.id) })
  const remove = () => {
    if (!window.confirm(`Delete ${profile.name}? ${profile.key_shared_with?.length ? 'Its saved key stays, since another profile uses it' : 'Its saved key is removed from your keychain'}${jobs.length ? ', and its jobs go back to the writing profile' : ''}.`)) return
    void run(async () => { onChanged(await api<ModelsOverview>(`/models/profiles/${profile.id}`, undefined, 'DELETE')); setResult({ tone: 'info', text: `${profile.name} deleted.` }) })
  }
  const where = profile.config.provider === 'codex' ? 'Codex CLI login' : profile.config.provider === 'claude_code' ? 'Claude Code login' : profile.config.base_url
  return <li className="model-profile">
    <div><span className="eyebrow">{profile.provider_name}</span><h3>{profile.name}</h3>
      <p className="subtle">{profile.config.model || 'Unfinished: choose a model'} · {where}{keyLine(profile)}</p>
      <ModelUsage usage={usage} />
      {jobs.length > 0 && <p className="model-jobs"><Check size={14} aria-hidden="true" />{jobs.map(job => job.name).join(', ')}</p>}
      {check && <p className="subtle" role="status">Connected. {check.count ? `${check.count} models available. ` : ''}No text was generated.{check.note ? ` ${check.note}` : ''}</p>}
    </div>
    <div className="form-actions">
      <button type="button" className="button" onClick={() => void verify()} disabled={busy}><PlugZap size={15} aria-hidden="true" />{busy ? 'Checking…' : 'Check connection'}</button>
      <button type="button" className="button" onClick={onEdit} aria-label={`Edit ${profile.name}`}><Pencil size={15} aria-hidden="true" />Edit</button>
      <button type="button" className="button" onClick={() => void copy()} disabled={busy} aria-label={`Duplicate ${profile.name}`}><Copy size={15} aria-hidden="true" />Duplicate</button>
      <button type="button" className="button" onClick={remove} disabled={busy} aria-label={`Delete ${profile.name}`}><Trash2 size={15} aria-hidden="true" />Delete</button>
    </div>
  </li>
}

function JobAssignments({ overview, onChanged, setResult }: { overview: ModelsOverview; onChanged: (data?: ModelsOverview) => void; setResult: (result: Result) => void }) {
  const ready = overview.profiles.filter(profile => profile.ready)
  const writing = overview.profiles.find(profile => profile.id === overview.routes[WRITING])
  const change = async (job: ModelJob, profileId: string) => {
    try {
      onChanged(await api<ModelsOverview>('/models/routes', { job: job.key, profile_id: profileId || null }, 'PUT'))
      setResult({ tone: 'info', text: `${job.name} updated.` })
    } catch (error) { setResult({ tone: 'error', text: failure(error, 'Not changed.') }) }
  }
  return <fieldset className="model-routes form-stack"><legend>Which profile does each job</legend>
    {overview.jobs.map(job => <div className="field" key={job.key}>
      <label htmlFor={`model-job-${job.key}`}>{job.name}</label>
      <select id={`model-job-${job.key}`} value={overview.routes[job.key] ?? ''} title={job.detail} onChange={event => void change(job, event.target.value)}>
        <option value="">{job.key === WRITING ? 'None' : `Same as writing${writing ? ` (${writing.name})` : ''}`}</option>
        {ready.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
      </select>
    </div>)}
  </fieldset>
}
