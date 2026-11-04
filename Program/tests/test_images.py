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
    """A stand-in image maker: answers each request with `maker.handle(request)` and keeps what it was sent."""
    class Maker:
        def __init__(self):
            self.sent, self.handle = [], None

        def transport(self, request: httpx.Request) -> httpx.Response:
            self.sent.append(request)
            return self.handle(request)

    found = Maker()
    monkeypatch.setattr(images, 'client', lambda: httpx.Client(transport=httpx.MockTransport(found.transport)))
    monkeypatch.setattr(images, 'POLL_SECONDS', 0)
    return found


def api() -> TestClient:
    return TestClient(create_app())


def test_the_prompt_holds_what_a_portrait_shows_and_nothing_private():
    found = portraits.facts(Character.model_validate(DANA))
    assert 'Tall and broad-shouldered' in found and '180 cm' in found and 'a chipped front tooth' in found
    assert '- Age: 38' in found and 'Baltimore, today' in found and 'Steady at work' in found
    assert 'Dana' not in found and not any(text in found for text in PRIVATE.values())


def test_image_settings_are_off_until_set_and_keep_the_key_out_of_the_file(keys):
    assert api().get('/api/images').json()['ready'] is False
    refused = api().put('/api/images', json={'provider': 'comfyui', 'base_url': 'http://127.0.0.1:8188'})
    assert refused.status_code == 422 and 'checkpoint' in refused.json()['error']
    saved = api().put('/api/images', json={'provider': 'openai', 'base_url': 'https://api.openai.com/v1/images/generations',
                                           'model': 'gpt-image-1', 'key': 'sk-test'}).json()
    assert saved == {'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-image-1', 'size': '',
                     'has_key': True, 'ready': True}
    assert keys == {'image-openai': 'sk-test'}
    assert api().put('/api/images', json={'provider': 'openai', 'base_url': 'https://x.test', 'size': 'big'}).status_code == 422


def test_make_a_portrait_draws_a_card_sized_png_and_saves_nothing(model, maker):
    images.configure('openai', 'https://api.openai.com/v1', 'gpt-image-1', key='sk-test')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(picture(kind='JPEG')).decode()}]})
    made = api().post('/api/characters', json={'character': DANA}).json()
    found = api().post(f"/api/characters/{made['id']}/portrait/make", json={'style': 'painted'}).json()

    assert found['prompt'].startswith(DRAWN) and found['prompt'].endswith('muted colours.')
    sent = json.loads(maker.sent[0].content)
    assert str(maker.sent[0].url) == 'https://api.openai.com/v1/images/generations'
    assert sent == {'prompt': found['prompt'], 'model': 'gpt-image-1', 'n': 1, 'size': '1024x1536'}
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
    images.configure('openai', 'https://openrouter.ai/api/v1', 'some/image-model')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(200, json={'data': [{'b64_json': base64.b64encode(picture()).decode()}]})
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 200 and found.json()['prompt'] == DRAWN
    assert str(maker.sent[0].url) == 'https://openrouter.ai/api/v1/images'
    assert json.loads(maker.sent[0].content)['aspect_ratio'] == '2:3'


def test_comfyui_runs_the_bundled_workflow(model, maker):
    images.configure('comfyui', 'http://127.0.0.1:8188', 'sd_xl_base_1.0.safetensors')
    model.replies = [json.dumps({'prompt': DRAWN})]
    polls = iter([{}, {'job-1': {'status': {'completed': True},
                                 'outputs': {'7': {'images': [{'filename': 'p_0001.png', 'subfolder': '', 'type': 'output'}]}}}}])

    def handle(request):
        if request.url.path == '/prompt':
            return httpx.Response(200, json={'prompt_id': 'job-1'})
        if request.url.path == '/history/job-1':
            return httpx.Response(200, json=next(polls))
        assert request.url.path == '/view' and request.url.params['filename'] == 'p_0001.png'
        return httpx.Response(200, content=picture((832, 1248)))

    maker.handle = handle
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': 'photo'})
    assert found.status_code == 200
    graph = json.loads(maker.sent[0].content)['prompt']
    assert graph['1']['inputs']['ckpt_name'] == 'sd_xl_base_1.0.safetensors'
    assert graph['2']['inputs']['text'] == found.json()['prompt'] and 'nsfw' in graph['3']['inputs']['text']
    assert graph['4']['inputs'] == {'width': 832, 'height': 1248, 'batch_size': 1}
    assert isinstance(graph['5']['inputs']['seed'], int)


def test_a_provider_error_comes_back_as_a_plain_message(model, maker):
    images.configure('openai', 'https://api.openai.com/v1', 'gpt-image-1', key='sk-test')
    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: httpx.Response(400, json={'error': {'message': 'Your request was rejected by our safety system.'}})
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 422
    assert found.json()['error'] == ('The image maker refused this portrait under its content rules. It said: '
                                     '"Your request was rejected by our safety system."')

    model.replies = [json.dumps({'prompt': DRAWN})]
    maker.handle = lambda request: (_ for _ in ()).throw(httpx.ConnectError('refused'))
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 502 and 'Could not reach the image maker' in found.json()['error']


def test_an_unsafe_prompt_goes_back_once_then_is_refused(model, maker):
    images.configure('openai', 'https://api.openai.com/v1', 'gpt-image-1')
    model.replies = [json.dumps({'prompt': 'A topless woman'}), json.dumps({'prompt': 'A seductive woman'})]
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 502 and 'seductive' in found.json()['error'] and maker.sent == []
    assert 'topless' in model.asked[1][1]


def test_nothing_is_asked_until_an_image_maker_is_set(model, keys):
    found = api().post('/api/portrait/make', json={'character': DANA, 'style': ''})
    assert found.status_code == 409 and model.asked == []
    assert api().post('/api/portrait/make', json={'character': DANA, 'style': 'cubist'}).status_code == 422
    assert [style['name'] for style in api().get('/api/portrait/styles').json()][0] == 'Photo'
