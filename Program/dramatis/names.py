"""Names for a character, drawn the way Prospero's Companion names its people, so they are called what people of their
age and background are really called. The banks and the drawing are Companion's own, vendored: what babies were named
by birth year and culture (formats/companion/naming.py and data/given_names.json), each era's name groups
(data/names.json) and `generators.name`, which puts a given name and a family name together.

- Companion draws a name for a city; Dramatis has none, so `Place` reads one from the character's setting: the era its
  words read as (Victorian, the frontier, medieval, a storybook fantasy, the future, and so on) picks the era's bank, a
  year in it is the year their age counts back from, and a country or a people it names makes that country's names the
  local ones. With nothing to go on it is Companion's own default: the modern United States.
- A people their idea names ("a Nigerian nurse", "a Korean grandmother in Houston") is where half the names they are
  offered come from; the other half come from the place, so a word like "French" in "teaches French" never decides
  alone, and the model picks the one that fits.
- `Roll.brief` is for a draft: when the user left Name blank, a few names for the model to choose from, at the age they
  are; and ordinary given and family names for the people their story mentions, with their family sharing theirs.
- No name the AI-slop audit lists is ever offered (dramatis/slop.py): not its stock names (Elara, Voss), nor the real
  but overdrawn ones it flags under Worth a look (Elias, Nora, Hale).
- `Roll.swaps` is for a model's draft that still has a stock or made-up name after its one retry: each is swapped for a
  drawn one wherever it appears, the same one each time, as Companion swaps invented names. A name the user typed or
  pasted is theirs and never changes.
- `Roll.full` is the form's Roll a name, with no model.
"""
import re
import secrets
from functools import cache

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dramatis import looks, slop
from dramatis.formats.companion import catalog, generators, naming

PRONOUNS = {'woman': 'she', 'man': 'he', 'nonbinary': 'they'}
# Eras and the banks of particular times and places, by the words a setting uses for them, first match wins. An era
# Companion grounds in birth years (its given_names.json `era_years`) also takes a year the setting gives.
ERAS = (('steampunk', r'steampunk'), ('jazz-age', r'jazz age|roaring (?:19)?20s|prohibition|19(?:2\d|20s)'),
        ('frontier', r'frontier|wild west|old west|cowboys?|gold rush|homestead'),
        ('victorian', r'victorian|edwardian|regency|gaslit|18[4-9]\d|19(?:0\d|1[0-4])|19th century'),
        ('medieval', r'medieval|middle ages|feudal|knights?|castles?|crusades?|1[0-4]\d\d'),
        ('fantasy', r'fantasy|elves|elven|dwar(?:f|ves)|wizards?|sorcer\w+|dragons?|enchanted|fairy ?tale|kingdom'),
        ('future', looks.FUTURE.pattern))
BANKS = (('edo-japan', r'edo|samurai|shogun\w*|tokugawa|feudal japan'), ('qing-china', r'qing|imperial china|manchu'),
         ('ottoman', r'ottoman|constantinople|sultan\w*'), ('mughal-india', r'mughal'),
         ('ancient-rome', r'ancient rome|roman empire|roman republic|legionar\w*|caesar|pompeii'))
YEAR = re.compile(r'\b(1[6-9]\d\d|2\d\d\d)s?\b')
# Peoples by the words for them, and the culture whose names are theirs (Companion's given_names.json keys).
PEOPLES = {
    'ireland': ('irish',), 'scotland': ('scottish', 'scots'), 'england-wales': ('british', 'welsh', 'cornish'),
    'italy': ('italian',), 'germany': ('german',), 'france': ('french', 'quebecois', 'québécois'), 'spain': ('spanish',),
    'mexico': ('mexican', 'chicano', 'chicana'),
    'us-hispanic': ('latina', 'latino', 'latinx', 'latine', 'hispanic', 'puerto rican', 'cuban', 'dominican',
                    'colombian', 'salvadoran', 'guatemalan', 'peruvian', 'venezuelan'),
    'poland': ('polish',), 'russia': ('russian', 'ukrainian'), 'china': ('chinese', 'cantonese', 'taiwanese'),
    'japan': ('japanese',), 'korea': ('korean',), 'vietnam': ('vietnamese',), 'philippines': ('filipino', 'filipina'),
    'india': ('indian', 'pakistani', 'bangladeshi', 'punjabi', 'tamil', 'gujarati', 'bengali'),
    'nigeria': ('nigerian', 'yoruba', 'igbo'), 'ghana': ('ghanaian',), 'jamaica': ('jamaican', 'trinidadian', 'caribbean'),
    'haiti': ('haitian',), 'us-black': ('african american', 'african-american', 'black american', 'black british'),
    'jewish-diaspora': ('jewish',), 'israel': ('israeli',),
    'arab': ('arab', 'lebanese', 'egyptian', 'syrian', 'palestinian', 'iraqi', 'jordanian', 'moroccan', 'saudi', 'emirati'),
}
# The audit's rules whose hits are a person's name: the ones a model's draft has swapped after its retry.
NAME_RULES = ('names_feminine', 'names_masculine', 'names_romance_hero', 'names_unisex', 'names_stock_full', 'surnames')
GIVEN_RULES = {'names_feminine': 'she', 'names_masculine': 'he', 'names_romance_hero': 'he'}
# Keys of a character that are not their words: never swapped in.
NOT_WORDS = ('personality_sliders', 'looks_from', 'apps', 'card', 'ignored_flags', 'looks')
TRIES = 12
# How often Roll a name takes their people's names over the place's, when their words name a people.
KIN_SHARE = 2 / 3


def words_of(pattern: str) -> re.Pattern:
    return re.compile(rf'\b(?:{pattern})\b', re.IGNORECASE)


@cache
def peoples() -> tuple[tuple[re.Pattern, str], ...]:
    return tuple((words_of('|'.join(re.escape(word) for word in words)), culture) for culture, words in PEOPLES.items())


@cache
def countries() -> re.Pattern:
    """Every country Companion's names know, longest first, so "South Korea" wins over "Korea"."""
    return words_of('|'.join(re.escape(name) for name in sorted(naming.data()['countries'], key=len, reverse=True)))


def era_of(text: str) -> tuple[str, str | None]:
    """(era, bank) for a setting: a bank of its own for a time and place Companion keeps one for, else the era's."""
    for bank, pattern in BANKS:
        if words_of(pattern).search(text):
            return 'medieval', bank
    return next((era for era, pattern in ERAS if words_of(pattern).search(text)), 'modern'), None


def culture_of(text: str) -> str | None:
    """The culture whose names are theirs, by the country or the people a text names."""
    if found := countries().search(text or ''):
        return naming.local_culture(found[0])
    return next((culture for pattern, culture in peoples() if pattern.search(text or '')), None)


class Place:
    """What Companion's `generators.name` takes for a city, read from where and when they come from. `kin` is the
    culture of the people their idea names ("a Nigerian nurse"), when it is not the setting's own."""

    def __init__(self, setting: str = '', words: str = ''):
        setting = setting or ''
        self.era, self.bank = era_of(setting or words)
        year = YEAR.search(setting)
        self.year = int(year[1]) if year and self.era in naming.data()['era_years'] else None
        if self.year and self.era == 'modern' and self.year > naming.data()['present_year']:
            self.era = 'future'
        self.culture = culture_of(setting)
        kin = culture_of(words)
        self.kin = kin if kin and kin != (self.culture or 'us') and self.mix(kin) else None

    def groups(self) -> dict[str, dict]:
        era = catalog.names()['eras'][self.era]
        return catalog.names()['banks'][self.bank or era['bank']]

    def country(self, culture: str | None) -> str:
        return next((name for name, each in naming.data()['countries'].items() if each == culture), '')

    def mix(self, culture: str | None) -> dict[str, float] | None:
        """The name groups for a culture that is not the era's usual one: in a country, the group that takes that
        country's own names (the modern bank's anglo, "local" to wherever they are); for a people with no country of
        their own here (Black American, Jewish), or a bank with no such group, the groups tied to that culture."""
        if not culture or culture == 'us':
            return None
        groups = self.groups()
        local = {key: 1.0 for key, group in groups.items() if group.get('cultures') == {'local': 1}}
        tied = {key: group['cultures'][culture] for key, group in groups.items()
                if (group.get('cultures') or {}).get(culture)}
        return (local if self.country(culture) else {}) or tied or None

    def city(self, kin: bool = False) -> dict:
        culture = self.kin if kin and self.kin else self.culture
        names = {key: value for key, value in (('bank', self.bank), ('year', self.year)) if value}
        if mix := self.mix(culture):
            names['mix'] = mix
        return {'id': '', 'era': self.era, 'country': self.country(culture), 'names': names or None}


def ok(name: str) -> bool:
    """A name to offer: nothing in it the audit lists, hard or flagged, and nothing Companion reads as invented."""
    return bool(name.strip()) and not slop.scan(name) and not naming.is_invented(name)


class Roll:
    """Names for one character, from their seed: the same seed draws the same names."""

    def __init__(self, seed: str, *, gender: str = '', age: int | None = None, setting: str = '', words: str = ''):
        self.seed, self.age = seed, age if age and age >= 18 else None
        self.pronouns = PRONOUNS.get(gender)
        self.place = Place(setting, words)

    def drawn(self, label: str, *, pronouns: str | None = None, age: int | None = None, family: str | None = None,
              kin: bool = False) -> dict:
        """One name from Companion's banks that the audit never flags, redrawn until it is one."""
        city = self.place.city(kin)
        found = {}
        for attempt in range(TRIES):
            found = generators.name(city, seed=f'{self.seed}:{label}:{attempt}', pronouns=pronouns, age=age,
                                    family=family)
            if ok(found['full']):
                break
        return found

    def full(self, label: str = 'name') -> str:
        """Their own name: of their gender and age, most often from their people when their words name one."""
        kin = bool(self.place.kin) and generators.unit(self.seed, label, 'kin') < KIN_SHARE
        return self.drawn(label, pronouns=self.pronouns, age=self.age or 33, kin=kin)['full']

    def candidates(self, count: int = 8) -> list[tuple[str, int]]:
        """(full name, age) to choose from: around their age, or across adult ages when it is open; half from their
        people when their words name one."""
        ages = [self.age + offset for offset in (-3, 0, 2, -1, 3, 1, -2, 0)] if self.age else \
            [26, 31, 36, 41, 46, 51, 56, 29]
        found: dict[str, int] = {}
        for index, age in enumerate(ages[:count]):
            age = max(18, age)
            name = self.drawn(f'pick-{index}', pronouns=self.pronouns, age=age,
                              kin=bool(self.place.kin) and index % 2 == 0)
            found.setdefault(name['full'], age)
        return list(found.items())

    def others(self) -> tuple[list[str], list[str]]:
        """Ordinary given names and family names for the people their story mentions."""
        around = self.age or 38
        kin = bool(self.place.kin)
        given = [self.drawn(f'other-{index}', age=max(18, around + offset), kin=kin and index % 2 == 0)['given']
                 for index, offset in enumerate((28, 26, -2, 3, -5, 30))]
        family = [self.drawn(f'family-{index}', age=around, kin=kin and index % 2 == 0)['family'] for index in range(4)]
        return list(dict.fromkeys(given)), list(dict.fromkeys(family))

    def brief(self, named: bool, pasted: bool = False) -> str:
        """For the prompt: names to choose from when they have none yet, and names for everyone else."""
        given, family = self.others()
        lines = []
        if not named:
            listed = ', '.join(name if self.age else f'{name} (about {age})' for name, age in self.candidates())
            lines.append(('If their text gives them no name' if pasted else 'Unless the user\'s words name them') +
                         f', choose one of these names, which people their age commonly have where they come from: '
                         f'{listed}.')
        lines.append(('For anyone you add who is not in their text' if pasted else 'For the people their story mentions') +
                     f', use ordinary given names such as {", ".join(given)}. '
                     'Their parents and siblings share their family name; anyone else has an ordinary family name '
                     f'such as {", ".join(family)}.')
        return '\n'.join(lines)

    def others_brief(self) -> str:
        given, family = self.others()
        return (f'Anyone it mentions who has no name yet gets an ordinary one: given names such as {", ".join(given)}; '
                'their parents and siblings share their family name, anyone else has one such as '
                f'{", ".join(family)}.')

    def swaps(self, hits: list[dict], own: str = '') -> dict[str, str]:
        """For each word of a stock or made-up name among a model's hard hits, a drawn word to put in its place, the
        same wherever it appears: a word of their own name (`own`) from one name drawn for them, at their gender and
        age; anyone else's from one drawn for that name, its family name for a surname or the last word of a stock full
        name, else its given name. `hits` are the audit's, so a name the user typed or pasted is never among them."""
        found: dict[str, str] = {}
        theirs = own.split()
        mine = self.drawn('swap-own', pronouns=self.pronouns, age=self.age or 33) if theirs else {}
        for hit in hits:
            rule = rule_of(hit)
            if rule is None:
                continue
            words = [word for word in hit['match'].split() if not word.endswith('.')]
            drawn = None
            for index, word in enumerate(words):
                if word in found:
                    continue
                if word in theirs:
                    found[word] = mine['family' if len(theirs) > 1 and theirs[-1] == word else 'given']
                    continue
                drawn = drawn or self.drawn(f"swap-{hit['match'].casefold()}", pronouns=GIVEN_RULES.get(rule))
                family = rule == 'surnames' or (rule == 'names_stock_full' and 0 < index == len(words) - 1) or \
                    (rule == 'made_up' and family_word(word))
                found[word] = drawn['family' if family else 'given']
        return found


def rule_of(hit: dict) -> str | None:
    """The id of the name rule a hit is from, or None for a hit that is not a person's name."""
    if hit['rule'] == slop.MADE_UP:
        return 'made_up'
    return next((key for key, title in rule_titles().items() if title == hit['rule']), None)


@cache
def rule_titles() -> dict[str, str]:
    return {category['id']: category['title'] for category in slop.data()['categories'] if category['id'] in NAME_RULES}


def family_word(word: str) -> bool:
    """Whether a made-up word reads as a family name: on Companion's list of invented ones, or shaped like one."""
    folded = {item.casefold() for item in naming.data()['invented']['family']}
    return word.casefold() in folded or bool(naming.COINED_FAMILY.search(word))


def replaced(value, swaps: dict[str, str]):
    """`value` with each swapped word replaced as a whole word, case and all, in every text inside it."""
    pattern = re.compile(r'(?<![A-Za-z])(' + '|'.join(map(re.escape, sorted(swaps, key=len, reverse=True)))
                         + r')(?![A-Za-z])')
    if isinstance(value, str):
        return pattern.sub(lambda match: swaps[match[0]], value)
    if isinstance(value, list):
        return [replaced(item, swaps) for item in value]
    if isinstance(value, dict):
        return {key: item if key in NOT_WORDS else replaced(item, swaps) for key, item in value.items()}
    return value


# The form's Roll a name -----------------------------------------------------------------------------------------------

class RollBody(BaseModel):
    gender: str = Field(default='', max_length=20)
    age: int | None = Field(default=None, ge=0, le=5000)
    setting: str = Field(default='', max_length=200)
    about: str = Field(default='', max_length=4000)


router = APIRouter(prefix='/api/names')


@router.post('/roll')
def roll_route(body: RollBody) -> dict:
    """A name for the form, from what it says of them so far; no model."""
    found = Roll(secrets.token_hex(5), gender=body.gender, age=body.age, setting=body.setting, words=body.about)
    return {'name': found.full()}
