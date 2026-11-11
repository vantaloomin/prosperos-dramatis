"""What the server knows about the request a model call runs for: whether the screen is still waiting for it, and what
step it is at.

- **Stop stops the model.** When the screen stops waiting (Stop, leaving the screen, closing the tab), the browser
  drops the request. `Calls` hears that and sets the request's `gone` event; `ai.run` cancels the model call it is
  waiting on, which closes a hosted API's stream and ends a Claude Code or Codex process (the providers do that when
  cancelled), so no tokens are spent and a local model's slot is free for the next ask.
- **Progress.** A request may name its run (`X-Dramatis-Run`); the steps a draft takes (`step`) are kept under it for
  a while, and the screen asks for them (GET /api/progress/{run}) while it waits.
"""
import asyncio
import threading
import time
from contextvars import ContextVar

from fastapi import APIRouter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

GONE: ContextVar[threading.Event | None] = ContextVar('gone', default=None)
RUN: ContextVar[str | None] = ContextVar('run', default=None)
HEADER = b'x-dramatis-run'
KEPT_SECONDS = 600
STEPS: dict[str, tuple[str, float]] = {}
_steps = threading.Lock()


class Calls:
    """ASGI middleware for /api requests: the run they name, and an event set when the client goes away."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/'):
            await self.app(scope, receive, send)
            return
        gone, queue = threading.Event(), asyncio.Queue()
        run = dict(scope['headers']).get(HEADER, b'').decode('latin-1')[:40] or None

        async def watch():
            while True:
                message = await receive()
                await queue.put(message)
                if message['type'] == 'http.disconnect':
                    gone.set()
                    return

        async def received() -> Message:
            return await queue.get()

        watcher = asyncio.create_task(watch())
        tokens = GONE.set(gone), RUN.set(run)
        try:
            await self.app(scope, received, send)
        finally:
            watcher.cancel()
            GONE.reset(tokens[0])
            RUN.reset(tokens[1])


def step(text: str):
    """The step the current request's model work is at, for the screen to show."""
    run = RUN.get()
    if not run:
        return
    now = time.monotonic()
    with _steps:
        STEPS[run] = (text, now)
        for old in [key for key, (_, at) in STEPS.items() if now - at > KEPT_SECONDS]:
            del STEPS[old]


router = APIRouter(prefix='/api')


@router.get('/progress/{run}')
def progress(run: str):
    with _steps:
        found = STEPS.get(run[:40])
    return {'step': found[0] if found else ''}
