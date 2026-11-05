"""Stands in for companion/world/decades.py, which the vendored naming.py asks for the past year a modern world runs
in. Dramatis has no world clock: a draft's own year, when its setting gives one, rides in as the place's `names.year`
(dramatis/names.py), which naming.py reads after this."""


def year_of(city: dict | None) -> int | None:
    return None
