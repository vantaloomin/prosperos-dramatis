# Vendored from vantaloomin/prosperos-companion Program/companion/world/catalog.py by scripts/sync_format.py: only DATA, names, name_groups, with the imports they use.
# Edit it there, then sync.
from functools import cache
from pathlib import Path
from dramatis.formats.companion.schema import Names


DATA = Path(__file__).parent / 'data'


@cache
def names() -> dict:
    """The shared name banks and each era's default bank and group weights."""
    return Names.model_validate_json((DATA / 'names.json').read_text(encoding='utf-8')).model_dump()


def name_groups(data: dict) -> tuple[dict[str, dict], dict[str, float]]:
    """The name groups a city draws residents' names from, and the weight of each.

    A city's own `names.mix` wins; a city with its own groups and no mix uses only those; otherwise the era's
    weights apply when the city keeps its era's bank, else every group of the bank weighs the same.
    """
    own = data.get('names') or {}
    era = names()['eras'][data['era']]
    bank = own.get('bank') or era['bank']
    groups = names()['banks'][bank] | own.get('groups', {})
    if own.get('mix'):
        mix = own['mix']
    elif own.get('groups'):
        mix = dict.fromkeys(own['groups'], 1.0)
    elif bank == era['bank'] and era['mix']:
        mix = era['mix']
    else:
        mix = {}
    # Weights for groups the bank lacks (say, after a city changes era) are ignored.
    mix = {key: weight for key, weight in mix.items() if weight > 0 and key in groups}
    return groups, mix or dict.fromkeys(groups, 1.0)
