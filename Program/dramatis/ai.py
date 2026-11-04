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
from contextlib import contextmanager
from contextvars import ContextVar

from dramatis import profiles
from dramatis.formats.companion.errors import DomainError, require
from dramatis.formats.companion.providers.chat import INCOMPLETE, ChatProvider

JOB: ContextVar[str] = ContextVar('job', default=profiles.WRITING)
PROVIDER = ChatProvider()
# A model that turns down the profile's reasoning effort is asked with one it takes, and the profile remembers it.
PROVIDER.learned_effort = profiles.learn_effort

_loop: asyncio.AbstractEventLoop | None = None
_starting = threading.Lock()


def run(work):
    """Run one of the providers' coroutines to its end from a route (FastAPI runs Dramatis' routes in threads). They
    share one event loop of their own, so the provider's per-run memory (prompt cache, learned efforts) holds."""
    global _loop
    with _starting:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, name='dramatis-models', daemon=True).start()
    return asyncio.run_coroutine_threadsafe(work, _loop).result()


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
