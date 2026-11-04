import type { Arc, Secret } from './api'
import { Fold, TextArea } from './Fields'

/** Their inner arc. Who they could become (Psyche.tsx) sits beside it. */
export function InnerLife({ arc, onChange }: { arc: Arc; onChange: (arc: Arc) => void }) {
  const set = (change: Partial<Arc>) => onChange({ ...arc, ...change })
  return (
    <Fold title="Inner life" filled={!!(arc.lie || arc.truth || arc.catalyst)}>
      <div className="grid three">
        <TextArea name="arc.lie" label="Lie they believe" write="the lie they believe" value={arc.lie} onChange={(lie) => set({ lie })} maxLength={300} rows={3} />
        <TextArea name="arc.truth" label="Truth they need" write="the truth they need" value={arc.truth} onChange={(truth) => set({ truth })} maxLength={300} rows={3} />
        <TextArea name="arc.catalyst" label="What could force it" write="what could force it" value={arc.catalyst} onChange={(catalyst) => set({ catalyst })} maxLength={300} rows={3} />
      </div>
    </Fold>
  )
}

/** Something they keep from most people. It goes with them into every card and app, so they know what they are
 * keeping. */
export function SecretSection({ secret, onChange }: { secret: Secret; onChange: (secret: Secret) => void }) {
  const set = (change: Partial<Secret>) => onChange({ ...secret, ...change })
  return (
    <Fold title="Secret" filled={!!(secret.truth || secret.cover_story || secret.known_by)}>
      <TextArea name="secret.truth" label="What's really true" write="their secret" value={secret.truth} onChange={(truth) => set({ truth })} maxLength={600} rows={3} />
      <div className="grid two">
        <TextArea name="secret.cover_story" label="What people believe instead" write="what people believe instead" value={secret.cover_story} onChange={(cover_story) => set({ cover_story })} maxLength={400} rows={2} />
        <TextArea name="secret.known_by" label="Who knows" write="who knows" value={secret.known_by} onChange={(known_by) => set({ known_by })} maxLength={200} rows={2} />
      </div>
    </Fold>
  )
}
