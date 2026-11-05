# Vendored from vantaloomin/prosperos-companion Program/companion/world/dating.py by scripts/sync_format.py. Edit it there, then sync.
"""What a townsperson is like to date, by rule (docs/dating.md).

Every townsperson's dating details are drawn from their sheet's seed like the rest of them, so they are the
same every time and nothing is stored: how they look, who they are attracted to, whether they are single,
what they are looking for, how picky they are, and a short bio built from what the sheet already says about
them (job, quirk, goal, usual spot). No model is involved.

The rates are rough real-world ones: most adults are straight, younger people are more often bisexual (US
surveys put adults under 30 near one in five identifying as LGBT, mostly bisexual, and adults over 60 near
one in fifty), and the chance of having a partner rises with age until widowhood takes some away.
"""
from datetime import date

from dramatis.formats.companion import generators
from dramatis.stand_ins import lifespans, mix, townsfolk

GENDERS = ('woman', 'man', 'nonbinary')
GENDER_OF = {'she/her': 'woman', 'he/him': 'man', 'they/them': 'nonbinary'}
LOOKING = ('serious', 'casual', 'friends')
# By age band: (upper age, gay share, bisexual share for women, for men, for nonbinary people).
ORIENTATION_RATES = ((29, 0.04, 0.15, 0.06), (44, 0.03, 0.07, 0.03), (59, 0.025, 0.02, 0.02), (200, 0.02, 0.01, 0.01))
# The chance of having a partner by age band, and how many of those are married.
PARTNERED = ((24, 0.30, 0.20), (29, 0.50, 0.45), (34, 0.60, 0.60), (64, 0.65, 0.80), (200, 0.55, 0.90))
LIKE_BASE = 0.6
TEMPER_LIKES = {'warm': 0.05, 'cheerful': 0.05, 'chatty': 0.05, 'easygoing': 0.05, 'shy': -0.05, 'anxious': -0.05,
                'gruff': -0.05, 'driven': -0.05}

# Looks --------------------------------------------------------------------------------------------------

# Rough colouring by the heritage their name comes from (townsfolk sheet 'heritage', a culture or name group).
REGIONS = (
    ('east', ('china', 'chinese', 'japan', 'korea', 'vietnam', 'east-asian', 'edo', 'qing', 'philippines')),
    ('south', ('india', 'south-asian', 'mughal')),
    ('african', ('ghana', 'nigeria', 'black', 'west-african', 'haiti', 'jamaica', 'caribbean')),
    ('latin', ('mexic', 'hispanic')),
    ('arab', ('arab', 'ottoman')),
    ('celtic', ('ireland', 'irish', 'scot', 'welsh', 'cornish')),
    ('european', ('england', 'english', 'anglo', 'us', 'american', 'france', 'germany', 'german', 'poland',
                  'russia', 'slavic', 'italy', 'italian', 'spain', 'jewish', 'israel', 'norman', 'west-riding',
                  'roman')),
)
HAIR = {
    'east': {'black': 85, 'dark brown': 15},
    'south': {'black': 75, 'dark brown': 25},
    'african': {'black': 90, 'dark brown': 10},
    'latin': {'black': 50, 'dark brown': 40, 'brown': 10},
    'arab': {'black': 70, 'dark brown': 30},
    'celtic': {'dark brown': 25, 'brown': 25, 'light brown': 12, 'red': 13, 'blond': 15, 'black': 10},
    'european': {'dark brown': 30, 'brown': 25, 'light brown': 12, 'blond': 17, 'red': 4, 'black': 12},
    None: {'black': 30, 'dark brown': 30, 'brown': 20, 'blond': 12, 'red': 3, 'light brown': 5},
}
EYES = {
    'east': {'dark brown': 90, 'brown': 10}, 'south': {'dark brown': 80, 'brown': 15, 'hazel': 5},
    'african': {'dark brown': 90, 'brown': 10}, 'latin': {'brown': 70, 'dark brown': 15, 'hazel': 10, 'green': 5},
    'arab': {'brown': 70, 'dark brown': 15, 'hazel': 10, 'green': 5},
    'celtic': {'blue': 40, 'brown': 20, 'green': 15, 'hazel': 15, 'gray': 10},
    'european': {'blue': 27, 'brown': 35, 'hazel': 16, 'green': 12, 'gray': 10},
    None: {'brown': 55, 'blue': 20, 'hazel': 12, 'green': 8, 'gray': 5},
}
HAIR_STYLES = {
    'woman': ('long', 'shoulder-length', 'in a bob', 'cropped short', 'curly', 'always up in a bun', 'in a ponytail',
              'wavy'),
    'man': ('short', 'cropped', 'buzzed', 'a little messy', 'longish', 'neatly parted', 'curly'),
    'nonbinary': ('short', 'cropped', 'shoulder-length', 'a little messy', 'curly', 'shaved at the sides'),
}
DYED = ('bleached', 'dyed pink', 'dyed blue', 'dyed purple')
BUILDS = {
    'woman': ('slim', 'petite', 'average', 'athletic', 'curvy', 'soft', 'tall and lean', 'full-figured'),
    'man': ('slim', 'lean', 'average', 'athletic', 'stocky', 'broad-shouldered', 'heavyset', 'wiry'),
    'nonbinary': ('slim', 'lean', 'average', 'athletic', 'soft', 'wiry', 'stocky'),
}
# Builds by how much of them there is, for the world's mix of builds (companion/world/mix.py).
BUILD_GROUPS = {'slender': ('slim', 'petite', 'lean', 'wiry', 'tall and lean'),
                'middle': ('average', 'athletic', 'broad-shouldered', 'curvy'),
                'heavier': ('soft', 'stocky', 'full-figured', 'heavyset')}
# Mean and spread of adult height in centimetres; people in older eras were a little shorter.
HEIGHT = {'woman': (162, 6.5), 'man': (176, 7.0), 'nonbinary': (169, 8.0)}
STYLES = {
    'modern': ('streetwear', 'smart casual', 'thrift-store vintage', 'all black, always', 'athleisure', 'preppy',
               'workwear and boots', 'bright colors and prints', 'band T-shirts and jeans', 'sharp and tailored',
               'cozy knits', 'whatever was clean'),
    'future': ('sleek tech fabrics', 'twentieth-century revival', 'reflective streetwear', 'plain grey utility wear',
               'hand-made and patched', 'bright synthetic colors', 'sharp and tailored'),
    'period': ('neat Sunday best', 'well-worn working clothes', 'a little dandyish', 'plain and sensible',
               'fashionable to the last button', 'mended but spotless', 'bright ribbons and a good hat'),
    # An era's own looks, where the period ones above don't fit it.
    'jazz-age': ('a sharp three-piece suit', 'beads, fringe and a short hemline', 'a cloche hat pulled low',
                 'Oxford bags and a sweater vest', 'well-worn working clothes', 'neat Sunday best',
                 'two-tone shoes and a pocket square', 'mended but spotless', 'a raccoon coat and college colors'),
}
DETAILS = ('freckles', 'dimples', 'a gap-toothed smile', 'glasses', 'laugh lines', 'a crooked smile',
           'a scar through one eyebrow', 'very long eyelashes', 'a small mole above the lip', 'a broken nose that '
           'healed a little crooked', 'rosy cheeks', 'striking eyebrows')
MODERN_DETAILS = ('a nose ring', 'a tattoo sleeve', 'a small tattoo on the wrist', 'several ear piercings')
BEARDS = ('a full beard', 'stubble', 'a neat moustache', 'a trimmed beard')

# The bio -----------------------------------------------------------------------------------------------

LOOKING_TEXT = {'serious': 'a relationship', 'casual': 'something casual', 'friends': 'new friends'}
PART_TEXT = {'morning': 'mornings', 'afternoon': 'afternoons', 'evening': 'evenings', 'late': 'late evenings'}
# A personal-column notice, in older eras: what they seek, by what they are looking for.
SEEKS = {'serious': 'with a view to matrimony', 'casual': 'for amusement and good company',
         'friends': 'for friendship and correspondence'}
COLUMN_HEIGHT = ((155, 'small'), (165, 'of middling height'), (180, 'tall'), (999, 'very tall'))


def region(sheet: dict) -> str | None:
    heritage = (sheet.get('heritage') or '').lower()
    return next((name for name, words in REGIONS if any(word in heritage for word in words)), None) \
        if heritage else None


def weighted(seed: str, label: str, table: dict):
    return generators.pick(seed, label, list(table), list(table.values()))


def gender(sheet: dict) -> str:
    return GENDER_OF.get(sheet.get('pronouns', ''), 'nonbinary')


def life_of(sheet: dict, data: dict | None = None) -> int:
    """Their age in human terms (companion/world/lifespans.py): who is partnered, who is looking and who they date
    follow it, so an elf of 300 dates like someone of 48. Orientation keeps their real age, as their adult side does."""
    return lifespans.life_age(sheet['age'], lifespans.lifespan_of(sheet.get('folk'), data))


def rates(age: int) -> tuple:
    """The age band's orientation rates, as the world's mix has them (companion/world/mix.py)."""
    # An elf of 300 is in the last band (companion/world/lifespans.py).
    return mix.orientation_band(next((band for band in ORIENTATION_RATES if age <= band[0]), ORIENTATION_RATES[-1]))


def orientation(seed: str, age: int, who: str) -> tuple[str, list[str]]:
    """Their orientation label and the genders they are drawn to."""
    _upper, gay, bi_woman, bi_man = rates(age)
    roll = generators.unit(seed, 'orientation')
    if who == 'nonbinary':
        return 'queer', weighted(seed, 'drawn-to', {('woman', 'man', 'nonbinary'): 6, ('woman', 'nonbinary'): 2,
                                                    ('man', 'nonbinary'): 2})
    other = 'man' if who == 'woman' else 'woman'
    if roll < gay:
        return ('lesbian' if who == 'woman' else 'gay'), [who]
    if roll < gay + (bi_woman if who == 'woman' else bi_man):
        return 'bisexual', ['woman', 'man', 'nonbinary']
    return 'straight', [other]


def status(seed: str, age: int, desire: str, modern: bool) -> str:
    """Single, seeing someone, married or widowed."""
    _upper, partnered, married = next((band for band in PARTNERED if age <= band[0]), PARTNERED[-1])
    if desire == 'company':  # Wanting someone to come home to: most of them haven't found them.
        partnered *= 0.2
    elif desire == 'family':
        partnered = min(partnered + 0.1, 0.9)
    if generators.unit(seed, 'partnered') < partnered:
        return 'married' if generators.unit(seed, 'married') < (married if modern else 0.9) else 'seeing someone'
    return 'widowed' if age >= 60 and generators.unit(seed, 'widowed') < 0.4 else 'single'


def looking(seed: str, age: int, desire: str, single: bool, modern: bool, real: int | None = None) -> str:
    """What they are after: 'serious', 'casual', 'friends', or 'no' (not looking, so not on the app). `age` is their
    life age; `real` their real one, which `orientation` reads, when it differs."""
    if not single:
        return 'no'
    away = 0.6 if desire == 'quiet' else 0.1 if desire == 'company' else 0.35
    if age >= 65:
        away = max(away, 0.55)
    # Gay, lesbian and bisexual adults use dating apps about twice as often (Pew, 2023: 51% against 28%). This
    # reads the same roll `orientation` does, before their gender is known.
    _upper, gay, bi_woman, bi_man = rates(age if real is None else real)
    if generators.unit(seed, 'orientation') < gay + max(bi_woman, bi_man):
        away /= 3
    if generators.unit(seed, 'looking') < away:
        return 'no'
    weights = {'serious': 45, 'casual': 30, 'friends': 25}
    if desire in ('company', 'family', 'security'):
        weights['serious'] += 30
    if desire == 'adventure':
        weights['casual'] += 25
    if age < 25:
        weights['casual'] += 15
    if age >= 40:
        weights['serious'] += 15
    if not modern:
        weights = {'serious': weights['serious'] + 40, 'casual': 5, 'friends': weights['friends']}
    return weighted(seed, 'looking-for', weights)


def age_range(age: int, looking_for: str) -> tuple[int, int]:
    """Who they would date: never under 18, and not far from their own age."""
    low = max(18, round(age / 2 + 7), age - (15 if looking_for == 'casual' else 10))
    return low, age + (15 if looking_for == 'casual' else 10)


def height_cm(seed: str, who: str, modern: bool) -> int:
    mean, spread = HEIGHT[who]
    mean = mix.height_mean(who, mean)
    # The mean of three draws is close enough to a bell curve, with the spread restored.
    draw = sum(generators.unit(seed, 'height', n) for n in range(3)) / 3 - 0.5
    return round(mean - (0 if modern else 5) + draw * spread * 6)


def hair(seed: str, sheet: dict, who: str, era: str) -> str:
    age = life_of(sheet)
    if who == 'man' and age >= 35 and generators.unit(seed, 'bald') < (age - 30) / 60:
        return generators.pick(seed, 'bald-how', ['a shaved head', 'thinning hair', 'a receding hairline'])
    color = weighted(seed, 'hair', HAIR[region(sheet)])
    if age >= 55 and generators.unit(seed, 'grey') < 0.6:
        color = generators.pick(seed, 'grey-how', ['gray', 'silver', 'salt-and-pepper'])
    elif age >= 42 and generators.unit(seed, 'grey') < 0.3:
        color = f'greying {color}'
    elif era != 'period' and age < 40 and generators.unit(seed, 'dyed') < 0.08:
        color = generators.pick(seed, 'dyed-how', list(DYED))
    style = generators.pick(seed, 'hair-style', list(HAIR_STYLES[who]))
    return f'{color} hair, {style}' if style.startswith(('in ', 'always', 'a ', 'neatly', 'shaved')) \
        else f'{style} {color} hair'


def build(seed: str, sheet: dict, who: str) -> str:
    sporty = sheet.get('goals', [''])[0] in ('race', 'strong') or 'trainer' in (sheet.get('occupation') or '')
    if sporty and generators.unit(seed, 'sporty') < 0.7:
        return 'athletic'
    if not mix.builds_changed():
        return generators.pick(seed, 'build', list(BUILDS[who]))
    # Each group's share is split evenly among the builds it has for them.
    groups = [(group, [item for item in BUILDS[who] if item in members]) for group, members in BUILD_GROUPS.items()]
    weights = [mix.current()[group] / len(items) for group, items in groups for _item in items]
    return generators.pick(seed, 'build', [item for _group, items in groups for item in items], weights) \
        if sum(weights) else generators.pick(seed, 'build', list(BUILDS[who]))


def fitted(drawn: str, tall: int, who: str) -> str:
    """A build that names a height agrees with the height drawn: no 5'2" 'tall and lean', no 6' 'petite'."""
    mean = mix.height_mean(who, HEIGHT[who][0])
    if drawn == 'tall and lean' and tall < mean + 5:
        return 'lean'
    return 'slim' if drawn == 'petite' and tall > mean else drawn


def era_kind(data: dict) -> str:
    era = data.get('era', 'modern')
    return 'future' if era == 'future' else 'modern' if townsfolk.modern(data) else 'period'


def looks(sheet: dict, data: dict) -> dict:
    seed, who, era = townsfolk.drawn(sheet), gender(sheet), era_kind(data)
    details = list(DETAILS) + (list(MODERN_DETAILS) if era != 'period' else [])
    tall = height_cm(seed, who, era != 'period')
    found = {'height_cm': tall, 'build': fitted(build(seed, sheet, who), tall, who),
             'hair': hair(seed, sheet, who, era), 'eyes': f"{weighted(seed, 'eyes', EYES[region(sheet)])} eyes",
             'style': generators.pick(seed, 'style', list(STYLES.get(data.get('era', ''), STYLES[era]))),
             'detail': generators.pick(seed, 'detail', details)}
    if who == 'man' and generators.unit(seed, 'beard') < mix.beard_share():
        found['beard'] = generators.pick(seed, 'beard-how', list(BEARDS))
    return found


def on_app(sheet: dict, data: dict) -> bool:
    """Whether they are looking at all, from what the sheet has before it is named (names are the slow part)."""
    if sheet.get('notable'):
        return False  # A city's named characters are never on the app.
    seed, is_modern, life = townsfolk.drawn(sheet), townsfolk.modern(data), life_of(sheet, data)
    single = status(seed, life, sheet['desire'], is_modern) in ('single', 'widowed')
    return looking(seed, life, sheet['desire'], single, is_modern, sheet['age']) != 'no'


def details(sheet: dict, data: dict) -> dict:
    """Everything about them that dating needs, the same every time for the same person."""
    seed, who, is_modern = townsfolk.drawn(sheet), gender(sheet), townsfolk.modern(data)
    label, drawn_to = orientation(seed, sheet['age'], who)
    life = life_of(sheet, data)
    state = status(seed, life, sheet['desire'], is_modern)
    after = looking(seed, life, sheet['desire'], state in ('single', 'widowed'), is_modern, sheet['age'])
    low, high = age_range(life, after)  # In human terms, like `suits` reads it.
    return {'gender': who, 'orientation': label, 'drawn_to': drawn_to, 'status': state, 'looking': after,
            'age_range': [low, high], 'life': life, 'picky': round(generators.unit(seed, 'picky'), 3), 'looks': looks(sheet, data)}


# How they come across ------------------------------------------------------------------------------------

def height_text(cm: int, data: dict) -> str:
    if (data.get('country') or '').lower() in ('us', 'united states', 'usa', 'united kingdom', 'uk', 'england',
                                                'britain') or (data.get('country') or '').startswith('United Kingdom'):
        inches = round(cm / 2.54)
        return f"{inches // 12}'{inches % 12}\""
    return f'{cm} cm'


def looks_text(found: dict, data: dict) -> str:
    """'5'9", athletic, short dark brown hair, hazel eyes, freckles; style: streetwear'."""
    parts = [height_text(found['height_cm'], data), found['build'], found['hair'], found['eyes'],
             *([found['beard']] if found.get('beard') else []), found['detail']]
    return f"{', '.join(parts)}; style: {found['style']}"


def job_text(sheet: dict) -> str:
    occupation = sheet.get('occupation') or ''
    if occupation == 'retired':
        return 'Retired'
    if sheet.get('staff'):
        return f"{occupation[0].upper()}{occupation[1:]} at {sheet['place']['name']}"
    return f'{occupation[0].upper()}{occupation[1:]}' if occupation else ''


def haunt_text(sheet: dict) -> str:
    visits = sheet.get('visits')
    if not visits or sheet['place'].get('kind') == 'street':
        return ''
    return f"Find me at {sheet['place']['name']} most {PART_TEXT[visits['part']]}."


def bio(sheet: dict, data: dict, after: str, day: date) -> str:
    """Up to three short lines from what the sheet says about them."""
    seed = townsfolk.drawn(sheet)
    lines = [townsfolk.story(sheet, data, day)['goal']['bio'], townsfolk.quirk_bio(data, sheet['quirk']),
             haunt_text(sheet)]
    if sheet.get('occupation') == 'retired':
        lines.insert(0, 'Retired, and busier than ever.')
    lines = sorted((line for line in lines if line), key=lambda line: generators.unit(seed, 'bio', line))[:3]
    return ' '.join(lines)


def notice(sheet: dict, found: dict, data: dict) -> str:
    """Their notice in a personal column, for older eras: no name, just initials to write to."""
    seed, who, looks_ = townsfolk.drawn(sheet), found['gender'], found['looks']
    word = {'woman': 'LADY', 'man': 'GENTLEMAN', 'nonbinary': 'PERSON'}[who]
    if found['status'] == 'widowed':
        word = {'woman': 'WIDOW', 'man': 'WIDOWER'}.get(who, word)
    tall = next(text for limit, text in COLUMN_HEIGHT if looks_['height_cm'] < limit + (10 if who == 'man' else 0))
    sought = ' or '.join({'woman': 'a lady', 'man': 'a gentleman', 'nonbinary': 'a kindred spirit'}[g]
                         for g in found['drawn_to'][:2])
    trade = f", {sheet['occupation']} by trade" if sheet.get('occupation') not in ('', 'retired', None) else ''
    hood = townsfolk.neighborhood_name(data, sheet['home'])
    quirk = sheet['quirk'].replace('their', 'one\'s').replace('they ', 'one ')
    box = 10 + int(generators.unit(seed, 'box') * 90)
    initials = f"{sheet['name'][:1]}.{(sheet['full'].split()[-1] or ' ')[:1]}."
    return (f"{word}, {sheet['age']}, {tall}, {looks_['hair'].split(',')[0]}{trade}, of {hood}; {quirk}; seeks "
            f"{sought} {SEEKS.get(found['looking'], 'for company')}. Write to ‘{initials}’, Box {box}.")


def card(sheet: dict, data: dict, day: date, found: dict | None = None) -> dict:
    """What the dating screen shows about someone: first name, age, looks, job and bio. Never their family name."""
    found = found or details(sheet, data)
    return {'key': sheet['key'], 'name': sheet['name'], 'age': sheet['age'],
            # A long-lived kind's age in human terms, as matching reads it (`life_of`): an elf of 225 is about 40.
            'life_age': found['life'] if found['life'] != sheet['age'] else None, 'gender': found['gender'],
            'pronouns': sheet.get('pronouns', ''), 'orientation': found['orientation'],
            'looking': found['looking'], 'looking_text': LOOKING_TEXT.get(found['looking'], ''),
            'looks': looks_text(found['looks'], data), 'job': job_text(sheet),
            'neighborhood': townsfolk.neighborhood_name(data, sheet['home']),
            'bio': bio(sheet, data, found['looking'], day),
            'notice': '' if townsfolk.modern(data) else notice(sheet, found, data)}


def likes(sheet: dict, found: dict, profile: dict) -> float:
    """The chance they say yes to the user: pickier people less, a big age gap or a different aim much less."""
    chance = LIKE_BASE - 0.35 * found['picky'] + TEMPER_LIKES.get(sheet['temperament'], 0.0)
    if found['looking'] == 'casual':
        chance += 0.1
    if found['looking'] != profile['looking_for']:
        chance -= 0.2
    chance -= max(0, abs(found.get('life', sheet['age']) - profile['age']) - 5) * 0.02
    return min(max(chance, 0.05), 0.9)


def says_yes(sheet: dict, found: dict, profile: dict) -> bool:
    """Whether they like the user back: their rules and a roll fixed for this person and this user's profile."""
    return generators.unit(townsfolk.drawn(sheet), 'likes-you', profile['seed']) < likes(sheet, found, profile)


def suits(sheet: dict, found: dict, profile: dict) -> bool:
    """Whether they belong in the user's deck: single, looking, adults on both sides and drawn to each other.
    Someone looking for friends meets anyone also looking for friends."""
    if found['looking'] == 'no' or sheet['age'] < 18 or profile['age'] < 18:
        return False
    if not profile['age_min'] <= found.get('life', sheet['age']) <= profile['age_max']:
        return False
    if found['gender'] not in profile['interested_in']:
        return False
    if profile['looking_for'] == 'friends' or found['looking'] == 'friends':
        return found['looking'] == profile['looking_for']
    low, high = found['age_range']
    return profile['gender'] in found['drawn_to'] and low <= profile['age'] <= high
