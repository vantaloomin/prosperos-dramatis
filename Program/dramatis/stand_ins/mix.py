"""Stands in for companion/world/mix.py, the sliders a Companion world sets for its people's pronouns, heights, builds
and beards. Dramatis has no world, so the vendored dating.py and generators.name get Companion's built-in mix (its
DEFAULTS)."""
DEFAULTS = {'nonbinary': 6, 'women': 50, 'slender': 37.5, 'middle': 37.5, 'heavier': 25, 'beard': 35}


def current() -> dict:
    return DEFAULTS


def height_mean(who: str, built_in: float) -> float:
    return built_in


def builds_changed() -> bool:
    return False


def beard_share() -> float:
    return DEFAULTS['beard'] / 100


def pronoun_weights(modern: bool) -> list[float]:
    """She, he and they: 47, 47 and 6 in modern worlds and 2 in older eras, as Companion has them built in."""
    nonbinary = DEFAULTS['nonbinary'] if modern else DEFAULTS['nonbinary'] / 3
    rest = 100 - DEFAULTS['nonbinary']
    return [rest * DEFAULTS['women'] / 100, rest * (100 - DEFAULTS['women']) / 100, nonbinary]
