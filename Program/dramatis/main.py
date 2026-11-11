"""The local server: the API under /api, and the built screen (Program/dist) for everything else."""
import base64
import binascii
import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dramatis import (
    NAME,
    VERSION,
    assistant,
    calls,
    cards,
    cast_ai,
    cast_routes,
    drafting,
    fixes,
    images,
    imports,
    interview,
    library,
    library_tools,
    model_routes,
    names,
    portraits,
    settings,
    slop,
)
from dramatis.character import APPS, App, Character, Gender, Relationship, problems, shapes
from dramatis.formats.companion import personality
from dramatis.formats.companion.errors import DomainError, require
from dramatis.local_only import LocalOnly

HERE = Path(__file__).resolve().parent
DIST = HERE.parent / 'dist'
SOURCE = HERE / 'formats' / 'SOURCE.json'


class Body(BaseModel):
    model_config = {'extra': 'forbid', 'str_strip_whitespace': True}


class DraftBody(Body):
    """The quick start: anything left open is the model's to choose."""
    idea: str = Field(default='', max_length=2000)
    name: str = Field(default='', max_length=80)
    gender: Gender = ''
    age: int | None = Field(default=None, ge=1, le=5000)
    setting: str = Field(default='', max_length=200)
    vibe: str = Field(default='', max_length=300)
    apps: list[App] = Field(default_factory=lambda: list(APPS), min_length=1, max_length=3)
    relationship: Relationship = 'friendship'
    timezone: str = Field(default='', max_length=64)
    emotional_edges: bool = False


class SplitBody(Body):
    text: str = Field(min_length=1, max_length=40000)
    apps: list[App] = Field(default_factory=lambda: list(APPS), min_length=1, max_length=3)
    relationship: Relationship = 'friendship'
    timezone: str = Field(default='', max_length=64)
    emotional_edges: bool = False


class FieldBody(Body):
    character: dict
    field: str = Field(max_length=40)
    request: str = Field(default='', max_length=500)


class SaveBody(Body):
    character: Character
    seed: str = Field(default='', max_length=40)
    # The revision the form was opened from: a save over a newer one is refused (dramatis/records.py). None saves anyway.
    revision: int | None = None


class CheckBody(Body):
    """`fields` are the ones a model wrote, the only ones the audit reads (all of them when left out): text the user
    typed or brought from another app is theirs. `allowed` is what they wrote themselves, such as pasted notes."""
    character: dict
    fields: list[Annotated[str, Field(max_length=40)]] | None = Field(default=None, max_length=200)
    allowed: str = Field(default='', max_length=60000)


class SlidersBody(Body):
    """The form as it stands, for its sliders: what its words settle and the rest rolled from the seed. `roll` rolls
    the Rolled ones again; `type` sets four of them from a four-letter type."""
    character: dict
    seed: str = Field(default='', max_length=40)
    roll: int = Field(default=0, ge=0, le=100000)
    type: str = Field(default='', max_length=4)
    # A character brought from another app: what their words don't settle stays In between until Roll again.
    still: bool = False


class FileBody(Body):
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


def format_source() -> dict:
    """Which commit of each app the vendored formats came from."""
    return {app: {'repo': found['repo'], 'commit': found['commit']}
            for app, found in json.loads(SOURCE.read_text(encoding='utf-8')).items()}


def checked(raw: dict) -> Character:
    """A character from the form, or a plain error naming the first field that does not fit."""
    try:
        return Character.model_validate(raw)
    except ValueError as error:
        errors = getattr(error, 'errors', lambda: [])()
        where = '.'.join(map(str, errors[0]['loc'])) if errors else 'character'
        message = errors[0]['msg'] if errors else str(error)
        raise DomainError(f'{where}: {message}', 422, 'invalid_character') from error


def sliders(body: SlidersBody) -> dict:
    """Companion's own slider rules (vendored): the user's settings, then the form's words, then the roll."""
    character = {key: value for key, value in body.character.items() if key != 'intimacy'}
    seed = f'{body.seed or "dramatis"}-{body.roll}' if body.roll else body.seed or 'dramatis'
    definition = {'identity': character.get('about') or '', **character}
    settled = personality.settle(definition, body.seed or 'dramatis')
    if body.still and not body.roll:
        stored = personality.clean(character.get('personality_sliders'))
        settled = {key: value if value['source'] != 'rolled' or key in stored else personality.slider(1, 'rolled')
                   for key, value in settled.items()}
    if body.roll:
        settled = personality.reroll(settled, seed)
    if body.type:
        try:
            settled = personality.from_type(body.type, settled)
        except ValueError as error:
            raise DomainError(str(error), 422) from error
    return personality.view(settled) | {'traits': personality.form_traits()}


def file_name(name: str, suffix: str) -> str:
    kept = re.sub(r'[^A-Za-z0-9 _-]+', '', name).strip()[:80] or 'character'
    return f'{kept}{suffix}'


def download(data: bytes, name: str, media: str) -> Response:
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{name}"'})


def api() -> APIRouter:  # noqa: C901 - one route each, kept together
    router = APIRouter(prefix='/api')

    @router.get('/health')
    def health():
        return {'ok': True, 'name': NAME, 'version': VERSION, 'formats': format_source(),
                'notice': settings.notice()}

    @router.get('/characters')
    def characters(search: str = Query('', max_length=200)):
        return library.listing(search)

    @router.get('/characters/{character_id}')
    def character(character_id: str):
        record = library.get(character_id)
        found = checked(record['character'])  # A character saved before a field was added comes back with it empty.
        return record | {'character': found.model_dump(), 'problems': problems(found)}

    @router.post('/characters')
    def create(body: SaveBody):
        record = library.save(body.character, seed=body.seed)
        return record | {'problems': problems(body.character)}

    @router.put('/characters/{character_id}')
    def update(character_id: str, body: SaveBody):
        record = library.save(body.character, character_id, revision=body.revision)
        return record | {'problems': problems(body.character)}

    @router.delete('/characters/{character_id}')
    def remove(character_id: str):
        library.delete(character_id)
        return {'ok': True}

    @router.put('/characters/{character_id}/portrait')
    def portrait(character_id: str, body: FileBody):
        try:
            data = base64.b64decode(body.data, validate=True)
        except (ValueError, binascii.Error) as error:
            raise DomainError('Choose the picture again; it did not arrive whole.', 422) from error
        return library.set_portrait(character_id, images.portrait_png(data))

    @router.delete('/characters/{character_id}/portrait')
    def no_portrait(character_id: str):
        return library.set_portrait(character_id, None)

    @router.get('/characters/{character_id}/portrait.png')
    def portrait_file(character_id: str):
        data = library.portrait(character_id)
        require(data is not None, 'They have no portrait.', 404)
        return Response(data, media_type='image/png', headers={'Cache-Control': 'no-store'})

    @router.get('/characters/{character_id}/card.{kind}')
    def card_file(character_id: str, kind: str, target: cards.Target = Query('prospero', alias='for')):
        """`?for=prospero` (the default) carries everything for the Prospero apps; `?for=chat` is the card for
        SillyTavern, Marinara, Front Porch and other chat apps, without what only the Prospero apps use."""
        require(kind in ('json', 'png'), 'Cards are JSON or PNG.', 404)
        record = library.get(character_id)
        found = checked(record['character'])
        full = cards.card(found, record['created'], record['updated'], target)
        name = file_name(found.name, f" (Prospero).{kind}" if target == 'prospero' else f'.{kind}')
        if kind == 'json':
            return download(json.dumps(full, ensure_ascii=False, indent=1).encode('utf-8'), name, 'application/json')
        picture = images.for_target(library.portrait(character_id) or cards.plain_png(), target)
        return download(cards.with_card(picture, full), name, 'image/png')

    @router.post('/check')
    def check(body: CheckBody):
        """What each app's own models make of the form as it stands, and what the AI-slop audit finds in it."""
        found = checked(body.character)
        hits = slop.audit(found.model_dump(), body.allowed)
        if body.fields is not None:
            hits = [hit for hit in hits if hit['field'] in body.fields]
        return {'problems': problems(found), 'apps': sorted(shapes(found)), 'audit': hits}

    @router.post('/sliders')
    def slider_view(body: SlidersBody):
        return sliders(body)

    @router.post('/draft')
    def draft(body: DraftBody):
        return drafting.draft(body.model_dump())

    @router.post('/draft/split')
    def split(body: SplitBody):
        return drafting.split(body.model_dump())

    @router.post('/draft/field')
    def field(body: FieldBody):
        return drafting.rewrite(body.character, body.field, body.request)

    @router.post('/cards/open')
    def open_card(body: FileBody):
        """A character file from Dramatis or another app, read for the form; nothing is saved."""
        return imports.opened(body.filename, body.data)

    return router


def create_app(dist: Path = DIST, hosts: set[str] | None = None) -> FastAPI:
    """The app; `hosts` are the names it answers to (dramatis/local_only.py: this computer's own)."""
    app = FastAPI(title=NAME, version=VERSION)
    app.add_middleware(calls.Calls)
    app.add_middleware(LocalOnly, allowed=hosts)

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, error: DomainError):
        return JSONResponse({'error': error.message, 'code': error.code}, status_code=error.status)

    app.include_router(api())
    app.include_router(calls.router)
    app.include_router(cast_routes.router())
    app.include_router(interview.router)
    app.include_router(names.router)
    app.include_router(fixes.router)
    app.include_router(portraits.router())
    app.include_router(cast_ai.router)
    app.include_router(assistant.router)
    app.include_router(model_routes.router)
    app.include_router(library_tools.router)
    if (dist / 'index.html').is_file():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/{path:path}', include_in_schema=False)
        def screen(path: str):
            if path == 'api' or path.startswith('api/'):  # An API path no route answers is not a page of the screen.
                return JSONResponse({'error': 'Not found.', 'code': 'not_found'}, status_code=404)
            wanted = (dist / path).resolve()
            if path and wanted.is_file() and wanted.is_relative_to(dist.resolve()):
                return FileResponse(wanted)
            return FileResponse(dist / 'index.html')

    return app


app = create_app()
