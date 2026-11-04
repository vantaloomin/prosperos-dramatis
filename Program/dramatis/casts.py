"""Casts: a story's people laid out as a two-layer four-corner opposition, saved beside the character library.

A cast has an outer square (the sides and why each fights) and, under up to two of its corners, an inner square (people
who share that side's why and fight over how). Corners carry tags for their how; two corners on different sides that
share a tag are a resonance candidate, a likely defector, double agent, bridge or mirror. The author confirms or
dismisses each candidate. Relationships between the cast's characters, a theme question and the template picks
(dramatis/data/cast_*.json) complete it.

A cast refers to characters by library id and never copies them. The structural rules below are the only hard errors;
everything `checks` finds is a soft warning with a reason and a fix, and nothing here calls a model.

On disk: <Dramatis home>/casts/<id>.json, {"id", "created", "updated", "cast"}, written whole like the library.
"""
import json
import re
import secrets
from functools import cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator

from dramatis import library, settings
from dramatis.character import Input
from dramatis.formats.companion.errors import DomainError, require

DATA = Path(__file__).resolve().parent / 'data'
AxisKind = Literal['value', 'means', 'cost', 'purity', 'leadership', 'secret', 'goal-definition', 'dilemma']
CornerId = Annotated[str, Field(pattern=r'^[a-z0-9-]{1,24}$')]
Tag = Annotated[str, Field(pattern=r'^[a-z0-9-]{1,30}$')]
Severity = Literal['warn', 'info']
# Past these, a cast has more people than a story can give room to (soft warning only).
MOST_FULL_SPLITS = 2
MOST_CHARACTERS = 12
# Words that say "how" without saying anything, dropped before two stances are compared.
FILLER = {'by', 'through', 'with'}


class Axis(Input):
    kind: AxisKind
    label: str = Field(default='', max_length=120)  # 'How to keep order'; for a dilemma, the dilemma question


class Corner(Input):
    id: CornerId  # unique across the whole cast
    label: str = Field(default='', max_length=80)  # 'The Order', 'Pragmatist'
    stance: str = Field(default='', max_length=200)  # outer: the why; inner: the how
    tags: list[Tag] = Field(default_factory=list, max_length=6)
    role: str = Field(default='', max_length=30)  # template role: 'zealot', 'main', 'challenger' ...
    fields: dict[str, Annotated[str, Field(max_length=300)]] = {}  # role-specific texts (the web template's)
    character_id: str | None = None
    note: str = Field(default='', max_length=600)
    depth: Literal['single', 'partial', 'full'] = 'single'  # outer corners only
    inner: 'Square | None' = None  # outer corners only

    @model_validator(mode='after')
    def depth_fits(self):
        wanted = {'single': (0, 0), 'partial': (2, 2), 'full': (3, 4)}[self.depth]
        found = len(self.inner.corners) if self.inner else 0
        if not wanted[0] <= found <= wanted[1]:
            shape = {'single': 'no inner square', 'partial': 'an inner square of 2 corners',
                     'full': 'an inner square of 3 or 4 corners'}[self.depth]
            raise ValueError(f'{name_of(self)} is {self.depth}, so it needs {shape}.')
        return self


class Square(Input):
    axis: Axis
    question: str = Field(default='', max_length=300)  # how this square asks the theme, smaller
    corners: list[Corner] = Field(min_length=2, max_length=4)


class Resonance(Input):
    a: CornerId
    b: CornerId
    on: Tag  # the shared how
    role: Literal['defector', 'double-agent', 'bridge', 'mirror', ''] = ''
    status: Literal['confirmed', 'dismissed']
    note: str = Field(default='', max_length=400)


class Relationship(Input):
    """How one character sees another (directed: `from` about `to`), in the shape the WriteforMe spec agreed."""
    model_config = ConfigDict(populate_by_name=True)
    from_id: str = Field(alias='from')
    to_id: str = Field(alias='to')
    dynamic: str = Field(default='', max_length=300)  # how `from` sees `to`
    hidden_tension: str = Field(default='', max_length=300)
    trust: int = Field(default=5, ge=1, le=10)
    notes: str = Field(default='', max_length=600)

    @model_validator(mode='after')
    def not_themself(self):
        if self.from_id == self.to_id:
            raise ValueError('A relationship is between two different characters.')
        return self


class Cast(Input):
    title: str = Field(default='', max_length=120)
    theme: str = Field(default='', max_length=300)
    genre: str = ''  # id from cast_genres.json, or ''
    group: str = ''  # id from cast_groups.json, or ''
    outer: Square
    resonance: list[Resonance] = Field(default_factory=list, max_length=40)
    relationships: list[Relationship] = Field(default_factory=list, max_length=120)
    focus_id: str | None = None  # the character whose psyche the board shows

    @field_validator('outer')
    @classmethod
    def inner_squares_fit(cls, outer: Square) -> Square:
        for side in outer.corners:
            if not side.inner:
                continue
            if side.inner.axis.kind == 'dilemma':
                raise ValueError(f'Only the outer square can be a dilemma; choose another axis for {name_of(side)}.')
            if side.inner.axis.kind == outer.axis.kind:
                raise ValueError(f"{name_of(side)}'s split fights over the same thing as the outer square "
                                 f'({outer.axis.kind}); choose another axis for it.')
            for corner in side.inner.corners:
                if corner.inner or corner.depth != 'single':
                    raise ValueError(f'{name_of(corner)} is already inside a split, so it cannot be split again.')
        return outer

    @model_validator(mode='after')
    def ids_fit(self):
        sides = side_of(self)
        seen = [corner.id for corner in corners(self)]
        twice = sorted({found for found in seen if seen.count(found) > 1})
        if twice:
            raise ValueError(f'Two corners share the id {twice[0]}; each corner needs its own.')
        for link in self.resonance:
            missing = [found for found in (link.a, link.b) if found not in sides]
            if missing:
                raise ValueError(f'A resonance link names {missing[0]}, which is not a corner on this board.')
            if sides[link.a] == sides[link.b]:
                raise ValueError('A resonance link joins corners on two different sides, not one.')
        pairs = [(found.from_id, found.to_id) for found in self.relationships]
        if len(set(pairs)) < len(pairs):
            raise ValueError('There are two relationships from one character to the same other; keep one.')
        return self


def name_of(corner: Corner) -> str:
    """A corner as a message names it: its label, else its role, else its id."""
    return corner.label or corner.role.capitalize() or f'Corner {corner.id}'


def names_of(found: list[Corner]) -> str:
    labels = [name_of(corner) for corner in found]
    return labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' and ' + labels[-1]


def corners(cast: Cast) -> list[Corner]:
    """Every corner, each outer corner followed by its inner square's."""
    return [found for side in cast.outer.corners for found in [side, *(side.inner.corners if side.inner else [])]]


def side_of(cast: Cast) -> dict[str, str]:
    """Each corner's outer side: an outer corner is its own side, and an inner corner is its outer corner's."""
    return {found.id: side.id for side in cast.outer.corners
            for found in [side, *(side.inner.corners if side.inner else [])]}


def people(cast: Cast) -> list[Corner]:
    """The corners that stand for someone: unsplit outer corners and every inner corner (a split side is a group)."""
    return [found for side in cast.outer.corners for found in (side.inner.corners if side.inner else [side])]


def linked(cast: Cast) -> list[str]:
    """Library ids linked to corners, once each, in board order."""
    return list(dict.fromkeys(found.character_id for found in corners(cast) if found.character_id))


def mentioned(cast: Cast) -> list[str]:
    """Every library id the cast names: its corners, both ends of each relationship, and the focus."""
    ends = [end for found in cast.relationships for end in (found.from_id, found.to_id)]
    return list(dict.fromkeys([*linked(cast), *ends, *([cast.focus_id] if cast.focus_id else [])]))


# ---- The template banks -------------------------------------------------------------------------------------------

@cache
def bank(name: str) -> list[dict]:
    return json.loads((DATA / f'cast_{name}.json').read_text(encoding='utf-8'))


def templates() -> dict:
    return {name: bank(name) for name in ('axes', 'genres', 'groups', 'tags')}


def genre(genre_id: str) -> dict | None:
    return next((found for found in bank('genres') if found['id'] == genre_id), None)


# ---- The computed view: resonance candidates and checks -----------------------------------------------------------

def candidates(cast: Cast) -> list[dict]:
    """Pairs of people on different sides who share a how tag, one per shared tag, leaving out any pair the author
    already confirmed or dismissed. A pair is unordered: `a` sorts before `b`."""
    sides, decided = side_of(cast), {tuple(sorted((found.a, found.b))) for found in cast.resonance}
    found = []
    everyone = people(cast)
    for index, one in enumerate(everyone):
        for other in everyone[index + 1:]:
            a, b = sorted((one, other), key=lambda corner: corner.id)
            if sides[a.id] == sides[b.id] or (a.id, b.id) in decided:
                continue
            found += [{'a': a.id, 'b': b.id, 'on': tag} for tag in sorted(set(a.tags) & set(b.tags))]
    return sorted(found, key=lambda pair: (pair['a'], pair['b'], pair['on']))


def check(code: str, severity: Severity, found: list[Corner], message: str, fix: str) -> dict:
    return {'code': code, 'severity': severity, 'corners': [corner.id for corner in found], 'message': message,
            'fix': fix}


def plain(stance: str) -> str:
    words = re.sub(r'[^\w\s-]', ' ', stance.lower()).split()
    return ' '.join(word for word in words if word not in FILLER)


def theme_checks(cast: Cast) -> list[dict]:
    found = []
    if not cast.theme:
        found.append(check('no-theme', 'warn', [], 'The cast has no theme question yet.',
                           'Write the one question the story asks, such as "Is order worth what it costs?"'))
    for side in cast.outer.corners:
        if side.inner and not side.inner.question:
            found.append(check('no-theme-tie', 'warn', [side], f"{name_of(side)}'s split doesn't say how it asks "
                               'the theme.', f'Write the smaller question the people of {name_of(side)} fight over.'))
    return found


def stance_checks(cast: Cast) -> list[dict]:
    found = []
    blank = [corner for corner in corners(cast) if not corner.stance]
    if blank:
        found.append(check('blank-stance', 'warn', blank, f'{names_of(blank)} {"has" if len(blank) == 1 else "have"}'
                           ' no stance yet.', 'Give each a stance: for a side, why it fights; inside a split, how.'))
    squares = [(cast.outer, False), *((side.inner, True) for side in cast.outer.corners if side.inner)]
    for square, inner in squares:
        for index, one in enumerate(square.corners):
            for other in square.corners[index + 1:]:
                same_tags = inner and one.tags and set(one.tags) == set(other.tags)
                same_words = plain(one.stance) and plain(one.stance) == plain(other.stance)
                if inner and (same_tags or same_words):
                    found.append(check('duplicate-how', 'warn', [one, other], f'{names_of([one, other])} fight the '
                                       'same way.', 'Give one of them a different how, or merge them.'))
                elif not inner and same_words:
                    found.append(check('duplicate-why', 'warn', [one, other], f'{names_of([one, other])} stand for '
                                       'the same thing.', 'Give one of them a different why, or merge them.'))
    return found


def size_checks(cast: Cast) -> list[dict]:
    found = []
    full = [side for side in cast.outer.corners if side.depth == 'full']
    if len(full) > MOST_FULL_SPLITS:
        found.append(check('cast-bloat', 'warn', full, f'{names_of(full)} are all split four ways, which is more '
                           'people than most stories can follow.', 'Make one of them a split in two, or a single '
                           'corner.'))
    count = len(linked(cast))
    if count > MOST_CHARACTERS:
        found.append(check('cast-bloat', 'warn', [], f'{count} characters are linked; past {MOST_CHARACTERS}, '
                           'some will have nothing to do.', 'Merge two corners, or leave a corner as a group.'))
    return found


def character_checks(cast: Cast, names: dict[str, str]) -> list[dict]:
    found = []
    gone = [corner for corner in corners(cast) if corner.character_id and corner.character_id not in names]
    if gone:
        found.append(check('missing-character', 'warn', gone, f"{names_of(gone)}'s character is no longer in the "
                           'library.', 'Link someone else, or draft a new character for it.'))
    rows = [row for row in cast.relationships if row.from_id not in names or row.to_id not in names]
    if rows:
        found.append(check('missing-character', 'warn', [], f'{len(rows)} relationship{"s name" if len(rows) > 1 else
                           " names"} a character who is no longer in the library.', 'Remove the row, or link the '
                           'character again.'))
    open_corners = [corner for corner in people(cast) if not corner.character_id]
    if open_corners:
        found.append(check('unlinked', 'info', open_corners, f'No character yet for {names_of(open_corners)}.',
                           'Link a character from the library, or draft one for the corner.'))
    return found


def by_role(cast: Cast, role: str) -> list[Corner]:
    return [corner for corner in corners(cast) if corner.role == role]


def template_checks(cast: Cast) -> list[dict]:
    """The rules the cast's genre lists. Judgement calls are reminders (info); the model-backed versions are later."""
    template = genre(cast.genre) or {}
    found = []
    for code in template.get('checks', []):
        if code == 'role-fields':
            for corner in [corner for side in template.get('outer', []) for corner in by_role(cast, side.get('role'))]:
                wanted = next(side['fields'] for side in template['outer'] if side.get('role') == corner.role)
                empty = [field.replace('_', ' ') for field in wanted if not corner.fields.get(field)]
                if empty:
                    found.append(check(code, 'warn', [corner], f'{name_of(corner)} has nothing yet for '
                                       f'{" or ".join(empty)}.', 'Fill in what the template asks of this corner.'))
        elif code in REMINDERS:
            role, message, fix = REMINDERS[code]
            named = by_role(cast, role) if role else [side for side in cast.outer.corners
                                                     if side.inner and side.inner.axis.kind == 'secret']
            if named:
                found.append(check(code, 'info', named, message.format(names_of(named)), fix))
    return found


REMINDERS = {
    'challenger-has-flaw': ('challenger', '{} should be tempting, and still have a real flaw.',
                            'Make sure their way of living costs them something too.'),
    'comforter-not-villain': ('comforter', '{} agrees with the hero; that should feel safe, not sinister.',
                              'Keep the trap in what they share, not in a hidden bad intent.'),
    'warning-sympathetic': ('warning', '{} should be someone the reader feels for, not a cautionary cartoon.',
                            'Show how they got there one reasonable step at a time.'),
    'secret-differs': ('', 'In {}, everyone should share the motive and hide something different.',
                       'Check that no two people there are hiding the same thing.'),
}


def known_names(cast: Cast) -> dict[str, str]:
    """Names of the characters the cast names that are still in the library."""
    names = {}
    for character_id in mentioned(cast):
        try:
            names[character_id] = library.get(character_id)['character'].get('name') or 'Unnamed'
        except (DomainError, OSError, ValueError, KeyError):
            continue
    return names


def computed(cast: Cast) -> dict:
    names = known_names(cast)
    checks = [*theme_checks(cast), *stance_checks(cast), *size_checks(cast), *character_checks(cast, names),
              *template_checks(cast)]
    return {'candidates': candidates(cast), 'checks': checks, 'names': names}


def checked(raw: dict) -> Cast:
    """A cast from the board, or a plain error naming where it breaks a structural rule."""
    try:
        return Cast.model_validate(raw)
    except ValidationError as error:
        first = error.errors()[0]
        where = '.'.join(map(str, first['loc'])) or 'cast'
        message = first['msg'].removeprefix('Value error, ')
        raise DomainError(f'{where}: {message}' if first['loc'] else message, 422, 'invalid_cast') from error


# ---- The store ----------------------------------------------------------------------------------------------------

def folder() -> Path:
    return settings.home() / 'casts'


def path_of(cast_id: str) -> Path:
    require(cast_id.isalnum() and len(cast_id) <= 40, 'That is not a cast in this library.', 404)
    return folder() / f'{cast_id}.json'


def dumped(cast: Cast) -> dict:
    return cast.model_dump(by_alias=True)


def listing() -> list[dict]:
    found = []
    for path in folder().glob('*.json') if folder().is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            cast = Cast.model_validate(record['cast'])
        except (OSError, ValueError, KeyError):
            continue
        found.append({'id': record['id'], 'title': cast.title, 'theme': cast.theme, 'updated': record['updated'],
                      'characters': len(linked(cast))})
    return sorted(found, key=lambda record: record['updated'], reverse=True)


def get(cast_id: str) -> dict:
    path = path_of(cast_id)
    if not path.is_file():
        raise DomainError('That cast is not in this library any more.', 404)
    return json.loads(path.read_text(encoding='utf-8'))


def save(cast: Cast, cast_id: str | None = None) -> dict:
    """A new cast, or a new version of one already here."""
    if cast_id:
        record = get(cast_id) | {'cast': dumped(cast), 'updated': library.now()}
    else:
        stamp = library.now()
        record = {'id': secrets.token_hex(library.ID_LENGTH // 2), 'created': stamp, 'updated': stamp,
                  'cast': dumped(cast)}
    library.write(path_of(record['id']), (json.dumps(record, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    return get(record['id'])


def delete(cast_id: str):
    get(cast_id)
    path_of(cast_id).unlink(missing_ok=True)


def export(cast_id: str) -> dict:
    """The cast and the full record of every character it names that is still in the library, for other apps."""
    cast = checked(get(cast_id)['cast'])
    characters = {}
    for character_id in mentioned(cast):
        try:
            characters[character_id] = library.get(character_id)['character']
        except (DomainError, OSError, ValueError):
            continue
    return {'format': 'prospero-cast', 'version': 1, 'cast': dumped(cast), 'characters': characters}


Corner.model_rebuild()
