// From Prospero's Companion src/features/settings/models/budgets.ts at c641bca.
import type { ProfileConfig } from './types'

// Bounded choices for a profile's budgets (Iris, #535): context size and time limit as presets, the longest reply
// as a slider. A saved or reported value that is not a preset is kept as one more choice, so nothing changes by itself.

const CONTEXTS = [8000, 16000, 32000, 64000, 128000, 200000, 1000000]
const TIMES = [120, 300, 600, 900, 1800]

/** 16000 and 16384 are both "16K"; 1,000,000 is "1M". */
export function shortTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${+(tokens / 1_000_000).toFixed(1)}M`
  return `${Math.round(tokens / 1000)}K`
}

type Choice = { value: number; label: string }

function withExtras(presets: Choice[], extras: Choice[]): Choice[] {
  const all = [...presets]
  for (const extra of extras) if (!all.some(choice => choice.value === extra.value)) all.push(extra)
  return all.sort((a, b) => a.value - b.value)
}

export function contextChoices(saved: number, reported?: number | null): Choice[] {
  // An odd value the service reported is offered as it is; a saved odd value (an older profile) stays selectable.
  const extras: Choice[] = []
  if (reported) extras.push({ value: reported, label: `${reported.toLocaleString()} (reported)` })
  extras.push({ value: saved, label: saved.toLocaleString() })
  return withExtras(CONTEXTS.map(value => ({ value, label: shortTokens(value) })), extras)
}

const minutes = (seconds: number) => seconds % 60 ? `${seconds} s` : `${seconds / 60} min`

export function timeChoices(saved: number): Choice[] {
  return withExtras(TIMES.map(value => ({ value, label: minutes(value) })), [{ value: saved, label: minutes(saved) }])
}

/** 1,000 to 32,000 in steps of 500 (a whole character is a long reply), stretched to hold a saved value outside it. */
export function replyRange(saved: number) {
  return { min: Math.min(1000, saved), max: Math.max(32000, saved), step: 500 }
}

/** The fold's summary value: "16K context · 800 reply", and the effort when one is set. */
/** The same, short for a phone: "16K · 800". */
export function generationShort(config: ProfileConfig): string {
  return `${shortTokens(config.context_tokens)} · ${config.max_output_tokens.toLocaleString()}`
}

export function generationSummary(config: ProfileConfig): string {
  const parts = [`${shortTokens(config.context_tokens)} context`, `${config.max_output_tokens.toLocaleString()} reply`]
  if (config.reasoning_effort) parts.push(`${config.reasoning_effort.charAt(0).toUpperCase()}${config.reasoning_effort.slice(1)} effort`)
  return parts.join(' · ')
}
