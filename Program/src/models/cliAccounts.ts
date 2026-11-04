// The Claude Code and Codex accounts found on this PC (claude, claude2, codex2…), so a profile can pick one.
// From Prospero's Companion src/features/settings/models/cliAccounts.ts at c641bca.
import { shownPath } from './ui'
import type { Provider } from './types'

export const WINDOWS = typeof navigator !== 'undefined' && /win/i.test(navigator.platform)

/** The typed account folder's example, for this computer. */
export const folderExample = (base: 'claude' | 'codex', windows = WINDOWS) => windows ? `C:\\Users\\you\\.${base}-second` : `~/.${base}-second`

export interface CliAccount { provider: Provider; account_dir: string; commands: string[]; sources: string[]; signed_in: boolean; email: string }

const plain = (folder: string) => shownPath(folder.trim()).replace(/[\\/]+$/, '').replace(/\\/g, '/').toLowerCase()

/** Whether a profile's account folder is this account ('' is the usual account), typed with ~ for the home folder or not. */
export const sameAccount = (account: CliAccount, folder: string | undefined) => plain(account.account_dir) === plain(folder ?? '')

const folderName = (folder: string) => folder.split(/[\\/]/).filter(Boolean).pop() ?? folder

/** The account's row: its command (claude2), else its folder's name. The one with no folder is the usual account. */
export const accountName = (account: CliAccount): string => account.commands[0] ?? folderName(account.account_dir)

export const isUsual = (account: CliAccount) => !account.account_dir

/** The row's quiet value: the email Claude Code reports, else whether it is signed in. */
export const accountValue = (account: CliAccount): string => !account.signed_in ? 'Not signed in' : account.email || 'Signed in'

/** How to sign in to an account that is not signed in yet, as a command for this computer's terminal: its own
 * command (claude2) when it has one, else the CLI with the account's folder set. */
export function signInStep(account: CliAccount, windows: boolean): string {
  const base = account.provider === 'codex' ? 'codex' : 'claude'
  const login = account.provider === 'codex' ? ' login' : ''
  const wrapper = account.commands.find(command => command !== base)
  if (wrapper) return wrapper + login
  if (!account.account_dir) return base + login
  const variable = account.provider === 'codex' ? 'CODEX_HOME' : 'CLAUDE_CONFIG_DIR'
  return windows ? `$env:${variable}="${account.account_dir}"; ${base}${login}` : `${variable}="${account.account_dir}" ${base}${login}`
}

/** Where a new profile starts: the usual account when it is signed in, else the first signed-in one, else the usual. */
export function startingAccount(accounts: CliAccount[]): CliAccount | undefined {
  const usual = accounts.find(account => !account.account_dir)
  if (usual?.signed_in) return usual
  return accounts.find(account => account.signed_in) ?? usual
}

export type FolderShown = 'plain' | 'open' | 'closed'

/** How the typed account folder shows: plainly when there are no accounts to pick (looking off or none found), open
 * while the folder matches none of them, and closed behind "Type an account folder instead" while one is picked. */
export function folderShown(looking: boolean, found: number, picked: boolean): FolderShown {
  if (!looking || !found) return 'plain'
  return picked ? 'closed' : 'open'
}
