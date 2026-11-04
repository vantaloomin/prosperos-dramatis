"""Models: profiles, the connection test, the Claude Code and Codex accounts found here, and which profile does each
job. Ported from Prospero's Companion's text_model_routes.py; the providers are Companion's own (dramatis/ai.py)."""
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from dramatis import ai, profiles
from dramatis.formats.companion.providers import balance, cli_accounts
from dramatis.formats.companion.providers.config import ConnectionProbe, ProfileCreate, ProfileUpdate, RouteUpdate


class Looking(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


router = APIRouter(prefix='/api/models')


@router.get('')
def overview():
    return profiles.overview()


@router.post('/profiles', status_code=201)
def create_profile(body: ProfileCreate):
    return profiles.create(body)


@router.put('/profiles/{profile_id}')
def update_profile(profile_id: str, body: ProfileUpdate):
    return profiles.update(profile_id, body)


@router.post('/profiles/{profile_id}/duplicate', status_code=201)
def duplicate_profile(profile_id: str):
    return profiles.duplicate(profile_id)


@router.delete('/profiles/{profile_id}')
def delete_profile(profile_id: str):
    return profiles.delete(profile_id)


@router.post('/discover')
def discover(body: ConnectionProbe):
    """Test an unsaved form: list the service's models without generating anything."""
    return ai.run(ai.PROVIDER.check(body.config.model_dump(), profiles.probe_key(body)))


@router.post('/profiles/{profile_id}/check')
def check_profile(profile_id: str):
    profile = profiles.found(profiles.stored(), profile_id)
    return ai.run(ai.PROVIDER.check(profile['config'], profiles.key_for(profile)))


@router.get('/profiles/{profile_id}/usage')
def profile_usage(profile_id: str, fresh: bool = False):
    """Credits or plan limits the service reports for free, or null; never spends tokens."""
    profile = profiles.found(profiles.stored(), profile_id)
    if not balance.has_lookup(profile['config']):
        return None
    return ai.run(ai.PROVIDER.usage((profile['id'], profile['revision']), profile['config'], profiles.key_for(profile),
                                    fresh))


@router.get('/cli-accounts')
def cli_accounts_found():
    """The Claude Code and Codex accounts on this computer (claude, claude2, codex…), for a profile to pick; none
    while looking for them is turned off."""
    enabled = profiles.stored()['find_cli_accounts']
    return {'enabled': enabled, 'accounts': ai.run(cli_accounts.accounts_with_logins()) if enabled else []}


@router.put('/looking')
def set_looking(body: Looking):
    return profiles.set_looking(body.enabled)


@router.put('/routes')
def set_route(body: RouteUpdate):
    return profiles.set_route(body.job, body.profile_id)
