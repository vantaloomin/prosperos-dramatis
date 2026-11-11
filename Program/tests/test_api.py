import base64
import json

from fastapi.testclient import TestClient

from dramatis.cards import plain_png
from dramatis.formats.companion.imports import cards as reader
from dramatis.main import create_app
from tests.helpers import SLEEP, reply

CHARACTER = {'name': 'Dana Okafor', 'gender': 'woman', 'age': 38, 'about': 'An ER nurse.', 'personality': 'Steady.',
             'voice': 'Short sentences.', 'sound': 'A low alto.',
             'interests': ['duckpin bowling'], 'companion': {'schedule': [SLEEP]}}


def client() -> TestClient:
    return TestClient(create_app())


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_health_names_the_vendored_formats():
    found = client().get('/api/health').json()
    assert found['ok'] and set(found['formats']) == {'companion', 'adventure', 'dungeon'}


def test_a_character_is_saved_listed_changed_and_deleted():
    api = client()
    made = api.post('/api/characters', json={'character': CHARACTER}).json()
    assert made['problems'] == {} and made['character']['apps'] == ['companion', 'adventure', 'dungeon']
    assert [item['name'] for item in api.get('/api/characters').json()] == ['Dana Okafor']
    changed = api.put(f"/api/characters/{made['id']}", json={'character': CHARACTER | {'name': 'Dana Price'}}).json()
    assert changed['id'] == made['id'] and changed['character']['name'] == 'Dana Price'
    assert api.delete(f"/api/characters/{made['id']}").json() == {'ok': True}
    assert api.get(f"/api/characters/{made['id']}").status_code == 404
    assert api.get('/api/characters/..%2Fsettings').status_code == 404


def test_a_bad_form_names_the_field():
    found = client().post('/api/check', json={'character': CHARACTER | {'age': 12}})
    assert found.status_code == 422 and found.json()['error'].startswith('age:')


def test_cards_carry_every_apps_shape_and_come_back_whole():
    api = client()
    made = api.post('/api/characters', json={'character': CHARACTER}).json()
    full = api.get(f"/api/characters/{made['id']}/card.json").json()
    assert full['spec'] == 'chara_card_v3' and full['data']['name'] == 'Dana Okafor'
    assert full['data']['description'] == ('An ER nurse.\n\nGender: woman\n\nAge: 38\n\nHow they talk: Short sentences.'
                                           '\n\nHow they sound: A low alto.\n\nInterests: duckpin bowling')
    assert full['data']['tags'] == []
    extension = full['data']['extensions']['prospero']
    assert extension['format'] == 'prospero-character' and set(extension['apps']) == {'companion', 'adventure', 'dungeon'}
    assert extension['apps']['companion']['identity'] == 'An ER nurse.'

    portrait = api.put(f"/api/characters/{made['id']}/portrait", json={'filename': 'p.png', 'data': encoded(plain_png((2, 3)))})
    assert portrait.json()['portrait'] is True
    png = api.get(f"/api/characters/{made['id']}/card.png")
    assert png.headers['content-disposition'] == 'attachment; filename="Dana Okafor (Prospero).png"'
    # Any card reader finds the V3 card, and the V2 copy for older ones.
    assert json.loads(reader.embedded_card(png.content))['spec'] == 'chara_card_v3'
    texts = {payload.partition(b'\0')[0] for kind, payload in reader.chunks(png.content) if kind == b'tEXt'}
    assert texts == {b'chara', b'ccv3'}
    opened = api.post('/api/cards/open', json={'filename': 'Dana.png', 'data': encoded(png.content)}).json()
    assert opened['kind'] == 'character' and opened['character']['name'] == 'Dana Okafor'


def test_the_chat_app_card_leaves_the_prospero_part_out():
    api = client()
    made = api.post('/api/characters', json={'character': CHARACTER}).json()
    chat = api.get(f"/api/characters/{made['id']}/card.json?for=chat")
    assert chat.headers['content-disposition'] == 'attachment; filename="Dana Okafor.json"'
    assert chat.json()['data']['extensions'] == {} and 'Sleep' not in chat.text
    png = api.get(f"/api/characters/{made['id']}/card.png?for=chat")
    assert png.status_code == 200 and b'prospero' not in png.content
    # Without the extension it is any other app's card to Dramatis, read from its headed description.
    opened = api.post('/api/cards/open', json={'filename': 'Dana.png', 'data': encoded(png.content)}).json()
    assert opened['kind'] == 'file' and opened['name'] == 'Dana Okafor'
    assert opened['character']['voice'] == 'Short sentences.' and opened['character']['age'] == 38
    assert api.get(f"/api/characters/{made['id']}/card.json?for=tavern").status_code == 422


def test_another_apps_card_opens_as_text_for_the_paste_box_and_as_a_form():
    card = {'spec': 'chara_card_v2', 'data': {'name': 'Mira', 'description': '{{char}} runs a ferry.'}}
    found = client().post('/api/cards/open', json={'filename': 'mira.json', 'data': encoded(json.dumps(card).encode())})
    opened = found.json()
    assert {key: opened[key] for key in ('kind', 'format', 'name', 'text', 'truncated')} == {
        'kind': 'file', 'format': 'Character Card V2', 'name': 'Mira',
        'text': 'Name: Mira\n\nDescription:\nMira runs a ferry.', 'truncated': False}
    assert opened['character']['background'] == 'Mira runs a ferry.' and opened['card'] is None


def test_portraits_are_pngs():
    api = client()
    made = api.post('/api/characters', json={'character': CHARACTER}).json()
    refused = api.put(f"/api/characters/{made['id']}/portrait", json={'filename': 'p.jpg', 'data': encoded(b'\xff\xd8')})
    assert refused.status_code == 422


def test_sliders_follow_companions_rules():
    api = client()
    found = api.post('/api/sliders', json={'character': {'about': 'A shy nurse.'}, 'seed': 'abc'}).json()
    assert found['sliders']['social'] == {'level': 0, 'source': 'idea'}
    assert [trait['key'] for trait in found['traits']] == ['social', 'warmth', 'order', 'curiosity', 'stress']
    typed = api.post('/api/sliders', json={'character': {}, 'seed': 'abc', 'type': 'ENFJ'}).json()
    assert typed['type'] == 'ENFJ'
    assert api.post('/api/sliders', json={'character': {}, 'type': 'QQQQ'}).status_code == 422

    still = api.post('/api/sliders', json={'character': {'about': 'A shy nurse.'}, 'seed': 'abc', 'still': True}).json()
    assert still['sliders']['social'] == {'level': 0, 'source': 'idea'}
    assert {key: value['level'] for key, value in still['sliders'].items() if key != 'social'} == dict.fromkeys(
        ['warmth', 'order', 'curiosity', 'stress'], 1)
    kept = {'social': {'level': 2, 'source': 'rolled'}}
    stored = api.post('/api/sliders', json={'character': {'personality_sliders': kept}, 'still': True}).json()
    assert stored['sliders']['social'] == {'level': 2, 'source': 'rolled'}


def test_the_audit_reads_only_what_a_model_wrote():
    api = client()
    mara = CHARACTER | {'name': 'Mara Quill', 'about': 'Mara Quill keeps the lighthouse.'}
    every = api.post('/api/check', json={'character': mara}).json()['audit']
    assert {hit['field'] for hit in every} >= {'name'}
    brought = api.post('/api/check', json={'character': mara, 'fields': []}).json()['audit']
    assert brought == []
    theirs = api.post('/api/check', json={'character': mara, 'allowed': 'Her name is Mara Quill.'}).json()['audit']
    assert not [hit for hit in theirs if hit['match'].strip() == 'Quill']


def test_drafting_through_the_api(model):
    model.replies = [reply()]
    found = client().post('/api/draft', json={'idea': 'a nurse', 'apps': ['dungeon']}).json()
    assert found['character']['name'] == 'Dana Okafor' and found['character']['apps'] == ['dungeon']
    assert client().post('/api/draft', json={'age': 15}).status_code == 422


def test_a_character_whose_file_is_in_use_is_not_deleted_and_says_why(monkeypatch):
    from pathlib import Path
    client = TestClient(create_app())
    made = client.post('/api/characters', json={'character': {'name': 'Dana'}}).json()

    def locked(self, missing_ok=False):
        raise PermissionError('in use')
    monkeypatch.setattr(Path, 'unlink', locked)
    answer = client.delete(f"/api/characters/{made['id']}")
    assert answer.status_code == 409 and 'another program' in answer.json()['error']
