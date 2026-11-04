"""A Dramatis character: one person, written once, that each Prospero app can take in its own shape.

The shared part is who they are, which every app reads: name, gender, age and kind, About them, personality, voice,
look, background, wants and fears, skills, flaws and interests, the five personality sliders, Looks, and how they
come across. `companion` holds what only Prospero's Companion uses: how they know the user and the everyday life its
simulation runs (routine, weekly schedule, life themes, texting habits, emotional edges).

Each field's limit is the tightest of the apps that read it, so nothing is cut short on the way in. `for_companion`,
`for_adventure` and `for_dungeon` lay a character out as each app's own request models expect, and check it with
those models (vendored in dramatis/formats by scripts/sync_format.py), so a character Dramatis accepts loads in each
app unchanged. Each app fills in what is left empty its own way (Looks from its banks, a name that fits its world).
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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


class CompanionLife(Input):
    """What only Prospero's Companion reads: how they know the user and the everyday life it simulates."""
    relationship: Literal['friendship', 'romance', 'mentor', 'family', 'other'] = 'friendship'
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
    voice: str = Field(default='', max_length=600)
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


# Each app's own shape ---------------------------------------------------------------------------------------------

def companion_background(character: Character) -> str:
    """Companion has no Wants or Fears: they go at the end of the background, where its chat context reads them."""
    extra = [f"{label} {text.rstrip('.')}." for label, text in (('What they want:', character.wants),
                                                               ('What they fear:', character.fears)) if text]
    text = '\n\n'.join(part for part in (character.background, ' '.join(extra)) if part)
    return text[:12000]


def looks_with_age(character: Character, oldest: int) -> dict:
    looks = character.looks.model_dump()
    return looks | {'age': character.age if character.age is not None and character.age <= oldest else None}


def for_companion(character: Character) -> dict:
    """A Companion CharacterDefinition. Where they live is left to the world they move into: Companion gives them a
    city, a job, a home and a routine of its own when the routine here is empty."""
    life = character.companion
    definition = {
        'name': character.name, 'identity': character.about, 'personality': character.personality,
        'voice': character.voice, 'skills': character.skills, 'flaws': character.flaws,
        'interests': character.interests, 'background': companion_background(character),
        'appearance': character.appearance, 'looks': looks_with_age(character, COMPANION_OLDEST),
        'routine': life.routine, 'location': character.setting, 'relationship': life.relationship,
        'starting_closeness': life.starting_closeness, 'history_together': life.history_together,
        'seen_as': character.seen_as, 'sees_self': character.sees_self, 'absence_reaction': life.absence_reaction,
        'emotional_traits': [trait.model_dump() for trait in life.emotional_traits],
        'timezone': life.timezone or 'UTC', 'schedule': life.schedule, 'life_themes': life.life_themes,
        'texting': life.texting.model_dump(), 'birthday': character.birthday, 'kind': character.kind,
        'lifespan': character.lifespan, 'personality_sliders': sliders_of(character),
    }
    return companion.CharacterDefinition.model_validate(definition).model_dump(exclude_none=True)


def persona(character: Character, models) -> dict:
    """Who they are in Adventure or Dungeon: the persona's name, gender, age, About you, birthday and kind."""
    return models.PersonaInput.model_validate({
        'name': character.name or None, 'gender': character.gender or None, 'age': character.age,
        'about': character.about or None, 'birthday': character.birthday or None, 'kind': character.kind or None,
        'lifespan': character.lifespan}).model_dump()


def for_adventure(character: Character) -> dict:
    """Adventure's persona and its made character (adventure/making.py): look, voice, wants, fears, sliders, Looks and
    how they come across."""
    made = adventure.MadeCharacter.model_validate({
        'look': character.appearance, 'voice': character.voice, 'wants': character.wants, 'fears': character.fears,
        'personality_sliders': sliders_of(character), 'looks': looks_with_age(character, adventure.PERSONA_AGES[1]),
        'seen_as': character.seen_as, 'sees_self': character.sees_self})
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
