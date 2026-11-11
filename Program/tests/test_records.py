import json
import threading

from fastapi.testclient import TestClient

from dramatis import library, records, settings
from dramatis.main import create_app
from tests.test_casts import board


def api() -> TestClient:
    return TestClient(create_app())


def test_an_old_file_opens_in_the_current_schema_and_is_written_in_it_on_save():
    library.folder().mkdir(parents=True)
    old = {'id': 'abc123', 'created': '2026-11-01T00:00:00+00:00', 'updated': '2026-11-01T00:00:00+00:00', 'seed': 's',
           'character': {'name': 'Dana', 'intimacy': {'enabled': False}}}
    (library.folder() / 'abc123.json').write_text(json.dumps(old), encoding='utf-8')
    opened = api().get('/api/characters/abc123').json()
    assert opened['character']['name'] == 'Dana' and opened['schema'] == records.schema('character')
    assert opened['revision'] == 0
    saved = api().put('/api/characters/abc123', json={'character': {'name': 'Dana'}, 'revision': 0}).json()
    on_disk = json.loads((library.folder() / 'abc123.json').read_text(encoding='utf-8'))
    assert on_disk['schema'] == records.schema('character') and 'intimacy' not in on_disk['character']
    assert saved['revision'] == on_disk['revision'] == 1


def test_a_file_from_a_newer_dramatis_is_refused_not_changed():
    library.folder().mkdir(parents=True)
    newer = {'id': 'abc123', 'schema': 99, 'updated': '', 'character': {'name': 'Dana', 'later': True}}
    (library.folder() / 'abc123.json').write_text(json.dumps(newer), encoding='utf-8')
    answer = api().get('/api/characters/abc123')
    assert answer.status_code == 409 and 'newer Dramatis' in answer.json()['error']


def test_a_save_from_an_older_revision_is_refused_and_one_without_saves_anyway():
    client = api()
    made = client.post('/api/characters', json={'character': {'name': 'Dana'}}).json()
    first = client.put(f"/api/characters/{made['id']}", json={'character': {'name': 'Dana A'}, 'revision': made['revision']})
    assert first.status_code == 200
    stale = client.put(f"/api/characters/{made['id']}", json={'character': {'name': 'Dana B'}, 'revision': made['revision']})
    assert stale.status_code == 409 and stale.json()['code'] == 'stale' and 'another tab' in stale.json()['error']
    assert client.get(f"/api/characters/{made['id']}").json()['character']['name'] == 'Dana A'
    assert client.put(f"/api/characters/{made['id']}", json={'character': {'name': 'Dana B'}}).status_code == 200


def test_a_cast_save_from_an_older_revision_is_refused():
    client = api()
    cast = board()
    made = client.post('/api/casts', json={'cast': cast}).json()
    assert client.put(f"/api/casts/{made['id']}", json={'cast': cast, 'revision': made['revision']}).status_code == 200
    assert client.put(f"/api/casts/{made['id']}", json={'cast': cast, 'revision': made['revision']}).status_code == 409


def test_saves_at_once_each_write_through_their_own_temporary_file(tmp_path):
    target = tmp_path / 'one.json'
    threads = [threading.Thread(target=records.write, args=(target, f'{{"n": {n}}}'.encode())) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert json.loads(target.read_text())['n'] in range(20)
    assert [path.name for path in tmp_path.iterdir()] == ['one.json']


def test_an_unreadable_character_is_named_and_the_rest_of_the_library_works():
    client = api()
    made = client.post('/api/characters', json={'character': {'name': 'Dana'}}).json()
    (library.folder() / 'broken1.json').write_text('{"id": "broken1", "charac', encoding='utf-8')
    listed = client.get('/api/characters').json()
    assert [item['name'] for item in listed] == ['Dana', 'broken1.json'] and listed[1]['broken'] is True
    answer = client.get('/api/characters/broken1')
    assert answer.status_code == 422 and 'characters/broken1.json' in answer.json()['error']
    assert client.get(f"/api/characters/{made['id']}").status_code == 200


def test_an_unreadable_settings_file_is_kept_aside_and_said_once():
    settings.path().parent.mkdir(parents=True, exist_ok=True)
    settings.path().write_text('{"model": {"profiles": [', encoding='utf-8')
    assert settings.load() == {'model': {}, 'image': {}}
    aside = list(settings.home().glob('settings.unreadable-*.json'))
    assert len(aside) == 1 and aside[0].read_text(encoding='utf-8').startswith('{"model"')
    client = api()
    assert 'kept as' in client.get('/api/health').json()['notice']
    assert client.get('/api/health').json()['notice'] == ''
    settings.save({'image': {'kind': 'off'}})
    assert json.loads(settings.path().read_text(encoding='utf-8'))['image'] == {'kind': 'off'}
