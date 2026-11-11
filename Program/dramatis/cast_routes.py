"""The cast API under /api: the store (dramatis/casts.py), the live checks for an unsaved board, the template banks,
and two exports: the whole cast as one `prospero-cast` file, and each of its characters as their own card, zipped."""
import io
import json
import zipfile
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel

from dramatis import cards, casts, library
from dramatis.formats.companion.errors import DomainError, require


class CastBody(BaseModel):
    model_config = {'extra': 'forbid'}
    cast: dict  # checked by casts.checked, so a broken rule comes back as one plain sentence
    # The revision the board was opened from: a save over a newer one is refused. None saves anyway.
    revision: int | None = None


def shown(record: dict) -> dict:
    return record | {'computed': casts.computed(casts.checked(record['cast']))}


def download(data: bytes, name: str, media: str) -> Response:
    return Response(data, media_type=media, headers={'Content-Disposition': f'attachment; filename="{name}"'})


def file_name(title: str, suffix: str) -> str:
    from dramatis.main import file_name  # main includes this router, so it is imported when first used

    return file_name(title, suffix)


def card_files(cast_id: str, kind: str, target: cards.Target) -> list[tuple[str, bytes]]:
    """Each character the cast names that is still in the library, as the card their own Card button makes, with
    their place in this cast added (casts.context_for)."""
    from dramatis.main import checked

    cast = casts.checked(casts.get(cast_id)['cast'])
    names = casts.known_names(cast)
    found, taken = [], set()
    for character_id in casts.mentioned(cast):
        try:
            record = library.get(character_id)
        except DomainError:
            continue
        character = checked(record['character'])
        full = cards.card(character, record['created'], record['updated'], target,
                          casts.context_for(cast, character_id, names))
        name, count = file_name(character.name, f'.{kind}'), 1
        while name.lower() in taken:
            count += 1
            name = file_name(f'{character.name or "character"} {count}', f'.{kind}')
        taken.add(name.lower())
        if kind == 'json':
            found.append((name, json.dumps(full, ensure_ascii=False, indent=1).encode('utf-8')))
        else:
            found.append((name, cards.with_card(library.portrait(character_id) or cards.plain_png(), full)))
    return found


def router() -> APIRouter:  # noqa: C901 - one route each, kept together
    found = APIRouter(prefix='/api')

    @found.get('/cast-templates')
    def cast_templates():
        return casts.templates()

    @found.get('/casts')
    def listing():
        return casts.listing()

    @found.post('/casts/check')
    def check(body: CastBody):
        """What the board as it stands computes to, before it is saved."""
        return {'computed': casts.computed(casts.checked(body.cast))}

    @found.get('/casts/{cast_id}')
    def get(cast_id: str):
        return shown(casts.get(cast_id))

    @found.post('/casts')
    def create(body: CastBody):
        return shown(casts.save(casts.checked(body.cast)))

    @found.put('/casts/{cast_id}')
    def update(cast_id: str, body: CastBody):
        return shown(casts.save(casts.checked(body.cast), cast_id, body.revision))

    @found.delete('/casts/{cast_id}')
    def remove(cast_id: str):
        casts.delete(cast_id)
        return {'ok': True}

    @found.get('/casts/{cast_id}/cast.json')
    def cast_file(cast_id: str):
        bundle = casts.export(cast_id)
        data = json.dumps(bundle, ensure_ascii=False, indent=1).encode('utf-8')
        return download(data, file_name(bundle['cast']['title'] or 'cast', '.json'), 'application/json')

    @found.get('/casts/{cast_id}/cards.zip')
    def card_zip(cast_id: str, target: cards.Target = Query('prospero', alias='for'),
                 kind: Literal['png', 'json'] = 'png'):
        """Every character in the cast as their own card, the same one their Card button makes: `?for=prospero` or
        `?for=chat` as for one character, and `?kind=png` (the default) or `json`."""
        files = card_files(cast_id, kind, target)
        require(bool(files), 'No character in this cast is in the library yet.', 404)
        packed = io.BytesIO()
        with zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files:
                archive.writestr(name, data)
        title = casts.get(cast_id)['cast']['title'] or 'cast'
        return download(packed.getvalue(), file_name(title, ' cards.zip'), 'application/zip')

    return found
