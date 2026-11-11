import { useRef } from 'react'
import { CheckCircle2, Download, TriangleAlert } from 'lucide-react'
import { APPS, APP_NAMES, type App, type Problems } from '../api'

/** Where a card can go: `prospero` keeps everything for Companion, Adventure and Dungeon; `chat` is the card for other
 * chat apps, without what only the Prospero apps use (dramatis/cards.py). */
export const CARD_TARGETS: { target: 'prospero' | 'chat'; name: string; leaves?: string }[] = [
  { target: 'prospero', name: 'Prospero apps' },
  { target: 'chat', name: 'SillyTavern, Marinara, Front Porch and other chat apps', leaves: 'Leaves out what only the Prospero apps use, like the schedule and sliders.' },
]

/** The card in either kind, from the form's header. */
export function ExportCard({ id }: { id: string }) {
  const menu = useRef<HTMLDetailsElement>(null)
  const close = () => { if (menu.current) menu.current.open = false }
  return (
    <details className="export" ref={menu}>
      <summary className="button"><Download size={14} aria-hidden /> Export card</summary>
      <ul>
        {CARD_TARGETS.map(({ target, name, leaves }) => (
          <li key={target}>
            <span>{name}</span>
            {leaves && <span className="muted small">{leaves}</span>}
            <span className="row">
              {(['png', 'json'] as const).map((kind) => (
                <a key={kind} className="button" href={`/api/characters/${id}/card.${kind}?for=${target}`} download onClick={close}
                  aria-label={`${kind.toUpperCase()} for ${name}`}>{kind.toUpperCase()}</a>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

/** Which apps take them as they stand, by each app's own models, or what an app would refuse. */
export function WorksIn({ apps, problems, error, saved }: { apps: App[]; problems: Problems; error: string; saved: boolean }) {
  return (
    <div className="works-in" aria-live="polite">
      {error ? <p className="error small"><TriangleAlert size={14} aria-hidden /> {error}</p> : APPS.filter((app) => apps.includes(app)).map((app) => {
        const found = problems[app]
        return found?.length
          ? <details key={app} className="error small"><summary><TriangleAlert size={14} aria-hidden /> {APP_NAMES[app]} would refuse this</summary><ul>{found.map((problem) => <li key={problem}>{problem}</li>)}</ul></details>
          : <span key={app} className="ok small"><CheckCircle2 size={14} aria-hidden /> Works in {APP_NAMES[app]}</span>
      })}
      {!saved && <span className="muted small">Save them to export a card.</span>}
    </div>
  )
}
