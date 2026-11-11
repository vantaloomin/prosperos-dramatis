"""What the library does besides keep characters and casts: duplicate a character, back the whole library up as one
file and bring one back, open a cast file another Dramatis exported, and say which casts a character is in before
they are deleted. Routes are under /api/library."""
import base64
import binascii
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from dramatis import NAME, VERSION, casts, library, records
from dramatis.character import Character
from dramatis.formats.companion.errors import DomainError, require

BACKUP = 'prospero-dramatis-backup'
MANIFEST = 'dramatis-backup.json'
ENTRY = re.compile(r'^(characters|casts)/([A-Za-z0-9]{1,40})\.(json|png)$')
MAX_BACKUP = 500 * 1024 * 1024  # unpacked
MAX_ENTRIES = 20000
COPY = ' (copy)'
NAME_LIMIT = 80  # Character.name


def decoded(data: str, what: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, binascii.Error) as error:
        raise DomainError(f'Choose the {what} again; it did not arrive whole.', 422) from error


# ---- Duplicate ----------------------------------------------------------------------------------------------------

def duplicate(character_id: str) -> dict:
    """A new character with everything the first one has, their portrait included, named as a copy."""
    record = library.get(character_id)
    character = Character.model_validate(record['character'])
    name = character.name[:NAME_LIMIT - len(COPY)].rstrip() + COPY if character.name else ''
    made = library.save(character.model_copy(update={'name': name}), seed=record.get('seed', ''))
    picture = library.portrait(character_id)
    return library.set_portrait(made['id'], picture) if picture else made


# ---- Which casts name them ----------------------------------------------------------------------------------------

def casts_of(character_id: str) -> list[dict]:
    """The casts that name this character, by title, for the warning before they are deleted."""
    found = []
    for item in casts.listing():
        try:
            cast = casts.checked(casts.get(item['id'])['cast'])
        except DomainError:
            continue
        if character_id in casts.mentioned(cast):
            found.append({'id': item['id'], 'title': cast.title or 'Untitled cast'})
    return found


# ---- Back up and bring back ---------------------------------------------------------------------------------------

def backup() -> tuple[str, bytes]:
    """Every character, portrait and cast, as one zip, with a note of what made it."""
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, json.dumps({'format': BACKUP, 'version': 1, 'app': NAME, 'app_version': VERSION,
                                               'made': library.now()}, indent=1))
        for folder in (library.folder(), casts.folder()):
            for path in sorted(folder.iterdir()) if folder.is_dir() else []:
                if ENTRY.match(f'{folder.name}/{path.name}'):
                    archive.write(path, f'{folder.name}/{path.name}')
    return f'Dramatis backup {datetime.now(UTC).date().isoformat()}.zip', packed.getvalue()


def entries(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """The backup's own files by name, after checking it is a Dramatis backup of a size worth unpacking."""
    infos = archive.infolist()
    require(len(infos) <= MAX_ENTRIES and sum(info.file_size for info in infos) <= MAX_BACKUP,
            'That backup is larger than Dramatis brings back in one go.', 422)
    try:
        manifest = json.loads(archive.read(MANIFEST))
    except (KeyError, ValueError) as error:
        raise DomainError('That is not a Dramatis backup: it has no dramatis-backup.json.', 422) from error
    require(isinstance(manifest, dict) and manifest.get('format') == BACKUP, 'That is not a Dramatis backup.', 422)
    require(manifest.get('version') == 1, 'That backup was made by a newer Dramatis. Update Dramatis to bring it back.',
            409)
    return {info.filename: info for info in infos if ENTRY.match(info.filename)}


def record_of(archive: zipfile.ZipFile, name: str, kind: str) -> dict | None:
    """A character or cast from the backup, in the current schema and whole, or None when it can't be read."""
    folder, stem, _ = ENTRY.match(name).groups()
    try:
        record = json.loads(archive.read(name))
        if not isinstance(record, dict) or record.get('id') != stem:
            return None
        record = records.migrated(record, kind, Path(name))
        if kind == 'character':
            Character.model_validate(record['character'])
        else:
            casts.checked(record['cast'])
        return record
    except (DomainError, ValueError, KeyError, TypeError):
        return None


def restore(data: bytes) -> dict:
    """Brings back every character and cast in the backup that this library does not have. One already here is left
    as it is, since it may be newer than the backup; a file that can't be read is counted and left out."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise DomainError('That is not a Dramatis backup: it is not a zip file.', 422) from error
    added = {'characters': 0, 'casts': 0}
    kept = skipped = 0
    with archive, records.LOCK:
        found = entries(archive)
        for name in sorted(found):
            folder, stem, suffix = ENTRY.match(name).groups()
            if suffix != 'json':
                continue
            kind = 'character' if folder == 'characters' else 'cast'
            target = library.path_of(stem) if kind == 'character' else casts.path_of(stem)
            if target.is_file():
                kept += 1
                continue
            record = record_of(archive, name, kind)
            if record is None:
                skipped += 1
                continue
            records.store(target, record | {'revision': record['revision'] - 1}, kind)
            added[folder] += 1
            picture = f'characters/{stem}.png'
            if kind == 'character' and picture in found:
                data = archive.read(picture)
                if data.startswith(library.PNG) and len(data) <= library.MAX_PORTRAIT:
                    library.write(library.path_of(stem, '.png'), data)
    return added | {'kept': kept, 'skipped': skipped}


# ---- Open a cast file ---------------------------------------------------------------------------------------------

REFERENCES = ('character_id', 'from', 'to', 'focus_id')


def relinked(value, ids: dict[str, str]):
    """The cast with each character id it names swapped for the one it has in this library."""
    if isinstance(value, list):
        return [relinked(item, ids) for item in value]
    if isinstance(value, dict):
        return {key: ids.get(item, item) if key in REFERENCES and isinstance(item, str) else relinked(item, ids)
                for key, item in value.items()}
    return value


def import_cast(data: bytes) -> dict:
    """A cast file (casts.export) as a new cast here. A character it carries that this library already has by id is
    linked as they are here; any other comes in as a new character. Nothing already here is changed."""
    try:
        bundle = json.loads(data)
    except ValueError as error:
        raise DomainError('That is not a cast file: it is not JSON.', 422) from error
    require(isinstance(bundle, dict) and bundle.get('format') == 'prospero-cast',
            'That is not a cast file. A cast file is what Export cast makes.', 422)
    require(bundle.get('version') == 1, 'That cast file was made by a newer Dramatis. Update Dramatis to open it.', 409)
    cast = casts.checked(bundle.get('cast'))
    carried = bundle.get('characters') if isinstance(bundle.get('characters'), dict) else {}
    ids, added = {}, 0
    for old_id in casts.mentioned(cast):
        if old_id.isalnum() and library.path_of(old_id).is_file():
            continue
        raw = carried.get(old_id)
        if not isinstance(raw, dict):
            continue
        try:
            character = Character.model_validate(raw)
        except ValueError:
            continue
        ids[old_id] = library.save(character)['id']
        added += 1
    saved = casts.save(casts.checked(relinked(casts.dumped(cast), ids)))
    return {'cast': saved, 'added': added}


# ---- Routes -------------------------------------------------------------------------------------------------------

class Body(BaseModel):
    model_config = {'extra': 'forbid'}


class BackupBody(Body):
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=700_000_000)


class CastFileBody(Body):
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=40_000_000)


router = APIRouter(prefix='/api/library')


@router.post('/characters/{character_id}/duplicate')
def duplicate_route(character_id: str):
    return duplicate(character_id)


@router.get('/characters/{character_id}/casts')
def casts_route(character_id: str):
    library.get(character_id)
    return casts_of(character_id)


@router.get('/backup.zip')
def backup_route():
    name, data = backup()
    return Response(data, media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="{name}"'})


@router.post('/backup')
def restore_route(body: BackupBody):
    return restore(decoded(body.data, 'backup'))


@router.post('/casts/import')
def import_route(body: CastFileBody):
    return import_cast(decoded(body.data, 'cast file'))
