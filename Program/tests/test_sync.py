import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'sync_format.py'
FORMATS = SCRIPT.parent.parent / 'dramatis' / 'formats'
spec = importlib.util.spec_from_file_location('sync_format', SCRIPT)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def checkout(root: Path, app: str) -> Path:
    """A checkout of one app holding its vendored files as they are vendored now, without the header."""
    for source, name in {**sync.APPS[app]['files'], **sync.APPS[app]['data']}.items():
        text = (FORMATS / app / name).read_text(encoding='utf-8')
        if name.endswith('.py'):
            text = text.split('\n', 1)[1]
            for original, swapped in (('companion.errors', 'dramatis.formats.companion.errors'),):
                text = text.replace(swapped, original)
            text = text.replace('from dramatis.stand_ins import', 'from companion.world import')
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
