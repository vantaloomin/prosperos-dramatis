"""The character library: one JSON file per character in Dramatis' folder (characters/<id>.json), and their portrait
beside it (<id>.png) when they have one. Files are kept as dramatis/records.py keeps them: whole, with a schema
number and a revision for each save."""
import secrets
from datetime import UTC, datetime
from pathlib import Path

from dramatis import records, settings
from dramatis.character import Character
from dramatis.formats.companion.errors import DomainError, require

ID_LENGTH = 12
PNG = b'\x89PNG\r\n\x1a\n'
MAX_PORTRAIT = 10 * 1024 * 1024


def folder() -> Path:
    return settings.home() / 'characters'


def now() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


def path_of(character_id: str, suffix: str = '.json') -> Path:
    require(character_id.isalnum() and len(character_id) <= 40, 'That is not a character in this library.', 404)
    return folder() / f'{character_id}{suffix}'


write = records.write


def summary(record: dict) -> dict:
    character = record['character']
    return {'id': record['id'], 'name': character.get('name') or 'Unnamed', 'about': character.get('about', '')[:200],
            'apps': character.get('apps', []), 'updated': record['updated'],
            'portrait': path_of(record['id'], '.png').is_file()}


def listing() -> list[dict]:
    """Every character, newest first. A file that cannot be read is listed by its name at the end, so it is never
    lost quietly; opening it says what is wrong."""
    found, broken = [], []
    for path in folder().glob('*.json') if folder().is_dir() else []:
        try:
            found.append(summary(records.read(path, 'character')))
        except (DomainError, KeyError, TypeError, AttributeError):
            if path.stem.isalnum():
                broken.append({'id': path.stem, 'name': path.name, 'about': '', 'apps': [], 'updated': '',
                               'portrait': False, 'broken': True})
    return sorted(found, key=lambda record: record['updated'], reverse=True) + broken


def get(character_id: str) -> dict:
    path = path_of(character_id)
    if not path.is_file():
        raise DomainError('That character is not in this library any more.', 404)
    record = records.read(path, 'character')
    record['portrait'] = path_of(character_id, '.png').is_file()
    return record


def save(character: Character, character_id: str | None = None, seed: str = '', revision: int | None = None) -> dict:
    """A new character, or a new version of one already here; with `revision`, only over the version it was made
    from (dramatis/records.py `current`)."""
    if character_id:
        with records.LOCK:
            record = get(character_id)
            records.current(record, revision, record['character'].get('name') or 'This character')
            return store(record | {'character': character.model_dump(), 'updated': now()})
    else:
        stamp = now()
        record = {'id': secrets.token_hex(ID_LENGTH // 2), 'created': stamp, 'updated': stamp,
                  'seed': seed or secrets.token_hex(5), 'character': character.model_dump()}
    return store(record)


def delete(character_id: str):
    get(character_id)
    try:
        path_of(character_id).unlink(missing_ok=True)
        path_of(character_id, '.png').unlink(missing_ok=True)
    except OSError as error:
        raise DomainError('They could not be deleted: another program has their file open. Close it and try again.',
                          409, 'in_use') from error


def portrait(character_id: str) -> bytes | None:
    path = path_of(character_id, '.png')
    return path.read_bytes() if path.is_file() else None


def set_portrait(character_id: str, data: bytes | None) -> dict:
    """Their portrait, a PNG (the picture a PNG card is made from), or None to take it away. It counts as a change to
    them, so the library's thumbnail and the card's modification date follow it."""
    with records.LOCK:
        record = get(character_id)
        if data is None:
            path_of(character_id, '.png').unlink(missing_ok=True)
        else:
            require(data.startswith(PNG), 'Choose a PNG picture. A JPEG can be saved as PNG in any picture editor.', 422)
            require(len(data) <= MAX_PORTRAIT, 'Portraits are limited to 10 MB.', 422)
            write(path_of(character_id, '.png'), data)
        return store(record | {'updated': now()})


def store(record: dict) -> dict:
    """A character's file, written whole. Whether they have a portrait is read from the picture itself."""
    records.store(path_of(record['id']), record, 'character')
    return get(record['id'])
