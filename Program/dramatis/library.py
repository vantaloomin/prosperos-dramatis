"""The character library: one JSON file per character in Dramatis' folder (characters/<id>.json), and their portrait
beside it (<id>.png) when they have one. Saves write a whole file at a time, through a temporary file, so a crash
never leaves half a character."""
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from dramatis import settings
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


def write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    partial.write_bytes(data)
    partial.replace(path)


def summary(record: dict) -> dict:
    character = record['character']
    return {'id': record['id'], 'name': character.get('name') or 'Unnamed', 'about': character.get('about', '')[:200],
            'apps': character.get('apps', []), 'updated': record['updated'], 'portrait': record['portrait']}


def listing() -> list[dict]:
    records = []
    for path in folder().glob('*.json') if folder().is_dir() else []:
        try:
            records.append(summary(json.loads(path.read_text(encoding='utf-8'))))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(records, key=lambda record: record['updated'], reverse=True)


def get(character_id: str) -> dict:
    path = path_of(character_id)
    if not path.is_file():
        raise DomainError('That character is not in this library any more.', 404)
    record = json.loads(path.read_text(encoding='utf-8'))
    record['portrait'] = path_of(character_id, '.png').is_file()
    return record


def save(character: Character, character_id: str | None = None, seed: str = '') -> dict:
    """A new character, or a new version of one already here."""
    if character_id:
        record = get(character_id) | {'character': character.model_dump(), 'updated': now()}
    else:
        stamp = now()
        record = {'id': secrets.token_hex(ID_LENGTH // 2), 'created': stamp, 'updated': stamp,
                  'seed': seed or secrets.token_hex(5), 'character': character.model_dump(), 'portrait': False}
    write(path_of(record['id']), (json.dumps(record, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    return get(record['id'])


def delete(character_id: str):
    get(character_id)
    path_of(character_id).unlink(missing_ok=True)
    path_of(character_id, '.png').unlink(missing_ok=True)


def portrait(character_id: str) -> bytes | None:
    path = path_of(character_id, '.png')
    return path.read_bytes() if path.is_file() else None


def set_portrait(character_id: str, data: bytes | None) -> dict:
    """Their portrait, a PNG (the picture a PNG card is made from), or None to take it away."""
    get(character_id)
    if data is None:
        path_of(character_id, '.png').unlink(missing_ok=True)
    else:
        require(data.startswith(PNG), 'Choose a PNG picture. A JPEG can be saved as PNG in any picture editor.', 422)
        require(len(data) <= MAX_PORTRAIT, 'Portraits are limited to 10 MB.', 422)
        write(path_of(character_id, '.png'), data)
    return get(character_id)
