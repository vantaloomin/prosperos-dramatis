import pytest
from fastapi.testclient import TestClient

from dramatis.main import create_app


@pytest.fixture
def api():
    return TestClient(create_app(hosts={'127.0.0.1', 'localhost', '::1'}), base_url='http://127.0.0.1:8815')


def test_its_own_page_and_the_dev_server_are_answered(api):
    assert api.get('/api/characters').status_code == 200
    assert api.get('/api/characters', headers={'host': 'localhost:5207', 'origin': 'http://localhost:5207'}).status_code == 200
    assert api.get('/api/characters', headers={'host': '[::1]:8815'}).status_code == 200


def test_a_foreign_host_is_refused_before_any_route(api):
    # DNS rebinding: a site whose name now points at 127.0.0.1 still names itself in Host.
    answer = api.get('/api/characters', headers={'host': 'evil.example'})
    assert answer.status_code == 403 and answer.json()['code'] == 'not_local'
    assert api.get('/', headers={'host': 'evil.example:8815'}).status_code == 403


def test_a_page_from_elsewhere_is_refused(api):
    for origin in ('https://evil.example', 'null', 'http://127.0.0.1.evil.example'):
        answer = api.post('/api/characters', json={'character': {'name': 'Dana'}}, headers={'origin': origin})
        assert answer.status_code == 403, origin
    assert api.get('/api/characters').json() == []
