"""dramatis/library_tools.py and the library's search: duplicate, which casts name someone, back up and bring back,
and a cast file opened as a new cast."""
import base64
import io
import json
import shutil
import zipfile

from fastapi.testclient import TestClient

from dramatis import casts, library
from dramatis.cards import plain_png
from dramatis.character import Character
from dramatis.main import create_app
from tests.test_casts import board


def api() -> TestClient:
    return TestClient(create_app())


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode()


def made(name: str, **more) -> str:
    return library.save(Character(name=name, about=f'{name}, for the test.', **more))['id']


def linked_cast(*ids: str) -> dict:
    """The Salt Crown with the Zealot and the Negotiator played by the characters given, and one relationship."""
    raw = board()
    raw['outer']['corners'][0]['inner']['corners'][0]['character_id'] = ids[0]
    raw['outer']['corners'][1]['inner']['corners'][0]['character_id'] = ids[1]
    raw['relationships'] = [{'from': ids[0], 'to': ids[1], 'dynamic': 'Thinks he is soft.'}]
    return raw


def test_search_finds_by_name_or_any_text_and_never_by_a_field_name():
    made('Ida Brandt', background='Grew up over a bakery in Hamburg.')
    made('Tom Reyes')
    names = lambda search: [item['name'] for item in ok(api().get('/api/characters', params={'search': search}))]  # noqa: E731
    assert names('ida') == ['Ida Brandt']
    assert names('BAKERY hamburg') == ['Ida Brandt']
    assert names('bakery tom') == []
    assert names('background') == []
    assert sorted(names('')) == ['Ida Brandt', 'Tom Reyes']


def test_a_duplicate_has_everything_including_the_portrait_and_is_named_a_copy():
    first = made('Ida Brandt', wants='To leave the bakery.')
    library.set_portrait(first, plain_png((2, 3)))
    copy = ok(api().post(f'/api/library/characters/{first}/duplicate'))
    assert copy['id'] != first and copy['character']['name'] == 'Ida Brandt (copy)'
    assert copy['character']['wants'] == 'To leave the bakery.' and copy['portrait'] is True
    assert library.get(first)['character']['name'] == 'Ida Brandt'
    long = made('A' * 80)
    assert len(ok(api().post(f'/api/library/characters/{long}/duplicate'))['character']['name']) == 80


def test_the_delete_warning_names_the_casts_they_are_in():
    ida, tom, alone = made('Ida'), made('Tom'), made('Alone')
    cast = casts.save(casts.checked(linked_cast(ida, tom)))
    assert ok(api().get(f'/api/library/characters/{ida}/casts')) == [{'id': cast['id'], 'title': 'The Salt Crown'}]
    assert ok(api().get(f'/api/library/characters/{alone}/casts')) == []


def test_a_backup_brings_back_what_is_missing_and_leaves_what_is_here(tmp_path):
    ida, tom = made('Ida'), made('Tom')
    library.set_portrait(ida, plain_png((2, 3)))
    casts.save(casts.checked(linked_cast(ida, tom)))
    response = api().get('/api/library/backup.zip')
    assert response.status_code == 200 and 'Dramatis backup' in response.headers['content-disposition']
    data = response.content
    # Ida is lost with her portrait; Tom is still here and changed since the backup.
    library.path_of(ida).unlink()
    library.path_of(ida, '.png').unlink()
    library.save(Character(name='Tom, renamed'), tom)
    shutil.rmtree(casts.folder())
    found = ok(api().post('/api/library/backup', json={'filename': 'backup.zip', 'data': encoded(data)}))
    assert found == {'characters': 1, 'casts': 1, 'kept': 1, 'skipped': 0}
    assert library.get(ida)['character']['name'] == 'Ida' and library.portrait(ida) == plain_png((2, 3))
    assert library.get(tom)['character']['name'] == 'Tom, renamed'
    assert len(casts.listing()) == 1


def test_a_backup_with_a_broken_or_foreign_file_brings_back_the_rest():
    packed = io.BytesIO()
    good = {'id': 'abc123', 'created': '', 'updated': '', 'seed': 's', 'character': {'name': 'Ida'}, 'schema': 1}
    with zipfile.ZipFile(packed, 'w') as archive:
        archive.writestr('dramatis-backup.json', json.dumps({'format': 'prospero-dramatis-backup', 'version': 1}))
        archive.writestr('characters/abc123.json', json.dumps(good))
        archive.writestr('characters/def456.json', '{not json')
        archive.writestr('characters/ghi789.json', json.dumps(good))  # its id is not its file name
        archive.writestr('../outside.json', json.dumps(good))
    found = ok(api().post('/api/library/backup', json={'filename': 'b.zip', 'data': encoded(packed.getvalue())}))
    assert found == {'characters': 1, 'casts': 0, 'kept': 0, 'skipped': 2}
    assert not (library.folder().parent / 'outside.json').exists()


def test_what_is_not_a_backup_is_refused_in_plain_words():
    refused = api().post('/api/library/backup', json={'filename': 'b.zip', 'data': encoded(b'hello')})
    assert refused.status_code == 422 and 'not a zip' in refused.json()['error']
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, 'w') as archive:
        archive.writestr('other.txt', 'hi')
    refused = api().post('/api/library/backup', json={'filename': 'b.zip', 'data': encoded(packed.getvalue())})
    assert refused.status_code == 422 and 'not a Dramatis backup' in refused.json()['error']


def test_a_cast_file_opens_as_a_new_cast_bringing_in_who_is_missing():
    ida, tom = made('Ida'), made('Tom')
    bundle = casts.export(casts.save(casts.checked(linked_cast(ida, tom)))['id'])
    # Opened in another library, where Ida is already here by id and Tom is not.
    shutil.rmtree(casts.folder())
    library.path_of(tom).unlink()
    found = ok(api().post('/api/library/casts/import', json={
        'filename': 'cast.json', 'data': encoded(json.dumps(bundle).encode())}))
    assert found['added'] == 1
    cast = casts.checked(found['cast']['cast'])
    new_tom = next(item['id'] for item in library.listing() if item['name'] == 'Tom')
    assert set(casts.mentioned(cast)) == {ida, new_tom}
    assert cast.relationships[0].from_id == ida and cast.relationships[0].to_id == new_tom


def test_what_is_not_a_cast_file_is_refused():
    refused = api().post('/api/library/casts/import', json={'filename': 'x.json', 'data': encoded(b'{"format": "x"}')})
    assert refused.status_code == 422 and 'not a cast file' in refused.json()['error']
