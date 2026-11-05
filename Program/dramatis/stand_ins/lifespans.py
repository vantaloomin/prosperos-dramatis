"""Stands in for companion/world/lifespans.py, which the vendored dating.py and looks.py ask how far through life
someone is. Dramatis hands them an age already in human terms (dramatis/looks.py `life_age`), so everyone here lives a
human lifespan and an age is the age it says."""
HUMAN_LIFESPAN = 80
LONG_LIVED = 150


def lifespan_of(kind: str | None, data: dict | None = None, own: int | None = None) -> int | None:
    return HUMAN_LIFESPAN


def life_age(real: int | None, lifespan: int | None) -> int | None:
    return real


def sheet_lifespan(definition: dict, data: dict | None = None) -> int | None:
    return HUMAN_LIFESPAN
