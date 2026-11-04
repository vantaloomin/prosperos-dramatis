// The profile form from Prospero's Companion src/features/settings/models/ProfileEditor.tsx at c641bca (itself
// adapted from prosperos-study), without recall profiles. It opens in place in the list of profiles.
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Check, PlugZap } from 'lucide-react'
import { api, FoldRow, Field, Notice, SettingRow, shownPath, TextInput } from './ui'
import { CliAccountPicker } from './CliAccountPicker'
import { folderExample } from './cliAccounts'
import { GenerationSettings } from './GenerationSettings'
import { generationShort, generationSummary } from './budgets'
import { ModelCombobox } from './ModelCombobox'
import { applyDiscovered, discoveredSettings, profileReady, reusableKey, savedKeyApplies, typedModelSettings, type Discovery } from './discovery'
import { cliProviders, configFor, providerOrder, providers, type ModelProfile, type ProfileConfig, type Provider } from './types'

const failure = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback

function useDiscovery(profile?: ModelProfile) {
  const [result, setResult] = useState<Discovery | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const sequence = useRef(0)
  useEffect(() => () => { sequence.current++ }, [])
  const reset = () => { sequence.current++; setResult(null); setError(''); setBusy(false) }
  const connect = async (config: ProfileConfig, key: string, onResult: (value: Discovery) => void) => {
    const request = ++sequence.current
    setBusy(true); setError(''); setResult(null)
    try {
      const value = await api<Discovery>('/models/discover', { config, api_key: key || null, profile_id: profile?.id ?? null })
      if (request !== sequence.current) return
      setResult(value); onResult(value)
    } catch (problem) {
      if (request === sequence.current) setError(failure(problem, 'The connection test failed.'))
    } finally { if (request === sequence.current) setBusy(false) }
  }
  return { result, busy, error, reset, connect }
}

type Patch = (change: Partial<ProfileConfig>) => void
type Discovered = ReturnType<typeof useDiscovery>

function useSave(profile: ModelProfile | undefined, onDone: (saved?: ModelProfile) => void) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const save = async (body: { name: string; config: ProfileConfig; api_key: string | null; share_key?: boolean }) => {
    if (saving) return
    setSaving(true); setError('')
    try {
      onDone(profile
        ? await api<ModelProfile>(`/models/profiles/${profile.id}`, { ...body, expected_revision: profile.revision }, 'PUT')
        : await api<ModelProfile>('/models/profiles', body))
    } catch (problem) { setError(failure(problem, 'The profile was not saved.')) } finally { setSaving(false) }
  }
  return { saving, error, save }
}

function useProfileForm(profile: ModelProfile | undefined, others: ModelProfile[]) {
  const fresh = configFor
  const [name, setName] = useState(profile?.name ?? '')
  const [config, setConfig] = useState<ProfileConfig>(profile?.config ?? fresh('local'))
  const [key, setKey] = useState('')
  const [shareKey, setShareKey] = useState(true)
  const discovery = useDiscovery(profile)
  const patch: Patch = (change) => { if (change.base_url !== undefined || change.cli_account_dir !== undefined || change.cli_path !== undefined) discovery.reset(); setConfig(current => ({ ...current, ...change })) }
  const changeProvider = (provider: Provider) => { discovery.reset(); setConfig(fresh(provider)); setKey('') }
  const changeKey = (value: string) => { discovery.reset(); setKey(value) }
  const test = () => { void discovery.connect(config, key, result => setConfig(current => applyDiscovered(result, current))) }
  return { name, setName, config, key, discovery, found: discovery.result?.location, patch, changeProvider, changeKey, test, ...readiness(profile, config, key, others),
    shareKey, setShareKey, body: { name: name.trim(), config, api_key: key || null, share_key: shareKey } }
}

function keyState(profile: ModelProfile | undefined, config: ProfileConfig, others: ModelProfile[]) {
  const savedKey = savedKeyApplies(profile?.config, profile?.has_saved_key ?? false, config)
  return { savedKey, reused: savedKey ? undefined : reusableKey(others, config, profile?.id), sharedWith: savedKey ? profile?.key_shared_with ?? [] : [] }
}

function readiness(profile: ModelProfile | undefined, config: ProfileConfig, key: string, others: ModelProfile[]) {
  const { savedKey, reused, sharedWith } = keyState(profile, config, others)
  const ready = profileReady(config)
  return { savedKey, reused: reused?.name, sharedWith, ready, canSave: ready || !!key.trim() || savedKey || !!reused, keyless: cliProviders.includes(config.provider) }
}

export function ProfileEditor({ profile, others, onDone }: { profile?: ModelProfile; others: ModelProfile[]; onDone: (saved?: ModelProfile) => void }) {
  const form = useProfileForm(profile, others)
  const saving = useSave(profile, onDone)
  const { config, patch, discovery } = form
  const submit = (event: FormEvent) => { event.preventDefault(); if (form.canSave) void saving.save(form.body) }
  return <form className="model-profile-editor form-stack" onSubmit={submit} aria-label={profile ? `Edit ${profile.name}` : 'New model profile'}>
    <ProviderPicker selected={config.provider} choices={providerOrder} onChange={form.changeProvider} />
    <TextInput label="Profile name" value={form.name} onChange={form.setName} maxLength={120} placeholder="Careful drafting, quick local…" tip="Leave empty to name it after the provider and model." />
    <ConnectionFields config={config} patch={patch} fresh={!profile} keyEntry={{ saved: form.savedKey, reused: form.reused, sharedWith: form.sharedWith, value: form.key, onChange: form.changeKey, share: form.shareKey, onShare: form.setShareKey }} found={form.found} />
    <ModelDiscovery config={config} discovery={discovery} onTest={form.test} patch={patch} />
    <ModelFields config={config} patch={patch} discovery={discovery} />
    <SaveActions ready={form.ready} keyless={form.keyless} typed={!!form.key.trim()} canSave={form.canSave} saving={saving.saving} error={saving.error} onCancel={() => onDone()} />
  </form>
}

/** "the key" only once one is typed: a borrowed or already saved key is not what Save stores (Iris). */
function SaveActions({ ready, keyless, typed, canSave, saving, error, onCancel }: { ready: boolean; keyless: boolean; typed: boolean; canSave: boolean; saving: boolean; error: string; onCancel: () => void }) {
  const what = typed ? 'the key' : 'it'
  return <>
    {!ready && canSave && <p className="subtle">You can save {what} now and choose a model later.</p>}
    {error && <Notice tone="error">{error}</Notice>}
    <div className="form-actions"><button type="submit" className="button primary" disabled={!canSave} aria-disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button><button type="button" className="button" onClick={onCancel}>Cancel</button>{!keyless && <span className="subtle keychain-note">Keys are kept in your system keychain, never in Dramatis' settings file.</span>}</div>
  </>
}

const PROVIDER_TIPS: Partial<Record<Provider, string>> = {
  claude_code: 'Uses the Claude plan your Claude Code is signed in to. No key is entered here, and the app never sees your password or token. To sign in, run claude once in a terminal.',
}

/** One select (Iris, 1.3 form): what the provider is sits behind the ? on its label. */
function ProviderPicker({ selected, choices, onChange }: { selected: Provider; choices: Provider[]; onChange: (provider: Provider) => void }) {
  return <Field label="Provider" tip={PROVIDER_TIPS[selected] ?? providers[selected].description}>{(id, describedBy) =>
    <select id={id} value={selected} aria-describedby={describedBy} onChange={event => onChange(event.target.value as Provider)}>
      {choices.map(provider => <option key={provider} value={provider}>{providers[provider].name}</option>)}
    </select>}</Field>
}

type KeyEntry = { saved: boolean; reused?: string; sharedWith: string[]; value: string; onChange: (value: string) => void; share: boolean; onShare: (value: boolean) => void }

function ConnectionFields({ config, patch, fresh, keyEntry, found }: { config: ProfileConfig; patch: Patch; fresh: boolean; keyEntry: KeyEntry; found?: string }) {
  const local = config.provider === 'local' || config.provider === 'kobold'
  if (config.provider === 'codex') return <CodexFields config={config} patch={patch} fresh={fresh} found={found} />
  if (config.provider === 'claude_code') return <ClaudeCodeFields config={config} patch={patch} fresh={fresh} found={found} />
  return <>
    {(local || config.provider === 'compatible') && <TextInput label="Server address" value={config.base_url} onChange={value => patch({ base_url: value })} maxLength={500} tip={local ? 'An address on this computer. LM Studio and Ollama usually end in /v1.' : 'The API base URL, without /models or /chat/completions.'} />}
    <TokenEntry key={config.provider} {...keyEntry} local={local || config.provider === 'compatible'} />
  </>
}

type CliFieldsProps = { config: ProfileConfig; patch: Patch; fresh: boolean; found?: string }

const CLI_FIELDS = {
  claude_code: { base: 'claude', name: 'Claude Code', hint: 'For a second Claude account: a folder of its own that keeps that account\'s sign-in. Test connection says how to sign in to it. Leave empty for the account Claude Code usually uses.' },
  codex: { base: 'codex', name: 'Codex', hint: 'For a second ChatGPT account: a folder of its own that keeps that account\'s sign-in. Test connection says how to sign in to it. Leave empty for the account Codex usually uses.' },
} as const

/** Which account and where the CLI is, for Claude Code and Codex. Folders show the home folder as ~ (expanded on save). */
function CliFields({ config, patch, fresh, found }: CliFieldsProps) {
  const provider = config.provider === 'codex' ? 'codex' : 'claude_code'
  const fields = CLI_FIELDS[provider]
  return <>
    <CliAccountPicker provider={provider} value={config.cli_account_dir} fresh={fresh} onPick={folder => patch({ cli_account_dir: folder })}>
      <TextInput label="Account folder (optional)" value={shownPath(config.cli_account_dir ?? '')} onChange={value => patch({ cli_account_dir: value })} maxLength={500} placeholder={folderExample(fields.base)} tip={fields.hint} />
    </CliAccountPicker>
    <TextInput label={`${fields.name} location (optional)`} value={config.cli_path ?? ''} onChange={value => patch({ cli_path: value })} maxLength={500} placeholder={found ? shownPath(found) : undefined} tip={`Leave empty to use the ${fields.name} found on this computer.`} />
  </>
}

function ClaudeCodeFields(props: CliFieldsProps) {
  return <>
    <Notice>Claude follows Anthropic’s usage policy, so it won’t write a character’s adult side. For characters like that, give Writing another profile.</Notice>
    <CliFields {...props} />
  </>
}

function CodexFields(props: CliFieldsProps) {
  return <>
    <p className="subtle">Uses the Codex CLI’s own login; no key is entered here. Codex runs in an empty temporary folder with its shell, plugins, web search and tools turned off.</p>
    <CliFields {...props} />
  </>
}

function ModelDiscovery({ config, discovery, onTest, patch }: { config: ProfileConfig; discovery: Discovered; onTest: () => void; patch: Patch }) {
  const models = discovery.result?.model_details ?? []
  const choose = (id: string) => { const model = models.find(item => item.id === id); if (model) patch(discoveredSettings(model, config)) }
  return <section className="model-discovery form-stack" aria-label="Connection and models">
    <TestButton blocked={config.provider === 'compatible' && !config.base_url.trim()} busy={discovery.busy} connected={!!discovery.result} onTest={onTest} />
    {discovery.error && <Notice tone="error">{discovery.error}</Notice>}
    {discovery.result?.note && <p className="subtle">{discovery.result.note}</p>}
    {models.length > 0 && <ModelCombobox models={models} value={models.some(model => model.id === config.model) ? config.model : ''} onChange={choose} />}
  </section>
}

function TestButton({ blocked, busy, connected, onTest }: { blocked: boolean; busy: boolean; connected: boolean; onTest: () => void }) {
  return <div className="form-actions"><button type="button" className="button" disabled={busy || blocked} onClick={onTest}><PlugZap size={16} aria-hidden="true" />{busy ? 'Testing…' : 'Test connection'}</button>{connected && <span className="connection-success" role="status"><Check size={15} aria-hidden="true" />Connected</span>}</div>
}

function ModelFields({ config, patch, discovery }: { config: ProfileConfig; patch: Patch; discovery: Discovered }) {
  const models = discovery.result?.model_details ?? []
  return <>
    <TextInput label="Model ID" value={config.model} onChange={value => patch(typedModelSettings(value.trim(), config, models))} maxLength={200} placeholder="Pick from the list or type an ID"
      tip="The exact name the service uses for the model, such as gpt-4o-mini or llama3.1:8b. Test connection lists the models this service offers, and picking one fills in its settings." />
    <div className="row-list"><FoldRow summary="Generation settings" value={<GenerationValue config={config} />}>
      <div className="fold-pad"><GenerationSettings config={config} patch={patch} model={models.find(model => model.id === config.model)} /></div>
    </FoldRow></div>
  </>
}

function TokenEntry(entry: KeyEntry & { local: boolean }) {
  const [editing, setEditing] = useState(false)
  if (editing) return <KeyField {...entry} onDone={() => setEditing(false)} />
  // A key another profile saved for this service is used as it is; typing one is only for a different key.
  const borrowed = !!entry.reused && !entry.saved
  const others = entry.sharedWith.join(', ')
  const value = borrowed ? `From ${entry.reused}` : entry.saved ? (others ? `Shared with ${others}` : 'Saved') : 'None saved'
  const action = borrowed ? 'Use a different key' : entry.saved ? 'Replace key' : 'Add API key'
  return <div className="row-list key-row"><SettingRow label="API key" tip={entry.local ? 'Local servers can leave this empty, and an environment variable such as OPENAI_API_KEY also works.' : undefined}>
    {id => <><span className="row-value">{value}</span><button id={id} type="button" className="button" onClick={() => setEditing(true)}>{action}</button></>}
  </SettingRow></div>
}

function KeyField({ saved, reused, sharedWith, value, onChange, share, onShare, onDone }: KeyEntry & { onDone: () => void }) {
  const others = sharedWith.join(', ')
  return <div className="token-entry"><TextInput label="API key" type="password" value={value} onChange={onChange} maxLength={4000} tip="Saved in your system keychain. It is never shown again." />
    {/* A replaced key does every job that shared it, so a rotated key keeps them all working; unticked, only this profile changes. */}
    {saved && others && <label className="checkbox-row"><input type="checkbox" checked={share} onChange={(event) => onShare(event.target.checked)} />Also use it for {others}</label>}
    <button type="button" className="text-button" onClick={() => { onChange(''); onShare(true); onDone() }}>{reused && !saved ? `Use the ${reused} key` : 'Cancel key entry'}</button></div>
}

/** "16K context · 800 reply", or "16K · 800" on a phone (Iris), with the full line as its title. */
function GenerationValue({ config }: { config: ProfileConfig }) {
  const full = generationSummary(config)
  return <span title={full}><span className="wide-only">{full}</span><span className="narrow-only" aria-label={full}>{generationShort(config)}</span></span>
}
