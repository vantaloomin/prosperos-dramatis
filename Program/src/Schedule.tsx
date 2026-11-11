import { Plus, Trash2 } from 'lucide-react'
import type { Block, BlockKind } from './api'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const KINDS: BlockKind[] = ['work', 'study', 'errand', 'leisure', 'social', 'rest', 'sleep']
const KIND_NAMES: Record<BlockKind, string> = { work: 'Work', study: 'Study', errand: 'Errands', leisure: 'Leisure', social: 'Social', rest: 'Rest', sleep: 'Sleep' }

/** Problems Companion would refuse, or that would leave its life simulation without a night's sleep. */
export function scheduleProblems(blocks: Block[]): string[] {
  const found: string[] = []
  blocks.forEach((block, index) => {
    const name = block.label.trim() || `Block ${index + 1}`
    if (!block.label.trim()) found.push(`${name} needs a name.`)
    if (!block.days.length) found.push(`${name} needs at least one day.`)
    if (block.start === block.end) found.push(`${name} starts and ends at the same time.`)
  })
  const slept = new Set(blocks.filter((block) => block.kind === 'sleep').flatMap((block) => block.days))
  if (blocks.length && slept.size < 7) found.push('Companion needs a sleep block on every day.')
  return found
}

/** Their week for Companion's life simulation: recurring blocks in their local time. */
export function Schedule({ blocks, onChange }: { blocks: Block[]; onChange: (blocks: Block[]) => void }) {
  const change = (index: number, patch: Partial<Block>) => onChange(blocks.map((block, at) => at === index ? { ...block, ...patch } : block))
  const toggleDay = (index: number, day: number) => {
    const days = blocks[index].days
    change(index, { days: days.includes(day) ? days.filter((item) => item !== day) : [...days, day].sort() })
  }
  const problems = scheduleProblems(blocks)
  return (
    <div className="schedule">
      {!blocks.length && <p className="muted small">No week yet. Companion gives them one that fits their job when they arrive.</p>}
      {blocks.map((block, index) => (
        <div key={index} className="block">
          <input aria-label="What it is" value={block.label} maxLength={120} onChange={(event) => change(index, { label: event.target.value })} />
          <select aria-label="Kind" value={block.kind} onChange={(event) => change(index, { kind: event.target.value as BlockKind })}>
            {KINDS.map((kind) => <option key={kind} value={kind}>{KIND_NAMES[kind]}</option>)}
          </select>
          <input aria-label="Starts" type="time" value={block.start} onChange={(event) => change(index, { start: event.target.value })} />
          <input aria-label="Ends" type="time" value={block.end} onChange={(event) => change(index, { end: event.target.value })} />
          <span className="days" role="group" aria-label="Days">
            {DAYS.map((day, number) => (
              <button key={day} type="button" className="chip" aria-pressed={block.days.includes(number)} onClick={() => toggleDay(index, number)}>{day}</button>
            ))}
          </span>
          <button type="button" className="icon" aria-label={`Remove ${block.label || 'this block'}`} onClick={() => onChange(blocks.filter((_, at) => at !== index))}><Trash2 size={14} /></button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...blocks, { key: '', label: '', kind: 'leisure', days: [0, 1, 2, 3, 4], start: '18:00', end: '19:00', themes: [] }])}><Plus size={14} aria-hidden /> Add a block</button>
      {problems.length > 0 && <ul className="error small">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul>}
    </div>
  )
}
