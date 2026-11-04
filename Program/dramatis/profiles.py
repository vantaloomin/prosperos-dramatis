"""Model profiles and which one does each job: Prospero's Companion's Settings > Models, kept in Dramatis' settings.json.

A profile is one provider, model, address and saved key, checked with Companion's own `ProfileConfig`
(dramatis/formats/companion/providers/config.py), so every provider Companion offers works here: OpenAI, Anthropic,
OpenRouter, Google, NanoGPT, any OpenAI-compatible API, LM Studio or Ollama on this computer, Kobold, Codex under the
user's ChatGPT login, and Claude Code under their Claude plan. Ported from Companion's text_models.py, which keeps
profiles in its database: here they are the `model` part of settings.json, and the jobs are Dramatis' own.

The writing profile does every job until another job is given one of its own. Saving a profile never contacts the
service. A saved key lives in the system keyring (Companion's vault, under Dramatis' name) and stays with its
provider and address: changing either drops it, so a key is never sent somewhere it was not entered for. A key a
profile saved is reused by a new profile on the same service, so one key does every job.
"""
import threading
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import ValidationError

from dramatis import settings
from dramatis.formats.companion.errors import DomainError, require
from dramatis.formats.companion.providers.config import (
    CLI_PROVIDERS,
    PROVIDER_NAMES,
    ProfileCreate,
    ProfileUpdate,
    SavedProfileConfig,
    profile_ready,
)
from dramatis.formats.companion.providers.urls import is_loopback
from dramatis.formats.companion.providers.vault import SystemVault, credential_for

WRITING = 'writing'
JOBS = [
    {'key': WRITING, 'name': 'Writing', 'detail': 'Drafts, Help me write, the interview and portrait prompts. Every '
     'other job uses this profile unless you choose another.'},
    {'key': 'assistant', 'name': 'Sidebar Assistant', 'detail': 'The chat beside the character form.'},
    {'key': 'cast', 'name': 'Cast board', 'detail': 'Suggesting corners and relationships, checking the square and '
     'finding the turn.'},
]
JOB_KEYS = {job['key'] for job in JOBS}
# Where a new profile starts: room for a whole character in one reply, and time for a slow local model to write it.
DRAFTING = {'max_output_tokens': 8000, 'context_tokens': 32000, 'timeout_seconds': 600}

VAULT = SystemVault()
# One read-change-write of settings.json at a time.
LOCK = threading.RLock()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def stored() -> dict:
    """{'profiles': [...], 'routes': {job: profile id}, 'find_cli_accounts': bool}, after moving an older setting."""
    saved = settings.load()['model']
    if 'provider' in saved:
        saved = adopt_legacy(saved)
    profiles = [profile for profile in saved.get('profiles') or [] if isinstance(profile, dict) and profile.get('id')]
    routes = {job: profile_id for job, profile_id in (saved.get('routes') or {}).items()
              if job in JOB_KEYS and any(profile['id'] == profile_id for profile in profiles)}
    return {'profiles': profiles, 'routes': routes, 'find_cli_accounts': saved.get('find_cli_accounts', True) is not False}


def write(state: dict) -> dict:
    settings.save({'model': state})
    return state


def adopt_legacy(saved: dict) -> dict:
    """Dramatis' one model setting before profiles ({provider, model, base_url}, key under the provider's name) as
    the writing profile, so an app that drafted before still drafts after."""
    provider = {'anthropic': 'anthropic', 'claude-cli': 'claude_code'}.get(saved['provider'])
    base_url = saved.get('base_url') or ''
    if saved['provider'] == 'openai':
        provider = 'local' if is_loopback(urlsplit(base_url).hostname) else 'compatible'
    state = {'profiles': [], 'routes': {}}
    if provider:
        model = saved.get('model') or {'anthropic': 'claude-opus-5-5', 'claude_code': 'sonnet'}.get(provider, '')
        try:
            config = SavedProfileConfig(provider=provider, model=model, base_url=base_url if provider in
                                        {'local', 'compatible'} else '', **DRAFTING,
                                        reasoning_effort='medium' if provider == 'anthropic' else None).model_dump()
        except (ValidationError, DomainError):
            config = None
        if config:
            reference = saved['provider'] if provider not in CLI_PROVIDERS and safe_get(saved['provider']) else None
            profile = made(default_name(config), config, reference)
            state = {'profiles': [profile], 'routes': {WRITING: profile['id']} if profile_ready(config) else {}}
    with LOCK:
        return write(state)


def safe_get(reference: str) -> str | None:
    try:
        return VAULT.get(reference)
    except DomainError:
        return None


def made(name: str, config: dict, reference: str | None) -> dict:
    stamp = now()
    return {'id': uuid4().hex, 'name': name, 'revision': 1, 'config': config, 'credential_ref': reference,
            'created_at': stamp, 'updated_at': stamp}


def default_name(config: dict) -> str:
    model = config.get('model')
    return f"{PROVIDER_NAMES[config['provider']]} · {model}" if model else f"{PROVIDER_NAMES[config['provider']]} connection"


def sharing(profiles: list[dict], profile: dict) -> list[str]:
    """The other profiles using this profile's saved key."""
    reference = profile.get('credential_ref')
    return [other['name'] for other in profiles if reference and other.get('credential_ref') == reference
            and other['id'] != profile['id']]


def view(profile: dict, profiles: list[dict]) -> dict:
    config = profile['config']
    return {'id': profile['id'], 'name': profile['name'], 'revision': profile['revision'], 'config': config,
            'provider_name': PROVIDER_NAMES[config['provider']], 'has_saved_key': bool(profile.get('credential_ref')),
            'key_shared_with': sharing(profiles, profile), 'ready': profile_ready(config),
            'updated_at': profile.get('updated_at')}


def overview(state: dict | None = None) -> dict:
    state = state or stored()
    profiles = sorted(state['profiles'], key=lambda profile: (profile['name'].casefold(), profile.get('created_at', '')))
    return {'profiles': [view(profile, profiles) for profile in profiles], 'routes': state['routes'], 'jobs': JOBS,
            'find_cli_accounts': state['find_cli_accounts']}


def found(state: dict, profile_id: str) -> dict:
    for profile in state['profiles']:
        if profile['id'] == profile_id:
            return profile
    raise DomainError('That model profile is gone. Reopen Models.', 404, 'not_found')


def view_of(state: dict, profile_id: str) -> dict:
    return view(found(state, profile_id), state['profiles'])


def assigned(state: dict, job: str) -> dict | None:
    """The profile doing a job: its own, else the writing profile's."""
    profile_id = state['routes'].get(job) or state['routes'].get(WRITING)
    return next((profile for profile in state['profiles'] if profile['id'] == profile_id), None)


def for_job(job: str) -> dict:
    """The settings a job's model calls use, with `profile_id` and `key`; a 409 that says so when none is set up."""
    state = stored()
    profile = assigned(state, job)
    require(profile is not None and profile_ready(profile['config']), 'No model is set up yet. Add one in Models: a '
            'hosted service with its key, a model running on this computer, Codex, or Claude Code.', 409)
    config = {**profile['config'], 'profile_id': profile['id'], 'profile_name': profile['name']}
    return config | {'key': key_for(profile)}


def key_for(profile: dict) -> str | None:
    return credential_for(VAULT, profile.get('credential_ref'), profile['config']['provider'])


def same_connection(first: dict, second: dict) -> bool:
    return first['provider'] == second['provider'] and (first['base_url'] == second['base_url'] or not first['base_url'])


def same_service(first: dict, second: dict) -> bool:
    """The same provider at the same address, so a key saved for one is meant for the other."""
    return first['provider'] == second['provider'] and \
        (first.get('base_url') or '').rstrip('/') == (second.get('base_url') or '').rstrip('/')


def reusable_key(state: dict, config: dict, excluding: str | None = None) -> dict | None:
    """The profile whose saved key a new or keyless profile on the same service uses, most recently changed first."""
    if config['provider'] in CLI_PROVIDERS:
        return None
    keyed = [profile for profile in state['profiles'] if profile.get('credential_ref') and profile['id'] != excluding
             and same_service(profile['config'], config)]
    return max(keyed, key=lambda profile: profile.get('updated_at', ''), default=None)


def probe_key(body) -> str | None:
    """The key a connection test uses: the one typed, else the profile's saved key if it still applies, else a key
    another profile saved for the same service."""
    if body.api_key:
        return body.api_key
    config, state, reference = body.config.model_dump(), stored(), None
    if body.profile_id:
        profile = found(state, body.profile_id)
        if same_connection(profile['config'], config):
            reference = profile.get('credential_ref')
    if reference is None:
        reference = (reusable_key(state, config) or {}).get('credential_ref')
    return credential_for(VAULT, reference, config['provider'])


def store_key(body, reference: str | None) -> str | None:
    if not body.api_key:
        return reference
    require(body.config.provider not in CLI_PROVIDERS, 'This provider uses its own CLI login; do not enter a key here.',
            422)
    reference = reference or uuid4().hex
    VAULT.put(reference, body.api_key)
    return reference


def adopt_writing(state: dict, profile: dict):
    """The first finished profile writes, so a new user can draft after one form."""
    if WRITING not in state['routes'] and profile_ready(profile['config']):
        state['routes'][WRITING] = profile['id']


def create(body: ProfileCreate) -> dict:
    config = body.config.model_dump()
    reference = store_key(body, None)
    with LOCK:
        state = stored()
        if reference is None:
            reference = (reusable_key(state, config) or {}).get('credential_ref')
        profile = made(body.name or default_name(config), config, reference)
        state['profiles'].append(profile)
        adopt_writing(state, profile)
        return view_of(write(state), profile['id'])


def update(profile_id: str, body: ProfileUpdate) -> dict:
    config = body.config.model_dump()
    with LOCK:
        state = stored()
        profile = found(state, profile_id)
        require(profile['revision'] == body.expected_revision, 'This profile changed. Reopen it and try again.', 409)
        before = profile.get('credential_ref')
        kept = before if same_connection(profile['config'], config) else None
        if kept and body.api_key and not body.share_key and sharing(state['profiles'], profile):
            kept = None  # Asked for a key of its own: the others keep the shared one.
        reference = store_key(body, kept)
        if reference is None:
            reference = (reusable_key(state, config, profile_id) or {}).get('credential_ref')
        profile |= {'name': body.name or default_name(config), 'config': config, 'credential_ref': reference,
                    'revision': profile['revision'] + 1, 'updated_at': now()}
        jobs = [job for job, assigned_id in state['routes'].items() if assigned_id == profile_id]
        require(not jobs or profile_ready(config), 'This profile does a job in Models. Choose a model before saving '
                'it, or give the job to another profile first.', 409)
        adopt_writing(state, profile)
        result = view_of(write(state), profile_id)
        if before and before != reference:
            release(state, before)
        return result


def delete(profile_id: str) -> dict:
    """Jobs it did go back to the writing profile; the writing job waits for one to be chosen."""
    with LOCK:
        state = stored()
        profile = found(state, profile_id)
        state['profiles'] = [other for other in state['profiles'] if other['id'] != profile_id]
        state['routes'] = {job: assigned_id for job, assigned_id in state['routes'].items() if assigned_id != profile_id}
        write(state)
        if profile.get('credential_ref'):
            release(state, profile['credential_ref'])
        return overview(state)


def duplicate(profile_id: str) -> dict:
    """A copy of a profile, named "… copy", sharing its saved key, for another model on the same service."""
    with LOCK:
        state = stored()
        profile = found(state, profile_id)
        names = {other['name'] for other in state['profiles']}
        name, number = f"{profile['name']} copy"[:120], 2
        while name in names:
            name, number = f"{profile['name']} copy {number}"[:120], number + 1
        copy = made(name, dict(profile['config']), profile.get('credential_ref'))
        state['profiles'].append(copy)
        return view_of(write(state), copy['id'])


def release(state: dict, reference: str):
    """Remove a saved key once no profile uses it."""
    if not any(profile.get('credential_ref') == reference for profile in state['profiles']):
        try:
            VAULT.delete(reference)
        except DomainError:
            pass  # The profile is gone either way; a key the keyring would not remove stays there unused.


def set_route(job: str, profile_id: str | None) -> dict:
    require(job in JOB_KEYS, 'There is no such job.', 422)
    with LOCK:
        state = stored()
        if profile_id:
            require(profile_ready(found(state, profile_id)['config']), 'Choose a model for this profile before giving '
                    'it a job.', 409)
            state['routes'][job] = profile_id
        else:
            state['routes'].pop(job, None)
        return overview(write(state))


def set_looking(enabled: bool) -> dict:
    with LOCK:
        state = stored() | {'find_cli_accounts': enabled}
        return overview(write(state))


def learn_effort(config: dict, instead: str | None, levels: list[str] | None):
    """The model turned down the profile's reasoning effort (providers/efforts.py): the profile asks with `instead`
    from now on and, when the service named them, Models offers only `levels`. A profile changed meanwhile is left as
    the user made it."""
    with LOCK:
        state = stored()
        profile = next((item for item in state['profiles'] if item['id'] == config.get('profile_id')), None)
        saved = profile and profile['config']
        if not saved or saved.get('model') != config.get('model') or \
                saved.get('reasoning_effort') != config.get('reasoning_effort'):
            return
        saved['reasoning_effort'] = instead
        if levels:
            reported = saved.get('reported_capabilities') or {}
            if reported.get('model_id') != saved['model']:
                reported = {'model_id': saved['model']}
            saved['reported_capabilities'] = {**reported, 'supported_efforts': levels}
        profile |= {'revision': profile['revision'] + 1, 'updated_at': now()}
        write(state)

