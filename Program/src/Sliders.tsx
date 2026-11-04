import { useEffect, useState } from 'react'
import { Dices, X } from 'lucide-react'
import { sendJson, type Character, type Slider, type SliderView, type Trait } from './api'

const SOURCE_NAMES = { rolled: 'Rolled', idea: 'From their words', you: 'Set by you' }

/** The five personality sliders, settled by Companion's own rules on the server: what the user set, then what the
 * character's words say ("shy", "kind"), then rolled from the form's seed. Roll again changes only the Rolled ones. */
export function Sliders({ character, seed, onChange }: { character: () => Character; seed: string; onChange: (sliders: Record<Trait, Slider>) => void }) {
  const [view, setView] = useState<SliderView | null>(null)
  const [roll, setRoll] = useState(0)
  const [type, setType] = useState('')
  const [error, setError] = useState('')
  const ask = async (body: { roll?: number; type?: string; sliders?: Record<string, Slider> | null }) => {
    setError('')
    try {
      const current = character()
      const found = await sendJson<SliderView>('/api/sliders', 'POST', {
        character: { ...current, personality_sliders: body.sliders === undefined ? current.personality_sliders : body.sliders },
        seed, roll: body.roll ?? 0, type: body.type ?? '',
      })
      setView(found)
      onChange(found.sliders)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The sliders could not be set.')
    }
  }
  // Settled once when the form opens; words typed later settle a slider the next time they are asked for.
  useEffect(() => { void ask({}) }, [seed])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!view) return error ? <p className="error small">{error}</p> : null
  const set = (key: Trait, level: number) => void ask({ sliders: { ...view.sliders, [key]: { level, source: 'you' } } })
  const handBack = (key: Trait) => {
    const rest = { ...view.sliders }
    delete rest[key]
    void ask({ sliders: rest })
  }
  return (
    <div className="sliders">
      <p className="muted small">{view.chips.length ? view.chips.join(' · ') : 'In between on everything.'}{view.type && <> · reads as {view.type}</>}</p>
      {view.traits.map((trait) => {
        const current = view.sliders[trait.key]
        return (
          <div key={trait.key} className="slider">
            <span className="slider-name">{trait.name}</span>
            <div className="stops" role="radiogroup" aria-label={trait.name}>
              {[trait.low, 'In between', trait.high].map((label, level) => (
                <button key={label} type="button" role="radio" aria-checked={current.level === level} title={trait.shows[level]} onClick={() => set(trait.key, level)}>{label}</button>
              ))}
            </div>
            <span className="muted small">{trait.shows[current.level]} <em>({SOURCE_NAMES[current.source]})</em>
              {current.source === 'you' && <button type="button" className="icon" aria-label={`Hand ${trait.name} back to the roll`} onClick={() => handBack(trait.key)}><X size={12} /></button>}
            </span>
          </div>
        )
      })}
      <div className="row">
        <button type="button" onClick={() => { const next = roll + 1; setRoll(next); void ask({ roll: next }) }}><Dices size={14} aria-hidden /> Roll again</button>
        <input aria-label="Start from a four-letter type" placeholder="Start from a type (ENFJ)" maxLength={4} value={type} className="narrow"
          onChange={(event) => setType(event.target.value.toUpperCase())} />
        <button type="button" disabled={type.length !== 4} onClick={() => void ask({ type })}>Set</button>
      </div>
      {error && <p className="error small" role="alert">{error}</p>}
    </div>
  )
}
