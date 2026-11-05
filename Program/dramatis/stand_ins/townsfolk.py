"""Stands in for companion/world/townsfolk.py, which the vendored dating.py asks for a sheet's seed and whether its
era is a modern one."""
MODERN = {'modern', 'future', 'other'}


def drawn(sheet: dict) -> str:
    return sheet.get('seed', sheet['key'])


def modern(data: dict) -> bool:
    return data.get('era', 'modern') in MODERN
