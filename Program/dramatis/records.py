"""How Dramatis keeps a file in its folder: characters (dramatis/library.py) and casts (dramatis/casts.py) alike.

- **Whole files, safely.** A file is written to a temporary file of its own beside it and moved into place, so a crash
  never leaves half a record, and two saves at once never write through the same temporary file.
- **A schema number and migrations.** Every record says which `schema` it was written in. Opening an older one runs
  the steps in `MIGRATIONS` from its number up, in order, so a field renamed or removed later never makes an old file
  unreadable; it is written in the new schema the next time it is saved. A record from a newer Dramatis is refused
  rather than changed.
- **A revision for each save.** `revision` counts the saves; a save may say which revision it was made from, and one
  made from an older revision (another tab, another window) is refused rather than silently written over the newer.
- **A file that cannot be read** is named in the error, and the rest of the library carries on.
"""
import json
import secrets
import threading
from collections.abc import Callable
from pathlib import Path

from dramatis.formats.companion.errors import DomainError

# One lock for every read-compare-write, so a stale save can never slip in between the check and the write.
LOCK = threading.RLock()


def drop_intimacy(record: dict) -> dict:
    """Schema 0 to 1, characters: early saves kept a Companion `intimacy` part the character never had a field for."""
    if isinstance(record.get('character'), dict):
        record['character'].pop('intimacy', None)
    return record


# Per kind of record: step N takes a record in schema N to schema N + 1. A new schema is one more step on the end.
MIGRATIONS: dict[str, list[Callable[[dict], dict]]] = {
    'character': [drop_intimacy],
    'cast': [lambda record: record],
}


def schema(kind: str) -> int:
    return len(MIGRATIONS[kind])


def migrated(record: dict, kind: str, path: Path) -> dict:
    found = record.get('schema', 0)
    if not isinstance(found, int) or found < 0:
        raise unreadable(path, 'its schema number is not one Dramatis knows')
    if found > schema(kind):
        raise DomainError(f'{path.name} was saved by a newer Dramatis. Update Dramatis to open it.', 409, 'newer')
    for step in MIGRATIONS[kind][found:]:
        record = step(record)
    return record | {'schema': schema(kind), 'revision': record.get('revision', 0)}


def unreadable(path: Path, why: str) -> DomainError:
    return DomainError(f"{path.parent.name}/{path.name} can't be read ({why}). The rest of the library is fine; "
                       'move that file aside or restore it from a backup.', 422, 'unreadable')


def read(path: Path, kind: str) -> dict:
    """A record from its file, in the current schema."""
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except OSError as error:
        raise unreadable(path, error.strerror or 'it could not be opened') from error
    except ValueError as error:
        raise unreadable(path, 'it is not whole JSON') from error
    if not isinstance(record, dict) or not isinstance(record.get('id'), str):
        raise unreadable(path, 'it is not a Dramatis record')
    return migrated(record, kind, path)


def write(path: Path, data: bytes):
    """A whole file, through a temporary file of its own, moved into place in one step."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f'{path.name}.{secrets.token_hex(4)}.partial')
    try:
        partial.write_bytes(data)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def store(path: Path, record: dict, kind: str):
    """A record written whole, in the current schema, one revision on."""
    kept = {key: value for key, value in record.items() if key != 'portrait'}
    kept |= {'schema': schema(kind), 'revision': record.get('revision', 0) + 1}
    write(path, (json.dumps(kept, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))


def current(record: dict, revision: int | None, what: str):
    """Refuses a save made from an older revision than the one on disk."""
    if revision is not None and revision != record.get('revision', 0):
        raise DomainError(f'{what} changed somewhere else (another tab or window) since this was opened. Saving now '
                          'would write over that.', 409, 'stale')
