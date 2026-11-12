/** A failure the server explained: its own message, and its code (`stale`, `unreadable`, …) when it gave one. */
export class ApiError extends Error {
  constructor(message: string, readonly code: string) { super(message) }
}

/** The run a model call's signal belongs to (src/modelCall.ts): sent as X-Dramatis-Run, so the screen can ask the
 * server which step that call is at (dramatis/calls.py). */
export const runs = new WeakMap<AbortSignal, string>()

/** Calls to the local Dramatis server. Errors carry the server's own message. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const run = init?.signal ? runs.get(init.signal) : undefined
  const response = await fetch(path, run ? { ...init, headers: { ...init?.headers, 'X-Dramatis-Run': run } } : init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? 'The request was not understood.' : body.detail
    throw new ApiError(body.error ?? detail ?? `The server answered ${response.status}.`, body.code ?? '')
  }
  return body as T
}

/** A save made from `revision`: when the file changed elsewhere since (another tab), the user chooses whether to save
 * over it (dramatis/records.py). Throws a plain error when they don't. */
export async function savedOver<T>(save: (revision?: number) => Promise<T>, revision: number | undefined): Promise<T> {
  try {
    return await save(revision)
  } catch (failure) {
    if (!(failure instanceof ApiError) || failure.code !== 'stale') throw failure
    if (!window.confirm(`${failure.message} Save over it anyway?`)) throw new Error('Not saved. Discard changes to see the other version, or Save again to choose.')
    return save(undefined)
  }
}

export const getJson = <T,>(path: string) => call<T>(path)
/** `signal` lets a model call be stopped: the screen stops waiting, and what comes back later is dropped. */
export const sendJson = <T,>(path: string, method: 'POST' | 'PUT' | 'DELETE', data?: unknown, signal?: AbortSignal) =>
  call<T>(path, { method, signal, headers: { 'Content-Type': 'application/json' }, body: data === undefined ? undefined : JSON.stringify(data) })

/** Whether a failure is the user pressing Stop, which needs no message. */
export const stopped = (failure: unknown) => failure instanceof DOMException && failure.name === 'AbortError'

/** A file as base64, for the server to read (cards, portraits). */
export function fileData(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] ?? '')
    reader.onerror = () => reject(new Error('That file could not be read.'))
    reader.readAsDataURL(file)
  })
}

export type {
  App, Arc, Block, BlockKind, CardParts, Character, CompanionLife, EmotionalTrait, Gender, Impulse, Looks, LooksField, Psyche,
  Relationship, Secret, Slider, Trait,
} from './generated/character'
import type { App, CardParts, Character, Looks, Psyche, Relationship, Slider, Trait } from './generated/character'
export const APPS: App[] = ['companion', 'adventure', 'dungeon']
export const APP_NAMES: Record<App, string> = { companion: 'Companion', adventure: 'Adventure', dungeon: 'Dungeon' }
/** How they know the user in Companion. A user persona is the user themself (dramatis/character.py): Companion takes
 * them as a persona, so its everyday life is not theirs. */
export const RELATIONSHIPS: [Relationship, string][] = [['friendship', 'Friendship'], ['romance', 'Romance, only with your yes'],
  ['mentor', 'Mentor'], ['family', 'Family'], ['other', 'Something else'], ['persona', 'User persona']]
/** Where a draft's Details came from (dramatis/looks.py); a field the user sets has no mark. */
export type LooksFrom = Character['looks_from']
export type ImpulseKey = keyof Psyche
/** What the interview suggests for one field, from POST /api/draft/from-interview. */
export type ProposedField = 'voice' | 'appearance' | 'seen_as' | 'sees_self' | 'flaws' | 'interests'
export interface Suggestion { field: ProposedField; value: string | string[]; reason: string }
export interface Interviewed { interview: string; sample: string; audit: AuditHit[] }
export interface AuditHit { field: string; label: string; severity: 'hard' | 'flag'; rule: string; match: string; context: string }
export type Problems = Partial<Record<App, string[]>>
export interface Saved { id: string; created: string; updated: string; revision: number; seed: string; character: Character; portrait: boolean; problems: Problems }
export interface Summary { id: string; name: string; about: string; apps: App[]; updated: string; portrait: boolean; broken?: boolean }
/** `missing`: the fields a quick-start draft came back without after its one retry, or that a split left empty because
 * they still gave the secret away (dramatis/drafting.py). */
export interface Drafted { character: Character; seed: string; filled_in?: string[]; instructions?: string[]; missing?: string[]; shortened?: string[] }
export interface Opened { kind: 'character'; character: Character }
/** Another app's character file, read: its text for the paste box, the form filled from it (or why not), and what it
 * keeps for their cards. */
export interface OpenedFile {
  kind: 'file'; format: string; name: string; text: string; truncated: boolean; character: Character | null; refused: string
  card: CardParts | null; kept: string[]; portrait: string | null; notes: string[]; instructions: string[]
}
export interface Health { ok: boolean; name: string; version: string; notice?: string; formats: Record<App, { repo: string; commit: string }> }
export interface ImageConfig {
  kind: 'off' | 'comfyui' | 'codex' | 'hosted'; provider: string; family: string; base_url: string; model: string; has_key: boolean; ready: boolean
  families: Record<string, string>; providers: Record<string, { label: string; base_url: string }>
}
export interface ImageCheck { ok: boolean; summary: string; details: string[] }
export interface PortraitStyle { key: string; name: string }
export interface MadePortrait { image: string; prompt: string; style: string }
export interface TraitInfo { key: Trait; name: string; low: string; high: string; shows: string[] }
export interface SliderView { sliders: Record<Trait, Slider>; chips: string[]; type: string | null; traits: TraitInfo[] }

export const emptyLooks = (): Looks => ({
  height_cm: null, weight_kg: null, build: '', skin: '', face: '', jaw: '', nose: '', eyes: '', eye_shape: '', hair: '',
  facial_hair: '', feature: '',
})

export const emptyPsyche = (): Psyche => ({
  was: { text: '', pressed_by: [] }, expected: { text: '', pressed_by: [] }, wants_to_be: { text: '', pressed_by: [] },
  fears_becoming: { text: '', pressed_by: [] },
})

export function emptyCharacter(apps: App[] = APPS): Character {
  return {
    name: '', gender: '', age: null, kind: '', lifespan: null, birthday: '', setting: '', about: '', personality: '',
    voice: '', sound: '', appearance: '', background: '', wants: '', fears: '', skills: [], flaws: [], interests: [],
    looks: emptyLooks(), looks_from: {}, personality_sliders: null, seen_as: '', sees_self: '', apps,
    companion: {
      relationship: 'friendship', starting_closeness: 1, history_together: '', routine: '', schedule: [], life_themes: [],
      texting: { bursts: false, lowercase: false, typos: false, quick: false }, emotional_traits: [], absence_reaction: '',
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? '',
    },
    interview: '', arc: { lie: '', truth: '', catalyst: '' }, secret: { truth: '', cover_story: '', known_by: '' }, psyche: null,
    card: null, ignored_flags: [], written: [],
  }
}

export const cleanList = (items: string[]) => [...new Set(items.map((item) => item.trim()).filter(Boolean))]

/** The form as the server takes it: lists without blank lines, numbers as numbers. */
export function cleaned(character: Character): Character {
  return {
    ...character, skills: cleanList(character.skills), flaws: cleanList(character.flaws), interests: cleanList(character.interests),
    companion: {
      ...character.companion, life_themes: cleanList(character.companion.life_themes),
      emotional_traits: character.companion.emotional_traits.filter((edge) => edge.name.trim()),
    },
    card: character.card && { ...character.card, tags: cleanList(character.card.tags), alternate_greetings: character.card.alternate_greetings.filter((text) => text.trim()) },
  }
}
