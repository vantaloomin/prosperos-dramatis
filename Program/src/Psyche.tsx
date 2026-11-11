import { useQuery } from '@tanstack/react-query'
import { emptyPsyche, getJson, type Impulse, type ImpulseKey, type Psyche as PsycheValue, type Summary } from './api'
import { Fold, TextArea } from './Fields'
import { FIELDS } from './generated/fields'

/** The four pulls, each with its label (dramatis/fields.py). */
export const IMPULSES: [ImpulseKey, string][] = (['was', 'expected', 'wants_to_be', 'fears_becoming'] as const)
  .map((key) => [key, FIELDS[`psyche.${key}`].label])
const MOST_PRESSING = 6

/** Who they could become: four pulls on them (the Cast board calls it their inner square), each pressed by other
 * characters in the library. An empty one is saved as null by the server. */
export function Psyche({ psyche, selfId, onChange }: { psyche: PsycheValue | null; selfId?: string; onChange: (psyche: PsycheValue) => void }) {
  const value = psyche ?? emptyPsyche()
  const set = (key: ImpulseKey, change: Partial<Impulse>) => onChange({ ...value, [key]: { ...value[key], ...change } })
  return (
    <Fold title="Who they could become" filled={psyche !== null}>
      <div className="grid two">
        {IMPULSES.map(([key]) => (
          <div key={key} className="stack">
            <TextArea field={`psyche.${key}`} value={value[key].text} onChange={(text) => set(key, { text })} rows={2} />
            <PressedBy chosen={value[key].pressed_by} selfId={selfId} onChange={(pressed_by) => set(key, { pressed_by })} />
          </div>
        ))}
      </div>
    </Fold>
  )
}

/** Other characters in the library, picked by name; one no longer there can still be taken off. */
function PressedBy({ chosen, selfId, onChange }: { chosen: string[]; selfId?: string; onChange: (ids: string[]) => void }) {
  const listing = useQuery({ queryKey: ['characters'], queryFn: () => getJson<Summary[]>('/api/characters') })
  const others = (listing.data ?? []).filter((item) => item.id !== selfId)
  const gone = chosen.filter((id) => !others.some((item) => item.id === id))
  if (!others.length && !gone.length) return null
  const toggle = (id: string) => onChange(chosen.includes(id) ? chosen.filter((item) => item !== id) : [...chosen, id])
  return (
    <fieldset className="pressed-by">
      <legend>Pressed by</legend>
      <div className="row">
        {others.map((item) => {
          const on = chosen.includes(item.id)
          return <button key={item.id} type="button" className="chip" aria-pressed={on} disabled={!on && chosen.length >= MOST_PRESSING} onClick={() => toggle(item.id)}>{item.name}</button>
        })}
        {gone.map((id) => <button key={id} type="button" className="chip" aria-pressed onClick={() => toggle(id)}>Not in the library</button>)}
      </div>
    </fieldset>
  )
}
