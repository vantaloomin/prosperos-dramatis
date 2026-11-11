// Written by scripts/screen_types.py from dramatis/character.py. Do not edit: change dramatis/character.py and run it again.

export type App = 'companion' | 'adventure' | 'dungeon'
export type Gender = 'woman' | 'man' | 'nonbinary' | ''
export type Trait = 'social' | 'warmth' | 'order' | 'curiosity' | 'stress'
export type Relationship = 'friendship' | 'romance' | 'mentor' | 'family' | 'other' | 'persona'
export type LooksField = 'height_cm' | 'weight_kg' | 'build' | 'skin' | 'face' | 'jaw' | 'nose' | 'eyes' | 'eye_shape' | 'hair' | 'facial_hair' | 'feature'
export type BlockKind = 'work' | 'study' | 'errand' | 'leisure' | 'social' | 'rest' | 'sleep'

export interface Character {
  name: string
  gender: Gender
  age: number | null
  kind: string
  lifespan: number | null
  birthday: string
  setting: string
  about: string
  personality: string
  voice: string
  sound: string
  appearance: string
  background: string
  wants: string
  fears: string
  skills: string[]
  flaws: string[]
  interests: string[]
  looks: Looks
  looks_from: Partial<Record<LooksField, 'idea' | 'rolled'>>
  personality_sliders: Partial<Record<Trait, Slider>> | null
  seen_as: string
  sees_self: string
  apps: App[]
  companion: CompanionLife
  interview: string
  arc: Arc
  secret: Secret
  psyche: Psyche | null
  card: CardParts | null
  ignored_flags: string[]
  written: string[]
}

/** Face, height, build and the rest, so every picture shows the same person; an empty field is drawn by the app. */
export interface Looks {
  height_cm: number | null
  weight_kg: number | null
  build: string
  skin: string
  face: string
  jaw: string
  nose: string
  eyes: string
  eye_shape: string
  hair: string
  facial_hair: string
  feature: string
}

export interface Slider {
  level: number
  source: 'rolled' | 'idea' | 'you'
}

/** What only Prospero's Companion reads: how they know the user and the everyday life it simulates. A persona has neither, so for one only the relationship counts. */
export interface CompanionLife {
  relationship: Relationship
  starting_closeness: number
  history_together: string
  routine: string
  schedule: Block[]
  life_themes: string[]
  texting: Texting
  emotional_traits: EmotionalTrait[]
  absence_reaction: string
  timezone: string
}

/** Their inner arc, for writers and for Adventure and Dungeon stories; the draft fills it only when asked for. */
export interface Arc {
  lie: string
  truth: string
  catalyst: string
}

/** Something they keep from most people. The library always keeps it; a card carries it only when included. */
export interface Secret {
  truth: string
  cover_story: string
  known_by: string
}

/** Their inner square (the Cast spec's package B): four pulls on one person. */
export interface Psyche {
  was: Impulse
  expected: Impulse
  wants_to_be: Impulse
  fears_becoming: Impulse
}

/** What the card they came from had that Dramatis doesn't make, kept as it was ({{char}} and {{user}} included) for the cards they export: a chat app gets its greetings, lorebook and its own extensions back. */
export interface CardParts {
  source: string
  first_mes: string
  alternate_greetings: string[]
  mes_example: string
  scenario: string
  creator_notes: string
  system_prompt: string
  post_history_instructions: string
  creator: string
  character_version: string
  tags: string[]
  character_book: Record<string, unknown> | null
  extensions: Record<string, unknown>
}

/** One recurring part of the companion's day, in the companion's timezone (PRD T2). */
export interface Block {
  key: string
  label: string
  kind: BlockKind
  days: number[]
  start: string
  end: string
  themes: string[]
}

export interface Texting {
  bursts: boolean
  lowercase: boolean
  typos: boolean
  quick: boolean
}

export interface EmotionalTrait {
  name: string
  intensity: 'mild' | 'moderate' | 'strong'
  note: string
}

export interface Impulse {
  text: string
  pressed_by: string[]
}
