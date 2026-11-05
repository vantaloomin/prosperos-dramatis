# Vendored from vantaloomin/prosperos-companion Program/companion/world/generators.py by scripts/sync_format.py: only unit, pick, PRONOUNS, GIVEN, seeded_pronouns, name, group_of, kind_of, drawn, _feminine_family, _family, _given_for, with the imports they use.
# Edit it there, then sync.
import hashlib
from dramatis.formats.companion import catalog, naming
from dramatis.stand_ins import lifespans
from dramatis.stand_ins import mix as town_mix


def unit(seed: str, *parts) -> float:
    """A stable number in [0, 1) for this seed and label."""
    digest = hashlib.sha256('\x1f'.join(map(str, (seed, *parts))).encode()).digest()
    return int.from_bytes(digest[:8], 'big') / 2 ** 64


def pick(seed: str, label: str, items: list, weights: list[float] | None = None):
    """Weighted choice that depends only on the seed, the label and the order of `items`."""
    if not items:
        return None
    weights = weights or [1.0] * len(items)
    total = sum(weights)
    target, running = unit(seed, label) * total, 0.0
    for item, weight in zip(items, weights, strict=True):
        running += weight
        if target < running:
            return item
    return items[-1]


PRONOUNS = {'she': 'she/her', 'he': 'he/him', 'they': 'they/them'}


GIVEN = {'she': 'feminine', 'he': 'masculine'}


def seeded_pronouns(data: dict, seed: str, group: str | None = None) -> str:
    """The pronouns `name` gives this seed when none are asked for: 'she', 'he' or 'they'. A kind whose city entry
    gives its own `pronouns` weights uses those (Grandport's elves are mostly women)."""
    own = lifespans.pronoun_weights(data, kind_of(data, seed, group)) if data.get('kinds') else None
    modern = data['era'] in ('modern', 'future', 'other')
    return pick(seed, 'pronouns', ['she', 'he', 'they'], own or town_mix.pronoun_weights(modern))


def name(data: dict, *, seed: str, pronouns: str | None = None, group: str | None = None,
         family: str | None = None, age: int | None = None, avoid=()) -> dict:
    """A resident's name from the city's name groups. `family` keeps a relative's family name.

    In modern settings a group linked to cultures takes the given name from what babies were called around
    the person's birth year (`age` years before the data's present year; a seeded adult age without one),
    and the family name from that culture when it lists its own.

    Someone unrelated (no `family`) never gets a family name in `avoid` or in the city's `kin` (the
    companion's own and their relatives', set by companion/life/network.py): only that family name is drawn
    again, from the same seed, so everyone else's name stays as it was.
    """
    groups, mix = catalog.name_groups(data)
    group = group_of(data, seed, group)
    names = groups[group]
    if pronouns not in PRONOUNS:
        pronouns = seeded_pronouns(data, seed, group)
    links = naming.links(names, data)
    if family and not names.get('own_family'):
        # A relative's given name comes from a culture that fits the family name they share.
        links = {key: weight for key, weight in links.items() if not naming.culture(key)['surnames']
                 or naming.base_family(key, family) in naming.culture_surnames(key)}
    culture = pick(seed, 'culture', list(links), list(links.values())) if links else None
    if culture:
        age = age if age is not None else 22 + round(unit(seed, 'name-age') * 42)
        given = _given_for(seed, culture, naming.present_year(data) - age, pronouns)
    else:
        pools = [names[GIVEN[pronouns]]] if pronouns in GIVEN else [names['neutral']]
        if names['neutral'] and unit(seed, 'neutral-name') < 0.12:
            pools.insert(0, names['neutral'])
        pools += [names['feminine'] + names['masculine'] + names['neutral']]
        given = pick(seed, 'given', next(pool for pool in pools if pool))
    if family:
        family = naming.gendered(culture, naming.base_family(culture, family), pronouns) if culture else family
    else:
        avoid = {item.casefold() for item in (*avoid, *data.get('kin', ()))}
        family = _family(seed, culture, pronouns, names, groups, mix)
        for attempt in range(1, 9):
            if not family or not avoid & {family.casefold(), naming.base_family(culture, family).casefold()}:
                break
            family = _family(f'{seed}:family:{attempt}', culture, pronouns, names, groups, mix)
    if pronouns == 'she':
        family = _feminine_family(family, names)
    return {'given': given, 'family': family, 'full': f'{given} {family}', 'pronouns': PRONOUNS[pronouns],
            'group': group, 'culture': culture}


def group_of(data: dict, seed: str, group: str | None = None) -> str:
    """The name group a resident's name comes from (`name`): `group` when the city has it, else drawn by the seed
    from the groups their kind is named from (`kind_of`)."""
    return drawn(data, seed, group)[0]


def kind_of(data: dict, seed: str, group: str | None = None) -> str:
    """A resident's kind (companion/world/lifespans.py): `group`'s when given, else rolled from the shares the city's
    `kinds` block gives each kind (humans the rest), else their drawn name group's."""
    return drawn(data, seed, group)[1]


def drawn(data: dict, seed: str, group: str | None = None) -> tuple[str, str]:
    """(name group, kind) for a seed. A city without kind shares draws the group from the whole mix, as before shares
    existed; with them, the kind comes first and the group from that kind's own (a human keeps the group they had
    when the mix has no kind-tied groups)."""
    groups, mix = catalog.name_groups(data)
    if group in groups:
        return group, lifespans.of_group(data, group)
    shares = lifespans.shares(data)
    if not shares:
        group = pick(seed, 'name-group', list(mix), list(mix.values()))
        return group, lifespans.of_group(data, group)
    kind, mark = lifespans.HUMAN, unit(seed, 'folk-kind')
    for key, share in shares.items():
        if mark < share:
            kind = key
            break
        mark -= share
    weights = lifespans.groups_for(data, kind)
    return pick(seed, 'name-group', list(weights), list(weights.values())), kind


def _feminine_family(family: str, names: dict) -> str:
    for ending, feminine in (names.get('feminine_family') or {}).items():
        if family.endswith(ending):
            return family[:-len(ending)] + feminine
    return family


def _family(seed: str, culture: str | None, pronouns: str, names: dict, groups: dict, mix: dict) -> str:
    surnames = naming.culture(culture)['surnames'] if culture and not names.get('own_family') else []
    if surnames:
        family = pick(seed, 'family', surnames, naming.rank_weights(surnames))
        return naming.gendered(culture, naming.base_family(culture, family), pronouns)
    # Most residents' family names come from the same heritage group; some from anywhere in the city.
    # From people of their own kind: a human isn't a Hrívë Court elf's namesake.
    same = {key: weight for key, weight in mix.items() if groups[key].get('kind') == names.get('kind')} or mix
    other = pick(seed, 'family-group', list(same), list(same.values()))
    return pick(seed, 'family', names['family'] if unit(seed, 'mixed') >= 0.2 else groups[other]['family'])


def _given_for(seed: str, culture: str, born: int, pronouns: str) -> str:
    """A given name popular within a few years of `born`, ranked by popularity."""
    year = born + round((unit(seed, 'birth-year') * 2 - 1) * naming.SPREAD)
    found = naming.cohort(culture, year)
    if pronouns in GIVEN:
        pool = found[GIVEN[pronouns]]
    else:
        # Names given to both girls and boys that year, else the name they were given at birth from either list.
        shared = [item for item in found['feminine'] if item in set(found['masculine'])]
        pool = shared or found[pick(seed, 'neutral-list', ['feminine', 'masculine'])]
    return pick(seed, 'given', pool, naming.rank_weights(pool))
