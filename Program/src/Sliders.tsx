import { useEffect, useRef, useState } from 'react'
import { Dices, X } from 'lucide-react'
import { sendJson, type Character, type Slider, type SliderView, type Trait } from './api'

const SOURCE_NAMES = { rolled: 'Rolled', idea: 'From their words', you: 'Set by you' }

/** The five personality sliders, settled by Companion's own rules on the server: what the user set, then what the
 * character's words say ("shy", "kind"), then rolled from the form's seed. Roll again changes only the Rolled ones.
 * Type shows the four-letter type they read as; typing one sets four sliders from it. A character brought from another
 * app is `still`: what their words don't settle stays In between, unrolled, until Roll again. */
export function Sliders({ character, words, seed, still, onChange }: {
  character: () => Character; words: string; seed: string; still?: boolean; onChange: (sliders: Record<Trait, Slider>) => void
}) {
  const [view, setView] = useState<SliderView | null>(null)
  const [roll, setRoll] = useState(0)
  // What the user is typing into Type; null shows the type the sliders read as.
  const [type, setType] = useState<string | null>(null)
  const [error, setError] = useState('')
  const ask = async (body: { roll?: number; type?: string; sliders?: Record<string, Slider> | null }) => {
    setError('')
    try {
      const current = character()
      const found = await sendJson<SliderView>('/api/sliders', 'POST', {
        character: { ...current, personality_sliders: body.sliders === undefined ? current.personality_sliders : body.sliders },
        seed, roll: body.roll ?? 0, type: body.type ?? '', still: !!still,
      })
      setView(found)
      onChange(found.sliders)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The sliders could not be set.')
    }
  }
  // Settled when the form opens, and again a moment after the words they read change (About them, Personality, How
  // they talk, Flaws), so what is saved is what opening them settles: a saved character never opens changed.
  const opened = useRef(true)
  useEffect(() => { void ask({}) }, [seed])  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (opened.current) { opened.current = false; return }
    const timer = setTimeout(() => void ask({}), 600)
    return () => clearTimeout(timer)
  }, [words])  // eslint-disable-line react-hooks/exhaustive-deps
  if (!view) return error ? <p className="error small">{error}</p> : null
  const set = (key: Trait, level: number) => void ask({ sliders: { ...view.sliders, [key]: { level, source: 'you' } } })
  const handBack = (key: Trait) => {
    const rest = { ...view.sliders }
    delete rest[key]
    void ask({ sliders: rest })
  }
  return (
    <div className="sliders">
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
            <span className="muted small">{trait.shows[current.level]} {!(still && !roll && current.source === 'rolled') && <em>({SOURCE_NAMES[current.source]})</em>}
              {current.source === 'you' && <button type="button" className="icon" aria-label={`Hand ${trait.name} back to the roll`} onClick={() => handBack(trait.key)}><X size={12} /></button>}
            </span>
          </div>
        )
      })}
      <div className="row">
        <button type="button" onClick={() => { const next = roll + 1; setRoll(next); void ask({ roll: next }) }}><Dices size={14} aria-hidden /> Roll again</button>
        <label className="type-label" htmlFor="slider-type">Type</label>
        <input id="slider-type" className="type" maxLength={4} value={type ?? view.type ?? ''} onBlur={() => setType(null)}
          onChange={(event) => {
            const typed = event.target.value.toUpperCase().replace(/[^A-Z]/g, '')
            setType(typed)
            if (typed.length === 4) void ask({ type: typed }).then(() => setType(null))
          }} />
      </div>
      {error && <p className="error small" role="alert">{error}</p>}
    </div>
  )
}
