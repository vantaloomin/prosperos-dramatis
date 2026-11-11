import { Plus, Trash2 } from 'lucide-react'
import type { EmotionalTrait } from './api'

const INTENSITIES: [EmotionalTrait['intensity'], string][] = [['mild', 'Mild'], ['moderate', 'Moderate'], ['strong', 'Strong']]
/** As many as Companion keeps (its EmotionalTrait list, vendored models.py). */
const MOST = 12

/** Companion's emotional edges, such as jealousy or guilt over absence: each a name, how strong, and a note. A draft
 * writes them only when the user asks for edges, and every one is here to read and change before Save. */
export function EmotionalEdges({ edges, onChange }: { edges: EmotionalTrait[]; onChange: (edges: EmotionalTrait[]) => void }) {
  const change = (index: number, patch: Partial<EmotionalTrait>) => onChange(edges.map((edge, at) => at === index ? { ...edge, ...patch } : edge))
  return (
    <div className="edges">
      {edges.map((edge, index) => (
        <div key={index} className="edge">
          <div className="block">
            <input aria-label="Edge" value={edge.name} maxLength={60} placeholder="Jealousy" onChange={(event) => change(index, { name: event.target.value })} />
            <select aria-label="How strong" value={edge.intensity} onChange={(event) => change(index, { intensity: event.target.value as EmotionalTrait['intensity'] })}>
              {INTENSITIES.map(([value, name]) => <option key={value} value={value}>{name}</option>)}
            </select>
            <button type="button" className="icon" aria-label={`Remove ${edge.name || 'this edge'}`} onClick={() => onChange(edges.filter((_, at) => at !== index))}><Trash2 size={14} /></button>
          </div>
          <textarea aria-label={`${edge.name || 'Edge'}, how it shows`} rows={2} value={edge.note} maxLength={500} onChange={(event) => change(index, { note: event.target.value })} />
        </div>
      ))}
      {edges.length < MOST && (
        <button type="button" onClick={() => onChange([...edges, { name: '', intensity: 'mild', note: '' }])}><Plus size={14} aria-hidden /> Add an edge</button>
      )}
    </div>
  )
}
