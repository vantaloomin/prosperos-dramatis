"""Stands in for companion/world/couples.py, which the vendored dating.py asks whether someone who started with a
partner is single again by a given day. That needs a town and its weeks; a Dramatis character has neither, so they
keep the status they were given."""


def looking_again(sheet: dict, data: dict, seeded: str, day) -> bool:
    return False
