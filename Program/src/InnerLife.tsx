import { useState, type ReactNode } from 'react'
import type { Arc, Secret } from './api'
import { TextArea } from './Fields'

/** Editor's Help me write for one text field, or nothing when no model is set up. */
export type Help = (field: string, label: string, value: string, apply: (value: string) => void) => ReactNode

/** A folded section that starts open when it already holds something. */
export function Folded({ title, filled, children }: { title: string; filled: boolean; children: ReactNode }) {
  const [open] = useState(filled)
  return <details className="section" open={open}><summary>{title}</summary>{children}</details>
}

/** Their inner arc. The Cast layer's psyche sits beside it (Psyche.tsx). */
export function InnerLife({ arc, onChange, help }: { arc: Arc; onChange: (arc: Arc) => void; help: Help }) {
  const set = (change: Partial<Arc>) => onChange({ ...arc, ...change })
  return (
    <Folded title="Inner life" filled={!!(arc.lie || arc.truth || arc.catalyst)}>
      <div className="grid three">
        <TextArea label="Lie they believe" value={arc.lie} onChange={(lie) => set({ lie })} maxLength={300} rows={3}
          help={help('arc.lie', 'the lie they believe', arc.lie, (lie) => set({ lie }))} />
        <TextArea label="Truth they need" value={arc.truth} onChange={(truth) => set({ truth })} maxLength={300} rows={3}
          help={help('arc.truth', 'the truth they need', arc.truth, (truth) => set({ truth }))} />
        <TextArea label="What could force it" value={arc.catalyst} onChange={(catalyst) => set({ catalyst })} maxLength={300} rows={3}
          help={help('arc.catalyst', 'what could force it', arc.catalyst, (catalyst) => set({ catalyst }))} />
      </div>
    </Folded>
  )
}

/** Something they keep from most people. The library always keeps it; a card carries it only when the user ticks
 * Include their secret in the Export card menu. */
export function SecretSection({ secret, onChange, help }: { secret: Secret; onChange: (secret: Secret) => void; help: Help }) {
  const set = (change: Partial<Secret>) => onChange({ ...secret, ...change })
  return (
    <Folded title="Secret" filled={!!(secret.truth || secret.cover_story || secret.known_by)}>
      <TextArea label="What's really true" value={secret.truth} onChange={(truth) => set({ truth })} maxLength={600} rows={3}
        hint="Cards leave it out unless you tick Include their secret."
        help={help('secret.truth', 'their secret', secret.truth, (truth) => set({ truth }))} />
      <div className="grid two">
        <TextArea label="What people believe instead" value={secret.cover_story} onChange={(cover_story) => set({ cover_story })} maxLength={400} rows={2}
          help={help('secret.cover_story', 'what people believe instead', secret.cover_story, (cover_story) => set({ cover_story }))} />
        <TextArea label="Who knows" value={secret.known_by} onChange={(known_by) => set({ known_by })} maxLength={200} rows={2}
          help={help('secret.known_by', 'who knows', secret.known_by, (known_by) => set({ known_by }))} />
      </div>
    </Folded>
  )
}
