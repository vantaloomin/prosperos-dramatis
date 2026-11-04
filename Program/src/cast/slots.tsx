/** Where the AI actions go (package D: Suggest corners, Check my square, Find the turn, Suggest a relationship). The board
 * renders each slot in its place; until D fills them they render nothing. A slot proposes changes through `update`, and
 * nothing is saved until the author saves the cast. */
import type { Cast, Corner, Resonance } from '../castApi'

export interface SlotProps { cast: Cast; update: (change: (cast: Cast) => Cast) => void }

/** The board header: Suggest corners for the outer square. */
export function HeaderActions(_: SlotProps) { return null }

/** An outer card's actions: Suggest corners for the inner square under it. */
export function SideActions(_: SlotProps & { side: Corner }) { return null }

/** The checks strip: Check my square. */
export function ChecksActions(_: SlotProps) { return null }

/** The panel of a confirmed resonance link: Find the turn. */
export function ResonanceActions(_: SlotProps & { link: Resonance }) { return null }

/** A relationship row: Suggest, when its texts are empty. */
export function RelationshipActions(_: SlotProps & { index: number }) { return null }
