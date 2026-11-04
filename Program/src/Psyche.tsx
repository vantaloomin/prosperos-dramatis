import { useQuery } from '@tanstack/react-query'
import { emptyPsyche, getJson, type Impulse, type ImpulseKey, type Psyche as PsycheValue, type Summary } from './api'
import { TextArea } from './Fields'
import { Folded, type Help } from './InnerLife'

export const IMPULSES: [ImpulseKey, string, string][] = [
  ['was', 'Who they were', 'who they were'], ['expected', "Who they're expected to be", "who they're expected to be"],
  ['wants_to_be', 'Who they want to be', 'who they want to be'], ['fears_becoming', 'Who they fear becoming', 'who they fear becoming'],
]
const MOST_PRESSING = 6

/** Their inner square: four pulls on them, each pressed by other characters in the library. An empty one is saved as
 * null by the server. */
export function Psyche({ psyche, selfId, onChange, help }: { psyche: PsycheValue | null; selfId?: string; onChange: (psyche: PsycheValue) => void; help: Help }) {
  const value = psyche ?? emptyPsyche()
  const set = (key: ImpulseKey, change: Partial<Impulse>) => onChange({ ...value, [key]: { ...value[key], ...change } })
  return (
    <Folded title="Inner square" filled={psyche !== null}>
      <div className="grid two">
        {IMPULSES.map(([key, label, helpLabel]) => (
          <div key={key} className="stack">
            <TextArea label={label} value={value[key].text} onChange={(text) => set(key, { text })} maxLength={300} rows={2}
              help={help(`psyche.${key}`, helpLabel, value[key].text, (text) => set(key, { text }))} />
            <PressedBy chosen={value[key].pressed_by} selfId={selfId} onChange={(pressed_by) => set(key, { pressed_by })} />
          </div>
        ))}
      </div>
    </Folded>
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
