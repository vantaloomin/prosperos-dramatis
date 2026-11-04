/** Where the AI actions sit on the board (CastAi.tsx): Suggest corners in the header and on a split side's card, Check my
 * square in the checks strip, Find the turn on a confirmed link, and Suggest on an empty relationship row. Without a
 * model set up, the header offers Set up a text model and the rest render nothing, as Help me write does on the form.
 * A slot proposes changes through `update`, and nothing is saved until the author saves the cast. */
import { useModelReady } from '../Fields'
import type { Cast, CastCheck, Corner, Resonance, TagInfo } from '../castApi'
import { CheckSquare, FindTurn, SetUpModel, SuggestCorners, SuggestRelationship } from './CastAi'

export interface SlotProps { cast: Cast; update: (change: (cast: Cast) => Cast) => void }

/** The board header: Suggest corners for the outer square. */
export function HeaderActions({ cast, update, tags }: SlotProps & { tags: TagInfo[] }) {
  return useModelReady() ? <SuggestCorners cast={cast} update={update} target="outer" tags={tags} /> : <SetUpModel />
}

/** An outer card's actions: Suggest corners for the inner square under it, once it is split. */
export function SideActions({ cast, update, side, tags }: SlotProps & { side: Corner; tags: TagInfo[] }) {
  const ready = useModelReady()
  return ready && side.inner ? <SuggestCorners cast={cast} update={update} target={side.id} tags={tags} compact /> : null
}

/** The checks strip: Check my square. */
export function ChecksActions({ cast, lit, onLight }: SlotProps & { lit: CastCheck | null; onLight: (check: CastCheck | null) => void }) {
  return useModelReady() ? <CheckSquare cast={cast} lit={lit} onLight={onLight} /> : null
}

/** The panel of a confirmed resonance link: Find the turn. */
export function ResonanceActions({ cast, update, link }: SlotProps & { link: Resonance }) {
  return useModelReady() ? <FindTurn key={`${link.a}~${link.b}~${link.on}`} cast={cast} update={update} link={link} /> : null
}

/** A relationship row: Suggest, while its texts are empty. */
export function RelationshipActions({ cast, update, index }: SlotProps & { index: number }) {
  return useModelReady() ? <SuggestRelationship cast={cast} update={update} index={index} /> : null
}
