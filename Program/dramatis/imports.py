"""Bring a character from another app in to edit it. The file is read with Prospero's Companion's own character importer
(companion/imports/formats.py, vendored with its card reader and lorebooks), so Dramatis opens what Companion opens:
Character Cards V1 to V3 as JSON or PNG (SillyTavern, Chub, Agnai, RisuAI and most card sites), CHARX, Backyard Archive
(BYAF), Marinara Engine's own export, and Pygmalion and Backyard / Faraday JSON. A plain JSON object that is none of
those, a blurb such as {"name": "Mira", "age": 31, "likes": ["ferries"]}, is read here key by key.

What comes back is for the user to choose from, and nothing is saved:

- `text`: the character as headed text for the paste box, which the user reads before Split into fields sends it to
  their model. The split is the Paste path, unchanged (dramatis/drafting.py `split`): a minor refused in code first,
  the text inside markers it cannot close, lines that talk to the app or the model named back.
- `character`: the form filled straight from the file with no model (Open as the file has it). Headed lines ("Age:
  34", "How they talk: ...", the headings of Dramatis' own chat cards among them) go to their fields, and the rest of
  a description is their Background. The Paste path's safeguards come first: a text that makes them younger than 18,
  or an Appearance with a child's look, is `refused` instead, and the lines that talk to the app or the model are
  named in `instructions`. A headed Secret goes to their secret and nowhere else, cut short rather than spilled.
- `card`: what the file has that Dramatis doesn't make (greetings, example messages, scenario, notes, prompts, tags,
  lorebook, other apps' extensions), as it came, for the cards they export (dramatis/character.py `CardParts`),
  whichever way the form is filled. No model sees it.
- `portrait`: the file's picture as a PNG without the card inside it, for the form to save with them.

A Prospero card Dramatis made comes back whole from its extension (`kind: character`). No script or macro runs, nothing
is fetched and no model is asked.
"""
import base64
import io
import json
import re
from pathlib import PureWindowsPath

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from dramatis import adults, asking, cards, drafting, fields, library
from dramatis.character import CARD_DATA, CARD_TEXT, CardParts, Character, Looks
from dramatis.formats.companion.errors import DomainError
from dramatis.formats.companion.imports import cards as reader
from dramatis.formats.companion.imports import formats, lorebooks

BLURB = 'JSON'
LIMITS = fields.text_limits(*drafting.TEXT_LIMITS, 'setting', 'arc.lie', 'arc.truth')
# The headings and keys that name a field, by the field (dotted for their arc) they fill. Dramatis' own card headings
# (cards.description) come first in each.
FIELD_NAMES = {
    'name': ('name', 'char name', 'character name', 'display name', 'full name'),
    'gender': ('gender', 'sex'),
    'age': ('age',),
    'kind': ('kind', 'species', 'race'),
    'setting': ('from', 'setting', 'origin', 'where and when', 'world'),
    'birthday': ('birthday', 'date of birth', 'birth date'),
    'about': ('about', 'about them', 'summary', 'overview', 'bio', 'identity', 'concept'),
    'description': ('description', 'char persona', 'persona', 'ai persona'),
    'personality': ('personality', 'temperament', 'personality traits', 'traits'),
    'appearance': ('appearance', 'physical appearance', 'physical description', 'body'),
    'looks': ('looks',),
    'voice': ('how they talk', 'voice', 'speech', 'speech style', 'speaking style', 'way of speaking'),
    'sound': ('how they sound',),
    'background': ('background', 'backstory', 'history', 'biography', 'past'),
    'wants': ('wants', 'what they want', 'goals', 'goal', 'desires', 'motivation', 'motivations'),
    'fears': ('fears', 'what they fear', 'fear'),
    'skills': ('skills', 'abilities', 'talents'),
    'flaws': ('flaws', 'weaknesses'),
    'interests': ('interests', 'likes', 'hobbies'),
    'seen_as': ('how others see them', 'outward appearance', 'reputation'),
    'sees_self': ('how they see themselves', 'self image'),
    'arc.lie': ('lie they believe',),
    'arc.truth': ('truth they need',),
    'secret': ('secret', 'secrets'),
}
LABELS = {name: field for field, names in FIELD_NAMES.items() for name in names}
# A blurb's keys for the parts of a card Dramatis keeps as they are.
PART_NAMES = {'scenario': 'scenario', 'world scenario': 'scenario', 'first mes': 'first_mes',
              'first message': 'first_mes', 'greeting': 'first_mes', 'char greeting': 'first_mes',
              'alternate greetings': 'alternate_greetings', 'mes example': 'mes_example',
              'example dialogue': 'mes_example', 'example messages': 'mes_example', 'creator notes': 'creator_notes',
              'system prompt': 'system_prompt', 'post history instructions': 'post_history_instructions',
              'tags': 'tags', 'creator': 'creator', 'character version': 'character_version'}
LISTED = ('alternate_greetings', 'tags')
# The kept parts, as the note names them.
KEPT = (('first_mes', 'first message'), ('alternate_greetings', 'other greetings'),
        ('mes_example', 'example messages'), ('scenario', 'scenario'), ('creator_notes', "creator's notes"),
        ('system_prompt', 'system prompt'), ('post_history_instructions', 'instructions after the chat'),
        ('tags', 'tags'), ('character_book', 'lorebook'), ('extensions', "other apps' settings"))
GENDER_WORDS = {'woman': 'woman', 'female': 'woman', 'f': 'woman', 'she': 'woman', 'man': 'man', 'male': 'man',
                'm': 'man', 'he': 'man', 'nonbinary': 'nonbinary', 'non binary': 'nonbinary', 'enby': 'nonbinary',
                'they': 'nonbinary'}
MONTHS = {month.lower(): number for number, month in enumerate(cards.MONTHS, 1)}
LOOKS = {label.lower(): key for key, label, _ in cards.LOOKS}
HEAD = re.compile(r"^\s*(?:[-*•]\s*)?\[?(?P<label>[A-Za-z][A-Za-z '’/-]{0,40}?)\]?\s*:\s*(?P<rest>.*)$")
SECRET_PARTS = re.compile(r'\s*(What people believe instead|Who knows):\s*', re.IGNORECASE)
MACROS = ((re.compile(r'\{\{char\}\}|<BOT>', re.IGNORECASE), None),
          (re.compile(r'\{\{user\}\}|<USER>', re.IGNORECASE), 'the user'))
YOUTHFUL_TEXT = ('Characters are always adults, and their appearance gives them a younger look ({found}). Change it in '
                 'the text, or start from the quick start.')


def label_key(label: str) -> str:
    """A heading or key as the tables spell it: "speechStyle", "speech_style" and "Speech style" are one."""
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', label)
    return re.sub(r'[^a-z]+', ' ', spaced.lower()).strip()


def spelled(text: str, name: str) -> str:
    """{{char}} and {{user}} as the person reading the form would say them."""
    for macro, value in MACROS:
        text = macro.sub(value or name or 'they', text)
    return text.strip()


def headed(text: str) -> tuple[str, list[tuple[str, str]]]:
    """A text's lead (what comes before its first heading that names a field) and its headed sections, in order. A
    line that starts with a heading no field has ("Note: ...") stays part of the section it is in."""
    lead, found = [], []
    for line in text.splitlines():
        match = HEAD.match(line)
        if match and label_key(match['label']) in LABELS:
            found.append((match['label'].strip(), [match['rest']]))
        elif found:
            found[-1][1].append(line)
        else:
            lead.append(line)
    return '\n'.join(lead).strip(), [(label, '\n'.join(lines).strip()) for label, lines in found]


def items_of(value) -> list[str]:
    """A list's items, from a JSON list or a line of them ("a; b; c", bullet lines, or "a, b, c")."""
    if isinstance(value, list):
        return [shown(item) for item in value if shown(item)]
    text = str(value)
    lines = [re.sub(r'^\s*[-*•]\s*', '', line).strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    splitter = ';' if ';' in text else ','
    return [item.strip() for item in text.split(splitter) if item.strip()]


def shown(value) -> str:
    """Any JSON value as text: a list one item a line, an object one "Key: value" a line."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool) or value is None:
        return ''
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        return '\n'.join(f'- {text}' for text in map(shown, value) if text)
    if isinstance(value, dict):
        return '\n'.join(f'{humanized(key)}: {text}' for key, item in value.items() if (text := shown(item)))
    return ''


def humanized(key: str) -> str:
    words = label_key(key)
    return words[:1].upper() + words[1:] if words else str(key)


# Values for the fields that take a set shape -----------------------------------------------------------------------

def gender_value(text: str) -> str:
    words = label_key(text)
    return GENDER_WORDS.get(words) or GENDER_WORDS.get(words.split(' ')[0] if words else '', '')


def birthday_value(text: str) -> str:
    """MM-DD from "03-04", "March 4" or "4 March"; '' when it gives no month and day."""
    found = re.fullmatch(r'\s*(\d{1,2})-(\d{1,2})\s*', text)
    if found:
        month, day = int(found[1]), int(found[2])
    else:
        words = re.findall(r'[a-z]+|\d+', text.lower())
        names = [MONTHS[word] for word in words if word in MONTHS]
        days = [int(word) for word in words if word.isdigit() and int(word) <= 31]
        if len(names) != 1 or len(days) != 1 or len(words) > 3:
            return ''
        month, day = names[0], days[0]
    return f'{month:02d}-{day:02d}' if 1 <= month <= 12 and 1 <= day <= 31 else ''


def looks_value(text: str) -> tuple[dict, list[str]]:
    """Looks field by field from "Height: 180 cm; Eyes: brown", and the parts that are not one of them."""
    found, rest = {}, []
    for part in (piece.strip() for piece in text.split(';')):
        label, _, value = part.partition(':')
        key = LOOKS.get(label.strip().lower())
        if key in ('height_cm', 'weight_kg'):
            number = adults.age_value(value)
            value = number if number is not None else None
        if key and value not in (None, '') and key not in found:
            try:
                Looks.model_validate({key: value})
                found[key] = value.strip() if isinstance(value, str) else value
                continue
            except ValidationError:
                pass
        if part:
            rest.append(part)
    return found, rest


def secret_value(text: str) -> dict:
    """The secret from "What is true. What people believe instead: ... Who knows: ...", cut to its limits."""
    pieces = SECRET_PARTS.split(text)
    found = {'truth': pieces[0]}
    for label, value in zip(pieces[1::2], pieces[2::2], strict=False):
        # Dramatis' own cards end each part with a full stop (character.secret_text), which the fields don't have.
        found['cover_story' if label.lower().startswith('what') else 'known_by'] = value.strip().removesuffix('.')
    return {key: asking.text_value(found.get(key, ''), limit) for key, limit in drafting.SECRET_LIMITS.items()}


# The form, filled from the file's words ----------------------------------------------------------------------------

class Form:
    """A character filled in field by field from an imported file. Text that fits no field, or is too long for its
    own, goes to the Background with its heading; their secret never does."""

    def __init__(self):
        self.made: dict = {'arc': {}, 'looks': {}}
        self.background: list[str] = []
        self.young, self.cut = None, False

    def put(self, label: str, value):
        field = LABELS.get(label_key(label))
        if field is None:
            return self.spill(label, value)
        text = shown(value)
        if not text and not isinstance(value, list):
            return None
        handler = getattr(self, f"put_{field.replace('.', '_')}", None)
        if handler is not None:
            return handler(label, value, text)
        if field in drafting.LIST_LIMITS:
            return self.listed(field, label, value)
        return self.text(field, label, text)

    def spill(self, label: str, value):
        text = shown(value)
        if text:
            self.background.append(f'{label}: {text}' if label else text)

    def text(self, field: str, label: str, text: str):
        where, key = (self.made['arc'], field[4:]) if field.startswith('arc.') else (self.made, field)
        joined = f'{where[key]}\n\n{text}' if where.get(key) else text
        if len(joined) <= LIMITS[field]:
            where[key] = joined
        else:
            self.spill(label, text)

    def listed(self, field: str, label: str, value):
        count, limit = drafting.LIST_LIMITS[field]
        items = items_of(value)
        kept = [item for item in items if len(item) <= limit]
        self.made[field] = asking.list_value([*self.made.get(field, []), *kept], count, limit)
        dropped = [item for item in items if item not in self.made[field]]
        if dropped:
            self.spill(label, '; '.join(dropped))

    def put_name(self, label, value, text):
        if not self.made.get('name') and len(text) <= LIMITS['name'] and '\n' not in text:
            self.made['name'] = text
        elif text != self.made.get('name'):
            self.spill(label, text)

    def put_description(self, label, value, text):
        """A card's description: its headed lines go to their fields; the rest is About them when it is short and
        the description had headings (as Dramatis' own cards do), and their Background otherwise."""
        lead, sections = headed(text)
        if lead and sections and len(lead) <= LIMITS['about'] and not self.made.get('about'):
            self.made['about'] = lead
        elif lead:
            self.background.append(lead)
        for heading, section in sections:
            self.put(heading, section)

    def put_personality(self, label, value, text):
        lead, sections = headed(text)
        if lead:
            self.text('personality', label, lead)
        for heading, section in sections:
            self.put(heading, section)

    def put_background(self, label, value, text):
        self.background.append(text)

    def put_gender(self, label, value, text):
        found = gender_value(text)
        if found and not self.made.get('gender'):
            self.made['gender'] = found
        elif found != self.made.get('gender'):
            self.spill(label, text)

    def put_age(self, label, value, text):
        age = adults.age_value(value if isinstance(value, int) else text)
        if age is not None and age < 18:
            self.young = age
        elif age is not None and age <= 5000 and len(text) <= 40 and self.made.get('age') is None:
            self.made['age'] = age
        else:
            self.spill(label, text)

    def put_kind(self, label, value, text):
        kind = drafting.kind_value(text)
        if len(text) <= 40 and len(text.split()) <= 3 and not self.made.get('kind'):
            self.made['kind'] = kind
        else:
            self.spill(label, text)

    def put_birthday(self, label, value, text):
        found = birthday_value(text)
        if found and not self.made.get('birthday'):
            self.made['birthday'] = found
        else:
            self.spill(label, text)

    def put_looks(self, label, value, text):
        found, rest = looks_value(text.replace('\n', '; '))
        self.made['looks'] = found | self.made['looks']
        if rest:
            self.text('appearance', label, '; '.join(rest))

    def put_secret(self, label, value, text):
        found = secret_value(text)
        self.made['secret'] = self.made.get('secret') or found

    def character(self, text: str) -> dict:
        """The form as it stands, after the Paste path's checks: no one younger than 18 and no child's look."""
        adults.adult_text(text)
        adults.adults_only(self.young)
        looked = adults.youthful(self.made.get('appearance', ''))
        if looked:
            raise DomainError(YOUTHFUL_TEXT.format(found=', '.join(f'"{word}"' for word in looked)), 422, 'under_18')
        background, self.cut = fitted(self.background)
        made = {key: value for key, value in self.made.items() if key not in ('arc', 'looks')}
        made |= {'background': background, 'arc': self.made['arc'], 'looks': self.made['looks']}
        made['gender'] = made.get('gender') or by_pronouns(' '.join(value for value in made.values() if isinstance(value, str)))
        return Character.model_validate(made).model_dump()


SHE = re.compile(r"\b(?:she|her|hers|herself)\b", re.IGNORECASE)
HE = re.compile(r"\b(?:he|him|his|himself)\b", re.IGNORECASE)


def by_pronouns(text: str) -> str:
    """Woman or man when the card's own words about them clearly say she or he; '' when they don't, or mix them
    (another person in their story). They is left alone: it is as often other people as them."""
    she, he = len(SHE.findall(text)), len(HE.findall(text))
    if she >= 2 and she >= 4 * he:
        return 'woman'
    if he >= 2 and he >= 4 * she:
        return 'man'
    return ''


def fitted(chunks: list[str]) -> tuple[str, bool]:
    """The Background from its parts, cut at a paragraph when it is past its limit; and whether it was cut."""
    text = '\n\n'.join(chunk.strip() for chunk in chunks if chunk.strip())
    if len(text) <= LIMITS['background']:
        return text, False
    cut = text[:LIMITS['background']]
    return (cut[:cut.rfind('\n\n')] if '\n\n' in cut else cut).rstrip(), True


# Reading the file --------------------------------------------------------------------------------------------------

def an_apps_own(value) -> bool:
    """Whether a JSON value is a file Companion's importer reads (or names), so not a blurb."""
    if not isinstance(value, dict) or not value or 'spec' in value or all(key in value for key in formats.FIELDS):
        return True
    if str(value.get('type', '')).startswith('marinara_') or value.get('format') == 'marinara-hierarchical-map':
        return True
    if any(matches(value) for _, matches, _ in formats.NATIVE):
        return True
    try:
        return lorebooks.kind_of(value) is not None
    except DomainError:
        return True


def blurb(filename: str, source: bytes) -> dict | None:
    """A JSON object that is no app's character file or lorebook, or None. One that only wraps another
    ({"character": {...}}) is unwrapped."""
    if PureWindowsPath(filename).suffix.lower() not in ('.json', '') or source.startswith((reader.SIGNATURE, b'PK')):
        return None
    try:
        value = json.loads(source.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError):
        return None
    for _ in range(3):
        if an_apps_own(value) or len(value) != 1 or not isinstance(next(iter(value.values())), dict):
            break
        value = next(iter(value.values()))
    return None if an_apps_own(value) else value


def from_blurb(value: dict) -> dict:
    form, parts, text = Form(), {}, []
    name = next((shown(value[key]) for key in value if LABELS.get(label_key(key)) == 'name'), '')
    for key, item in value.items():
        if part := PART_NAMES.get(label_key(key)):
            parts[part] = part_value(part, item)
            continue
        if key in ('character_book', 'extensions') and isinstance(item, dict):
            parts[key] = item
            continue
        form.put(humanized(key), spelled(item, name) if isinstance(item, str) else item)
        if shown(item):
            text.append(f'{humanized(key)}:\n{spelled(shown(item), name)}')
    if not text:
        raise reader.problem('This JSON file has nothing in it that describes a character.')
    return {'format': BLURB, 'name': name, 'text': '\n\n'.join(text), 'form': form, 'parts': parts, 'picture': None}


def part_value(part: str, value):
    if part == 'tags':
        return items_of(value)
    if part == 'alternate_greetings':
        return [text for text in map(shown, value if isinstance(value, list) else [value]) if text]
    return shown(value)


def raw_card(filename: str, source: bytes, found: dict) -> dict | None:
    """The card's own data object, for the parts Companion's reader leaves out, when the file is a card (JSON, PNG,
    CHARX or Marinara's own export); None for BYAF and the older apps' JSON."""
    if not found['format'].startswith(('Character Card', 'CHARX', 'Marinara')):
        return None
    if PureWindowsPath(filename).suffix.lower() == '.charx' or source.startswith(b'PK'):
        value = formats.member_json(formats.members(source), 'card.json')
    elif PureWindowsPath(filename).suffix.lower() == '.png' or source.startswith(reader.SIGNATURE):
        value = formats.parsed(reader.embedded_card(source))
    else:
        value = formats.parsed(source)
    if isinstance(value, dict) and str(value.get('type', '')).startswith('marinara_'):
        value = value.get('data')
    return reader.card_data(value)


def portable(book: dict) -> dict:
    """A lorebook Companion's reader made (BYAF's lore) as a card's character_book."""
    return {'name': book['name'], 'description': book['description'], 'extensions': {}, 'entries': [
        {'keys': entry['keywords'], 'content': entry['text'], 'name': entry['title'], 'comment': entry['title'],
         'enabled': entry['enabled'], 'constant': entry['always'], 'insertion_order': number, 'use_regex': False,
         'extensions': {}} for number, entry in enumerate(book['entries'])]}


def card_parts(found: dict, raw: dict | None) -> dict:
    character = found['character']
    parts = {key: formats.text(character, key) for key in ('scenario', 'first_mes', 'mes_example', 'creator_notes')}
    if raw is None:
        return parts | {'character_book': portable(found['book']) if found.get('book') else None}
    parts |= {key: formats.text(raw, key) for key in ('system_prompt', 'post_history_instructions', 'creator',
                                                      'character_version')}
    for key in LISTED:
        parts[key] = [item for item in raw.get(key) or [] if isinstance(item, str) and item.strip()] \
            if isinstance(raw.get(key), list) else []
    parts['character_book'] = raw['character_book'] if isinstance(raw.get('character_book'), dict) else None
    parts['extensions'] = raw['extensions'] if isinstance(raw.get('extensions'), dict) else {}
    return parts


def from_file(filename: str, encoded: str, source: bytes) -> dict:
    found = formats.read(filename, encoded)
    if found['character'] is None:
        raise reader.problem(f"This is a lorebook ({found['format']}), not a character. Open a character's card; the "
                             'lorebook it carries comes with them.')
    # The older apps' JSON fills only some of a card's fields.
    character = found['character'] = {key: '' for key in (*formats.FIELDS, 'creator_notes')} | found['character']
    parts = card_parts(found, raw_card(filename, source, found))
    name = character['name'].strip()
    description = '\n\n'.join(text for text in (
        character['description'], *(f'{label}: {character.get(key, "")}' for key, label in
                                    (('backstory', 'Backstory'), ('appearance', 'Appearance')) if character.get(key)))
        if text.strip())
    form = Form()
    for label, text in (('Name', name), ('Description', description), ('Personality', character['personality'])):
        form.put(label, spelled(text, name))
    data = {key: character.get(key, '') for key in formats.FIELDS} | {
        'description': description, 'creator_notes': character.get('creator_notes', ''),
        'character_book': parts['character_book']}
    shown_text = reader.card_text(data)
    return {'format': found['format'], 'name': name, 'text': shown_text['text'], 'form': form, 'parts': parts,
            'picture': found.get('picture')}


# What the screen gets ----------------------------------------------------------------------------------------------

def kept(parts: dict, source: str) -> tuple[CardParts | None, list[str]]:
    """The parts to keep, cut to their limits; a lorebook or extensions too large to keep are left out, said so."""
    shaped = {key: value[:CARD_TEXT] if isinstance(value, str) else value for key, value in parts.items()}
    # What Dramatis' own cards say anyway (its line in the creator's notes, version 1) is not the card's own.
    shaped['creator_notes'] = '' if shaped.get('creator_notes') == cards.MADE_WITH else shaped.get('creator_notes', '')
    version = shaped.get('character_version', '')
    shaped |= {'source': source[:120], 'creator': shaped.get('creator', '')[:200],
               'character_version': '' if version == '1' else version[:60],
               'tags': [tag.strip()[:100] for tag in shaped.get('tags', [])][:64],
               'alternate_greetings': [text[:CARD_TEXT] for text in shaped.get('alternate_greetings', [])][:64]}
    notes = []
    for key, said in (('extensions', "Their card's settings for other apps were too large to keep."),
                      ('character_book', 'Their lorebook was too large to keep.')):
        if len(json.dumps([shaped.get('character_book'), shaped.get('extensions')], ensure_ascii=False)) > CARD_DATA:
            shaped[key] = {} if key == 'extensions' else None
            notes.append(said)
    found = CardParts.model_validate(shaped)
    return (None if found.empty() else found), notes


def kept_names(parts: CardParts | None) -> list[str]:
    if parts is None:
        return []
    found = parts.model_dump()
    names = []
    for key, name in KEPT:
        if key == 'alternate_greetings' and found[key]:
            count = len(found[key])
            names.append('1 other greeting' if count == 1 else f'{count} other greetings')
        elif key == 'character_book' and found[key]:
            count = len(found[key].get('entries') or [])
            names.append(f"lorebook ({'1 entry' if count == 1 else f'{count} entries'})")
        elif found[key]:
            names.append(name)
    return names


def portrait(data: bytes | None) -> tuple[str | None, str]:
    """The file's picture as a PNG portrait without a card inside it, and what to tell the user when there is none."""
    if not data:
        return None, ''
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format == 'PNG':
                opened.verify()
                png = cards.without_card(data)
            else:
                picture = opened.convert('RGBA' if 'A' in opened.getbands() else 'RGB')
                out = io.BytesIO()
                picture.save(out, 'PNG', optimize=True)
                png = out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, DomainError):
        return None, "Their picture couldn't be read, so it was left out."
    if len(png) > library.MAX_PORTRAIT:
        return None, 'Their picture is larger than a portrait can be (10 MB), so it was left out.'
    return base64.b64encode(png).decode('ascii'), ''


def offered(read: dict) -> dict:
    text = read['text']
    parts, notes = kept(read['parts'], read['format'])
    picture, said = portrait(read['picture'])
    character, refused = None, ''
    try:
        character = read['form'].character(text) | {'card': parts and parts.model_dump()}
        if read['form'].cut:
            notes.append('Their Background was longer than the form holds (12,000 characters), so its end was left '
                         'out; the whole text is in the box.')
    except DomainError as error:
        refused = error.message
    return {'kind': 'file', 'format': read['format'], 'name': read['name'], 'text': text[:reader.TEXT_LIMIT],
            'truncated': len(text) > reader.TEXT_LIMIT, 'character': character, 'refused': refused,
            'card': parts and parts.model_dump(), 'kept': kept_names(parts), 'portrait': picture,
            'notes': [note for note in (*notes, said) if note], 'instructions': drafting.instructions_in(text)}


def opened(filename: str, encoded: str) -> dict:
    """A character file: the whole character when Dramatis made it, otherwise what it holds for the user to open in
    the form as it is, or to split into the fields with their model."""
    source = formats.decoded(encoded)
    ours = cards.own_character(filename, source)
    if ours is not None:
        return {'kind': 'character', 'character': ours}
    value = blurb(filename, source)
    return offered(from_blurb(value) if value is not None else from_file(filename, encoded, source))
