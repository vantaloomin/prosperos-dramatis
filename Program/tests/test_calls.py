import asyncio
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dramatis import ai, calls
from dramatis.main import create_app


def slow(seen: dict):
    async def work():
        seen['started'] = True
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            seen['cancelled'] = True
            raise
        return 'finished'
    return work()


def test_a_call_whose_client_went_away_is_cancelled_not_left_running():
    seen, gone = {}, threading.Event()
    token = calls.GONE.set(gone)
    try:
        threading.Timer(0.3, gone.set).start()
        with pytest.raises(ai.Stopped):
            ai.run(slow(seen))
    finally:
        calls.GONE.reset(token)
    for _ in range(50):
        if seen.get('cancelled'):
            break
        threading.Event().wait(0.02)
    assert seen == {'started': True, 'cancelled': True}


def test_the_server_hears_the_client_go_and_the_route_stops_its_model_call():
    seen = {}
    app = FastAPI()
    app.add_middleware(calls.Calls)

    @app.post('/api/slow')
    def route():
        try:
            return ai.run(slow(seen))
        except ai.Stopped:
            seen['stopped'] = True
            raise

    messages = [{'type': 'http.request', 'body': b'{}', 'more_body': False}]
    done = asyncio.Event()

    async def receive():
        if messages:
            return messages.pop(0)
        await asyncio.sleep(0.3)  # The browser drops the request a moment after sending it.
        return {'type': 'http.disconnect'}

    async def send(message):
        if message['type'] == 'http.response.body' and not message.get('more_body'):
            done.set()

    scope = {'type': 'http', 'method': 'POST', 'path': '/api/slow', 'raw_path': b'/api/slow', 'query_string': b'',
             'headers': [(b'host', b'127.0.0.1')], 'http_version': '1.1', 'scheme': 'http', 'root_path': '',
             'server': ('127.0.0.1', 8815), 'client': ('127.0.0.1', 5000)}

    async def main():
        with pytest.raises(ai.Stopped):  # This bare app has no handler for it; Dramatis's answers 499.
            await asyncio.wait_for(app(scope, receive, send), 5)
    asyncio.run(main())
    for _ in range(50):
        if seen.get('cancelled'):
            break
        threading.Event().wait(0.02)
    assert seen == {'started': True, 'cancelled': True, 'stopped': True}


def test_a_draft_tells_the_screen_its_steps(model):
    from dramatis import drafting
    from tests.helpers import reply
    shown = []
    real = calls.step
    model.replies = [reply()]
    token = calls.RUN.set('run1')
    try:
        calls.step = lambda text: (shown.append(text), real(text))
        drafting.draft({'idea': 'a nurse', 'apps': ['adventure']})
    finally:
        calls.step = real
        calls.RUN.reset(token)
    assert shown[:4] == ['Settling how they look', 'Drawing names', 'Writing', 'Checking what came back']
    assert TestClient(create_app()).get('/api/progress/run1').json() == {'step': 'Checking what came back'}
    assert TestClient(create_app()).get('/api/progress/nobody').json() == {'step': ''}
