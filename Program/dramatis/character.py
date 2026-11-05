"""A Dramatis character: one person, written once, that each Prospero app can take in its own shape.

The shared part is who they are, which every app reads: name, gender, age and kind, About them, personality, voice,
look, background, wants and fears, skills, flaws and interests, the five personality sliders, Looks, and how they
come across, and how their voice sounds for text to speech. `companion` holds what only Prospero's Companion uses: how
they know the user and the everyday life its simulation runs (routine, weekly schedule, life themes, texting habits,
emotional edges).

A character whose relationship is `persona` is the user themself, someone to play as rather than someone to talk to.
Companion takes them as a persona (its PersonaInput, companion/worlds.py) instead of a companion, so none of its
everyday life applies; Adventure and Dungeon already take every character as the player's persona.

Their depth is optional and no app has a field for it yet: an in-voice `interview`, an inner `arc` (the lie they
believe, the truth they need, what could force it), a `secret`, and a `psyche` (who they were, are expected to be,
want to be and fear becoming, each with the characters who press on it). The whole character rides in a card's
extension; the app shapes fold the parts each app can use into fields it already reads (`folded`), the secret
included, so the character knows what they are keeping.

`card` holds what a card they were imported from carries that Dramatis doesn't make (its greetings, example
messages, scenario, notes, prompts, tags, lorebook and other apps' extensions, dramatis/imports.py), as the card had
it, so their exported cards give it back. No app shape and no model prompt reads it.

Each field's limit is the tightest of the apps that read it, so nothing is cut short on the way in. `for_companion`,
`for_adventure` and `for_dungeon` lay a character out as each app's own request models expect, and check it with
those models (vendored in dramatis/formats by scripts/sync_format.py), so a character Dramatis accepts loads in each
app unchanged. Each app fills in what is left empty its own way (Looks from its banks, a name that fits its world).
"""
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from dramatis.formats.adventure import models as adventure
from dramatis.formats.companion import models as companion
from dramatis.formats.dungeon import models as dungeon

APPS = ('companion', 'adventure', 'dungeon')
App = Literal['companion', 'adventure', 'dungeon']
Gender = Literal['woman', 'man', 'nonbinary', '']
Trait = Literal['social', 'warmth', 'order', 'curiosity', 'stress']
# How long they live, as Adventure and Dungeon offer it (their models' LIFESPANS); 0 is "Doesn't age".
LIFESPANS = (0, 80, 150, 300, 600, 1000)
OLDEST = 5000
# Past this, Companion reads the age from their words rather than their Looks (its Looks stop at 120).
COMPANION_OLDEST = 120
# Companion's background and both apps' sees_self limits, which the folded depth must fit inside.
BACKGROUND, SEES_SELF = 12000, 1200
PRONOUNS = {'woman': 'she', 'man': 'he', 'nonbinary': 'they'}
ListItem = Annotated[str, Field(max_length=300)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Slider(Input):
    level: int = Field(ge=0, le=2)
    source: Literal['rolled', 'idea', 'you'] = 'rolled'


class Looks(Input):
    """Face, height, build and the rest, so every picture shows the same person; an empty field is drawn by the app."""
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=35, le=250)
    build: str = Field(default='', max_length=120)
    skin: str = Field(default='', max_length=120)
    face: str = Field(default='', max_length=120)
    jaw: str = Field(default='', max_length=120)
    nose: str = Field(default='', max_length=120)
    eyes: str = Field(default='', max_length=120)
    eye_shape: str = Field(default='', max_length=120)
    hair: str = Field(default='', max_length=200)
    facial_hair: str = Field(default='', max_length=120)
    feature: str = Field(default='', max_length=200)


class EmotionalTrait(Input):
    name: str = Field(min_length=1, max_length=60)
    intensity: Literal['mild', 'moderate', 'strong'] = 'mild'
    note: str = Field(default='', max_length=500)


class Texting(Input):
    bursts: bool = False
    lowercase: bool = False
    typos: bool = False
    quick: bool = False


Relationship = Literal['friendship', 'romance', 'mentor', 'family', 'other', 'persona']
# They are the user: Companion's own Relationship has no such value, because there a persona is not a companion.
PERSONA = 'persona'


class CompanionLife(Input):
    """What only Prospero's Companion reads: how they know the user and the everyday life it simulates. A persona has
    neither, so for one only the relationship counts."""
    relationship: Relationship = 'friendship'
    starting_closeness: int = Field(default=1, ge=1, le=5)
    history_together: str = Field(default='', max_length=2000)
    routine: str = Field(default='', max_length=8000)
    # Weekly blocks, checked block by block with Companion's own RoutineBlock.
    schedule: list[dict] = Field(default_factory=list, max_length=24)
    life_themes: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=20)
    texting: Texting = Field(default_factory=Texting)
    emotional_traits: list[EmotionalTrait] = Field(default_factory=list, max_length=12)
    absence_reaction: str = Field(default='', max_length=2000)
    timezone: str = Field(default='', max_length=64)

    @field_validator('schedule')
    @classmethod
    def blocks(cls, value: list[dict]) -> list[dict]:
        return [companion.RoutineBlock.model_validate(item).model_dump() for item in value]


class Arc(Input):
    """Their inner arc, for writers and for Adventure and Dungeon stories; the draft fills it only when asked for."""
    lie: str = Field(default='', max_length=300)       # what they believe that holds them back, in plain words
    truth: str = Field(default='', max_length=300)     # what they would need to learn
    catalyst: str = Field(default='', max_length=300)  # the kind of event or person that could force it


class Secret(Input):
    """Something they keep from most people. The library always keeps it; a card carries it only when included."""
    truth: str = Field(default='', max_length=600)        # what is really so
    cover_story: str = Field(default='', max_length=400)  # what people believe instead
    known_by: str = Field(default='', max_length=200)     # who knows, in words ("only her sister")


class Impulse(Input):
    text: str = Field(default='', max_length=300)
    # Library ids of the characters who press on it; set on the form, never by a model, and kept out of app shapes.
    pressed_by: list[str] = Field(default_factory=list, max_length=6)


class Psyche(Input):
    """Their inner square (the Cast spec's package B): four pulls on one person."""
    was: Impulse = Field(default_factory=Impulse)
    expected: Impulse = Field(default_factory=Impulse)
    wants_to_be: Impulse = Field(default_factory=Impulse)
    fears_becoming: Impulse = Field(default_factory=Impulse)

    def empty(self) -> bool:
        return not any(impulse.text or impulse.pressed_by for impulse in (self.was, self.expected, self.wants_to_be,
                                                                          self.fears_becoming))


# A card's own text parts (Character Card V3 sets no limits; these are roomy), and its lorebook and extensions together.
CARD_TEXT, CARD_DATA = 40000, 4_000_000
CardText = Annotated[str, Field(max_length=CARD_TEXT)]


class CardParts(Input):
    """What the card they came from had that Dramatis doesn't make, kept as it was ({{char}} and {{user}} included)
    for the cards they export: a chat app gets its greetings, lorebook and its own extensions back."""
    source: str = Field(default='', max_length=120)  # the kind of file it came from, "Backyard Archive (BYAF)"
    first_mes: CardText = ''
    alternate_greetings: list[CardText] = Field(default_factory=list, max_length=64)
    mes_example: CardText = ''
    scenario: CardText = ''
    creator_notes: CardText = ''
    system_prompt: CardText = ''
    post_history_instructions: CardText = ''
    creator: str = Field(default='', max_length=200)
    character_version: str = Field(default='', max_length=60)
    tags: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=64)
    character_book: dict | None = None
    # Other apps' own extensions (SillyTavern's, Front Porch's); never `prospero`, which each export writes afresh.
    extensions: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def fits(self):
        self.extensions.pop('prospero', None)
        if len(json.dumps([self.character_book, self.extensions], ensure_ascii=False)) > CARD_DATA:
            raise ValueError("The card's lorebook and extensions are too large to keep.")
        return self

    def empty(self) -> bool:
        return not any(value for key, value in self.model_dump().items() if key != 'source')


class Character(Input):
    name: str = Field(default='', max_length=80)
    gender: Gender = ''
    age: int | None = Field(default=None, ge=18, le=OLDEST)
    # The kind of person they are ('elf'), empty for an ordinary human or to read it from their words.
    kind: str = Field(default='', max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = None
    birthday: str = Field(default='', pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')
    # Where and when they come from, in the user's words ("Baltimore, today", "a frontier town in 1870").
    setting: str = Field(default='', max_length=200)
    about: str = Field(default='', max_length=2000)
    personality: str = Field(default='', max_length=8000)
    # How they talk: their words, rhythm, humour and what they avoid saying, as instructions for writing them.
    voice: str = Field(default='', max_length=600)
    # How they sound: the physical voice for text to speech (age, pitch, pace, texture), never personality or their
    # name. Kept apart from `voice` so neither the user nor a model mixes the two.
    sound: str = Field(default='', max_length=300)
    appearance: str = Field(default='', max_length=600)
    background: str = Field(default='', max_length=12000)
    wants: str = Field(default='', max_length=300)
    fears: str = Field(default='', max_length=300)
    skills: list[ListItem] = Field(default_factory=list, max_length=20)
    flaws: list[ListItem] = Field(default_factory=list, max_length=20)
    interests: list[Annotated[str, Field(max_length=120)]] = Field(default_factory=list, max_length=50)
    looks: Looks = Field(default_factory=Looks)
    personality_sliders: dict[Trait, Slider] | None = None
    seen_as: str = Field(default='', max_length=400)
    sees_self: str = Field(default='', max_length=1200)
    # Which apps they are made for: what the form shows, and which drafting asks for. Exports carry every app's shape.
    apps: list[App] = Field(default_factory=lambda: list(APPS), min_length=1, max_length=3)
    companion: CompanionLife = Field(default_factory=CompanionLife)
    # The in-voice interview: their answers to about 14 questions, as Markdown (dramatis/interview.py).
    interview: str = Field(default='', max_length=16000)
    arc: Arc = Field(default_factory=Arc)
    secret: Secret = Field(default_factory=Secret)
    psyche: Psyche | None = None
    card: CardParts | None = None

    @field_validator('lifespan')
    @classmethod
    def listed(cls, value):
        if value not in (None, *LIFESPANS):
            raise ValueError("Pick one of the lifespans listed, or Doesn't age.")
        return value

    @field_validator('apps')
    @classmethod
    def distinct(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator('psyche')
    @classmethod
    def no_empty_psyche(cls, value: Psyche | None) -> Psyche | None:
        return None if value is None or value.empty() else value

    @field_validator('card')
    @classmethod
    def no_empty_card(cls, value: CardParts | None) -> CardParts | None:
        return None if value is None or value.empty() else value

    def is_persona(self) -> bool:
        return self.companion.relationship == PERSONA


# Each app's own shape ---------------------------------------------------------------------------------------------

def folded(own: str, extras: list[str], limit: int, between: str) -> str:
    """Their own text, then each extra that has text, in order. Past the app's limit, extras go from last to first;
    their own text is never cut (its limit is already the app's)."""
    kept = [extra for extra in extras if extra]
    while kept and len(between.join([own, *kept] if own else kept)) > limit:
        kept.pop()
    return between.join([own, *kept] if own else kept)


def sentence(text: str) -> str:
    return text.rstrip().rstrip('.') + '.' if text.strip() else ''


def secret_text(secret: Secret) -> str:
    """The secret in one paragraph: what is true, what people believe instead and who knows."""
    parts = [sentence(secret.truth)]
    parts += [f'{label} {sentence(text)}' for label, text in (('What people believe instead:', secret.cover_story),
                                                              ('Who knows:', secret.known_by)) if text]
    return ' '.join(part for part in parts if part)


def arc_sentence(arc: Arc) -> str:
    """The arc as Companion reads it: "They tell themselves …; what they need to learn is …"."""
    lie, truth = arc.lie.rstrip().rstrip('.'), arc.truth.rstrip().rstrip('.')
    if lie and truth:
        return f'They tell themselves {lie}; what they need to learn is {truth}.'
    return f'They tell themselves {lie}.' if lie else f'What they need to learn is {truth}.' if truth else ''


def psyche_lines(character: Character) -> list[str]:
    """How they see themselves, from their psyche: what is expected of them, who they want to be and who they fear
    becoming, in that order."""
    psyche = character.psyche or Psyche()
    return [f'{label} {impulse.text.strip()}' if impulse.text.strip() else ''
            for label, impulse in (('People expect me to be:', psyche.expected), ('I want to be:', psyche.wants_to_be),
                                   ("I'm afraid of turning into:", psyche.fears_becoming))]


def companion_background(character: Character) -> str:
    """Companion has no Wants, Fears, arc, secret or psyche fields: they go at the end of the background, where its
    chat context reads them, as many as fit within its limit."""
    wanted = [f"{label} {sentence(text)}" for label, text in (('What they want:', character.wants),
                                                              ('What they fear:', character.fears)) if text]
    secret = secret_text(character.secret)
    was = (character.psyche.was.text.strip() if character.psyche else '')
    extras = [' '.join(wanted), arc_sentence(character.arc),
              f'Something they keep to themselves: {secret}' if secret else '',
              f'Who they were: {sentence(was)}' if was else '']
    return folded(character.background, extras, BACKGROUND, '\n\n')


def companion_sees_self(character: Character) -> str:
    return folded(character.sees_self, psyche_lines(character), SEES_SELF, '\n')


def adventure_sees_self(character: Character) -> str:
    """Adventure's private view of themselves: their own lines, then the lie they believe, their secret and
    their psyche, as many as fit."""
    secret = secret_text(character.secret)
    extras = [f'What I tell myself: {sentence(character.arc.lie)}' if character.arc.lie else '',
              f'Something I keep to myself: {secret}' if secret else '', *psyche_lines(character)]
    return folded(character.sees_self, extras, SEES_SELF, '\n')


def looks_with_age(character: Character, oldest: int) -> dict:
    looks = character.looks.model_dump()
    return looks | {'age': character.age if character.age is not None and character.age <= oldest else None}


def for_companion(character: Character) -> dict:
    """A Companion CharacterDefinition, or `{'persona': PersonaInput}` for the user's own persona. Where a companion
    lives is left to the world they move into: Companion gives them a city, a job, a home and a routine of its own when
    the routine here is empty."""
    if character.is_persona():
        return {'persona': persona(character, companion, looks=character.appearance or None)}
    life = character.companion
    definition = {
        'name': character.name, 'identity': character.about, 'personality': character.personality,
        'voice': character.voice, 'skills': character.skills, 'flaws': character.flaws,
        'interests': character.interests, 'background': companion_background(character),
        'appearance': character.appearance, 'looks': looks_with_age(character, COMPANION_OLDEST),
        'routine': life.routine, 'location': character.setting, 'relationship': life.relationship,
        'starting_closeness': life.starting_closeness, 'history_together': life.history_together,
        'seen_as': character.seen_as, 'sees_self': companion_sees_self(character),
        'absence_reaction': life.absence_reaction,
        'emotional_traits': [trait.model_dump() for trait in life.emotional_traits],
        'timezone': life.timezone or 'UTC', 'schedule': life.schedule, 'life_themes': life.life_themes,
        'texting': life.texting.model_dump(), 'birthday': character.birthday, 'kind': character.kind,
        'lifespan': character.lifespan, 'personality_sliders': sliders_of(character),
    }
    return companion.CharacterDefinition.model_validate(definition).model_dump(exclude_none=True)


def persona(character: Character, models, **more) -> dict:
    """Who they are as an app's persona: name, gender, age, About you, birthday and kind, and whatever else that app's
    PersonaInput takes (`more`, such as Companion's How you look)."""
    return models.PersonaInput.model_validate({
        'name': character.name or None, 'gender': character.gender or None, 'age': character.age,
        'about': character.about or None, 'birthday': character.birthday or None, 'kind': character.kind or None,
        'lifespan': character.lifespan, **more}).model_dump()


def for_adventure(character: Character) -> dict:
    """Adventure's persona and its made character (adventure/making.py): look, voice, wants, fears, sliders, Looks and
    how they come across."""
    made = adventure.MadeCharacter.model_validate({
        'look': character.appearance, 'voice': character.voice, 'wants': character.wants, 'fears': character.fears,
        'personality_sliders': sliders_of(character), 'looks': looks_with_age(character, adventure.PERSONA_AGES[1]),
        'seen_as': character.seen_as, 'sees_self': adventure_sees_self(character)})
    return {'persona': persona(character, adventure), 'made': made.model_dump()}


def for_dungeon(character: Character) -> dict:
    return {'persona': persona(character, dungeon)}


SHAPES = {'companion': for_companion, 'adventure': for_adventure, 'dungeon': for_dungeon}


def sliders_of(character: Character) -> dict | None:
    if not character.personality_sliders:
        return None
    return {key: value.model_dump() for key, value in character.personality_sliders.items()}


def shapes(character: Character) -> dict[str, dict]:
    """Every app's shape of the character; one an app's own models refuse is left out (see `problems`)."""
    found = {}
    for app, shape in SHAPES.items():
        try:
            found[app] = shape(character)
        except ValidationError:
            continue
    return found


def problems(character: Character) -> dict[str, list[str]]:
    """What each app's own models would refuse, in plain words, by app; empty when every app takes them."""
    found = {}
    for app, shape in SHAPES.items():
        try:
            shape(character)
        except ValidationError as error:
            found[app] = [f"{'.'.join(map(str, item['loc'])) or 'character'}: {item['msg']}" for item in error.errors()]
    return found
