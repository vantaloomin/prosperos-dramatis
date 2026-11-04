"""Drafting with the user's model: a whole character from a few picks, a pasted character split into the fields, and
one field rewritten to fit the rest. Ported from Prospero's Companion (companion/drafting.py and
companion/character_helper.py at ae9b0ab) and Adventure (adventure/making.py at 4e35586), for every app at once.

- The personality sliders are rolled before the model writes, from the user's own words where they settle one
  (Companion's personality.py, vendored), and the model gets them as behaviour, never as trait names.
- The model replies with one JSON object; a reasoning block, a Markdown fence or a sentence around it is ignored.
  The reply is shaped here: text trimmed to each field's limit, lists de-duplicated and capped, weekly blocks
  checked one by one with Companion's own RoutineBlock. A reply that cannot be used is asked for once more with the
  problem named, and refused after that so the user can fill in the form themselves.
- Characters are adults: an age pick or a reply under 18 is refused.
- The user's picks win over the model: name, gender, age, where and when, the relationship, and emotional edges,
  which stay off unless the user turns them on or their words ask for them.

Nothing is saved: a draft goes back to the form for review. The prompts are files in dramatis/prompts.
"""
import json
import re
import secrets
from pathlib import Path

from pydantic import ValidationError

from dramatis import ai
from dramatis.character import APPS, Character
from dramatis.formats.companion import personality
from dramatis.formats.companion.errors import DomainError
from dramatis.formats.companion.models import RoutineBlock

PROMPTS = Path(__file__).parent / 'prompts'
TEXT_LIMITS = {'name': 80, 'about': 2000, 'personality': 8000, 'voice': 600, 'appearance': 600,
               'background': 12000, 'wants': 300, 'fears': 300}
LIST_LIMITS = {'skills': (20, 300), 'flaws': (20, 300), 'interests': (50, 120)}
LIFE_TEXT = {'routine': 8000, 'absence_reaction': 2000}
REQUIRED = ('name', 'about', 'personality')
GENDERS = ('woman', 'man', 'nonbinary')
APP_NAMES = {'companion': "Prospero's Companion (an everyday life and chats)",
             'adventure': "Prospero's Adventure (a tabletop story, with a mind of their own)",
             'dungeon': "Prospero's Dungeon (a tabletop story)"}
ADULTS_ONLY = 'Characters are always adults. Give them an age of 18 or older, or leave their age open.'
# An age the about line gives that is under 18 ("is 16", "a 15-year-old").
YOUNG = re.compile(r"\b(?:is|am|aged?)\s+(?:1[0-7]|[1-9])\b(?!\s*(?:years?\s+(?:ago|later|since)|%|:))"
                   r"|\b(?:1[0-7]|[1-9])[- ]years?[- ]old\b", re.IGNORECASE)
EDGE_WORDS = ('jealous', 'possessive', 'envious', 'clingy', 'needy', 'misses you', 'missing you', 'guilt', 'absence')
NO_EDGES = ('Leave "emotional_traits" as [] and "absence_reaction" as "". The user has not asked for jealousy, '
            'guilt over absence or similar traits.')
EDGES = ('The user asked for emotional edges. You may add up to 3 "emotional_traits", each {"name": short name, '
         '"intensity": "mild" | "moderate" | "strong", "note": how it shows}, and an "absence_reaction" sentence, '
         'but only ones their idea supports.')
FIELD_EDGES = 'Do not add jealousy, guilt over absence, possessiveness or neediness unless the character already has them.'
PERSONALITY_BRIEF = ('Their personality, decided by the app. Build the character around it and do not soften it; '
                     'show it as behaviour, never as trait names or scores.')
# A voice that avoids capitals turns on lowercase texting in Companion (companion/texting.py LOWERCASE).
LOWERCASE = re.compile(r'lower-?case|avoids? capital|no capital|without capital|never capitali|skips? capital'
                       r'|(?:rarely|seldom|hardly ever|never) (?:uses? |bothers? with )?capital', re.IGNORECASE)
SLEEP_PROBLEM = 'the schedule needs sleep blocks that cover every day, 0 to 6.'

CORE_SHAPE = '''  "name": "first and last name, or the one name they go by",
  "gender": "woman | man | nonbinary",
  "age": a whole number of years, 18 or more,
  "kind": "\\"\\" for an ordinary human, else one lowercase word for what they are, such as \\"elf\\"",
  "about": "2 to 4 sentences: their age, what they do, who they live or travel with, what they care about right now",
  "personality": "a paragraph: temperament, how they treat people, the contradiction, what annoys them",
  "voice": "2 to 4 sentences of instructions for how they talk and write",
  "appearance": "2 or 3 plain sentences: what people see",
  "background": "1 or 2 paragraphs of ordinary history",
  "wants": "one sentence: what they are after",
  "fears": "one sentence: what they are afraid of",
  "skills": ["4 to 7 concrete skills, one short phrase each"],
  "flaws": ["3 to 5 real flaws, one short sentence each"],
  "interests": ["4 to 8 specific interests, a few words each"]'''
LIFE_SHAPE = ''',
  "routine": "3 to 5 sentences in their own words describing a normal weekday and weekend",
  "life_themes": ["5 to 10 short themes their everyday life tends to involve, such as people, places by type, hobbies"],
  "schedule": [
    {"label": "short name", "kind": "work | study | errand | leisure | social | rest | sleep",
     "days": [0, 1, 2, 3, 4], "start": "HH:MM", "end": "HH:MM", "themes": ["up to 5 short themes"]}
  ],
  "emotional_traits": [],
  "absence_reaction": ""'''
SCHEDULE_RULES = ('Schedule rules: 4 to 8 blocks in 24-hour time, in their local time. Days are numbers, 0 is Monday '
                  'and 6 is Sunday. Always include a sleep block every day; a block that ends earlier than it starts '
                  'runs past midnight. Work matches their real hours. Blocks on the same day must not overlap. Add at '
                  'least one recurring thing that is theirs, such as a class, a standing call or a regular errand.')
FILLED_IN = ''',
  "filled_in": ["the keys of the fields their text said nothing about"]'''


class Unusable(Exception):
    """The model's reply could not become a character; the message says why, for the one retry."""


def template(name: str) -> str:
    return (PROMPTS / name).read_text(encoding='utf-8')


def fill(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    return text


def field_guides() -> dict[str, dict]:
    return json.loads(template('fields.json'))


def shape_text(apps: list[str], split: bool = False) -> str:
    life = 'companion' in apps
    body = CORE_SHAPE + (LIFE_SHAPE if life else '') + (FILLED_IN if split else '')
    return '{\n' + body + '\n}' + (f'\n\n{SCHEDULE_RULES}' if life else '')


# Asking the model -------------------------------------------------------------------------------------------------

def parse_object(text: str) -> dict:
    """The JSON object in a reply, ignoring a reasoning block, a Markdown fence or a sentence around it."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.DOTALL)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise Unusable('it did not contain a JSON object.')
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise Unusable(f'the JSON was malformed ({error.msg}).') from error
    if not isinstance(data, dict):
        raise Unusable('it was not a JSON object.')
    return data


def ask(system: str, shape, prompt: str = 'Write the JSON now.'):
    """One request and, if the reply cannot be used, one retry that names the problem. `shape(raw, final)` is strict
    on the first reply; on the retry it makes do where it can."""
    reply = ai.complete(system, prompt)
    try:
        return shape(parse_object(reply), False)
    except Unusable as problem:
        retry = (f'{prompt}\n\nYour last reply was:\n{reply[:6000]}\n\n'
                 + fill(template('repair.md'), problem=str(problem)))
    try:
        return shape(parse_object(ai.complete(system, retry)), True)
    except Unusable as problem:
        raise DomainError(f"The model's draft could not be used: {problem} Try again, or fill in the form yourself.",
                          502, 'draft_unusable') from problem


# Shaping what came back -------------------------------------------------------------------------------------------

def text_value(value, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ''


def list_value(value, count: int, limit: int) -> list[str]:
    items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    seen, result = set(), []
    for item in items:
        text = item.strip()[:limit] if isinstance(item, str) else ''
        if text and text.lower() not in seen:
            seen.add(text.lower())
            result.append(text)
    return result[:count]


def block(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    days = item.get('days')
    try:
        return RoutineBlock.model_validate({
            'label': text_value(item.get('label'), 120), 'kind': item.get('kind') or 'leisure',
            'days': sorted({day for day in days if isinstance(day, int)}) if isinstance(days, list) else days,
            'start': item.get('start'), 'end': item.get('end'),
            'themes': list_value(item.get('themes'), 10, 120)}).model_dump()
    except (ValidationError, TypeError):
        return None


def schedule_value(value) -> list[dict]:
    return [found for found in map(block, value if isinstance(value, list) else []) if found][:24]


def sleeps_every_day(blocks: list[dict]) -> bool:
    return {day for item in blocks if item['kind'] == 'sleep' for day in item['days']} == set(range(7))


def traits_value(value) -> list[dict]:
    traits = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict) and text_value(item.get('name'), 60):
            intensity = item.get('intensity') if item.get('intensity') in ('mild', 'moderate', 'strong') else 'mild'
            traits.append({'name': text_value(item.get('name'), 60), 'intensity': intensity,
                           'note': text_value(item.get('note'), 500)})
    return traits[:3]


def age_value(value) -> int | None:
    """A whole number of years from a pick or a reply ("34", 34, "about 40"); None when it gives none."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    found = re.search(r'\d{1,4}', value) if isinstance(value, str) else None
    return int(found[0]) if found else None


def adults_only(age: int | None, about: str = '') -> None:
    if (age is not None and age < 18) or YOUNG.search(about or ''):
        raise DomainError(ADULTS_ONLY, 422, 'under_18')


def edges_allowed(picks: dict) -> bool:
    words = f"{picks.get('idea', '')} {picks.get('vibe', '')}".lower()
    return bool(picks.get('emotional_edges')) or any(word in words for word in EDGE_WORDS)


def kind_value(value) -> str:
    text = re.sub(r'[^a-z0-9-]+', '-', value.strip().lower()).strip('-')[:40] if isinstance(value, str) else ''
    return '' if text in ('human', 'person', 'none') else text


class Shape:
    """Turns a model's reply into a character the form can show, with the user's picks winning."""

    def __init__(self, picks: dict, sliders: dict, split: bool = False):
        self.picks, self.sliders, self.split = picks, sliders, split
        self.apps = picks.get('apps') or list(APPS)

    def __call__(self, raw: dict, final: bool) -> dict:
        if raw.get('under_18') is True:
            raise DomainError('Characters are always adults, and this character reads as younger than 18. Change '
                              'their age in the text, or start from the quick start.', 422, 'under_18')
        made = {key: text_value(raw.get(key), limit) for key, limit in TEXT_LIMITS.items()}
        made |= {key: list_value(raw.get(key), *limits) for key, limits in LIST_LIMITS.items()}
        made['name'] = (self.picks.get('name') or '').strip() or made['name']
        missing = [key for key in REQUIRED if not made[key]]
        if missing:
            raise Unusable(f"it left out {', '.join(missing)}.")
        age = self.picks.get('age') or age_value(raw.get('age'))
        adults_only(age, made['about'])
        made |= {'age': age if age and age <= 5000 else None, 'kind': kind_value(raw.get('kind')),
                 'gender': self.picks.get('gender') or (raw.get('gender') if raw.get('gender') in GENDERS else ''),
                 'setting': (self.picks.get('setting') or '').strip()[:200], 'apps': self.apps,
                 'personality_sliders': self.sliders, 'companion': self.life(raw, made, final)}
        try:
            character = Character.model_validate(made).model_dump()
        except ValidationError as error:
            raise Unusable(f"it did not fit the character format ({error.errors()[0]['msg']}).") from error
        result = {'character': character}
        if self.split:
            filled = raw.get('filled_in') if isinstance(raw.get('filled_in'), list) else []
            result['filled_in'] = [key for key in dict.fromkeys(filled) if key in made and key not in ('name',)]
        return result

    def life(self, raw: dict, made: dict, final: bool) -> dict:
        """Companion's part: how they know the user (the user's picks) and, when they are made for Companion, the
        everyday life the model wrote."""
        life = {'relationship': self.picks.get('relationship') or 'friendship',
                'timezone': (self.picks.get('timezone') or '')[:64]}
        if 'companion' not in self.apps:
            return life
        blocks = schedule_value(raw.get('schedule'))
        if not sleeps_every_day(blocks) and not final:
            raise Unusable(SLEEP_PROBLEM)
        life |= {key: text_value(raw.get(key), limit) for key, limit in LIFE_TEXT.items()}
        life |= {'schedule': blocks, 'life_themes': list_value(raw.get('life_themes'), 20, 120),
                 'texting': {'lowercase': bool(LOWERCASE.search(made['voice']))}}
        if edges_allowed(self.picks):
            life['emotional_traits'] = traits_value(raw.get('emotional_traits'))
        else:
            life['absence_reaction'] = ''
        return life


# The three requests -----------------------------------------------------------------------------------------------

def new_seed() -> str:
    return secrets.token_hex(5)


def rolled(words: str, seed: str) -> dict:
    """The sliders the app decides before the model writes: what the user's words say, the rest rolled by seed."""
    return personality.settle({}, seed, personality.from_words(words))


def personality_brief(sliders: dict) -> str:
    lines = '\n'.join(f'- {line}' for line in personality.behaviour(personality.levels_of(sliders)))
    return f'{PERSONALITY_BRIEF}\n{lines}' if lines else ''


def picks_text(picks: dict) -> str:
    apps = picks.get('apps') or list(APPS)
    rows = [('Idea', picks.get('idea') or 'None given. Surprise them with someone ordinary and specific.'),
            ('Name', picks.get('name')), ('Gender', picks.get('gender')), ('Age', picks.get('age')),
            ('Where and when they come from', picks.get('setting')), ('Vibe', picks.get('vibe')),
            ('Relationship to the user', picks.get('relationship') if 'companion' in apps else ''),
            ('Made for', '; '.join(APP_NAMES[app] for app in apps))]
    return '\n'.join(f'- {label}: {value}' for label, value in rows if value)


def draft(picks: dict) -> dict:
    """A whole character from the quick start's picks, for the form to review; nothing is saved."""
    adults_only(picks.get('age'))
    seed = new_seed()
    sliders = rolled(f"{picks.get('idea', '')} {picks.get('vibe', '')}", seed)
    system = fill(template('draft.md'), rules=template('rules.md'), picks=picks_text(picks),
                  personality=personality_brief(sliders), emotional=EDGES if edges_allowed(picks) else NO_EDGES,
                  shape=shape_text(picks.get('apps') or list(APPS)))
    return ask(system, Shape(picks, sliders)) | {'seed': seed}


def split(picks: dict) -> dict:
    """A whole pasted character split into the fields, with the ones the model had to fill in; nothing is saved."""
    seed = new_seed()
    text = picks['text']
    sliders = rolled(text, seed)
    # Last, so braces in the user's own text are never read as placeholders.
    system = fill(template('split.md'), rules=template('rules.md'), shape=shape_text(picks.get('apps') or list(APPS),
                  split=True), emotional=EDGES if edges_allowed(picks) else NO_EDGES, pasted=text)
    return ask(system, Shape({key: value for key, value in picks.items() if key != 'name'}, sliders, split=True)) | \
        {'seed': seed}


def rewrite(character: dict, field: str, request: str = '') -> dict:
    """A new value for one field, written to fit the rest of the character as the form has it."""
    guides = field_guides()
    if field not in guides:
        raise DomainError(f'{field} cannot be rewritten.', 422)
    guide = guides[field]
    current = {key: value for key, value in character.items() if key not in ('personality_sliders', 'apps')}
    system = fill(template('field.md'), rules=template('rules.md'), field=field, field_guide=guide['guide'],
                  field_shape=guide['shape'], emotional=FIELD_EDGES,
                  request=f'What the user wants changed: {request.strip()}' if request.strip() else '',
                  character=json.dumps(current, ensure_ascii=False, indent=1))
    return ask(system, lambda raw, final: {'field': field, 'value': field_value(field, guide, raw, final)})


def field_value(field: str, guide: dict, raw: dict, final: bool):
    value = raw.get('value', raw.get(field))
    if field == 'schedule':
        blocks = schedule_value(value)
        if not blocks or (not sleeps_every_day(blocks) and not final):
            raise Unusable(SLEEP_PROBLEM)
        return blocks
    if 'count' in guide:
        found = list_value(value, guide['count'], guide['limit'])
    else:
        found = text_value(value, guide['limit'])
    if not found:
        raise Unusable(f'"{field}" was empty.')
    return found
