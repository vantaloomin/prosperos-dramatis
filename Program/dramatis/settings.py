"""Dramatis' own folder: settings.json and the character library (DRAMATIS_HOME overrides where).

- `model`: the model profiles and which one does each job (dramatis/profiles.py); their keys are in the system
  keyring, not here.
- `image`: which image maker draws portraits (dramatis/images.py), off until set; its key is in the keyring too.
"""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from dramatis import records

KEYS = ('model', 'image')
# What happened to a settings file that could not be read, said once on the screen (`notice`).
NOTICE: list[str] = []


def home() -> Path:
    if os.environ.get('DRAMATIS_HOME'):
        return Path(os.environ['DRAMATIS_HOME'])
    if os.name == 'nt' and os.environ.get('APPDATA'):
        return Path(os.environ['APPDATA']) / 'ProsperoDramatis'
    return Path.home() / '.prosperos-dramatis'


def path() -> Path:
    return home() / 'settings.json'


def load() -> dict:
    """The settings. A file that is there but cannot be read is moved aside, never quietly read as empty: the models
    and image maker start over, and `notice` says where the old file went."""
    try:
        saved = json.loads(path().read_text(encoding='utf-8'))
    except FileNotFoundError:
        saved = {}
    except (OSError, ValueError):
        saved = set_aside()
    saved = saved if isinstance(saved, dict) else set_aside()
    return {key: saved.get(key) if isinstance(saved.get(key), dict) else {} for key in KEYS}


def set_aside() -> dict:
    stamp = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')
    aside = path().with_name(f'settings.unreadable-{stamp}.json')
    try:
        path().replace(aside)
    except OSError:
        return {}
    NOTICE.append(f"Your settings file couldn't be read, so your models and image maker start over. The old file is "
                  f'kept as {aside}.')
    return {}


def notice() -> str:
    """What the screen should say about the settings file, once."""
    said = ' '.join(NOTICE)
    NOTICE.clear()
    return said


def save(settings: dict) -> dict:
    with records.LOCK:
        kept = load() | {key: settings[key] for key in KEYS if key in settings}
        records.write(path(), (json.dumps(kept, indent=2) + '\n').encode('utf-8'))
    return load()
