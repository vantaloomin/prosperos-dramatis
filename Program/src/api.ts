/** Calls to the local Dramatis server. Errors carry the server's own message. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? 'The request was not understood.' : body.detail
    throw new Error(body.error ?? detail ?? `The server answered ${response.status}.`)
  }
  return body as T
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

export type App = 'companion' | 'adventure' | 'dungeon'
export const APPS: App[] = ['companion', 'adventure', 'dungeon']
export const APP_NAMES: Record<App, string> = { companion: 'Companion', adventure: 'Adventure', dungeon: 'Dungeon' }
export type Gender = 'woman' | 'man' | 'nonbinary' | ''
export type Relationship = 'friendship' | 'romance' | 'mentor' | 'family' | 'other' | 'persona'
/** How they know the user in Companion. A user persona is the user themself (dramatis/character.py): Companion takes
 * them as a persona, so its everyday life is not theirs. */
export const RELATIONSHIPS: [Relationship, string][] = [['friendship', 'Friendship'], ['romance', 'Romance, only with your yes'],
  ['mentor', 'Mentor'], ['family', 'Family'], ['other', 'Something else'], ['persona', 'User persona']]
export type BlockKind = 'work' | 'study' | 'errand' | 'leisure' | 'social' | 'rest' | 'sleep'

export interface Slider { level: number; source: 'rolled' | 'idea' | 'you' }
export type Trait = 'social' | 'warmth' | 'order' | 'curiosity' | 'stress'
export interface Looks {
  height_cm: number | null; weight_kg: number | null; build: string; skin: string; face: string; jaw: string; nose: string
  eyes: string; eye_shape: string; hair: string; facial_hair: string; feature: string
}
export interface Block { key?: string; label: string; kind: BlockKind; days: number[]; start: string; end: string; themes: string[] }
export interface EmotionalTrait { name: string; intensity: 'mild' | 'moderate' | 'strong'; note: string }
export interface CompanionLife {
  relationship: Relationship; starting_closeness: number; history_together: string; routine: string; schedule: Block[]
  life_themes: string[]; texting: { bursts: boolean; lowercase: boolean; typos: boolean; quick: boolean }
  emotional_traits: EmotionalTrait[]; absence_reaction: string; timezone: string
}
/** Their inner arc: the lie they believe, the truth they need, and what could force it. */
export interface Arc { lie: string; truth: string; catalyst: string }
/** Something they keep from most people; it goes with them into every card and app. */
export interface Secret { truth: string; cover_story: string; known_by: string }
/** One pull on them, and the library characters who press on it (never written by a model). */
export interface Impulse { text: string; pressed_by: string[] }
export type ImpulseKey = 'was' | 'expected' | 'wants_to_be' | 'fears_becoming'
export type Psyche = Record<ImpulseKey, Impulse>
/** What the card they were imported from had that Dramatis doesn't make, kept as it came for the cards they export. */
export interface CardParts {
  source: string; first_mes: string; alternate_greetings: string[]; mes_example: string; scenario: string; creator_notes: string
  system_prompt: string; post_history_instructions: string; creator: string; character_version: string; tags: string[]
  character_book: { entries?: unknown[] } | null; extensions: Record<string, unknown>
}
export interface Character {
  name: string; gender: Gender; age: number | null; kind: string; lifespan: number | null; birthday: string; setting: string
  about: string; personality: string; voice: string; sound: string; appearance: string; background: string; wants: string; fears: string
  skills: string[]; flaws: string[]; interests: string[]; looks: Looks
  personality_sliders: Partial<Record<Trait, Slider>> | null; seen_as: string; sees_self: string
  apps: App[]; companion: CompanionLife
  interview: string; arc: Arc; secret: Secret; psyche: Psyche | null; card: CardParts | null
}
/** What the interview suggests for one field, from POST /api/draft/from-interview. */
export type ProposedField = 'voice' | 'appearance' | 'seen_as' | 'sees_self' | 'flaws' | 'interests'
export interface Suggestion { field: ProposedField; value: string | string[]; reason: string }
export interface Interviewed { interview: string; sample: string; audit: AuditHit[] }
export interface AuditHit { field: string; label: string; severity: 'hard' | 'flag'; rule: string; match: string; context: string }
export type Problems = Partial<Record<App, string[]>>
export interface Saved { id: string; created: string; updated: string; seed: string; character: Character; portrait: boolean; problems: Problems }
export interface Summary { id: string; name: string; about: string; apps: App[]; updated: string; portrait: boolean }
export interface Drafted { character: Character; seed: string; filled_in?: string[]; instructions?: string[] }
export interface Opened { kind: 'character'; character: Character }
/** Another app's character file, read: its text for the paste box, the form filled from it (or why not), and what it
 * keeps for their cards. */
export interface OpenedFile {
  kind: 'file'; format: string; name: string; text: string; truncated: boolean; character: Character | null; refused: string
  card: CardParts | null; kept: string[]; portrait: string | null; notes: string[]; instructions: string[]
}
export interface Health { ok: boolean; name: string; version: string; formats: Record<App, { repo: string; commit: string }> }
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
    looks: emptyLooks(), personality_sliders: null, seen_as: '', sees_self: '', apps,
    companion: {
      relationship: 'friendship', starting_closeness: 1, history_together: '', routine: '', schedule: [], life_themes: [],
      texting: { bursts: false, lowercase: false, typos: false, quick: false }, emotional_traits: [], absence_reaction: '',
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone ?? '',
    },
    interview: '', arc: { lie: '', truth: '', catalyst: '' }, secret: { truth: '', cover_story: '', known_by: '' }, psyche: null,
    card: null,
  }
}

export const cleanList = (items: string[]) => [...new Set(items.map((item) => item.trim()).filter(Boolean))]

/** The form as the server takes it: lists without blank lines, numbers as numbers. */
export function cleaned(character: Character): Character {
  return {
    ...character, skills: cleanList(character.skills), flaws: cleanList(character.flaws), interests: cleanList(character.interests),
    companion: { ...character.companion, life_themes: cleanList(character.companion.life_themes) },
    card: character.card && { ...character.card, tags: cleanList(character.card.tags), alternate_greetings: character.card.alternate_greetings.filter((text) => text.trim()) },
  }
}
