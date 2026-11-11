"""Every field of the character form, defined once: its key (dotted for the parts inside the character, `arc.lie`), the
label the form shows, where it sits in the character, the form's section, and the words Help me write and a list's Add
button use. Each limit is read from the Pydantic model (dramatis/character.py), never typed again.

The server reads it for the audit's labels (dramatis/slop.py), the drafts' limits (dramatis/drafting.py), the
assistant (dramatis/assistant.py) and the importer; the screen gets the same table as `src/generated/fields.ts`, which
`scripts/screen_types.py` writes from it (with the character's TypeScript types), and a test fails when that file is
out of date. A new field is one more `Spec` here, after it is in the model.
"""
import types
import typing
from dataclasses import dataclass
from functools import cache

from annotated_types import MaxLen
from pydantic import BaseModel

from dramatis.character import Character

# The form's sections, in its order.
SECTIONS = ('who', 'comes_across', 'story', 'looks', 'depth', 'companion')


@dataclass(frozen=True)
class Spec:
    key: str
    label: str
    section: str
    path: tuple[str, ...] = ()
    write: str = ''  # what Help me write calls it ("their personality"); empty when it has no Help me write
    add: str = ''    # a list's Add button
    # Which reading of it the audit and the model calls make: `core` for the character's own text, `life` for
    # Companion's, `depth` for their arc, secret and psyche; empty for a field no model writes.
    group: str = ''

    def at(self) -> tuple[str, ...]:
        return self.path or (self.key,)


def life(key: str, label: str, **more) -> Spec:
    return Spec(key, label, 'companion', ('companion', key), **more)


def depth(key: str, label: str, write: str) -> Spec:
    outer, inner = key.split('.')
    return Spec(key, label, 'depth', (outer, inner, 'text') if outer == 'psyche' else (outer, inner), write,
                group='depth')


def look(key: str, label: str) -> Spec:
    return Spec(f'looks.{key}', label, 'looks', ('looks', key))


SPECS = (
    Spec('name', 'Name', 'who', group='core'),
    Spec('gender', 'Gender', 'who'),
    Spec('age', 'Age', 'who'),
    Spec('setting', 'Where and when', 'who'),
    Spec('kind', 'Kind, if not human', 'who'),
    Spec('lifespan', 'How long they live', 'who'),
    Spec('birthday', 'Birthday', 'who'),
    Spec('about', 'About them', 'who', write='about them', group='core'),
    Spec('personality', 'Personality', 'who', write='their personality', group='core'),
    Spec('voice', 'How they talk', 'who', write='how they talk', group='core'),
    Spec('sound', 'How they sound aloud', 'who', write='how they sound aloud', group='core'),
    Spec('seen_as', 'How others see them', 'comes_across', write='how others see them', group='core'),
    Spec('sees_self', 'How they see themselves', 'comes_across', write='how they see themselves', group='core'),
    Spec('background', 'Background', 'story', write='their background', group='core'),
    Spec('wants', 'What they want', 'story', write='what they want', group='core'),
    Spec('fears', 'What they fear', 'story', write='what they fear', group='core'),
    Spec('skills', 'Skills', 'story', write='skills', add='Add a skill', group='core'),
    Spec('flaws', 'Flaws', 'story', write='flaws', add='Add a flaw', group='core'),
    Spec('interests', 'Interests', 'story', write='interests', add='Add an interest', group='core'),
    Spec('appearance', 'Appearance', 'looks', write='their appearance', group='core'),
    look('height_cm', 'Height (cm)'),
    look('weight_kg', 'Weight (kg)'),
    look('build', 'Build'),
    look('skin', 'Skin'),
    look('face', 'Face'),
    look('jaw', 'Jaw'),
    look('nose', 'Nose'),
    look('eyes', 'Eyes'),
    look('eye_shape', 'Eye shape'),
    look('hair', 'Hair'),
    look('facial_hair', 'Facial hair'),
    look('feature', 'Something people notice'),
    Spec('interview', 'Interview', 'depth', group='core'),
    depth('arc.lie', 'Lie they believe', 'the lie they believe'),
    depth('arc.truth', 'Truth they need', 'the truth they need'),
    depth('arc.catalyst', 'What could force it', 'what could force it'),
    depth('secret.truth', "What's really true", 'their secret'),
    depth('secret.cover_story', 'What people believe instead', 'what people believe instead'),
    depth('secret.known_by', 'Who knows', 'who knows'),
    depth('psyche.was', 'Who they were', 'who they were'),
    depth('psyche.expected', "Who they're expected to be", "who they're expected to be"),
    depth('psyche.wants_to_be', 'Who they want to be', 'who they want to be'),
    depth('psyche.fears_becoming', 'Who they fear becoming', 'who they fear becoming'),
    life('relationship', 'Relationship'),
    life('starting_closeness', 'How close you start'),
    life('history_together', 'How you know each other', group='life'),
    life('routine', 'Their routine', write='their routine', group='life'),
    life('schedule', 'Their week', write='their week'),
    life('life_themes', 'Life themes', write='life themes', add='Add a life theme', group='life'),
    life('timezone', 'Time zone'),
    life('emotional_traits', 'Emotional edges', group='life'),
    life('absence_reaction', 'When you are away', group='life'),
)
BY_KEY = {spec.key: spec for spec in SPECS}
LABELS = {spec.key: spec.label for spec in SPECS}


def labels(group: str) -> dict[str, str]:
    return {spec.key: spec.label for spec in SPECS if spec.group == group}


def path(key: str) -> tuple[str, ...]:
    """Where a field sits in the character: arc.lie under arc, psyche.was in its text, routine under companion."""
    spec = BY_KEY.get(key)
    return spec.at() if spec else (key,)


# ---- Limits, from the model ---------------------------------------------------------------------------------------

def model_in(annotation) -> type[BaseModel]:
    """The model a field holds, through `X | None`."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for arg in typing.get_args(annotation):
        if isinstance(arg, type) and issubclass(arg, BaseModel):
            return arg
    raise TypeError(f'{annotation} holds no model.')


def max_length(metadata) -> int | None:
    return next((item.max_length for item in metadata if isinstance(item, MaxLen)), None)


@cache
def limits(key: str) -> dict[str, int]:
    """A field's limits as the model sets them: `limit` for a text (or each item of a list of texts) and `count` for a
    list's length."""
    model, *outer, last = (Character, *path(key))
    for part in outer:
        model = model_in(model.model_fields[part].annotation)
    info = model.model_fields[last]
    found = {}
    if typing.get_origin(info.annotation) is list:
        found['count'] = max_length(info.metadata)
        item = typing.get_args(info.annotation)[0]
        if typing.get_origin(item) is typing.Annotated:
            found['limit'] = max_length(sum((getattr(meta, 'metadata', []) for meta in item.__metadata__), []))
    elif info.annotation is str or (isinstance(info.annotation, types.UnionType) and str in info.annotation.__args__):
        found['limit'] = max_length(info.metadata)
    return {name: value for name, value in found.items() if value is not None}


def limit(key: str) -> int:
    return limits(key)['limit']


def text_limits(*keys: str) -> dict[str, int]:
    return {key: limit(key) for key in keys}


def list_limits(*keys: str) -> dict[str, tuple[int, int]]:
    return {key: (limits(key)['count'], limits(key)['limit']) for key in keys}


def table() -> dict[str, dict]:
    """The registry as the screen reads it: each field's label, section, limits and Help me write and Add words."""
    return {spec.key: {'label': spec.label, 'section': spec.section, **limits(spec.key),
                       **({'write': spec.write} if spec.write else {}), **({'add': spec.add} if spec.add else {})}
            for spec in SPECS}
