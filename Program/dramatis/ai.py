"""Calling the model the user chose for the job, through Prospero's Companion's own text model providers (vendored in
dramatis/formats/companion/providers by scripts/sync_format.py): OpenAI, Anthropic, OpenRouter, Google, NanoGPT, any
OpenAI-compatible API, LM Studio or Ollama on this computer, Kobold, Codex under the user's ChatGPT login, and Claude
Code under their Claude plan. Which profile does which job is dramatis/profiles.py.

Every model call in Dramatis comes through `complete`: drafts, Help me write, the interview, the AI-slop retry,
portrait prompts, the Sidebar Assistant and the Cast board's help. The job is `writing` unless the caller says
otherwise with `doing`. The model only ever drafts: dramatis/drafting.py checks what comes back and the form shows it
for review. Nothing is saved until the user saves.
"""
import asyncio
import threading
from concurrent.futures import CancelledError
from concurrent.futures import TimeoutError as Waiting
from contextlib import contextmanager
from contextvars import ContextVar

from dramatis import calls, profiles
from dramatis.formats.companion.errors import DomainError, require
from dramatis.formats.companion.providers.chat import INCOMPLETE, ChatProvider

JOB: ContextVar[str] = ContextVar('job', default=profiles.WRITING)
PROVIDER = ChatProvider()
# A model that turns down the profile's reasoning effort is asked with one it takes, and the profile remembers it.
PROVIDER.learned_effort = profiles.learn_effort

_loop: asyncio.AbstractEventLoop | None = None
_starting = threading.Lock()
# How often a waiting route looks whether its client went away.
LOOK_SECONDS = 0.2


class Stopped(DomainError):
    """The screen stopped waiting, so the model call was cancelled."""

    def __init__(self):
        super().__init__('Stopped.', 499, 'stopped')


def run(work):
    """Run one of the providers' coroutines to its end from a route (FastAPI runs Dramatis' routes in threads). They
    share one event loop of their own, so the provider's per-run memory (prompt cache, learned efforts) holds. When the
    request's client goes away (dramatis/calls.py), the coroutine is cancelled rather than left running."""
    global _loop
    with _starting:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name='dramatis-models', daemon=True).start()
    gone = calls.GONE.get()
    if gone is not None and gone.is_set():
        work.close()
        raise Stopped()
    future = asyncio.run_coroutine_threadsafe(work, _loop)
    while True:
        try:
            return future.result(timeout=None if gone is None else LOOK_SECONDS)
        except Waiting:
            if gone.is_set():
                future.cancel()
                raise Stopped() from None
        except CancelledError:
            raise Stopped() from None


@contextmanager
def doing(job: str):
    """Model calls inside go to the profile that does `job` (the writing profile when it has none of its own)."""
    token = JOB.set(job)
    try:
        yield
    finally:
        JOB.reset(token)


def complete(system: str, prompt: str) -> str:
    """One answer from the model doing the current job, as text."""
    config = profiles.for_job(JOB.get())
    return run(reply(config, config.pop('key'), system, prompt))


async def reply(config: dict, key: str | None, system: str, prompt: str) -> str:
    parts, finish = [], None
    async for chunk in PROVIDER.stream(config, key, system, [{'role': 'user', 'content': prompt}]):
        parts.append(chunk.text)
        finish = chunk.finish_reason or finish
    require(finish != 'length', f"{INCOMPLETE['length']} Raise the longest reply for {config['profile_name']} in "
            'Models, then try again.', 502)
    require(finish != 'content_filter', 'The model declined this draft. Try rewording the ask, or another model.', 422)
    return ''.join(parts)


# The image maker's key (dramatis/images.py) is kept in the same keyring as the profiles' keys.

def api_key(name: str) -> str:
    try:
        return profiles.VAULT.get(name) or ''
    except DomainError:
        return ''


def store_key(name: str, key: str):
    if key:
        profiles.VAULT.put(name, key)
    else:
        try:
            profiles.VAULT.delete(name)
        except DomainError:
            pass
