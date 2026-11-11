"""Dramatis answers only its own page. It listens on 127.0.0.1, but a web page you visit can still reach it: a site
whose name is pointed at 127.0.0.1 after the page loads (DNS rebinding) talks to this server as if it were the site
itself, and could read the library, secrets included, delete it, or spend your model's tokens. So every request must
name this computer as its host, and a request from a page must come from a page on this computer: Dramatis's own
screen, or the Vite dev server during development. Anything else is refused before any route runs."""
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

# The names this computer answers to; any port, so --port, the dev server and the launchers all keep working.
LOCAL = {'localhost', '127.0.0.1', '::1'}


def hostname(value: str) -> str:
    """The host part of a Host header or an Origin, without the port; '' when it has none."""
    if '://' not in value:
        value = f'//{value}'
    try:
        return (urlsplit(value).hostname or '').lower()
    except ValueError:
        return ''


class LocalOnly:
    """ASGI middleware: 403 for a request whose Host, or Origin when it has one, is not this computer."""

    def __init__(self, app: ASGIApp, allowed: set[str] | None = None):
        self.app, self.allowed = app, set(LOCAL) if allowed is None else allowed

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] in ('http', 'websocket'):
            headers = {key.decode('latin-1').lower(): value.decode('latin-1') for key, value in scope['headers']}
            origin = headers.get('origin')
            if hostname(headers.get('host', '')) not in self.allowed or \
                    (origin is not None and hostname(origin) not in self.allowed):
                await refuse(scope, send)
                return
        await self.app(scope, receive, send)


async def refuse(scope: Scope, send: Send):
    if scope['type'] == 'websocket':
        await send({'type': 'websocket.close', 'code': 1008})
        return
    body = b'{"error": "Dramatis answers only its own page on this computer.", "code": "not_local"}'
    await send({'type': 'http.response.start', 'status': 403,
                'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())]})
    await send({'type': 'http.response.body', 'body': body})
