"""The stand-in model (dramatis/stub.py): each route that asks a model gets an answer it can use."""
import pytest
from fastapi.testclient import TestClient

from dramatis import ai, asking, profiles, slop, stub
from dramatis.main import create_app


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv('DRAMATIS_HOME', str(tmp_path))
    monkeypatch.setattr(stub, 'DELAY', 0)
    monkeypatch.setattr(profiles, 'VAULT', profiles.VAULT)
    monkeypatch.setattr(ai, 'complete', ai.complete)
    assert stub.install() == str(tmp_path)
    return TestClient(create_app())


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_every_model_route_answers_with_the_stand_in(api):
    assert api.get('/api/models').json()['profiles'][0]['name'] == 'Stand-in model'
    drafted = ok(api.post('/api/draft', json={'idea': 'a night nurse', 'emotional_edges': True}))
    character = drafted['character']
    assert character['about'].startswith('Dana is 38') and not drafted.get('missing')
    ok(api.post('/api/draft/split', json={'text': 'Dana, a night nurse in Baltimore.'}))
    assert ok(api.post('/api/draft/field', json={'character': character, 'field': 'voice'}))['value']
    answer = ok(api.post('/api/assistant', json={'message': 'Give her a sister.', 'character': character}))
    assert [edit['field'] for edit in answer['edits']] == ['background', 'wants']
    heard = ok(api.post('/api/draft/interview', json={'character': character}))
    assert heard['sample'] == 'Nights, mostly. Somebody has to.'
    ok(api.post('/api/draft/from-interview', json={'character': character | {'interview': heard['interview']}}))
    marked = character | {'about': character['about'] + ' Her tapestry of grief.'}
    hits = [hit for hit in slop.audit(marked) if hit['match'].lower() == 'tapestry']
    assert ok(api.post('/api/draft/fix', json={'character': marked, 'hits': hits}))['fields']
    from tests.test_casts import board
    cast = board()
    assert len(ok(api.post('/api/cast-ai/suggest', json={'cast': cast, 'target': 'outer'}))['proposals']) == 2
    ok(api.post('/api/cast-ai/check', json={'cast': cast}))


# Each prompt and the answer the stand-in gives it: the first mark in ANSWERS its text carries.
PROMPTS = {'assistant.md': 'Sidebar Assistant', 'fix.md': '{"spans"', 'interview.md': '{"interview"',
           'cast-check.md': '{"flags"', 'cast-suggest.md': '{"corner_id"', 'from-interview.md': '{"proposals"',
           'cast-turn.md': '{"turn"', 'cast-relationship.md': '{"dynamic"', 'portrait.md': '{"prompt"',
           'field.md': '{"value"', 'draft.md': None, 'split.md': None}


@pytest.mark.parametrize(('name', 'mark'), PROMPTS.items())
def test_each_prompt_gets_the_answer_it_asks_for(name, mark):
    text = asking.template(name)
    assert next((found for found, _ in stub.ANSWERS if found in text), None) == mark
