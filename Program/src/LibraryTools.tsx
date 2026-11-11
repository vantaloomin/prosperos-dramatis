import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ArchiveRestore, Download } from 'lucide-react'
import { fileData, sendJson } from './api'
import { listed } from './Start'

interface Restored { characters: number; casts: number; kept: number; skipped: number }

const count = (number: number, one: string, many: string) => `${number} ${number === 1 ? one : many}`

/** What a backup brought back, in a sentence. */
export function restoredLine(found: Restored): string {
  const added = [found.characters && count(found.characters, 'character', 'characters'), found.casts && count(found.casts, 'cast', 'casts')].filter(Boolean) as string[]
  return [
    added.length ? `Brought back ${listed(added)}.` : 'Nothing to bring back.',
    found.kept ? `${found.kept} already here ${found.kept === 1 ? 'was' : 'were'} left as ${found.kept === 1 ? 'it is' : 'they are'}.` : '',
    found.skipped ? `${count(found.skipped, 'file', 'files')} couldn't be read.` : '',
  ].filter(Boolean).join(' ')
}

/** Under the library: the whole library and its casts as one file, and one brought back. Nothing already here is
 * written over (dramatis/library_tools.py). */
export function LibraryTools() {
  const client = useQueryClient()
  const picker = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [said, setSaid] = useState<{ tone: 'note' | 'error'; text: string } | null>(null)
  const bring = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setSaid(null)
    try {
      const found = await sendJson<Restored>('/api/library/backup', 'POST', { filename: file.name, data: await fileData(file) })
      await Promise.all([client.invalidateQueries({ queryKey: ['characters'] }), client.invalidateQueries({ queryKey: ['casts'] })])
      setSaid({ tone: 'note', text: restoredLine(found) })
    } catch (failure) {
      setSaid({ tone: 'error', text: failure instanceof Error ? failure.message : 'That backup could not be brought back.' })
    } finally {
      setBusy(false)
      if (picker.current) picker.current.value = ''
    }
  }
  return (
    <div className="library-tools">
      <div className="row">
        <a className="button quiet" href="/api/library/backup.zip" download><Download size={14} aria-hidden /> Back up</a>
        <button type="button" className="quiet" disabled={busy} onClick={() => picker.current?.click()}>
          <ArchiveRestore size={14} aria-hidden /> {busy ? 'Bringing back…' : 'Bring back a backup'}
        </button>
        <input ref={picker} type="file" accept=".zip" hidden aria-label="Backup file" onChange={(event) => void bring(event.target.files?.[0])} />
      </div>
      {said && <p className={`${said.tone} small`} role="status">{said.text}</p>}
    </div>
  )
}
