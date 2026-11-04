import base64
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from dramatis import ai, images, portraits
from dramatis.cards import PLAIN_SIZE
from dramatis.character import Character
from dramatis.formats.companion.images.adapters.comfyui import ComfyAdapter
from dramatis.formats.companion.images.adapters.hosted import HostedAdapter
from dramatis.main import create_app

PRIVATE = {'seen_as': 'People think she is cold', 'sees_self': 'I am the only grown-up here',
           'background': 'Her father left when she was nine'}
DANA = {'name': 'Dana Okafor', 'gender': 'woman', 'age': 38, 'setting': 'Baltimore, today',
        'about': 'An ER nurse.', 'personality': 'Steady at work, scattered at home.',
        'appearance': 'Tall and broad-shouldered, cropped grey-streaked hair.',
        'looks': {'height_cm': 180, 'eyes': 'dark brown', 'feature': 'a chipped front tooth'}} | PRIVATE
DRAWN = 'A tall broad-shouldered woman in her late thirties, waist-up, three-quarter view, plain grey background.'


def picture(size=(1024, 1536), kind='PNG') -> bytes:
    out = io.BytesIO()
    Image.new('RGB', size, (120, 90, 80)).save(out, kind)
    return out.getvalue()


@pytest.fixture
def keys(monkeypatch):
    """A keyring of its own, so no test reads or writes the user's."""
    found = {}
    monkeypatch.setattr(ai, 'api_key', lambda name: found.get(name, ''))
    monkeypatch.setattr(ai, 'store_key', lambda name, key: found.update({name: key}))
    return found


@pytest.fixture
def maker(monkeypatch, keys):
    """A stand-in image maker behind Companion's own adapters: answers each request with `maker.handle(request)` and
    keeps what it was sent."""
    class Maker:
        def __init__(self):
            self.sent, self.handle = [], None

        def transport(self, request: httpx.Request) -> httpx.Response:
            self.sent.append(request)
            return self.handle(request)

    found = Maker()
    mock = httpx.MockTransport(found.transport)
    made = {'comfyui': lambda: ComfyAdapter(transport=mock, poll_seconds=0), 'hosted': lambda: HostedAdapter(transport=mock)}
    monkeypatch.setattr(images, 'adapter', lambda kind: made[kind]())
    return found


def api() -> TestClient:
    return TestClient(create_app())


def test_the_prompt_holds_what_a_portrait_shows_and_nothing_private():
    found = portraits.facts(Character.model_validate(DANA))
    assert 'Tall and broad-shouldered' in found and '180 cm' in found and 'a chipped front tooth' in found
    assert '- Age: 38' in found and 'Baltimore, today' in found and 'Steady at work' in found
    assert 'Dana' not in found and not any(text in found for text in PRIVATE.values())


def test_image_settings_are_off_until_set_and_keep_the_key_out_of_the_file(keys):
    found = api().get('/api/images').json()
    assert found['kind'] == 'off' and found['ready'] is False
    assert found['families']['krea2'] == 'Krea 2' and found['providers']['openai']['base_url'] == 'https://api.openai.com/v1'
    assert api().put('/api/images', json={'kind': 'hosted', 'provider': 'openai'}).json()['ready'] is False
    saved = api().put('/api/images', json={'kind': 'hosted', 'provider': 'openai', 'model': 'gpt-image-1',
                                           'base_url': 'https://api.openai.com/v1/images/generations', 'key': 'sk-test'}).json()
    assert {key: saved[key] for key in ('kind', 'provider', 'base_url', 'model', 'has_key', 'ready')} == {
        'kind': 'hosted', 'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-image-1',
        'has_key': True, 'ready': True}
    assert keys == {'image-api': 'sk-test'} and 'sk-test' not in (images.settings.path()).read_text()
    local = api().put('/api/images', json={'kind': 'comfyui', 'family': 'booru'}).json()
    assert local['base_url'] == 'http://127.0.0.1:8188' and local['ready'] is True
    assert api().put('/api/images', json={'kind': 'comfyui', 'family': 'dall-e'}).status_code == 422
    assert api().put('/api/images', json={'kind': 'hosted', 'provider': 'other', 'base_url': 'http://example.com/v1'}).status_code == 422


def test_make_a_portrait_draws_a_card_sized_png_and_saves_nothing(model, maker):
    images.configure('hosted', 'openai', model='gpt-image-1', key='sk-test')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(picture(kind='JPEG')).decode()}]})
    made = api().post('/api/characters', json={'character': DANA}).json()
    found = api().post(f"/api/characters/{made['id']}/portrait/make", json={'style': 'painted'}).json()

    assert found['prompt'].startswith(DRAWN) and found['prompt'].endswith('muted colours.')
    sent = json.loads(maker.sent[0].content)
    assert str(maker.sent[0].url) == 'https://api.openai.com/v1/images/generations'
    assert sent == {'prompt': f"{found['prompt']}\nAvoid: {images.NEGATIVE}", 'model': 'gpt-image-1', 'n': 1,
                    'size': '1024x1536'}
    assert maker.sent[0].headers['authorization'] == 'Bearer sk-test'
    with Image.open(io.BytesIO(base64.b64decode(found['image']))) as drawn:
        assert drawn.format == 'PNG' and drawn.size == PLAIN_SIZE
    system, _ = model.asked[0]
    assert not any(text in system for text in PRIVATE.values()) and 'Dana' not in system
    assert api().get(f"/api/characters/{made['id']}").json()['portrait'] is False

    # Use this: the existing portrait route saves the picture as it came back.
    used = api().put(f"/api/characters/{made['id']}/portrait", json={'filename': 'portrait.png', 'data': found['image']})
    assert used.json()['portrait'] is True
    assert api().get(f"/api/characters/{made['id']}/portrait.png").content == base64.b64decode(found['image'])
    assert api().get('/api/characters').json()[0]['portrait'] is True


def test_an_unsaved_character_gets_a_portrait_from_the_form(model, maker):
    images.configure('hosted', 'openrouter', model='some/image-model', key='sk-or')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(picture()).decode()}]})
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 200 and found.json()['prompt'] == DRAWN
    assert str(maker.sent[0].url) == 'https://openrouter.ai/api/v1/images'
    assert json.loads(maker.sent[0].content)['aspect_ratio'] == '2:3'


def test_comfyui_runs_companions_workflow_for_the_family(model, maker):
    images.configure('comfyui', family='krea2', model='krea2-mine.safetensors')
    model.replies = [json.dumps({'prompt': DRAWN})]
    polls = iter([{}, {'job-1': {'status': {'completed': True},
                                 'outputs': {'9': {'images': [{'filename': 'p_0001.png', 'subfolder': ''}]}}}}])

    def handle(request):
        if request.url.path == '/prompt':
            return httpx.Response(200, json={'prompt_id': 'job-1'})
        if request.url.path == '/history/job-1':
            return httpx.Response(200, json=next(polls))
        assert request.url.path == '/view' and request.url.params['filename'] == 'p_0001.png'
        return httpx.Response(200, content=picture((832, 1216)))

    maker.handle = handle
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': 'photo'})
    assert found.status_code == 200
    assert str(maker.sent[0].url) == 'http://127.0.0.1:8188/prompt'
    nodes = json.loads(maker.sent[0].content)['prompt'].values()
    assert any(node['inputs'].get('unet_name') == 'krea2-mine.safetensors' for node in nodes)
    texts = [node['inputs'].get('text') for node in nodes if isinstance(node['inputs'].get('text'), str)]
    assert found.json()['prompt'] in texts
    assert any(node['inputs'].get('width') == 832 and node['inputs'].get('height') == 1216 for node in nodes)


def test_a_provider_error_comes_back_as_a_plain_message(model, maker):
    images.configure('hosted', 'openai', model='gpt-image-1', key='sk-test')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(400, json={'error': {'message': 'Rejected by our safety system.'}})
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 422 and found.json()['code'] == 'image_refused'
    assert 'content rules' in found.json()['error'] and 'Rejected by our safety system.' in found.json()['error']

    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: (_ for _ in ()).throw(httpx.ConnectError('refused'))
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 502 and 'reach the provider' in found.json()['error']


def test_check_asks_comfyui_what_it_has_without_drawing(maker):
    images.configure('comfyui', family='krea2')
    maker.handle = lambda request: httpx.Response(200, json={})
    found = api().post('/api/images/check').json()
    assert found['ok'] is False and found['details'] and all(request.url.path == '/object_info' for request in maker.sent)


def test_an_unsafe_prompt_goes_back_once_then_is_refused(model, maker):
    images.configure('hosted', 'openai', model='gpt-image-1', key='sk-test')
    model.replies = [json.dumps({'prompt': 'A topless woman'}), json.dumps({'prompt': 'A seductive woman'})]
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 502 and 'seductive' in found.json()['error'] and maker.sent == []
    assert 'topless' in model.asked[1][1]


def test_nothing_is_asked_until_an_image_maker_is_set(model, keys):
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 409 and model.asked == []
    assert api().post('/api/portrait/make', json={'character': DANA, 'style': 'cubist'}).status_code == 422
    assert [style['name'] for style in api().get('/api/portrait/styles').json()][0] == 'Photo'
