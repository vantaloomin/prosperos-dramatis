import importlib.util
import json
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'sync_format.py'
FORMATS = SCRIPT.parent.parent / 'dramatis' / 'formats'
spec = importlib.util.spec_from_file_location('sync_format', SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def unvendored(text: str, app: str) -> str:
    """A vendored module as the app has it: its header off and its imports pointed back at the app's own modules."""
    text = re.sub(r'\A(?:# (?:Vendored from|Edit it there).*\n)+', '', text)
    back = {place: module for module, place in sync.APPS[app]['modules'].items()}

    def line(match: re.Match) -> str:
        module, names, indent = match['module'], match['names'], match['indent']
        if module in back:
            return f'{indent}from {back[module]} import {names}'
        places: dict[str, list[str]] = {}
        for name in (item.strip() for item in names.strip('()').split(',')):
            places.setdefault(back[f"{module}.{name.split(' as ')[0]}"].rpartition('.')[0], []).append(name)
        return '\n'.join(f"{indent}from {place} import {', '.join(found)}" for place, found in places.items())

    return re.sub(r'^(?P<indent>[ \t]*)from (?P<module>dramatis\.(?:formats|stand_ins)[\w.]*) import (?P<names>.+)$', line,
                  text, flags=re.M)


def checkout(root: Path, app: str) -> Path:
    """A checkout of one app holding its vendored files as they are vendored now, as the app has them."""
    parts = {source: target for source, (target, _names) in sync.APPS[app]['parts'].items()}
    for source, name in {**sync.APPS[app]['files'], **parts, **sync.APPS[app]['data']}.items():
        text = (FORMATS / app / name).read_text(encoding='utf-8')
        if name.endswith('.py'):
            text = unvendored(text, app)
        (root / source).parent.mkdir(parents=True, exist_ok=True)
        (root / source).write_text(text, encoding='utf-8')
    return root


def test_the_vendored_copies_say_where_they_came_from():
    sources = json.loads((FORMATS / 'SOURCE.json').read_text(encoding='utf-8'))
    assert set(sources) == set(sync.APPS)
    for app, found in sources.items():
        for name in found['files'].values():
            assert (FORMATS / app / name).is_file()


def test_check_passes_when_nothing_moved_and_fails_on_drift(tmp_path, capsys):
    root = checkout(tmp_path / 'companion', 'companion')
    assert sync.main(['--companion', str(root), '--check'], target=FORMATS) == 0
    models = root / 'Program/companion/models.py'
    models.write_text(models.read_text(encoding='utf-8') + '\n# moved on\n', encoding='utf-8')
    assert sync.main(['--companion', str(root), '--check'], target=FORMATS) == 1
    assert 'companion/models.py' in capsys.readouterr().err


def test_syncing_writes_the_copies_and_stamps_the_source(tmp_path):
    root = checkout(tmp_path / 'dungeon', 'dungeon')
    target = tmp_path / 'formats'
    assert sync.main(['--dungeon', str(root)], target=target) == 0
    assert (target / 'dungeon/models.py').read_text(encoding='utf-8').startswith('# Vendored from vantaloomin/')
    assert json.loads((target / 'SOURCE.json').read_text(encoding='utf-8'))['dungeon']['commit'] == 'unknown'


def test_an_import_that_is_not_vendored_stops_the_sync(tmp_path):
    root = checkout(tmp_path / 'companion', 'companion')
    errors = root / 'Program/companion/errors.py'
    errors.write_text('from companion.database import optional\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='not vendored'):
        sync.main(['--companion', str(root)], target=tmp_path / 'formats')


def test_one_import_of_modules_from_two_places_becomes_a_line_for_each():
    line = '    from companion.world import catalog, dating, intimacy\n'
    found = sync.IMPORT.sub(lambda match: sync.swap(match, sync.APPS['companion']['modules'], 'x.py'), line)
    assert found == ('    from dramatis.formats.companion import catalog, dating\n'
                     '    from dramatis.stand_ins import intimacy\n')


SOURCE = """import hashlib
import json
from functools import cache

from companion.world import catalog, naming


def unused():
    return json.dumps({})


# Seeded, so the same seed draws the same.
@cache
def drawn(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest() + catalog.DATA.name


LIMIT = 3
"""


def test_a_part_is_the_named_definitions_as_written_with_the_imports_they_use():
    assert sync.part(SOURCE, ('drawn', 'LIMIT'), 'x.py') == """import hashlib
from functools import cache
from companion.world import catalog


# Seeded, so the same seed draws the same.
@cache
def drawn(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest() + catalog.DATA.name


LIMIT = 3
"""
    with pytest.raises(SystemExit, match='no longer defines gone'):
        sync.part(SOURCE, ('drawn', 'gone'), 'x.py')


def test_a_part_that_moved_on_is_drift(tmp_path, capsys):
    root = checkout(tmp_path / 'companion', 'companion')
    generators = root / 'Program/companion/world/generators.py'
    generators.write_text(generators.read_text(encoding='utf-8').replace('2 ** 64', '2 ** 63'), encoding='utf-8')
    assert sync.main(['--companion', str(root), '--check'], target=FORMATS) == 1
    assert 'companion/generators.py' in capsys.readouterr().err
