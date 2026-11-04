"""Models: Companion's profiles and providers in Dramatis, each job going to its own profile, keys kept out of the
settings file, and the one model setting from before profiles carried over."""
import json
import os
import sys

import httpx
import pytest
from fastapi.testclient import TestClient

from dramatis import ai, profiles, settings
from dramatis.formats.companion.errors import DomainError
from dramatis.formats.companion.providers.chat import ChatProvider
from dramatis.main import create_app

LOCAL = {'provider': 'local', 'model': 'qwen3:8b', 'base_url': 'http://127.0.0.1:1234/v1', **profiles.DRAFTING}


class Server:
    """An OpenAI-compatible server on this computer: lists two models, and answers each chat with the next reply."""

    def __init__(self):
        self.replies, self.asked = [], []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data': [{'id': 'qwen3:8b'}, {'id': 'gemma4:12b'}]})
        body = json.loads(request.content)
        self.asked.append((str(request.url), request.headers.get('authorization'), body))
        text, reason = self.replies.pop(0)
        events = [{'choices': [{'delta': {'content': text}}]}, {'choices': [{'delta': {}, 'finish_reason': reason}]}]
        stream = ''.join(f'data: {json.dumps(event)}\n\n' for event in events) + 'data: [DONE]\n\n'
        return httpx.Response(200, text=stream, headers={'content-type': 'text/event-stream'})


@pytest.fixture
def server(monkeypatch):
    found = Server()
    provider = ChatProvider(transport=httpx.MockTransport(found))
    provider.learned_effort = profiles.learn_effort
    monkeypatch.setattr(ai, 'PROVIDER', provider)
    return found


def made(api, config=LOCAL, **more):
    response = api.post('/api/models/profiles', json={'name': '', 'config': config, **more})
    assert response.status_code == 201, response.text
    return response.json()


def test_the_first_finished_profile_writes_and_every_draft_goes_through_it(server):
    api = TestClient(create_app())
    profile = made(api)
    assert profile['name'] == 'Local / LM Studio · qwen3:8b' and profile['ready']
    assert api.get('/api/models').json()['routes'] == {'writing': profile['id']}
    server.replies = [('{"name": "Ida"}', 'stop')]
    assert ai.complete('Be brief.', 'Write the JSON now.') == '{"name": "Ida"}'
    url, _, body = server.asked[0]
    assert url == 'http://127.0.0.1:1234/v1/chat/completions' and body['model'] == 'qwen3:8b'
    assert body['max_tokens'] == 8000 and body['messages'][0] == {'role': 'system', 'content': 'Be brief.'}


def test_each_job_goes_to_its_own_profile_or_else_the_writing_one(server):
    api = TestClient(create_app())
    writing = made(api)
    other = made(api, {**LOCAL, 'model': 'gemma4:12b'})
    assert api.put('/api/models/routes', json={'job': 'cast', 'profile_id': other['id']}).json()['routes']['cast'] == other['id']
    server.replies = [('one', 'stop'), ('two', 'stop'), ('three', 'stop')]
    with ai.doing('cast'):
        ai.complete('s', 'p')
    with ai.doing('assistant'):
        ai.complete('s', 'p')
    ai.complete('s', 'p')
    assert [body['model'] for _, _, body in server.asked] == ['gemma4:12b', 'qwen3:8b', 'qwen3:8b']
    assert api.delete(f"/api/models/profiles/{other['id']}").json()['routes'] == {'writing': writing['id']}


def test_the_sidebar_assistant_and_cast_board_ask_their_own_profiles(server):
    api = TestClient(create_app())
    made(api)
    assistant = made(api, {**LOCAL, 'model': 'gemma4:12b'})
    api.put('/api/models/routes', json={'job': 'assistant', 'profile_id': assistant['id']})
    server.replies = [(json.dumps({'reply': 'Hello.', 'edits': []}), 'stop')]
    answered = api.post('/api/assistant', json={'message': 'Hi', 'character': {}, 'history': []})
    assert answered.status_code == 200, answered.text
    assert server.asked[0][2]['model'] == 'gemma4:12b'


def test_a_key_goes_to_the_keyring_and_a_copy_shares_it(server, own_keyring):
    api = TestClient(create_app())
    hosted = {'provider': 'openrouter', 'model': 'deepseek/deepseek-v4', **profiles.DRAFTING}
    profile = made(api, hosted, api_key='sk-or-secret')
    assert 'sk-or-secret' not in settings.path().read_text(encoding='utf-8')
    assert list(own_keyring.secrets.values()) == ['sk-or-secret'] and profile['has_saved_key']
    copy = api.post(f"/api/models/profiles/{profile['id']}/duplicate").json()
    assert copy['name'] == f"{profile['name']} copy" and copy['key_shared_with'] == [profile['name']]
    # A new profile on the same service uses the saved key without asking for it again.
    assert made(api, {**hosted, 'model': 'x-ai/grok-5'})['has_saved_key']
    for found in api.get('/api/models').json()['profiles']:
        api.delete(f"/api/models/profiles/{found['id']}")
    assert own_keyring.secrets == {}


def test_a_key_is_never_kept_for_another_address(server):
    api = TestClient(create_app())
    profile = made(api, {**LOCAL, 'provider': 'compatible', 'base_url': 'https://api.deepseek.com/v1'}, api_key='sk-1')
    moved = api.put(f"/api/models/profiles/{profile['id']}", json={
        'name': profile['name'], 'config': {**profile['config'], 'base_url': 'https://example.com/v1'},
        'expected_revision': profile['revision']}).json()
    assert not moved['has_saved_key']


def test_an_old_edit_is_turned_away(server):
    api = TestClient(create_app())
    profile = made(api)
    body = {'name': 'Mine', 'config': profile['config'], 'expected_revision': profile['revision']}
    assert api.put(f"/api/models/profiles/{profile['id']}", json=body).status_code == 200
    assert api.put(f"/api/models/profiles/{profile['id']}", json=body).status_code == 409


def test_companion_checks_the_settings(server):
    api = TestClient(create_app())
    remote = api.post('/api/models/profiles', json={'config': {**LOCAL, 'base_url': 'http://192.168.1.9:1234/v1'}})
    assert remote.status_code == 422
    cut = api.post('/api/models/profiles', json={'config': {**LOCAL, 'max_output_tokens': 40000, 'context_tokens': 32000}})
    assert cut.status_code == 422


def test_the_connection_test_lists_models_without_writing(server):
    api = TestClient(create_app())
    found = api.post('/api/models/discover', json={'config': {**LOCAL, 'model': ''}}).json()
    assert found['models'] == ['qwen3:8b', 'gemma4:12b'] and found['generated'] is False and server.asked == []


def test_a_reply_cut_at_the_limit_says_how_to_fix_it(server):
    api = TestClient(create_app())
    made(api)
    server.replies = [('{"name": "Id', 'length')]
    with pytest.raises(DomainError, match='Raise the longest reply'):
        ai.complete('s', 'p')


def test_without_a_profile_nothing_is_set_up():
    with pytest.raises(DomainError, match='No model is set up') as error:
        ai.complete('s', 'p')
    assert error.value.status == 409


def test_the_one_model_setting_from_before_becomes_the_writing_profile(own_keyring):
    own_keyring.put('anthropic', 'sk-ant-old')
    settings.save({'model': {'provider': 'anthropic', 'model': 'claude-opus-5-5', 'base_url': ''}})
    found = profiles.overview()
    [profile] = found['profiles']
    assert found['routes'] == {'writing': profile['id']} and profile['has_saved_key']
    assert profile['config']['provider'] == 'anthropic' and profile['config']['model'] == 'claude-opus-5-5'
    assert profiles.for_job('writing')['key'] == 'sk-ant-old'
    assert 'provider' not in settings.load()['model']


@pytest.mark.parametrize(('old', 'provider'), [({'provider': 'openai', 'base_url': 'http://127.0.0.1:1234/v1',
                                                 'model': 'qwen3'}, 'local'),
                                                ({'provider': 'claude-cli', 'model': ''}, 'claude_code')])
def test_a_local_server_or_the_claude_command_line_from_before_carries_over(old, provider):
    settings.save({'model': old})
    [profile] = profiles.overview()['profiles']
    assert profile['config']['provider'] == provider and profile['ready']


def test_looking_for_cli_accounts_can_be_turned_off():
    api = TestClient(create_app())
    assert api.put('/api/models/looking', json={'enabled': False}).json()['find_cli_accounts'] is False
    assert api.get('/api/models/cli-accounts').json() == {'enabled': False, 'accounts': []}


@pytest.mark.skipif(os.name == 'nt', reason='the stand-in CLI is a POSIX script')
def test_claude_code_answers_through_its_own_login(tmp_path):
    """The Claude Code profile runs the claude command line (here a stand-in) with the system prompt in a file and
    every tool off, and the reply comes back like any other."""
    cli = tmp_path / 'claude'
    events = [{'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta',
                                                                                         'text': '{"name": "Tom"}'}}},
              {'type': 'result', 'subtype': 'success', 'result': '{"name": "Tom"}'}]
    lines = '\n'.join(json.dumps(event) for event in events)
    cli.write_text(f'#!{sys.executable}\nimport sys\nsys.stdin.read()\nopen({str(tmp_path / "args")!r}, "w").write('
                   f'" ".join(sys.argv[1:]))\nprint({lines!r})\n', encoding='utf-8')
    cli.chmod(0o755)
    TestClient(create_app()).post('/api/models/profiles', json={'config': {
        'provider': 'claude_code', 'model': 'sonnet', 'cli_path': str(cli), **profiles.DRAFTING}})
    assert ai.complete('Be brief.', 'Write the JSON now.') == '{"name": "Tom"}'
    assert '--tools  --strict-mcp-config' in (tmp_path / 'args').read_text(encoding='utf-8')
