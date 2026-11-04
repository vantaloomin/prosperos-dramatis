import { useEffect, useId, useState } from 'react'
import { ChevronDown, ChevronRight, Plus, Split, Undo2 } from 'lucide-react'
import {
  AXIS_KINDS, LIMITS, addInnerCorner, dropCorner, editCorner, emptyCorner, freshId, mergeSide, splitSide, words,
  type AxisInfo, type AxisKind, type Cast, type Corner, type Genre, type Group, type Square,
} from '../castApi'
import { CornerCard, type CornerContext } from './CornerCard'
import { SideActions } from './slots'

/** Whether the screen is phone-narrow, where the 2x2 becomes a list of sides. */
export function useNarrow(query = '(max-width: 720px)') {
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches)
  useEffect(() => {
    const media = window.matchMedia(query)
    const change = () => setNarrow(media.matches)
    media.addEventListener('change', change)
    return () => media.removeEventListener('change', change)
  }, [query])
  return narrow
}

interface Props {
  cast: Cast
  axes: AxisInfo[]
  genre?: Genre
  group?: Group
  context: CornerContext
  update: (change: (cast: Cast) => Cast) => void
}

const axisName = (axes: AxisInfo[], kind: AxisKind) => axes.find((item) => item.kind === kind)?.label || words(kind)
/** The kinds an inner square may take: not the outer square's own, and not one only an outer square takes (the dilemma). */
const innerKinds = (axes: AxisInfo[], outer: AxisKind, keep?: AxisKind) => AXIS_KINDS.filter((kind) =>
  kind === keep || (kind !== outer && kind !== 'dilemma' && !axes.find((item) => item.kind === kind)?.outer_only))

/** The outer square: its axis, and a card for each side, with the inner square of any side that is split. */
export function SquareView({ cast, axes, genre, group, context, update }: Props) {
  const narrow = useNarrow()
  const outer = cast.outer
  const taken = new Set(outer.corners.map((side) => side.inner?.axis.kind).filter(Boolean))
  const help = axes.find((item) => item.kind === outer.axis.kind)?.help
  const setOuter = (change: Partial<Square>) => update((current) => ({ ...current, outer: { ...current.outer, ...change } }))
  return (
    <section className="square outer-square" aria-label="Outer square">
      <AxisRow kind={outer.axis.kind} label={outer.axis.label} help={help} axes={axes} kinds={AXIS_KINDS}
        taken={taken} onChange={(axis) => setOuter({ axis: { ...outer.axis, ...axis } })} />
      <div className="sides">
        {outer.corners.map((side, index) => (
          <Side key={side.id} side={side} index={index} cast={cast} axes={axes} genre={genre} group={group} context={context} narrow={narrow} update={update} />
        ))}
      </div>
      {outer.corners.length < 4 && (
        <button type="button" className="link" onClick={() => update((current) => ({
          ...current, outer: { ...current.outer, corners: [...current.outer.corners, emptyCorner(freshId(current))] },
        }))}><Plus size={13} aria-hidden /> Add a side</button>
      )}
    </section>
  )
}

/** A square's axis: the kind of thing its corners disagree about, and in words. A dilemma names its question. */
function AxisRow({ kind, label, help, axes, kinds, taken, onChange }: {
  kind: AxisKind; label: string; help?: string; axes: AxisInfo[]; kinds: AxisKind[]; taken?: Set<AxisKind | undefined>
  onChange: (axis: { kind?: AxisKind; label?: string }) => void
}) {
  const id = useId()
  return (
    <div className="axis">
      <div className="axis-row">
        <label className="sr-only" htmlFor={`${id}-kind`}>They disagree about</label>
        <select id={`${id}-kind`} value={kind} onChange={(event) => onChange({ kind: event.target.value as AxisKind })}>
          {kinds.map((item) => <option key={item} value={item} disabled={taken?.has(item) && item !== kind}>{axisName(axes, item)}</option>)}
        </select>
        <input aria-label={kind === 'dilemma' ? 'The dilemma' : 'The axis in your words'} value={label} maxLength={LIMITS.axis}
          placeholder={kind === 'dilemma' ? 'The dilemma, as a question' : 'In your words: how to keep order'} onChange={(event) => onChange({ label: event.target.value })} />
      </div>
      {help && <span className="hint">{help}</span>}
    </div>
  )
}

function Side({ side, index, cast, axes, genre, group, context, narrow, update }: {
  side: Corner; index: number; cast: Cast; axes: AxisInfo[]; genre?: Genre; group?: Group; context: CornerContext; narrow: boolean
  update: (change: (cast: Cast) => Cast) => void
}) {
  const [open, setOpen] = useState(false)
  const [splitting, setSplitting] = useState<'full' | 'partial' | null>(null)
  const pick = genre?.outer[index]
  const change = (id: string) => (part: Partial<Corner>) => update((current) => editCorner(current, id, (corner) => ({ ...corner, ...part })))
  const suggested = genre?.split === index && !side.inner
  const body = (
    <CornerCard corner={side} outer context={context} stanceHint={pick?.stance_hint} fieldKeys={Object.keys(side.fields)} onChange={change(side.id)}
      onRemove={cast.outer.corners.length > 2 ? () => update((current) => dropCorner(current, side.id)) : undefined}
      actions={<SideActions cast={cast} update={update} side={side} />}>
      {side.inner ? <InnerSquare side={side} cast={cast} axes={axes} context={context} update={update} change={change} />
        : splitting ? <SplitPrompt cast={cast} side={side} mode={splitting} axes={axes} genre={genre} group={group} update={update} onDone={() => setSplitting(null)} />
          : (
            <div className="row split-buttons">
              <button type="button" className={suggested ? 'primary' : undefined} onClick={() => setSplitting('full')}><Split size={14} aria-hidden /> Split this side</button>
              <button type="button" onClick={() => setSplitting('partial')}>Split in two</button>
            </div>
          )}
    </CornerCard>
  )
  if (!narrow) return body
  const count = side.inner?.corners.length ?? 0
  return (
    <div className="side-fold">
      <button type="button" className="side-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={14} aria-hidden /> : <ChevronRight size={14} aria-hidden />}
        <strong>{side.label || 'Unnamed side'}</strong>
        {count > 0 && <span className="muted small">{count} corners</span>}
      </button>
      {open && body}
    </div>
  )
}

/** The first question a split asks: what the corners on this side disagree about. Labels come from the group type's roles. */
function SplitPrompt({ cast, side, mode, axes, genre, group, update, onDone }: {
  cast: Cast; side: Corner; mode: 'full' | 'partial'; axes: AxisInfo[]; genre?: Genre; group?: Group; update: (change: (cast: Cast) => Cast) => void; onDone: () => void
}) {
  const kinds = innerKinds(axes, cast.outer.axis.kind)
  const preferred = [group?.axis, genre?.axis].find((kind) => kind && kinds.includes(kind))
  const [kind, setKind] = useState<AxisKind>(preferred ?? kinds[0])
  const id = useId()
  const help = axes.find((item) => item.kind === kind)?.help
  const roles = group?.roles ?? []
  const count = mode === 'partial' ? 2 : Math.min(4, Math.max(3, roles.length || 4))
  const labels = Array.from({ length: count }, (_, n) => roles[n] ?? '')
  return (
    <div className="split-prompt">
      <label htmlFor={id}>Within {side.label || 'this side'}, they disagree about</label>
      <select id={id} value={kind} onChange={(event) => setKind(event.target.value as AxisKind)}>
        {kinds.map((item) => <option key={item} value={item}>{axisName(axes, item)}</option>)}
      </select>
      {help && <span className="hint">{help}</span>}
      <div className="row">
        <button type="button" className="primary" onClick={() => { update((current) => splitSide(current, side.id, kind, '', labels)); onDone() }}>
          Split into {count}
        </button>
        <button type="button" onClick={onDone}>Cancel</button>
      </div>
    </div>
  )
}

function InnerSquare({ side, cast, axes, context, update, change }: {
  side: Corner; cast: Cast; axes: AxisInfo[]; context: CornerContext; update: (change: (cast: Cast) => Cast) => void
  change: (id: string) => (part: Partial<Corner>) => void
}) {
  const inner = side.inner!
  const kinds = innerKinds(axes, cast.outer.axis.kind, inner.axis.kind)
  const help = axes.find((item) => item.kind === inner.axis.kind)?.help
  const setInner = (part: Partial<Square>) => change(side.id)({ inner: { ...inner, ...part } })
  const merge = () => {
    const filled = inner.corners.some((corner) => corner.stance || corner.note || corner.character_id || corner.tags.length)
    if (!filled || window.confirm(`Merge ${side.label || 'this side'} back into one corner? Its inner corners and their resonance go.`)) update((current) => mergeSide(current, side.id))
  }
  return (
    <div className="square inner-square">
      <AxisRow kind={inner.axis.kind} label={inner.axis.label} help={help} axes={axes} kinds={kinds} onChange={(axis) => setInner({ axis: { ...inner.axis, ...axis } })} />
      <input aria-label="How this side asks the theme" value={inner.question} maxLength={LIMITS.question}
        placeholder={cast.theme ? `How ${side.label || 'this side'} asks: ${cast.theme}` : 'How this side asks the theme'} onChange={(event) => setInner({ question: event.target.value })} />
      <div className="inner-corners">
        {inner.corners.map((corner) => (
          <CornerCard key={corner.id} corner={corner} outer={false} context={context} onChange={change(corner.id)}
            onRemove={inner.corners.length > 2 ? () => update((current) => dropCorner(current, corner.id)) : undefined} />
        ))}
      </div>
      <div className="row">
        {inner.corners.length < 4 && <button type="button" className="link" onClick={() => update((current) => addInnerCorner(current, side.id))}><Plus size={13} aria-hidden /> Add a corner</button>}
        <button type="button" className="link" onClick={merge}><Undo2 size={13} aria-hidden /> Merge back into one</button>
      </div>
    </div>
  )
}
