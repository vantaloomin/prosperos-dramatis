"""The Details of how a character looks (height, build, hair and the rest), settled before the model writes their
Appearance, so the paragraph and the fields can never disagree and every portrait gets the same person.

It works like the personality sliders (dramatis/drafting.py `rolled`). The fields the user's own words speak of
("red hair, soft freckles", "a towering dwarf") are the model's to read into the fields from those words, using
Companion's own reading of what an appearance covers (vendored formats/companion/looks.py `covered`). Every other
field is rolled here first, from the draft's seed, with Companion's own banks and rules (its Matchlight looks and
looks sheet), so a Dramatis roll is the roll Companion would make for them. The model then gets the rolled ones as
facts and writes the Appearance from them. Each field remembers where it came from (`Character.looks_from`):
`idea` for their words, `rolled` for the roll; a field the user edits on the form drops its mark.

The one ordinary detail an Appearance has (a habit, wear, what they carry) is rolled too (data/looks-everyday.json),
and the model is told to give them no scar or mark the fields or the user's words don't: left to choose, models give
every character the same one (a chickenpox scar above the left eyebrow, three drafts running).

After the reply, a field still empty is rolled when the Appearance the model wrote says nothing of it, and a weight
follows the height and build the words gave. Nothing here calls a model.
"""
import json
import re
from functools import cache
from pathlib import Path

from dramatis.formats.companion import generators
from dramatis.formats.companion import looks as sheet

NUMBERS = ('height_cm', 'weight_kg')
WORDS = ('build', 'skin', 'face', 'jaw', 'nose', 'eyes', 'eye_shape', 'hair', 'facial_hair', 'feature')
FIELDS = NUMBERS + WORDS
LIMITS = {'height_cm': (120, 230), 'weight_kg': (35, 250)}
TEXT_LIMITS = {field: 200 if field in ('hair', 'feature') else 120 for field in WORDS}
PRONOUNS = {'woman': 'she/her', 'man': 'he/him', 'nonbinary': 'they/them'}
LABELS = {'height_cm': 'Height', 'weight_kg': 'Weight', 'build': 'Build', 'skin': 'Skin', 'face': 'Face shape',
          'jaw': 'Jaw and chin', 'nose': 'Nose', 'eyes': 'Eye colour', 'eye_shape': 'Eye shape', 'hair': 'Hair',
          'facial_hair': 'Facial hair', 'feature': 'Something people notice'}
# What the model writes into "looks" for a field their words speak of.
SHAPES = {'height_cm': 'their height in centimetres, a whole number', 'weight_kg': 'their weight in kilograms, a whole number',
          'build': 'a word or two, such as \\"curvy\\" or \\"wiry\\"', 'skin': 'their skin, such as \\"fair\\" or \\"deep brown\\"',
          'face': 'face shape, such as \\"round\\"', 'jaw': 'such as \\"a soft jawline\\"', 'nose': 'such as \\"a straight nose\\"',
          'eyes': 'eye colour, such as \\"hazel\\"', 'eye_shape': 'such as \\"hooded\\"',
          'hair': 'colour, length and how they wear it, such as \\"shoulder-length red hair, usually clipped up\\"',
          'facial_hair': 'such as \\"stubble\\", or \\"\\" for none', 'feature': 'one thing people notice, such as \\"freckles\\"'}
LOOKS_ASK = ('Their words describe their {fields}. Fill "looks" with those, as their words have them: one short '
             'phrase each, numbers as whole numbers. Leave one "" (or null for a number) where their words do not '
             'settle it, and write their appearance to agree with "looks".')
LOOKS_BRIEF = ('Their looks, decided by the app. Their appearance agrees with every one of these and need not '
               'mention them all; never give them a different height, build, skin, eyes or hair:')
# The one ordinary detail an Appearance gets, rolled like the rest: left to the model, it is the same scar every time.
EVERYDAY = Path(__file__).parent / 'data' / 'looks-everyday.json'
EVERYDAY_LINE = 'An everyday detail'
NO_MARKS = ('Give them no scar, mole, birthmark or other mark on their body unless these, or the user\'s own words, '
            'give one.')
# A kind of being whose size and colouring a human roll would get wrong: their words decide those.
OTHER_KINDS = re.compile(r'\b(?:elf|elves|elven|dwar(?:f|ves|ven)|orcs?|orcish|half-orc|goblins?|hobgoblins?|halflings?'
                         r'|hobbits?|gnomes?|giants?|ogres?|trolls?|centaurs?|minotaurs?|fae|faer(?:ie|y)|fair(?:y|ies)'
                         r'|pixies?|dragons?|dragonborn|lizard\w*|tiefling|demons?|angels?|android|robot|cyborg|alien'
                         r'|beast\w*|furry|catfolk|kitsune|nekomimi|werewol(?:f|ves)|merfolk|mermaid|merman|slime)\b',
                         re.IGNORECASE)
KIND_FIELDS = {'height_cm', 'weight_kg', 'build', 'skin'}
# Where and when they live, read for the roll: older eras are a little shorter, never dyed pink, and have no tattoo
# sleeves; the future keeps the modern details.
FUTURE = re.compile(r'\b(?:future|futuristic|sci-?fi|space ?station|starships?|spaceships?|colony ship|cyberpunk'
                    r'|2[1-9]\d\d|[3-9]\d{3})\b', re.IGNORECASE)
PERIOD = re.compile(r'\b(?:1[0-8]\d\ds?|19[0-3]\ds?|194[0-5]|medieval|victorian|regency|edwardian|renaissance|ancient'
                    r'|viking|feudal|frontier|wild west|fantasy|kingdom|castle|knights?|tavern|\d{1,2}(?:st|nd|rd|th) '
                    r'century)\b', re.IGNORECASE)
# Hair their words give, when they name no heritage: the colouring rolled around it is the one that hair is most
# often found with, so red hair is not rolled with deep brown skin. Keys are Companion's heritage words.
HAIR_HERITAGE = ((re.compile(r'\b(?:red|ginger|auburn|copper|strawberry[- ]blonde?)[- ]?(?:hair|haired|head)|\bredhead\b',
                             re.IGNORECASE), 'irish'),
                 (re.compile(r'\b(?:blonde?|platinum|flaxen|towheaded)\b', re.IGNORECASE), 'english'))
FEET = re.compile(r"(\d)\s*(?:'|’|ft|feet|foot)\s*(\d{1,2})?")
POUNDS = re.compile(r'(\d{2,3})\s*(?:lbs?|pounds)', re.IGNORECASE)
NUMBER = re.compile(r'\d{2,3}')
HUMAN_LIFESPAN, ADULT = 80, 18


def era_of(text: str) -> str:
    return 'future' if FUTURE.search(text or '') else 'period' if PERIOD.search(text or '') else 'modern'


def life_age(age: int | None, lifespan: int | None, seed: str, words: str = '') -> int:
    """Their age in human terms, for the roll (grey hair, a receding hairline): stretched by a long lifespan; with no
    age picked, the one their words give ("a 58-year-old", "in her forties"); else a seeded adult age, as Companion
    draws one, which is also what someone who doesn't age or is older than any human gets."""
    if age and lifespan and lifespan > HUMAN_LIFESPAN:
        age = round(ADULT + (age - ADULT) * (HUMAN_LIFESPAN - ADULT) / (lifespan - ADULT))
    if not age and lifespan != 0:
        age = sheet.age_of({'identity': words}, seed)
    if not age or lifespan == 0 or age > 110:
        return 24 + round(generators.unit(seed, 'looks-age') * 16)
    return max(ADULT, age)


def covered(words: str) -> set[str]:
    """The fields their words speak of, which the model reads from them rather than the roll."""
    found = sheet.covered(words)
    if OTHER_KINDS.search(words or ''):
        found |= KIND_FIELDS - {'weight_kg'}
    return found


def rolled(seed: str, *, gender: str = '', age: int | None = None, lifespan: int | None = None, words: str = '',
           setting: str = '') -> dict:
    """Every field rolled from the seed with Companion's banks: colouring from the heritage their words name, size and
    hair from their gender and age, the details from their era."""
    pronouns = PRONOUNS.get(gender) or sheet.pronouns_of({'identity': words})
    stand_in = {'key': seed, 'seed': seed, 'age': life_age(age, lifespan, seed, words), 'pronouns': pronouns,
                'heritage': heritage(f'{words} {setting}'), 'goals': [''], 'occupation': ''}
    drawn = sheet.drawn(seed, stand_in, {'era': era_of(f'{setting} {words}')})
    return {field: drawn.get(field) for field in FIELDS}


def heritage(words: str) -> str:
    """The heritage their words name (Companion's reading), else the one the hair they give suggests, else ''."""
    named = sheet.heritage_of({'identity': words})
    return named or next((key for pattern, key in HAIR_HERITAGE if pattern.search(words or '')), '')


@cache
def everyday_bank() -> dict:
    return json.loads(EVERYDAY.read_text(encoding='utf-8'))


def everyday_choices(era: str) -> dict[str, list[str]]:
    """The details that fit their era, by group: every era's, then the present's or the past's."""
    extra = 'period' if era == 'period' else 'modern'
    return {name: group['any'] + group.get(extra, []) for name, group in everyday_bank()['groups'].items()}


def everyday(seed: str, era: str) -> str:
    """One everyday detail for their Appearance (a habit, wear, what they carry), from the seed and their era: a group
    first, then a detail in it, so drafts spread across kinds of detail and not only the biggest group."""
    choices = everyday_choices(era)
    group = generators.pick(seed, 'everyday-group', sorted(choices))
    return generators.pick(seed, 'everyday', choices[group])


def empty(value) -> bool:
    return value in (None, '')


def number(field: str, value) -> int | None:
    """A height or weight from the model: 165, "165 cm", "5'5\\"", "130 lb"; None outside what the form takes."""
    if isinstance(value, bool):
        return None
    found = None
    if isinstance(value, int | float):
        found = round(value)
    elif isinstance(value, str):
        feet, pounds, plain = FEET.search(value), POUNDS.search(value), NUMBER.search(value)
        if field == 'height_cm' and feet and 'cm' not in value:
            found = round((int(feet[1]) * 12 + int(feet[2] or 0)) * 2.54)
        elif field == 'weight_kg' and pounds:
            found = round(int(pounds[1]) / 2.20462)
        elif plain:
            found = int(plain[0])
    low, high = LIMITS[field]
    return found if found is not None and low <= found <= high else None


def bank_build(text: str) -> str:
    """The bank's build that a written build names ("curvy, full-chested" is curvy), for working out a weight."""
    words = (text or '').lower()
    return next((build for build in sorted(sheet.bank()['bmi'], key=len, reverse=True) if build in words), '')


def line(field: str, value) -> str:
    if field == 'height_cm':
        return sheet.height_text(value)
    if field == 'weight_kg':
        return sheet.weight_text(value)
    return str(value)


class Plan:
    """A draft's looks: the fields the user's words speak of, for the model to fill from them, and the rest rolled
    before the model writes."""

    def __init__(self, seed: str, *, words: str = '', gender: str = '', age: int | None = None,
                 lifespan: int | None = None, setting: str = ''):
        self.seed = seed
        self.words = sorted(covered(f'{words} {setting}'), key=FIELDS.index)
        # A weight rolled for a build they never had is "heavily muscled" at 62 kg: when their words give their
        # height or build, the weight waits for those (`settle`).
        later = {'weight_kg'} if {'height_cm', 'build'} & set(self.words) else set()
        self.all = rolled(seed, gender=gender, age=age, lifespan=lifespan, words=words, setting=setting)
        self.rolled = {field: value for field, value in self.all.items()
                       if field not in self.words and field not in later and not empty(value)}
        self.everyday = everyday(seed, era_of(f'{setting} {words}'))

    def brief(self) -> str:
        """The rolled fields as facts for the prompt, with the everyday detail and no marks beyond them."""
        rows = [f'- {LABELS[field]}: {line(field, value)}' for field, value in self.rolled.items()]
        rows.append(f'- {EVERYDAY_LINE}: {self.everyday}')
        return '\n'.join([LOOKS_BRIEF, *rows, '', NO_MARKS])

    def ask(self) -> str:
        if not self.words:
            return ''
        names = [LABELS[field].lower() for field in self.words]
        return LOOKS_ASK.format(fields=names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}")

    def shape(self) -> str:
        """The "looks" key of the reply, with only the fields their words speak of."""
        if not self.words:
            return ''
        body = ', '.join(f'"{field}": "{SHAPES[field]}"' for field in self.words)
        return f',\n  "looks": {{{body}}}'

    def settle(self, raw, appearance: str) -> tuple[dict, dict]:
        """The fields and where each came from: the model's reading of the user's words, the roll, and for a field
        still empty, the roll where the Appearance the model wrote says nothing of it."""
        given = raw if isinstance(raw, dict) else {}
        found = dict(self.rolled)
        sources = {field: 'rolled' for field in self.rolled}
        for field in self.words:
            value = number(field, given.get(field)) if field in NUMBERS else \
                given.get(field).strip()[:TEXT_LIMITS[field]] if isinstance(given.get(field), str) else ''
            if not empty(value):
                found[field], sources[field] = value, 'idea'
        spoken = covered(appearance)
        for field in FIELDS:
            if field in found or field == 'weight_kg' or field in spoken or empty(self.all[field]):
                continue
            found[field], sources[field] = self.all[field], 'rolled'
        if 'weight_kg' not in found and 'weight_kg' not in sheet.covered(appearance) and found.get('height_cm'):
            found['weight_kg'] = sheet.weight_kg(self.seed, found['height_cm'], bank_build(found.get('build', '')))
            sources['weight_kg'] = 'rolled'
        looks = {field: found.get(field, None if field in NUMBERS else '') for field in FIELDS}
        return looks, sources
