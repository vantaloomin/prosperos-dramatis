"""Stands in for companion/world/intimacy.py, which Companion's models.py asks whether an entry on a character's adult
side is allowed. Dramatis does not make the adult side (each app sets it up under its own settings) and leaves
`intimacy` out of every character it checks, so this refuses every entry: it fails closed."""


def allowed(text: str) -> bool:
    return False
