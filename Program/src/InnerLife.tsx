import type { Arc, Secret } from './api'
import { Fold, TextArea } from './Fields'

/** Their inner arc. Who they could become (Psyche.tsx) sits beside it. */
export function InnerLife({ arc, onChange }: { arc: Arc; onChange: (arc: Arc) => void }) {
  const set = (change: Partial<Arc>) => onChange({ ...arc, ...change })
  return (
    <Fold title="Inner life" filled={!!(arc.lie || arc.truth || arc.catalyst)}>
      <div className="grid three">
        <TextArea field="arc.lie" value={arc.lie} onChange={(lie) => set({ lie })} rows={3} />
        <TextArea field="arc.truth" value={arc.truth} onChange={(truth) => set({ truth })} rows={3} />
        <TextArea field="arc.catalyst" value={arc.catalyst} onChange={(catalyst) => set({ catalyst })} rows={3} />
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
      <TextArea field="secret.truth" value={secret.truth} onChange={(truth) => set({ truth })} rows={3} />
      <div className="grid two">
        <TextArea field="secret.cover_story" value={secret.cover_story} onChange={(cover_story) => set({ cover_story })} rows={2} />
        <TextArea field="secret.known_by" value={secret.known_by} onChange={(known_by) => set({ known_by })} rows={2} />
      </div>
    </Fold>
  )
}
