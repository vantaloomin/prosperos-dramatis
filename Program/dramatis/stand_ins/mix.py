"""Stands in for companion/world/mix.py, the sliders a Companion world sets for its people's heights, builds and
beards. Dramatis has no world, so the vendored dating.py gets Companion's built-in mix (its DEFAULTS)."""
DEFAULTS = {'slender': 37.5, 'middle': 37.5, 'heavier': 25, 'beard': 35}


def current() -> dict:
    return DEFAULTS


def height_mean(who: str, built_in: float) -> float:
    return built_in


def builds_changed() -> bool:
    return False


def beard_share() -> float:
    return DEFAULTS['beard'] / 100
