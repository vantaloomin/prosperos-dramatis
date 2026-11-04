// Models: pick which Claude or ChatGPT account a Claude Code or Codex profile uses, from the accounts found on this
// PC (Companion's providers/cli_accounts.py). From Prospero's Companion src/features/settings/models/CliAccountPicker.tsx
// at c641bca; a new profile starts on a signed-in account by itself. Whether the app looks at all is one switch in
// Models (CliLookRow), since it applies to every profile; Dramatis keeps it with the profiles, not in workspace settings.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { api, FoldRow, Notice, RowGroup, shownPath, SwitchRow } from './ui'
import { type FolderShown, WINDOWS, accountName, accountValue, isUsual, folderShown, sameAccount, signInStep, startingAccount, type CliAccount } from './cliAccounts'
import type { ModelsOverview, Provider } from './types'

const KEY = ['cli-accounts']
interface Found { enabled: boolean; accounts: CliAccount[] }
interface PickerProps { provider: Provider; value?: string; fresh: boolean; onPick: (folder: string) => void; children: ReactNode }

// Each account's sign-in is asked of its CLI, which takes a moment, so the list is kept while Models is open.
const useFound = () => useQuery({ queryKey: KEY, queryFn: () => api<Found>('/models/cli-accounts'), staleTime: 5 * 60_000 })

/** `fresh` is a new profile: it moves to a signed-in account by itself when the usual one is not signed in.
 * `children` is the typed account folder, kept behind "Type an account folder instead" while a found account is picked. */
export function CliAccountPicker({ provider, value, fresh, onPick, children }: PickerProps) {
  const query = useFound()
  const mine = accountsFor(query.data, provider)
  useStartingAccount(fresh && !value?.trim(), mine, onPick)
  if (!query.data && !query.isError) return <p className="subtle">Looking for accounts on this computer…</p>
  const { enabled, chosen, shown } = picked(query.data, mine, value)
  if (!enabled) return <>{children}</>
  return <div className="cli-accounts form-stack">
    <AccountList provider={provider} accounts={mine ?? []} chosen={chosen} busy={query.isFetching} onPick={onPick} onLook={() => void query.refetch()}>
      {shown !== 'plain' && <TypedFolder shown={shown} picked={chosen?.account_dir}>{children}</TypedFolder>}
    </AccountList>
    {shown === 'plain' && children}
    <SignInNote chosen={chosen} />
  </div>
}

function picked(found: Found | undefined, mine: CliAccount[] | null, value?: string) {
  const enabled = found?.enabled ?? true
  const chosen = mine?.find(account => sameAccount(account, value))
  return { enabled, chosen, shown: folderShown(enabled, mine?.length ?? 0, !!chosen) }
}

function SignInNote({ chosen }: { chosen?: CliAccount }) {
  if (!chosen || chosen.signed_in) return null
  return <Notice>This account is not signed in. Run <code>{signInStep(chosen, WINDOWS)}</code> in a terminal and sign in, then look again.</Notice>
}

const accountsFor = (found: Found | undefined, provider: Provider) => found ? found.accounts.filter(account => account.provider === provider) : null

function useStartingAccount(open: boolean, accounts: CliAccount[] | null, onPick: (folder: string) => void) {
  const done = useRef(false)
  useEffect(() => {
    if (done.current || !open || !accounts) return
    done.current = true
    const start = startingAccount(accounts)
    if (start?.account_dir) onPick(start.account_dir)
  }, [open, accounts, onPick])
}

interface ListProps { provider: Provider; accounts: CliAccount[]; chosen?: CliAccount; busy: boolean; onPick: (folder: string) => void; onLook: () => void; children?: ReactNode }

/** The accounts as radio rows (the usual one first, as the server sorts them), Look again on the heading, and the
 * typed folder as the last row. */
function AccountList({ provider, accounts, chosen, busy, onPick, onLook, children }: ListProps) {
  const id = useId()
  return <section className="row-group cli-account-list" aria-labelledby={`${id}-label`}>
    <div className="row-group-heading">
      <h3 id={`${id}-label`} className="row-group-label">Account</h3>
      <button type="button" className="icon-button" aria-label="Look again" title="Look again" disabled={busy} onClick={onLook}><RefreshCw aria-hidden="true" /></button>
    </div>
    {accounts.length
      ? <div className="row-list" role="radiogroup" aria-labelledby={`${id}-label`}>
        {accounts.map(account => <label key={account.account_dir || 'usual'} className="setting-row radio-row" title={[account.account_dir && shownPath(account.account_dir), account.email].filter(Boolean).join(' · ') || undefined}>
          <input type="radio" name={`${id}-account`} checked={account === chosen} onChange={() => onPick(account.account_dir)} />
          <span className="setting-row-label">{accountName(account)}{isUsual(account) && <><span className="wide-only">(usual account)</span><span className="narrow-only">(usual)</span></>}</span>
          <span className="row-value">{accountValue(account)}</span>
        </label>)}
        {children}
      </div>
      : <p className="subtle">No {provider === 'codex' ? 'Codex' : 'Claude Code'} accounts found on this computer.</p>}
  </section>
}

/** Closed while a found account is picked until the user opens it, open while the folder matches none of them.
 * Picking another account closes it again. */
function TypedFolder({ shown, picked, children }: { shown: FolderShown; picked?: string; children: ReactNode }) {
  const [opened, setOpened] = useState<{ picked?: string; open: boolean }>({ open: false })
  const open = shown === 'open' || (opened.open && opened.picked === picked)
  return <FoldRow nested summary="Type an account folder instead" open={open} onToggle={next => setOpened({ picked, open: next })}>
    <div className="form-stack">{children}</div>
  </FoldRow>
}

/** On unless turned off. Off, nothing is looked for and a profile only uses a typed folder. */
export function CliLookRow({ overview }: { overview: ModelsOverview }) {
  const client = useQueryClient()
  const [error, setError] = useState('')
  const save = async (find_cli_accounts: boolean) => {
    setError('')
    try {
      client.setQueryData(['models'], await api<ModelsOverview>('/models/looking', { enabled: find_cli_accounts }, 'PUT'))
      await client.invalidateQueries({ queryKey: KEY })
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'That setting was not saved.') }
  }
  return <>
    <RowGroup>
      <SwitchRow label="Look for Claude Code and Codex accounts" checked={overview.find_cli_accounts} onChange={checked => void save(checked)}
        tip="Finds your accounts on this computer from their commands (such as claude2), your PowerShell profile and folder names, for every Claude Code and Codex profile. Sign-ins are never opened." />
    </RowGroup>
    {error && <Notice tone="error">{error}</Notice>}
  </>
}
